"""Community modules: installing reviewed, signed modules, and loading them.

Switched off. Two locks must both be open before anything is fetched or loaded:
BUILD_ENABLED in this file (False in this version of Everyome) and
"enabled": true in ~/.everyome/community.json, which a person or their IT team
sets on purpose. With either closed, nothing here downloads or imports outside code.

When on, a module is offered only if
  - the registry index is signed by a key in the site's allowed_signers file,
  - its archive's SHA-256 matches the reviewed entry in that index, and the
    archive itself carries a maintainer's signature,
  - it has not been withdrawn (the index's revoked list), and
  - it passes the automated checks again after unpacking.

Authors can try their own module before submitting it by pointing
EVERYOME_DEV_MODULES at its folder. Those load with an "Unreviewed" label and
are never fetched from anywhere.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

from .manifest import Manifest, ManifestError, load

BUILD_ENABLED = False             # Intent: the registry ships switched off; turning it on is a release decision.
HOME = Path.home() / ".everyome"
CONFIG = HOME / "community.json"  # {"enabled": false, "registry": URL or folder, "allowed_signers": path, "signers": [identities]}
STORE = HOME / "community"
MAX_DOWNLOAD = 25 * 1024 ** 2


class CommunityError(RuntimeError):
    """Something about a community module could not be trusted; the message says what."""


def settings() -> dict:
    try:
        return {"enabled": False, **json.loads(CONFIG.read_text())}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"enabled": False}


def enabled() -> bool:
    return BUILD_ENABLED and settings().get("enabled") is True


def _need_enabled():
    if not BUILD_ENABLED:
        raise PermissionError("Community modules are switched off in this version of Everyome.")
    if settings().get("enabled") is not True:
        raise PermissionError(f"Community modules are switched off on this computer (see {CONFIG}).")


# ------------------------------------------------------------------ fetching
def _fetch(base: str, rel: str, dest: Path) -> Path:
    """Copy base/rel to dest. base is a folder, or an https address; nothing else is accepted."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if base.startswith("https://"):
        with urllib.request.urlopen(base.rstrip("/") + "/" + rel, timeout=30) as r, open(dest, "wb") as fh:
            got = 0
            while chunk := r.read(1 << 16):
                got += len(chunk)
                if got > MAX_DOWNLOAD:
                    raise CommunityError(f"{rel} is larger than {MAX_DOWNLOAD // 1024 ** 2} MB; not downloaded.")
                fh.write(chunk)
    elif "://" in base:
        raise CommunityError("The registry address must start with https:// (or be a folder on this computer).")
    else:
        shutil.copyfile(Path(base).expanduser() / rel, dest)
    return dest


def _verified(path: Path, cfg: dict) -> str:
    """The identity that signed path, or an error if no trusted maintainer did."""
    from everyome.registry.bundle import verify
    signers = Path(cfg.get("allowed_signers", "")).expanduser()
    for ident in cfg.get("signers", []):
        if verify(path, Path(str(path) + ".sig"), signers, ident):
            return ident
    raise CommunityError(f"{path.name} is not signed by a trusted maintainer; it was not used.")


def index(refresh: bool = False) -> dict:
    """The registry index, checked against the trusted keys every time it is read."""
    _need_enabled()
    cfg, cached = settings(), STORE / "index.json"
    if refresh or not cached.exists():
        tmp = STORE / "index.new"
        _fetch(cfg["registry"], "index.json", tmp / "index.json")
        _fetch(cfg["registry"], "index.json.sig", tmp / "index.json.sig")
        _verified(tmp / "index.json", cfg)
        for name in ("index.json", "index.json.sig"):
            os.replace(tmp / name, STORE / name)
        tmp.rmdir()
    _verified(cached, cfg)
    return json.loads(cached.read_text())


def _entry(idx: dict, module_id: str, version: str | None = None) -> dict:
    withdrawn = {(r["id"], r.get("version")) for r in idx.get("revoked", [])}
    ok = [e for e in idx["modules"] if e["id"] == module_id and (e["id"], e["version"]) not in withdrawn and (e["id"], None) not in withdrawn
          and (version is None or e["version"] == version)]
    if not ok:
        raise CommunityError(f"{module_id} {version or ''} is not in the registry, or has been withdrawn.".replace("  ", " "))
    return sorted(ok, key=lambda e: [int(x) if x.isdigit() else x for x in e["version"].replace("a", ".").replace("b", ".").replace("rc", ".").split(".")])[-1]


