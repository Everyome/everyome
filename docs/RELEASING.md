# Releasing Everyome to PyPI

Releases are published by GitHub Actions when a maintainer pushes a version tag, using PyPI's Trusted
Publishing: PyPI accepts the upload because it comes from this repository's *Release* workflow, so no token is
stored anywhere. Nothing is uploaded until a maintainer approves it on GitHub.

## 1. Prepare

Prepare on a branch (`git switch -c release-<version>`) and merge it into `main` only after the upload. The
one-line installer that users run is `install.sh` on `main`, and it installs the version it names: on `main`
before that version is on PyPI, it fails for everyone. Push the branch to run CI (the *Installer* workflow can
only pass after the upload; cancel it on the branch).

1. Set the version in `everyome/__init__.py` (the only place the package reads it), in `CITATION.cff`, in
   `install.sh` (`VERSION=`), in `pipelines/pyproject.toml` and in the `pipelines` extra in `pyproject.toml`.
   Use `0.1.0a1`-style numbers for pre-releases. The *Release* workflow stops if any of these differs from the tag.
2. Update the version in the install commands of `README.md` and `docs/INSTALL.md`. For a pre-release, those
   install lines must name the exact version (`pip install "everyome==0.1.0a1"`), not use `--pre`.
3. Run the tests: `pytest` (with `pip install -e ".[dev]"`). Pushes are tested on Linux only; before a
   release, also run the macOS jobs: on GitHub, Actions, CI, *Run workflow* (or `gh workflow run CI -f macos=true`),
   and wait for all jobs to pass.

## 2. Release

1. Tag the last commit of the release branch and push the tag:

   ```bash
   git tag -a v<version> -m "Everyome <version>"
   git push origin refs/tags/v<version>
   ```

2. The *Release* workflow (Actions tab) then:
   - checks the tag matches every version line;
   - builds both packages (the pipelines build stops if anything fetched differs from
     `everyome/pipelines.lock.json`) and runs `twine check`;
   - installs the built files into a fresh environment, the way users will, and runs the tests against them;
   - waits for a maintainer's approval (*Review deployments*, then *Approve and deploy*). This is the moment
     of upload, so look over the run first;
   - uploads `everyome-pipelines`, then `everyome`;
   - waits for PyPI to list them, then runs the one-line installer on new Linux and macOS machines.

   The same tag push also runs the full CI on Linux and macOS.
3. Check https://pypi.org/project/everyome/ and https://pypi.org/project/everyome-pipelines/.
4. Merge the release branch into `main` (`git merge --ff-only release-<version>`) and push: the README and the
   one-liner now name the new version.

If the workflow fails before the upload, nothing has been published: fix it on the branch, then move the tag
(`git tag -d v<version> && git push origin :refs/tags/v<version>`, and tag again). Once a version is uploaded it
can never be uploaded again, even after deleting it from PyPI; fix mistakes with a new version.

## 3. One-time setup

1. On PyPI, for each project (`everyome`, `everyome-pipelines`): *Manage*, *Publishing*, *Add a new publisher*,
   GitHub, with owner `Everyome`, repository `everyome`, workflow `release.yml`, environment `pypi`.
   A brand-new package can be set up the same way before its first upload, as a *pending publisher*
   (https://pypi.org/manage/account/publishing/).
2. On GitHub: repository *Settings*, *Environments*, *New environment* named `pypi`. Under *Deployment protection
   rules*, tick *Required reviewers* and add the maintainers. Under *Deployment branches and tags*, choose
   *Selected branches and tags* and add the tag rule `v*`.
3. Once a release has gone out this way, delete the project tokens on PyPI (*Account settings*, *API tokens*) and
   from `~/.pypirc`.

## 4. Rehearsing on TestPyPI (optional)

TestPyPI is a separate site with its own account: https://test.pypi.org. Build locally (as in section 5) and
upload with a TestPyPI token:

```bash
twine upload --repository testpypi dist/*
# take only everyome from TestPyPI, then everything it needs from the real PyPI
pip download --no-deps --pre --index-url https://test.pypi.org/simple/ everyome==<version> -d testpypi_dl
pip install --pre --index-url https://pypi.org/simple/ --find-links testpypi_dl "everyome[all]==<version>"
```

Never let pip fetch everyome's dependencies from TestPyPI: anyone can upload there, and it holds broken copies
of common packages (for example `fastapi`). pip does not prefer the first index; it picks the highest version
across all of them, so `--extra-index-url` is not enough.

## 5. Uploading by hand (only if GitHub Actions can't be used)

1. Build and check both packages:

   ```bash
   rm -rf dist build pipelines/everyome_pipelines/bundles pipelines/dist
   python -m build
   python -m everyome.core.pipelines build --into pipelines/everyome_pipelines/bundles
   python -m build pipelines --outdir dist
   twine check --strict dist/*
   ```

2. Install the wheels into a fresh environment and run the tests against them, by exact version and without
   `--pre`, so dependencies come from stable releases.
3. Upload with a project-scoped token per package (https://pypi.org/manage/account/token/), kept in
   `~/.pypirc` as `[pypi-everyome]` and `[pypi-pipelines]` (both with
   `repository = https://upload.pypi.org/legacy/` and `username = __token__`, listed under `index-servers`;
   `chmod 600`). Never paste a token in chat or put one in the repository. Pipelines first:

   ```bash
   twine upload --repository pypi-pipelines dist/everyome_pipelines-<version>*
   twine upload --repository pypi-everyome dist/everyome-<version>*
   ```

4. Pushing the tag starts the *Release* workflow; reject its approval step (*Review deployments*, *Reject*), since
   the files are already up. PyPI's index can take a few minutes to list a new upload; if an install says the
   version doesn't exist, wait and retry.
