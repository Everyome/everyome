**What it shows.** Each library's read pairs, from sequencing to unique valid contacts.

| Column | Good libraries | If not |
|---|---|---|
| Aligned pairs | both reads aligned in most pairs | wrong genome, contamination or poor reads |
| Valid pairs | usually over 40% of read pairs | below 25%: poor digestion or ligation (many dangling ends) |
| Duplicates | under 20–30% | a library with little diversity; more sequencing adds little |
| Within chromosomes (cis) | 60–90% | below 60%: many random ligations between broken DNA |
| Of those, over 20 kb | over 30–40% | mostly short-range contacts carry little information about folding |

Values worth a look are in red. For a usable map at a given resolution, aim for enough unique valid pairs that most
bins have hundreds of contacts: tens of millions for a few-hundred-megabase genome at 10–20 kb.