# ------------------------------------------------------------------ installing
def safe_extract(archive: Path, dest: Path, limit: int = MAX_DOWNLOAD) -> None:
    """Unpack only ordinary files and folders, only inside dest, and only up to limit bytes."""
    total = 0
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            p = PurePosixPath(m.name)
            if p.is_absolute() or ".." in p.parts or any(x.startswith(".") for x in p.parts) or not (m.isreg() or m.isdir()):
                raise CommunityError(f"The archive contains {m.name!r}, which is not allowed; nothing was unpacked.")
            total += m.size
        if total > limit:
            raise CommunityError("The archive unpacks to more than the size limit; nothing was unpacked.")
        dest.mkdir(parents=True)
        for m in members:
            out = dest.joinpath(*PurePosixPath(m.name).parts)
            if m.isdir():
                out.mkdir(parents=True, exist_ok=True)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(m) as src, open(out, "wb") as fh:
                shutil.copyfileobj(src, fh)


def install(module_id: str, version: str | None = None) -> dict:
    """Fetch, verify, unpack and re-check one reviewed module. Returns its registry entry."""
    from everyome.registry import bundle, checks
    _need_enabled()
    cfg, entry = settings(), _entry(index(refresh=True), module_id, version)
    with tempfile.TemporaryDirectory() as td:
        arc = _fetch(cfg["registry"], f"archives/{entry['archive']}", Path(td) / entry["archive"])
        _fetch(cfg["registry"], f"archives/{entry['archive']}.sig", Path(td) / (entry["archive"] + ".sig"))
        if bundle.sha256(arc) != entry["sha256"]:
            raise CommunityError(f"{entry['archive']} does not match the reviewed version (SHA-256 differs); it was not installed.")
        _verified(arc, cfg)
        dest = STORE / "modules" / entry["id"] / entry["version"]
        if dest.exists():
            shutil.rmtree(dest)
        safe_extract(arc, dest)
    report = checks.check(dest)
    if not report["ok"] or report["id"] != entry["id"]:
        shutil.rmtree(dest)
        raise CommunityError(f"{entry['id']} failed the automated checks after unpacking; it was removed. " + "; ".join(report["failures"]))
    (dest.parent / "installed.json").write_text(json.dumps({"version": entry["version"], "sha256": entry["sha256"]}))
    return entry


def uninstall(module_id: str) -> None:
    folder = STORE / "modules" / module_id
    if folder.is_dir():
        shutil.rmtree(folder)


# ------------------------------------------------------------------ loading
def _use(m: Manifest, source: str, review: dict | None = None) -> Manifest:
    m.source, m.review = source, review or {}
    # Intent: a module's code is its own package (everyome_c_<id>), so adding its folder cannot shadow anything else.
    if str(m.dir) not in sys.path:
        sys.path.append(str(m.dir))
    return m


def installed() -> tuple[dict[str, Manifest], list[str]]:
    """Reviewed modules installed on this computer and still approved. Empty while switched off."""
    if not enabled():
        return {}, []
    found, problems = {}, []
    try:
        idx = index()
    except (CommunityError, OSError, KeyError) as e:
        return {}, [f"Community modules were not loaded: {e}"]
    for meta in sorted((STORE / "modules").glob("*/installed.json")):
        mid, rec = meta.parent.name, json.loads(meta.read_text())
        try:
            entry = _entry(idx, mid, rec["version"])
            if entry["sha256"] != rec["sha256"]:
                raise CommunityError(f"{mid} {rec['version']} no longer matches the registry")
            found[mid] = _use(load(meta.parent / rec["version"] / "module.yaml"), "community", entry)
        except (CommunityError, ManifestError) as e:
            problems.append(f"{e}. It is not offered; reinstall or remove it.")
    return found, problems


def unreviewed() -> tuple[dict[str, Manifest], list[str]]:
    """An author's own module folders (EVERYOME_DEV_MODULES), for trying a module before submitting it."""
    found, problems = {}, []
    for root in filter(None, os.environ.get("EVERYOME_DEV_MODULES", "").split(os.pathsep)):
        root = Path(root).expanduser()
        for path in ([root / "module.yaml"] if (root / "module.yaml").is_file() else sorted(root.glob("*/module.yaml"))):
            try:
                m = load(path)
            except ManifestError as e:
                problems.append(str(e))
                continue
            found[m.id] = _use(m, "unreviewed")
    return found, problems
