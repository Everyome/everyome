**What it shows.** The insulation score: for each bin, how many contacts cross it within the window (a diamond on the
map just off the diagonal), relative to the chromosome's typical value, on a log2 scale. Inside a domain many contacts
cross; at a boundary few do, so **boundaries are dips**.

- **Window.** Similar to the size of the smallest domains you expect. A small window finds small domains and more
  noise; a large one finds only strong, large-scale boundaries. Try a few.
- **Minimum boundary strength.** How deep a dip must be, compared with the peaks either side. Raise it to keep only
  clear boundaries.
- **Triangles** mark HiCExplorer's boundaries from the pipeline (if it called them at this resolution). The two
  methods often disagree on weak boundaries: TAD calling has no single right answer. Trust boundaries both find and
  that you can see on the map.
- Domain sizes differ between species: around 1 Mb in mammals, tens to a few hundred kilobases in flies and many
  invertebrates.
