# Installing Everyome

Three ways in:

- **[One-line install](#one-line-install)**: the easiest. One command does everything.
- **[Quick install](#quick-install)** if you already use Python and the command line.
- **[Step by step](#step-by-step-for-people-new-to-the-command-line)** if you have never used a terminal and want to
  see each step. No experience needed; it takes about 15 minutes, most of it waiting for downloads.

Everyome runs on **macOS** and **Linux**. Windows is not tested yet (see [Windows](#windows)).

---

## One-line install

1. Open a terminal: on a Mac press **⌘ Command + Space**, type `Terminal` and press Return; on Linux press
   **Ctrl + Alt + T**.
2. Copy this line, paste it into the terminal and press Return:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/Everyome/everyome/main/install.sh | bash
   ```

3. Wait until it says **Everyome … is installed** (about 10 minutes, mostly downloads; a lot of text is normal).
4. Close the terminal. From now on, start Everyome from its **icon**, with no terminal needed:
   - **Mac:** click **Everyome** in the Dock (the bar at the bottom of the screen), or press ⌘ Space and type
     `Everyome`.
   - **Linux:** your applications menu, or the icon on your desktop.

   Everyome opens in your browser. To stop it, click **Quit** at the top right.

What it does, all inside your home folder and without administrator rights: if you have no conda, it downloads
Miniforge, checks the download against its published checksum, and installs it into `~/miniforge3`; it makes an
environment called `everyome` with Python 3.12 from conda-forge; it installs Everyome with every analysis; and it adds
the Everyome icon. If you already have conda, it uses yours. To skip the icon (for example on a cluster login node),
run it as `curl -fsSL … | EVERYOME_NO_ICON=1 bash`. Running it again repairs or updates an installation. You can
[read the script](https://github.com/Everyome/everyome/blob/main/install.sh) before running it.

If it stops with a message, the [table below](#if-something-goes-wrong) covers the usual causes, or follow the
step-by-step guide instead.

---

## Quick install

```bash
conda create -n everyome python=3.12
conda activate everyome
pip install "everyome[all]==0.1.0a5"
everyome
```

`everyome` opens the app in your browser at http://127.0.0.1:8777. Choose **Demo cluster** to try everything with
example data. Any Python 3.10 to 3.14 environment works (venv, uv or conda); `everyome[all]` installs every analysis
and the pipelines package, plain `everyome` only the app and the tutorial. Name the exact version (as above) while
Everyome is in early releases: that installs this early Everyome but stable releases of everything it needs (avoid
`pip install --pre`).

To use your own cluster, see [On your cluster](#on-your-cluster).

### The Everyome icon

The one-line installer adds an icon that starts Everyome without a terminal. After any other install, add it with
`everyome --shortcut` (and take it away with `everyome --remove-shortcut`). On a Mac it is **Everyome** in the Dock,
and in the Applications folder inside your home folder (not the main one, which needs an administrator password);
on Linux it is in the applications menu and on the desktop. Opening it
starts Everyome in the background and opens it in your browser; opening it again while Everyome is running just
opens the browser. Stop Everyome with **Quit** at the top right. Its messages go to `~/.everyome/logs/app.log`, which
is the place to look if the icon seems to do nothing.

---

## Step by step, for people new to the command line

You will type a few commands into a **terminal**: a window where you give the computer instructions as text. Each
command below is in a grey box. Copy it, paste it into the terminal, and press **Return** (or **Enter**). That is all
the "coding" there is.

A few things that are normal:

- Some commands print a lot of text; others print nothing. Both are fine. Wait until the terminal shows its prompt
  again (a line ending in `%` or `$`) before typing the next command.
- When you type a password in a terminal, nothing appears on screen. It is still being typed.
- If something goes wrong, see [If something goes wrong](#if-something-goes-wrong) at the end.

### 1. Open a terminal

- **Mac:** press **⌘ Command + Space**, type `Terminal`, and press Return. (Or open Finder, then Applications,
  Utilities, Terminal.)
- **Linux:** press **Ctrl + Alt + T**, or find **Terminal** in your applications menu.

A window opens with a line of text ending in `%` or `$`. That is the prompt: the terminal is waiting for you.

### 2. Install Miniforge (once per computer)

Miniforge installs **conda**, a free tool that keeps the software Everyome needs separate from everything else on
your computer. It uses the free, community-run conda-forge collection of packages. (If you already have Anaconda or
Miniconda, you can skip to step 3; they work the same way here. Note that Anaconda's own package channel has paid
terms for larger organisations, which is one reason Miniforge is recommended.)

**On a Mac, the easiest way is the installer you double-click.** First, find out which kind of Mac you have: click
the Apple menu (top left), then **About This Mac**. If it says **Chip: Apple M…**, you have Apple Silicon; if it says
**Processor: Intel**, you have an Intel Mac. Then download the matching installer:

- Apple Silicon: https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.pkg
- Intel: https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.pkg

Open the downloaded file and click **Continue** through the screens. At the installation-type screen, click
**Customise** and make sure the option to **initialise conda for your shell** is ticked. Then click **Install**.
When it says it was successful, **close the terminal window and open a new one** (step 1).

**On Linux (or on a Mac, if you prefer the terminal),** paste these two commands, one at a time:

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
```

```bash
bash Miniforge3-$(uname)-$(uname -m).sh
```

The installer asks a few questions:

1. Press Return to read the licence, then press **q** to leave it, type `yes` and press Return to accept.
2. Press Return to install it in the suggested place (your home folder).
3. When asked whether to **initialise** conda, type `yes` and press Return.

Then **close the terminal window and open a new one**.

**Check it worked:** in the new terminal, type

```bash
conda --version
```

It should print a version, such as `conda 26.9.4`. The prompt may also now start with `(base)`.

### 3. Make a home for Everyome (once)

This creates a separate **environment** called `everyome`, with the right version of Python in it:

```bash
conda create -n everyome python=3.12
```

When it asks `Proceed ([y]/n)?`, type `y` and press Return. Then switch into the new environment:

```bash
conda activate everyome
```

The prompt now starts with `(everyome)`. That tells you Everyome's environment is active.

### 4. Install Everyome (once)

```bash
pip install "everyome[all]==0.1.0a5"
```

This downloads Everyome and everything it needs, and takes a few minutes. It prints a lot; yellow warnings are
fine. It has worked when the last line starts with `Successfully installed`.

### 5. Start Everyome

```bash
everyome
```

Your web browser opens Everyome. (If it doesn't, open your browser and go to http://127.0.0.1:8777.) Everything
runs on your own computer; nothing is sent anywhere.

**Leave the terminal window open while you use Everyome.** To stop it, click **Quit** at the top right of
Everyome, or click on the terminal window and press **Ctrl + C**.

To try it out, click **Connect**, choose **Demo cluster**, and follow the pages. The demo has example data for every
analysis and a pretend job scheduler, so you can try everything before using real data.

### Next time

You only do steps 2 to 4 once. To start Everyome without a terminal from now on, add its icon once:

```bash
everyome --shortcut
```

Then open **Everyome** from the Dock (Mac), or your applications menu or desktop (Linux). Or, from a
terminal: `conda activate everyome`, then `everyome`.

### Updating to a new version

```bash
conda activate everyome
pip install --upgrade "everyome[all]==<new version>"
```

using the version number from the README or https://pypi.org/project/everyome/.

### Removing Everyome

```bash
conda deactivate
conda remove -n everyome --all
```

This deletes the environment and everything installed in it. Projects on this computer and the demo data are kept
in `~/.everyome` (projects on a cluster stay on the cluster); delete that folder too if you want them gone.

### If something goes wrong

| What you see | What to do |
|---|---|
| `conda: command not found` | Close the terminal and open a new one. If it still happens, run `~/miniforge3/bin/conda init` (or `~/miniforge3/bin/conda init zsh` on a Mac), then open a new terminal. |
| `everyome: command not found` | The environment isn't active: run `conda activate everyome` first. If it still fails, repeat step 4. |
| The prompt doesn't show `(everyome)` | Run `conda activate everyome`. |
| `No matching distribution found for everyome` | Check the version number is typed exactly, and that your Python is 3.10 to 3.14 (`python --version`). |
| Errors while installing, mentioning `h5py` or a compiler | Usually a too-new Python. Make the environment again with `python=3.12` (step 3, after `conda remove -n everyome --all`). |
| `address already in use` | Everyome is already running in another terminal window. Use that one, or start this one on another port: `everyome --port 8778`. |
| The browser shows nothing | Wait a few seconds and reload. Check the terminal for an error message. |

If you are still stuck, open an issue at https://github.com/Everyome/everyome/issues with what you typed and what
the terminal printed (leave out anything private, such as passwords or file paths you'd rather not share).

---

## Windows

Everyome has not been tested on Windows yet. The likely route is **WSL** (Windows Subsystem for Linux), which runs
Linux inside Windows: open **PowerShell** as administrator, run `wsl --install`, restart, open the **Ubuntu** app it
adds, and follow the Linux steps above in that window. Then open http://127.0.0.1:8777 in your Windows browser. If you
try this, please tell us how it went (issues link above).

## On your cluster

To run analyses on a Slurm cluster through your own account, Everyome also needs to be installed **on the cluster**,
in a Python environment there (the same steps, run after logging in to the cluster; or ask IT for a shared
installation). The cluster also needs Nextflow, Java and Apptainer for the pipeline analyses. In the app, **Connect**
then **My cluster** runs readiness checks and tells you what is missing. For pipelines and containers on clusters
(including clusters without internet), see [`PIPELINES.md`](PIPELINES.md).

## Python versions

Everyome needs Python 3.10 or newer. It is tested on 3.10 and 3.12; 3.13 and 3.14 should work. Python 3.15 is not
supported yet, because some of the scientific packages Everyome uses do not install there.
