"""Finding modules.

Only first-party modules shipped inside Everyome load. Community modules are
built into the design but switched off: they run code on people's cluster
accounts, so each must be reviewed, signed and pinned before it can be offered
(docs/PLAN.md section 7). Nothing here downloads or loads outside code.
"""
from __future__ import annotations

from pathlib import Path

from .manifest import Manifest, ManifestError, load

FIRST_PARTY = Path(__file__).resolve().parents[1] / "modules"
COMMUNITY_ENABLED = False


def discover(root: Path = FIRST_PARTY) -> tuple[dict[str, Manifest], list[str]]:
    """Every valid module under root, plus plain messages for any that failed to load."""
    found, problems = {}, []
    for path in sorted(root.glob("*/*/module.yaml")):
        try:
            m = load(path)
        except ManifestError as e:
            problems.append(str(e))
            continue
        if m.id in found:
            problems.append(f"{path}: id {m.id} is already used by {found[m.id].dir}")
            continue
        # Intent: people learn before they run; a module without a manual and example data is not offered.
        missing = [what for what, ok in (("a manual", m.learn.get("manual")), ("example data", m.demo.get("data") or m.demo.get("build"))) if not ok]
        if missing:
            problems.append(f"{path}: not listed until it has {' and '.join(missing)}")
            continue
        found[m.id] = m
    return found, problems


def community_registry():
    """Placeholder for the reviewed community registry; stays off until review and signing exist."""
    if not COMMUNITY_ENABLED:
        raise PermissionError("Community modules are switched off in this version of Everyome.")
    raise NotImplementedError
