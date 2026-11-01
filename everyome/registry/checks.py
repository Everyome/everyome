"""Automated checks for a module submitted to the community registry.

check(folder) returns a report: failures stop a submission; warnings must be
looked at by a human reviewer (they are often fine, but they are where harm
would hide). The report is also written as Markdown for the pull request.

These checks never run the module's code. Its own tests run separately, in CI.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from everyome.core import suites
from everyome.core.manifest import ManifestError, load

# Intent: open-source licences only, so anyone may read, run and fix a module (SPDX identifiers).
LICENCES = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "MPL-2.0", "LGPL-2.1-or-later", "LGPL-3.0-or-later",
            "GPL-2.0-or-later", "GPL-3.0-or-later", "AGPL-3.0-or-later"}
MAX_BYTES = 20 * 1024 ** 2
BINARY = {".so", ".dylib", ".dll", ".exe", ".bin", ".pyc", ".pyo", ".jar", ".whl", ".egg", ".zip", ".tar", ".gz", ".bz2", ".7z"}
ALLOWED_DATA = {".fa", ".fasta", ".fna", ".gb", ".gbk", ".gff", ".gtf", ".csv", ".tsv", ".txt", ".json", ".yaml", ".yml", ".md",
                ".js", ".py", ".css", ".svg", ".png", ".bed", ".sam", ".vcf", ".fastq", ".fq"}
NETWORK = {"requests", "urllib", "urllib3", "http", "httpx", "socket", "ftplib", "smtplib", "aiohttp", "paramiko", "telnetlib"}
RISKY_CALLS = {"eval", "exec", "compile", "__import__"}
RISKY_ATTRS = {("os", "system"), ("os", "popen"), ("subprocess", "run"), ("subprocess", "Popen"), ("subprocess", "call"),
               ("subprocess", "check_output"), ("shutil", "rmtree"), ("os", "remove"), ("os", "unlink"), ("importlib", "import_module")}
SECRETS = [r"\.ssh", r"id_rsa", r"id_ed25519", r"\.pypirc", r"\.netrc", r"\.aws", r"TOKEN", r"PASSWORD", r"SECRET"]


def package_name(module_id: str) -> str:
    """The Python package a community module's code must live in, so it cannot clash with Everyome or other modules."""
    return "everyome_c_" + module_id.replace(".", "_")


def _py_findings(path: Path, rel: str) -> list[str]:
    out = []
    try:
        tree = ast.parse(path.read_text(), filename=rel)
    except SyntaxError as e:
        return [f"FAIL {rel}: not valid Python ({e.msg}, line {e.lineno})"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                if n.split(".")[0] in NETWORK:
                    out.append(f"WARN {rel}:{node.lineno}: imports {n} (network access)")
                if n.split(".")[0] == "subprocess":
                    out.append(f"WARN {rel}:{node.lineno}: imports subprocess (runs other programs)")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in RISKY_CALLS:
                out.append(f"WARN {rel}:{node.lineno}: calls {f.id}() (runs code built at run time)")
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id, f.attr) in RISKY_ATTRS:
                out.append(f"WARN {rel}:{node.lineno}: calls {f.value.id}.{f.attr}()")
            if isinstance(f, ast.Attribute) and f.attr == "home":
                out.append(f"WARN {rel}:{node.lineno}: reads the user's home folder")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr == "environ":
            out.append(f"WARN {rel}:{node.lineno}: reads environment variables")
    return out


