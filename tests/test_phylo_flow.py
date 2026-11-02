"""Alignment and tree building end to end on the demo cluster: pinned containers in the job scripts, the three stages
(stand-ins), the Run-page report, the live session (alignment, model, rooting, collapsing, groups, export), the record
and an exact repeat. Also the Newick handling the viewer relies on, and the real-tool commands (without running them)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from everyome.core import containers, server
from everyome.core.manifest import ManifestError, load
from everyome.modules.phylo.tree import engine as eng_mod
from everyome.modules.phylo.tree import newick as nw
from rerun_helpers import rerun, rerun_until_session_replayed

MID = "phylo.tree"
OUT = ["Homo_sapiens", "Drosophila_melanogaster"]
SCYPHO = {"Aurelia_aurita", "Cassiopea_xamachana", "Rhopilema_esculentum", "Chrysaora_fuscescens"}


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


def node_of(tree, tips):
    """The index of the drawn node whose tips are exactly these (via its tip descendants)."""
    nodes = {n["i"]: n for n in tree["nodes"]}
    below = {}
    for n in reversed(tree["nodes"]):
        below[n["i"]] = {n["tip"]} if "tip" in n else set().union(*(below[k] for k in n.get("kids", [])))
    return next(i for i, s in below.items() if s == set(tips) and "tip" not in nodes[i])


def test_newick_rooting_keeps_support_on_its_branch():
    t = nw.parse("((A:1,B:2)90/99:0.5,(C:1,'D x':3)70/80:0.2,E:4);")
    assert t.tips() == ["A", "B", "C", "D x", "E"]
    r = nw.root_outgroup(t, ["C", "D x"])
    assert nw.write(r) == "((C:1,'D x':3)70/80:0.1,((A:1,B:2)90/99:0.5,E:4)70/80:0.1);"
    m = nw.root_midpoint(t)
    assert nw.write(m).startswith("(E:3.6,")
    length = lambda x: round(sum(n.length or 0 for n in x.walk() if n is not x), 6)
    assert length(t) == length(r) == length(m)
    with pytest.raises(ValueError, match="not monophyletic"):
        nw.root_outgroup(t, ["A", "C"])
    assert nw.support("90/99") == {"alrt": 90, "ufboot": 99} and nw.strong({"alrt": 79, "ufboot": 99}) is False


def test_manifest_pins_containers_by_digest(tmp_path):
    m = load(server.modules.FIRST_PARTY / "phylo" / "tree" / "module.yaml")
    assert set(m.containers) == {"mafft", "trimal", "iqtree"}
    assert containers.image_file(m.containers["iqtree"]).startswith("quay.io-biocontainers-iqtree-3.1.4--h8471819_0-6e5792be5219")
    assert containers.pull_url(m.containers["mafft"]).startswith("docker://quay.io/biocontainers/mafft@sha256:b8ccc402")
    y = (server.modules.FIRST_PARTY / "phylo" / "tree" / "module.yaml").read_text()
    bad = tmp_path / "module.yaml"
    bad.write_text(y.replace("@sha256:b8ccc402a9156868fefda5caa8693f847b47dcc69aae848557f7115850e60790", ""))
    (tmp_path / "docs").symlink_to(server.modules.FIRST_PARTY / "phylo" / "tree" / "docs")
    (tmp_path / "ui.js").write_text("")
    with pytest.raises(ManifestError, match="sha256"):
        load(bad)


def test_real_tool_commands(tmp_path, monkeypatch):
    """Without the demo, each stage runs its tool in the pinned image, with the run's settings."""
    from everyome.modules.phylo.tree import stage
    seen = []
    monkeypatch.setattr(stage, "tool", lambda name, args, params, run_dir, **kw: seen.append((name, args)))
    monkeypatch.delenv("EVERYOME_DEMO", raising=False)
    fa = tmp_path / "in.fa"
    fa.write_text(">a one\nACGTACGT\n>b\nACGTACGA\n>c\nACGAACGT\n>d x|y\nTCGTACGT\n")
    p = {"sequences": str(fa), "seq_type": "auto", "already_aligned": False, "mafft_strategy": "linsi", "mafft_extra": "--adjustdirection",
         "trim_method": "gap_threshold", "min_present": 0.8, "trimal_extra": "", "model": "MFP", "bootstrap": 1000, "alrt": 0,
         "outgroup": "d x|y", "seed": 7, "iqtree_extra": "--bnni"}
    res = tmp_path / "results"
    res.mkdir()
    stage.align(p, str(tmp_path), res, 4)
    assert (res / "names.tsv").read_text().splitlines()[1:] == ["a\ta one", "b\tb", "c\tc", "d\td x|y"]
    (res / "trimmed.fasta").write_text((res / "sequences.fasta").read_text())
    stage.trim(p, str(tmp_path), res, 4)
    stage.tree(p, str(tmp_path), res, 4)
    (_, mafft), (_, trimal), (_, iq) = seen
    assert mafft[:6] == ["mafft", "--localpair", "--maxiterate", "1000", "--thread", "4"] and "--nuc" in mafft and "--adjustdirection" in mafft
    assert trimal[trimal.index("-gt") + 1] == "0.8" and "-colnumbering" in trimal
    assert iq[:2] == ["iqtree3", "-s"] and iq[iq.index("-m") + 1] == "MFP" and iq[iq.index("-B") + 1] == "1000" and "--alrt" not in iq
    assert iq[iq.index("-o") + 1] == "d" and iq[-1] == "--bnni" and iq[iq.index("--seed") + 1] == "7"
    with pytest.raises(ValueError, match="different first word"):
        stage.clean_names([("x 1", "A"), ("x 2", "A")])


