"""Bulk RNA-seq end to end on the demo cluster: samples table, pipeline (stand-in), report, DESeq2, export, record and rerun.

Needs the rna extra (pip install -e ".[rna]"); skipped without it.
"""
import json
import time

import pytest

pytest.importorskip("pydeseq2")

from fastapi.testclient import TestClient  # noqa: E402

from everyome.core import server  # noqa: E402
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run  # noqa: E402

MID = "rna.bulk_de"


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


def test_bulk_rna_end_to_end(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "rna"}))
    scan = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))
    rows = scan["rows"]
    assert [r["condition"] for r in rows] == ["control"] * 3 + ["treated"] * 3 and all(r["fastq_2"] for r in rows)

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"reads_dir": f"{data}/fastq", "samples": rows,
                                                                        "fasta": f"{data}/genome/genome.fa", "gtf": f"{data}/genome/genes.gtf"}}))
    rd = tmp_path / "demo_cluster/projects/rna/runs" / run["id"]
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["fasta"].endswith("genome.fa") and "aligner" not in nfp            # only changed settings go to the pipeline
    assert (rd / "samplesheet.csv").read_text().startswith("sample,fastq_1,fastq_2,strandedness\ncontrol_1,")
    scripts = ok(c.post("/api/run/preview", json={}))["scripts"]
    assert len(scripts) == 1 and "demo_pipeline" in scripts[0]["script"]

    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    prog = ok(c.get("/api/run/progress"))
    assert prog["started"] and prog["completed"] > 10 and prog["failed"] == 0
    rep = ok(c.get("/api/run/report"))
    assert rep["counts"] == "results/star_salmon/salmon.merged.gene_counts.tsv" and rep["genes"] == 3000 and len(rep["samples"]) == 6
    html = c.get("/api/run/file", params={"path": rep["multiqc"]})
    assert html.status_code == 200 and "sandbox" in html.headers["content-security-policy"]
    assert c.get("/api/run/file", params={"path": "../run.json"}).status_code == 400

    ok(c.post("/api/session/start"))
    wait(lambda: ok(c.get("/api/session/status"))["state"] == "READY")
    o = call(c, "overview")
    assert len(o["samples"]) == 6 and o["missing"] == []
    q = call(c, "sample_qc")
    pc1 = dict(zip(q["samples"], q["pc1"]))
    assert (pc1["control_1"] > 0) == (pc1["control_2"] > 0) != (pc1["treated_1"] > 0)   # conditions separate on PC1

    bad = c.post("/api/s/call/run_de", json={"test": "treated", "reference": "treated"})
    assert bad.status_code == 400 and "two different conditions" in bad.json()["detail"]
    call(c, "run_de", test="treated", reference="control"); wait(lambda: done(c), timeout=600)
    de = ok(c.get("/api/s/status"))["de"]
    truth = json.loads((rd / "demo_truth.json").read_text())
    r = call(c, "results", padj=0.05, n=5000)
    found = {x["gene"] for x in r["rows"]}
    up = {x["gene"] for x in r["rows"] if x["lfc"] > 0}
    # Intent: the demo has 120 genes truly up and 120 down (some too lowly expressed to detect with 3 replicates).
    # DESeq2 should find a good share of them while keeping false calls near the 5% it controls for.
    false = found - set(truth["up"]) - set(truth["down"])
    assert len(up & set(truth["up"])) >= 50 and len(false) <= 0.1 * len(found), (len(up & set(truth["up"])), len(false), len(found))
    assert de["up"] == r["up"] and de["genes_tested"] > 2000
    v = call(c, "volcano")
    assert len(v["x"]) == len(v["y"]) == len(v["sig"]) and sum(1 for s in v["sig"] if s) == r["up"] + r["down"]
    g = call(c, "gene", gene=truth["up"][0])
    assert len(g["values"]) == 6

    call(c, "export", padj=0.05, lfc=1.0); wait(lambda: done(c))
    names = {f["name"] for f in call(c, "files")}
    assert "differential_expression/de_treated_vs_control_significant.csv" in names
    assert c.get("/api/s/download", params={"name": "differential_expression/normalized_counts.csv"}).status_code == 200

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/rnaseq version 3.27.0", "PyDESeq2 (version", "design ~ condition", "control as the reference level",
                   "absolute log2 fold change of at least 1.0", "RNA-seq libraries from 6 samples (control, treated)"):
        assert phrase in rec["methods"], phrase
    assert "**Pipeline:** nf-core/rnaseq release 3.27.0, profile apptainer" in rec["protocol"]

    # Repeat from the bundle in a new folder: same genes found
    new = tmp_path / "repeat_rna"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    f = "results/differential_expression/de_treated_vs_control_significant.csv"
    assert (new / f).read_text() == (rd / f).read_text()
