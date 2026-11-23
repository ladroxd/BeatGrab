#!/usr/bin/env python3
"""BeatGrab helper: receives a YouTube link from the Chrome extension,
downloads it as MP3 into your BeatGrab folder, and shows the file so you can
drag it into FL Studio.

Needs:  pip install -U "yt-dlp[default]"   and   ffmpeg + Node.js (or Deno) on PATH.
Run:    python install.py once, and Chrome starts and stops this helper itself.
        python beatgrab.py runs it by hand in a console (for troubleshooting).
"""
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

PORT = int(os.environ.get("BEATGRAB_PORT", "9835"))
CONFIG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "BeatGrab" / "config.json"


def load_out_dir():
    """Folder picked in the extension popup, else BEATGRAB_DIR, else ~/Music/BeatGrab."""
    try:
        folder = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("folder")
        if folder and Path(folder).is_absolute():
            return Path(folder)
    except (OSError, ValueError, AttributeError):
        pass
    return Path(os.environ.get("BEATGRAB_DIR", Path.home() / "Music" / "BeatGrab"))


OUT_DIR = load_out_dir()
PICKER_LOCK = threading.Lock()
# Runs in its own process so the dialog gets a proper main thread.
PICKER_SCRIPT = """
import sys, tkinter
from tkinter import filedialog
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.update()
chosen = filedialog.askdirectory(parent=root, initialdir=sys.argv[1], mustexist=False,
                                 title="BeatGrab: where should beats be saved?")
sys.stdout.buffer.write(chosen.encode("utf-8"))
"""


def pick_folder():
    """Show the Windows folder picker and remember the choice. Returns the folder in use."""
    global OUT_DIR
    if not PICKER_LOCK.acquire(blocking=False):
        raise RuntimeError("The folder window is already open (check your taskbar).")
    try:
        start = OUT_DIR if OUT_DIR.is_dir() else Path.home()
        proc = subprocess.run([sys.executable, "-c", PICKER_SCRIPT, str(start)],
                              stdin=subprocess.DEVNULL, capture_output=True)
        chosen = proc.stdout.decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise RuntimeError("Could not open the folder window.")
        if chosen:  # empty = cancelled
            folder = Path(chosen).resolve()
            folder.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps({"folder": str(folder)}), encoding="utf-8")
            OUT_DIR = folder
            print("Save folder is now:", folder)
        return OUT_DIR
    finally:
        PICKER_LOCK.release()
REVEAL = os.environ.get("BEATGRAB_REVEAL", "1") != "0"
YT_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
MAX_JOBS = 50

JOBS = {}  # job id -> {"state": "working" | "done" | "error", "file": str, "error": str}
JOBS_LOCK = threading.Lock()


def clean_url(raw):
    """Return a canonical watch URL, or None if this isn't a single YouTube video."""
    try:
        u = urlparse(raw)
    except Exception:
        return None
    if u.scheme not in ("http", "https") or u.hostname not in YT_HOSTS:
        return None
    if u.hostname == "youtu.be":
        vid = u.path.strip("/")
    elif u.path == "/watch":
        vid = parse_qs(u.query).get("v", [""])[0]
    elif u.path.startswith("/shorts/"):
        vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
    else:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        return None
    return f"https://www.youtube.com/watch?v={vid}"


def js_runtime_args():
    """yt-dlp needs a JavaScript runtime for YouTube. Deno is picked up on its
    own; Node has to be enabled explicitly."""
    if shutil.which("deno"):
        return []
    if shutil.which("node"):
        return ["--js-runtimes", "node"]
    return []


def reveal(path):
    """Open the folder with the file selected, so it's ready to drag."""
    try:
        system = platform.system()
        if system == "Windows":
            # Explorer only accepts quotes around the path itself, not around the
            # whole "/select,..." argument, so build the command line by hand.
            # (No shell involved, and Windows filenames can't contain quotes.)
            subprocess.Popen(f'explorer /select,"{Path(path).resolve()}"', stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(Path(path).parent)])
    except Exception:
        pass


