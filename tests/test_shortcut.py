"""The Everyome icon (`everyome --shortcut`), the launcher it runs, and Quit in the app."""
import json
import os
import plistlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from everyome.core import shortcut


def test_linux_menu_entry_and_desktop_icon(tmp_path):
    (tmp_path / "Desktop").mkdir()
    lines = shortcut.create(home=tmp_path, system="Linux", python="/opt/my env/bin/python", env={"PATH": ""})
    menu = tmp_path / ".local/share/applications/everyome.desktop"
    desk = tmp_path / "Desktop/everyome.desktop"
    launcher = tmp_path / ".everyome/everyome-launcher"
    assert menu.exists() and desk.exists() and os.access(desk, os.X_OK) and os.access(launcher, os.X_OK)
    assert f'Exec="{launcher}"' in menu.read_text() and "Terminal=false" in menu.read_text()
    assert (tmp_path / ".local/share/icons/hicolor/512x512/apps/everyome.png").stat().st_size > 1000
    # Intent: a Python path with a space still runs.
    assert "'/opt/my env/bin/python' -m everyome" in launcher.read_text()
    assert any("desktop" in x for x in lines)
    shortcut.create(home=tmp_path, system="Linux", python="/x/python", env={"PATH": ""})  # again: replaces its own
    assert "/x/python" in launcher.read_text()
    shortcut.remove(home=tmp_path, system="Linux", env={"PATH": ""})
    assert not menu.exists() and not desk.exists() and not launcher.exists()


def test_never_touches_someone_elses_icon(tmp_path):
    menu = tmp_path / ".local/share/applications/everyome.desktop"
    menu.parent.mkdir(parents=True)
    menu.write_text("[Desktop Entry]\nName=Someone else's\n")
    assert "alone" in shortcut.create(home=tmp_path, system="Linux", env={"PATH": ""})[0]
    shortcut.remove(home=tmp_path, system="Linux", env={"PATH": ""})
    assert "Someone else's" in menu.read_text()


def test_mac_app(tmp_path):
    shortcut.create(home=tmp_path, system="Darwin", python="/env/bin/python")
    app = tmp_path / "Applications/Everyome.app"
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == shortcut.BUNDLE_ID and info["LSUIElement"] is True
    assert os.access(app / "Contents/MacOS/Everyome", os.X_OK)
    if sys.platform == "darwin":  # Intent: the icon is made with macOS's own tools.
        assert (app / "Contents/Resources/Everyome.icns").stat().st_size > 1000 and info["CFBundleIconFile"] == "Everyome"
    shortcut.remove(home=tmp_path, system="Darwin")
    assert not app.exists()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url, headers):
    req = urllib.request.Request(url, method="POST", headers=headers, data=b"")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _up(url):
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
            return json.load(r)["name"] == "Everyome"
    except OSError:
        return False


@pytest.mark.skipif(sys.platform == "win32", reason="the launcher is a bash script")
def test_launcher_starts_in_background_and_quit_stops_it(tmp_path):
    """What a double-click does: start Everyome in the background; a second start just finds it; Quit stops it."""
    port, home = _free_port(), tmp_path / "home"
    home.mkdir()
    launcher = tmp_path / "launch"
    launcher.write_text(shortcut.launcher(sys.executable))
    launcher.chmod(0o755)
    env = dict(os.environ, HOME=str(home))
    url = f"http://127.0.0.1:{port}"
    assert subprocess.run([str(launcher), "--no-browser", "--port", str(port)], env=env, timeout=10).returncode == 0
    for _ in range(120):
        if _up(url):
            break
        time.sleep(0.5)
    else:
        raise AssertionError((home / ".everyome/logs/app.log").read_text())
    try:
        again = subprocess.run([sys.executable, "-m", "everyome", "--no-browser", "--port", str(port)], env=env,
                               capture_output=True, text=True, timeout=30)
        assert again.returncode == 0 and "already running" in again.stdout
        assert _post(url + "/api/quit", {}) == 403  # Intent: another website can't stop it.
        assert _up(url)
        assert _post(url + "/api/quit", {"x-everyome": "quit"}) == 200
        for _ in range(40):
            if not _up(url):
                break
            time.sleep(0.25)
        assert not _up(url)
    finally:
        if _up(url):  # Intent: never leave a server behind if the test fails half way.
            _post(url + "/api/quit", {"x-everyome": "quit"})


def test_quit_refused_under_a_test_client():
    from fastapi.testclient import TestClient
    from everyome.core.server import app
    assert TestClient(app).post("/api/quit", headers={"x-everyome": "quit"}).status_code == 409
