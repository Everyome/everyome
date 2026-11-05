"""Imaging spatial end to end on the demo cluster (Xenium-style sections): find sections, read cells, filter, cluster,
markers, naming, the tissue view, spatially variable genes, neighbourhoods, export, record and an exact repeat.
Also the MERSCOPE and CosMx readers on small tables in their formats.

Needs the singlecell extra; skipped without it.
"""
import json

import numpy as np
import pytest

pytest.importorskip("scanpy")
pytest.importorskip("leidenalg")

from flow_helpers import call, demo_client, done, ok, wait  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, wait_for_session  # noqa: E402

MID = "spatial.imaging"


def test_merscope_and_cosmx_readers(tmp_path):
    from everyome.modules.spatial.imaging.readers import detect, read
    m = tmp_path / "merscope"
    m.mkdir()
    (m / "cell_by_gene.csv").write_text("cell,GeneA,GeneB,Blank-1\nc1,3,0,1\nc2,1,5,0\n")
    (m / "cell_metadata.csv").write_text("EntityID,fov,volume,center_x,center_y\nc1,0,200,10.5,20.0\nc2,0,180,30.0,40.5\n")
    a, plat = read(str(m))
    assert plat == "merscope" and list(a.var_names) == ["GeneA", "GeneB"] and a.obsm["spatial"].tolist() == [[10.5, 20.0], [30.0, 40.5]]
    c = tmp_path / "cosmx"
    c.mkdir()
    (c / "Run1_exprMat_file.csv").write_text("fov,cell_ID,GeneA,NegPrb1,GeneB\n1,0,9,9,9\n1,1,2,0,1\n2,1,0,1,4\n")
    (c / "Run1_metadata_file.csv").write_text("fov,cell_ID,CenterX_global_px,CenterY_global_px\n1,1,100,200\n2,1,300,400\n")
    assert detect(c) == "cosmx"
    a, plat = read(str(c))
    assert list(a.obs_names) == ["1_1", "2_1"] and list(a.var_names) == ["GeneA", "GeneB"]
    assert np.asarray(a.X.todense()).tolist() == [[2, 1], [0, 4]] and a.obsm["spatial"][1].tolist() == [300, 400]


def test_imaging_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "xen"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": data}))["rows"]
    assert [(r["sample"], r["platform"]) for r in rows] == [("section_control", "xenium"), ("section_treated", "xenium")]
    rows[0]["condition"], rows[1]["condition"] = "control", "treated"
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"data_dir": data, "samples": rows}}))
    rd = tmp_path / "demo_cluster/projects/xen/runs" / run["id"]
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    call(c, "load"); wait(lambda: done(c))
    n = call(c, "spots_per_sample")
    assert n == {"section_control": 3000, "section_treated": 3000}
    t = call(c, "tissue", sample="section_control", key="total_counts")
    assert len(t["x"]) == 3000 and t["image"] == "" and t["colour"]["gene"] == "Transcripts per cell"
    assert not any(g.startswith("NegControl") for g in [x["gene"] for x in call(c, "genes", q="Neg")])

    q = call(c, "qc_data")
    assert q["thresholds"]["min_counts"] == 10 and q["mito_edges"] is None
    call(c, "qc_apply", min_counts=10, max_counts=100000, min_genes=5, max_genes=10000); wait(lambda: done(c))
    call(c, "cluster", n_top_genes=100, n_pcs=15, n_neighbors=15, resolution=0.3, min_dist=0.3, batch_key="sample", harmony=False)
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

    call(c, "spatial_genes"); wait(lambda: done(c))
    sv = ok(c.get("/api/s/status"))["spatial_genes"]
    assert sv[0]["morans_i"] > 0.3 and sum(g["gene"][:4] in ("epid", "gast", "musc", "neur") for g in sv[:10]) >= 8

    call(c, "neighbourhood", by="annotation", k=10, permutations=50); wait(lambda: done(c))
    nh = ok(c.get("/api/s/status"))["neighbourhood"]
    z, ratio, g = dict(zip(nh["groups"], nh["z"])), dict(zip(nh["groups"], nh["log2_ratio"])), nh["groups"]
    # Rings: each type sits with its own kind, borders the next ring in, and never touches rings further off.
    assert z["epidermis"][g.index("epidermis")] > 10
    assert ratio["epidermis"][g.index("gastrodermis")] > ratio["epidermis"][g.index("neuron")] + 2
    assert ratio["epidermis"][g.index("neuron")] < -3 and z["epidermis"][g.index("neuron")] < -5

    comp = call(c, "composition", group="condition")
    share = dict(zip(comp["groups"], comp["fractions"][comp["types"].index("immune")]))
    assert share["treated"] > 0.01 and share["control"] < 0.005
    call(c, "export", group="condition"); wait(lambda: done(c), timeout=600)

    rec = ok(c.post("/api/run/record"))
    for phrase in ("imaged on 10x Genomics Xenium", "control probes were excluded", "Moran's I", "Neighbourhood enrichment", "fewer than 10"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_xen"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert p1.returncode == 0, p1.stderr
    p2 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--session")
    assert p2.returncode == 0, p2.stderr
    f = "results/composition_counts_by_condition.csv"
    assert (new / f).read_text() == (rd / f).read_text()
