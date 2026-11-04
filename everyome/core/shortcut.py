"""An Everyome icon, for people who would rather not use a terminal: `everyome --shortcut` adds it, `--remove-shortcut`
takes it away. The one-line installer adds it for you.

macOS: Everyome.app in ~/Applications (found by Spotlight), and a tile in the Dock. Linux: an entry in the app menu and, if
there is a Desktop folder, an icon there. Both run the same small launcher, which starts Everyome in the background
(or, if it is already running, just opens it in the browser) and keeps its messages in ~/.everyome/logs/app.log.
Everything is made on this computer, so macOS doesn't treat it as a download from an unknown developer.
"""
from __future__ import annotations

import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from importlib.resources import files
from pathlib import Path

from everyome import __version__

ICON = files("everyome") / "static" / "icon-512.png"
BUNDLE_ID = "org.everyome.app"
MARK = "# Everyome launcher, made by `everyome --shortcut`."


def launcher(python: str) -> str:
    """The script the icon runs: start Everyome in the background with this Python, then return straight away."""
    return f"""#!/bin/bash
{MARK}
# Starts Everyome in the background and opens it in your browser; if it is already running, just opens it.
# Messages go to ~/.everyome/logs/app.log. Stop Everyome with Quit in the app.
mkdir -p "$HOME/.everyome/logs"
nohup {shlex.quote(python)} -m everyome "$@" >> "$HOME/.everyome/logs/app.log" 2>&1 &
"""


def _ours(path: Path) -> bool:
    # Intent: never overwrite or delete an icon someone else made with the same name.
    try:
        if path.suffix == ".app":
            return plistlib.loads((path / "Contents" / "Info.plist").read_bytes()).get("CFBundleIdentifier") == BUNDLE_ID
        return MARK in path.read_text() or "X-Everyome-Shortcut=true" in path.read_text()
    except (OSError, ValueError, UnicodeDecodeError, plistlib.InvalidFileException):
        return False


def _icns(dest: Path) -> bool:
    """Make the macOS icon file from the PNG with the system's own tools (sips, iconutil)."""
    if not (shutil.which("sips") and shutil.which("iconutil")):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        src, iconset = Path(tmp) / "icon.png", Path(tmp) / "Everyome.iconset"
        src.write_bytes(ICON.read_bytes())
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = size * scale
                if px > 512:
                    continue
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                r = subprocess.run(["sips", "-z", str(px), str(px), str(src), "--out", str(iconset / name)], capture_output=True)
                if r.returncode:
                    return False
        return subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(dest)], capture_output=True).returncode == 0


def _mac_app(home: Path) -> Path:
    return home / "Applications" / "Everyome.app"


def _real_home(home: Path) -> bool:
    # Intent: the Dock belongs to the account, whatever $HOME says; only touch it for the account's own home folder,
    # never for a test or a scratch install with HOME pointed elsewhere.
    try:
        import pwd
    except ImportError:  # Intent: Windows has no pwd module, and no Dock.
        return False
    real = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    return home.resolve() == real and Path(os.environ.get("HOME", real)).resolve() == real


def _dock_tile(t: dict) -> bool:
    data = t.get("tile-data", {})
    return data.get("bundle-identifier") == BUNDLE_ID or data.get("file-data", {}).get("_CFURLString", "").rstrip("/").endswith("/Everyome.app")


def dock(app: Path, add: bool, home: Path, run=subprocess.run) -> str | None:
    """Add Everyome's tile to the Dock (or take it away). Returns what happened, or None if the Dock wasn't changed."""
    r = run(["defaults", "export", "com.apple.dock", "-"], capture_output=True)
    if r.returncode:
        return None
    try:
        prefs = plistlib.loads(r.stdout)
    except (plistlib.InvalidFileException, ValueError):
        return None
    tiles = prefs.get("persistent-apps", [])
    url = app.as_uri() + "/"
    if add and any(t.get("tile-data", {}).get("file-data", {}).get("_CFURLString") == url for t in tiles):
        return "Everyome is already in your Dock."
    kept = [t for t in tiles if not _dock_tile(t)]
    if not add and len(kept) == len(tiles):
        return None
    if add:
        kept.append({"tile-type": "file-tile", "tile-data": {
            "bundle-identifier": BUNDLE_ID, "file-label": "Everyome",
            "file-data": {"_CFURLString": url, "_CFURLStringType": 15}}})
    # Intent: keep a copy of the Dock settings as they were, in case anything goes wrong.
    backup = home / ".everyome" / "dock-before-everyome.plist"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(r.stdout)
    prefs["persistent-apps"] = kept
    if run(["defaults", "import", "com.apple.dock", "-"], input=plistlib.dumps(prefs), capture_output=True).returncode:
        return None
    run(["killall", "Dock"], capture_output=True)  # Intent: the Dock re-reads its settings when it restarts.
    # Intent: wait until the restarted Dock has taken the change in. After an add it rewrites the new tile (adding its
    # own GUID) and saves; a change made before that save is lost, as seen when adding and removing within seconds.
    for _ in range(30):
        time.sleep(0.5)
        if run(["pgrep", "-x", "Dock"], capture_output=True).returncode:
            continue
        if not add:
            time.sleep(2)
            break
        now = run(["defaults", "export", "com.apple.dock", "-"], capture_output=True)
        try:
            if any(_dock_tile(t) and "GUID" in t for t in plistlib.loads(now.stdout).get("persistent-apps", [])):
                break
        except (plistlib.InvalidFileException, ValueError):
            pass
    return "Added Everyome to your Dock." if add else "Removed Everyome from your Dock."


