"""The module manifest (module.yaml), spec version 1.

A manifest tells the core everything it needs to show and run a module: its
inputs and settings (with defaults, ranges and plain-language help), its batch
stages, its interactive steps, and where its manual and demo data live. The GUI
builds its forms from it, so every setting is editable without new screens.

See docs/PLAN.md section 4. Bump SPEC when a change would break existing modules.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SPEC = 1
KINDS = {"local", "batch", "interactive"}
TYPES = {"text", "longtext", "int", "float", "bool", "choice", "file", "folder", "table"}
ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


class ManifestError(ValueError):
    """A module.yaml that does not follow the spec; the message says what to fix."""


@dataclass
class Field:
    id: str
    label: str
    type: str = "text"
    default: object = None
    help: str = ""
    required: bool = False
    min: float | None = None
    max: float | None = None
    choices: list = field(default_factory=list)
    group: str = ""
    demo: str = ""            # demo-data file or folder filled in on the demo cluster
    columns: list = field(default_factory=list)   # table: [{id, label, pattern?, help?}]
    fill: dict = field(default_factory=dict)      # table: {helper, from, label} fills rows from another input
    one_of: list = field(default_factory=list)    # table: [[col, col], ...] each row fills at least one column of each group
    advanced: bool = False    # shown under "Advanced" (for example, parameters a pipeline marks as hidden)
    pipeline: bool = False    # passed to the Nextflow pipeline as a parameter

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Stage:
    id: str
    name: str
    title: str
    run: str
    resources: dict = field(default_factory=dict)


@dataclass
class Step:
    id: str
    title: str


@dataclass
class Manifest:
    id: str
    name: str
    suite: str
    version: str
    summary: str
    kind: list[str]
    dir: Path
    authors: list[str] = field(default_factory=list)
    licence: str = ""
    cite: list[dict] = field(default_factory=list)
    inputs: list[Field] = field(default_factory=list)
    params: list[Field] = field(default_factory=list)
    resources: dict = field(default_factory=dict)
    stages: list[Stage] = field(default_factory=list)
    engine: str = ""
    ui: list = field(default_factory=list)   # the module's GUI views: JS files, loaded in order (shared views first)
    steps: list[Step] = field(default_factory=list)
    learn: dict = field(default_factory=dict)
    demo: dict = field(default_factory=dict)
    helpers: dict = field(default_factory=dict)   # name -> "package.module:function(backend, **args)", run on the app side
    report: str = ""          # "package.module:function(backend, run)": summary shown when the batch stages finish
    requires: list[str] = field(default_factory=list)   # Python packages the cluster's Python must have
    tools: list[dict] = field(default_factory=list)     # [{name, version: shell command}] recorded in the run record
    methods: str = ""         # "package.module:function(record) -> str": draft methods text for the write-up
    nextflow: dict = field(default_factory=dict)  # batch.engine nextflow: pipeline, revision, schema, samplesheet, profile, demo
    source: str = "everyome"  # everyome (shipped), community (reviewed and signed) or unreviewed (an author's own folder)
    review: dict = field(default_factory=dict)    # community: who reviewed it and when, from the signed registry index
    containers: dict = field(default_factory=dict)  # staged: {name: repository:tag@sha256:digest} the stages run their tools in
    check: str = ""           # "package.module:function(values, demo) -> [problems]": refuses a run before anything is written

    @property
    def fields(self) -> list[Field]:
        return self.inputs + self.params

    def as_dict(self):
        """What the GUI needs (no file-system paths)."""
        return {"id": self.id, "name": self.name, "suite": self.suite, "version": self.version, "summary": self.summary,
                "kind": self.kind, "authors": self.authors, "licence": self.licence, "cite": self.cite,
                "source": self.source, "review": {k: self.review.get(k) for k in ("reviewed_by", "reviewed_at") if self.review.get(k)},
                "inputs": [f.as_dict() for f in self.inputs], "params": [f.as_dict() for f in self.params],
                "resources": self.resources,
                "stages": [{"id": s.id, "name": s.name, "title": s.title} for s in self.stages],
                "steps": [s.__dict__ for s in self.steps], "has_manual": bool(self.learn.get("manual")), "has_ui": bool(self.ui),
                "helpers": sorted(self.helpers), "has_report": bool(self.report), "requires": self.requires,
                "guides": sorted((self.learn.get("guides") or {})),
                "batch_engine": "nextflow" if self.nextflow else ("staged" if self.stages else ""),
                "pipeline": {k: self.nextflow.get(k) for k in ("pipeline", "revision", "profile")} if self.nextflow else None,
                "containers": self.containers,
                "playground": ({**{k: v for k, v in self.learn["playground"].items() if k != "scripts"},
                                "n_scripts": len(self.learn["playground"]["scripts"]),
                                # Intent: a fingerprint per script, so a file two modules share loads once in the page.
                                "script_keys": [hashlib.sha256((self.dir / s).read_bytes()).hexdigest()[:16]
                                                for s in self.learn["playground"]["scripts"]]}
                               if self.learn.get("playground") else None)}


def _field(d: dict, where: str) -> Field:
    if not isinstance(d, dict) or "id" not in d:
        raise ManifestError(f"{where}: every entry needs an id")
    f = Field(**{k: v for k, v in d.items() if k in Field.__dataclass_fields__})
    if not re.match(r"^[a-z][a-z0-9_]*$", f.id):
        raise ManifestError(f"{where}.{f.id}: ids use lower case letters, digits and _")
    if f.type not in TYPES:
        raise ManifestError(f"{where}.{f.id}: type must be one of {', '.join(sorted(TYPES))}")
    if f.type == "choice" and not f.choices:
        raise ManifestError(f"{where}.{f.id}: a choice needs a list of choices")
    if f.type == "table":
        if not f.columns or not all(isinstance(c, dict) and c.get("id") and c.get("label") for c in f.columns):
            raise ManifestError(f"{where}.{f.id}: a table needs columns, each with an id and a label")
        if not all(isinstance(g, list) and set(g) <= {c["id"] for c in f.columns} for g in f.one_of):
            raise ManifestError(f"{where}.{f.id}: one_of lists groups of this table's column ids")
        for c in f.columns:
            if c.get("pattern"):
                try:
                    re.compile(c["pattern"])
                except re.error:
                    raise ManifestError(f"{where}.{f.id}: column {c['id']} has a pattern that is not a valid regular expression")
    if not f.label:
        raise ManifestError(f"{where}.{f.id}: give it a label people will read")
    if f.default is not None:
        _, err = coerce(f, f.default)
        if err:
            raise ManifestError(f"{where}.{f.id}: default {f.default!r} is not valid ({err})")
    return f


def load(path: Path) -> Manifest:
    """Read and check a module.yaml; raises ManifestError with a plain explanation."""
    path = Path(path)
    try:
        d = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise ManifestError(f"{path}: not valid YAML ({e})")
    if d.get("spec") != SPEC:
        raise ManifestError(f"{path}: spec must be {SPEC} (found {d.get('spec')!r})")
    for k in ("id", "name", "suite", "version", "summary", "kind"):
        if not d.get(k):
            raise ManifestError(f"{path}: missing {k}")
    if not ID.match(d["id"]):
        raise ManifestError(f"{path}: id {d['id']!r} should look like suite.name (lower case)")
    kind = d["kind"] if isinstance(d["kind"], list) else [d["kind"]]
    if not set(kind) <= KINDS:
        raise ManifestError(f"{path}: kind must be from {', '.join(sorted(KINDS))}")
    batch, inter = d.get("batch") or {}, d.get("interactive") or {}
    m = Manifest(id=d["id"], name=d["name"], suite=d["suite"], version=str(d["version"]), summary=d["summary"].strip(),
                 kind=kind, dir=path.parent, authors=d.get("authors", []), licence=d.get("licence", ""), cite=d.get("cite", []),
                 inputs=[_field(x, "inputs") for x in d.get("inputs", [])], params=[_field(x, "params") for x in d.get("params", [])],
                 resources=batch.get("resources", {}), engine=inter.get("engine", ""), ui=[inter["ui"]] if isinstance(inter.get("ui"), str) else list(inter.get("ui") or []),
                 steps=[Step(s["id"], s["title"]) for s in inter.get("steps", [])],
                 learn=d.get("learn", {}), demo=d.get("demo", {}), helpers=d.get("helpers", {}),
                 report=batch.get("report", ""), requires=d.get("requires", []),
                 tools=d.get("tools", []), methods=d.get("methods", ""), check=batch.get("check", ""))
    ids = [f.id for f in m.fields]
    if len(ids) != len(set(ids)):
        raise ManifestError(f"{path}: input and setting ids must be unique")
    if "batch" in kind and batch.get("engine") == "nextflow":
        _nextflow(m, batch, path)
    elif "batch" in kind:
        if batch.get("engine", "staged") != "staged":
            raise ManifestError(f"{path}: the batch engine must be 'staged' or 'nextflow'")
        for s in batch.get("stages", []):
            for k in ("id", "name", "title", "run"):
                if not s.get(k):
                    raise ManifestError(f"{path}: every batch stage needs {k}")
            m.stages.append(Stage(str(s["id"]), s["name"], s["title"], s["run"], s.get("resources", {})))
        if not m.stages:
            raise ManifestError(f"{path}: a batch module needs at least one stage")
        from . import containers
        m.containers = dict(batch.get("containers") or {})
        for name, ref in m.containers.items():
            try:
                containers.parse(ref)
            except ValueError as e:
                # Intent: a tag alone can be moved to a different image; only a digest pins it.
                raise ManifestError(f"{path}: batch.containers.{name}: {e}")
    if "local" in kind and len(kind) > 1:
        raise ManifestError(f"{path}: a local module runs only on this computer; it cannot also be batch or interactive")
    if ("interactive" in kind or "local" in kind) and (not m.engine or ":" not in m.engine):
        raise ManifestError(f"{path}: interactive.engine should be 'package.module:ClassName'")
    for k in ("manual",):
        if m.learn.get(k) and not (m.dir / m.learn[k]).exists():
            raise ManifestError(f"{path}: learn.{k} points to a missing file")
    guides = m.learn.get("guides") or {}
    if not isinstance(guides, dict):
        raise ManifestError(f"{path}: learn.guides should map a short name to a Markdown file")
    for key, f in guides.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(key)) or not (m.dir / f).is_file():
            raise ManifestError(f"{path}: guide {key} needs a lower-case name and an existing file ({f})")
    pg = m.learn.get("playground")
    if pg:
        if not pg.get("scripts") or not pg.get("object"):
            raise ManifestError(f"{path}: learn.playground needs scripts (loaded in order) and the object they define")
        for f in pg["scripts"]:
            if not (m.dir / f).is_file():
                raise ManifestError(f"{path}: learn.playground script {f} is missing")
    if not all((m.dir / f).is_file() for f in m.ui):
        raise ManifestError(f"{path}: interactive.ui points to a missing file")
    if m.demo.get("data") and not (m.dir / m.demo["data"]).is_dir():
        raise ManifestError(f"{path}: demo.data points to a missing folder")
    if not all(isinstance(t, dict) and t.get("name") and t.get("version") for t in m.tools):
        raise ManifestError(f"{path}: every entry in tools needs a name and a version command")
    for name, target in {**m.helpers, **({"report": m.report} if m.report else {}), **({"methods": m.methods} if m.methods else {}), **({"batch.check": m.check} if m.check else {}), **({"demo.build": m.demo["build"]} if m.demo.get("build") else {})}.items():
        if ":" not in str(target):
            raise ManifestError(f"{path}: {name} should be 'package.module:function'")
    for f in m.fields:
        if f.fill and (f.fill.get("helper") not in m.helpers or f.fill.get("from") not in ids):
            raise ManifestError(f"{path}: {f.id}.fill needs a helper listed under helpers and an input id in 'from'")
    return m


def _nextflow(m: Manifest, batch: dict, path: Path) -> None:
    """A Nextflow pipeline: one head job; its parameters become fields, read from the pipeline's own schema."""
    from . import nfschema
    for k in ("pipeline", "revision", "schema", "samplesheet"):
        if not batch.get(k):
            raise ManifestError(f"{path}: a nextflow batch needs {k}")
    if str(batch["revision"]) in ("", "latest", "master", "main", "dev"):
        raise ManifestError(f"{path}: pin the pipeline to a release (revision), never a branch")
    from . import pipelines
    if pipelines.key(batch["pipeline"], str(batch["revision"])) not in pipelines.lock():
        raise ManifestError(f"{path}: {batch['pipeline']} {batch['revision']} is not in pipelines.lock.json; "
                            "add it with python -m everyome.core.pipelines build --update-lock")
    try:
        schema = json.loads((m.dir / batch["schema"]).read_text())
    except (FileNotFoundError, ValueError):
        raise ManifestError(f"{path}: batch.schema {batch['schema']} is missing or not JSON")
    sheet = batch["samplesheet"]
    table = next((f for f in m.inputs if f.id == sheet.get("from") and f.type == "table"), None)
    cols = {c["id"] for c in table.columns} if table else set()
    # A column is a table column id, or {name, from: column} (renamed), {name, if_filled: column} (true/false) or {name, value} (fixed).
    srcs = [c if isinstance(c, str) else c.get("from") or c.get("if_filled") for c in sheet.get("columns", []) if isinstance(c, str) or "value" not in c]
    if not table or not srcs or not set(srcs) <= cols or not sheet.get("param"):
        raise ManifestError(f"{path}: batch.samplesheet needs 'from' (a table input), its 'columns' and the pipeline 'param'")
    # Intent: 'fixed' parameters are always passed with the module's value and are not offered as settings (for
    # example, turning off a pipeline's built-in human reference so the user's own genome is used).
    fixed = batch.get("fixed") or {}
    skip = set(batch.get("skip", [])) | {sheet["param"], "outdir"} | set(fixed)
    taken = {f.id for f in m.fields}
    demo, over, upstream = batch.get("demo_values", {}), batch.get("defaults", {}), {}
    for f in nfschema.fields(schema, skip):
        if f.id in taken:
            raise ManifestError(f"{path}: pipeline parameter {f.id} clashes with a module input or setting")
        f.demo = demo.get(f.id, "")
        if f.id in over:
            # Intent: a module may start from a better default than the pipeline's own (for example, a protocol the
            # default aligner needs); the pipeline's default is kept so the parameter file stays complete.
            upstream[f.id] = f.default
            f.default = over[f.id]
            f.help = (f.help + " " if f.help else "") + f"Everyome starts from {over[f.id]!r}; the pipeline's own default is {upstream[f.id]!r}."
        m.params.append(f)
    if set(fixed) - {f.id for f in nfschema.fields(schema, set())}:
        raise ManifestError(f"{path}: batch.fixed names unknown pipeline parameters: {', '.join(sorted(set(fixed) - {f.id for f in nfschema.fields(schema, set())}))}")
    if set(over) - {f.id for f in m.params}:
        raise ManifestError(f"{path}: batch.defaults names unknown pipeline parameters: {', '.join(sorted(set(over) - {f.id for f in m.params}))}")
    m.report = batch.get("report", m.report)
    gpu = batch.get("gpu") or {}
    if gpu and not ({"param", "profile", "label"} <= set(gpu) and gpu["param"] in {f.id for f in m.params}
                    and (not gpu.get("partition") or gpu["partition"] in {f.id for f in m.params})):
        raise ManifestError(f"{path}: batch.gpu needs param (a pipeline setting), profile and label, and partition if given must be a setting")
    m.nextflow = {k: batch.get(k) for k in ("pipeline", "revision", "schema", "samplesheet", "profile", "demo", "gpu")}
    m.nextflow["upstream"] = upstream
    m.nextflow["fixed"] = dict(fixed)
    m.nextflow["profile"] = m.nextflow.get("profile") or "apptainer"
    m.stages = [Stage("01", "pipeline", f"Run {batch['pipeline']} {batch['revision']}", run="")]


