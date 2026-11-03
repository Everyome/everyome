"""End to end on the demo cluster: connect, project, run, check scripts, submit, live session, export.

Uses the real app server, the pretend Slurm and a real session process, as a user would.
"""
import time

import pytest
from fastapi.testclient import TestClient

from everyome.core import server
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run


def wait(fn, timeout=600, every=0.5):  # generous: CI runners can be several times slower than a laptop
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


@pytest.fixture()
def client(tmp_path):
    server.S.demo_root = tmp_path / "demo_cluster"
    c = TestClient(server.app)
    yield c
    c.post("/api/session/stop") if server.S.run else None
    c.post("/api/disconnect")


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def test_tutorial_module_end_to_end(client, tmp_path):
    r = ok(client.post("/api/connect", json={"mode": "demo"}))
    assert all(c["ok"] for c in r["checks"]), r["checks"]

    p = ok(client.post("/api/project/create", json={"name": "test project"}))
    assert p["name"] == "test_project"

    st = ok(client.get("/api/state"))
    fasta = f"{st['conn']['data_root']}/tutorial.sequence_summary/sequences.fasta"
    bad = client.post("/api/run/create", json={"module": "tutorial.sequence_summary", "values": {"min_length": -1, "fasta": fasta}})
    assert bad.status_code == 400 and "at least 0" in bad.json()["detail"]

    run = ok(client.post("/api/run/create", json={"module": "tutorial.sequence_summary",
                                                   "values": {"fasta": fasta, "min_length": "100", "count_n": False, "rounding": "3"}}))
    assert run["values"]["min_length"] == 100 and run["defaults_changed"] == ["min_length"]
    assert run["jobs"] == {}                              # nothing submitted on create

    scripts = ok(client.post("/api/run/preview", json={}))["scripts"]
    assert [s["stage"] for s in scripts] == ["01", "02"]
    assert all(f"#SBATCH --job-name=Claude_{run['user']}_everyome_tutorial_sequence_summary_" in s["script"] for s in scripts)

    jobs = ok(client.post("/api/run/submit", json={}))["jobs"]
    assert set(jobs) == {"01", "02"}
    wait_for_run(client)
    assert "kept" in ok(client.get("/api/run/log", params={"stage": "01"}))["log"]
    gc = (tmp_path / "demo_cluster/projects/test_project/runs" / run["id"] / "results/gc.tsv").read_text().splitlines()
    assert gc[0] == "id\tlength\tgc" and len(gc) > 10

    ok(client.post("/api/session/start"))
    wait(lambda: ok(client.get("/api/session/status"))["state"] == "READY")
    s = ok(client.post("/api/s/call/summary", json={}))
    assert s["sequences"] == len(gc) - 1
    assert client.post("/api/s/call/not_allowed", json={}).status_code == 404
    kept = ok(client.post("/api/s/call/set_gc_range", json={"lo": 0.45, "hi": 0.65}))["kept"]
    ok(client.post("/api/s/call/export", json={}))
    wait(lambda: not ok(client.get("/api/s/status"))["task"]["running"])
    out = (tmp_path / "demo_cluster/projects/test_project/runs" / run["id"] / "results/gc_filtered.tsv").read_text().splitlines()
    assert len(out) == kept + 1
    state = (tmp_path / "demo_cluster/projects/test_project/runs" / run["id"] / "session/state.json").read_text()
    assert "set GC range" in state and "exported" in state   # decisions recorded in order

    # Record and write-ups
    rec = ok(client.post("/api/run/record"))
    assert {"protocol.md", "methods.md", "references.bib", "rerun/"} <= set(rec["files"])
    assert "Live-session steps" in rec["protocol"] and "Set gc range" in rec["protocol"] and "SHA-256" in rec["protocol"]
    assert "Shortest sequence kept | **100** | 50" in rec["protocol"]
    assert "between 0.45 and 0.65" in rec["methods"]
    ok(client.post("/api/run/methods", json={"text": "My edited methods."}))
    assert ok(client.get("/api/run/record"))["methods"] == "My edited methods."
    assert "between 0.45" in ok(client.post("/api/run/methods/reset"))["methods"]
    assert client.get("/api/run/record/file", params={"name": "references.bib"}).text.startswith("@misc{horkan2026")
    assert client.get("/api/run/record/file", params={"name": "../run.json"}).status_code == 404

    # Repeat the run from its bundle, in a new folder, and get the same result
    run_dir = tmp_path / "demo_cluster/projects/test_project/runs" / run["id"]
    demo_root, new = tmp_path / "demo_cluster", tmp_path / "repeat_1"
    p = rerun(demo_root, run_dir / "record/rerun", new)
    assert p.returncode == 0 and "Nothing submitted" in p.stdout and not (new / "logs/01_lengths.log").exists()
    p = rerun(demo_root, run_dir / "record/rerun", new, "--submit")
    assert p.returncode == 0 and "Submitted" in p.stdout, p.stderr
    rerun_until_session_replayed(demo_root, run_dir / "record/rerun", new)
    assert (new / "results/gc_filtered.tsv").read_text() == (run_dir / "results/gc_filtered.tsv").read_text()
