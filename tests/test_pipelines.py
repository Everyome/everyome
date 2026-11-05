"""Pipelines shipped with Everyome: packed reproducibly, checked by SHA-256, installed on the cluster when Run is pressed,
and run from that copy offline. Uses small stand-in bundles, so no download is needed."""
import io
import json
import sys
import tarfile
import zipfile

import pytest
from fastapi.testclient import TestClient

from everyome.core import modules, pipelines, server
from everyome.core.backends import LocalBackend

KEY = "nf-core/rnaseq@3.27.0"


def tgz(files: dict, modes: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), (modes or {}).get(name, 0o644)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.fixture()
def bundles(tmp_path, monkeypatch):
    """A stand-in pipeline and plugin, with a lock that pins them, found through EVERYOME_PIPELINE_BUNDLES."""
    src = tgz({"rnaseq-3.27.0/main.nf": "workflow {}", "rnaseq-3.27.0/nextflow.config": "plugins {\n  id 'nf-schema@2.7.2'\n}\n",
               "rnaseq-3.27.0/bin/tool.py": "print(1)", "rnaseq-3.27.0/LICENSE": "MIT",
               "rnaseq-3.27.0/modules/nf-core/fastqc/main.nf": "container \"${ x ? 'https://depot/x' : 'biocontainers/fastqc:0.12.1--hdfd78af_0' }\"",
               "rnaseq-3.27.0/modules/nf-core/fastqc/tests/main.nf.test": "test", "rnaseq-3.27.0/docs/usage.md": "docs",
               "rnaseq-3.27.0/.github/workflows/ci.yml": "ci", "rnaseq-3.27.0/CHANGELOG.md": "log"},
              {"rnaseq-3.27.0/bin/tool.py": 0o755})
    code, containers = pipelines._trim_and_pack(src, pipelines.folder_name(KEY))
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        z.writestr("classes/Plugin.class", "x")
    plugin = zbuf.getvalue()
    d = tmp_path / "bundles"
    d.mkdir()
    (d / "nf-core-rnaseq-3.27.0.tar.gz").write_bytes(code)
    (d / "nf-schema-2.7.2.zip").write_bytes(plugin)
    lock = {KEY: {"pipeline": "nf-core/rnaseq", "revision": "3.27.0", "archive": "nf-core-rnaseq-3.27.0.tar.gz", "sha256": pipelines.sha256(code),
                  "bytes": len(code), "containers": containers, "source": "https://github.com/nf-core/rnaseq/tree/3.27.0",
                  "plugins": [{"id": "nf-schema", "version": "2.7.2", "archive": "nf-schema-2.7.2.zip", "sha256": pipelines.sha256(plugin)}]}}
    real = json.loads(pipelines.LOCK.read_text())
    (tmp_path / "lock.json").write_text(json.dumps({**real, **lock}))
    monkeypatch.setattr(pipelines, "LOCK", tmp_path / "lock.json")
    monkeypatch.setattr(pipelines, "USER_BUNDLES", tmp_path / "no_user_bundles")
    # Intent: hide an installed everyome-pipelines too, so only these stand-in files are found (as in a clean checkout).
    monkeypatch.setitem(sys.modules, "everyome_pipelines", None)
    monkeypatch.setenv("EVERYOME_PIPELINE_BUNDLES", str(d))
    return {"dir": d, "code": code, "containers": containers}


def test_shipped_lock_pins_every_pipeline_module():
    lock = pipelines.lock()
    found, _ = modules.available()
    used = {pipelines.key(m.nextflow["pipeline"], str(m.nextflow["revision"])) for m in found.values() if m.nextflow}
    assert used == {"nf-core/rnaseq@3.27.0", "nf-core/scrnaseq@4.2.0", "nf-core/genomeassembler@2.0.1", "nf-core/bacass@2.6.1", "nf-core/proteinfold@2.0.0",
                    "nf-core/sarek@3.11.0", "nf-core/hic@2.1.0", "nf-core/riboseq@2.0.0", "nf-core/atacseq@2.1.2"} and used <= set(lock)
    for k in used:
        e = lock[k]
        # Intent: nf-core/hic 2.1.0 predates nf-core's validation plugins and uses none; every other pipeline ships its own.
        assert len(e["sha256"]) == 64 and (e["plugins"] or k == "nf-core/hic@2.1.0") and all(len(p["sha256"]) == 64 for p in e["plugins"]) and e["containers"]


