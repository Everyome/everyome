"""Single-cell RNA-seq end to end on the demo cluster: samples table, pipeline (stand-in), report, load, filter
(with the mitochondrial share), cluster, markers, naming, export, record and rerun.

Needs the singlecell extra (pip install -e ".[singlecell]"); skipped without it.
"""
import json
import time
from collections import Counter

import pytest

pytest.importorskip("scanpy")
pytest.importorskip("leidenalg")

from fastapi.testclient import TestClient  # noqa: E402

from everyome.core import server  # noqa: E402
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session  # noqa: E402

MID = "singlecell.scrna"
DAY = {"ctrl_1": "day1", "treated_1": "day1", "ctrl_2": "day2", "treated_2": "day2"}


def wait(fn, timeout=600, every=0.5):  # generous: CI runners can be several times slower than a laptop
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


def test_scrna_end_to_end(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "pbmc"}))
    scan = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))
    rows = scan["rows"]
    assert [r["sample"] for r in rows] == ["ctrl_1", "ctrl_2", "treated_1", "treated_2"]
    assert [r["condition"] for r in rows] == ["ctrl", "ctrl", "treated", "treated"] and all(r["fastq_2"] for r in rows)
    for r in rows:
        r["batch"] = DAY[r["sample"]]

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"reads_dir": f"{data}/fastq", "samples": rows,
                                                                        "fasta": f"{data}/genome/genome.fa", "gtf": f"{data}/genome/genes.gtf"}}))
    rd = tmp_path / "demo_cluster/projects/pbmc/runs" / run["id"]
    nfp = json.loads((rd / "nf_params.json").read_text())
    # Intent: Everyome's own starting value differs from the pipeline's, so it is written out; untouched settings are not.
    assert nfp["protocol"] == "10XV3" and "aligner" not in nfp and nfp["fasta"].endswith("genome.fa")
    assert (rd / "samplesheet.csv").read_text().startswith("sample,fastq_1,fastq_2,expected_cells\nctrl_1,")

    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    assert ok(c.get("/api/run/progress"))["failed"] == 0
    rep = ok(c.get("/api/run/report"))
    assert [m["kind"] for m in rep["matrices"]] == ["cellbender_filter", "raw"] and rep["multiqc"]

    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)
    assert [m["kind"] for m in call(c, "matrices") if m["exists"]] == ["cellbender_filter", "raw"]
    call(c, "load"); wait(lambda: done(c))
    st = ok(c.get("/api/s/status"))
    assert st["loaded_from"]["kind"] == "cellbender_filter" and st["loaded_from"]["symbols"] and st["loaded_from"]["missing"] == []
    assert set(st["obs_columns"]) == {"sample", "condition", "batch"}
    assert call(c, "cells_per_sample") == {"ctrl_1": 650, "ctrl_2": 650, "treated_1": 650, "treated_2": 650}

    # Damaged cells stand out by their mitochondrial share; the default threshold removes them.
    q = call(c, "qc_data")
    assert q["mito_edges"] and q["thresholds"]["max_mito"] == 20.0
    truth = json.loads((rd / "demo_truth.json").read_text())["cells"]
    t = {"min_counts": 500, "max_counts": 5000, "min_genes": 200, "max_genes": 1500, "max_mito": 20}
    prev = call(c, "qc_preview", **t)
    damaged = sum(1 for v in truth.values() if v["kind"] == "damaged")
    assert damaged > 50 and prev["total"] - prev["kept"] >= damaged * 0.9
    call(c, "qc_apply", **t); wait(lambda: done(c))
    kept = ok(c.get("/api/s/status"))["cells"]
    assert 2100 < kept < 2500

    call(c, "cluster", n_top_genes=1000, n_pcs=20, n_neighbors=15, resolution=0.4, min_dist=0.3, batch_key="batch", harmony=True)
    wait(lambda: done(c), timeout=600)
    s = call(c, "cluster_summary")
    assert 5 <= len(s["clusters"]) <= 12 and s["batch_mixing"] > 0.6

    # Each true cell type's markers lead one of the clusters.
    tops = {cl["id"]: [g["gene"] for g in call(c, "markers", cluster=cl["id"])[:5]] for cl in s["clusters"]}
    for marker in ("CD3E", "MS4A1", "NKG7", "FCER1A", "ISG15"):
        assert any(marker in g for g in tops.values()), (marker, tops)
    g = call(c, "genes", q="cd3")
    assert {"gene": "CD3E", "name": ""} in g
    assert call(c, "colour", key="pct_mito")["kind"] == "num"

    # Name each cluster after its best-known marker; the interferon cluster appears only in treated samples.
    known = {"CD3E": "T cells", "MS4A1": "B cells", "NKG7": "NK cells", "LYZ": "Monocytes", "FCER1A": "Dendritic cells", "ISG15": "IFN monocytes"}
    for cid, genes in tops.items():
        name = next((known[x] for x in genes if x in known), "")
        if name:
            call(c, "annotate", cluster=cid, name=name, color="#C2A24A")
    comp = call(c, "composition", group="condition")
    i = comp["types"].index("IFN monocytes")
    share = dict(zip(comp["groups"], comp["fractions"][i]))
    assert share["treated"] > 0.1 and share["ctrl"] < 0.02
    assert c.post("/api/s/call/export", json={"group": "../x"}).status_code == 400
    call(c, "export", group="condition"); wait(lambda: done(c), timeout=600)
    assert {"annotated.h5ad", "composition_fractions_by_condition.csv", "markers_by_cluster.xlsx"} <= {f["name"] for f in call(c, "files")}

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/scrnaseq version 4.2.0", "from 4 samples (ctrl, treated)", "simpleaf (alevin-fry", "10XV3 chemistry",
                   "CellBender", "with genes named by their symbols", "more than 20% of UMIs from mitochondrial genes",
                   "corrected with Harmony", "Leiden clustering", "compared descriptively by condition"):
        assert phrase in rec["methods"], phrase

    # Repeat from the bundle in a new folder: same cells kept and same composition.
    new = tmp_path / "repeat_scrna"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    f = "results/composition_counts_by_condition.csv"
    assert (new / f).read_text() == (rd / f).read_text()
