**What it shows.** The predicted aligned error (PAE): the expected error, in Å, in residue *j*'s position (across)
when the model is lined up on residue *i* (down). Dark is low error (confident), light is high.

- **Dark squares on the diagonal** are blocks that are confidently shaped: domains.
- **Light areas between two dark squares** mean the two domains' positions relative to each other are uncertain,
  even if each domain is confident. Do not read anything into how the domains touch.
- **Dark areas off the diagonal** link parts that are confidently placed together, for example two domains that
  pack against each other or the two chains of a confident complex.
- ESMFold does not report PAE here; use pLDDT only, or add AlphaFold2 or ColabFold to compare.
