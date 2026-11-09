**What it shows.** For each primer pair, Cq against the log of the starting quantity in a dilution series. A straight
line means the reaction behaves the same at every amount of template.

- **Slope**: about −3.32 means 100% efficiency (the product doubles each cycle). Efficiency is 10^(−1/slope) − 1.
- **Acceptable**: 90–110% (shown in red outside this range), with **R²** of 0.98 or more.
- Efficiency matters because a small error grows each cycle: assuming 100% for a pair that is really 90% turns a
  5-cycle difference into a fold change about 30% too high. Try it in the playground.
- Targets without at least three dilutions use the efficiency in the run's settings.
