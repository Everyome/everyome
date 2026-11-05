**What happens.** For each section, Everyome reads the counts and positions at the bin size you choose.

- **Visium HD**: Space Ranger's `binned_outputs/square_002um`, `square_008um` or `square_016um`, with the tissue image.
- **Stereo-seq**: the GEM file (one line per gene per DNB spot, 500 nm apart), summed into square bins of this size.
- **Curio Seeker**: the beads (10 µm) as they are; the bin size doesn't apply.
- **8 µm** is about one cell: good for cell types. **16 µm** holds more RNA per bin and is easier to cluster, but mixes
  neighbouring cells. **2 µm** is for checking fine structure; most bins hold very little RNA.
