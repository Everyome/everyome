# Writing a community module

The community registry is **switched off** in this version of Everyome. This guide
is here so authors can build and test modules now; nothing is published until the
registry opens and a maintainer has reviewed the module.

## What a community module can do (for now)

- Run **on the person's own computer** (`kind: [local]`). Modules that submit
  cluster jobs need their code installed on each cluster, which the registry does
  not do yet.
- Use Python packages Everyome already depends on, plus those listed in `requires`
  (the person installs them; the registry never installs packages).
- Read the files the person gives it and write into its run folder.

It must not reach the network, read files it was not given (home folder, SSH keys,
browser data), run other programs, or build code at run time, unless the manual
explains why and the reviewer agrees.

## Folder layout

```
my_module/
  module.yaml                   the manifest (spec 1; see Everyome's own modules for examples)
  LICENSE                       an open-source licence (MIT, BSD, Apache-2.0, GPL, ...)
  everyome_c_community_<name>/  ALL Python code, in a package named after the id
    __init__.py
    engine.py                   class Engine(BaseEngine) and a methods(record) function
  ui.js                         the module's views (Everyome.registerViews)
  docs/manual.md                the manual
  docs/guides/*.md              "how to read this" notes, one per chart or table
  docs/playground/*.js          the playground (Everyome.makePlayground)
  demo/                         small example data (the whole module under 20 MB)
  tests/test_*.py               tests that run on the example data
```

- `id` is `community.<name>`; the package is `everyome_c_community_<name>`, so
  modules never clash with each other or with Everyome.
- `version` looks like `1.0.0` (or `1.0.0a1`); every change is a new version.
- `licence` is an SPDX id, for example `MIT`.
- Source only: no compiled files, archives or hidden files.

A complete small example lives in Everyome's repository at
`tests/fixtures/community_kmer/` (a k-mer spectrum module).

## Try it

```bash
python -m everyome.registry check path/to/my_module --markdown   # the same checks the registry runs
EVERYOME_DEV_MODULES=path/to/my_module everyome                  # loads it, marked "Unreviewed"
```

Fix everything under **Must fix**. Anything under **For the reviewer to look at**
is allowed, but explain it in your pull request.

## Submit it (when the registry opens)

Open a pull request to the `everyome-modules` registry repository adding your
folder under `submissions/`. Its CI runs the checks and your tests; a maintainer
then works through the [review checklist](REVIEW_CHECKLIST.md). Accepted modules
are packed, signed by the maintainer and listed in the signed index; Everyome
refuses anything whose signature or checksum does not match, and stops offering
a version once it is withdrawn.
