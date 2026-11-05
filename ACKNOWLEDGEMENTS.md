# Acknowledgements

Everyome stands on a great deal of other people's work. This page says what is whose, thanks the people behind it,
and lists the references to cite for the parts of Everyome you use. Each analysis also writes its own methods
section, with the references for exactly the tools it ran.

## What Everyome brings together

Everyome is a way in to analyses, not a replacement for the tools behind them. It gives one place to set up, run
and read two kinds of work:

- **Helen R Horkan's own analyses**, starting with SPLiTscape (SPLiT-seq reads to annotated cell types).
- **Pipelines and tools written by other people**, such as the nf-core pipelines and the programs listed below.
  Everyome runs them as their authors released them, pinned to a version and under their own licences; it sets
  them up, submits them and helps you read the results. The credit for them belongs to their authors, so please
  cite them as well as Everyome.

## People

- **Helen R Horkan PhD** (Stowers Institute for Medical Research) created and wrote Everyome and SPLiTscape: the
  idea, the scientific design, the analysis scripts, the app, the house styles and the logo.

## Institution

- **Stowers Institute for Medical Research**, Helen R Horkan's institution.

## Tools used to build it

Helen used **Claude**, Anthropic's AI assistant (through Claude Code and Claude Cowork), as a coding assistant
while building Everyome: to help draft and check code, documentation, tests and the logo's design files. She
reviewed and tested what it produced, and the decisions about the science, the design and what Everyome does are
hers.

- Anthropic (2026). Claude (Claude Opus models). https://www.anthropic.com/claude
- Anthropic (2026). Claude Code. https://claude.com/claude-code

## Workflows, pipelines and containers

- **nf-core**: Ewels P.A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines.
  *Nature Biotechnology* 38:276–278. https://doi.org/10.1038/s41587-020-0439-x
- **Nextflow**: Di Tommaso P. et al. (2017). Nextflow enables reproducible computational workflows.
  *Nature Biotechnology* 35:316–319. https://doi.org/10.1038/nbt.3820
- **nf-schema** (Nextflow plugin, Apache 2.0). https://github.com/nextflow-io/nf-schema
- The nf-core pipelines Everyome ships (each MIT-licensed, © its nf-core team):
  - nf-core/rnaseq: https://doi.org/10.5281/zenodo.1400710
  - nf-core/scrnaseq: https://doi.org/10.5281/zenodo.3568187
  - nf-core/genomeassembler: https://doi.org/10.5281/zenodo.14986998
  - nf-core/bacass: https://doi.org/10.5281/zenodo.2669428
  - nf-core/proteinfold: https://doi.org/10.5281/zenodo.7629996
- **Apptainer / Singularity**: Kurtzer G.M., Sochat V., Bauer M.W. (2017). Singularity: scientific containers for
  mobility of compute. *PLoS ONE* 12:e0177459. https://doi.org/10.1371/journal.pone.0177459
- **BioContainers**: da Veiga Leprevost F. et al. (2017). BioContainers: an open-source and community-driven
  framework for software standardization. *Bioinformatics* 33:2580–2582. https://doi.org/10.1093/bioinformatics/btx192
- **Seqera Containers** (images built by Wave, used by nf-core pipelines). https://seqera.io/containers/

## Tools the analyses run

### DNA

- Kolmogorov M. et al. (2019). Flye. *Nature Biotechnology* 37:540–546. https://doi.org/10.1038/s41587-019-0072-8
- Cheng H. et al. (2021). hifiasm. *Nature Methods* 18:170–175. https://doi.org/10.1038/s41592-020-01056-5
- Alonge M. et al. (2022). RagTag. *Genome Biology* 23:258. https://doi.org/10.1186/s13059-022-02823-7
- Walker B.J. et al. (2014). Pilon. *PLoS ONE* 9:e112963. https://doi.org/10.1371/journal.pone.0112963
- Shumate A., Salzberg S.L. (2021). Liftoff. *Bioinformatics* 37:1639–1643. https://doi.org/10.1093/bioinformatics/btaa1016
- Manni M. et al. (2021). BUSCO. *Molecular Biology and Evolution* 38:4647–4654. https://doi.org/10.1093/molbev/msab199
- Gurevich A. et al. (2013). QUAST. *Bioinformatics* 29:1072–1075. https://doi.org/10.1093/bioinformatics/btt086
- Wick R.R. et al. (2017). Unicycler. *PLoS Computational Biology* 13:e1005595. https://doi.org/10.1371/journal.pcbi.1005595
- Seemann T. (2014). Prokka. *Bioinformatics* 30:2068–2069. https://doi.org/10.1093/bioinformatics/btu153
- Schwengers O. et al. (2021). Bakta. *Microbial Genomics* 7:000685. https://doi.org/10.1099/mgen.0.000685

### RNA

