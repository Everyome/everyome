"""Demo data for protein function annotation: ten made-up proteins with familiar domains placed in them, and the
matches InterProScan reports for such domains (Pfam signatures and their InterPro entries and GO terms, as published
in InterPro), which the demo stand-in writes for them. Two proteins have no known domain, as in any real genome.

<root>/proteins.faa
<root>/.demo_truth/matches.json   per protein: [database, accession, description, start, end, InterPro, InterPro name, GO]
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# Pfam signature: (description, InterPro entry, InterPro name, GO terms, length)
SIG = {
    "PF00069": ("Protein kinase domain", "IPR000719", "Protein kinase domain", "GO:0004672|GO:0005524|GO:0006468", 260),
    "PF00018": ("SH3 domain", "IPR001452", "SH3 domain", "", 50),
    "PF00076": ("RNA recognition motif. (a.k.a. RRM, RBD, or RNP domain)", "IPR000504", "RNA recognition motif domain", "GO:0003676", 70),
    "PF00071": ("Ras family", "IPR001806", "Small GTPase", "GO:0003924|GO:0005525", 160),
    "PF00001": ("7 transmembrane receptor (rhodopsin family)", "IPR000276", "G protein-coupled receptor, rhodopsin-like",
                "GO:0004930|GO:0007186|GO:0016020", 260),
    "PF00096": ("Zinc finger, C2H2 type", "IPR013087", "Zinc finger C2H2-type", "", 23),
    "PF00046": ("Homeodomain", "IPR001356", "Homeodomain", "GO:0003677|GO:0006355", 57),
    "PF00560": ("Leucine Rich Repeat", "IPR001611", "Leucine-rich repeat", "GO:0005515", 22),
}
# GO terms used above: (name, category), as named in the Gene Ontology.
GO = {"GO:0004672": ("protein kinase activity", "MOLECULAR_FUNCTION"), "GO:0005524": ("ATP binding", "MOLECULAR_FUNCTION"),
      "GO:0006468": ("protein phosphorylation", "BIOLOGICAL_PROCESS"), "GO:0003676": ("nucleic acid binding", "MOLECULAR_FUNCTION"),
      "GO:0003924": ("GTPase activity", "MOLECULAR_FUNCTION"), "GO:0005525": ("GTP binding", "MOLECULAR_FUNCTION"),
      "GO:0004930": ("G protein-coupled receptor activity", "MOLECULAR_FUNCTION"),
      "GO:0007186": ("G protein-coupled receptor signaling pathway", "BIOLOGICAL_PROCESS"), "GO:0016020": ("membrane", "CELLULAR_COMPONENT"),
      "GO:0003677": ("DNA binding", "MOLECULAR_FUNCTION"), "GO:0006355": ("regulation of DNA-templated transcription", "BIOLOGICAL_PROCESS"),
      "GO:0005515": ("protein binding", "MOLECULAR_FUNCTION")}
# protein: (length, [(signature, start), ...])
PROTEINS = {
    "nvKin1": (420, [("PF00069", 60)]),
    "nvKinSH3": (520, [("PF00018", 20), ("PF00069", 180)]),
    "nvRbp1": (300, [("PF00076", 30), ("PF00076", 150)]),
    "nvRas1": (190, [("PF00071", 8)]),
    "nvOps1": (360, [("PF00001", 40)]),
    "nvZnf1": (280, [("PF00096", 120), ("PF00096", 148), ("PF00096", 176), ("PF00096", 204)]),
    "nvHox1": (240, [("PF00046", 150)]),
    "nvLrr1": (330, [("PF00560", 60), ("PF00560", 84), ("PF00560", 108), ("PF00560", 132), ("PF00560", 156)]),
    "nvUnk1": (210, []),
    "nvUnk2": (150, []),
}


def matches() -> dict:
    out = {}
    for pid, (n, doms) in PROTEINS.items():
        out[pid] = [["Pfam", s, SIG[s][0], start, start + SIG[s][4] - 1, SIG[s][1], SIG[s][2], SIG[s][3]] for s, start in doms]
    return out


def build(root: Path):
    rng = np.random.default_rng(51)
    root.mkdir(parents=True, exist_ok=True)
    aa = list("ACDEFGHIKLMNPQRSTVWY")
    lines = []
    for pid, (n, _) in PROTEINS.items():
        seq = "M" + "".join(rng.choice(aa, n - 1))
        lines.append(f">{pid} demo protein\n" + "\n".join(seq[i:i + 60] for i in range(0, n, 60)))
    (root / "proteins.faa").write_text("\n".join(lines) + "\n")
    t = root / ".demo_truth"
    t.mkdir(exist_ok=True)
    (t / "matches.json").write_text(json.dumps(matches()))
