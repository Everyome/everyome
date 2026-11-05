"""Small pieces of methods text that every module writes the same way.

Modules build their own draft methods (each module's methods.py) from the run record; these helpers keep the
shared sentences identical across modules. Kept free of heavy imports, because records are written in the app.
"""
from __future__ import annotations


def last(history: list, action: str, prefix: bool = False):
    """The most recent session decision with this action (or, with prefix=True, starting with it), or None."""
    hits = [h for h in history if (h["action"].startswith(action) if prefix else h["action"] == action)]
    return hits[-1] if hits else None


def nextflow_cite(rec: dict) -> str:
    """ (Nextflow 25.10.4; Di Tommaso et al., 2017), or just the citation when the version wasn't recorded."""
    nf = ((rec.get("software") or {}).get("tools") or {}).get("nextflow")
    return f" (Nextflow {nf.split()[-1]}; Di Tommaso et al., 2017)" if nf else " (Di Tommaso et al., 2017)"


def pipeline_name(rec: dict, default: str) -> tuple[str, str]:
    """(pipeline, revision) as recorded, falling back to the module's pipeline name."""
    pipe = rec.get("pipeline") or {}
    return pipe.get("pipeline", default), pipe.get("revision", "")


def changed_settings(rec: dict, exclude=(), lead: str = "Other pipeline settings changed from their defaults: ") -> str:
    """One sentence listing settings changed from their defaults (skipping those the text already describes), or ''."""
    changed = [x for x in rec["settings"] if x["changed"] and x["id"] not in exclude]
    return (lead + "; ".join(f"{x['id']} = {x['value']}" for x in changed) + ".") if changed else ""


def setting(rec: dict, key: str, default=None):
    """A setting's value from the record, or the default."""
    s = next((x for x in rec["settings"] if x["id"] == key), None)
    return (s or {}).get("value") or default


def table(rec: dict, key: str) -> list:
    """A table input's rows from the record."""
    return next((x["value"] for x in rec["inputs"] if x["id"] == key), []) or []


def version(sw: dict, name: str, cite: str = "") -> str:
    """ (version X; Author, year), or just the citation, or nothing: for a Python package or a tool."""
    v = (sw.get("python") or {}).get(name) or (sw.get("tools") or {}).get(name)
    if v:
        # Intent: tools often print their own name first ("samtools 1.21"); keep only the version.
        v = v.split()[-1] if v.lower().startswith(name.lower()) else v
    inside = "; ".join(p for p in (f"version {v}" if v else "", cite) if p)
    return f" ({inside})" if inside else ""


def join_and(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