- Love M.I., Huber W., Anders S. (2014). DESeq2. *Genome Biology* 15:550. https://doi.org/10.1186/s13059-014-0550-8
- Muzellec B. et al. (2023). PyDESeq2. *Bioinformatics* 39:btad547. https://doi.org/10.1093/bioinformatics/btad547
- Patro R. et al. (2017). Salmon. *Nature Methods* 14:417–419. https://doi.org/10.1038/nmeth.4197
- Wagner G.P., Kin K., Lynch V.J. (2012). Measurement of mRNA abundance using RNA-seq data (TPM). *Theory in Biosciences* 131:281–285. https://doi.org/10.1007/s12064-012-0162-3

### Single cell and spatial

- Bredikhin D., Kats I., Stegle O. (2022). MUON. *Genome Biology* 23:42. https://doi.org/10.1186/s13059-021-02577-8
- Hao Y. et al. (2021). Integrated analysis of multimodal single-cell data (weighted nearest neighbours). *Cell* 184:3573–3587. https://doi.org/10.1016/j.cell.2021.04.048
- Cusanovich D.A. et al. (2015). TF-IDF and LSI for single-cell ATAC. *Science* 348:910–914. https://doi.org/10.1126/science.aab1601
- Zhang K. et al. (2024). SnapATAC2. *Nature Methods* 21:217–227. https://doi.org/10.1038/s41592-023-02139-9
- Zhang H. et al. (2021). Chromap. *Nature Communications* 12:6566. https://doi.org/10.1038/s41467-021-26865-w
- Buenrostro J.D. et al. (2015). Single-cell chromatin accessibility. *Nature* 523:486–490. https://doi.org/10.1038/nature14590
- Wolf F.A., Angerer P., Theis F.J. (2018). Scanpy. *Genome Biology* 19:15. https://doi.org/10.1186/s13059-017-1382-0
- Virshup I. et al. (2024). anndata: access and store annotated data matrices. *Journal of Open Source Software*
  9:4371. https://doi.org/10.21105/joss.04371
- Korsunsky I. et al. (2019). Harmony. *Nature Methods* 16:1289–1296. https://doi.org/10.1038/s41592-019-0619-0
- Traag V.A., Waltman L., van Eck N.J. (2019). Leiden. *Scientific Reports* 9:5233. https://doi.org/10.1038/s41598-019-41695-z
- igraph: Csárdi G., Nepusz T. (2006). The igraph software package for complex network research. *InterJournal*
  Complex Systems 1695. https://igraph.org
- McInnes L., Healy J., Melville J. (2018). UMAP. arXiv:1802.03426. https://arxiv.org/abs/1802.03426
- He D. et al. (2022). Alevin-fry. *Nature Methods* 19:316–322. https://doi.org/10.1038/s41592-022-01408-3
- Fleming S.J. et al. (2023). CellBender. *Nature Methods* 20:1323–1335. https://doi.org/10.1038/s41592-023-01943-7
- Rosenberg A.B. et al. (2018). SPLiT-seq. *Science* 360:176–182. https://doi.org/10.1126/science.aam8999
- Split-seq toolbox (Rebekka Wegmann, MIT). https://github.com/RebekkaWegmann/splitseq_toolbox
- Drop-seq tools (Broad Institute, MIT): Macosko E.Z. et al. (2015). *Cell* 161:1202–1214.
  https://doi.org/10.1016/j.cell.2015.05.002 · https://github.com/broadinstitute/Drop-seq
- Pairfq (S. Evan Staton, MIT). https://github.com/sestaton/Pairfq
- Dobin A. et al. (2013). STAR. *Bioinformatics* 29:15–21. https://doi.org/10.1093/bioinformatics/bts635
- Martin M. (2011). Cutadapt. *EMBnet.journal* 17:10–12. https://doi.org/10.14806/ej.17.1.200
- Danecek P. et al. (2021). Twelve years of SAMtools and BCFtools. *GigaScience* 10:giab008. https://doi.org/10.1093/gigascience/giab008
- Picard (Broad Institute). https://broadinstitute.github.io/picard/
- FastQC (Babraham Bioinformatics). https://www.bioinformatics.babraham.ac.uk/projects/fastqc/
- Ståhl P.L. et al. (2016). Spatial transcriptomics. *Science* 353:78–82. https://doi.org/10.1126/science.aaf2403
- Palla G. et al. (2022). Squidpy. *Nature Methods* 19:171–178. https://doi.org/10.1038/s41592-021-01358-2
- Janesick A. et al. (2023). Xenium. *Nature Communications* 14:8353. https://doi.org/10.1038/s41467-023-43458-x
- Chen K.H. et al. (2015). MERFISH. *Science* 348:aaa6090. https://doi.org/10.1126/science.aaa6090
- He S. et al. (2022). CosMx spatial molecular imaging. *Nature Biotechnology* 40:1794–1806. https://doi.org/10.1038/s41587-022-01483-z
- Oliveira M.F. et al. (2025). Visium HD. *Nature Genetics* 57:1512–1523. https://doi.org/10.1038/s41588-025-02193-3
- Chen A. et al. (2022). Stereo-seq. *Cell* 185:1777–1792. https://doi.org/10.1016/j.cell.2022.04.003
- Rodriques S.G. et al. (2019). Slide-seq. *Science* 363:1463–1467. https://doi.org/10.1126/science.aaw1219
- Moran P.A.P. (1950). Moran's I. *Biometrika* 37:17–23. https://doi.org/10.1093/biomet/37.1-2.17

