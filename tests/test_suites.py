"""The suite catalogue lines up with the installed modules, and suggestions make sense."""
from fastapi.testclient import TestClient

from everyome.core import modules, server, suites

CAT = suites.load()
MODS, _ = modules.discover()


def test_catalogue_matches_modules():
    assert suites.check(CAT, MODS) == []


def test_every_planned_suite_is_listed():
    ids = [s["id"] for s in suites.public(CAT, MODS)["suites"]]
    assert ids == ["tutorial", "dna", "rna", "singlecell", "spatial", "protein", "molbio", "phylo"]


def test_ready_and_planned_tools():
    pub = {s["id"]: s for s in suites.public(CAT, MODS)["suites"]}
    assert pub["tutorial"]["ready"] and not pub["dna"]["ready"]
    assert pub["tutorial"]["tools"][0]["ready"] is True


def test_single_cell_data_and_cell_type_aim():
    top = suites.suggest(CAT, MODS, ["sc_rna"], ["cell_types"])
    assert {t["id"] for t in top[:2]} == {"singlecell.splitseq", "singlecell.scrna"}
    assert top[0]["both"] and "Fits your data" in top[0]["reason"] and "Fits your aim" in top[0]["reason"]


def test_fit_to_both_ranks_above_fit_to_one():
    top = suites.suggest(CAT, MODS, ["bulk_rna"], ["compare"])
    assert top[0]["id"] == "rna.bulk_de"


def test_tools_must_fit_named_data():
    ids = {t["id"] for t in suites.suggest(CAT, MODS, ["sc_rna"], ["compare"])}
    assert "rna.bulk_de" not in ids and "singlecell.scrna" in ids


def test_aim_alone_still_suggests():
    assert suites.suggest(CAT, MODS, ["not_sure"], ["evolution"])[0]["id"] == "phylo.tree"


def test_nothing_chosen_gives_nothing():
    assert suites.suggest(CAT, MODS, [], []) == []


def test_unknown_suite_is_reported():
    m = next(iter(MODS.values()))
    broken = {m.id: type(m)(**{**m.__dict__, "suite": "Tutorial"})}
    assert any("is not one of" in p for p in suites.check(CAT, broken))


def test_api_needs_no_connection():
    c = TestClient(server.app)
    assert len(c.get("/api/suites").json()["suites"]) == 8
    r = c.post("/api/suggest", json={"data": ["constructs"], "aims": ["design"]}).json()["suggestions"]
    assert r[0]["id"] == "molbio.primers" and r[0]["ready"] is True          # ready tools come first among equals
    r = c.post("/api/suggest", json={"data": ["sequences"], "aims": ["evolution"]}).json()["suggestions"]
    assert r[0]["suite"] == "phylo" and r[0]["ready"] is False


def test_not_sure_alone_points_to_the_worked_example():
    assert suites.suggest(CAT, MODS, ["not_sure"], [])[0]["id"] == "tutorial.sequence_summary"
