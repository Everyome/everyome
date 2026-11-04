"""Start Everyome: `everyome` (or `python -m everyome`) opens the app in your browser."""
import argparse
import json
import os
import threading
import urllib.request
import webbrowser

import uvicorn


def already_running(url: str) -> bool:
    """True if Everyome already answers at this address."""
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=1) as r:
            return json.load(r).get("name") == "Everyome"
    except (OSError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser(description="Everyome: every -ome, for everyone")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    ap.add_argument("--shortcut", action="store_true",
                    help="add an Everyome icon (Applications on macOS; the app menu and desktop on Linux), then stop")
    ap.add_argument("--remove-shortcut", action="store_true", help="remove the icon --shortcut added, then stop")
    a = ap.parse_args()
    if a.shortcut or a.remove_shortcut:
        from everyome.core import shortcut
        for line in (shortcut.create() if a.shortcut else shortcut.remove()):
            print(line)
        return
    url = f"http://127.0.0.1:{a.port}"
    if already_running(url):
        # Intent: a second click on the icon just brings Everyome back up in the browser.
        print(f"Everyome is already running at {url}")
        if not a.no_browser:
            webbrowser.open(url)
        return
    try:
        import setproctitle
        from everyome.core.slurm import proc_name
        # Intent: the app's process name says who started it, with the same prefix as job names (core/slurm.py).
        setproctitle.setproctitle(proc_name(os.environ.get("USER", "user"), "everyome_app"))
    except ImportError:
        pass
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Everyome is running at {url}  (press Ctrl+C, or Quit in the app, to stop it)")
    from everyome.core import server
    # Intent: listen on localhost only; the app is for this computer's user. Quit in the app stops this server.
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=a.port, log_level="warning",
                                        timeout_graceful_shutdown=5))
    server.QUIT = lambda: setattr(srv, "should_exit", True)
    srv.run()


if __name__ == "__main__":
    main()
