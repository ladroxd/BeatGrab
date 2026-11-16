# TODO

## To verify by hand

These work in automated runs (headless Chromium plus the real helper) but
have not been confirmed in everyday use.

- [ ] Toolbar window opened from the real toolbar icon in Chrome.
- [ ] "Change folder": pick a folder in the Windows dialog, then send a beat
      and check it lands there.
- [ ] Helper starts with the real Chrome and stops when it closes (tested in
      Chromium only), including with several Chrome profiles open.
- [ ] In-page "Send to FL" button position when signed in, and in dark mode.
- [ ] BPM and key on a range of real beat uploads (so far checked against
      sample titles and descriptions only).
- [ ] A long video (10 minutes or more) downloads without the extension
      losing track of it.
- [ ] WAV and MP3 files show up in the FL Studio Browser and drag into the
      Playlist.
- [ ] Windows notification appears on screen on save and on failure.

## Repo

- [ ] Choose a license and add a `LICENSE` file (the README has no License
      section until then).
- [ ] Add a screenshot of the "Send to FL" button on a watch page to the
      README.
- [ ] Publish a release with a zip, and point the README's download button
      at it instead of the `main` branch zip.

## Ideas

- [ ] Put BPM and key in the filename when the title doesn't already have
      them.
- [ ] Show the chosen format on the in-page button (for example
      "Send to FL - WAV").
- [ ] In-page button on Shorts.
- [ ] Open the saved folder from the toolbar window.
- [ ] Option for a subfolder per day or per uploader.
- [ ] Detect BPM and key from the audio when the uploader didn't list them.
- [ ] Package the helper as a single .exe with yt-dlp and ffmpeg bundled, so
      setup needs no Python install.
- [ ] Have `install-beatgrab.bat` also install yt-dlp, ffmpeg and Node.js
      when they are missing.

## Not planned

- Publishing to the Chrome Web Store. It does not accept YouTube
  downloaders, so BeatGrab stays a load-unpacked extension for personal use.
- Playlists or bulk downloads. One video per click, on purpose.
