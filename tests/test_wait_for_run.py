"""The end-to-end tests' waits for a run and for its live session: done, stopped by a failure, or still going at
the timeout."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from rerun_helpers import wait_for_run, wait_for_session  # noqa: E402


class Client:
    """Stands in for the app's test client; returns one status after another."""
    def __init__(self, *statuses):
        self.statuses = list(statuses)

    def get(self, url, params=None):
        if url == "/api/run/log":  # Intent: each stage's log, as the app returns it.
            st = {"log": f"the end of {params['stage']}'s log"}
            return type("R", (), {"status_code": 200, "text": "", "json": lambda self: st})()
        st = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return type("R", (), {"status_code": 200, "text": "", "json": lambda self: st})()


def status(done=False, **states):
    return {"done": done, "stages": {k: {"job": i, "state": s} for i, (k, s) in enumerate(states.items())}}


def test_returns_when_every_stage_completed():
    c = Client(status(qc="RUNNING", trim="PENDING"), status(True, qc="COMPLETED", trim="COMPLETED"))
    assert wait_for_run(c, timeout=5, every=0)["done"]


def test_stops_at_once_on_a_failed_stage_and_names_it():
    # Intent: this used to wait out the whole timeout and say only "timed out".
    c = Client(status(qc="COMPLETED", trim="FAILED", bam="CANCELLED"))
    with pytest.raises(AssertionError, match=r"(?s)stopped: \{'trim': 'FAILED', 'bam': 'CANCELLED'\}.*the end of trim's log"):
        wait_for_run(c, timeout=600, every=0)


def test_timeout_says_how_far_each_stage_got():
    c = Client(status(qc="COMPLETED", trim="RUNNING"))
    with pytest.raises(AssertionError, match=r"not finished after 0.2 s; stages: \{'qc': 'COMPLETED', 'trim': 'RUNNING'\}"):
        wait_for_run(c, timeout=0.2, every=0.05)


def test_session_ready():
    c = Client({"state": "PENDING"}, {"state": "STARTING"}, {"state": "READY", "node": "n1"})
    assert wait_for_session(c, timeout=5, every=0)["node"] == "n1"


def test_session_that_failed_stops_at_once_and_shows_its_log(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/session.log").write_text("starting\nModuleNotFoundError: No module named 'pydeseq2'\n")
    with pytest.raises(AssertionError, match=r"(?s)session job stopped: FAILED.*No module named 'pydeseq2'"):
        wait_for_session(Client({"state": "FAILED"}), tmp_path, timeout=600, every=0)


def test_session_timeout_gives_the_last_state():
    with pytest.raises(AssertionError, match=r"session not ready after 0.2 s \(last state STARTING\)"):
        wait_for_session(Client({"state": "STARTING"}), timeout=0.2, every=0.05)
