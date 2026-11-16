#!/usr/bin/env python3
"""One-time setup: lets Chrome start the BeatGrab helper when Chrome opens and
stop it when Chrome closes (Chrome's "native messaging").

Run:  python install.py              (or double-click install-beatgrab.bat)
      python install.py --uninstall  to undo it
Run it again if you move the BeatGrab folder.
"""
import json
import os
import sys
import winreg
from pathlib import Path

HOST = "com.beatgrab.helper"
# Fixed by the "key" in extension/manifest.json, so it's the same on every PC.
EXTENSION_ID = "mecjkcnnpijnbbchjefjnepaljfbcfjh"
HERE = Path(__file__).resolve().parent
LAUNCHER = HERE / "beatgrab-host.bat"
MANIFEST = HERE / f"{HOST}.json"
BROWSER_KEYS = {
    "Google Chrome": r"Software\Google\Chrome\NativeMessagingHosts",
    "Microsoft Edge": r"Software\Microsoft\Edge\NativeMessagingHosts",
    "Chromium": r"Software\Chromium\NativeMessagingHosts",
}
OLD_STARTUP_SHORTCUT = (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu"
                        / "Programs" / "Startup" / "BeatGrab helper.lnk")


def install():
    LAUNCHER.write_text(
        "@echo off\n"
        "rem Written by install.py. Chrome runs this to start the BeatGrab helper.\n"
        f'"{sys.executable}" "%~dp0beatgrab.py" --native %*\n',
        encoding="utf-8",
    )
    MANIFEST.write_text(json.dumps({
        "name": HOST,
        "description": "BeatGrab helper",
        "path": str(LAUNCHER),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"],
    }, indent=2), encoding="utf-8")
    for browser, key in BROWSER_KEYS.items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{key}\{HOST}") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, str(MANIFEST))
        print(f"Registered for {browser}")
    if OLD_STARTUP_SHORTCUT.exists():
        OLD_STARTUP_SHORTCUT.unlink()
        print("Removed the old Startup shortcut (Chrome starts the helper now)")

    sys.path.insert(0, str(HERE))
    import beatgrab
    beatgrab.check_setup()  # warns if yt-dlp, ffmpeg or Node.js is missing

    print()
    print("Done. Next:")
    print("  1. If BeatGrab was already in Chrome, remove it in chrome://extensions,")
    print("     then Load unpacked the 'extension' folder again.")
    print("  2. Close Chrome completely and open it again.")
    print("The helper now starts with Chrome and stops when Chrome closes.")


def uninstall():
    for browser, key in BROWSER_KEYS.items():
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key}\{HOST}")
            print(f"Unregistered from {browser}")
        except FileNotFoundError:
            pass
    for f in (LAUNCHER, MANIFEST):
        if f.exists():
            f.unlink()
    print("Done. Chrome will no longer start the BeatGrab helper.")


if __name__ == "__main__":
    if sys.platform != "win32":
        sys.exit("This installer is for Windows.")
    uninstall() if "--uninstall" in sys.argv[1:] else install()
