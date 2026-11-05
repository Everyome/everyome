"""High-resolution spatial end to end on the demo cluster (Visium HD-style sections): find sections, read at 16 then
8 µm, filter, cluster, markers, naming, tissue view over the image, neighbourhoods, export, record and an exact repeat.
Also the Stereo-seq (GEM) and Curio readers on small files in their formats.

Needs the singlecell extra; skipped without it.
"""
import gzip
import json

import numpy as np
import pytest

pytest.importorskip("scanpy")
pytest.importorskip("leidenalg")

from flow_helpers import call, demo_client, done, ok, wait  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, wait_for_session  # noqa: E402

MID = "spatial.hires"


def test_stereo_and_curio_readers(tmp_path):
    import anndata as ad
    import pandas as pd
    from everyome.modules.spatial.hires.readers import detect, read
    s = tmp_path / "stereo"
    s.mkdir()
    with gzip.open(s / "A1.gem.gz", "wt") as fh:
        fh.write("#FileFormat=GEMv0.1\n#SortedBy=None\ngeneID\tx\ty\tMIDCount\nGeneA\t0\t0\t2\nGeneA\t3\t1\t1\nGeneB\t25\t0\t4\nGeneA\t25\t25\t1\n")
    assert detect(s) == "stereo"
    a, meta, plat = read(str(s), "", bin_um=10)                       # 10 µm = 20 DNB spots per side
    by = {n: dict(zip(a.var_names, np.asarray(a[n].X.todense()).ravel())) for n in a.obs_names}
    assert sorted(by) == ["bin10_0_0", "bin10_1_0", "bin10_1_1"] and by["bin10_0_0"] == {"GeneA": 3, "GeneB": 0}
    assert a.obsm["spatial"][list(a.obs_names).index("bin10_1_1")].tolist() == [15.0, 15.0]
    c = tmp_path / "curio"
    c.mkdir()
    b = ad.AnnData(np.array([[1, 0], [2, 3]], dtype=np.float32), obs=pd.DataFrame(index=["b1", "b2"]), var=pd.DataFrame(index=["GeneA", "GeneB"]))
    b.obsm["spatial"] = np.array([[1.0, 2.0], [3.0, 4.0]])
    b.write_h5ad(c / "sample_anndata.h5ad")
    a, meta, plat = read(str(c))
    assert plat == "curio" and a.obsm["spatial"].tolist() == [[1.0, 2.0], [3.0, 4.0]]


def test_hires_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "hd"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": data}))["rows"]
    assert [(r["sample"], r["platform"]) for r in rows] == [("hd_control", "visium_hd"), ("hd_treated", "visium_hd")]
    rows[0]["condition"], rows[1]["condition"] = "control", "treated"
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"data_dir": data, "samples": rows, "mito_genes": ""}}))
    rd = tmp_path / "demo_cluster/projects/hd/runs" / run["id"]
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    call(c, "load", bin_um=16); wait(lambda: done(c))
    assert call(c, "spots_per_sample") == {"hd_control": 45 * 45, "hd_treated": 45 * 45}
    call(c, "load", bin_um=8); wait(lambda: done(c))
    assert call(c, "spots_per_sample") == {"hd_control": 90 * 90, "hd_treated": 90 * 90}
    t = call(c, "tissue", sample="hd_treated", key="total_counts")
    assert t["image"].startswith("data:image/png;base64,") and t["width"] == 600 and len(t["x"]) == 8100
    assert max(t["x"]) <= 600 and t["colour"]["gene"] == "UMIs per bin"

    call(c, "qc_apply", min_counts=20, max_counts=100000, min_genes=10, max_genes=10000); wait(lambda: done(c))
    call(c, "cluster", n_top_genes=200, n_pcs=15, n_neighbors=15, resolution=0.3, min_dist=0.3, batch_key="sample", harmony=False)
    wait(lambda: done(c), timeout=600)
    truth = json.loads((tmp_path / "demo_cluster/data" / MID / ".demo_truth/markers.json").read_text())
    named = {}
    for cl in call(c, "cluster_summary")["clusters"]:
        top = [g["gene"] for g in call(c, "markers", cluster=cl["id"])[:5]]
        hit = next((t for t, genes in truth.items() if sum(g in genes for g in top) >= 3), None)
        if hit:
            named[cl["id"]] = hit
            call(c, "annotate", cluster=cl["id"], name=hit, color="#C2A24A")
    assert set(named.values()) == set(truth), named

    call(c, "neighbourhood", by="annotation", k=8, permutations=50); wait(lambda: done(c))
    nh = ok(c.get("/api/s/status"))["neighbourhood"]
    ratio, g = dict(zip(nh["groups"], nh["log2_ratio"])), nh["groups"]
    # Bands: epidermis borders gastrodermis, never neurons (two bands away).
    assert ratio["epidermis"][g.index("gastrodermis")] > ratio["epidermis"][g.index("neuron")] + 2

    comp = call(c, "composition", group="condition")
    share = dict(zip(comp["groups"], comp["fractions"][comp["types"].index("immune")]))
    assert share["treated"] > 0.01 and share["control"] < 0.005
    call(c, "export", group="condition"); wait(lambda: done(c), timeout=600)

    rec = ok(c.post("/api/run/record"))
    for phrase in ("10x Genomics Visium HD", "Space Ranger's 8-µm bins", "Each bin was treated as one observation", "Neighbourhood enrichment"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_hd"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert p1.returncode == 0, p1.stderr
    p2 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--session")
    assert p2.returncode == 0, p2.stderr
    f = "results/composition_counts_by_condition.csv"
    assert (new / f).read_text() == (rd / f).read_text()
