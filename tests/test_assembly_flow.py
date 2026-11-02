"""Genome assembly and bacterial assembly end to end on the demo cluster: reads table, pipeline (stand-in), report,
the shared assembly explorer (compare, contigs, genes, choose, export), record and rerun."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from everyome.core import server
from rerun_helpers import rerun, rerun_until_session_replayed


def wait(fn, timeout=600, every=0.5):  # generous: CI runners can be several times slower than a laptop
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


def run_pipeline_and_session(c):
    ok(c.post("/api/run/submit", json={}))
    wait(lambda: ok(c.get("/api/run/status"))["done"])
    assert ok(c.get("/api/run/progress"))["failed"] == 0
    ok(c.post("/api/session/start"))
    wait(lambda: ok(c.get("/api/session/status"))["state"] == "READY")


def by_label(c):
    return {a["label"]: a for a in call(c, "assemblies")}


def test_genome_assembly_end_to_end(client, tmp_path):
    c, mid = client, "dna.assembly"
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{mid}"
    ok(c.post("/api/project/create", json={"name": "plant"}))
    scan = ok(c.post(f"/api/modules/{mid}/helpers/scan", json={"path": f"{data}/reads"}))
    rows = scan["rows"]
    assert [(r["sample"], r["strategy"], r["assembler"], r["polish"]) for r in rows] == [
        ("plant_ont", "single", "flye", "medaka+pilon"), ("plant_hifi", "single", "hifiasm", "pilon"),
        ("plant_hybrid", "hybrid", "hifiasm", "pilon"), ("plant_scaffold", "scaffold", "flye_hifiasm", "pilon")]
    assert all(r["short_1"].endswith("plant_R1.fastq.gz") for r in rows)

    # Every row needs long reads.
    bad = c.post("/api/run/create", json={"module": mid, "values": {"assemblies": [{**rows[0], "ontreads": "", "hifireads": ""}]}})
    assert bad.status_code == 400 and "at least one of: Nanopore reads, PacBio HiFi reads" in bad.json()["detail"]

    run = ok(c.post("/api/run/create", json={"module": mid, "values": {"reads_dir": f"{data}/reads", "assemblies": rows, "lift_annotations": True,
                                                                        "ref_fasta": f"{data}/reference/related.fa", "ref_gff": f"{data}/reference/related.gff3",
                                                                        "genome_size": "750k"}}))
    rd = tmp_path / "demo_cluster/projects/plant/runs" / run["id"]
    sheet = (rd / "samplesheet.csv").read_text().splitlines()
    assert sheet[0] == "sample,ontreads,hifireads,shortread_F,shortread_R,use_short_reads,paired,strategy,assembler,polish"
    assert sheet[1].endswith(",true,true,single,flye,medaka+pilon")
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["busco"] is True and nfp["quast"] is True and nfp["lift_annotations"] is True and "assembler" not in nfp

    run_pipeline_and_session(c)
    rep = ok(c.get("/api/run/report"))
    assert any(p.endswith("plant_scaffold_assembly_scaffold.fasta") for p in rep["assemblies"]) and rep["report"]
    a = by_label(c)
    scaffold, ont = a["plant_scaffold · polished (pilon)"], a["plant_ont · assembly (flye)"]
    # Intent: the demo genome has three chromosomes; scaffolding Nanopore onto HiFi recovers them, HiFi alone breaks at long repeats.
    assert scaffold["n"] == 3 and scaffold["total"] == 750_000 and a["plant_hifi · assembly (hifiasm)"]["n"] > scaffold["n"]
    assert ont["busco"]["complete"] < a["plant_ont · polished (medaka)"]["busco"]["complete"] < a["plant_ont · polished (pilon)"]["busco"]["complete"]
    assert scaffold["annotation"] and len(call(c, "nx_curves")) == len(a)
    g = call(c, "genes", id=scaffold["id"], q="kinase")
    assert g["genes"] > 150 and g["unmapped"] is not None and g["matches"] == len(g["rows"]) > 0
    assert all("kinase" in (x["product"] + x["name"]).lower() for x in g["rows"])
    ct = call(c, "contigs", id=scaffold["id"])
    assert ct["count"] == 3 and ct["contigs"][0]["length"] == 300_000

    with pytest.raises(AssertionError):
        call(c, "export")                                               # choose first
    call(c, "choose", id=scaffold["id"], reason="three chromosomes, complete BUSCO")
    ex = call(c, "export")
    assert ex["files"] == ["plant_scaffold_final_assembly.fa", "plant_scaffold_final_annotation.gff3", "assembly_comparison.tsv"]
    assert c.get("/api/s/download", params={"name": "final/plant_scaffold_final_assembly.fa"}).text.startswith(">")

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/genomeassembler version 2.0.1", "4 assemblies were made", "plant_scaffold from Oxford Nanopore and PacBio HiFi and Illumina reads",
                   "scaffolded onto the other with RagTag", "polished with Medaka followed by Pilon", "BUSCO (Manni et al., 2021)",
                   "Liftoff (Shumate and Salzberg, 2021)", "plant_scaffold · polished (pilon) was chosen", "Reason recorded: three chromosomes"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_assembly"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    f = "results/final/assembly_comparison.tsv"
    assert (new / f).read_text() == (rd / f).read_text()


def test_bacterial_assembly_end_to_end(client, tmp_path):
    c, mid = client, "dna.bacterial"
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{mid}"
    ok(c.post("/api/project/create", json={"name": "bugs"}))
    scan = ok(c.post(f"/api/modules/{mid}/helpers/scan", json={"path": f"{data}/reads"}))
    assert [r["sample"] for r in scan["rows"]] == ["isolate1", "isolate2"] and "Set Assembly type to hybrid" in scan["message"]
    run = ok(c.post("/api/run/create", json={"module": mid, "values": {"reads_dir": f"{data}/reads", "isolates": scan["rows"][:1],
                                                                        "assembler": "unicycler,dragonflye"}}))
    rd = tmp_path / "demo_cluster/projects/bugs/runs" / run["id"]
    sheet = (rd / "samplesheet.tsv").read_text().splitlines()
    assert sheet[0] == "ID\tR1\tR2\tLongFastQ\tFast5\tGenomeSize" and sheet[1].endswith("\tNA\tNA")
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["input"].endswith("samplesheet.tsv") and nfp["assembly_type"] == "hybrid" and nfp["skip_kraken2"] is True

    run_pipeline_and_session(c)
    rep = ok(c.get("/api/run/report"))
    assert len(rep["assemblies"]) == 2 and len(rep["annotations"]) == 2 and rep["multiqc"]
    a = by_label(c)
    uni, dfl = a["isolate1 · assembly (unicycler)"], a["isolate1 · assembly (dragonflye)"]
    # Intent: the hybrid Unicycler assembly recovers the chromosome and both plasmids; Dragonflye misses the small plasmid.
    assert uni["n"] == 3 and dfl["n"] == 2 and uni["total"] - dfl["total"] == 6_000
    assert uni["busco"]["lineage"] == "bacteria_odb10" and uni["annotation"].startswith("Prokka/isolate1-unicycler/")
    g = call(c, "genes", id=uni["id"])
    assert g["genes"] > 400 and g["counts"]["CDS"] == g["genes"]
    call(c, "choose", id=uni["id"])
    assert "isolate1_final_annotation.gff3" in call(c, "export")["files"]
    rec = ok(c.post("/api/run/record"))
    for phrase in ("Genomes of 1 isolate (isolate1) were assembled from Illumina and long reads together (hybrid assembly)",
                   "nf-core/bacass version 2.6.1", "Unicycler (Wick et al., 2017) and Dragonflye", "Prokka (Seemann, 2014)",
                   "isolate1 · assembly (unicycler) was chosen"):
        assert phrase in rec["methods"], phrase
    assert "contamination" not in rec["methods"]                     # screening was off
