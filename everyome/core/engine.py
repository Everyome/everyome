"""Base class for interactive module engines (generalised from SPLiTscape part 2).

An engine runs inside a session on a compute node (or this computer for the
demo). It works on one run folder, keeps its decisions in session/state.json,
and records every decision in order so the run can be written up later.
Long steps run in the background and report progress.

Subclasses list the methods the GUI may call in API; nothing else is reachable.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from pathlib import Path


class BaseEngine:
    API: tuple[str, ...] = ()

    def __init__(self, run_dir: str):
        self.dir = Path(run_dir)
        self.out = self.dir / "session"
        self.out.mkdir(exist_ok=True)
        (self.dir / "results").mkdir(exist_ok=True)
        self.run = json.loads((self.dir / "run.json").read_text())
        self.params = json.loads((self.dir / "params.json").read_text())
        self.state_path = self.out / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"step": "start", "history": []}
        self.task = {"running": False, "step": "", "progress": 0, "error": None, "message": ""}
        self.lock = threading.Lock()

    # ---------------------------------------------------------------- state
    def _save_state(self):
        self.state_path.write_text(json.dumps(self.state, indent=1))

    def _record(self, action: str, **details):
        """Note a decision (in order) for the run record and the lab-book protocol."""
        self.state.setdefault("history", []).append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, **details})
        self._save_state()

    def status(self):
        return {"step": self.state.get("step"), "task": self.task, "module": self.run["module"], "run": self.run["id"]}

    # ---------------------------------------------------------------- background work
    def _background(self, fn, *args):
        if self.task["running"]:
            raise RuntimeError("Another step is still running.")
        self.task = {"running": True, "step": fn.__name__, "progress": 0, "error": None, "message": ""}

        def wrap():
            try:
                with self.lock:
                    fn(*args)
            except Exception as e:                       # report, never crash the session
                self.task["error"] = f"{e}"
                traceback.print_exc()
            finally:
                self.task["running"] = False
                self.task["progress"] = 100 if not self.task["error"] else self.task["progress"]
        threading.Thread(target=wrap, daemon=True).start()
        return self.task

    def _prog(self, p, msg):
        self.task.update(progress=p, message=msg)
