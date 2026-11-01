"""The learning layer: every module has a manual, example data, a playground and guides, and the views use them."""
import re
import shutil

import pytest
from fastapi.testclient import TestClient

from everyome.core import modules, server

FOUND, PROBLEMS = modules.discover()


@pytest.mark.parametrize("mid", sorted(FOUND))
def test_every_module_is_complete(mid):
    m = FOUND[mid]
    assert m.learn.get("manual") and (m.demo.get("data") or m.demo.get("build"))
    assert m.learn.get("playground"), f"{mid} has no playground"
    assert m.learn.get("guides"), f"{mid} has no guides"


@pytest.mark.parametrize("mid", sorted(FOUND))
def test_views_and_guides_match(mid):
    m = FOUND[mid]
    used = set(re.findall(r'guide\("([a-z0-9_]+)"', "".join((m.dir / f).read_text() for f in m.ui)))
    have = set(m.learn["guides"])
    assert used - have == set(), f"{mid}: views ask for guides that do not exist: {used - have}"
    assert have - used == set(), f"{mid}: guides never shown in the views: {have - used}"


def test_guides_are_served():
    c = TestClient(server.app)
    g = c.get("/api/modules/rna.bulk_de/guides").json()
    assert "volcano" in g and "adjusted" in g["volcano"].lower()
    assert c.get("/api/modules/molbio.primers").json()["guides"] == ["check", "map", "order", "pairs"]


def test_module_without_a_manual_is_not_listed(tmp_path):
    src = FOUND["tutorial.sequence_summary"].dir
    dst = tmp_path / "tutorial" / "copy"
    shutil.copytree(src, dst)
    y = (dst / "module.yaml").read_text().replace("id: tutorial.sequence_summary", "id: tutorial.copy")
    y = re.sub(r"\nlearn:\n(  .*\n)+", "\n", y)
    (dst / "module.yaml").write_text(y)
    found, problems = modules.discover(tmp_path)
    assert "tutorial.copy" not in found and any("not listed until it has a manual" in p for p in problems)
