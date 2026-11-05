"""Protein function annotation end to end on the demo cluster: the InterProScan stand-in, the overview, one protein's
domains and GO terms, search, GO terms overall, export, record and an exact repeat. Also the real InterProScan
command line (no EBI lookup by default; the data folder bound where the image expects it) and FASTA cleaning."""
import csv
import json

from everyome.modules.protein.function import stage
from flow_helpers import call, demo_client, ok  # noqa: F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session

MID = "protein.function"


def test_interproscan_command_and_cleaning(tmp_path, monkeypatch):
    src = tmp_path / "in.faa"
    src.write_text(">p1 some protein\nMKV LL*\n>p2\nMAA\n")
    assert stage.clean(src, tmp_path / "out.fa") == 2
    assert (tmp_path / "out.fa").read_text() == ">p1\nMKVLL\n>p2\nMAA\n"
    args = stage.interproscan_args({"goterms": True, "pathways": False, "applications": "Pfam, PANTHER"}, tmp_path / "p.fa", tmp_path, 8)
    assert args[0] == "/opt/interproscan/interproscan.sh" and "-dp" in args and "-goterms" in args and "-pa" not in args
    assert args[args.index("-appl") + 1] == "Pfam,PANTHER" and args[args.index("-cpu") + 1] == "8"
    assert "-dp" not in stage.interproscan_args({"lookup": True}, tmp_path / "p.fa", tmp_path, 1)
    # The data folder is bound at the image's own path.
    seen = {}
    monkeypatch.setenv("EVERYOME_CONTAINERS", str(tmp_path / "c"))
    monkeypatch.delenv("EVERYOME_DEMO", raising=False)
    monkeypatch.setattr(stage.containers, "ensure", lambda ref, cache: tmp_path / "x.sif")
    monkeypatch.setattr(stage.containers, "runner", lambda: "apptainer")
    monkeypatch.setattr(stage.subprocess, "run", lambda cmd, check: seen.setdefault("cmd", cmd))
    data = tmp_path / "ipr_data"
    data.mkdir()
    stage.annotate({"proteins": str(src), "data_dir": str(data)}, str(tmp_path), tmp_path, 4)
    cmd = seen["cmd"]
    assert f"{data.resolve()}:/opt/interproscan/data" in cmd and cmd[:2] == ["apptainer", "exec"]


def test_function_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "ipr"}))
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"proteins": f"{data}/proteins.faa"}}))
    rd = tmp_path / "demo_cluster/projects/ipr/runs" / run["id"]
    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    assert ok(c.get("/api/run/report"))["proteins"] == 10
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    o = call(c, "overview")
    assert o["proteins"] == 10 and o["with_match"] == 8 and o["databases"] == {"Pfam": 17}
    assert o["top_entries"][0]["proteins"] == 2 and o["top_entries"][0]["entry"] == "IPR000719"       # two kinases
    p = call(c, "protein", id="nvKinSH3")
    assert [m["accession"] for m in p["matches"]] == ["PF00018", "PF00069"]
    assert {g["name"] for g in p["go"]} == {"protein kinase activity", "ATP binding", "protein phosphorylation"}
    assert call(c, "protein", id="nvUnk1")["matches"] == []
    assert set(call(c, "search", q="kinase")) == {"nvKin1", "nvKinSH3"}
    assert call(c, "search", q="GO:0003677") == ["nvHox1"]
    go = {t["id"]: t for t in call(c, "go_terms")}
    assert go["GO:0004672"]["proteins"] == ["nvKin1", "nvKinSH3"] and go["GO:0016020"]["aspect"] == "cellular component"
    call(c, "export")
    rows = list(csv.DictReader(open(rd / "results/tables/protein_annotations.csv")))
    assert len(rows) == 10 and next(r for r in rows if r["protein"] == "nvZnf1")["interpro_entries"] == "IPR013087"

    rec = ok(c.post("/api/run/record"))
    for phrase in ("InterProScan", "lookup service for precalculated matches was disabled", "Of 10 proteins, 8 (80%)"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_ipr"
    p1 = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p1.returncode == 0, p1.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("results/tables/protein_annotations.csv", "results/tables/go_terms.csv"):
        assert (new / f).read_text() == (rd / f).read_text(), f
