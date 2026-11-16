BEATGRAB - one click on a YouTube beat -> MP3 in a folder FL Studio can see
=========================================================================

ONE-TIME SETUP (Windows)
1. Install Python from python.org (tick "Add Python to PATH").
2. Open Command Prompt and run:
       pip install -U "yt-dlp[default]"
       winget install ffmpeg
       winget install OpenJS.NodeJS.LTS
   (close and reopen Command Prompt afterwards. Node.js is needed because
   yt-dlp has to run YouTube's player JavaScript; Deno works too.)
3. Chrome: open chrome://extensions, turn on Developer mode (top right),
   click "Load unpacked", pick the "extension" folder.
   Pin BeatGrab to the toolbar (puzzle icon -> pin).
4. FL Studio: Options > File settings > "Browser extra search folders" -> add
       C:\Users\<you>\Music\BeatGrab
   Now every grabbed beat shows up in FL's Browser panel; drag it into the Playlist.

5. Optional, so you never have to start anything: press Win+R, type
   shell:startup, and in that folder create a shortcut named
   "BeatGrab helper" with this target (use your own paths):
       "C:\...\Python312\pythonw.exe" "C:\...\BeatGrab\helper\beatgrab.py"
   The helper then starts hidden every time you log in to Windows.
   Without this, double-click start-beatgrab.bat each time instead.

EVERY DAY
1. With the Startup shortcut from step 5 the helper is already running,
   hidden. Nothing to open.
   To stop it: Task Manager > end "pythonw.exe". To stop it auto-starting:
   delete that shortcut.
   If something is wrong, end pythonw.exe and double-click start-beatgrab.bat
   instead: it shows a console that warns if yt-dlp, ffmpeg or Node.js is
   missing and prints why a download failed.
2. On a YouTube video, click "Send to FL" next to the Like button
   (or press Alt+Shift+G).
   Badge on the toolbar icon: ... = downloading, OK = done, ERR = failed.
   A Windows notification also tells you when it is saved or why it failed.

THE TOOLBAR WINDOW (click the BeatGrab icon)
- Shows the beat: thumbnail, title, uploader, length, plus BPM and key when
  the uploader wrote them in the title, description or tags ("Not listed"
  otherwise; nothing is detected from the audio).
- MP3 / WAV switch. The choice is remembered and also applies to the
  "Send to FL" button and the shortcut. WAV files are about 10x bigger and are
  not better quality than the MP3 (YouTube's audio is already compressed).
- "Change folder" opens the normal Windows folder window. The toolbar window
  closes when you do that; the new folder shows next time you open it.
  Remember to add the new folder in FL Studio (setup step 4).
- Want your own picture on the "Send to FL" button? Save it as
  extension\fl.png and reload the extension.
3. When it finishes, the folder pops open with the MP3 selected, so you can
   also drag it straight from Explorer into FL's Playlist.

TIPS
- The save folder is changed from the toolbar window ("Change folder").
- Stop the folder popping open each time:
      set BEATGRAB_REVEAL=0
- If downloads suddenly fail, YouTube changed something:
      pip install -U "yt-dlp[default]"
- After editing anything in the "extension" folder, press the reload arrow on
  the BeatGrab card in chrome://extensions.
- The MP3 carries the video title, uploader and thumbnail as tags.
- Single videos only (playlists are ignored on purpose).
- The helper only listens on 127.0.0.1 and only accepts requests from this
  extension.

NOTE: downloading from YouTube is against YouTube's terms. Keep it for
personal listening / reference, and get a proper lease or license from the
producer before using any beat in a release.
