# everyome-modules (template)

The starting point for the Everyome community module registry: a separate
repository that maintainers control. It is not created yet, and Everyome's
registry is switched off.

| Path | What |
|---|---|
| `submissions/<name>/` | Pull requests add a module folder here |
| `entries/<id>/<version>.json` | One approval each: archive checksum, reviewer, date (written by `approve`) |
| `archives/` | Signed, reproducible archives of approved modules |
| `revoked.json` | Withdrawn versions |
| `index.json` + `.sig` | What Everyome reads; signed by a maintainer |
| `allowed_signers.example` | Format for the maintainers' public keys |
| `.github/workflows/check.yml` | Runs the automated checks and the module's tests on every pull request |

Reviewing and publishing: see `docs/REVIEW_CHECKLIST.md` in the Everyome repository.

Rules for maintainers:
- At least one maintainer who is not an author approves each module.
- Signing keys stay on maintainers' own computers; CI never holds them.
- Protect the main branch: pull requests only, with review.
