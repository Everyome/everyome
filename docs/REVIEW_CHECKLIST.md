# Review checklist for community modules

For registry maintainers. A module is approved only when **every** box is ticked
by a maintainer who is not one of its authors. Paste this list into the pull
request and tick it there, so the review is on record.

## Automated (CI must be green)

- [ ] `python -m everyome.registry check` passes (no **Must fix** items).
- [ ] The module's own tests pass on its example data.

## Safety: read every line of code

- [ ] Each item under **For the reviewer to look at** is explained by the author and acceptable.
- [ ] No network access (Python or browser), unless essential, explained in the manual, and limited to named, trustworthy sources.
- [ ] Reads only the files the person chose and writes only inside the run folder.
- [ ] No other programs run (`subprocess`, `os.system`), no code built at run time (`eval`, `exec`, dynamic imports).
- [ ] Nothing touches credentials: SSH keys, tokens, `~/.pypirc`, browser data, environment secrets.
- [ ] `ui.js` and playground scripts only call Everyome's helpers and `/api`; no remote scripts, fonts or trackers.
- [ ] `requires` lists only well-known packages from PyPI or conda-forge, with no typo-squatted names.
- [ ] The example data contains no personal, patient or unpublished data.

## Science

- [ ] The method does what the manual says, with defaults a careful biologist would choose.
- [ ] The methods text it writes is accurate and cites the tools with DOIs or URLs.
- [ ] Results on the example data are what the manual says they should be.

## Learning material

- [ ] The manual explains every setting in plain language.
- [ ] The playground teaches something true, and its caveats say where it simplifies.
- [ ] Every chart or table has a "how to read this" guide.

## Licence and credit

- [ ] The licence is open source and the `LICENSE` file matches `module.yaml`.
- [ ] Authors are credited; third-party code or data keeps its licence and is acknowledged.

## Publishing (maintainer, after approval)

```bash
python -m everyome.registry approve REGISTRY submissions/<name> --reviewer "Your Name" --key ~/.ssh/id_ed25519
python -m everyome.registry index REGISTRY --key ~/.ssh/id_ed25519
```

Commit `entries/`, `archives/` and the signed `index.json`. To withdraw a version:
`python -m everyome.registry revoke REGISTRY community.<name> --version 1.0.0 --reason "..."`,
then rebuild and sign the index. Installed copies stop loading the next time Everyome starts.
