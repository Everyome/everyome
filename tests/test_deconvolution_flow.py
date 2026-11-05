"""Cell types in spots end to end on the demo cluster: two GPU stages (cell2location stand-ins), the run report, the
session (mapping checks, each type on the tissue against the known make-up of every spot, the main type, signature
genes, cell types found together), export, record and an exact repeat. Also the GPU job headers."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scanpy")

from everyome.core import runs  # noqa: E402
from everyome.core.manifest import load  # noqa: E402
from everyome.modules.spatial.deconvolution import stage  # noqa: E402
from flow_helpers import call, demo_client, ok  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session  # noqa: E402

MID = "spatial.deconvolution"
HERE = Path(stage.__file__).parent


def test_gpu_stages_and_missing_cell2location(tmp_path, monkeypatch):
    m = load(HERE / "module.yaml")
    run = {"dir": "/r", "user": "u", "resources": {"cpus": 4, "mem": "32G", "time": "12:00:00", "partition": "normal"},
           "values": {"gpu_partition": "gpu"}, "pipelines_dir": "/p"}
    for s in m.stages:
        script = runs.stage_script(run, m, s, "python")
        assert "#SBATCH --gres=gpu:1" in script and "#SBATCH --partition=gpu" in script
    assert "#SBATCH --mem=64G" in runs.stage_script(run, m, m.stages[1], "python")
    # Without cell2location in Everyome's Python, the stage says what to ask IT for.
    monkeypatch.delenv("EVERYOME_DEMO", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "cell2location", None)
    with pytest.raises(RuntimeError, match=r"everyome\[deconvolution\]"):
        stage.reference({"reference": str(tmp_path / "ref.h5ad")}, tmp_path)


def test_deconvolution_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "c2l"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/visium"}))["rows"]
    assert [r["sample"] for r in rows] == ["skin_control", "skin_treated"] and set(rows[0]) == {"sample", "outs"}
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"samples": rows, "reference": f"{data}/reference.h5ad"}}))
    rd = tmp_path / "demo_cluster/projects/c2l/runs" / run["id"]
    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    rep = ok(c.get("/api/run/report"))
    assert len(rep["types"]) == 5 and rep["spots"] > 1000 and len(rep["mapping_curve"]) > 50

    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)
    o = call(c, "overview")
    assert o["sections"] == ["skin_control", "skin_treated"] and "Immune cells" in o["types"]
    imm = next(t for t in o["per_type"] if t["type"] == "Immune cells")
    assert imm["skin_treated"] > 20 * imm["skin_control"]                 # immune cells only in the treated section

    truth = pd.read_csv(f"{data}/.demo_truth/spots.csv")
    t = call(c, "tissue", sample="skin_treated", key="Keratinocytes", measure="share")
    tr = truth[truth["sample"] == "skin_treated"]["Keratinocytes"].to_numpy()
    assert t["spots"] == len(tr) and t["image"].startswith("data:image/png") and np.corrcoef(t["colour"]["values"], tr)[0, 1] > 0.95
    d = call(c, "tissue", sample="skin_treated", key="dominant")
    main = [d["colour"]["categories"][k] for k in d["colour"]["codes"]]
    true_main = truth[truth["sample"] == "skin_treated"].iloc[:, 3:].idxmax(axis=1).tolist()
    assert np.mean([a == b for a, b in zip(main, true_main)]) > 0.9
    s = call(c, "signature", cell_type="Smooth muscle cells")
    assert {g["gene"] for g in s["genes"][:5]} == {"ACTA2", "MYH11", "DES", "CNN1", "TAGLN"}

    r = call(c, "together", measure="share")
    assert len(r["corr"]) == 5 and all(abs(r["corr"][i][i] - 1) < 1e-6 for i in range(5))
    pairs = {frozenset(p[:2]): p[2] for p in r["pairs"]}
    assert pairs[frozenset(("Keratinocytes", "Smooth muscle cells"))] < 0               # top and bottom layers never meet
    bad = c.post("/api/s/call/tissue", json={"sample": "skin_treated", "key": "Neurons"})
    assert bad.status_code == 400 and "No cell type called Neurons" in bad.json()["detail"]

    call(c, "export")
    names = {f["name"] for f in call(c, "files")}
    assert {"final/cell_abundance_mean.csv", "final/cell_type_shares.csv", "final/main_cell_type.csv", "final/cell_types_together.csv"} <= names

    rec = ok(c.post("/api/run/record"))
    for phrase in ("Cell types in 2 10x Visium sections (skin_control and skin_treated) were mapped with cell2location",
                   "Kleshchevnikov et al., 2022", "each of 5 cell types", "an expected 30 cells per spot and a detection alpha of 20",
                   "Pearson correlation of their share of each spot"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_c2l"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("cell_type_shares.csv", "main_cell_type.csv", "cell_types_together.csv"):
        assert (new / "results/final" / f).read_text() == (rd / "results/final" / f).read_text(), f
