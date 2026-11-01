**Which matrix to start from.**

- **CellBender**: empty droplets and ambient RNA removed. Best for most experiments.
- **Called by the aligner**: the aligner's own cell calling (for example Cell Ranger's). Use it if CellBender was skipped.
- **Every barcode**: includes empty droplets. Only for checking cell calling yourself: set a firm minimum UMI threshold in the next step.
