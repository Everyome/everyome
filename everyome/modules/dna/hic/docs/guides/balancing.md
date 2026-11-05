**Why balance a map.** Some bins are seen more often than others for reasons that have nothing to do with folding:
how many restriction sites they have, their GC content and how uniquely reads align. Balancing (iterative correction)
gives every bin a weight so that each row of the map adds up to the same total, removing these biases.

Compare *Balanced* with *No: raw counts* on the same region: raw maps show stripes across bins with many or few
reads; balanced maps show the folding. Bins with too few contacts to balance are left out (grey).
