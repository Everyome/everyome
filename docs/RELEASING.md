# Releasing Everyome to PyPI

Releases are uploaded by a maintainer, from their own computer, with their own
PyPI token. Nothing in this repository uploads on its own.

## 1. Prepare

1. Set the version in `everyome/__init__.py` (the only place it lives) and in
   `CITATION.cff`. Use `0.1.0a1`-style numbers for pre-releases.
2. Run the tests: `pytest` (with `pip install -e ".[test,all]"`).
3. Build and check:

   ```bash
   rm -rf dist build
   python -m build
   twine check --strict dist/*
   ```

4. Optional but worth it: install the wheel into a fresh environment and run
   the tests against it (this catches files left out of the package).

## 2. Rehearse on TestPyPI

TestPyPI is a separate site with its own account: https://test.pypi.org

```bash
twine upload --repository testpypi dist/*
pip install --pre --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ everyome
```

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
