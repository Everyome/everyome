"""Single-cell ATAC-seq end to end on the demo cluster: find samples, the reads-to-fragments stage (chromap stand-in),
read fragments with SnapATAC2, filter on fragments and TSS enrichment, cluster on tiles, markers from gene activity,
naming, export, record and an exact repeat. Also the real chromap command line.

Needs SnapATAC2 (pip install -e ".[atac]"); skipped without it.
"""
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("snapatac2")
pytest.importorskip("scanpy")

from flow_helpers import call, demo_client, done, ok, wait  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, wait_for_run, wait_for_session  # noqa: E402

MID = "singlecell.scatac"


def test_chromap_command_line(tmp_path):
    from everyome.modules.singlecell.scatac import stage
    p = {"genome": "/ref/g.fa", "whitelist": "/ref/wl.txt", "chromap_extra": "--min-read-length 25",
         "samples": [{"sample": "s1", "read1": "/r/s1_R1.fastq.gz", "read2": "/r/s1_R3.fastq.gz", "barcodes": "/r/s1_R2.fastq.gz"}]}
    args = stage.chromap_args(p, p["samples"][0], Path("/run/results/genome.index"), Path("/run/results/fragments/s1.tsv"), 8)
    assert args[:3] == ["chromap", "--preset", "atac"]
    for a, b in (("-1", "/r/s1_R1.fastq.gz"), ("-2", "/r/s1_R3.fastq.gz"), ("-b", "/r/s1_R2.fastq.gz"),
                 ("--barcode-whitelist", "/ref/wl.txt"), ("-t", "8"), ("-r", "/ref/g.fa")):
        assert args[args.index(a) + 1] == b, a
    assert args[-2:] == ["--min-read-length", "25"]
    assert sorted(stage.binds(p, "/run")) == ["/r", "/ref", "/run"]


def test_scatac_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "atac"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))["rows"]
    assert [r["sample"] for r in rows] == ["polyp_A", "polyp_B"]
    assert rows[0]["barcodes"].endswith("_R2.fastq.gz") and rows[0]["read2"].endswith("_R3.fastq.gz")
    rows[0]["condition"], rows[1]["condition"] = "control", "treated"

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {
        "reads_dir": f"{data}/fastq", "samples": rows, "genome": f"{data}/reference/genome.fa", "annotation": f"{data}/reference/genes.gtf"}}))
    rd = tmp_path / "demo_cluster/projects/atac/runs" / run["id"]
    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    rep = ok(c.get("/api/run/report"))
    assert all(f["size"] for f in rep["fragments"])

    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)
    call(c, "load", min_fragments=500, bin_size=500); wait(lambda: done(c))
    s = call(c, "load_summary")
    assert [x["sample"] for x in s["samples"]] == ["polyp_A", "polyp_B"]
    assert all(x["cells"] >= 250 and x["median_tsse"] > 4 for x in s["samples"])
    assert set(s["frag_sizes"]) == {"polyp_A", "polyp_B"}

    q = call(c, "qc_data")
    assert q["thresholds"]["min_counts"] == 1000 and q["thresholds"]["min_genes"] == 4
    th = {"min_counts": 1000, "max_counts": 100000, "min_genes": 4, "max_genes": 1000}
    call(c, "qc_apply", **th); wait(lambda: done(c))

    call(c, "cluster", n_top_genes=200, n_pcs=15, n_neighbors=15, resolution=0.4, min_dist=0.3, batch_key="sample", harmony=False)
    wait(lambda: done(c), timeout=600)
    summ = call(c, "cluster_summary")
    assert 3 <= len(summ["clusters"]) <= 8, summ["clusters"]

    # Each cluster's top markers come from one cell type's planted genes, and every type is found.
    truth = json.loads((tmp_path / "demo_cluster/data" / MID / ".demo_truth/markers.json").read_text())
    found = {}
    for cl in summ["clusters"]:
        top = [g["gene"] for g in call(c, "markers", cluster=cl["id"])[:5]]
        hits = {t for t, genes in truth.items() if sum(g in genes for g in top) >= 3}
        if hits:
            found[cl["id"]] = hits.pop()
    assert set(found.values()) == set(truth), found
    for cid, name in found.items():
        call(c, "annotate", cluster=cid, name=name.capitalize(), color="#C2A24A")
    call(c, "export", group="condition"); wait(lambda: done(c), timeout=600)
    assert "annotated.h5ad" in {f["name"] for f in call(c, "files")}

    rec = ok(c.post("/api/run/record"))
    for phrase in ("Chromap", "using its ATAC-seq preset", "SnapATAC2", "TSS enrichment below 4", "spectral embedding",
                   "as 4 cell types"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_atac"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p1.returncode == 0, p1.stderr
    from rerun_helpers import rerun_until_session_replayed
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    f = "results/composition_counts_by_condition.csv"
    assert (new / f).read_text() == (rd / f).read_text()
