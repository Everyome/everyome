**What it shows.** Reads counted per sample by nf-core/rnaseq, and the full quality report.

- Samples should have broadly similar totals. One far below the rest may have failed or been under-sequenced.
- The **MultiQC report** has every check: read quality, adapter trimming, alignment rate, strandedness and duplication.
  Look first at the alignment rate (usually above 70%) and at any sample flagged in red.
