**What it shows.** A model of evolution says how often each letter changes into each other one, and how much
that rate differs between positions. ModelFinder fits many models and picks the one with the best **BIC**,
which rewards fit but charges for every extra parameter.

- Names are built from parts: `GTR`, `HKY`, `K2P` (DNA) or `LG`, `WAG` (protein) for the changes; `+F` uses the
  letter frequencies from your data; `+I` allows a share of positions that never change; `+G4` lets rates vary
  between positions (four rate categories).
- **BIC weight** is how strongly the data prefer each model. Several models with similar weight usually give
  the same tree.