def test_iqtree_report_parsing():
    text = ("Input data: 12 sequences with 900 amino-acid sites\nNumber of constant sites: 300 (= 33% of all sites)\n"
            "Number of parsimony informative sites: 410\n\nBest-fit model according to BIC: LG+I+G4\n\nList of models sorted by BIC scores: \n\n"
            "Model                  LogL         AIC      w-AIC        AICc     w-AICc         BIC      w-BIC\n"
            "LG+I+G4          -9000.123   18050.246 +    0.700   18052.000 +    0.690   18200.500 +    0.950\n"
            "LG+G4            -9010.000   18068.000 -    0.300   18069.000 -    0.310   18206.000 -    0.050\n\n"
            "Model of substitution: LG+I+G4\nGamma shape alpha: 0.812\nLog-likelihood of the tree: -9000.1230 (s.e. 300.1)\n")
    r = eng_mod.parse_iqtree(text)
    assert r["best_model"] == "LG+I+G4" and r["criterion"] == "BIC" and r["sequences"] == 12 and r["sites"] == 900 and r["informative"] == 410
    assert [m["model"] for m in r["models"]] == ["LG+I+G4", "LG+G4"] and r["models"][1]["w_bic"] == 0.05 and r["gamma_alpha"] == 0.812


def test_tree_building_end_to_end(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "cnidaria"}))
    bad = c.post("/api/run/create", json={"module": MID, "values": {"sequences": f"{data}/sequences.fasta", "bootstrap": -1}})
    assert bad.status_code == 400 and "at least 0" in bad.json()["detail"]
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"sequences": f"{data}/sequences.fasta", "metadata": f"{data}/species.csv",
                                                                        "outgroup": ", ".join(OUT), "mafft_strategy": "linsi"}}))
    rd = tmp_path / "demo_cluster/projects/cnidaria/runs" / run["id"]
    scripts = ok(c.post("/api/run/preview", json={}))["scripts"]
    assert [s["stage"] for s in scripts] == ["01", "02", "03"]
    assert "EVERYOME_CONTAINERS" not in scripts[0]["script"]          # the demo cluster runs stand-ins, not containers

    ok(c.post("/api/run/submit", json={}))
    wait(lambda: ok(c.get("/api/run/status"))["done"])
    rep = ok(c.get("/api/run/report"))
    assert rep["sequences"] == 24 and rep["kept"] < rep["columns"] and rep["model"] == "K2P+G4" and rep["tree"]

    ok(c.post("/api/session/start"))
    wait(lambda: ok(c.get("/api/session/status"))["state"] == "READY")
    info = call(c, "load")
    assert info["sequences"] == 24 and info["type"] == "dna" and info["model"] == "K2P+G4" and info["selected_by"] == "BIC"
    s = call(c, "summary")
    flags = {r["name"]: r["flag"] for r in s["rows"] if r["flag"]}
    assert list(flags) == ["Morbakka_virulenta"] and "partial" in flags["Morbakka_virulenta"]
    assert next(r for r in s["rows"] if r["name"] == "Hydra_vulgaris")["original"] == "Hydra_vulgaris simulated gene"
    a = call(c, "alignment", start=0, width=100)
    assert a["total"] == s["columns"] and len(a["rows"]) == 24 and a["kept_all"].count("1") == s["kept"]
    mo = call(c, "models")
    assert mo["models"][0]["model"] == "K2P+G4" and len(mo["support"]) == 21 and all("ufboot" in x for x in mo["support"])

    # Rooted on the outgroup from the settings; every class forms one group, the medusa trait does not.
    t = call(c, "tree")
    assert t["view"]["root"] == {"how": "outgroup", "tips": OUT} and t["colour_by"] == "class" and t["tips"] == 24
    groups = {g["value"]: g for g in t["groups"]}
    assert all(groups[k]["clade"] for k in ("Anthozoa", "Hydrozoa", "Scyphozoa", "Cubozoa", "Staurozoa", "Bilateria"))
    assert groups["Scyphozoa"]["support"]["ufboot"] >= 95
    t = call(c, "view", colour_by="free_swimming_medusa")
    g = {x["value"]: x for x in t["groups"]}
    assert not g["yes"]["clade"] and not g["no"]["clade"] and g["not a cnidarian"]["clade"]

    # Midpoint rooting, then back to the outgroup; a group that is not monophyletic cannot root the tree.
    t = call(c, "reroot", how="midpoint")
    assert t["view"]["root"]["how"] == "midpoint"
    r = c.post("/api/s/call/reroot", json={"how": "outgroup", "tips": ["Homo_sapiens", "Hydra_vulgaris"]})
    assert r.status_code == 400 and "not monophyletic" in r.json()["detail"]
    t = call(c, "reroot", how="outgroup", tips=OUT)
    t = call(c, "view", colour_by="class")
    # Collapse the jellyfish (Scyphozoa) into one triangle, labelled with their class.
    n = node_of(t, SCYPHO)
    t = call(c, "collapse", node=n)
    tri = [x for x in t["nodes"] if x.get("collapsed")]
    assert len(tri) == 1 and tri[0]["collapsed"] == 4 and tri[0]["label"] == "Scyphozoa: 4 sequences" and t["rows"] == 24 - 4 + 2
    # A yes/no value does not name a group; the triangle is then named by its first and last sequence.
    tri2 = [x for x in call(c, "view", colour_by="free_swimming_medusa")["nodes"] if x.get("collapsed")][0]
    assert tri2["label"].startswith("4 sequences: ") and " … " in tri2["label"]
    call(c, "view", colour_by="class")
    ex = call(c, "export")
    assert ex["files"] == ["tree_rooted.nwk", "tree_figure.svg", "tips.tsv", "groups.tsv"]
    rooted = nw.parse(c.get("/api/s/download", params={"name": "final/tree_rooted.nwk"}).text)
    assert set(rooted.children[0].tips()) == set(OUT) and len(rooted.tips()) == 24          # collapsing only changes the figure
    svg = c.get("/api/s/download", params={"name": "final/tree_figure.svg"}).text
    assert svg.startswith("<svg") and "Scyphozoa: 4 sequences" in svg and "substitutions per site" in svg
    assert 'font-weight="bold">class</text>' in svg and ">Staurozoa</text>" in svg                  # the legend
    assert "Hydra_vulgaris\tHydra_vulgaris simulated gene\tHydrozoa\tno" in c.get("/api/s/download", params={"name": "final/tips.tsv"}).text

    rec = ok(c.post("/api/run/record"))
    for phrase in ("24 DNA sequences were aligned with MAFFT 7.525 (Katoh and Standley, 2013) using the L-INS-i strategy",
                   "trimAl 1.5.1 (Capella-Gutiérrez et al., 2009) using the automated1 method", "IQ-TREE 3.1.4 (Wong et al., 2025) under the K2P+G4 model, selected by ModelFinder",
                   "1,000 ultrafast bootstrap replicates (UFBoot2; Hoang et al., 2018)", "SH-aLRT; Guindon et al., 2010", "(random seed 12345)",
                   "rooted on Homo sapiens, Drosophila melanogaster as the outgroup", "grouped by class; each group formed a single clade"):
        assert phrase in rec["methods"], phrase
    protocol = (rd / "record/protocol.md").read_text()
    assert "Rooted the tree" in protocol and "Collapsed a group" in protocol

    new = tmp_path / "repeat_tree"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("results/final/tree_rooted.nwk", "results/final/tree_figure.svg", "results/final/groups.tsv"):
        assert (new / f).read_text() == (rd / f).read_text(), f


def test_real_runs_get_the_shared_container_folder(client, tmp_path):
    from everyome.core import runs
    m = server.modules.available()[0][MID]
    run = {"id": "r", "dir": "/x/runs/r", "resources": m.resources, "user": "hh", "values": {}, "demo": False, "pipelines_dir": "/shared/everyome/pipelines"}
    script = runs.stage_script(run, m, m.stages[2], "/usr/bin/python3")
    assert "export EVERYOME_CONTAINERS=/shared/everyome/pipelines/containers" in script
    assert "#SBATCH --job-name=Claude_hh_everyome_phylo_tree_03_tree" in script