### Protein

- Jumper J. et al. (2021). AlphaFold. *Nature* 596:583–589. https://doi.org/10.1038/s41586-021-03819-2
- Abramson J. et al. (2024). AlphaFold 3. *Nature* 630:493–500. https://doi.org/10.1038/s41586-024-07487-w
- Lin Z. et al. (2023). ESMFold. *Science* 379:1123–1130. https://doi.org/10.1126/science.ade2574
- Mirdita M. et al. (2022). ColabFold. *Nature Methods* 19:679–682. https://doi.org/10.1038/s41592-022-01488-1
- Evans R. et al. (2022). AlphaFold-Multimer. *bioRxiv*. https://doi.org/10.1101/2021.10.04.463034
- Bryant P., Pozzati G., Elofsson A. (2022). pDockQ. *Nature Communications* 13:1265. https://doi.org/10.1038/s41467-022-28865-w
- Kabsch W. (1976). Kabsch superposition. *Acta Crystallographica* A32:922–923. https://doi.org/10.1107/S0567739476001873

### Molecular biology

- Untergasser A. et al. (2012). Primer3. *Nucleic Acids Research* 40:e115. https://doi.org/10.1093/nar/gks596
- primer3-py (libnano). https://github.com/libnano/primer3-py
- Cock P.J.A. et al. (2009). Biopython. *Bioinformatics* 25:1422–1423. https://doi.org/10.1093/bioinformatics/btp163

### Phylogenetics

- Katoh K., Standley D.M. (2013). MAFFT. *Molecular Biology and Evolution* 30:772–780. https://doi.org/10.1093/molbev/mst010
- Capella-Gutiérrez S., Silla-Martínez J.M., Gabaldón T. (2009). trimAl. *Bioinformatics* 25:1972–1973. https://doi.org/10.1093/bioinformatics/btp348
- Wong T.K.F. et al. (2025). IQ-TREE 3. EcoEvoRxiv. https://doi.org/10.32942/X2P62N
- Minh B.Q. et al. (2020). IQ-TREE 2. *Molecular Biology and Evolution* 37:1530–1534. https://doi.org/10.1093/molbev/msaa015
- Kalyaanamoorthy S. et al. (2017). ModelFinder. *Nature Methods* 14:587–589. https://doi.org/10.1038/nmeth.4285
- Hoang D.T. et al. (2018). UFBoot2. *Molecular Biology and Evolution* 35:518–522. https://doi.org/10.1093/molbev/msx281
- Guindon S. et al. (2010). PhyML 3.0 and SH-aLRT. *Systematic Biology* 59:307–321. https://doi.org/10.1093/sysbio/syq010

## The software Everyome itself is built with

- **FastAPI** (https://fastapi.tiangolo.com), **Uvicorn** (https://www.uvicorn.org), **HTTPX**
  (https://www.python-httpx.org), **PyYAML** (https://pyyaml.org), **python-multipart** and **setproctitle**.
- **NumPy**: Harris C.R. et al. (2020). *Nature* 585:357–362. https://doi.org/10.1038/s41586-020-2649-2
- **SciPy**: Virtanen P. et al. (2020). *Nature Methods* 17:261–272. https://doi.org/10.1038/s41592-019-0686-2
- **pandas**: McKinney W. (2010). Proceedings of the 9th Python in Science Conference, 56–61.
  https://doi.org/10.25080/Majora-92bf1922-00a
- **Matplotlib**: Hunter J.D. (2007). *Computing in Science & Engineering* 9:90–95. https://doi.org/10.1109/MCSE.2007.55
- **seaborn**: Waskom M.L. (2021). *Journal of Open Source Software* 6:3021. https://doi.org/10.21105/joss.03021
- **openpyxl** (https://openpyxl.readthedocs.io) and **pytest** (https://pytest.org).
- **UMAP-JS** (PAIR, Google; Apache 2.0), bundled for the single-cell playground. https://github.com/PAIR-code/umap-js

## Design

- **Fonts**: all under the SIL Open Font License, served from **Fontsource** (https://fontsource.org); the logo uses
  **JetBrains Mono** (JetBrains) and **Playfair Display** (Claus Eggers Sørensen). Each font's licence ships with it in
  `everyome/static/fonts/`.
- **Themes**: each is drawn from the documented colouring of a cnidarian species. The Anthopleura theme's pink and
  green follow GitHub's **Primer** colours (MIT). https://primer.style
