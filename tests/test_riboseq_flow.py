"""Ribo-seq end to end on the demo cluster: samples table (type, pair, condition), pipeline (stand-in) with a contrasts
file, report, periodicity, ORFs, translational efficiency against the planted truth, export, record and an exact repeat.

Needs pandas and scipy (the rna extra); skipped without them.
"""
import json

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("pandas")

from everyome.modules.rna.riboseq.engine import bh, moderated_t, pairs_of  # noqa: E402
from everyome.modules.rna.riboseq import helpers  # noqa: E402
from everyome.modules.rna.riboseq.helpers import strip_type, type_of  # noqa: E402
from flow_helpers import call, demo_client, ok  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session  # noqa: E402

MID = "rna.riboseq"


def test_names_pairs_and_test():
    assert [type_of(n) for n in ("wt_1_ribo", "wt_1_RNA", "ko-rpf-2", "harr_1", "sample3")] == ["riboseq", "rnaseq", "riboseq", "tiseq", "rnaseq"]
    assert strip_type("wt_1_ribo") == strip_type("wt_1_rna") == "wt_1"
    # Without a pair column, libraries pair in order within each condition (as nf-core/riboseq does).
    rows = [{"sample": s, "type": t, "condition": c} for s, t, c in
            (("a1", "riboseq", "x"), ("a2", "riboseq", "x"), ("b1", "rnaseq", "x"), ("b2", "rnaseq", "x"))]
    assert [(p["ribo"], p["rna"]) for p in pairs_of(rows)] == [("a1", "b1"), ("a2", "b2")]
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, (500, 3)), rng.normal(0, 1, (500, 3))
    a[:20] += 6
    d, t, p = moderated_t(a, b)
    q = bh(p)
    assert (q[:20] < 0.05).sum() >= 18 and (q[20:] < 0.05).sum() <= 2


def test_riboseq_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "ribo"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))["rows"]
    assert len(rows) == 12 and {r["type"] for r in rows} == {"riboseq", "rnaseq"}
    assert {r["pair"] for r in rows} == {f"{c}_{i}" for c in ("control", "treated") for i in (1, 2, 3)}
    assert all(bool(r["fastq_2"]) == (r["type"] == "rnaseq") for r in rows)

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {
        "reads_dir": f"{data}/fastq", "samples": rows, "fasta": f"{data}/genome/genome.fa", "gtf": f"{data}/genome/genes.gtf"}}))
    rd = tmp_path / "demo_cluster/projects/ribo/runs" / run["id"]
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert "aligner" not in nfp                                                        # only changed settings go to the pipeline
    # Intent: with no contrasts file given, Everyome writes one from the samples table (each condition against the first).
    assert nfp["contrasts"] == f"{rd}/contrasts.csv"
    assert (rd / "contrasts.csv").read_text() == "id,variable,reference,target,batch,pair\ntreated_vs_control,condition,control,treated,,pair\n"
    assert helpers.contrasts({"samples": [{**r, "condition": "control"} for r in rows]}) == ""
    sheet = (rd / "samplesheet.csv").read_text().splitlines()
    assert sheet[0] == "sample,fastq_1,fastq_2,strandedness,type,pair,condition"

    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    rep = ok(c.get("/api/run/report"))
    assert rep["counts"].endswith("inframe_psite/gene_counts.tsv") and rep["genes"] == 1500 and len(rep["libraries"]) == 12
    assert rep["multiqc"] and rep["orfs"] > 1500 and max(rep["lengths"]["control_1_ribo"], key=rep["lengths"]["control_1_ribo"].get) == "29"

    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)
    truth = json.loads((tmp_path / "demo_cluster/data" / MID / ".demo_truth/truth.json").read_text())

    o = call(c, "overview")
    assert len(o["pairs"]) == 6 and o["anota2seq"] == ["treated_vs_control"] and len(o["periodicity_samples"]) == 6
    p = call(c, "periodicity")
    assert all(s["frame0"] > 0.6 for s in p["summary"])
    by = {b["length"]: b for b in p["detail"]["by_length"]}
    assert by[29]["offset"] == 12 and by[29]["frames"][0] > 0.65 and by[34]["frames"][0] < 0.45
    start = dict(zip(p["detail"]["start"]["x"], p["detail"]["start"]["y"]))
    assert sum(start[x] for x in range(0, 60, 3)) > 2 * sum(start[x] for x in range(1, 60, 3))     # the 3-nt rhythm

    orfs = call(c, "orfs", cls="uORF", n=500)
    assert orfs["classes"]["uORF"] == sum(1 for x in truth["orfs"] if x["class"] == "uORF") > 20
    assert {r["gene"] for r in orfs["rows"]} == set(truth["uorf_genes"])
    assert call(c, "orfs", q="teup1", n=10)["matching"] >= 1

    bad = c.post("/api/s/call/te", json={"test": "treated", "reference": "treated"})
    assert bad.status_code == 400
    te = call(c, "te", test="treated", reference="control")
    r = call(c, "results", n=2000)
    called = {x["gene"] for x in r["rows"] if x["class"] in ("translation", "buffering")}
    up = {x["gene"] for x in r["rows"] if x["class"] in ("translation", "buffering") and x["te"] > 0}
    planted = set(truth["te_up"]) | set(truth["te_down"])
    # Intent: most planted TE changes are found, almost nothing else is, and genes whose mRNA alone changed are not called.
    assert len(up & set(truth["te_up"])) >= 25 and len(called - planted) <= 0.05 * len(called), (len(up), len(called - planted))
    assert not called & (set(truth["rna_up"]) | set(truth["rna_down"]))
    assert r["classes"]["mRNA abundance"] >= 40
    assert te["anota2seq"]["contrast"] == "treated_vs_control" and te["anota2seq"]["both"] == te["anota2seq"]["significant"]
    g = call(c, "gene", q=truth["te_up"][0])
    assert len(g["pairs"]) == 6 and g["te"]["te_log2fc"] > 0 and g["orfs"]

    call(c, "export")
    assert {"final/periodicity.csv", "final/orfs.csv", "final/te_treated_vs_control.csv"} <= {f["name"] for f in call(c, "files")}

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/riboseq version 2.0.0", "anota2seq (Oertlin et al., 2019), comparing treated with control", "6 Ribo-seq and 6 matched RNA-seq libraries", "riboWaltz", "annotated reading frame (frame 0)",
                   "moderated t-test", "6 Ribo-seq/RNA-seq pairs", "anota2seq's translation analysis"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_ribo"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p1.returncode == 0, p1.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    f = "results/final/te_treated_vs_control.csv"
    assert (new / f).read_text() == (rd / f).read_text()
