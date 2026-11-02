**Why trim.** Columns that are mostly gaps, or where letters cannot be lined up with confidence, add noise
that can mislead the tree. Trimming removes them.

- `automated1` picks a method suited to the alignment; `gappyout` removes only gap-rich columns; `strict`
  also removes poorly conserved ones.
- Trimming too hard throws away real signal. If it removes most columns, try a gentler method or none, and
  see whether the tree changes; groups that only appear with one setting deserve caution.
