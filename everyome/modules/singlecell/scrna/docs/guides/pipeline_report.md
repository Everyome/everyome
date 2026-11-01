**What it shows.** The matrices nf-core/scrnaseq made, and its full quality report.

- **CellBender** removes empty droplets and the background ("ambient") RNA that leaks into every droplet. Start from its matrix unless you have a reason not to.
- In the **MultiQC report**, look first at the share of reads with a valid cell barcode (usually above 85%) and the share mapped to genes (usually above 60%). A sample far below the others may have a chemistry or reference problem.
