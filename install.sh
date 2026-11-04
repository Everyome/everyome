#!/usr/bin/env bash
# Everyome installer for macOS and Linux. One line, no administrator rights needed:
#
#   curl -fsSL https://raw.githubusercontent.com/Everyome/everyome/main/install.sh | bash
#
# What it does, all inside your home folder:
#   1. Uses your conda if you have one; otherwise installs Miniforge into ~/miniforge3 (checksum-verified).
#   2. Makes (or reuses) a conda environment called "everyome" with Python 3.12, from conda-forge.
#   3. Installs Everyome and all its analyses into that environment.
# Run it again at any time to repair or update an installation. Read it before you run it; it is short.
#
# Optional settings (put them before "bash", e.g. "... | EVERYOME_ENV=myenv bash"):
#   EVERYOME_ENV        environment name (default: everyome)
#   EVERYOME_CONDA_DIR  where to install Miniforge if you have no conda (default: ~/miniforge3)
#
# Everyome: https://github.com/Everyome/everyome (GPL-3.0-or-later). Created by Helen R Horkan PhD.

# Intent: everything sits in main(), called on the last line, so a download cut off half way runs nothing.
main() {
    set -euo pipefail

    # Intent: kept equal to everyome.__version__ (tests/test_install_script.py checks); bumped at each release.
    local VERSION="0.1.0a4"
    # Intent: a pinned Miniforge with its published SHA-256 per installer, so a changed download is refused.
    local MINIFORGE="26.9.4-1"
    local ENV_NAME="${EVERYOME_ENV:-everyome}"
    local CONDA_DIR="${EVERYOME_CONDA_DIR:-$HOME/miniforge3}"

    say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
    fail() { printf '\n\033[31mStopped: %s\033[0m\n' "$*" >&2
             printf 'Step-by-step guide: https://github.com/Everyome/everyome/blob/main/docs/INSTALL.md\n' >&2; exit 1; }

    say "Installing Everyome $VERSION"

    # 1. Which computer is this?
    local os arch
    case "$(uname -s)" in
        Darwin) os="MacOSX" ;;
        Linux)  os="Linux" ;;
        *) fail "this installer is for macOS and Linux. On Windows, install WSL and run it inside Ubuntu (see the guide)." ;;
    esac
    arch="$(uname -m)"
    case "$os-$arch" in
        MacOSX-arm64|MacOSX-x86_64|Linux-x86_64|Linux-aarch64) ;;
        Linux-arm64) arch="aarch64" ;;
        *) fail "no Miniforge installer for $os on $arch." ;;
    esac
    echo "Computer: $os $arch"

    # 2. Find conda, or install Miniforge.
    local conda=""
    if command -v conda >/dev/null 2>&1; then
        conda="$(command -v conda)"
    elif [ -x "$CONDA_DIR/bin/conda" ]; then
        conda="$CONDA_DIR/bin/conda"
    fi
    # Intent: conda can be a shell function rather than a file; ask it where its own program lives.
    if [ -n "$conda" ] && [ ! -x "$conda" ]; then
        conda="$(conda info --base 2>/dev/null)/bin/conda"
    fi

    local fresh=0
    if [ -n "$conda" ] && [ -x "$conda" ]; then
        echo "Using your conda: $conda"
    else
        [ -e "$CONDA_DIR" ] && fail "$CONDA_DIR exists but has no conda in it. Move it aside, or set EVERYOME_CONDA_DIR."
        local file="Miniforge3-$MINIFORGE-$os-$arch.sh" want
        case "$os-$arch" in
            MacOSX-arm64)  want="63f8f5367cd3e52d1dba3e22d8ad91d10ea0e93675ba5b0822312a4342d962e0" ;;
            MacOSX-x86_64) want="66b9e771fa268f30ce97c4f69bbce64a7e610dfd4cb993fb3b424466c3e42b50" ;;
            Linux-x86_64)  want="571b410272cc434f28bc6c5c49ca8ffd4a4d1bcba9f57f1b6baccdb46446cfcc" ;;
            Linux-aarch64) want="1f4e2f1898c054dd35133f778b92794116c28af330e5d5936d56d5f765401db4" ;;
        esac
        local tmp; tmp="$(mktemp -d)"
        # Intent: expanded now, because $tmp is local to main() and gone by the time the shell exits.
        # shellcheck disable=SC2064
        trap "rm -rf '$tmp'" EXIT
        say "Downloading Miniforge $MINIFORGE (about 100 MB)"
        curl -fL --progress-bar -o "$tmp/$file" \
            "https://github.com/conda-forge/miniforge/releases/download/$MINIFORGE/$file" \
            || fail "could not download Miniforge. Check your internet connection."
        local got
        if command -v sha256sum >/dev/null 2>&1; then got="$(sha256sum "$tmp/$file" | cut -d' ' -f1)"
        else got="$(shasum -a 256 "$tmp/$file" | cut -d' ' -f1)"; fi
        [ "$got" = "$want" ] || fail "the Miniforge download does not match its published checksum, so it was not run."
        echo "Checksum verified."
        say "Installing Miniforge into $CONDA_DIR"
        bash "$tmp/$file" -b -p "$CONDA_DIR" >/dev/null || fail "the Miniforge installer did not finish."
        conda="$CONDA_DIR/bin/conda"
        fresh=1
    fi

    # 3. Make or reuse the environment. conda-forge only: Anaconda's default channel has paid terms for larger
    #    organisations.
    local prefix=""
    prefix="$("$conda" run -n "$ENV_NAME" python -c 'import sys; print(sys.prefix)' 2>/dev/null || true)"
    if [ -n "$prefix" ]; then
        local pyver
        pyver="$("$prefix/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        case "$pyver" in
            3.10|3.11|3.12|3.13|3.14) echo "Reusing environment '$ENV_NAME' (Python $pyver)." ;;
            *) fail "environment '$ENV_NAME' has Python $pyver; Everyome needs 3.10 to 3.14. Remove it with
       conda remove -n $ENV_NAME --all
   and run this installer again." ;;
        esac
    else
        say "Making the '$ENV_NAME' environment (Python 3.12)"
        "$conda" create -y -q -n "$ENV_NAME" -c conda-forge --override-channels python=3.12 pip >/dev/null \
            || fail "could not make the '$ENV_NAME' environment."
        prefix="$("$conda" run -n "$ENV_NAME" python -c 'import sys; print(sys.prefix)')"
    fi

    # 4. Install Everyome. The exact version means stable releases of everything it needs (no --pre).
    say "Installing Everyome and its analyses (a few minutes; a lot of text is normal)"
    "$prefix/bin/python" -m pip install --upgrade --quiet pip || true
    "$prefix/bin/python" -m pip install --upgrade "everyome[all]==$VERSION" \
        || fail "pip could not install Everyome. The text above says why."
    "$prefix/bin/everyome" --help >/dev/null || fail "Everyome installed but does not start."

    # 5. Let new terminals find conda (only if we installed Miniforge: an existing conda is left as you set it).
    if [ "$fresh" = 1 ]; then
        local shell_name; shell_name="$(basename "${SHELL:-bash}")"
        case "$shell_name" in bash|zsh|fish|tcsh|xonsh) ;; *) shell_name="bash" ;; esac
        "$conda" init "$shell_name" >/dev/null 2>&1 || true
    fi

    say "Everyome $VERSION is installed."
    cat <<EOF
To start it, open a NEW terminal window and type:

    conda activate $ENV_NAME
    everyome

Your browser opens Everyome. Choose Demo cluster to try every analysis with example data.
Leave the terminal open while you use it; press Ctrl+C there to stop it.

Or start it now, without opening a new terminal:

    $prefix/bin/everyome

Please cite Everyome if you use it: https://github.com/Everyome/everyome
EOF
}

main "$@"