def _linux_paths(home: Path, env) -> dict[str, Path]:
    data = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    desktop = None
    try:  # Intent: the Desktop folder has a different name in some languages; xdg-user-dir knows it.
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, env={**env, "HOME": str(home)})
        if out.returncode == 0 and out.stdout.strip() and Path(out.stdout.strip()) != home:
            desktop = Path(out.stdout.strip())
    except OSError:
        pass
    desktop = desktop or home / "Desktop"
    return {"launcher": home / ".everyome" / "everyome-launcher", "icon": data / "icons" / "hicolor" / "512x512" / "apps" / "everyome.png",
            "menu": data / "applications" / "everyome.desktop", "desktop": desktop / "everyome.desktop"}


def create(home: Path | None = None, system: str | None = None, python: str | None = None, env=None,
           run=subprocess.run) -> list[str]:
    """Add the icon. Returns plain-language lines saying what was made."""
    home, system, python, env = home or Path.home(), system or platform.system(), python or sys.executable, env or os.environ
    if system == "Darwin":
        app = _mac_app(home)
        if app.exists():
            if not _ours(app):
                return [f"Left {app} alone: it isn't one Everyome made."]
            shutil.rmtree(app)
        (app / "Contents" / "MacOS").mkdir(parents=True)
        (app / "Contents" / "Resources").mkdir()
        exe = app / "Contents" / "MacOS" / "Everyome"
        exe.write_text(launcher(python))
        exe.chmod(0o755)
        info = {"CFBundleName": "Everyome", "CFBundleDisplayName": "Everyome", "CFBundleIdentifier": BUNDLE_ID,
                "CFBundleExecutable": "Everyome", "CFBundlePackageType": "APPL", "CFBundleShortVersionString": __version__,
                "LSMinimumSystemVersion": "11.0",
                # Intent: no Dock icon; the launcher returns at once and Everyome lives in the browser.
                "LSUIElement": True}
        if _icns(app / "Contents" / "Resources" / "Everyome.icns"):
            info["CFBundleIconFile"] = "Everyome"
        (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
        # Intent: tell Finder and Spotlight about the new app (and its icon) straight away.
        lsregister = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
        if Path(lsregister).exists():
            subprocess.run([lsregister, "-f", str(app)], capture_output=True)
        lines = [f"Added Everyome to the Applications folder in your home folder ({app})."]
        in_dock = dock(app, True, home, run) if _real_home(home) else None
        if in_dock:
            lines.append(in_dock)
        return lines + [("Click it in the Dock, or press ⌘ Space and type Everyome" if in_dock else
                         "Open it by pressing ⌘ Space and typing Everyome") + "; it opens Everyome in your browser."]
    if system == "Linux":
        p = _linux_paths(home, env)
        made = []
        for key in ("launcher", "menu", "desktop"):
            if p[key].exists() and not _ours(p[key]):
                return [f"Left {p[key]} alone: it isn't one Everyome made."]
        p["launcher"].parent.mkdir(parents=True, exist_ok=True)
        p["launcher"].write_text(launcher(python))
        p["launcher"].chmod(0o755)
        p["icon"].parent.mkdir(parents=True, exist_ok=True)
        p["icon"].write_bytes(ICON.read_bytes())
        entry = (f"[Desktop Entry]\nType=Application\nName=Everyome\nComment=Every -ome, for everyone\n"
                 f'Exec="{p["launcher"]}"\nIcon={p["icon"]}\nTerminal=false\nCategories=Science;Biology;Education;\n'
                 f"X-Everyome-Shortcut=true\n")
        p["menu"].parent.mkdir(parents=True, exist_ok=True)
        p["menu"].write_text(entry)
        made.append("Added Everyome to your applications menu.")
        if p["desktop"].parent.is_dir():
            p["desktop"].write_text(entry)
            p["desktop"].chmod(0o755)
            # Intent: GNOME asks before running a desktop icon unless it is marked trusted; best effort elsewhere.
            if shutil.which("gio"):
                subprocess.run(["gio", "set", str(p["desktop"]), "metadata::trusted", "true"], capture_output=True)
            made.append(f"Added an Everyome icon to your desktop ({p['desktop'].parent}).")
        return made + ["It opens Everyome in your browser."]
    return [f"An Everyome icon isn't available on {system} yet; start it with the `everyome` command."]


def remove(home: Path | None = None, system: str | None = None, env=None, run=subprocess.run) -> list[str]:
    """Take away what create() added (only files Everyome made)."""
    home, system, env = home or Path.home(), system or platform.system(), env or os.environ
    out = []
    if system == "Darwin":
        targets = [_mac_app(home)]
        if _real_home(home) and (msg := dock(_mac_app(home), False, home, run)):
            out.append(msg)
    elif system == "Linux":
        targets = list(_linux_paths(home, env).values())
    else:
        return [f"There is no Everyome icon on {system} to remove."]
    gone = []
    for t in targets:
        if t.exists() and (t.name == "everyome.png" or _ours(t)):
            shutil.rmtree(t) if t.is_dir() else t.unlink()
            gone.append(str(t))
    out += [f"Removed {g}" for g in gone]
    return out or ["There was no Everyome icon to remove."]
