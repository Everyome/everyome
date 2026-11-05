"""Containers for staged modules, pinned by digest (docs/PIPELINES.md).

A staged module can run its tools in containers instead of relying on what the
cluster has installed. It lists them in module.yaml under batch.containers as
`name: registry/repository:tag@sha256:<digest>`. The digest fixes the exact
image: the tag is only for people to read. Images are pulled once into the
same shared folder as the pipelines' containers (<pipelines folder>/containers),
so a cluster without internet on its compute nodes can fill it in advance:

    python -m everyome.core.containers pull phylo.tree --into <pipelines folder>/containers
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REF = re.compile(r"^(?P<repo>[a-z0-9][a-z0-9._/-]*):(?P<tag>[A-Za-z0-9._-]+)@sha256:(?P<digest>[0-9a-f]{64})$")


def parse(ref: str) -> dict:
    m = REF.match(ref or "")
    if not m:
        raise ValueError(f"{ref!r} should look like registry/repository:tag@sha256:<64 hex digits>")
    return m.groupdict()


def image_file(ref: str) -> str:
    """The image's file name in the shared folder; the digest is part of it, so a new pin never reuses an old image."""
    p = parse(ref)
    return f"{p['repo'].replace('/', '-')}-{p['tag']}-{p['digest'][:12]}.sif"


def pull_url(ref: str) -> str:
    p = parse(ref)
    return f"docker://{p['repo']}@sha256:{p['digest']}"


def label(ref: str) -> str:
    """Short form for records: repository:tag (sha256:first 12)."""
    p = parse(ref)
    return f"{p['repo']}:{p['tag']} (sha256:{p['digest'][:12]})"


def environment(site_dir: str) -> list[str]:
    """Line for a stage's job script: where the shared container images live."""
    return [f"export EVERYOME_CONTAINERS={shlex.quote(site_dir.rstrip('/') + '/containers')}"]


def runner() -> str:
    exe = shutil.which("apptainer") or shutil.which("singularity")
    if not exe:
        raise RuntimeError("Neither apptainer nor singularity was found on this node. Ask IT to make Apptainer available.")
    return exe


def ensure(ref: str, cache: Path) -> Path:
    """The image file, pulled first if this folder does not have it yet."""
    cache.mkdir(parents=True, exist_ok=True)
    final = cache / image_file(ref)
    if final.exists():
        return final
    # Intent: pull to a private name and rename, so two jobs pulling at once never see a half-written image.
    part = cache / f".{final.name}.{os.getpid()}.part"
    print(f"Pulling {label(ref)} into {cache} (once per cluster folder)", flush=True)
    try:
        subprocess.run([runner(), "pull", "--force", str(part), pull_url(ref)], check=True)
        os.replace(part, final)
    finally:
        part.unlink(missing_ok=True)
    return final


def command(ref: str, cache: Path, args: list[str], binds: list[str] = ()) -> list[str]:
    """argv that runs args inside the pinned image, with the folders the tool must see bound in."""
    sif = ensure(ref, cache)
    # Intent: bind only folders that exist; Apptainer already binds the home and working folders. "src:dst" binds a
    # folder at a fixed place inside the image (for tools that expect their data there).
    out = []
    for p in binds:
        src, _, dst = str(p).partition(":")
        src = str(Path(src).resolve())
        if Path(src).is_dir():
            out.append(f"{src}:{dst}" if dst else src)
    b = [x for d in dict.fromkeys(out) for x in ("--bind", d)]
    return [runner(), "exec", *b, str(sif), *args]


def main(argv=None) -> int:
    from . import modules
    ap = argparse.ArgumentParser(prog="python -m everyome.core.containers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("pull", help="fill a containers folder in advance (on a node with internet)")
    p.add_argument("modules", nargs="*")
    p.add_argument("--into", required=True)
    a = ap.parse_args(argv)
    found, _ = modules.discover()
    pinned = {mid: m.containers for mid, m in found.items() if m.containers}
    if a.cmd == "list":
        for mid, cs in pinned.items():
            for name, ref in cs.items():
                print(f"{mid}  {name}  {label(ref)}  {image_file(ref)}")
        return 0
    for mid in a.modules or list(pinned):
        if mid not in pinned:
            print(f"{mid}: no pinned containers", file=sys.stderr)
            return 1
        for ref in pinned[mid].values():
            print(ensure(ref, Path(a.into)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
