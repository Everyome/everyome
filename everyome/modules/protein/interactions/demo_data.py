"""Build the interaction prediction demo: two simulated complexes of two chains each, and the 'true' structures the
demo pipeline predicts.

<root> = <demo cluster>/data/protein.interactions/
  complexes/   one FASTA file per complex, with both chains (binder.fasta, nonbinder.fasta)

  binder      two small helical bundles packed against each other: a confident interface (high ipTM, high pDockQ)
  nonbinder   the same kind of chains, which the predictor places apart with no real contact and low confidence
truth() builds their Cα traces, confidence and scores the same way every time.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..structure.demo_data import AA_HELIX, AA_LOOP, _bridge, _helix

SCORES = {"binder": {"iptm": 0.86, "ptm": 0.84}, "nonbinder": {"iptm": 0.22, "ptm": 0.46}}


def _bundle(rng, centre: np.ndarray, flip: float = 1.0) -> np.ndarray:
    """Three 22-residue helices side by side, joined by short loops (a compact helical bundle)."""
    parts, prev = [], None
    for k, (dx, dy) in enumerate(((0, 0), (9.5, 0), (4.75, 8.2))):
        axis = np.array([0, 0, 1.0 if k % 2 == 0 else -1.0]) * flip
        start = centre + np.array([dx, dy, -15 if k % 2 == 0 else 15]) * np.array([1, 1, flip])
        h = _helix(22, start, axis, phase=k)
        if prev is not None:
            parts.append(_bridge(prev[-1], h[0], 4, rng))
        parts.append(h)
        prev = h
    return np.vstack(parts)


def truth() -> dict:
    out = {}
    for name, gap, seed in (("binder", 8.0, 3), ("nonbinder", 45.0, 4)):
        rng = np.random.default_rng(seed)
        a = _bundle(rng, np.array([0.0, 0, 0]))
        b = _bundle(rng, np.array([gap + 9.5, 0, 0]), flip=-1.0)
        seq = lambda n: "".join(rng.choice(list(AA_HELIX + AA_LOOP[:2]), n))
        n = len(a)
        if name == "binder":
            plddt = np.r_[np.full(n, 88.0), np.full(n, 87.0)] + rng.normal(0, 3, 2 * n)
        else:                                   # each chain folds, but nothing holds them together
            plddt = np.r_[np.full(n, 78.0), np.full(n, 72.0)] + rng.normal(0, 4, 2 * n)
        out[name] = {"seqs": [seq(n), seq(n)], "xyz": np.vstack([a, b]), "chains": ["A"] * n + ["B"] * n,
                     "plddt": np.clip(plddt, 20, 97), **SCORES[name]}
    return out


def build(root: Path) -> Path:
    d = root / "complexes"
    d.mkdir(parents=True, exist_ok=True)
    for name, p in truth().items():
        (d / f"{name}.fasta").write_text(f">{name}_A\n{p['seqs'][0]}\n>{name}_B\n{p['seqs'][1]}\n")
    return root