BPM_PATTERNS = [
    re.compile(r"(?<![\d.])(\d{2,3})(?:\.\d+)?\s*-?\s*(?i:bpm)\b"),      # "129 BPM"
    re.compile(r"\b(?i:bpm)\s*[:\-–=]?\s*(\d{2,3})(?![\d])"),            # "BPM: 129"
]
_ACC = r"([#b♯♭]|\s?(?i:sharp|flat))?"
_MODE = r"((?i:major|minor|maj|min))"
KEY_PATTERNS = [
    # "Key: F#m", "key of C", "KEY - Bb minor"
    re.compile(r"\b(?i:key)\b\s*[:\-–=]?\s*(?:(?i:of)\s+)?([A-G])" + _ACC + r"\s*-?\s*((?i:major|minor|maj|min)|m)?(?![A-Za-z])"),
    # "F# minor", "C Major", "Amin"
    re.compile(r"(?<![A-Za-z])([A-G])" + _ACC + r"\s*-?\s*" + _MODE + r"(?![A-Za-z])"),
    # "F#m", "Cm" ("Am" only when it isn't the word in "I Am", "Dm" not in "Dm me")
    re.compile(r"(?<![A-Za-z#])(?<!I )([A-G])([#b♯♭])?(m)(?![A-Za-z#])(?!\s+(?i:me|us)\b)"),
]


def find_bpm(text):
    for pattern in BPM_PATTERNS:
        for m in pattern.finditer(text):
            if 40 <= int(m.group(1)) <= 300:
                return int(m.group(1))
    return None


def find_key(text):
    for pattern in KEY_PATTERNS:
        m = pattern.search(text)
        if m:
            acc = (m.group(2) or "").strip().lower()
            acc = {"♯": "#", "sharp": "#", "♭": "b", "flat": "b"}.get(acc, acc)
            mode = (m.group(3) or "").lower()
            minor = mode == "m" or mode.startswith("min")
            return f"{m.group(1)}{acc} {'minor' if minor else 'major'}"
    return None


def short_key(key):
    """"A minor" -> "Am", "C# major" -> "C#", for filenames."""
    note, mode = key.split()
    return note + ("m" if mode == "minor" else "")


def file_prefix(details):
    """"[140 BPM - Am] ", "[140 BPM] ", "[Am] " or "" when neither is known."""
    parts = []
    if details.get("bpm"):
        parts.append(f"{details['bpm']} BPM")
    if details.get("key"):
        parts.append(short_key(details["key"]))
    return f"[{' - '.join(parts)}] " if parts else ""


# ---- BeatStars ---------------------------------------------------------------
# Most beat uploads link the beat on BeatStars, where the producer filled in BPM
# and key as fields. Links are either bsta.rs short links or beatstars.com pages.
BEATSTARS_LINK = re.compile(r"https?://(?:bsta\.rs|(?:[\w-]+\.)*beatstars\.com)/[^\s<>\"'()\[\]]*", re.I)
TRACK_ID_PATTERNS = [
    re.compile(r"[?&]trackId=(\d+)", re.I),                      # player.beatstars.com/?trackId=123
    re.compile(r"/beat/(?:[^/?#\s]*-)?(\d{4,})(?=[/?#]|$)"),     # /beat/some-title-123 or /beat/123
]
WEB_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BeatGrab"}
WEB_TIMEOUT = 6
MAX_STORE_LINKS = 3


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # makes urllib raise the 3xx, so we can read where it points