def coerce(f: Field, v) -> tuple[object, str]:
    """Turn a form value into the field's type; returns (value, error message or '')."""
    if f.type == "table":
        return _coerce_table(f, v)
    if v is None or v == "":
        # Intent: a required setting with a default (such as a pipeline's starting step) falls back to it.
        return (None, "required") if f.required and f.default in (None, "") else (f.default, "")
    if f.type in ("int", "float") and isinstance(v, bool):
        return None, f"should be a {'whole number' if f.type == 'int' else 'number'}"
    try:
        if f.type == "int":
            v = int(v)
        elif f.type == "float":
            v = float(v)
        elif f.type == "bool":
            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        else:
            v = str(v).strip()
    except ValueError:
        return None, f"should be a {'whole number' if f.type == 'int' else 'number'}"
    if f.type in ("int", "float"):
        if f.min is not None and v < f.min:
            return None, f"must be at least {f.min:g}"
        if f.max is not None and v > f.max:
            return None, f"must be at most {f.max:g}"
    if f.type == "choice" and v not in [str(c) for c in f.choices]:
        return None, "is not one of the choices"
    return v, ""


def _coerce_table(f: Field, v) -> tuple[object, str]:
    rows = v if isinstance(v, list) else []
    if v not in (None, "") and not isinstance(v, list):
        return None, "should be a table"
    ids = [c["id"] for c in f.columns]
    out = []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            return None, f"row {i} is not a table row"
        row = {c: str(r.get(c, "")).strip() for c in ids}
        if not any(row.values()):
            continue                                  # ignore blank rows
        for c in f.columns:
            if not row[c["id"]]:
                if c.get("optional"):
                    continue
                return None, f"row {i} is missing {c['label']}"
            if c.get("pattern") and not re.fullmatch(c["pattern"], row[c["id"]]):
                return None, f"row {i}: {c['label']} '{row[c['id']]}' {c.get('pattern_help') or 'is not in the expected form'}"
        for g in f.one_of:
            if not any(row[c] for c in g):
                labels = [next(c["label"] for c in f.columns if c["id"] == x) for x in g]
                return None, f"row {i} needs at least one of: {', '.join(labels)}"
        out.append(row)
    if f.required and not out:
        return None, "needs at least one row"
    return (out or (f.default if f.default is not None else [])), ""


def check_values(m: Manifest, values: dict) -> tuple[dict, dict]:
    """All inputs and settings with defaults filled in, plus {id: problem} for anything invalid."""
    out, errors = {}, {}
    for f in m.fields:
        v, err = coerce(f, values.get(f.id))
        if err:
            errors[f.id] = f"{f.label} {err}."
        out[f.id] = v
    return out, errors
