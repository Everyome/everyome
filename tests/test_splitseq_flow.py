"""SPLiT-seq (SPLiTscape) end to end on the demo cluster: settings, 8 stages, read QC, then the whole live session.

Needs the single-cell packages (pip install -e ".[singlecell]"); skipped without them.
"""
import os
import time

import pytest

pytest.importorskip("scanpy")
pytest.importorskip("harmonypy")

from fastapi.testclient import TestClient  # noqa: E402

from everyome.core import server  # noqa: E402

MID = "singlecell.splitseq"


def wait(fn, timeout=180, every=0.5):
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
    monkeypatch.setenv("EVERYOME_DEMO_PAUSE", "0.1")      # fast pretend stages
    server.S.demo_root = tmp_path / "demo_cluster"
    c = TestClient(server.app)
    yield c
    if server.S.run:
        c.post("/api/session/stop")
    c.post("/api/disconnect")


def task_done(c):
    s = ok(c.get("/api/s/status"))
    assert not s["task"]["error"], s["task"]["error"]
    return not s["task"]["running"]


def call(c, method, **kw):
    return ok(c.post(f"/api/s/call/{method}", json=kw))


def test_splitseq_end_to_end(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    assert os.path.exists(f"{data}/.demo_truth/info.json")      # demo data built on first connect
    ok(c.post("/api/project/create", json={"name": "split"}))
    assert ok(c.get(f"/api/modules/{MID}/check"))["missing"] == []

    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/raw"}))["rows"]
    assert [r["sublibrary"] for r in rows] == ["sublib_1", "sublib_2"]
    values = {"raw_dir": f"{data}/raw", "sublibraries": rows, "ref_fasta": f"{data}/refs/genome.fasta",
              "star_index": f"{data}/refs/star_index", "toolbox": f"{data}/refs/splitseq_toolbox/Split-seq_pipeline.sh",
              "pairfq": f"{data}/refs/pairfq_lite", "atlas_dir": f"{data}/atlas_10x", "annotation_table": f"{data}/refs/annotation.tsv"}

    bad = c.post("/api/run/create", json={"module": MID, "values": {**values, "sublibraries": [{"sublibrary": "sublib_1", "library_id": "L1"}]}})
    assert bad.status_code == 400 and "lib_01_1" in bad.json()["detail"]

    run = ok(c.post("/api/run/create", json={"module": MID, "values": values}))
    assert run["demo"] is True and run["values"]["preferred_species"] == ""
    scripts = ok(c.post("/api/run/preview", json={}))["scripts"]
    assert len(scripts) == 8 and "--mem=64G" in scripts[5]["script"] and "EVERYOME_CPUS=8" in scripts[0]["script"]

    ok(c.post("/api/run/submit", json={}))
    wait(lambda: ok(c.get("/api/run/status"))["done"])
    env = (tmp_path / "demo_cluster/projects/split/runs" / run["id"] / "config/reads.env").read_text()
    assert "SUBLIBS=(sublib_1 sublib_2)" in env and "RUNS=(run_1 run_2)" in env and "THREADS=8" in env
    rep = ok(c.get("/api/run/report"))
    assert {"reads", "regions", "dge", "knee"} <= set(rep) and len(rep["dge"]) == 2

    ok(c.post("/api/session/start"))
    wait(lambda: ok(c.get("/api/session/status"))["state"] == "READY")

    # On its own first (no atlas), then merged with the atlas.
    call(c, "merge", experiment="expt", include_atlas=False); wait(lambda: task_done(c))
    alone = ok(c.get("/api/s/status"))["merged"]
    assert alone["atlas_cells"] == 0 and alone["with_atlas"] is False and alone["cells"] == alone["experiment_cells"]
    assert {l["experiment"] for l in call(c, "libraries")} == {"expt"}
    call(c, "merge", experiment="expt"); wait(lambda: task_done(c))
    libs = call(c, "libraries")
    assert {l["library"] for l in libs} >= {"lib_01_1", "lib_01_2"}
    table = {l["library"]: {"batch": l["experiment"], "condition": "control" if l["experiment"] == "atlas" else "from_barcodes"} for l in libs}
    call(c, "label", table=table, columns=["batch", "condition"], sheets={"condition": f"{data}/sheets/round1_condition.xlsx"})
    wait(lambda: task_done(c))
    assert len(call(c, "unique_counts")) >= 4

    q = call(c, "qc_data")
    t = q["thresholds"]
    assert 0 < call(c, "qc_preview", **t)["kept"]
    call(c, "qc_apply", **t); wait(lambda: task_done(c))

    call(c, "cluster", n_top_genes=1000, n_pcs=20, batch_key="batch", harmony=True, n_neighbors=15, resolution=0.6, min_dist=0.3)
    wait(lambda: task_done(c), timeout=300)
    clusters = ok(c.get("/api/s/status"))["clusters"]
    assert len(clusters) >= 4
    first = clusters[0]["id"]
    m = call(c, "markers", cluster=first)
    assert m and m[0]["name"]                                  # readable names from the annotation table
    assert call(c, "colour", key="cluster")["kind"] == "cat"
    call(c, "annotate", cluster=first, name="Stem cells", color="#C2A24A")
    comp = call(c, "composition", group="condition")
    assert "Stem cells" in comp["types"]

    call(c, "export", group="condition"); wait(lambda: task_done(c), timeout=300)
    names = {f["name"] for f in call(c, "files")}
    assert {"annotated.h5ad", "markers_by_cluster.xlsx", "umap_annotation.png"} <= names
    assert c.get("/api/s/download", params={"name": "umap_annotation.png"}).status_code == 200

    state = (tmp_path / "demo_cluster/projects/split/runs" / run["id"] / "session/state.json").read_text()
    for action in ("combined sublibraries (no atlas)", "combined sublibraries and merged in an atlas", "labelled cells", "filtered cells", "clustered", "named a cluster", "exported results"):
        assert action in state


def test_atlas_is_optional(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "first_atlas"}))
    values = {"raw_dir": f"{data}/raw", "sublibraries": [{"sublibrary": "sublib_1", "library_id": "lib_01_1"}],
              "ref_fasta": f"{data}/refs/genome.fasta", "star_index": f"{data}/refs/star_index",
              "toolbox": f"{data}/refs/splitseq_toolbox/Split-seq_pipeline.sh", "pairfq": f"{data}/refs/pairfq_lite"}
    run = ok(c.post("/api/run/create", json={"module": MID, "values": values}))
    assert run["values"]["atlas_dir"] is None


def test_playground_scripts_are_served():
    c = TestClient(server.app)
    m = ok(c.get(f"/api/modules/{MID}"))
    assert m["playground"]["object"] == "Playground" and m["playground"]["n_scripts"] == 3
    for i in range(3):
        r = c.get(f"/api/modules/{MID}/playground/{i}")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/javascript")
    assert c.get(f"/api/modules/{MID}/playground/3").status_code == 404
