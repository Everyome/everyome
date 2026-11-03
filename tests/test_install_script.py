"""The one-line installer (install.sh): it installs this version of Everyome, and bash can read it."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import everyome

SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"
pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="install.sh is in the repository, not the package")


def test_installs_this_version():
    # Intent: a release that forgets to bump install.sh would quietly install the previous version.
    assert re.search(r'local VERSION="([^"]+)"', SCRIPT.read_text())[1] == everyome.__version__


def test_bash_can_read_it():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_every_installer_has_a_checksum():
    text = SCRIPT.read_text()
    for target in ("MacOSX-arm64", "MacOSX-x86_64", "Linux-x86_64", "Linux-aarch64"):
        assert re.search(rf'{target}\)\s+want="[0-9a-f]{{64}}"', text), target


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck not installed")
def test_shellcheck():
    p = subprocess.run(["shellcheck", str(SCRIPT)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
