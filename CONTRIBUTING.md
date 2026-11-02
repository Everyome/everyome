# Contributing to Everyome

Thank you for helping. Everyome is for biologists, so the bar for every change is
the same: a person who is not a programmer can use it, understand what it did,
and write it up.

## Reporting a problem

Open an issue with what you did, what you expected and what happened. Leave out
patient data, unpublished sequences, passwords, keys and cluster host names.

## Changing Everyome itself

1. `pip install -e ".[test,all]"` and `pytest` (see the README).
2. Keep comments to the *intent* of the code, and UI text plain and short.
3. Every module keeps its manual, example data, playground and "how to read this"
   guides; `tests/test_learning.py` checks this.
4. Never add code that submits cluster jobs on its own: jobs run only when the
   person clicks Run, under their own account. Job names are `<user>_everyome_…`, with a
   prefix if the site sets one. If an AI assistant starts processes while you develop (tests,
   demo runs), set `EVERYOME_JOB_PREFIX` to the assistant's name so they are labelled.
5. Literature references include a DOI or URL.

## Writing a module for the community registry

The community registry is built but **switched off** in this version of
Everyome. You can still write a module and try it on your own computer; see
[docs/MODULE_AUTHORS.md](docs/MODULE_AUTHORS.md). Every submission is read by a
maintainer before it is offered to anyone
([docs/REVIEW_CHECKLIST.md](docs/REVIEW_CHECKLIST.md)).

## Conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).
