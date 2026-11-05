"""ATAC-seq end to end on the demo cluster: libraries table, pipeline (stand-in), report, library checks, peaks,
DESeq2 comparison, a region, export, record and an exact repeat. Also the settings check that stops a run with no
genome size (the pipeline would skip peak calling).

Needs the rna extra for PyDESeq2 (pip install -e ".[rna]"); skipped without it.
"""
import json

import pytest

pytest.importorskip("pydeseq2")

from everyome.modules.dna.atac import helpers  # noqa: E402
from flow_helpers import call, demo_client, follow, ok  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session  # noqa: E402

MID = "dna.atac"


def test_settings_check():
    base = {"fasta": "/g/genome.fa", "gtf": "/g/genes.gtf", "libraries": [{"group": "a", "replicate": "1"}]}
    assert any("genome size" in p for p in helpers.check(base))
    assert helpers.check({**base, "macs_gsize": 4e8}) == [] and helpers.check({**base, "read_length": 100}) == []
    assert helpers.check({"genome": "GRCm38", "libraries": base["libraries"]}) == []
    assert helpers.libraries({"libraries": [{"group": "wt", "replicate": "1"}, {"group": "wt", "replicate": 1}, {"group": "wt", "replicate": "2"}]}) == [
        {"library": "wt_REP1", "group": "wt", "replicate": 1}, {"library": "wt_REP2", "group": "wt", "replicate": 2}]


def test_atac_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "atac"}))
    ok(c.get(f"/api/modules/{MID}/example"))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))["rows"]
    assert [(r["group"], r["replicate"]) for r in rows] == [("planula", "1"), ("planula", "2"), ("planula", "3"),
                                                            ("polyp", "1"), ("polyp", "2"), ("polyp", "3")]
    assert all(r["fastq_2"] for r in rows)

    # Without a genome size the run is refused before anything is written.
    bad = c.post("/api/run/create", json={"module": MID, "values": {"libraries": rows, "fasta": f"{data}/genome/genome.fa",
                                                                       "gtf": f"{data}/genome/genes.gtf", "macs_gsize": None}})
    assert bad.status_code == 400 and "genome size" in bad.json()["detail"]

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"reads_dir": f"{data}/fastq", "libraries": rows,
                                                                        "fasta": f"{data}/genome/genome.fa", "gtf": f"{data}/genome/genes.gtf",
                                                                        "macs_gsize": 2000000}}))
    rd = tmp_path / "demo_cluster/projects/atac/runs" / run["id"]
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["macs_gsize"] == 2000000 and nfp["narrow_peak"] is True and nfp["gtf"].endswith("genes.gtf")
    assert (rd / "samplesheet.csv").read_text().startswith("sample,fastq_1,fastq_2,replicate\nplanula,")

    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    prog = ok(c.get("/api/run/progress"))
    assert prog["completed"] > 30 and prog["failed"] == 0
    rep = ok(c.get("/api/run/report"))
    assert rep["kind"] == "narrow_peak" and rep["consensus"].endswith("narrow_peak/consensus/consensus_peaks.mLb.clN.featureCounts.txt")
    frip = {l["library"]: l["frip"] for l in rep["libraries"]}
    assert set(frip) == {f"{g}_REP{r}" for g in ("planula", "polyp") for r in (1, 2, 3)} and frip["polyp_REP3"] < 0.2
    assert rep["consensus_peaks"] > 500 and all(l["peaks"] > 300 for l in rep["libraries"]) and rep["multiqc"]

    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)
    o = call(c, "overview")
    assert o["consensus_peaks"] == rep["consensus_peaks"] and o["missing"] == [] and len(o["libraries"]) == 6
    q = call(c, "sample_qc")
    pc1 = dict(zip(q["libraries"], q["pc1"]))
    assert len({pc1[f"polyp_REP{r}"] > 0 for r in (1, 2, 3)}) == 1 and (pc1["polyp_REP1"] > 0) != (pc1["planula_REP1"] > 0)
    p = call(c, "peaks")
    assert sum(p["widths"]["counts"]) == p["consensus_peaks"] and 20 < p["tss"]["promoter_share"] < 70

    bad = c.post("/api/s/call/run_da", json={"test": "polyp", "reference": "polyp"})
    assert bad.status_code == 400 and "two different groups" in bad.json()["detail"]
    follow(c, "run_da", test="planula", reference="polyp")
    da = ok(c.get("/api/s/status"))["da"]
    truth = json.loads((rd / "demo_truth.json").read_text())
    r = call(c, "results", padj=0.05, n=5000)
    opening = {x["peak"] for x in r["rows"] if x["lfc"] > 0}
    closing = {x["peak"] for x in r["rows"] if x["lfc"] < 0}
    found = opening | closing
    false = found - set(truth["up"]) - set(truth["down"])
    # Intent: 70 sites truly open and 70 close 4-fold in planula; with three replicates DESeq2 should find most of the
    # stronger ones while keeping false calls near the 5% it controls for.
    assert len(opening & set(truth["up"])) >= 30 and len(closing & set(truth["down"])) >= 30, (len(opening), len(closing))
    assert len(false) <= 0.1 * len(found), (len(false), len(found))
    assert da["opening"] == r["opening"] and da["peaks_tested"] > 500
    v = call(c, "volcano")
    assert len(v["x"]) == len(v["y"]) and sum(1 for s in v["sig"] if s) == r["opening"] + r["closing"]
    near = next(x for x in r["rows"] if x["gene"])
    assert call(c, "results", q=near["gene"])["rows"]

    top = r["rows"][0]["peak"]
    loc = call(c, "locus", q=top, pad=3000)
    hit = next(x for x in loc["consensus"] if x["peak"] == top)
    assert hit["padj"] < 0.05 and len(loc["tracks"]) == 6 and loc["end"] - loc["start"] > 6000
    assert any(t["peaks"] for t in loc["tracks"] if t["group"] == ("planula" if hit["lfc"] > 0 else "polyp"))
    g = call(c, "locus", q="atg1")
    assert any(x["gene"] == "atg1" for x in g["genes"])
    assert c.post("/api/s/call/locus", json={"q": "nothing_here"}).status_code == 400

    call(c, "export", padj=0.05, lfc=1.0)
    names = {f["name"] for f in call(c, "files")}
    assert {"final/consensus_peaks_counts.csv", "final/da_planula_vs_polyp_significant.csv", "final/da_planula_vs_polyp_significant.bed",
            "final/normalised_log2.csv", "final/libraries.csv"} <= names
    assert c.get("/api/s/download", params={"name": "final/da_planula_vs_polyp_significant.csv"}).status_code == 200

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/atacseq version 2.1.2", "6 libraries from 2 groups: planula, polyp", "narrow-peak mode",
                   "effective genome size of 2,000,000 bp", "PyDESeq2 (version", "polyp as the reference level",
                   "absolute log2 fold change of at least 1.0"):
        assert phrase in rec["methods"], phrase
    assert "**Pipeline:** nf-core/atacseq release 2.1.2, profile apptainer" in rec["protocol"]

    new = tmp_path / "repeat_atac"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p1.returncode == 0, p1.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("results/final/da_planula_vs_polyp_significant.csv", "results/final/consensus_peaks_counts.csv"):
        assert (new / f).read_text() == (rd / f).read_text(), f
