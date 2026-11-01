"""The module manifest: valid modules load, broken ones explain what to fix, values are checked."""
import pytest

from everyome.core import manifest, modules
from everyome.core.manifest import ManifestError

GOOD = """
spec: 1
id: test.example
name: Example
suite: Test
version: 0.1.0
summary: An example.
kind: [batch]
params:
  - {id: n, label: Number, type: int, default: 5, min: 1, max: 10}
  - {id: mode, label: Mode, type: choice, choices: [a, b], default: a}
  - {id: flag, label: Flag, type: bool, default: false}
inputs:
  - {id: reads, label: Reads, type: file, required: true}
batch:
  stages:
    - {id: "01", name: one, title: Step one, run: "{python} -c 'print(1)'"}
"""


def write(tmp_path, text):
    p = tmp_path / "module.yaml"
    p.write_text(text)
    return p


def test_first_party_modules_load():
    found, problems = modules.discover()
    assert problems == []
    assert "tutorial.sequence_summary" in found


def test_good_manifest(tmp_path):
    m = manifest.load(write(tmp_path, GOOD))
    assert [f.id for f in m.fields] == ["reads", "n", "mode", "flag"]
    assert m.stages[0].id == "01"


@pytest.mark.parametrize("change, message", [
    (("spec: 1", "spec: 2"), "spec must be 1"),
    (("id: test.example", "id: Test Example"), "should look like suite.name"),
    (("type: int, default: 5", "type: integer, default: 5"), "type must be one of"),
    (("choices: [a, b], ", ""), "needs a list of choices"),
    (("default: 5, min: 1", "default: 50, min: 1"), "is not valid"),
    (("kind: [batch]", "kind: [server]"), "kind must be from"),
])
def test_broken_manifests_explain_themselves(tmp_path, change, message):
    with pytest.raises(ManifestError, match=message):
        manifest.load(write(tmp_path, GOOD.replace(*change)))


def test_check_values(tmp_path):
    m = manifest.load(write(tmp_path, GOOD))
    vals, errors = manifest.check_values(m, {"reads": "/x.fq", "n": "7", "flag": "true"})
    assert errors == {} and vals == {"reads": "/x.fq", "n": 7, "mode": "a", "flag": True}
    _, errors = manifest.check_values(m, {"n": "11", "mode": "c"})
    assert set(errors) == {"reads", "n", "mode"}
    assert "at most 10" in errors["n"]


def test_community_modules_are_off():
    from everyome.core import community
    assert community.BUILD_ENABLED is False and community.enabled() is False
    for fn in (community.index, lambda: community.install("community.anything")):
        with pytest.raises(PermissionError):
            fn()
    assert community.installed() == ({}, [])
