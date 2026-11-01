"""The community registry, dry run: a test module is checked, approved, signed, indexed, installed and used,
and tampered or withdrawn modules are refused. The registry stays switched off in the shipped app.

Needs OpenSSH's ssh-keygen (for signing); skipped without it.
"""
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from everyome.core import community, modules, server
from everyome.registry import bundle, checks
from everyome.registry.__main__ import main as registry_cli

FIXTURE = Path(__file__).parent / "fixtures" / "community_kmer"
MID = "community.kmer_spectrum"
pytestmark = pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="needs ssh-keygen")


def keypair(folder: Path, name: str) -> tuple[Path, str]:
    key = folder / name
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(key)], check=True)
    return key, (folder / f"{name}.pub").read_text().strip()


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A registry folder with the test module approved and signed, and a site that trusts the maintainer."""
    keys = tmp_path / "keys"
    keys.mkdir()
    key, pub = keypair(keys, "maintainer")
    signers = tmp_path / "allowed_signers"
    signers.write_text(f'maintainer@everyome namespaces="{bundle.NAMESPACE}" {pub}\n')
    reg = tmp_path / "registry"
    assert registry_cli(["approve", str(reg), str(FIXTURE), "--reviewer", "Test Reviewer", "--key", str(key)]) == 0
    assert registry_cli(["index", str(reg), "--key", str(key)]) == 0
    # Intent: this computer's Everyome settings live in the test folder, never in the real ~/.everyome.
    monkeypatch.setattr(community, "HOME", tmp_path / "home")
    monkeypatch.setattr(community, "CONFIG", tmp_path / "home/community.json")
    monkeypatch.setattr(community, "STORE", tmp_path / "home/community")
    community.HOME.mkdir()
    community.CONFIG.write_text(json.dumps({"enabled": True, "registry": str(reg), "allowed_signers": str(signers),
                                            "signers": ["maintainer@everyome"]}))
    return {"reg": reg, "key": key, "keys": keys, "signers": signers}


def copy_fixture(tmp_path) -> Path:
    dst = tmp_path / "submission"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


# ------------------------------------------------------------------ automated checks
def test_fixture_passes_the_checks():
    rep = checks.check(FIXTURE)
    assert rep["ok"], rep["failures"]
    assert rep["warnings"] == [] and rep["info"]["package"] == "everyome_c_community_kmer_spectrum"


def test_checks_catch_problems(tmp_path):
    sub = copy_fixture(tmp_path)
    eng = sub / "everyome_c_community_kmer_spectrum" / "engine.py"
    eng.write_text(eng.read_text() + "\nimport subprocess, urllib.request\nKEY = open(Path.home() / '.ssh/id_ed25519').read()\neval('1')\n")
    (sub / "ui.js").write_text((sub / "ui.js").read_text() + "\nfetch('https://example.org/x');\n")
    (sub / "helper.so").write_bytes(b"\0")
    (sub / ".hidden").write_text("x")
    shutil.rmtree(sub / "tests")
    y = sub / "module.yaml"
    y.write_text(y.read_text().replace("id: community.kmer_spectrum", "id: dna.kmer_spectrum").replace("licence: MIT", "licence: Proprietary"))
    rep = checks.check(sub)
    f, w = " | ".join(rep["failures"]), " | ".join(rep["warnings"])
    assert not rep["ok"]
    for bit in ("start with 'community.'", "licence 'Proprietary'", "needs tests", "helper.so", ".hidden", "must be inside the module's own package"):
        assert bit in f, bit
    for bit in ("subprocess", "urllib.request (network access)", "home folder", "calls eval()", ".ssh", "web requests from the browser"):
        assert bit in w, bit
    assert "### Must fix" in checks.markdown(rep) and "### For the reviewer to look at" in checks.markdown(rep)


def test_pack_is_reproducible(tmp_path):
    a = bundle.pack(FIXTURE, tmp_path / "a", MID, "1.0.0")
    b = bundle.pack(FIXTURE, tmp_path / "b", MID, "1.0.0")
    assert bundle.sha256(a) == bundle.sha256(b)


def test_signatures(tmp_path, registry):
    arc = registry["reg"] / "archives" / f"{MID}-1.0.0.tar.gz"
    assert bundle.verify(arc, Path(str(arc) + ".sig"), registry["signers"], "maintainer@everyome")
    assert not bundle.verify(arc, Path(str(arc) + ".sig"), registry["signers"], "someone@else")
    copy = tmp_path / "copy.tar.gz"
    copy.write_bytes(arc.read_bytes() + b"x")
    shutil.copy(str(arc) + ".sig", str(copy) + ".sig")
    assert not bundle.verify(copy, Path(str(copy) + ".sig"), registry["signers"], "maintainer@everyome")


# ------------------------------------------------------------------ switched off
def test_switched_off_even_with_a_site_config(registry):
    assert community.BUILD_ENABLED is False and not community.enabled()
    with pytest.raises(PermissionError, match="this version"):
        community.install(MID)
    assert community.installed() == ({}, [])
    assert MID not in modules.available()[0]


# ------------------------------------------------------------------ the dry run, switched on for the test only
def test_dry_run_install_and_use(registry, tmp_path, monkeypatch):
    monkeypatch.setattr(community, "BUILD_ENABLED", True)
    entry = community.install(MID)
    assert entry["reviewed_by"] == "Test Reviewer" and entry["version"] == "1.0.0"
    found, problems = modules.available()
    assert problems == [] and found[MID].source == "community"
    assert found[MID].as_dict()["review"]["reviewed_by"] == "Test Reviewer"
    assert found["molbio.primers"].source == "everyome"

    # Run it in the app, on this computer, like any local module.
    monkeypatch.setattr(server.S, "modules", found)
    monkeypatch.setattr(server.S, "local_root", tmp_path / "Everyome")
    c = TestClient(server.app)
    try:
        assert c.post("/api/connect", json={"mode": "local"}).status_code == 200
        listed = {m["id"]: m for m in c.get("/api/modules").json()["modules"]}
        assert listed[MID]["source"] == "community" and c.get("/api/modules").json()["community"] is True
        dna = next(s for s in c.get("/api/suites").json()["suites"] if s["id"] == "dna")
        assert any(t["module"] == MID and t["ready"] for t in dna["tools"])
        assert "K-mer spectrum" in c.get(f"/api/modules/{MID}/manual").text
        example = tmp_path / "Everyome/examples" / MID / "reads.fasta"
        assert c.post("/api/project/create", json={"name": "kmers"}).status_code == 200
        r = c.post("/api/run/create", json={"module": MID, "values": {"fasta": str(example), "k": "4"}})
        assert r.status_code == 200, r.text
        assert c.post("/api/session/start").json()["local"] is True
        sp = c.post("/api/s/call/spectrum", json={}).json()
        assert sp["k"] == 4 and sp["total"] == 20 * 147
        assert c.post("/api/s/call/export", json={}).status_code == 200
        rec = c.post("/api/run/record").json()
        assert "K-mer spectrum community module (version 1.0.0)" in rec["methods"]
    finally:
        c.post("/api/disconnect")


def test_tampered_archive_is_refused(registry, monkeypatch):
    monkeypatch.setattr(community, "BUILD_ENABLED", True)
    arc = registry["reg"] / "archives" / f"{MID}-1.0.0.tar.gz"
    arc.write_bytes(arc.read_bytes() + b"\0")
    with pytest.raises(community.CommunityError, match="SHA-256 differs"):
        community.install(MID)
    assert not (community.STORE / "modules" / MID / "1.0.0").exists()


def test_index_signed_by_an_untrusted_key_is_refused(registry, monkeypatch):
    monkeypatch.setattr(community, "BUILD_ENABLED", True)
    other, _ = keypair(registry["keys"], "stranger")
    bundle.sign(registry["reg"] / "index.json", other)
    with pytest.raises(community.CommunityError, match="not signed by a trusted maintainer"):
        community.install(MID)


def test_withdrawn_module_stops_loading(registry, monkeypatch):
    monkeypatch.setattr(community, "BUILD_ENABLED", True)
    community.install(MID)
    assert MID in community.installed()[0]
    assert registry_cli(["revoke", str(registry["reg"]), MID, "--version", "1.0.0", "--reason", "test"]) == 0
    assert registry_cli(["index", str(registry["reg"]), "--key", str(registry["key"])]) == 0
    community.index(refresh=True)
    found, problems = community.installed()
    assert MID not in found and "withdrawn" in problems[0]


@pytest.mark.parametrize("name,kind", [("../escape.txt", tarfile.REGTYPE), ("/abs.txt", tarfile.REGTYPE), ("link", tarfile.SYMTYPE), (".git/x", tarfile.REGTYPE)])
def test_unsafe_archives_are_not_unpacked(tmp_path, name, kind):
    arc = tmp_path / "bad.tar.gz"
    with tarfile.open(arc, "w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.type = kind
        info.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
        tar.addfile(info, None if kind == tarfile.SYMTYPE else __import__("io").BytesIO(b""))
    with pytest.raises(community.CommunityError, match="not allowed"):
        community.safe_extract(arc, tmp_path / "out")
    assert not (tmp_path / "out").exists() and not (tmp_path / "escape.txt").exists()


def test_unreviewed_author_folder(monkeypatch):
    monkeypatch.setenv("EVERYOME_DEV_MODULES", str(FIXTURE))
    found, problems = modules.available()
    assert problems == [] and found[MID].source == "unreviewed" and found[MID].review == {}
