"""Interface measures for a predicted complex: which residues touch across each pair of chains, how confident the
predictor is there, and pDockQ, a score for whether the chains really bind.

Contacts use Cα atoms within 8 Å (pDockQ was defined on Cβ; Cα is what every method writes, and gives similar
numbers). pDockQ: Bryant, Pozzati and Elofsson (2022), https://doi.org/10.1038/s41467-022-28865-w.
"""
from __future__ import annotations

import math

import numpy as np

CONTACT = 8.0


def contacts(xyz: np.ndarray, chains: list[str], a: str, b: str, cutoff: float = CONTACT) -> list[tuple[int, int]]:
    """Index pairs (i in chain a, j in chain b) closer than the cutoff."""
    ia = np.where(np.array(chains) == a)[0]
    ib = np.where(np.array(chains) == b)[0]
    if not len(ia) or not len(ib):
        return []
    d = np.linalg.norm(xyz[ia][:, None, :] - xyz[ib][None, :, :], axis=2)
    ii, jj = np.where(d < cutoff)
    return [(int(ia[i]), int(ib[j])) for i, j in zip(ii, jj)]


def pdockq(plddt: np.ndarray, pairs: list[tuple[int, int]]) -> float:
    """pDockQ from the interface's mean pLDDT and its number of contacts; 0.02 when there is no interface."""
    if not pairs:
        return 0.018
    residues = sorted({i for i, _ in pairs} | {j for _, j in pairs})
    x = float(np.mean(plddt[residues])) * math.log10(len(pairs))
    return round(0.724 / (1 + math.exp(-0.052 * (x - 152.611))) + 0.018, 3)


def interface_pae(pae: np.ndarray | None, pairs: list[tuple[int, int]]) -> float | None:
    """Mean predicted aligned error between contacting residues, both ways (lower: their placement is trusted)."""
    if pae is None or not pairs:
        return None
    i, j = np.array(pairs).T
    return round(float((pae[i, j] + pae[j, i]).mean() / 2), 1)


def describe(xyz: np.ndarray, chains: list[str], plddt: np.ndarray, pae: np.ndarray | None) -> list[dict]:
    """Every pair of chains: contacts, residues at the interface on each side, interface pLDDT, PAE and pDockQ."""
    names = list(dict.fromkeys(chains))
    out = []
    for x in range(len(names)):
        for y in range(x + 1, len(names)):
            a, b = names[x], names[y]
            pairs = contacts(xyz, chains, a, b)
            ra, rb = sorted({i for i, _ in pairs}), sorted({j for _, j in pairs})
            out.append({"a": a, "b": b, "contacts": len(pairs), "residues_a": len(ra), "residues_b": len(rb),
                        "interface_plddt": round(float(np.mean(plddt[ra + rb])), 1) if pairs else None,
                        "interface_pae": interface_pae(pae, pairs), "pdockq": pdockq(plddt, pairs),
                        "index_a": ra, "index_b": rb})
    return out


def verdict(pdq: float, iptm: float | None) -> str:
    """Plain-language reading of the scores (thresholds from the pDockQ and AlphaFold-Multimer papers)."""
    good = (pdq >= 0.5) or (iptm is not None and iptm >= 0.8)
    poor = (pdq < 0.23) and (iptm is None or iptm < 0.6)
    return "likely binds as predicted" if good else "unlikely to bind as predicted" if poor else "uncertain"