def test_trim_and_pack(bundles):
    with tarfile.open(fileobj=io.BytesIO(bundles["code"]), mode="r:gz") as t:
        names = {m.name: m for m in t.getmembers()}
    root = "nf-core-rnaseq-3.27.0/"
    assert set(names) == {root + n for n in ("main.nf", "nextflow.config", "bin/tool.py", "LICENSE", "modules/nf-core/fastqc/main.nf")}
    assert names[root + "bin/tool.py"].mode == 0o755 and names[root + "main.nf"].mode == 0o644 and names[root + "main.nf"].mtime == 0
    assert bundles["containers"] == ["biocontainers/fastqc:0.12.1--hdfd78af_0"]
    assert pipelines._plugins(bundles["code"]) == [("nf-schema", "2.7.2")]


def test_packing_is_reproducible():
    src = tgz({"p-1.0/main.nf": "a", "p-1.0/conf/base.config": "b"})
    assert pipelines._trim_and_pack(src, "x")[0] == pipelines._trim_and_pack(src, "x")[0]


def test_find_checks_checksums(bundles):
    assert set(pipelines.find(KEY)["files"]) == {"nf-core-rnaseq-3.27.0.tar.gz", "nf-schema-2.7.2.zip"}
    (bundles["dir"] / "nf-schema-2.7.2.zip").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="does not match the pinned"):
        pipelines.find(KEY)
    (bundles["dir"] / "nf-schema-2.7.2.zip").unlink()
    with pytest.raises(FileNotFoundError, match="pip install everyome-pipelines"):
        pipelines.find(KEY)


def test_install_on_the_cluster(bundles, tmp_path):
    be, site = LocalBackend(tmp_path), str(tmp_path / "site")
    assert not pipelines.installed(be, site, KEY)
    r = pipelines.install(be, site, KEY, sys.executable)
    d = tmp_path / "site" / "nf-core-rnaseq-3.27.0"
    assert r == {"installed": True, "dir": str(d)} and (d / "main.nf").read_text() == "workflow {}"
    assert (d / "bin/tool.py").stat().st_mode & 0o111 and (tmp_path / "site/plugins/nf-schema-2.7.2/classes/Plugin.class").exists()
    assert (tmp_path / "site/containers").is_dir() and not list((tmp_path / "site/.incoming").iterdir())
    assert pipelines.installed(be, site, KEY) and pipelines.install(be, site, KEY, sys.executable)["installed"] is False
    # A changed marker (for example, an older copy) means it is installed again.
    (d / ".everyome_bundle").write_text("old")
    assert pipelines.install(be, site, KEY, sys.executable)["installed"] is True


def test_run_installs_then_submits(bundles, tmp_path, monkeypatch):
    """Pressing Run on a real (not demo) run copies the pipeline first, then submits the head job that runs it offline."""
    monkeypatch.setattr(server.S, "demo_root", tmp_path / "demo_cluster")
    c = TestClient(server.app)
    try:
        assert c.post("/api/connect", json={"mode": "demo"}).status_code == 200
        assert c.post("/api/project/create", json={"name": "p"}).status_code == 200
        row = {"sample": "a", "fastq_1": "/d/a_R1.fastq.gz", "fastq_2": "", "strandedness": "auto", "condition": "x"}
        run = c.post("/api/run/create", json={"module": "rna.bulk_de", "values": {"samples": [row, {**row, "sample": "b"}]}}).json()
        assert run["job_prefix"] == "Claude" and run["pipelines_dir"].endswith("/pipelines")
        # Intent: treat this run as a real one, so the pipeline is installed rather than stood in for.
        server.S.run["demo"] = False
        pre = c.post("/api/run/preview", json={}).json()
        assert pre["pipeline"]["installed"] is False and pre["pipeline"]["here"] is True
        assert f"nextflow run {run['pipelines_dir']}/nf-core-rnaseq-3.27.0 " in pre["scripts"][0]["script"]
        assert c.post("/api/run/submit", json={}).status_code == 200
        assert pipelines.installed(server.S.backend, run["pipelines_dir"], KEY)
        assert c.post("/api/run/preview", json={}).json()["pipeline"]["installed"] is True
    finally:
        c.post("/api/disconnect")


def test_unversioned_plugins_are_pinned_or_refused():
    import io
    import tarfile

    def code(cfg):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            data = cfg.encode()
            info = tarfile.TarInfo("p-1.0/nextflow.config"); info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        return buf.getvalue()
    assert pipelines._plugins(code("plugins {\n    id 'nf-validation' // old style\n}\n")) == [("nf-validation", "1.1.3")]
    with pytest.raises(RuntimeError, match="nf-unknown without a version"):
        pipelines._plugins(code("plugins { id 'nf-unknown' }"))
