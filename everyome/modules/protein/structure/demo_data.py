"""Build the structure prediction demo: three simulated proteins, and the 'true' structures the demo pipeline predicts.

<root> = <demo cluster>/data/protein.structure/
  sequences/   one FASTA file per protein (twodomain.fasta, hairpin.fasta, disordered.fasta)

The proteins are made up, to show three things predictions often show:
  twodomain   a helical domain and a β-sheet domain joined by a flexible linker, with floppy ends: each domain
              is confident, but how the two sit relative to each other is not (high PAE between them)
  hairpin     a small, compact two-helix protein: confident everywhere
  disordered  a mostly disordered protein with one short helix: low confidence is the right answer here
truth() builds their CA traces and confidence the same way every time.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

AA_HELIX, AA_STRAND, AA_LOOP, AA_DISORDER = "AELKRMQEAL", "VIYTFVTIVW", "GNPDSGKT", "SPGEKDSQNPTESG"


def _helix(n: int, start: np.ndarray, axis: np.ndarray, phase: float = 0) -> np.ndarray:
    """An ideal α-helix: 100° and 1.5 Å per residue, radius 2.3 Å."""
    axis = axis / np.linalg.norm(axis)
    u = np.cross(axis, [0, 0, 1.0] if abs(axis[2]) < .9 else [1.0, 0, 0])
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    t = np.arange(n)
    ang = np.deg2rad(100 * t) + phase
    return start + np.outer(1.5 * t, axis) + 2.3 * (np.outer(np.cos(ang), u) + np.outer(np.sin(ang), v))


def _strand(n: int, start: np.ndarray, direction: np.ndarray, pleat: np.ndarray) -> np.ndarray:
    """A β-strand: 3.3 Å per residue, pleated ±0.9 Å."""
    t = np.arange(n)
    return start + np.outer(3.3 * t, direction) + np.outer(0.9 * (-1) ** t, pleat)


def _bridge(a: np.ndarray, b: np.ndarray, n: int, rng, bulge: float = 2.0) -> np.ndarray:
    """n loop residues from just after a to just before b, bowed out a little."""
    t = np.linspace(0, 1, n + 2)[1:-1, None]
    mid = rng.normal(0, bulge, 3)
    return a + (b - a) * t + np.sin(np.pi * t) * mid


def _walk(n: int, start: np.ndarray, rng, toward: np.ndarray | None = None) -> np.ndarray:
    """A floppy chain: 3.8 Å steps with some persistence (a disordered region)."""
    pts, d = [start], rng.normal(size=3)
    for _ in range(n):
        d = 0.6 * d / np.linalg.norm(d) + rng.normal(size=3) * 0.8 + (0.0 if toward is None else 0.25 * (toward - pts[-1]) / (np.linalg.norm(toward - pts[-1]) + 1e-9))
        d /= np.linalg.norm(d)
        pts.append(pts[-1] + 3.8 * d)
    return np.array(pts[1:])


def _seq(kind_counts: list[tuple[str, int]], rng) -> str:
    pools = {"h": AA_HELIX, "s": AA_STRAND, "l": AA_LOOP, "d": AA_DISORDER}
    return "".join("".join(rng.choice(list(pools[k]), n)) for k, n in kind_counts)


def _bundle(rng, centre) -> tuple[np.ndarray, list]:
    """Four helices of 16 residues, up-down, at the corners of a 10 Å square, joined by 4-residue loops."""
    corners = [np.array(c) for c in ([0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0])]
    parts, kinds = [], []
    for k, c in enumerate(corners):
        up = k % 2 == 0
        h = _helix(16, centre + c + ([0, 0, -12] if up else [0, 0, 12]), np.array([0, 0, 1.0 if up else -1.0]), phase=k)
        if parts:
            parts.append(_bridge(parts[-1][-1], h[0], 4, rng))
            kinds.append(("l", 4))
        parts.append(h)
        kinds.append(("h", 16))
    return np.vstack(parts), kinds


def _sheet(rng, centre) -> tuple[np.ndarray, list]:
    """Five antiparallel strands of 8 residues, 4.8 Å apart, joined by 3-residue turns."""
    parts, kinds = [], []
    for k in range(5):
        fwd = k % 2 == 0
        s = _strand(8, centre + np.array([0 if fwd else 23.1, 4.8 * k, 0]), np.array([1.0 if fwd else -1.0, 0, 0]), np.array([0, 0, 1.0]))
        if parts:
            parts.append(_bridge(parts[-1][-1], s[0], 3, rng, 1.0))
            kinds.append(("l", 3))
        parts.append(s)
        kinds.append(("s", 8))
    return np.vstack(parts), kinds


def _conf(kinds, rng, levels) -> np.ndarray:
    """pLDDT per residue from each stretch's kind (levels: kind -> (mean, sd))."""
    out = []
    for k, n in kinds:
        m, s = levels[k]
        out.extend(np.clip(rng.normal(m, s, n), 15, 98.5))
    return np.array(out)


