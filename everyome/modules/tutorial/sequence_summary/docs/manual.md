# Sequence summary

A small tutorial module. It takes a FASTA file, counts the sequences, measures
their lengths and GC content, and lets you explore and filter them. Use it to
learn how every Everyome module works before you run a real analysis.

## What happens

1. **Read the sequences and measure their lengths** (cluster job). Sequences
   shorter than *Shortest sequence kept* are left out.
2. **Work out the GC content of each sequence** (cluster job). GC content is the
   fraction of bases that are G or C.
3. **Explore and filter** (live session). Look at the spread of GC content,
   choose a range to keep, and export the filtered table.

## Settings

| Setting | Default | What it changes |
|---|---|---|
| Shortest sequence kept | 50 | Sequences below this length are left out of everything after stage 1. |
| Count N bases in GC content | Off | When on, unknown bases (N) count towards the total, which lowers GC for sequences with many Ns. |
| Decimal places for GC | 3 | Rounding in the results table only. |

## Reading the results

- **GC histogram.** Most genomes have a characteristic GC content; a second
  peak can mean contamination or a mix of organisms.
- **Very short sequences** give unreliable GC values, which is why short ones
  are left out by default.

## Outputs

| File | Contents |
|---|---|
| `results/lengths.tsv` | id, length for every sequence kept |
| `results/gc.tsv` | id, length, GC fraction |
| `results/gc_filtered.tsv` | the same, only for sequences inside your chosen GC range |
