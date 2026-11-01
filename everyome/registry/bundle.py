"""Packing, signing and verifying community modules, and the registry index.

Signatures use OpenSSH (`ssh-keygen -Y sign/verify`), which Everyome already
relies on: maintainers sign with their own SSH keys, and the app trusts only
the keys in its `allowed_signers` file. Nothing here needs a password or a
new dependency.

Registry layout (a git repository maintainers control):
  entries/<id>/<version>.json   one approval: archive name, SHA-256, who reviewed it and when
  archives/<id>-<version>.tar.gz (+ .sig)
  revoked.json                  [{id, version, reason}]
  index.json (+ .sig)           built from the above, signed by a maintainer
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import tarfile
import time
from pathlib import Path

NAMESPACE = "everyome-module"     # signatures made for one purpose cannot be reused for another


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pack(folder: Path, out_dir: Path, module_id: str, version: str) -> Path:
    """A reproducible archive of the module folder: same files in, same bytes out."""
    folder, out_dir = Path(folder), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{module_id}-{version}.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for f in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = tar.gettarinfo(str(f), arcname=str(f.relative_to(folder)))
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with open(f, "rb") as fh:
                tar.addfile(info, fh)
    with open(out, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(buf.getvalue())
    return out


def sign(path: Path, key: Path) -> Path:
    """Sign a file with an SSH private key (the maintainer runs this; ssh-agent or a passphrase prompt may appear)."""
    # Intent: re-signing (for example a rebuilt index) replaces the old signature; ssh-keygen will not overwrite it.
    Path(str(path) + ".sig").unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", str(key), "-n", NAMESPACE, str(path)], check=True, capture_output=True)
    return Path(str(path) + ".sig")


def verify(path: Path, sig: Path, allowed_signers: Path, identity: str) -> bool:
    """True only if `identity` (listed in allowed_signers) signed exactly this file."""
    if not Path(sig).is_file() or not Path(allowed_signers).is_file():
        return False
    with open(path, "rb") as fh:
        p = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers), "-I", identity, "-n", NAMESPACE, "-s", str(sig)],
                           stdin=fh, capture_output=True)
    return p.returncode == 0


def approve(registry: Path, archive: Path, report: dict, reviewer: str, notes: str = "") -> Path:
    """Record a reviewer's approval of one archive (after the checklist is done)."""
    if not report.get("ok"):
        raise ValueError("The automated checks did not pass; fix those first.")
    i = report["info"]
    entry = {"id": i["id"], "version": i["version"], "name": i["name"], "licence": i["licence"], "archive": Path(archive).name,
             "sha256": sha256(archive), "reviewed_by": reviewer, "reviewed_at": time.strftime("%Y-%m-%d"),
             "warnings_reviewed": report["warnings"], "notes": notes}
    out = Path(registry) / "entries" / i["id"] / f"{i['version']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entry, indent=1))
    return out


def build_index(registry: Path) -> Path:
    """index.json from every approval plus the withdrawn list (the app skips those). Sign it afterwards with sign()."""
    registry = Path(registry)
    entries = [json.loads(p.read_text()) for p in sorted((registry / "entries").glob("*/*.json"))]
    revoked = json.loads((registry / "revoked.json").read_text()) if (registry / "revoked.json").exists() else []
    out = registry / "index.json"
    out.write_text(json.dumps({"format": 1, "built": time.strftime("%Y-%m-%d %H:%M:%S"), "modules": entries, "revoked": revoked}, indent=1))
    return out