def redirect_target(link):
    """Where a short link points, without visiting the destination."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(urllib.request.Request(link, headers=WEB_HEADERS), timeout=WEB_TIMEOUT).close()
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400 and e.headers.get("Location"):
            return urljoin(link, e.headers["Location"])
    except (OSError, ValueError):
        pass
    return None


def beatstars_track_id(link):
    """Track id from a BeatStars link, following bsta.rs short links (never other sites)."""
    for _ in range(3):
        for pattern in TRACK_ID_PATTERNS:
            m = pattern.search(link)
            if m:
                return m.group(1)
        if (urlparse(link).hostname or "").lower() != "bsta.rs":
            return None  # a store front page, not a single beat
        link = redirect_target(link)
        if not link:
            return None
    return None


def beatstars_details(text):
    """BPM and key from the first BeatStars beat linked in `text`."""
    links = list(dict.fromkeys(m.group(0).rstrip(".,;:!") for m in BEATSTARS_LINK.finditer(text)))
    for link in links[:MAX_STORE_LINKS]:
        track = beatstars_track_id(link)
        if not track:
            continue
        api = f"https://main.v2.beatstars.com/beat?id={track}&fields=details"
        try:
            with urllib.request.urlopen(urllib.request.Request(api, headers=WEB_HEADERS),
                                        timeout=WEB_TIMEOUT) as resp:
                details = json.load(resp)["response"]["data"]["details"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        try:
            bpm = round(float(details.get("bpm") or 0))
        except (TypeError, ValueError):
            bpm = 0
        # key_note looks like "A_SHARP_MINOR", "D_MINOR", "E_FLAT_MAJOR"
        m = re.fullmatch(r"([A-G])(?:_(SHARP|FLAT))?_(MAJOR|MINOR)", str(details.get("key_note") or "").upper())
        key = f"{m.group(1)}{'#' if m.group(2) == 'SHARP' else 'b' if m.group(2) else ''} {m.group(3).lower()}" if m else None
        if 40 <= bpm <= 300 or key:
            return {"bpm": bpm if 40 <= bpm <= 300 else None, "key": key}
    return None


def uploader_comments(comments):
    """Top-level comments by the uploader, plus the pinned one, pinned first."""
    picked = [c for c in comments or [] if isinstance(c, dict)
              and (c.get("author_is_uploader") or c.get("is_pinned")) and c.get("parent", "root") == "root"]
    picked.sort(key=lambda c: not c.get("is_pinned"))
    return [str(c.get("text") or "") for c in picked]


def beat_details(title, description, tags, comments=()):
    """BPM and key as the uploader wrote them. Looks in order at the title, the
    description, the uploader's own comments (pinned first), the BeatStars page
    linked in either, and the tags. Each value comes from the first place that has it."""
    comment_text = "\n".join(comments)
    sources = [
        ("title", lambda: title),
        ("description", lambda: description),
        ("uploader's comment", lambda: comment_text),
        ("BeatStars page", lambda: beatstars_details(f"{description}\n{comment_text}")),
        ("tags", lambda: ", ".join(tags)),
    ]
    found = {"bpm": None, "key": None, "found_in": {}}
    for name, get in sources:
        if found["bpm"] and found["key"]:
            break
        value = get()
        if isinstance(value, str):
            value = {"bpm": find_bpm(value), "key": find_key(value)}
        for field in ("bpm", "key"):
            if not found[field] and value and value.get(field):
                found[field] = value[field]
                found["found_in"][field] = name
    return found


def run_ytdlp(cmd):
    # Force UTF-8 so titles with accents/emoji come back as a usable path.
    # stdin is closed off so yt-dlp never touches Chrome's message pipe.
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                          encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout).strip().splitlines()
        errors = [l for l in lines if l.startswith("ERROR")] or lines[-2:]
        raise RuntimeError(" | ".join(errors) or "yt-dlp failed")
    return proc


INFO_CACHE = {}  # url -> info dict
INFO_LOCKS = {}  # url -> lock, so the popup and a download don't look up the same video twice
INFO_LOCKS_GUARD = threading.Lock()
# The top comments are enough to catch the uploader's pinned one; no replies.
COMMENT_ARGS = ["--write-comments", "--extractor-args", "youtube:max_comments=20,20,0,0;comment_sort=top"]


def info(url):
    """Title, uploader, length, BPM and key for a video, without downloading it."""
    with INFO_LOCKS_GUARD:
        lock = INFO_LOCKS.setdefault(url, threading.Lock())
    with lock:
        if url in INFO_CACHE:
            return INFO_CACHE[url]
        cmd = [
            sys.executable, "-m", "yt_dlp",
            *js_runtime_args(),
            "--no-playlist", "--skip-download", "--no-warnings", *COMMENT_ARGS, "--dump-single-json",
            url,
        ]
        proc = run_ytdlp(cmd)
        data = json.loads(proc.stdout)
        title = str(data.get("title") or "")
        result = {
            "title": title,
            "uploader": str(data.get("uploader") or data.get("channel") or ""),
            "duration": data.get("duration"),
            **beat_details(title, str(data.get("description") or ""), [str(t) for t in data.get("tags") or []],
                           uploader_comments(data.get("comments"))),
        }
        with INFO_LOCKS_GUARD:
            while len(INFO_CACHE) >= MAX_JOBS:
                old = next(iter(INFO_CACHE))
                INFO_CACHE.pop(old)
                INFO_LOCKS.pop(old, None)
            INFO_CACHE[url] = result
        return result


def add_prefix(path, details):
    """Rename "Title.mp3" to "[140 BPM - Am] Title.mp3". Keeps the old name if that fails."""
    prefix = file_prefix(details)
    if not prefix:
        return path
    target = path.with_name(prefix + path.name)
    try:
        os.replace(path, target)  # replaces an earlier download of the same beat
    except OSError as e:
        print("Could not add BPM/key to the filename:", e)
        return path
    return target


def grab(url, fmt="mp3"):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Look up BPM and key while the audio downloads (usually cached from the
    # toolbar window already), then put them in front of the filename.
    details = {}

    def lookup():
        try:
            details.update(info(url))
        except Exception as e:
            print("No BPM/key for the filename:", e)

    lookup_thread = threading.Thread(target=lookup, daemon=True)
    lookup_thread.start()
    if fmt == "wav":
        # WAV can't hold cover art, so no thumbnail there.
        audio_args = ["-x", "--audio-format", "wav", "--embed-metadata"]
    else:
        audio_args = ["-x", "--audio-format", "mp3", "--audio-quality", "0",
                      "--embed-metadata", "--embed-thumbnail"]
    cmd = [
        sys.executable, "-m", "yt_dlp",
        *js_runtime_args(),
        *audio_args,
        "--no-playlist", "--windows-filenames",
        "--no-simulate", "--print", "after_move:filepath",
        "-o", str(OUT_DIR / "%(title).150B.%(ext)s"),
        url,
    ]
    proc = run_ytdlp(cmd)
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    if not lines:
        raise RuntimeError("yt-dlp finished but returned no file path")
    path = Path(lines[-1])
    if not path.is_file():
        raise RuntimeError(f"yt-dlp reported a file that isn't there: {path}")
    lookup_thread.join(timeout=60)
    return add_prefix(path, dict(details))


def run_job(job_id, url, fmt):
    try:
        path = grab(url, fmt)
    except Exception as e:
        print("FAILED:", e)
        result = {"state": "error", "error": str(e)}
    else:
        print("Saved:", path)
        if REVEAL:
            reveal(path)
        result = {"state": "done", "file": str(path)}
    with JOBS_LOCK:
        JOBS[job_id] = result


def start_job(url, fmt):
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        while len(JOBS) >= MAX_JOBS:  # forget the oldest jobs
            JOBS.pop(next(iter(JOBS)))
        JOBS[job_id] = {"state": "working"}
    threading.Thread(target=run_job, args=(job_id, url, fmt), daemon=True).start()
    return job_id


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _allowed(self, need_origin):
        """Only our extension may talk to us (blocks random websites). The custom
        header can't be sent cross-origin by a web page without a CORS preflight,
        which we never answer."""
        if self.headers.get("X-BeatGrab") != "1":
            return False
        origin = self.headers.get("Origin", "")
        if need_origin or origin:
            return origin.startswith("chrome-extension://")
        return True

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/ping":
            return self._send(200, {"ok": True, "folder": str(OUT_DIR)})
        if u.path == "/status":
            if not self._allowed(need_origin=False):
                return self._send(403, {"error": "forbidden"})
            job_id = parse_qs(u.query).get("job", [""])[0]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                return self._send(404, {"error": "unknown job (helper restarted?)"})
            return self._send(200, job)
        if u.path == "/info":
            if not self._allowed(need_origin=False):
                return self._send(403, {"error": "forbidden"})
            url = clean_url(parse_qs(u.query).get("url", [""])[0])
            if not url:
                return self._send(400, {"error": "open a single YouTube video first"})
            try:
                return self._send(200, info(url))
            except Exception as e:
                return self._send(500, {"error": str(e)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._allowed(need_origin=True):
            return self._send(403, {"error": "forbidden"})
        if self.path == "/pick-folder":
            # The folder can only be chosen by a person in a real Windows dialog,
            # never set to an arbitrary path by a request.
            try:
                return self._send(200, {"ok": True, "folder": str(pick_folder())})
            except Exception as e:
                return self._send(500, {"error": str(e)})
        if self.path != "/grab":
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(min(length, 10_000)) or b"{}")
        except Exception:
            return self._send(400, {"error": "bad request"})
        if not isinstance(data, dict):
            return self._send(400, {"error": "bad request"})
        url = clean_url(str(data.get("url", "")))
        if not url:
            return self._send(400, {"error": "open a single YouTube video first"})
        fmt = "wav" if data.get("format") == "wav" else "mp3"
        self._send(202, {"ok": True, "job": start_job(url, fmt)})

    def log_message(self, *a):
        pass


def check_setup():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print('WARNING: yt-dlp is not installed. Run:  pip install -U "yt-dlp[default]"')
    if not shutil.which("ffmpeg"):
        print("WARNING: ffmpeg is not on PATH. Run:  winget install ffmpeg  (then reopen this window)")
    if not (shutil.which("deno") or shutil.which("node")):
        print("WARNING: no Node.js or Deno found. YouTube downloads may fail. Run:  winget install OpenJS.NodeJS.LTS")


def serve_native():
    """Run as Chrome's native messaging host. Chrome starts us when the extension
    connects (at browser start) and closes our stdin when it quits, which is our
    cue to exit. stdout belongs to Chrome's message protocol, so prints go to stderr."""
    pipe_in, pipe_out = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr
    check_setup()
    state = {"server": None}

    def serve():
        # If another helper already has the port (a second Chrome profile, or one
        # started by hand), wait and take over when it goes away.
        while True:
            try:
                server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
            except OSError:
                time.sleep(2)
                continue
            state["server"] = server
            server.serve_forever()
            return

    threading.Thread(target=serve, daemon=True).start()

    def send(message):
        data = json.dumps(message).encode()
        pipe_out.write(struct.pack("=I", len(data)) + data)
        pipe_out.flush()

    while True:
        header = pipe_in.read(4)
        if len(header) < 4:
            break  # Chrome closed the pipe: it quit, or the extension was turned off
        size = struct.unpack("=I", header)[0]
        body = pipe_in.read(size)
        if len(body) < size:
            break
        try:
            message = json.loads(body)
        except ValueError:
            continue
        if isinstance(message, dict) and message.get("type") == "ping":
            send({"ok": True, "serving": state["server"] is not None, "folder": str(OUT_DIR)})
    os._exit(0)


if __name__ == "__main__":
    if "--native" in sys.argv[1:]:
        serve_native()
    check_setup()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        sys.exit(f"Port {PORT} is busy. BeatGrab is probably already running.")
    print(f"BeatGrab helper running on http://127.0.0.1:{PORT}")
    print(f"MP3s go to: {OUT_DIR}")
    print("Leave this window open. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
