**What it shows.** How many read pairs each sample had, and what share became usable contacts, from HiC-Pro's
statistics in nf-core/hic. The MultiQC report has every step in detail.

- **Valid pairs** are read pairs that came from two different restriction fragments joined by ligation: real contacts.
  The rest are mostly dangling ends (the fragment never ligated), self-circles and religation.
- **Duplicates** are pairs seen more than once, usually PCR copies; they are removed.
- One sample far below the rest may have failed or been under-sequenced. The live session checks each library in more detail.