def check(folder: Path) -> dict:
    folder = Path(folder)
    fails, warns, info = [], [], {}
    try:
        m = load(folder / "module.yaml")
    except (ManifestError, FileNotFoundError) as e:
        return {"ok": False, "id": None, "failures": [f"module.yaml: {e}"], "warnings": [], "info": {}}
    pkg = package_name(m.id)
    info.update(id=m.id, version=m.version, name=m.name, kind=m.kind, licence=m.licence, package=pkg)

    # ---- identity and scope
    if not m.id.startswith("community."):
        fails.append(f"community module ids start with 'community.' (for example community.{m.id.split('.')[-1]}), so they never clash with Everyome's own")
    if not re.fullmatch(r"\d+\.\d+\.\d+((a|b|rc)\d+)?", m.version):
        fails.append(f"version {m.version!r} should look like 1.2.0 (or 1.2.0a1 for a pre-release)")
    if m.suite not in {s["id"] for s in suites.load()["suites"]}:
        fails.append(f"suite {m.suite!r} is not one of Everyome's suites")
    if m.kind != ["local"]:
        fails.append("for now, community modules must run on this computer (kind: [local]); cluster modules need their code "
                     "installed on each cluster, which the registry does not do yet")
    if m.licence not in LICENCES:
        fails.append(f"licence {m.licence!r} is not an open-source licence Everyome accepts ({', '.join(sorted(LICENCES))})")

    # ---- learning layer, as for Everyome's own modules
    if not m.learn.get("manual"):
        fails.append("needs a manual (learn.manual)")
    if not (m.demo.get("data") or m.demo.get("build")):
        fails.append("needs example data (demo.data)")
    if not m.learn.get("playground"):
        fails.append("needs a playground (learn.playground)")
    if not m.learn.get("guides"):
        fails.append("needs at least one 'how to read this' guide (learn.guides)")
    if m.ui:
        used = set(re.findall(r'guide\("([a-z0-9_]+)"', "".join((m.dir / f).read_text() for f in m.ui)))
        if used - set(m.learn.get("guides") or {}):
            fails.append(f"views ask for guides that do not exist: {', '.join(sorted(used - set(m.learn.get('guides') or {})))}")

    named = list(m.ui) + [m.learn.get("manual") or ""] + list((m.learn.get("playground") or {}).get("scripts", [])) + \
        list((m.learn.get("guides") or {}).values()) + [m.demo.get("data") or ""]
    outside = [f for f in filter(None, named) if not (folder / f).resolve().is_relative_to(folder.resolve())]
    if outside:
        fails.append(f"files must be inside the module's folder: {', '.join(outside)}")

    # ---- code lives in its own package
    refs = [m.engine] + list(m.helpers.values()) + [m.methods, m.report, m.demo.get("build", "")]
    for ref in filter(None, refs):
        if not ref.split(":")[0].startswith(pkg + ".") and ref.split(":")[0] != pkg:
            fails.append(f"{ref} must be inside the module's own package, {pkg}")
    if not (folder / pkg / "__init__.py").is_file():
        fails.append(f"put the module's Python code in a package folder named {pkg}/ (with __init__.py)")
    if m.helpers:
        warns.append("declares helpers, which run inside the app with the user's connection: read them closely")

    # ---- tests
    tests = sorted((folder / "tests").glob("test_*.py")) if (folder / "tests").is_dir() else []
    if not tests:
        fails.append("needs tests (tests/test_*.py) that run on the example data")

    # ---- files: no binaries, nothing huge, nothing hidden
    total, n = 0, 0
    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(folder))
        n += 1
        total += f.stat().st_size
        if any(part.startswith(".") for part in f.relative_to(folder).parts):
            fails.append(f"{rel}: hidden files are not allowed")
        elif f.suffix.lower() in BINARY:
            fails.append(f"{rel}: compiled or archive files are not allowed; submit source only")
        elif f.suffix.lower() not in ALLOWED_DATA and f.name != "LICENSE":
            warns.append(f"{rel}: unusual file type, check what it is")
        if f.suffix == ".py":
            for line in _py_findings(f, rel):
                (fails if line.startswith("FAIL") else warns).append(line[5:])
        if f.suffix in {".py", ".js", ".yaml", ".yml"}:
            text = f.read_text(errors="replace")
            for pat in SECRETS:
                if re.search(pat, text):
                    warns.append(f"{rel}: mentions {pat.replace(chr(92), '')} (could touch credentials)")
            if f.suffix == ".js" and re.search(r"\b(fetch|XMLHttpRequest|WebSocket|navigator\.sendBeacon)\b", text):
                warns.append(f"{rel}: makes web requests from the browser; they should only go to Everyome's own /api")
    if total > MAX_BYTES:
        fails.append(f"the module is {total / 1e6:.1f} MB; the limit is {MAX_BYTES / 1e6:.0f} MB (keep example data small)")
    if not (folder / "LICENSE").is_file():
        fails.append("needs a LICENSE file with the licence text")
    info.update(files=n, bytes=total, tests=len(tests))
    return {"ok": not fails, "id": m.id, "failures": fails, "warnings": sorted(set(warns)), "info": info}


def markdown(report: dict) -> str:
    """The report as a pull-request comment."""
    i = report["info"]
    head = f"## Automated checks: {'passed' if report['ok'] else 'FAILED'}\n\n"
    if i:
        head += f"**{i.get('name')}** (`{i.get('id')}` {i.get('version')}), {i.get('licence')}, {i.get('files')} files, {i.get('bytes', 0) / 1e3:.0f} KB, {i.get('tests')} test files.\n\n"
    body = ""
    if report["failures"]:
        body += "### Must fix\n\n" + "".join(f"- {x}\n" for x in report["failures"]) + "\n"
    if report["warnings"]:
        body += "### For the reviewer to look at\n\n" + "".join(f"- {x}\n" for x in report["warnings"]) + "\n"
    if not report["failures"] and not report["warnings"]:
        body += "Nothing to flag. A reviewer still reads the code and works through the review checklist.\n"
    return head + body
