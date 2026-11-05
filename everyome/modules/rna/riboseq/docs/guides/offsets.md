**What it shows.** For each footprint length: how many footprints, the P-site offset riboWaltz chose (from the read's
5' end), and the share of P-sites in each frame.

- The **P-site offset** turns a read into the codon the ribosome was reading. It is usually 12 nt for 28–30 nt footprints
  and a little longer for longer ones.
- **Lengths with a strong frame 0** are the informative ones. A length with frames near a third each adds noise; some
  people leave such lengths out (riboWaltz and Plastid settings).
- If every length is weak, check the offsets plot in the pipeline's riboWaltz output before trusting the counts.