def truth(seed: int = 3) -> dict:
    """The three proteins: sequence, CA trace, pLDDT and region labels (domain name or 'flexible')."""
    rng = np.random.default_rng(seed)
    prots = {}
    # twodomain: tail - helical bundle - linker - β-sheet - tail
    tail1 = _walk(18, np.array([-6.0, -6, -14]), rng)[::-1]
    d1, k1 = _bundle(rng, np.zeros(3))
    d2, k2 = _sheet(rng, np.array([30.0, 8, 4]))
    link = _bridge(d1[-1], d2[0], 22, rng, 9.0)
    tail2 = _walk(14, d2[-1], rng)
    xyz = np.vstack([tail1, d1, link, d2, tail2])
    kinds = [("d", 18), *k1, ("d", 22), *k2, ("d", 14)]
    regions = ["flexible"] * 18 + ["helical domain"] * len(d1) + ["flexible"] * 22 + ["β-sheet domain"] * len(d2) + ["flexible"] * 14
    prots["twodomain"] = {"xyz": xyz, "seq": _seq(kinds, rng), "regions": regions,
                          "plddt": _conf(kinds, rng, {"h": (92, 3), "s": (89, 3.5), "l": (80, 5), "d": (38, 8)})}
    # hairpin: two helices of 30 joined by a turn, with short ends
    h1 = _helix(30, np.array([0.0, 0, 0]), np.array([0, 0, 1.0]))
    h2 = _helix(30, np.array([9.5, 0, 43.5]), np.array([0, 0, -1.0]), phase=1.5)
    turn = _bridge(h1[-1], h2[0], 5, rng, 2.5)
    end1, end2 = _walk(4, h1[0], rng), _walk(4, h2[-1], rng)
    xyz = np.vstack([end1[::-1], h1, turn, h2, end2])
    kinds = [("l", 4), ("h", 30), ("l", 5), ("h", 30), ("l", 4)]
    prots["hairpin"] = {"xyz": xyz, "seq": _seq(kinds, rng), "regions": ["hairpin"] * len(xyz),
                        "plddt": _conf(kinds, rng, {"h": (95, 1.5), "l": (84, 4)})}
    # disordered: a floppy chain with one short helix in the middle
    a = _walk(55, np.zeros(3), rng)
    h = _helix(14, a[-1] + [3.8, 0, 0], np.array([1.0, 0.3, 0.2]))
    b = _walk(51, h[-1], rng)
    xyz = np.vstack([a, h, b])
    kinds = [("d", 55), ("h", 14), ("d", 51)]
    prots["disordered"] = {"xyz": xyz, "seq": _seq(kinds, rng), "regions": ["flexible"] * 55 + ["short helix"] * 14 + ["flexible"] * 51,
                           "plddt": _conf(kinds, rng, {"h": (68, 5), "d": (32, 7)})}
    return prots


def build(root: Path) -> Path:
    (root / "sequences").mkdir(parents=True, exist_ok=True)
    for pid, p in truth().items():
        s = p["seq"]
        (root / "sequences" / f"{pid}.fasta").write_text(f">{pid} simulated protein\n" + "\n".join(s[i:i + 60] for i in range(0, len(s), 60)) + "\n")
    return root
