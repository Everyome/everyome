"""Finding modules.

First-party modules ship inside Everyome. Community modules are built in but
switched off (core/community.py): each must be reviewed, signed and pinned
before it can be offered (docs/PLAN.md section 7, docs/REVIEW_CHECKLIST.md).
"""
from __future__ import annotations

from pathlib import Path

from . import community
from .manifest import Manifest, ManifestError, load

FIRST_PARTY = Path(__file__).resolve().parents[1] / "modules"


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


def available() -> tuple[dict[str, Manifest], list[str]]:
    """Everything the app offers: Everyome's own modules, then reviewed community ones (when switched on),
    then an author's unreviewed folders. Everyome's own ids always win."""
    found, problems = discover()
    for more, probs in (community.installed(), community.unreviewed()):
        problems += probs
        for mid, m in more.items():
            if mid in found:
                problems.append(f"{m.dir}: id {mid} is already used by another module; not loaded")
            elif not mid.startswith("community."):
                problems.append(f"{m.dir}: community module ids start with 'community.'; not loaded")
            else:
                found[mid] = m
    return found, problems
