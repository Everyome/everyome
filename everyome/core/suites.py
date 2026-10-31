"""Suites, their tools (ready or planned), and suggestions from the user's data and aims.

Everything comes from everyome/suites.yaml. Suggestions are simple rules run on
this computer: no answers are stored or sent anywhere.
"""
from __future__ import annotations

from pathlib import Path

import yaml

FILE = Path(__file__).resolve().parents[1] / "suites.yaml"


def load(path: Path = FILE) -> dict:
    return yaml.safe_load(Path(path).read_text())


def check(cat: dict, modules: dict) -> list[str]:
    """Plain messages for anything in the catalogue that does not line up with the modules."""
    problems, tools = [], {t["id"]: (s["id"], t) for s in cat["suites"] for t in s["tools"]}
    suite_ids = {s["id"] for s in cat["suites"]}
    for tid, (_, t) in tools.items():
        if t.get("module") and t["module"] not in modules:
            problems.append(f"suites.yaml: {tid} points to module {t['module']}, which is not installed")
    for m in modules.values():
        if m.suite not in suite_ids:
            problems.append(f"{m.dir}/module.yaml: suite {m.suite!r} is not one of {', '.join(sorted(suite_ids))}")
        if m.id not in {t.get("module") for _, t in tools.values()}:
            problems.append(f"suites.yaml: module {m.id} is not listed as a tool of any suite")
    for kind in ("data_types", "aims"):
        for x in cat[kind]:
            for tid in x["tools"]:
                if tid not in tools:
                    problems.append(f"suites.yaml: {kind} {x['id']} names unknown tool {tid}")
    return problems


def public(cat: dict, modules: dict) -> dict:
    """The catalogue as the GUI shows it, with each tool marked ready or planned."""
    suites = []
    for s in cat["suites"]:
        tools = [{"id": t["id"], "name": t["name"], "module": t.get("module", ""),
                  "ready": bool(t.get("module")) and t["module"] in modules} for t in s["tools"]]
        suites.append({"id": s["id"], "name": s["name"], "blurb": s["blurb"], "tools": tools,
                       "ready": any(t["ready"] for t in tools)})
    return {"suites": suites, "data_types": [{"id": d["id"], "label": d["label"]} for d in cat["data_types"]],
            "aims": [{"id": a["id"], "label": a["label"]} for a in cat["aims"]]}


def suggest(cat: dict, modules: dict, data: list[str], aims: list[str], limit: int = 6) -> list[dict]:
    """Tools ranked by how well they fit the chosen data types and aims, with a reason for each."""
    pub = public(cat, modules)
    tools = {t["id"]: {**t, "suite": s["id"], "suite_name": s["name"]} for s in pub["suites"] for t in s["tools"]}
    picked_d = [d for d in cat["data_types"] if d["id"] in data and d["id"] != "not_sure"]
    picked_a = [a for a in cat["aims"] if a["id"] in aims]
    # Intent: "Not sure yet" names no data; on its own it points to the worked example.
    if "not_sure" in data and not picked_d and not picked_a:
        picked_d = [d for d in cat["data_types"] if d["id"] == "not_sure"]
    # Intent: once someone names their data, only suggest tools that can use it.
    need_data = bool(picked_d)
    out = []
    for tid, t in tools.items():
        fd = [d["label"] for d in picked_d if tid in d["tools"]]
        fa = [a["label"] for a in picked_a if tid in a["tools"]]
        if (not fd and not fa) or (need_data and not fd):
            continue
        # Intent: a tool that fits both the data and the aim beats one that fits only several data types.
        score = 3 * bool(fd) + 3 * bool(fa) + len(fd) + len(fa)
        reason = " ".join(filter(None, [f"Fits your data: {'; '.join(fd)}." if fd else "",
                                        f"Fits your aim: {'; '.join(fa)}." if fa else ""]))
        out.append({**t, "score": score, "reason": reason, "both": bool(fd) and bool(fa)})
    out.sort(key=lambda t: (-t["score"], not t["ready"], t["name"]))
    return out[:limit]
