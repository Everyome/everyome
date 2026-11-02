"""Structure prediction end to end on the demo cluster: proteins table, the check that refuses a huge database
download, GPU routing in the job's config, the pipeline (stand-in), the live session (predictions, a structure,
confidence, comparison of methods, export of whole and trimmed models), the record and an exact repeat."""
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from everyome.core import pipelines, runs, server
from everyome.modules.protein.structure import helpers
from everyome.modules.protein.structure import structure as st
from rerun_helpers import rerun, rerun_until_session_replayed

MID = "protein.structure"


def wait(fn, timeout=180, every=0.5):
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


def call(c, method, **kw):
    return ok(c.post(f"/api/s/call/{method}", json=kw))


def test_kabsch_and_domains():
    rng = np.random.default_rng(1)
    a = rng.normal(size=(40, 3)) * 10
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    q *= np.sign(np.linalg.det(q))
    assert st.kabsch_rmsd(a, a @ q.T + [5, -3, 2]) < 1e-6                      # a rotated, moved copy is the same structure
    n = 100
    pae = np.full((n, n), 25.0)
    pae[10:50, 10:50] = 2
    pae[60:95, 60:95] = 2
    plddt = [40] * 10 + [90] * 40 + [40] * 10 + [88] * 35 + [40] * 5
    d = st.domains(pae, plddt)
    assert [x["ranges"] for x in d] == [[[11, 50]], [[61, 95]]]
    pae[10:50, 60:95] = pae[60:95, 10:50] = 3                                  # the two now hold each other: one unit
    assert [x["ranges"] for x in st.domains(pae, plddt)] == [[[11, 50], [61, 95]]]


def test_check_refuses_a_huge_download():
    assert "about 2.6 TB" in helpers.check({"mode": "alphafold2", "db": ""})[0]
    assert helpers.check({"mode": "esmfold", "db": ""}) == []
    assert helpers.check({"mode": "colabfold", "use_msa_server": True}) == []
    assert helpers.check({"mode": "alphafold2,boltz", "db": "/shared/dbs"}) == []
    assert helpers.check({"mode": "alphafold2"}, demo=True) == []


def test_pipeline_pinned_with_its_prediction_containers():
    e = pipelines.lock()["nf-core/proteinfold@2.0.0"]
    assert "nf-core/proteinfold_alphafold2_standard:2.0.0" in e["containers"] and "nf-core/proteinfold_esmfold:2.0.0" in e["containers"]
    assert e["plugins"][0]["id"] == "nf-schema"


def test_gpu_tasks_go_to_the_gpu_partition(tmp_path):
    m = server.modules.available()[0][MID]
    vals = {f.id: f.default for f in m.fields}
    vals.update(proteins=[{"id": "p1", "fasta": "/d/p1.fa"}], gpu_partition="gpu", mode="esmfold")
    run = {"id": "r", "dir": "/x/runs/r", "values": vals, "resources": {**m.resources, "partition": "cpu"}, "user": "hh", "pipelines_dir": "/s/p"}
    files = runs.pipeline_files(run, m)
    cfg = files["nextflow.config"]
    assert "process.queue = 'cpu'" in cfg and "withLabel: 'process_gpu'" in cfg and "queue = 'gpu'" in cfg and "--gres=gpu:" in cfg
    assert json.loads(files["nf_params.json"])["use_gpu"] is True and "gpu_partition" not in json.loads(files["nf_params.json"])
    assert "-profile apptainer,gpu " in runs.nextflow_command(run, m, "python3")
    run["values"] = {**vals, "use_gpu": False}
    assert "process_gpu" not in runs.pipeline_files(run, m)["nextflow.config"] and "-profile apptainer " in runs.nextflow_command(run, m, "python3")


