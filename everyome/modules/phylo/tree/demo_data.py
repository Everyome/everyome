"""Build the alignment and tree building demo: one simulated gene in 22 cnidarians and two bilaterian outgroups.

<root> = <demo cluster>/data/phylo.tree/
  sequences.fasta   unaligned DNA, as you would collect it (with insertions, deletions and one partial sequence)
  species.csv       a table about each sequence (class, whether it has a free-swimming medusa) to colour the tree
  .demo_truth/      the true tree and the true alignment (the demo's stand-in for MAFFT returns the latter)

The species are real; the sequences are not. They are simulated along a tree that follows the broad shape of
cnidarian relationships, with one very short branch (where Staurozoa joins) so that support there is weak.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import newick as nw

# Branch lengths in substitutions per site. Hexacorallia, Octocorallia; Hydrozoa, Scyphozoa, Cubozoa, Staurozoa.
HEXA = "(((Nematostella_vectensis:0.06,Exaiptasia_diaphana:0.07):0.03,Actinia_equina:0.08):0.02,(Acropora_millepora:0.05,Stylophora_pistillata:0.06):0.04):0.05"
OCTO = "((Renilla_reniformis:0.07,Dendronephthya_gigantea:0.06):0.02,Xenia_sp:0.08):0.06"
HYDRO = "(((Hydra_vulgaris:0.14,(Hydractinia_symbiolongicarpus:0.05,Podocoryna_carnea:0.04):0.04):0.03,Physalia_physalis:0.09):0.02,Clytia_hemisphaerica:0.08):0.06"
SCYPHO = "((Aurelia_aurita:0.06,(Cassiopea_xamachana:0.05,Rhopilema_esculentum:0.05):0.02):0.02,Chrysaora_fuscescens:0.06):0.04"
CUBO = "((Tripedalia_cystophora:0.05,Alatina_alata:0.06):0.02,Morbakka_virulenta:0.06):0.05"
STAURO = "(Calvadosia_cruxmelitensis:0.07,Haliclystus_octoradiatus:0.07):0.05"
# Intent: the very short branch (0.004) joining Scyphozoa and Cubozoa leaves Staurozoa's place uncertain.
TRUE_TREE = (f"((Homo_sapiens:0.22,Drosophila_melanogaster:0.30):0.12,(({HEXA},{OCTO}):0.06,"
             f"({HYDRO},(({SCYPHO},{CUBO}):0.004,{STAURO}):0.03):0.06):0.06);")

CLASS = {"Homo_sapiens": "Bilateria", "Drosophila_melanogaster": "Bilateria",
         **dict.fromkeys(["Nematostella_vectensis", "Exaiptasia_diaphana", "Actinia_equina", "Acropora_millepora", "Stylophora_pistillata",
                          "Renilla_reniformis", "Dendronephthya_gigantea", "Xenia_sp"], "Anthozoa"),
         **dict.fromkeys(["Hydra_vulgaris", "Hydractinia_symbiolongicarpus", "Podocoryna_carnea", "Physalia_physalis", "Clytia_hemisphaerica"], "Hydrozoa"),
         **dict.fromkeys(["Aurelia_aurita", "Cassiopea_xamachana", "Rhopilema_esculentum", "Chrysaora_fuscescens"], "Scyphozoa"),
         **dict.fromkeys(["Tripedalia_cystophora", "Alatina_alata", "Morbakka_virulenta"], "Cubozoa"),
         **dict.fromkeys(["Calvadosia_cruxmelitensis", "Haliclystus_octoradiatus"], "Staurozoa")}
# Intent: a trait that is not one group on the tree (medusae were lost more than once), to show the monophyly check.
MEDUSA = {"Anthozoa": "no", "Scyphozoa": "yes", "Cubozoa": "yes", "Staurozoa": "no", "Bilateria": "not a cnidarian",
          "Hydra_vulgaris": "no", "Hydractinia_symbiolongicarpus": "no", "Physalia_physalis": "no",
          "Podocoryna_carnea": "yes", "Clytia_hemisphaerica": "yes"}
OUTGROUP = ["Homo_sapiens", "Drosophila_melanogaster"]
PARTIAL = "Morbakka_virulenta"
CORE, KAPPA, ALPHA, SEED = 1050, 4.0, 0.6, 7
BASES = "AGCT"                                # A<->G and C<->T are transitions (index ^ 1)


def _evolve(rng, parent: np.ndarray, d: float, rates: np.ndarray) -> np.ndarray:
    """K80 substitutions along one branch of length d (rates scale it per site)."""
    t = d * rates
    b = 1 / (KAPPA + 2)
    e1, e2 = np.exp(-4 * b * t), np.exp(-2 * (KAPPA * b + b) * t)
    p_ts, p_tv = 0.25 + 0.25 * e1 - 0.5 * e2, 0.25 - 0.25 * e1      # p_tv is for each of the two transversions
    u = rng.random(len(parent))
    out = parent.copy()
    ts = u < p_ts
    tv1 = (u >= p_ts) & (u < p_ts + p_tv)
    tv2 = (u >= p_ts + p_tv) & (u < p_ts + 2 * p_tv)
    out[ts] ^= 1
    out[tv1] ^= 2
    out[tv2] ^= 3
    return out


def simulate() -> dict:
    rng = np.random.default_rng(SEED)
    tree = nw.parse(TRUE_TREE)
    # Insertions (columns only one group has) and deletions (columns one group lost), in whole codons.
    events = [("ins", ["Hydra_vulgaris"], 9), ("ins", ["Aurelia_aurita", "Cassiopea_xamachana", "Rhopilema_esculentum", "Chrysaora_fuscescens"], 12),
              ("ins", ["Homo_sapiens", "Drosophila_melanogaster"], 6), ("ins", ["Nematostella_vectensis", "Exaiptasia_diaphana"], 3),
              ("del", ["Hydractinia_symbiolongicarpus", "Podocoryna_carnea"], 6), ("del", ["Acropora_millepora", "Stylophora_pistillata"], 9),
              ("del", ["Drosophila_melanogaster"], 15), ("del", ["Tripedalia_cystophora", "Alatina_alata", "Morbakka_virulenta"], 3),
              ("del", ["Renilla_reniformis"], 6)]
    total = CORE + sum(k for e, _, k in events if e == "ins")
    rates = rng.gamma(ALPHA, 1 / ALPHA, total)
    seqs = {}
    root = rng.integers(0, 4, total)
    stack = [(tree, root)]
    while stack:
        n, s = stack.pop()
        if n.is_tip:
            seqs[n.name] = s
        for c in n.children:
            stack.append((c, _evolve(rng, s, c.length or 0.0, rates)))
    names = tree.tips()
    present = {n: np.ones(total, bool) for n in names}
    ins_at = sorted(rng.choice(np.arange(60, CORE - 60, 3), sum(e == "ins" for e, _, _ in events), replace=False))
    # Lay the insertion columns into the core at their positions: build the column order.
    order, k, ins_cols = [], 0, []
    pos = list(range(CORE))
    extra = CORE
    for (e, who, size), at in zip([x for x in events if x[0] == "ins"], ins_at):
        ins_cols.append((at, list(range(extra, extra + size)), who))
        extra += size
    for p in pos:
        order.append(p)
        for at, cols, who in ins_cols:
            if at == p:
                order.extend(cols)
                for n in names:
                    if n not in who:
                        present[n][cols] = False
    for e, who, size in events:
        if e == "del":
            at = int(rng.choice(np.arange(60, CORE - 60, 3)))
            for n in who:
                present[n][at:at + size] = False
    # The partial sequence covers only the middle of the gene (for example, a fragment from a transcriptome).
    present[PARTIAL][:int(CORE * 0.42)] = False
    present[PARTIAL][int(CORE * 0.78):CORE] = False
    order = np.array(order)
    aln = {n: "".join(BASES[b] if ok else "-" for b, ok in zip(seqs[n][order], present[n][order])) for n in names}
    # Intent: drop columns that are gaps in every sequence (they carry nothing), as an aligner would.
    keep = [i for i in range(len(order)) if any(aln[n][i] != "-" for n in names)]
    aln = {n: "".join(s[i] for i in keep) for n, s in aln.items()}
    return {"tree": TRUE_TREE, "alignment": aln}


def build(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    sim = simulate()
    truth = root / ".demo_truth"
    truth.mkdir(exist_ok=True)
    order = list(sim["alignment"])
    (truth / "true_tree.nwk").write_text(sim["tree"] + "\n")
    (truth / "true_alignment.fasta").write_text("".join(f">{n}\n{sim['alignment'][n]}\n" for n in order))
    # Headers as they often come: a name, then a description (Everyome keeps the first word as the tip name).
    (root / "sequences.fasta").write_text("".join(
        f">{n} simulated gene {'(partial)' if n == PARTIAL else ''}\n".replace(" \n", "\n") +
        "\n".join(s[i:i + 70] for i in range(0, len(s), 70)) + "\n"
        for n in order for s in [sim["alignment"][n].replace("-", "")]))
    rows = ["name,class,free_swimming_medusa"] + [f"{n},{CLASS[n]},{MEDUSA[n] if n in MEDUSA else MEDUSA[CLASS[n]]}" for n in order]
    (root / "species.csv").write_text("\n".join(rows) + "\n")
    (truth / "truth.json").write_text(json.dumps({"outgroup": OUTGROUP, "classes": CLASS, "partial": PARTIAL}, indent=1))
    return root
