"""Genome annotation end to end on the demo cluster: three stages (Helixer, gffread, BUSCO stand-ins), the gene models,
one gene, export, record and an exact repeat. Also the real Helixer command line, the model folder bound where Helixer
looks, and the GPU stage's job header."""
from pathlib import Path

from everyome.core import runs
from everyome.core.manifest import load
from everyome.modules.dna.annotation import stage
from flow_helpers import call, demo_client, ok  # noqa: F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session

MID = "dna.annotation"
HERE = Path(stage.__file__).parent


def test_helixer_command_and_gpu_job(tmp_path, monkeypatch):
    args = stage.helixer_args({"genome": "/g/genome.fa", "lineage": "invertebrate", "species": "Nematostella"}, tmp_path)
    assert args[:3] == ["Helixer.py", "--fasta-path", "/g/genome.fa"] and args[args.index("--lineage") + 1] == "invertebrate"
    seen = {}
    monkeypatch.setenv("EVERYOME_CONTAINERS", str(tmp_path / "c"))
    monkeypatch.delenv("EVERYOME_DEMO", raising=False)
    monkeypatch.setattr(stage.containers, "ensure", lambda ref, cache: tmp_path / "x.sif")
    monkeypatch.setattr(stage.containers, "runner", lambda: "apptainer")
    monkeypatch.setattr(stage.subprocess, "run", lambda cmd, check: seen.setdefault("cmd", cmd))
    models = tmp_path / "helixer_models"
    models.mkdir()
    stage.predict({"genome": str(tmp_path / "genome.fa"), "models_dir": str(models)}, str(tmp_path), tmp_path, 4)
    assert f"{models.resolve()}:{Path.home()}/.local/share/Helixer/models" in seen["cmd"]
    # The prediction stage asks Slurm for a GPU, on the GPU partition when one is set.
    m = load(HERE / "module.yaml")
    run = {"dir": "/r", "user": "u", "resources": {"cpus": 4, "mem": "16G", "time": "12:00:00", "partition": "normal"},
           "values": {"gpu_partition": "gpu"}, "pipelines_dir": "/p"}
    s1 = runs.stage_script(run, m, m.stages[0], "python")
    assert "#SBATCH --gres=gpu:1" in s1 and "#SBATCH --partition=gpu" in s1 and "#SBATCH --mem=64G" in s1
    s2 = runs.stage_script(run, m, m.stages[1], "python")
    assert "--gres" not in s2 and "#SBATCH --partition=normal" in s2


def test_annotation_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "anno"}))
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"genome": f"{data}/genome.fa"}}))
    rd = tmp_path / "demo_cluster/projects/anno/runs" / run["id"]
    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    from everyome.modules.dna.annotation.demo_data import truth
    n = len(truth())
    rep = ok(c.get("/api/run/report"))
    assert rep["genes"] == n and rep["proteins"] == n and rep["busco"].startswith("C:86.4%")
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    o = call(c, "overview")
    assert o["genes"] == n and o["transcripts"] == n and o["busco"]["complete"] == 86.4
    assert sum(o["exon_hist"]["counts"]) == n and set(o["per_seq"]) == {"chr1", "chr2"}
    g0 = truth()[0]
    g = call(c, "gene", id=g0["id"])
    assert [tuple(e) for e in g["exons"]] == [tuple(e) for e in g0["exons"]] and g["protein"] == g0["protein"]
    assert len(call(c, "genes", q="chr2")) == sum(1 for t in truth() if t["chrom"] == "chr2")
    call(c, "export")
    assert {"final/annotation.gff3", "final/proteins.faa", "final/genes.csv"} <= {f["name"] for f in call(c, "files")}

    rec = ok(c.post("/api/run/record"))
    for phrase in ("Helixer", "invertebrate lineage model", "gffread", "metazoa_odb12", f"{n:,} genes"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_anno"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p1.returncode == 0, p1.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    assert (new / "results/final/genes.csv").read_text() == (rd / "results/final/genes.csv").read_text()
