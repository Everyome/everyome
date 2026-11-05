**How to read a contact map.** Both axes are the same stretch of chromosome. The square at row *i*, column *j* is how
often place *i* touched place *j*; the map is symmetric about the diagonal. Colours are on a log scale.

- **The diagonal** is darkest: neighbouring places always touch most.
- **Squares (triangles) along the diagonal** are TADs: stretches that touch themselves more than their neighbours.
- **A checkerboard** away from the diagonal is compartments: open stretches touch other open stretches, closed touch closed.
- **Dots** at the corners of squares are loops (often CTCF-anchored in vertebrates); they need fine maps and deep sequencing.
- **Grey rows and columns** are bins left out by balancing (repeats, gaps or too few contacts).

Choose a coarser resolution to see a whole chromosome, and a finer one to see domains. With *Automatic*, Everyome picks
the finest map that fits the region in about 250 bins.
