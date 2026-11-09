# qPCR analysis

Turns the results table from your qPCR instrument into relative expression: it checks replicates and controls,
works out primer efficiencies, helps you choose reference genes, and gives fold changes between groups. It runs on
this computer: no cluster needed.

## Getting started

1. On **Connect**, choose **This computer** (or the demo cluster).
2. Create or open a project, choose **qPCR analysis**, and give the results file exported from your instrument.
   *Fill in the example* loads a made-up 384-well plate with known answers.
3. Create the run. Everything happens straight away, in the app.

## What the results file needs

A table (CSV, tab-separated text or Excel) with one row per well and columns for:

| Column | Also recognised as |
|---|---|
| Well | Well Position, Pos |
| Sample | Sample Name, Name |
| Target (gene) | Target Name, Detector, Gene, Assay |
| Cq | Ct, Cp, CRT |
| Task (optional) | Content, Type: *unknown*, *standard* or *NTC* |
| Quantity (optional) | Starting Quantity (SQ), for standards |

Run details above the table, as QuantStudio and Bio-Rad CFX exports have, are skipped. Wells with *Undetermined*
or no Cq count as no amplification. Without a task column, wells with a quantity are standards and samples named
NTC or water are no-template controls.

Name biological replicates so their group can be guessed (`control_1`, `control_2`, `treated_1` …); you can change
the groups in the session.

## Steps

1. **Check the plate.** The plate coloured by Cq, technical replicates that spread too far, and the no-template
   controls. Click a well to leave it out.
2. **Primer efficiency.** Standard curves for each target, with slope, R² and efficiency.
3. **Reference genes and groups.** geNorm ranks every target by how steady it is; choose the references, and check
   each sample's group and the control group.
4. **Fold changes.** Each target in each group against the control, with 95% confidence intervals and p-values.
5. **Export.** Tables of fold changes, normalised expression, efficiencies and replicates.

Then **Record** gives a methods paragraph with the settings and the wells you left out.

## How it calculates

- Technical replicates are averaged (after the wells you left out).
- Efficiency E = 10^(−1/slope) − 1 from a standard curve with three or more dilutions; otherwise the efficiency in
  the settings (100% by default).
- Relative quantity of a target in a sample: (1 + E)^(mean Cq of that target − Cq in the sample), normalised to the
  geometric mean of the reference genes' relative quantities (Hellemans et al., 2007; Pfaffl, 2001).
- Fold change: against the mean of the control group on a log2 scale. Groups are compared with Welch's t-test on
  log2 values; p-values are adjusted across targets with Benjamini–Hochberg.
- Choosing *delta_delta_cq* in the settings assumes every pair is 100% efficient (Livak & Schmittgen, 2001).

## Good practice

Follow the MIQE guidelines (Bustin et al., 2009): report primer efficiencies, the reference genes and how they were
validated, the number of biological and technical replicates, and how outliers were handled. The methods text from
**Record** covers the analysis; add the wet-lab details yourself.

## References

- Hellemans J. et al. (2007). Genome Biology 8:R19. https://doi.org/10.1186/gb-2007-8-2-r19
- Vandesompele J. et al. (2002). Genome Biology 3:research0034. https://doi.org/10.1186/gb-2002-3-7-research0034
- Pfaffl M.W. (2001). Nucleic Acids Research 29:e45. https://doi.org/10.1093/nar/29.9.e45
- Livak K.J. & Schmittgen T.D. (2001). Methods 25:402–408. https://doi.org/10.1006/meth.2001.1262
- Bustin S.A. et al. (2009). Clinical Chemistry 55:611–622. https://doi.org/10.1373/clinchem.2008.112797