def test_structure_prediction_end_to_end(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "folding"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/sequences"}))["rows"]
    assert [r["id"] for r in rows] == ["disordered", "hairpin", "twodomain"]
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"fasta_dir": f"{data}/sequences", "proteins": rows, "mode": "alphafold2,esmfold"}}))
    rd = tmp_path / "demo_cluster/projects/folding/runs" / run["id"]
    assert (rd / "samplesheet.csv").read_text().splitlines()[0] == "id,fasta"
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["mode"] == "alphafold2,esmfold" and nfp["use_gpu"] is True

    ok(c.post("/api/run/submit", json={}))
    wait(lambda: ok(c.get("/api/run/status"))["done"])
    rep = ok(c.get("/api/run/report"))
    assert len(rep["structures"]) == 6 and any(p.startswith("alphafold2/split_msa_prediction/top_ranked_structures/") for p in rep["structures"])
    ok(c.post("/api/session/start"))
    wait(lambda: ok(c.get("/api/session/status"))["state"] == "READY")
    assert call(c, "load") == {"predictions": 6, "proteins": 3, "methods": ["alphafold2", "esmfold"]}
    P = {p["key"]: p for p in call(c, "predictions")}
    two, hp, dis = P["alphafold2/twodomain"], P["alphafold2/hairpin"], P["alphafold2/disordered"]
    # Two rigid domains on a floppy linker; a compact hairpin; a disordered protein with nothing confident and rigid.
    assert len(two["domains"]) == 2 and two["ranks"] == 5 and two["has_pae"] and 0.5 < two["ptm"] < 0.7
    assert hp["mean_plddt"] > 90 and len(hp["domains"]) == 1 and dis["domains"] == [] and dis["bands"]["very low"] > 70
    assert not P["esmfold/twodomain"]["has_pae"] and P["esmfold/twodomain"]["mean_plddt"] < two["mean_plddt"]

    s = call(c, "structure", key="alphafold2/twodomain")
    assert len(s["residues"]) == two["length"] and {r["domain"] for r in s["residues"]} == {"", "D1", "D2"}
    conf = call(c, "confidence", key="alphafold2/twodomain")
    assert len(conf["plddt"]) == 5 and conf["pae"]["n"] == two["length"] and len(conf["pae"]["cells"]) == two["length"]
    assert call(c, "confidence", key="esmfold/twodomain")["pae"] is None
    # ESMFold places the second domain differently: the whole differs, though each domain on its own agrees.
    cmp_ = call(c, "compare", id="twodomain")["pairs"][0]
    assert cmp_["rmsd"] > 5 and cmp_["confident_residues"] > 100 and [d["name"] for d in cmp_["domains"]] == ["D1", "D2"]
    assert all(d["rmsd"] < 1.5 for d in cmp_["domains"])
    assert call(c, "compare", id="hairpin")["pairs"][0]["rmsd"] < 1.5

    ex = call(c, "export", keys=["alphafold2/twodomain", "alphafold2/hairpin"], min_plddt=70)
    assert ex["files"] == ["twodomain_alphafold2_trimmed.pdb", "hairpin_alphafold2_trimmed.pdb", "predictions_summary.tsv"]
    pdb = c.get("/api/s/download", params={"name": "final/twodomain_alphafold2_trimmed.pdb"}).text
    atoms = [l for l in pdb.splitlines() if l.startswith("ATOM")]
    assert "REMARK 250" in pdb and 100 < len(atoms) < two["length"] and all(float(l[60:66]) >= 70 for l in atoms)
    summ = c.get("/api/s/download", params={"name": "final/predictions_summary.tsv"}).text.splitlines()
    assert summ[0].startswith("protein\tmethod") and summ[1].startswith("twodomain\talphafold2") and summ[1].split("\t")[-1] == str(len(atoms))
    bad = c.post("/api/s/call/export", json={"keys": ["alphafold2/disordered"], "domains_only": True})
    assert bad.status_code == 400 and "No residues" in bad.json()["detail"]

    rec = ok(c.post("/api/run/record"))
    for phrase in ("Structures of 3 proteins or complexes were predicted with AlphaFold2 (Jumper et al., 2021) and ESMFold (Lin et al., 2023)",
                   "nf-core/proteinfold version 2.0.0", "on GPUs", "monomer_ptm model preset", "twodomain (alphafold2): mean pLDDT",
                   "pTM 0.58", "joined where the mean PAE between them was below 5 Å", "residues with pLDDT below 70 were removed"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_folding"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("results/final/twodomain_alphafold2_trimmed.pdb", "results/final/predictions_summary.tsv"):
        assert (new / f).read_text() == (rd / f).read_text(), f


def test_run_refused_without_databases(client, tmp_path, monkeypatch):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    ok(c.post("/api/project/create", json={"name": "folding2"}))
    monkeypatch.setattr(server.S, "demo", False)          # as on a real cluster
    r = c.post("/api/run/create", json={"module": MID, "values": {"proteins": [{"id": "x", "fasta": "/d/x.fa"}]}})
    assert r.status_code == 400 and "Reference data folder" in r.json()["detail"]
