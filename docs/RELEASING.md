# Releasing Everyome to PyPI

Releases are uploaded by a maintainer, from their own computer, with their own
PyPI token. Nothing in this repository uploads on its own.

## 1. Prepare

Prepare on a branch (`git switch -c release-<version>`) and merge it into `main` only after the upload. The
one-line installer that users run is `install.sh` on `main`, and it installs the version it names: on `main`
before that version is on PyPI, it fails for everyone. Push the branch to run CI (the *Installer* workflow can
only pass after the upload; cancel it on the branch).

1. Set the version in `everyome/__init__.py` (the only place it lives), in
   `CITATION.cff` and in `install.sh` (`VERSION=`; a test checks it matches). Use `0.1.0a1`-style numbers for pre-releases.
2. Run the tests: `pytest` (with `pip install -e ".[dev]"`). Pushes are tested on Linux only; before a
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
   a new package needs an account-wide token, as below.
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
2. Have one API token per package, each scoped to its project
   (https://pypi.org/manage/account/token/), in `~/.pypirc` as two sections,
   `[pypi-everyome]` and `[pypi-pipelines]`, both with
   `repository = https://upload.pypi.org/legacy/` and `username = __token__`, and
   both listed under `index-servers`. Keep the file private (`chmod 600`); never
   paste a token in chat or put one in the repository.
   A brand-new package needs an "Entire account" token for its first upload (the
   project does not exist yet to scope a token to); swap it for a project token
   straight after.
3. Upload each package with its own token:

   ```bash
   twine upload --repository pypi-everyome dist/everyome-<version>*
   twine upload --repository pypi-pipelines dist/everyome_pipelines-<version>*
   ```

4. Check https://pypi.org/project/everyome/ and
   https://pypi.org/project/everyome-pipelines/. (Trusted Publishing from GitHub
   Actions would remove the stored tokens altogether.)

## 4. Afterwards

- Merge the release branch into `main` (`git merge --ff-only release-<version>`) and push: the README and the
  one-liner now name the new version. PyPI's index can take a few minutes to list a new upload; if an install
  says the version doesn't exist, wait and retry.
- The tag also runs the one-line installer on new Linux and macOS machines (the *Installer* workflow); check it
  passes, since that is what new users run.
- Tag the release in git: `git tag -a v<version> -m "Everyome <version>" && git push origin refs/tags/v<version>`.
  The tag push runs CI on Linux and macOS.
- A version number can never be uploaded twice, even after deleting it from
  PyPI; fix mistakes with a new version (for example `0.1.0a2`).
