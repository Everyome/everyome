"""Command line for authors and registry maintainers.

  python -m everyome.registry check FOLDER [--markdown]      automated checks (authors run this first)
  python -m everyome.registry pack FOLDER OUT_DIR             reproducible archive of a module
  python -m everyome.registry sign FILE --key KEY             sign with your SSH key (maintainers)
  python -m everyome.registry verify FILE --signers FILE --identity ID
  python -m everyome.registry approve REGISTRY FOLDER --reviewer NAME --key KEY [--notes TEXT]
                                                              check, pack, sign and record one approval
  python -m everyome.registry revoke REGISTRY ID [--version V] --reason TEXT
  python -m everyome.registry index REGISTRY --key KEY        rebuild and sign index.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bundle, checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m everyome.registry", description="Everyome community module registry tools.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("folder"); c.add_argument("--markdown", action="store_true")
    p = sub.add_parser("pack"); p.add_argument("folder"); p.add_argument("out")
    s = sub.add_parser("sign"); s.add_argument("file"); s.add_argument("--key", required=True)
    v = sub.add_parser("verify"); v.add_argument("file"); v.add_argument("--signers", required=True); v.add_argument("--identity", required=True)
    a = sub.add_parser("approve"); a.add_argument("registry"); a.add_argument("folder"); a.add_argument("--reviewer", required=True)
    a.add_argument("--key", required=True); a.add_argument("--notes", default="")
    r = sub.add_parser("revoke"); r.add_argument("registry"); r.add_argument("id"); r.add_argument("--version"); r.add_argument("--reason", required=True)
    i = sub.add_parser("index"); i.add_argument("registry"); i.add_argument("--key", required=True)
    ns = ap.parse_args(argv)

    if ns.cmd == "check":
        rep = checks.check(Path(ns.folder))
        print(checks.markdown(rep) if ns.markdown else json.dumps(rep, indent=1))
        return 0 if rep["ok"] else 1
    if ns.cmd == "pack":
        rep = checks.check(Path(ns.folder))
        if not rep["ok"]:
            print(checks.markdown(rep)); return 1
        print(bundle.pack(Path(ns.folder), Path(ns.out), rep["id"], rep["info"]["version"]))
        return 0
    if ns.cmd == "sign":
        print(bundle.sign(Path(ns.file), Path(ns.key)))
        return 0
    if ns.cmd == "verify":
        ok = bundle.verify(Path(ns.file), Path(ns.file + ".sig"), Path(ns.signers), ns.identity)
        print("Signature good." if ok else "Signature NOT valid for this identity.")
        return 0 if ok else 1
    if ns.cmd == "approve":
        rep = checks.check(Path(ns.folder))
        if not rep["ok"]:
            print(checks.markdown(rep)); return 1
        reg = Path(ns.registry)
        arc = bundle.pack(Path(ns.folder), reg / "archives", rep["id"], rep["info"]["version"])
        bundle.sign(arc, Path(ns.key))
        print(bundle.approve(reg, arc, rep, ns.reviewer, ns.notes))
        print("Now rebuild and sign the index: python -m everyome.registry index", reg, "--key KEY")
        return 0
    if ns.cmd == "revoke":
        f = Path(ns.registry) / "revoked.json"
        rows = json.loads(f.read_text()) if f.exists() else []
        rows.append({"id": ns.id, "version": ns.version, "reason": ns.reason})
        f.write_text(json.dumps(rows, indent=1))
        print(f"Withdrawn {ns.id} {ns.version or '(all versions)'}. Now rebuild and sign the index.")
        return 0
    if ns.cmd == "index":
        out = bundle.build_index(Path(ns.registry))
        print(bundle.sign(out, Path(ns.key)))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
