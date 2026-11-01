"""Pipelines that ship with Everyome: pinned, checked, and installed on the cluster from this computer.

Everyome does not ask the cluster to download a pipeline when a run starts.
Each Nextflow pipeline a module uses is packed as a bundle: the pipeline's own
code at a pinned release (minus its docs, tests and CI files) plus the Nextflow
plugins it needs. Bundles come from the everyome-pipelines package (or a folder
named in EVERYOME_PIPELINE_BUNDLES), are checked against the SHA-256 recorded
in pipelines.lock.json, and are copied to the cluster when the person presses
Run. The cluster then runs that copy with Nextflow offline, so it needs no
access to GitHub or the plugin registry.

Software containers are too large to ship. Nextflow keeps them in one shared
folder next to the pipelines, so they are downloaded once per cluster; sites
with no internet can fill that folder from a connected computer (docs/PIPELINES.md).

  python -m everyome.core.pipelines list
  python -m everyome.core.pipelines build [KEY ...] --into DIR [--update-lock]   (maintainers)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shlex
import sys
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

LOCK = Path(__file__).resolve().parents[1] / "pipelines.lock.json"
USER_BUNDLES = Path.home() / ".everyome" / "pipeline_bundles"
# Intent: only what the pipeline needs to run; documentation, tests and CI files stay upstream.
DROP_TOP = {"docs", "tests", ".github", ".devcontainer", ".vscode", ".hooks", "CHANGELOG.md", "nf-test.config", "tower.yml",
            "ro-crate-metadata.json", ".gitattributes", ".gitignore", ".editorconfig", ".prettierrc.yml", ".prettierignore",
            ".pre-commit-config.yaml", ".nf-core.yml", ".gitpod.yml", ".markdownlint.yml"}
CONTAINER = re.compile(r"'((?:community\.wave\.seqera\.io|quay\.io|biocontainers|docker\.io|nf-core)/[^'\s]+)'")


def lock() -> dict:
    return json.loads(LOCK.read_text())


def key(pipeline: str, revision: str) -> str:
    return f"{pipeline}@{revision}"


def folder_name(k: str) -> str:
    """nf-core/rnaseq@3.27.0 -> nf-core-rnaseq-3.27.0 (the folder on the cluster, and the archive's name)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", k.replace("@", "-"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ building bundles (maintainers, or a laptop with internet)
def _get(url: str) -> bytes:
    from everyome import __version__
    req = urllib.request.Request(url, headers={"User-Agent": f"everyome/{__version__}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _trim_and_pack(tarball: bytes, root: str) -> tuple[bytes, list[str]]:
    """Repack a GitHub release tarball reproducibly under root/, without docs, tests and CI files."""
    out, containers = io.BytesIO(), set()
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as src:
        members = sorted((m for m in src.getmembers() if m.isfile()), key=lambda m: m.name)
        with tarfile.open(fileobj=out, mode="w") as dst:
            for m in members:
                parts = PurePosixPath(m.name).parts[1:]        # drop GitHub's <repo>-<tag>/ folder
                if not parts or parts[0] in DROP_TOP or "tests" in parts[:-1]:
                    continue
                data = src.extractfile(m).read()
                if parts[-1] == "main.nf" and parts[0] == "modules":
                    containers.update(CONTAINER.findall(data.decode(errors="replace")))
                info = tarfile.TarInfo("/".join((root,) + parts))
                info.size, info.mtime, info.uid, info.gid, info.uname, info.gname = len(data), 0, 0, 0, "", ""
                info.mode = 0o755 if m.mode & 0o111 else 0o644      # bin/ scripts stay runnable
                dst.addfile(info, io.BytesIO(data))
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0, filename="") as g:
        g.write(out.getvalue())
    return gz.getvalue(), sorted(containers)


def _plugins(code: bytes) -> list[tuple[str, str]]:
    """The plugins a pipeline's nextflow.config asks for, as (id, version)."""
    with tarfile.open(fileobj=io.BytesIO(code), mode="r:gz") as t:
        cfg = next(t.extractfile(m).read().decode() for m in t.getmembers() if m.name.count("/") == 1 and m.name.endswith("/nextflow.config"))
    block = re.search(r"plugins\s*\{([^}]*)\}", cfg)
    return re.findall(r"id\s+'([\w-]+)@([\w.-]+)'", block.group(1)) if block else []


def _plugin_release(pid: str, version: str) -> dict:
    meta = json.loads(_get(f"https://registry.nextflow.io/api/v1/plugins/{pid}"))
    return next(r for r in meta["plugin"]["releases"] if r["version"] == version)


def build(k: str, into: Path, update_lock: bool = False) -> dict:
    """Fetch the pinned release and its plugins, pack them, and check (or record) their checksums."""
    pipeline, revision = k.split("@")
    entry = lock().get(k, {})
    owner_repo = pipeline
    code, containers = _trim_and_pack(_get(f"https://github.com/{owner_repo}/archive/refs/tags/{revision}.tar.gz"), folder_name(k))
    new = {"pipeline": pipeline, "revision": revision, "source": f"https://github.com/{owner_repo}/tree/{revision}",
           "archive": folder_name(k) + ".tar.gz", "sha256": sha256(code), "bytes": len(code), "containers": containers, "plugins": []}
    into.mkdir(parents=True, exist_ok=True)
    (into / new["archive"]).write_bytes(code)
    for pid, ver in _plugins(code):
        rel = _plugin_release(pid, ver)
        # Intent: the registry's public download address (its blob address needs a token).
        url = f"https://registry.nextflow.io/api/v1/plugins/{pid}/{ver}/download/{pid}-{ver}.zip"
        data = _get(url)
        if hashlib.sha512(data).hexdigest() != rel["sha512sum"]:
            raise RuntimeError(f"{pid} {ver} does not match the plugin registry's checksum")
        name = f"{pid}-{ver}.zip"
        (into / name).write_bytes(data)
        new["plugins"].append({"id": pid, "version": ver, "archive": name, "sha256": sha256(data), "sha512": rel["sha512sum"], "url": url})
    if entry and not update_lock:
        for a, b in [(entry["sha256"], new["sha256"])] + [(p["sha256"], q["sha256"]) for p, q in zip(entry["plugins"], new["plugins"])]:
            if a != b:
                raise RuntimeError(f"{k}: the files fetched now differ from the pinned ones; nothing was changed")
    if update_lock:
        all_ = lock() if LOCK.exists() else {}
        all_[k] = new
        LOCK.write_text(json.dumps(dict(sorted(all_.items())), indent=1) + "\n")
    return new


# ------------------------------------------------------------------ finding bundles on this computer
def bundle_dirs() -> list[Path]:
    dirs = [Path(p) for p in os.environ.get("EVERYOME_PIPELINE_BUNDLES", "").split(os.pathsep) if p]
    try:
        import everyome_pipelines
        dirs.append(Path(everyome_pipelines.BUNDLES))
    except ImportError:
        pass
    return dirs + [USER_BUNDLES]


def find(k: str) -> dict:
    """The lock entry with checked local paths to its archives; raises a plain-language error if missing or changed."""
    entry = lock().get(k)
    if not entry:
        raise LookupError(f"{k} is not one of the pipelines this version of Everyome ships.")
    files = {}
    for name, want in [(entry["archive"], entry["sha256"])] + [(p["archive"], p["sha256"]) for p in entry["plugins"]]:
        path = next((d / name for d in bundle_dirs() if (d / name).is_file()), None)
        if path is None:
            raise FileNotFoundError(f"The pipeline files for {k} are not on this computer. Install them with: "
                                    f"pip install everyome-pipelines  (or ask whoever installed Everyome).")
        if sha256(path.read_bytes()) != want:
            raise ValueError(f"{path} does not match the pinned {k}; it was not used. Reinstall everyome-pipelines.")
        files[name] = path
    return {**entry, "files": files}


# ------------------------------------------------------------------ installing on the cluster
def remote_dir(site_dir: str, k: str) -> str:
    return f"{site_dir.rstrip('/')}/{folder_name(k)}"


def installed(backend, site_dir: str, k: str) -> bool:
    entry = lock()[k]
    marker = f"{remote_dir(site_dir, k)}/.everyome_bundle"
    try:
        return backend.read_text(marker).strip() == entry["sha256"]
    except (FileNotFoundError, OSError):
        return False


def install(backend, site_dir: str, k: str, python: str) -> dict:
    """Copy the pipeline and its plugins to the cluster, check them there, and unpack them. Safe to repeat."""
    if installed(backend, site_dir, k):
        return {"installed": False, "dir": remote_dir(site_dir, k)}
    b = find(k)
    q, site = shlex.quote, site_dir.rstrip("/")
    inbox = f"{site}/.incoming"
    py_sha = f"{q(python)} -c " + q("import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())")
    for name, path in b["files"].items():
        want = next(x["sha256"] for x in [b] + b["plugins"] if x["archive"] == name)
        backend.write_bytes(f"{inbox}/{name}", path.read_bytes())
        rc, out, err = backend.run(f"{py_sha} {q(inbox + '/' + name)}", timeout=300)
        if rc or out.strip() != want:
            raise RuntimeError(f"{name} changed on its way to the cluster; nothing was installed. {err.strip()}")
    for p in b["plugins"]:
        # Intent: Nextflow looks for plugins as <dir>/<id>-<version>/ when it runs offline.
        dest = f"{site}/plugins/{p['id']}-{p['version']}"
        rc, _, err = backend.run(f"rm -rf {q(dest)} && mkdir -p {q(dest)} && {q(python)} -m zipfile -e {q(inbox + '/' + p['archive'])} {q(dest)}", timeout=300)
        if rc:
            raise RuntimeError(f"Could not unpack the {p['id']} plugin: {err.strip()}")
    dest, tmp = remote_dir(site, k), f"{inbox}/{folder_name(k)}"
    rc, _, err = backend.run(f"rm -rf {q(tmp)} && tar -xzf {q(inbox + '/' + b['archive'])} -C {q(inbox)} && "
                             f"rm -rf {q(dest)} && mv {q(tmp)} {q(dest)} && printf %s {q(b['sha256'])} > {q(dest + '/.everyome_bundle')} && "
                             f"mkdir -p {q(site + '/containers')} && rm -f {' '.join(q(inbox + '/' + n) for n in b['files'])}", timeout=600)
    if rc:
        raise RuntimeError(f"Could not unpack {k} on the cluster: {err.strip()}")
    return {"installed": True, "dir": dest}


def environment(site_dir: str) -> list[str]:
    """Lines for the pipeline's job script: run offline, with the shipped plugins and the shared container folder."""
    site = shlex.quote(site_dir.rstrip("/"))
    return ["export NXF_OFFLINE=true", f"export NXF_PLUGINS_DIR={site}/plugins",
            f"export NXF_APPTAINER_CACHEDIR={site}/containers", f"export NXF_SINGULARITY_CACHEDIR={site}/containers"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m everyome.core.pipelines")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    b = sub.add_parser("build")
    b.add_argument("keys", nargs="*")
    b.add_argument("--into", required=True)
    b.add_argument("--update-lock", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for k, e in lock().items():
            try:
                find(k); here = "on this computer"
            except (FileNotFoundError, ValueError) as err:
                here = str(err).split(".")[0]
            print(f"{k}  {e['bytes'] / 1e6:.1f} MB  {len(e['containers'])} containers  sha256 {e['sha256'][:12]}…  {here}")
        return 0
    for k in a.keys or list(lock()):
        e = build(k, Path(a.into), a.update_lock)
        print(f"{k}: {e['archive']} ({e['bytes'] / 1e6:.1f} MB), {len(e['plugins'])} plugins, {len(e['containers'])} containers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
