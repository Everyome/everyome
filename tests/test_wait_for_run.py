"""The end-to-end tests' wait for a run: finished, stopped by a failed stage, or still going at the timeout."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from rerun_helpers import wait_for_run  # noqa: E402


class Client:
    """Stands in for the app's test client; returns one run status after another."""
    def __init__(self, *statuses):
        self.statuses = list(statuses)

    def get(self, url):
        assert url == "/api/run/status"
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
    with pytest.raises(AssertionError, match=r"stopped: \{'trim': 'FAILED', 'bam': 'CANCELLED'\}"):
        wait_for_run(c, timeout=600, every=0)


def test_timeout_says_how_far_each_stage_got():
    c = Client(status(qc="COMPLETED", trim="RUNNING"))
    with pytest.raises(AssertionError, match=r"not finished after 0.2 s; stages: \{'qc': 'COMPLETED', 'trim': 'RUNNING'\}"):
        wait_for_run(c, timeout=0.2, every=0.05)
