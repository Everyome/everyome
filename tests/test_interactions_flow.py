"""Interaction prediction end to end on the demo cluster: find complexes, the multimer defaults passed to
nf-core/proteinfold, the stand-in pipeline, interfaces scored (a binder and a non-binder), one interface in detail,
record and an exact repeat. Also pDockQ against the published formula."""
import math

import numpy as np

from everyome.modules.protein.interactions import interface as itf
from flow_helpers import call, demo_client, ok  # noqa: F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session

MID = "protein.interactions"


def test_pdockq_matches_the_paper():
    # Bryant et al. (2022): pDockQ = 0.724 / (1 + e^(-0.052 (x - 152.611))) + 0.018, x = mean interface pLDDT × log10(contacts).
    plddt = np.full(10, 80.0)
    pairs = [(i, 5 + (i % 5)) for i in range(5)] * 20                # 100 contacts among residues 0-9
    x = 80 * math.log10(100)
    assert itf.pdockq(plddt, pairs) == round(0.724 / (1 + math.exp(-0.052 * (x - 152.611))) + 0.018, 3)
    assert itf.pdockq(plddt, []) == 0.018
    xyz = np.array([[0, 0, 0], [0, 0, 5], [0, 0, 30]], float)
    assert itf.contacts(xyz, ["A", "B", "B"], "A", "B") == [(0, 1)]
    assert itf.verdict(0.6, None) == "likely binds as predicted" and itf.verdict(0.1, 0.3) == "unlikely to bind as predicted"
    assert itf.verdict(0.3, 0.7) == "uncertain"


def test_interactions_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "ppi"}))
    scan = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/complexes"}))
    assert [r["id"] for r in scan["rows"]] == ["binder", "nonbinder"]
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"fasta_dir": f"{data}/complexes", "proteins": scan["rows"]}}))
    rd = tmp_path / "demo_cluster/projects/ppi/runs" / run["id"]
    import json
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["alphafold2_model_preset"] == "multimer" and nfp["use_gpu"] is True
    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    r = call(c, "interfaces")
    got = {m["id"]: m["pairs"][0] for m in r["complexes"]}
    assert got["binder"]["verdict"] == "likely binds as predicted" and got["binder"]["contacts"] > 30
    assert got["binder"]["iptm"] == 0.86 and got["binder"]["interface_pae"] < 8
    assert got["nonbinder"]["verdict"] == "unlikely to bind as predicted" and got["nonbinder"]["contacts"] == 0
    d = call(c, "interface", key=next(m["key"] for m in r["complexes"] if m["id"] == "binder"), a="A", b="B")
    assert len(d["side_a"]) == got["binder"]["residues_a"] and d["pae_block"]["rows"] == "A"
    assert call(c, "load")["proteins"] == 2                         # the structure steps work on the same predictions

    rec = ok(c.post("/api/run/record"))
    for phrase in ("multimer model preset", "pDockQ (Bryant et al., 2022)", "binder (alphafold2): chains A–B", "(likely binds as predicted)"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_ppi"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p1.returncode == 0, p1.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert (new / "session/interfaces.json").read_text() == (rd / "session/interfaces.json").read_text()
