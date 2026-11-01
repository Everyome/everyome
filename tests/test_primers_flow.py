"""Primer design end to end with no cluster at all ("This computer"): design, check, export, record and an exact repeat.

Needs the molbio extra (pip install -e ".[molbio]"); skipped without it.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("primer3")
pytest.importorskip("Bio")

from fastapi.testclient import TestClient  # noqa: E402

from everyome.core import server  # noqa: E402

MID = "molbio.primers"


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def client(tmp_path):
    server.S.local_root = tmp_path / "Everyome"
    c = TestClient(server.app)
    yield c
    c.post("/api/disconnect")


def call(c, method, **kw):
    return ok(c.post(f"/api/s/call/{method}", json=kw))


def test_primer_design_with_no_cluster(client, tmp_path):
    c = client
    r = ok(c.post("/api/connect", json={"mode": "local"}))
    names = [x["name"] for x in r["checks"]]
    assert all(x["ok"] for x in r["checks"]) and "Scheduler available" not in names     # no Slurm needed
    st = ok(c.get("/api/state"))
    assert st["conn"]["mode"] == "local" and st["label"] == "this computer"
    example = tmp_path / "Everyome/examples" / MID / "demo_plasmid.gb"
    assert example.exists()
    ok(c.post("/api/project/create", json={"name": "cloning"}))

    # Cluster analyses say what they need instead of failing later.
    bad = c.post("/api/run/create", json={"module": "tutorial.sequence_summary", "values": {}})
    assert bad.status_code == 400 and "runs on a computing cluster" in bad.json()["detail"]

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"sequence_file": str(example)}}))
    assert run["jobs"] == {} and ok(c.post("/api/run/preview", json={}))["scripts"] == []
    assert ok(c.post("/api/session/start"))["local"] is True
    assert ok(c.get("/api/session/status"))["state"] == "READY"

    info = call(c, "sequence_info")
    assert info["length"] == 3000 and info["circular"] is True
    assert {"EcoRI", "BamHI", "HindIII", "XhoI"} <= {s["name"] for s in info["sites"]}
    assert "gene of interest" in {f["label"] for f in info["features"]}
    assert c.post("/api/s/call/set_target", json={"start": 2990, "length": 50}).status_code == 400
    call(c, "set_target", start=300, length=796, label="gene of interest")
    too_long = c.post("/api/s/call/design", json={})
    assert too_long.status_code == 400 and "longest product allowed is 600" in too_long.json()["detail"]
    call(c, "set_target", start=400, length=200, label="gene of interest")
    d = call(c, "design")
    p = d["pairs"][0]
    assert len(d["pairs"]) == 5 and p["left_end"] < 400 and p["right_start"] > 599 and 100 <= p["product"] <= 600
    assert 57 <= p["left_tm"] <= 63 and 57 <= p["right_tm"] <= 63

    chk = call(c, "check_primers", left=p["left"], right=p["right"], name="pair 1")
    assert chk["product"] == p["product"] and chk["left"]["binds_at"] == p["left_start"]
    assert c.post("/api/s/call/check_primers", json={"left": "ACGTXX"}).status_code == 400

    ex = call(c, "export", chosen=[1, 2], prefix="demo")
    assert [o["name"] for o in ex["order"]] == ["demo_1_F", "demo_1_R", "demo_2_F", "demo_2_R"]
    gb = c.get("/api/s/download", params={"name": "demo_with_primers.gb"})
    assert gb.status_code == 200 and "primer_bind" in gb.text and "demo_1_F" in gb.text
    assert c.get("/api/s/download", params={"name": "../run.json"}).status_code == 404

    rec = ok(c.post("/api/run/record"))
    assert "flanking positions 400–599 (gene of interest)" in rec["methods"] and "primer3-py (version" in rec["methods"]
    assert "demo_1_F, demo_1_R, demo_2_F, demo_2_R" in rec["methods"]
    assert "| primer3 |" in rec["protocol"] and "| Bio |" in rec["protocol"] and "not found" not in rec["protocol"].split("## Software versions")[1].split("##")[0]

    # Repeat from the bundle: no jobs, just the replayed steps, same order sheet.
    rd = tmp_path / "Everyome/projects/cloning/runs" / run["id"]
    new = tmp_path / "repeat_primers"
    args = [sys.executable, "-m", "everyome.core.rerun", str(rd / "record/rerun"), str(new)]
    p1 = subprocess.run(args, capture_output=True, text=True, env=os.environ)
    assert p1.returncode == 0 and "no cluster stages" in p1.stdout, p1.stderr
    p2 = subprocess.run(args + ["--session"], capture_output=True, text=True, env=os.environ)
    assert p2.returncode == 0, p2.stderr
    assert (new / "results/order_sheet.csv").read_text() == (rd / "results/order_sheet.csv").read_text()


def test_local_modules_need_this_computer(tmp_path):
    """On the demo cluster (also this computer) primer design works; the module list says it runs here."""
    m = ok(TestClient(server.app).get(f"/api/modules/{MID}"))
    assert m["kind"] == ["local"] and m["steps"][0]["id"] == "sequence"
