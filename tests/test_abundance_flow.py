"""RNA abundance end to end on the demo cluster: read samples from an nf-core/rnaseq results folder, check samples,
look up a gene, find the planted expression patterns, export, record and an exact repeat."""
import json

from everyome.core import server  # noqa: F401  (imported so the app's state is set up before the fixture)
from everyome.modules.rna.abundance.engine import kmeans
from flow_helpers import call, demo_client, ok  # noqa: F401  (demo_client is a fixture)
from rerun_helpers import rerun, wait_for_session

import numpy as np

MID = "rna.abundance"


def test_kmeans_is_repeatable_and_finds_clear_groups():
    rng = np.random.default_rng(0)
    x = np.vstack([rng.normal(m, 0.1, size=(30, 3)) for m in ([3, 0, 0], [0, 3, 0], [0, 0, 3])])
    a, b = kmeans(x, 3), kmeans(x, 3)
    assert (a == b).all()
    assert sorted(np.bincount(a)) == [30, 30, 30]
    assert list(a[[0, 30, 60]]) == [0, 1, 2]                 # clusters numbered by the sample where they peak


def test_abundance_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "polyp"}))
    scan = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/results"}))
    rows = scan["rows"]
    assert [r["group"] for r in rows] == ["oral"] * 3 + ["aboral"] * 3 + ["tentacle"] * 3

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"results_dir": f"{data}/results", "samples": rows}}))
    rd = tmp_path / "demo_cluster/projects/polyp/runs" / run["id"]
    assert ok(c.post("/api/run/preview", json={}))["scripts"] == []        # no cluster stages
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    o = call(c, "overview")
    assert o["genes"] == 2000 and len(o["samples"]) == 9 and o["normalised"].startswith("log2 of size-factor")
    qc = call(c, "sample_qc")
    # Replicates of one tissue correlate best with each other.
    corr = np.array(qc["corr"])
    for i in range(9):
        best = max((j for j in range(9) if j != i), key=lambda j: corr[i, j])
        assert best // 3 == i // 3, (i, best)

    g = call(c, "gene", q="tentacle1")
    by = {v["sample"]: v["tpm"] for v in g["values"]}
    assert min(by[f"tentacle_{r}"] for r in (1, 2, 3)) > max(by[f"oral_{r}"] for r in (1, 2, 3))
    assert "choices" in call(c, "gene", q="oral")              # several genes match: the app asks which
    assert len(call(c, "top_genes", n=10)) == 10

    p = call(c, "patterns", n_genes=300, k=4, min_tpm=1)
    assert sum(p["sizes"]) == 300 and len(p["profiles"]) == 4
    truth = json.loads((tmp_path / "demo_cluster/data" / MID / ".demo_truth/patterns.json").read_text())
    clusters = {}
    for line in (rd / "results/gene_clusters.csv").read_text().splitlines()[1:]:
        gid, _, cl = line.split(",")
        clusters[gid] = int(cl)
    # Intent: each tissue's planted genes land mostly in one cluster, and a different one for each tissue.
    homes = []
    for tissue, ids in truth.items():
        got = [clusters[i] for i in ids if i in clusters]
        top = max(set(got), key=got.count)
        assert got.count(top) >= 0.8 * len(got), (tissue, got)
        homes.append(top)
    assert len(set(homes)) == 3

    call(c, "export")
    assert {"tpm.csv", "normalised_log2.csv", "samples.csv", "gene_clusters.csv"} <= {f["name"] for f in call(c, "files")}

    rec = ok(c.post("/api/run/record"))
    for phrase in ("for 9 samples (aboral, oral, tentacle)", "median-of-ratios", "grouped into 4 clusters by k-means"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_abundance"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert p1.returncode == 0, p1.stderr
    p2 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--session")
    assert p2.returncode == 0, p2.stderr
    for f in ("results/gene_clusters.csv", "results/tpm.csv"):
        assert (new / f).read_text() == (rd / f).read_text(), f
