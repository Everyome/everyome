"""Multiome end to end on the demo cluster: find Cell Ranger ARC outputs, read genes and peaks, filter, cluster on RNA
only (three groups) and on both together (all four planted types), markers, naming, export, record and an exact
repeat.

Needs muon (pip install -e ".[atac]"); skipped without it.
"""
import json

import pandas as pd
import pytest

pytest.importorskip("muon")
pytest.importorskip("scanpy")

from flow_helpers import call, demo_client, done, ok, wait  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, wait_for_session  # noqa: E402

MID = "singlecell.multiome"
SETTINGS = {"n_top_genes": 200, "n_pcs": 20, "n_neighbors": 15, "resolution": 1.2, "min_dist": 0.3, "batch_key": "sample", "harmony": False}


def test_multiome_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "multi"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": data}))["rows"]
    assert [r["sample"] for r in rows] == ["polyp_A", "polyp_B"] and all(r["outs"].endswith("/outs") for r in rows)
    rows[0]["condition"], rows[1]["condition"] = "control", "treated"
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"data_dir": data, "samples": rows, "mito_genes": "^mt-"}}))
    rd = tmp_path / "demo_cluster/projects/multi/runs" / run["id"]
    assert ok(c.post("/api/run/preview", json={}))["scripts"] == []
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    call(c, "load", min_atac=500); wait(lambda: done(c))
    s = call(c, "load_summary")
    assert [x["cells"] for x in s["samples"]] == [260, 260]
    th = {"min_counts": 300, "max_counts": 100000, "min_genes": 50, "max_genes": 10000, "max_mito": 20}
    call(c, "qc_apply", **th); wait(lambda: done(c))

    import scanpy as sc
    truth = json.loads((tmp_path / "demo_cluster/data" / MID / ".demo_truth/cell_types.json").read_text())

    def groups():
        a = sc.read_h5ad(rd / "session/clustered.h5ad")
        ct = pd.crosstab(a.obs["cluster"].values, [truth[n] for n in a.obs_names])
        pure = (ct.max(1) / ct.sum(1) >= 0.9).sum()
        return len(ct), int(pure), int((ct.max(0) / ct.sum(0) >= 0.9).sum())

    # RNA alone can't tell cnidocytes from neurons: no cluster holds 90% of either.
    call(c, "cluster", **SETTINGS, mode="rna"); wait(lambda: done(c), timeout=600)
    n, pure, types_found = groups()
    assert types_found == 2, (n, pure, types_found)          # epidermis and gastrodermis only
    # Both together find all four.
    call(c, "cluster", **SETTINGS, mode="joint"); wait(lambda: done(c), timeout=600)
    n, pure, types_found = groups()
    assert types_found == 4 and pure == n, (n, pure, types_found)
    w = call(c, "colour", key="rna_weight")
    assert w["kind"] == "num"

    for cl in call(c, "cluster_summary")["clusters"]:
        top = [g["gene"] for g in call(c, "markers", cluster=cl["id"])[:3]]
        name = next((p for p in ("epid", "gast", "cnne") if any(g.startswith(p) for g in top)), "")
        if name:
            call(c, "annotate", cluster=cl["id"], name=name, color="#C2A24A")
    call(c, "export", group="condition"); wait(lambda: done(c), timeout=600)

    rec = ok(c.post("/api/run/record"))
    for phrase in ("Cell Ranger ARC", "fewer than 500 ATAC counts", "latent semantic indexing", "weighted nearest neighbours",
                   "On average, cells weighted their RNA"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_multi"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert p1.returncode == 0, p1.stderr
    p2 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--session")
    assert p2.returncode == 0, p2.stderr
    f = "results/composition_counts_by_condition.csv"
    assert (new / f).read_text() == (rd / f).read_text()
