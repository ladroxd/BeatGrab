# BeatGrab setup and usage

The full guide. For what BeatGrab is and what it does, see the
[README](../README.md).

## One-time setup (Windows)

1. Install Python from [python.org](https://www.python.org/downloads/) and
   tick **Add Python to PATH**.
2. Open Command Prompt and run:

   ```bat
   pip install -U "yt-dlp[default]"
   winget install ffmpeg
   winget install OpenJS.NodeJS.LTS
   ```

   Close and reopen Command Prompt afterwards. Node.js is needed because
   yt-dlp has to run YouTube's player JavaScript; Deno works too.
3. In Chrome, open `chrome://extensions`, turn on **Developer mode** (top
   right), click **Load unpacked** and pick the `extension` folder. Pin
   BeatGrab to the toolbar (puzzle icon, then the pin).
4. In FL Studio, open **Options > File settings > Browser extra search
   folders** and add your save folder. By default that is:

   ```
   C:\Users\<you>\Music\BeatGrab
   ```

   Every beat you send now shows up in FL Studio's Browser panel, ready to
   drag into the Playlist.
5. Optional, so you never have to start anything: press Win+R, type
   `shell:startup`, and in that folder create a shortcut named
   **BeatGrab helper** with this target (use your own paths):

   ```
   "C:\...\Python312\pythonw.exe" "C:\...\BeatGrab\helper\beatgrab.py"
   ```

   The helper then starts hidden every time you log in to Windows. Without
   this, double-click `start-beatgrab.bat` each time instead.

## Every day

1. With the Startup shortcut from step 5, the helper is already running,
   hidden. There is nothing to open.
2. On a YouTube video, click **Send to FL** next to the Like button, or press
   Alt+Shift+G.
3. Watch the toolbar icon's badge: `...` means downloading, `OK` means done,
   `ERR` means it failed. A Windows notification also tells you when the beat
   is saved or why it failed.
4. When it finishes, the save folder opens with the file selected, so you can
   also drag it straight from Explorer into FL Studio's Playlist.

## The toolbar window

Click the BeatGrab icon in Chrome's toolbar.

- **Beat details:** thumbnail, title, uploader and length, plus BPM and key
  when the uploader wrote them in the title, description or tags. Otherwise
  they show "Not listed". Nothing is detected from the audio.
- **MP3 / WAV switch:** the choice is remembered and also applies to the
  **Send to FL** button and the shortcut. WAV files are several times bigger
  and are not better quality than the MP3, because YouTube's audio is already
  compressed.
- **Change folder:** opens the normal Windows folder window. The toolbar
  window closes when you do that; the new folder shows next time you open it.
  Remember to add the new folder in FL Studio (setup step 4).

## Tips

- **Your own picture on the button:** save it as `extension\fl.png` and
  reload the extension.
- **Stop the folder opening after each download:** set `BEATGRAB_REVEAL=0`
  before starting the helper.
- **Downloads suddenly fail:** YouTube changed something. Run
  `pip install -U "yt-dlp[default]"`.
- **After editing anything in the `extension` folder:** press the reload
  arrow on the BeatGrab card in `chrome://extensions`, then refresh your
  YouTube tabs.
- **Tags:** the MP3 carries the video title, uploader and thumbnail. WAV
  carries no cover art.
- **Single videos only:** playlists are ignored on purpose.

## Troubleshooting

- **The badge shows `ERR`:** hover over the icon to read the reason. "Helper
  not running" means the helper needs starting (see below).
- **Stop the helper:** in Task Manager, end `pythonw.exe`. To stop it
  auto-starting, delete the Startup shortcut.
- **See what the helper is doing:** end `pythonw.exe` and double-click
  `start-beatgrab.bat` instead. It shows a console that warns if yt-dlp,
  ffmpeg or Node.js is missing and prints why a download failed.

## A note on use

Downloading from YouTube is against YouTube's terms. Keep BeatGrab for
personal listening and reference, and get a proper lease or license from the
producer before using any beat in a release.
