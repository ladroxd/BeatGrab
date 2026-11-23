# Changelog

All notable changes to BeatGrab. Newest first.

## 1.8 - 2026-11-23

### Added
- BPM and key in front of the saved filename: `[140 BPM - Am] Title.mp3`,
  or just `[140 BPM]` / `[Am]` when only one is known. Nothing is added when
  neither is. The lookup runs while the audio downloads, so it adds no wait.
- BPM and key are also read from the uploader's own comments, pinned first.
- When YouTube doesn't have them, BPM and key come from the BeatStars beat
  linked in the description or a pinned comment (`bsta.rs` short links,
  `beatstars.com/beat/...` and `player.beatstars.com` links).
- Hovering BPM or key in the toolbar window shows where it was found.

### Changed
- Looking up a beat also reads its top 20 comments, in the same yt-dlp call.
  That adds about a second before BPM and key show in the toolbar window.
- The helper now contacts BeatStars as well as YouTube, only when a BeatStars
  beat is linked and YouTube doesn't list the BPM or key. The README's
  privacy section says so.
- "Dm me" is no longer read as the key D minor.
- The toolbar window and a download no longer look up the same video twice
  when both ask at once.

### Fixed
- ffmpeg or Node.js installed while Chrome was open is found without
  restarting Chrome. The helper reads the current PATH from Windows, and
  looks in winget's ffmpeg folder too.

### Notes
- After reinstalling or upgrading Python, run `install-beatgrab.bat` again
  and install yt-dlp for the new Python (`pip install -U "yt-dlp[default]"`).
  The helper is registered with one Python install, and Chrome reports
  "Helper not running" when that install is gone.

## 1.7 - 2026-11-16

### Added
- The helper starts when Chrome opens and stops when Chrome closes. It is
  registered as the extension's native messaging host; the extension
  connects at browser start, and Chrome closes the connection when it quits.
- `install-beatgrab.bat` (`helper/install.py`): one-time setup that registers
  the helper for Chrome, Edge and Chromium. `--uninstall` undoes it. It also
  removes the old Startup shortcut if there is one.
- If the helper stops while Chrome is open, the extension starts it again,
  backing off if it keeps failing. Sending a beat or opening the toolbar
  window also starts it if needed.
- Clear errors in the badge and toolbar window: "Helper not set up" versus
  "Helper not running".

### Changed
- The extension has a fixed ID (`key` in `manifest.json`). Updating from an
  older version needs the old card removed and the folder loaded again.
- `nativeMessaging` permission.
- A second helper (another Chrome profile, or one started by hand) waits for
  the port instead of failing, and takes over when the first one stops.
- The helper's child processes no longer inherit its standard input and
  output.

### Removed
- Auto-start with Windows through a Startup shortcut. Chrome starts the
  helper now.

## Docs - 2026-11-16

### Added
- `README.md` for GitHub: icon, download button, screenshot of the toolbar
  window, features, requirements, getting started, how it works and what is
  stored.
- `assets/popup.png`, a screenshot of the toolbar window with sample data.

### Changed
- The old `README.txt` moved to `docs/SETUP.md` as the full setup, usage and
  troubleshooting guide.

## 1.6 - 2026-11-16

### Added
- "Change folder" button in the toolbar window. It opens the normal Windows
  folder window; the choice is saved in `%APPDATA%\BeatGrab\config.json` and
  survives restarts.
- Helper endpoint `POST /pick-folder`. The folder can only be chosen by a
  person in the Windows dialog, never set to an arbitrary path by a request.

### Changed
- Save folder priority is now: folder picked in the toolbar window, then
  `BEATGRAB_DIR`, then `~/Music/BeatGrab`.

## 1.5 - 2026-11-16

### Added
- Beat details in the toolbar window: thumbnail, title, uploader, length, BPM
  and key. BPM and key are read from what the uploader wrote in the title,
  description or tags; nothing is detected from the audio.
- MP3 / WAV switch in the toolbar window. The choice is remembered and also
  applies to the in-page button and the keyboard shortcut.
- Helper endpoint `GET /info` and a `format` field on `POST /grab`.
- `storage` permission (for the format preference).

## 1.4 - 2026-11-16

### Added
- Toolbar window (popup) on the extension icon, with helper status, the
  current video, the send button and the save folder.

### Changed
- Clicking the toolbar icon opens the window instead of starting a download
  straight away. Alt+Shift+G still downloads directly.

## 1.3 - 2026-11-16

### Changed
- In-page button renamed from "MP3" to "Send to FL".

### Added
- Optional custom button image: save any picture as `extension/fl.png`.

## 1.2 - 2026-11-16

### Added
- In-page button next to the Like button on YouTube watch pages
  (`extension/content.js`). It survives YouTube's page-to-page navigation.

## 1.1 - 2026-11-16

First version tested end to end on Windows with real downloads.

### Added
- Chrome notification when a beat is saved or a download fails.
- Toolbar icon.
- Title, uploader and thumbnail embedded in the MP3.
- Startup checks: the helper warns if yt-dlp, ffmpeg or Node.js is missing,
  and says so if its port is already in use.
- Hidden auto-start with Windows through a Startup shortcut running
  `pythonw.exe`.

### Changed
- Downloads are now jobs: `POST /grab` answers at once with a job id and the
  extension polls `GET /status`, so Chrome can't kill the service worker
  during a long download.

### Fixed
- YouTube extraction failed without a JavaScript runtime. The helper now
  passes Node.js to yt-dlp when Deno isn't installed.
- The Explorer reveal opened Documents instead of the saved file when the
  path contained spaces.
- Titles and folders with accents or non-Latin characters could come back as
  a broken path. Output from yt-dlp is now read as UTF-8.

## 1.0

Initial build: MV3 extension with a toolbar button and Alt+Shift+G, plus a
local Python helper on `127.0.0.1:9835` that runs yt-dlp. Only tested against
a stub in a sandbox.
