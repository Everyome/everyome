"""Forms from a Nextflow pipeline's parameter schema (nextflow_schema.json, nf-core style).

Every parameter the pipeline accepts becomes an Everyome field in its group,
with the pipeline's own default, description and allowed values, so nothing is
hidden. Parameters the pipeline marks as hidden are shown under "Advanced".
Parameters Everyome sets itself (input, outdir and the like) are skipped.
"""
from __future__ import annotations

import re

from .manifest import Field

FORMATS = {"file-path": "file", "directory-path": "folder", "path": "file"}


def _label(name: str) -> str:
    words = name.replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def _help(p: dict) -> str:
    # Intent: one plain sentence from the pipeline's description, without Markdown links or code marks.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", p.get("description", "")).replace("`", "").strip()
    return text


def field_for(name: str, p: dict, group: str, required: bool) -> Field | None:
    t = p.get("type")
    if isinstance(t, list):                       # e.g. ["boolean", "string"]: offer it as text
        t = "string"
    if "enum" in p:
        kind = "choice"
    elif t == "boolean":
        kind = "bool"
    elif t == "integer":
        kind = "int"
    elif t == "number":
        kind = "float"
    elif t == "string":
        kind = FORMATS.get(p.get("format"), "text")
    else:
        return None
    f = Field(id=name, label=_label(name), type=kind, default=p.get("default"), help=_help(p), required=required,
              min=p.get("minimum"), max=p.get("maximum"), choices=[str(c) for c in p.get("enum", [])], group=group,
              advanced=bool(p.get("hidden")), pipeline=True)
    if kind == "bool" and f.default is None:
        f.default = False                         # Intent: in nf-core, a yes/no setting with no default is off
    if kind == "choice" and f.default is not None:
        f.default = str(f.default)
    if kind == "choice" and not required and f.default is None:
        f.choices = [""] + f.choices              # Intent: an empty choice means "leave it to the pipeline"
    return f


def fields(schema: dict, skip: set[str]) -> list[Field]:
    defs = schema.get("$defs") or schema.get("definitions") or {}
    order = [a["$ref"].split("/")[-1] for a in schema.get("allOf", []) if "$ref" in a] or list(defs)
    out = []
    for gid in order:
        g = defs.get(gid, {})
        req = set(g.get("required", []))
        for name, p in g.get("properties", {}).items():
            if name in skip:
                continue
            f = field_for(name, p, g.get("title", gid), name in req)
            if f:
                out.append(f)
    return out
