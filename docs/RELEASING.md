# Releasing Everyome to PyPI

Releases are uploaded by a maintainer, from their own computer, with their own
PyPI token. Nothing in this repository uploads on its own.

## 1. Prepare

1. Set the version in `everyome/__init__.py` (the only place it lives) and in
   `CITATION.cff`. Use `0.1.0a1`-style numbers for pre-releases.
2. Run the tests: `pytest` (with `pip install -e ".[test,all]"`). Pushes are tested on Linux only; before a
   release, also run the macOS jobs: on GitHub, Actions, CI, *Run workflow* (or `gh workflow run CI -f macos=true`),
   and wait for all four jobs to pass. Pushing a release tag (`v…`) runs them too.
3. Build and check:

   ```bash
   rm -rf dist build
   python -m build
   twine check --strict dist/*
   ```

4. Build the pipelines package too, at the same version (set it in
   `pipelines/pyproject.toml`, and in the `pipelines` extra in `pyproject.toml`). The build stops if anything fetched differs from
   `everyome/pipelines.lock.json`:

   ```bash
   rm -rf pipelines/everyome_pipelines/bundles pipelines/dist
   python -m everyome.core.pipelines build --into pipelines/everyome_pipelines/bundles
   python -m build pipelines --outdir dist
   twine check --strict dist/*
   ```

   Upload both packages (`dist/*` holds both). The first upload of
   `everyome-pipelines` also needs an account-wide token, as below.
5. Optional but worth it: install the wheel into a fresh environment and run
   the tests against it (this catches files left out of the package). Install it
   the way users will, by exact version and without `--pre`, so dependencies come
   from stable releases.
6. Update the version in the install commands of `README.md` and `docs/INSTALL.md`.
   For a pre-release, those install lines must name the exact version
   (`pip install "everyome==0.1.0a1"`), not use `--pre`.

## 2. Rehearse on TestPyPI

TestPyPI is a separate site with its own account: https://test.pypi.org

```bash
twine upload --repository testpypi dist/*
# take only everyome from TestPyPI, then everything it needs from the real PyPI
pip download --no-deps --pre --index-url https://test.pypi.org/simple/ everyome==<version> -d testpypi_dl
pip install --pre --index-url https://pypi.org/simple/ --find-links testpypi_dl "everyome[all]==<version>"
```

Never let pip fetch everyome's dependencies from TestPyPI: anyone can upload
there, and it holds broken copies of common packages (for example `fastapi`).
pip does not prefer the first index; it picks the highest version across all of
them, so `--extra-index-url` is not enough.

## 3. Upload to PyPI

1. Have a PyPI account with two-factor authentication on.
2. Create an API token at https://pypi.org/manage/account/token/ (for the first
   upload it must be "Entire account", because the project does not exist yet).
3. Upload; paste the token when twine asks (in the terminal, never in chat):

   ```bash
   twine upload dist/*
   ```

4. Check https://pypi.org/project/everyome/, then replace the account-wide token
   with one scoped to the `everyome` project, or set up Trusted Publishing from
   GitHub Actions so no token is stored at all.

## 4. Afterwards

- Tag the release in git: `git tag v0.1.0a1 && git push --tags`.
- A version number can never be uploaded twice, even after deleting it from
  PyPI; fix mistakes with a new version (for example `0.1.0a2`).
