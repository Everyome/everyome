"""Stand-ins for MAFFT, trimAl and IQ-TREE on the demo cluster, where the real tools are not installed.

They write the same files the real tools write, so the live session behaves exactly as after a real run:
- align: the demo's true alignment (MAFFT would find nearly the same one);
- trim: keeps columns that enough sequences have letters in (trimAl's methods are cleverer);
- tree: a neighbour-joining tree on Kimura two-parameter distances, with ordinary bootstrap support standing in
  for both SH-aLRT and UFBoot, and a short report in IQ-TREE's layout. Its model table is illustrative.
Never used on a real cluster.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

from . import newick as nw
from .stage import read_fasta, write_fasta

KEEP = {"automated1": 0.7, "gappyout": 0.7, "strict": 0.9, "strictplus": 0.95}
CODE = {c: i for i, c in enumerate("AGCT")}


def _pause():
    time.sleep(float(os.environ.get("EVERYOME_DEMO_PAUSE", "1")))


def align(res: Path, src: Path) -> None:
    _pause()
    truth = src.parent / ".demo_truth" / "true_alignment.fasta"
    have = dict(read_fasta(res / "sequences.fasta"))
    true = dict(read_fasta(truth)) if truth.exists() else {}
    if set(true) == set(have) and all(true[n].replace("-", "") == have[n] for n in have):
        write_fasta(res / "alignment.fasta", [(n, true[n]) for n in have])
    else:
        # Not the demo's own sequences: pad them to one length (not a real alignment; the demo has no aligner).
        w = max(len(s) for s in have.values())
        write_fasta(res / "alignment.fasta", [(n, s.ljust(w, "-")) for n, s in have.items()])
    print("Demo stand-in for MAFFT: wrote alignment.fasta", flush=True)


def trim(res: Path, method: str, min_present: float) -> None:
    _pause()
    recs = read_fasta(res / "alignment.fasta")
    share = KEEP.get(method, min_present)
    n, width = len(recs), len(recs[0][1])
    keep = [i for i in range(width) if sum(s[i] not in "-?." for _, s in recs) / n >= share]
    write_fasta(res / "trimmed.fasta", [(name, "".join(s[i] for i in keep)) for name, s in recs])
    (res / "trim_columns.txt").write_text("#ColumnsMap\t" + ", ".join(map(str, keep)) + "\n")
    print(f"Demo stand-in for trimAl: kept {len(keep)} of {width} columns", flush=True)


def _k2p(X: np.ndarray) -> np.ndarray:
    """Kimura two-parameter distances between rows of X (codes 0-3, -1 for a gap), ignoring gaps pair by pair."""
    n = len(X)
    D = np.zeros((n, n))
    for i in range(n):
        ok = (X[i] >= 0) & (X >= 0)
        diff = (X[i] != X) & ok
        ts = diff & ((X[i] ^ X) == 1)
        sites = np.maximum(ok.sum(1), 1)
        P, Q = ts.sum(1) / sites, (diff.sum(1) - ts.sum(1)) / sites
        with np.errstate(divide="ignore", invalid="ignore"):
            d = -0.5 * np.log(np.clip(1 - 2 * P - Q, 1e-6, None)) - 0.25 * np.log(np.clip(1 - 2 * Q, 1e-6, None))
        D[i] = np.nan_to_num(d, nan=3.0)
    np.fill_diagonal(D, 0)
    return (D + D.T) / 2


def _nj(D: np.ndarray, names: list[str]) -> nw.Node:
    nodes = [nw.Node(name=x) for x in names]
    D = D.copy()
    while len(nodes) > 3:
        n = len(nodes)
        r = D.sum(1)
        Q = (n - 2) * D - r[:, None] - r[None, :]
        np.fill_diagonal(Q, np.inf)
        i, j = np.unravel_index(np.argmin(Q), Q.shape)
        li = max(0.5 * D[i, j] + (r[i] - r[j]) / (2 * (n - 2)), 0.0)
        a, b = nodes[i], nodes[j]
        a.length, b.length = li, max(D[i, j] - li, 0.0)
        u = nw.Node(children=[a, b])
        a.parent = b.parent = u
        du = 0.5 * (D[i] + D[j] - D[i, j])
        keep = [k for k in range(n) if k not in (i, j)]
        D = np.vstack([np.hstack([D[np.ix_(keep, keep)], du[keep][:, None]]), np.append(du[keep], 0)])
        nodes = [nodes[k] for k in keep] + [u]
    # The last three join at an unrooted centre, as IQ-TREE writes its trees.
    a, b, c = nodes
    la = max((D[0, 1] + D[0, 2] - D[1, 2]) / 2, 0.0)
    lb, lc = max(D[0, 1] - la, 0.0), max(D[0, 2] - la, 0.0)
    root = nw.Node(children=[a, b, c])
    for x, ln in zip((a, b, c), (la, lb, lc)):
        x.parent, x.length = root, ln
    return root


def _splits(t: nw.Node, every: frozenset) -> set[frozenset]:
    """Each inner branch as the side of the split without the first tip, so splits compare across rootings."""
    first = sorted(every)[0]
    out = set()
    for n in t.walk():
        if n is t or n.is_tip:
            continue
        s = frozenset(n.tips())
        s = every - s if first in s else s
        if 1 < len(s) < len(every) - 1:
            out.add(s)
    return out


def tree(res: Path, kind: str, model: str, boot: int, alrt: int, seed: int, outgroup: list[str]) -> None:
    _pause()
    recs = read_fasta(res / "trimmed.fasta")
    names = [n for n, _ in recs]
    X = np.array([[CODE.get(c, -1) for c in s.upper()] for _, s in recs], dtype=np.int16)
    t = _nj(_k2p(X), names)
    every = frozenset(names)
    rng = np.random.default_rng(seed)
    # Intent: two independent sets of ordinary bootstrap replicates stand in for SH-aLRT and UFBoot.
    reps = {k: min(n, 100) for k, n in (("alrt", alrt), ("ufboot", boot)) if n}
    counts = {k: {} for k in reps}
    for k, n in reps.items():
        for _ in range(n):
            cols = rng.integers(0, X.shape[1], X.shape[1])
            for s in _splits(_nj(_k2p(X[:, cols]), names), every):
                counts[k][s] = counts[k].get(s, 0) + 1
    first = sorted(every)[0]
    for node in t.walk():
        if node is t or node.is_tip:
            continue
        s = frozenset(node.tips())
        s = every - s if first in s else s
        vals = [f"{100 * counts[k].get(s, 0) / reps[k]:.0f}" for k in ("alrt", "ufboot") if k in reps]
        node.label = "/".join(vals)
    if outgroup and nw.find_clade(t, set(outgroup)) is None:
        # Intent: as IQ-TREE does, warn but still write the (unrooted) tree; the live session roots it.
        print(f"Warning: the outgroup {', '.join(outgroup)} does not form one group on this tree.", flush=True)
    (res / "tree.treefile").write_text(nw.write(t) + "\n")
    _report(res, recs, kind, model, t)
    (res / "tree.log").write_text("Demo stand-in for IQ-TREE (neighbour joining with bootstrap).\n")
    print(f"Demo stand-in for IQ-TREE: tree of {len(names)} sequences written to tree.treefile", flush=True)


def _report(res: Path, recs, kind: str, model: str, t: nw.Node) -> None:
    cols = list(zip(*[s.upper() for _, s in recs]))
    letters = [set(c) - set("-?.N") for c in cols]
    const = sum(len(x) <= 1 for x in letters)
    informative = sum(sum(1 for b in set(c) - set("-?.N") if c.count(b) >= 2) >= 2 for c in cols)
    sites, n = len(cols), len(recs)
    length = sum((x.length or 0) for x in t.walk() if x is not t)
    unit = "nucleotide" if kind == "dna" else "amino-acid"
    L = ["IQ-TREE 3 stand-in on the Everyome demo cluster (neighbour joining; not IQ-TREE)", "",
         f"Input data: {n} sequences with {sites} {unit} sites",
         f"Number of constant sites: {const} (= {100 * const / sites:.4f}% of all sites)",
         f"Number of parsimony informative sites: {informative}", ""]
    base = -3.1 * informative - 0.9 * (sites - informative) - 40 * n
    if model.upper().startswith("MF") or model.upper() == "TEST":
        # Illustrative numbers in ModelFinder's layout: richer models fit a little better and cost parameters.
        table = [("K2P+G4", 0, 2), ("HKY+F+G4", 3, 5), ("TNe+G4", 1.5, 3), ("K2P+I+G4", 0.8, 3), ("TIM2+F+G4", 4, 7),
                 ("GTR+F+G4", 5, 9), ("JC+G4", -35, 1), ("K2P+I", -120, 2), ("K2P", -260, 1)]
        best = []
        for name, gain, k in table:
            ll = base + gain
            npar = 2 * n - 3 + k
            best.append((name, ll, 2 * npar - 2 * ll, 2 * npar - 2 * ll + 2 * npar * (npar + 1) / max(sites - npar - 1, 1), npar * np.log(sites) - 2 * ll))
        best.sort(key=lambda r: r[4])
        w = lambda i: np.exp(-0.5 * (np.array([r[i] for r in best]) - min(r[i] for r in best)))
        wa, wc, wb = (x / x.sum() for x in (w(2), w(3), w(4)))
        L += ["ModelFinder", "-----------", "", f"Best-fit model according to BIC: {best[0][0]}", "",
              "List of models sorted by BIC scores: ", "",
              "Model                  LogL         AIC      w-AIC        AICc     w-AICc         BIC      w-BIC"]
        L += [f"{r[0]:<16}{r[1]:>12.3f}{r[2]:>12.3f} + {wa[i]:>8.3g}{r[3]:>12.3f} + {wc[i]:>8.3g}{r[4]:>12.3f} + {wb[i]:>8.3g}" for i, r in enumerate(best)]
        L += ["", "AIC, w-AIC   : Akaike information criterion scores and weights.", ""]
        model = best[0][0]
    L += ["SUBSTITUTION PROCESS", "--------------------", "", f"Model of substitution: {model}", "",
          "MAXIMUM LIKELIHOOD TREE", "-----------------------", "",
          f"Log-likelihood of the tree: {base:.4f} (s.e. 120.0000)",
          f"Total tree length (sum of branch lengths): {length:.4f}", ""]
    (res / "tree.iqtree").write_text("\n".join(L) + "\n")
