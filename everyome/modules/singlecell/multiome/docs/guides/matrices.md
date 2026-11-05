**What happens.** Cell Ranger ARC writes one matrix per sample with two kinds of feature for the same cells: **genes**
(RNA counts) and **peaks** (open-chromatin regions it called). Everyome reads both, keeps the RNA as the main table and
the peaks beside it.

- Cells with very little ATAC signal are left out here; nuclei with good RNA but almost no chromatin signal can't be
  placed by their chromatin.
- ARC already removes most empty droplets; the next step sets thresholds on the RNA.
