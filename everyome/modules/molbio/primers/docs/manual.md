# Primer design

Designs PCR primers for a region of your sequence with Primer3, shows them on a
map of the sequence, checks primers you already have, and writes an order sheet.
It runs on this computer: no cluster needed.

## Getting started

1. On **Connect**, choose **This computer** (or the demo cluster).
2. Create or open a project, choose **Primer design**, and give a sequence:
   a GenBank file keeps your features on the map; FASTA or a pasted sequence
   also work. *Fill in the example* loads a small made-up demo plasmid.
3. Create the run. Everything happens straight away, in the app.

## Steps

1. **Look at the sequence.** A circular map for plasmids (a straight one for
   linear sequences), with your features and the restriction enzymes that cut
   only once. Choose the region to amplify: type its start and length, or pick
   a feature.
2. **Design primers.** Primer3 suggests pairs that flank the region, ranked by
   how well they fit your settings (lower penalty is better). Pick one to see it
   on the map.
3. **Check your own primers.** Paste a primer or a pair to get melting
   temperatures, GC content, hairpin and dimer strengths, and where they bind.
4. **Export.** All suggested pairs, an order sheet for the ones you choose, and a
   GenBank file with the primers added as features, saved in the run's
   `results/` folder.

## Settings

| Setting | Default | What it changes |
|---|---|---|
| Shortest / longest product | 100–600 bases | The size range of the PCR product. |
| Primer length | 18–25, best 20 | Longer primers are more specific but cost more. |
| Melting temperature | 57–63 °C, best 60 | Both primers of a pair should melt within a few degrees of each other. |
| GC content | 40–60 % | Very high or low GC makes primers bind poorly or non-specifically. |
| G or C at the 3' end | 1 | Helps the primer hold on where extension starts; more than 3 encourages mispriming. |
| Longest run of one base | 4 | Long runs (AAAAA) slip and misprime. |
| Salt, magnesium, dNTPs, primer concentration | 50 mM, 1.5 mM, 0.6 mM, 50 nM | Match your PCR mix; they change the calculated melting temperature. |
| Any other Primer3 setting | – | One per line as `NAME=value`. Every Primer3 setting can be used. |

## Reading the results

| Measure | Good | Worry when |
|---|---|---|
| Melting temperature (Tm) | Within 2–3 °C between the two primers | They differ by more than 5 °C. |
| Hairpin and dimer strength (ΔG) | Above about −5 kcal/mol (closer to 0) | Below about −9 kcal/mol, especially at the 3' end. |
| Dimer (Primer3's score, as a temperature) | Well below your annealing temperature | Near or above it. |
| Penalty | Low | – (it only ranks pairs against your settings) |

- **Where a primer binds** is checked against your sequence only. Check other
  templates (for example the genome) separately, for instance with Primer-BLAST.
- **Circular sequences:** Primer3 treats the sequence as running from position 1
  to the end, so it will not suggest a product that crosses the origin.

## References

- Untergasser A. et al. (2012). Primer3—new capabilities and interfaces. *Nucleic Acids Research* 40:e115. https://doi.org/10.1093/nar/gks596
- primer3-py: https://github.com/libnano/primer3-py
- Cock P.J.A. et al. (2009). Biopython. *Bioinformatics* 25:1422–1423. https://doi.org/10.1093/bioinformatics/btp163
