"""Start Everyome: `everyome` (or `python -m everyome`) opens the app in your browser."""
import argparse
import os
import threading
import webbrowser

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="Everyome: every -ome, for everyone")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    a = ap.parse_args()
    try:
        import setproctitle
        # Intent: Stowers policy names every process Claude_<user>_<tool>_<stage>.
        setproctitle.setproctitle(f"Claude_{os.environ.get('USER', 'user')}_everyome_app")
    except ImportError:
        pass
    url = f"http://127.0.0.1:{a.port}"
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Everyome is running at {url}  (press Ctrl+C to quit)")
    # Intent: listen on localhost only; the app is for this computer's user.
    uvicorn.run("everyome.core.server:app", host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
