const API = "http://127.0.0.1:9835";
const HEADERS = { "X-BeatGrab": "1" };
const $ = (id) => document.getElementById(id);

let tab = null;
let helperUp = false;
let busy = false;

// Returns the 11-character video id, or null if this tab isn't a single video.
function videoId(url) {
  try {
    const u = new URL(url);
    let id = null;
    if (u.hostname === "youtu.be") id = u.pathname.slice(1);
    else if (/(^|\.)youtube\.com$/.test(u.hostname)) {
      if (u.pathname === "/watch") id = u.searchParams.get("v");
      else if (u.pathname.startsWith("/shorts/")) id = u.pathname.split("/")[2];
    }
    return /^[A-Za-z0-9_-]{11}$/.test(id || "") ? id : null;
  } catch (e) {
    return null;
  }
}

function clock(seconds) {
  if (!Number.isFinite(seconds)) return "?";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${rest}` : `${m}:${rest}`;
}

function setResult(text, kind) {
  $("result").textContent = text;
  $("result").className = kind || "";
}

function refresh() {
  const id = tab && videoId(tab.url);
  if (!id) $("video").textContent = "Open a YouTube video to send it to FL Studio.";
  $("send").disabled = busy || !id || !helperUp;
  $("send").textContent = busy ? "Sending..." : "Send to FL";
}

function showVideo() {
  const id = videoId(tab.url);
  if (!id) return;
  $("video").textContent = (tab.title || "").replace(/^\(\d+\)\s*/, "").replace(/ - YouTube$/, "");
  $("thumb").src = `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;
  $("thumb").hidden = false;
}

// BPM and key come from what the uploader wrote in the title/description.
async function loadDetails() {
  if (!videoId(tab.url)) return;
  $("details").hidden = false;
  try {
    const res = await fetch(API + "/info?url=" + encodeURIComponent(tab.url), { headers: HEADERS });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    if (data.title) $("video").textContent = data.title;
    $("uploader").textContent = data.uploader || "";
    $("bpm").textContent = data.bpm || "Not listed";
    $("key").textContent = data.key || "Not listed";
    $("length").textContent = clock(data.duration);
  } catch (e) {
    for (const id of ["bpm", "key", "length"]) $(id).textContent = "?";
  }
}

async function ping() {
  return (await fetch(API + "/ping")).json();
}

async function checkHelper() {
  let data = null;
  let error = "";
  try {
    data = await ping();
  } catch (e) {
    // Normally Chrome started it already; if not, ask the background to start it.
    $("helper-text").textContent = "Starting helper...";
    const started = await chrome.runtime.sendMessage({ type: "start-helper" }).catch(() => null);
    if (started && started.ok) data = await ping().catch(() => null);
    else error = (started && started.error) || "";
  }
  try {
    if (!data) throw new Error(error);
    helperUp = true;
    $("dot").className = "on";
    $("helper-text").textContent = "Helper running";
    $("folder").textContent = "Saves to: " + data.folder;
    $("change").hidden = false;
  } catch (e) {
    helperUp = false;
    $("change").hidden = true;
    $("dot").className = "off";
    $("helper-text").textContent = "Helper not running";
    $("folder").textContent = e.message || "Restart Chrome, or double-click start-beatgrab.bat.";
  }
  refresh();
  if (helperUp) loadDetails();
}

async function send() {
  busy = true;
  setResult("Downloading... you can close this window, you'll get a notification.");
  refresh();
  let result;
  try {
    result = await chrome.runtime.sendMessage({ type: "grab", url: tab.url, tabId: tab.id });
  } catch (e) {
    result = { ok: false, error: e.message };
  }
  busy = false;
  if (result && result.ok) setResult("Sent: " + result.file.split(/[\\/]/).pop(), "ok");
  else setResult((result && result.error) || "Download failed", "err");
  refresh();
}

$("send").addEventListener("click", send);

// Opens the normal Windows "choose a folder" window (it comes from the helper).
// This popup usually closes when that window takes focus; the choice is saved
// either way and shows here next time.
$("change").addEventListener("click", async () => {
  $("change").disabled = true;
  try {
    const res = await fetch(API + "/pick-folder", { method: "POST", headers: HEADERS });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    $("folder").textContent = "Saves to: " + data.folder;
  } catch (e) {
    setResult(e.message || "Could not change the folder", "err");
  }
  $("change").disabled = false;
});

// The format choice is remembered and also used by the in-page button and Alt+Shift+G.
for (const input of document.querySelectorAll('input[name="format"]')) {
  input.addEventListener("change", () => chrome.storage.local.set({ format: input.value }));
}

(async () => {
  const { format } = await chrome.storage.local.get({ format: "mp3" });
  document.querySelector(`input[name="format"][value="${format === "wav" ? "wav" : "mp3"}"]`).checked = true;
  [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) showVideo();
  refresh();
  checkHelper();
})();
