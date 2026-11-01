"""Visium end to end on the demo cluster: Space Ranger folders, load, filter (with the mitochondrial share), regions,
the tissue view, spatially variable genes, markers, naming, comparison, export, record and an exact repeat.

Needs the singlecell extra (pip install -e ".[singlecell]"); skipped without it.
"""
import json
import time

import pytest

pytest.importorskip("scanpy")
pytest.importorskip("leidenalg")

from fastapi.testclient import TestClient  # noqa: E402

from everyome.core import server  # noqa: E402
from rerun_helpers import rerun  # noqa: E402

MID = "spatial.visium"


def wait(fn, timeout=240, every=0.5):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVERYOME_DEMO_PAUSE", "0.1")
    server.S.demo_root = tmp_path / "demo_cluster"
    c = TestClient(server.app)
    yield c
    if server.S.run:
        c.post("/api/session/stop")
    c.post("/api/disconnect")


def done(c):
    s = ok(c.get("/api/s/status"))
    assert not s["task"]["error"], s["task"]["error"]
    return not s["task"]["running"]


def call(c, method, **kw):
    return ok(c.post(f"/api/s/call/{method}", json=kw))


def test_visium_end_to_end(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "skin"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": data}))["rows"]
    assert [(r["sample"], r["condition"]) for r in rows] == [("skin_control", "control"), ("skin_treated", "treated")]
    assert all(r["outs"].endswith("/outs") for r in rows)

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"data_dir": data, "samples": rows}}))
    rd = tmp_path / "demo_cluster/projects/skin/runs" / run["id"]
    # Intent: no cluster stages; the live session starts straight away.
    assert ok(c.post("/api/run/preview", json={}))["scripts"] == []
    ok(c.post("/api/session/start"))
    wait(lambda: ok(c.get("/api/session/status"))["state"] == "READY")

    call(c, "load"); wait(lambda: done(c))
    n = call(c, "spots_per_sample")
    truth = json.loads((tmp_path / "demo_cluster/data" / MID / "truth.json").read_text())
    assert n == {s: len(truth[s]) for s in ("skin_control", "skin_treated")}
    t = call(c, "tissue", sample="skin_treated", key="total_counts")
    assert t["image"].startswith("data:image/png;base64,") and t["width"] == 600 and len(t["x"]) == n["skin_treated"] and t["r"] > 2
    assert max(t["x"]) <= 600 and max(t["y"]) <= 600

    # Damaged spots at the cut edge have a high mitochondrial share; the default threshold removes them.
    q = call(c, "qc_data")
    assert q["mito_edges"] and q["thresholds"]["max_mito"] == 20.0
    damaged = sum(v["damaged"] for s in truth.values() for v in s.values())
    th = {"min_counts": 300, "max_counts": 100000, "min_genes": 100, "max_genes": 10000, "max_mito": 20}
    prev = call(c, "qc_preview", **th)
    assert prev["total"] - prev["kept"] >= 0.9 * damaged
    call(c, "qc_apply", **th); wait(lambda: done(c))

    call(c, "cluster", n_top_genes=500, n_pcs=15, n_neighbors=15, resolution=0.3, min_dist=0.3, batch_key="sample", harmony=True)
    wait(lambda: done(c), timeout=300)
    s = call(c, "cluster_summary")
    assert 4 <= len(s["clusters"]) <= 10
    tops = {cl["id"]: [g["gene"] for g in call(c, "markers", cluster=cl["id"])[:5]] for cl in s["clusters"]}
    for marker in ("KRT14", "COL1A1", "ACTA2", "KRT17", "ISG15"):
        assert any(marker in g for g in tops.values()), (marker, tops)

    # Spatially variable genes: region markers rank high, unpatterned genes do not.
    call(c, "spatial_genes"); wait(lambda: done(c))
    sv = ok(c.get("/api/s/status"))["spatial_genes"]
    top10 = [g["gene"] for g in sv[:10]]
    from everyome.modules.spatial.visium.demo_data import REGIONS
    markers = {g for gs, _ in REGIONS.values() for g in gs}
    assert sum(g in markers for g in top10) >= 8 and not any(g.startswith("GENE") for g in top10), top10
    assert sv[0]["morans_i"] > 0.5
    view = call(c, "tissue", sample="skin_treated", key="cluster")
    assert view["colour"]["kind"] == "cat" and len(view["colour"]["codes"]) == len(view["x"])
    assert call(c, "tissue", sample="skin_control", key="KRT14")["colour"]["kind"] == "num"

    known = {"KRT14": "Epidermis", "COL1A1": "Dermis", "ACTA2": "Muscle", "KRT17": "Hair follicle", "ISG15": "Immune infiltrate"}
    for cid, genes in tops.items():
        name = next((known[x] for x in genes if x in known), "")
        if name:
            call(c, "annotate", cluster=cid, name=name, color="#C2A24A")
    comp = call(c, "composition", group="condition")
    share = dict(zip(comp["groups"], comp["fractions"][comp["types"].index("Immune infiltrate")]))
    assert share["treated"] > 0.02 and share["control"] < 0.01
    call(c, "export", group="condition"); wait(lambda: done(c), timeout=300)
    assert "annotated.h5ad" in {f["name"] for f in call(c, "files")}

    rec = ok(c.post("/api/run/record"))
    for phrase in ("2 10x Genomics Visium sections (control, treated)", "Each spot was treated as one observation", "corrected with Harmony",
                   "Moran's I (Moran, 1950)", "more than 20% of UMIs from mitochondrial genes"):
        assert phrase in rec["methods"], phrase

    # Repeat from the bundle: no jobs, just the replayed session, same composition.
    new = tmp_path / "repeat_visium"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert p1.returncode == 0 and "no cluster stages" in p1.stdout, p1.stderr
    p2 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--session")
    assert p2.returncode == 0, p2.stderr
    f = "results/composition_counts_by_condition.csv"
    assert (new / f).read_text() == (rd / f).read_text()
