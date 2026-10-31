"""How the app talks to the computer that does the work (carried over from SPLiTscape).

Two backends with one interface:
  * SSHBackend   — a real cluster. Uses the system `ssh` client, so the user's
                   key, ssh-agent, ~/.ssh/config and jump hosts all apply. The
                   app never reads the private key. BatchMode means it never
                   prompts for a password: key-based login only.
  * LocalBackend — this computer, inside a folder. With fake Slurm on PATH it is
                   the demo cluster; without it, it runs local modules.

Both expose: run, read_bytes, write_bytes, listdir, exists, tunnel, close.
"""
from __future__ import annotations

import os
import shlex
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Entry:
    name: str
    is_dir: bool
    size: int


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Backend:
    label = "cluster"
    user = "unknown"

    def run(self, cmd: str, timeout: float = 60, stdin: bytes | None = None) -> tuple[int, str, str]:
        raise NotImplementedError

    def read_bytes(self, path: str) -> bytes:
        rc, out, err = self.run_bytes(f"cat {shlex.quote(path)}")
        if rc:
            raise FileNotFoundError(f"{path}: {err.strip()}")
        return out

    def read_text(self, path: str) -> str:
        return self.read_bytes(path).decode()

    def write_bytes(self, path: str, data: bytes) -> None:
        q = shlex.quote(path)
        rc, _, err = self.run(f"mkdir -p $(dirname {q}) && cat > {q}", stdin=data)
        if rc:
            raise OSError(f"could not write {path}: {err.strip()}")

    def write_text(self, path: str, text: str) -> None:
        self.write_bytes(path, text.encode())

    def exists(self, path: str) -> bool:
        return self.run(f"test -e {shlex.quote(path)}")[0] == 0

    def listdir(self, path: str) -> list[Entry]:
        # Intent: portable listing (type, size, name), one entry per line.
        cmd = (f"cd {shlex.quote(path)} && for f in * .[!.]*; do [ -e \"$f\" ] || continue; "
               "if [ -d \"$f\" ]; then t=d; s=0; else t=f; s=$(wc -c < \"$f\" | tr -d ' '); fi; "
               "printf '%s\\t%s\\t%s\\n' \"$t\" \"$s\" \"$f\"; done")
        rc, out, err = self.run(cmd)
        if rc:
            raise FileNotFoundError(f"{path}: {err.strip() or 'not a folder'}")
        rows = [line.split("\t", 2) for line in out.splitlines() if line.count("\t") >= 2]
        return sorted((Entry(n, t == "d", int(s)) for t, s, n in rows), key=lambda e: (not e.is_dir, e.name.lower()))

    def run_bytes(self, cmd: str, timeout: float = 120) -> tuple[int, bytes, str]:
        raise NotImplementedError

    def tunnel(self, node: str, remote_port: int) -> int:
        """Forward a local port to node:remote_port; returns the local port."""
        raise NotImplementedError

    def close(self) -> None:
        pass


class LocalBackend(Backend):
    """This computer: a working folder, optionally with fake Slurm commands (the demo cluster)."""

    def __init__(self, root: Path, fake_slurm_bin: Path | None = None, label: str = "this computer"):
        self.root = root
        self.label = label
        self.env = dict(os.environ)
        if fake_slurm_bin:
            self.env["PATH"] = f"{fake_slurm_bin}{os.pathsep}{self.env.get('PATH', '')}"
            self.env["FAKE_SLURM_HOME"] = str(root / ".slurm")
        # Intent: jobs import this same copy of Everyome, as they would from a cluster install.
        self.env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(Path(__file__).resolve().parents[2]), self.env.get("PYTHONPATH")]))
        self.user = os.environ.get("USER", "user")
        self.host = "localhost"

    def run(self, cmd, timeout=60, stdin=None):
        p = subprocess.run(["bash", "-c", cmd], cwd=self.root, env=self.env, input=stdin,
                           capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")

    def run_bytes(self, cmd, timeout=120):
        p = subprocess.run(["bash", "-c", cmd], cwd=self.root, env=self.env, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr.decode(errors="replace")

    def tunnel(self, node, remote_port):
        return remote_port          # same machine: nothing to forward


class SSHBackend(Backend):
    """Real cluster over OpenSSH with connection sharing (one login, many commands)."""

    def __init__(self, host: str, user: str, port: int = 22, ssh_options: list[str] | None = None):
        self.host, self.user, self.port = host, user, port
        self.label = f"{user}@{host}"
        ctl = Path.home() / ".ssh" / "everyome-%r@%h-%p"
        (Path.home() / ".ssh").mkdir(mode=0o700, exist_ok=True)
        # Intent: share one login across commands (not supported by Windows' OpenSSH).
        share = [] if os.name == "nt" else ["-o", "ControlMaster=auto", "-o", f"ControlPath={ctl}", "-o", "ControlPersist=15m"]
        self.base = ["ssh", "-p", str(port), "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", *share,
                     "-o", "ServerAliveInterval=30", *(ssh_options or []), f"{user}@{host}"]
        self.tunnels: list[subprocess.Popen] = []

    def _ssh(self, cmd, stdin=None, timeout=60):
        # Intent: run under a login shell so the user's cluster PATH (Slurm, modules) is set.
        return subprocess.run([*self.base, f"bash -lc {shlex.quote(cmd)}"], input=stdin, capture_output=True, timeout=timeout)

    def run(self, cmd, timeout=60, stdin=None):
        p = self._ssh(cmd, stdin, timeout)
        return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")

    def run_bytes(self, cmd, timeout=120):
        p = self._ssh(cmd, None, timeout)
        return p.returncode, p.stdout, p.stderr.decode(errors="replace")

    def tunnel(self, node, remote_port):
        lport = free_port()
        args = [a for a in self.base if a != f"{self.user}@{self.host}"]
        proc = subprocess.Popen([*args, "-N", "-o", "ExitOnForwardFailure=yes",
                                 "-L", f"127.0.0.1:{lport}:{node}:{remote_port}", f"{self.user}@{self.host}"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.tunnels.append(proc)
        return lport

    def close(self):
        for t in self.tunnels:
            t.terminate()
        subprocess.run([*self.base[:-1], "-O", "exit", f"{self.user}@{self.host}"], capture_output=True)


def describe_ssh_error(err: str) -> str:
    """Turn common ssh failures into plain-language advice."""
    e = err.lower()
    if "permission denied" in e:
        return "The cluster refused your key. Check that your SSH key is added to the cluster and loaded (ssh-add)."
    if "could not resolve" in e or "name or service not known" in e:
        return "That cluster address could not be found. Check the host name, and that you are on the institute network or VPN."
    if "timed out" in e or "no route" in e:
        return "The cluster did not answer. Check you are on the institute network or VPN."
    if "host key verification failed" in e:
        return "Your computer has not seen this cluster before. Log in once from a terminal to accept its host key, or ask IT."
    return err.strip() or "Connection failed."
