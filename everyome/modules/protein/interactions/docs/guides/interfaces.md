**What it shows.** For each pair of chains in each predicted complex:

- **Contacts**: residue pairs closer than 8 Å across the interface (Cα atoms). A real interface usually has dozens.
- **Interface pLDDT**: the predictor's confidence in the residues that touch.
- **Interface PAE**: the predicted error in placing one chain's interface residues relative to the other's; below
  about 10 Å means the arrangement itself is trusted.
- **ipTM**: AlphaFold-Multimer's score for the whole interface; above about 0.8 is usually right, below about 0.6
  usually wrong.
- **pDockQ**: a score built from the contacts and their pLDDT (Bryant et al., 2022); above 0.5 is likely correct, below
  0.23 likely not.
- **Reading** combines them. "Uncertain" is common, and honest: it means look at the structure and test it.

A confident predicted interface is a hypothesis, not proof of binding. A low score doesn't rule binding out either:
the proteins may bind only with a partner, a modification or in another arrangement.
