"""Live session for alignment and tree building: check the alignment, read the model and support, explore and export the tree.

Works on what the stages wrote under <run>/results (see stage.py). The tree is never changed on disk: the view
(root, collapsed groups, ladderizing, colours) is kept in the session state and applied to the tree file each
time, so every view can be rebuilt exactly. Pure Python, so it runs on any cluster Python with Everyome.
"""
from __future__ import annotations

import csv
import html
import io
import math
import re
from pathlib import Path

from everyome.core.engine import BaseEngine

from . import newick as nw
from .stage import SAFE, read_fasta, tip_names

GAPS = set("-?.")
PALETTE = ["#7a1f2b", "#b8862b", "#2f5d62", "#5b3a6e", "#8c5a2b", "#3f6e3a", "#a34a6b", "#46607f", "#8a7a2a", "#5e5e5e"]


def parse_iqtree(text: str) -> dict:
    """What IQ-TREE's report (.iqtree) says: the data, the chosen model, the model table and the likelihood."""
    def num(pat, cast=float):
        m = re.search(pat, text)
        return cast(m.group(1)) if m else None
    out = {"best_model": (re.search(r"Best-fit model according to (\w+): (\S+)", text) or [None, None, None])[2],
           "criterion": (re.search(r"Best-fit model according to (\w+):", text) or [None, None])[1],
           "model": (re.search(r"Model of substitution: (\S+)", text) or [None, None])[1],
           "sequences": num(r"Input data: (\d+) sequences", int), "sites": num(r"sequences with (\d+) ", int),
           "constant": num(r"Number of constant sites: (\d+)", int), "informative": num(r"Number of parsimony informative sites: (\d+)", int),
           "log_likelihood": num(r"Log-likelihood of the tree: (-?[\d.]+)"), "tree_length": num(r"Total tree length \(sum of branch lengths\): ([\d.]+)"),
           "gamma_alpha": num(r"Gamma shape alpha: ([\d.]+)"), "stand_in": "stand-in" in text[:200], "models": []}
    m = re.search(r"List of models sorted by \w+ scores:\s*\n\s*\n?Model\s+LogL[^\n]*\n(.*?)(\n\s*\n|$)", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            toks = line.split()
            nums = [t for t in toks[1:] if t not in ("+", "-")]
            try:
                logl, aic, waic, aicc, waicc, bic, wbic = (float(x) for x in nums[:7])
            except ValueError:
                continue
            out["models"].append({"model": toks[0], "logl": logl, "aic": aic, "aicc": aicc, "bic": bic, "w_bic": wbic})
    return out


class Engine(BaseEngine):
    API = ("load", "summary", "alignment", "models", "tree", "reroot", "collapse", "expand", "view", "export", "files")
    REPLAY = ("load", "reroot", "collapse", "expand", "view", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        self._meta = None

    def status(self):
        return {**super().status(), "loaded": bool(self.state.get("loaded")), "view": self.state.get("view")}

    # ---------------------------------------------------------------- reading the results
    def _need(self, name: str) -> Path:
        p = self.res / name
        if not p.is_file():
            raise ValueError(f"results/{name} is missing. Check that every stage finished on the Run page.")
        return p

    def _names(self) -> dict:
        p = self.res / "names.tsv"
        rows = p.read_text().splitlines()[1:] if p.is_file() else []
        return dict(r.split("\t", 1) for r in rows if "\t" in r)

    def _kept(self, width: int) -> list[bool]:
        p = self.res / "trim_columns.txt"
        cols = [int(x) for x in re.findall(r"\d+", p.read_text().split("\t", 1)[-1])] if p.is_file() else list(range(width))
        keep = set(cols)
        return [i in keep for i in range(width)]

    def metadata(self) -> dict:
        """{tip: {column: value}} from the optional table; the first column names the sequence."""
        if self._meta is not None:
            return self._meta
        self._meta = {"columns": [], "rows": {}}
        path = self.params.get("metadata")
        if not path:
            return self._meta
        text = Path(path).read_text()
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",\t;")
        rows = list(csv.reader(io.StringIO(text), dialect))
        if len(rows) < 2:
            return self._meta
        head, back = rows[0], {v: k for k, v in self._names().items()}
        for r in rows[1:]:
            if not r or not r[0].strip():
                continue
            key = r[0].strip()
            # Intent: match the table to tips by the tree-safe name, or by the sequence's original header.
            tip = back.get(key) or SAFE.sub("_", key.split()[0]).strip("_")
            self._meta["rows"][tip] = {h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head) if i}
        self._meta["columns"] = head[1:]
        return self._meta

    def load(self):
        """Read the results once and note them for the record."""
        aln, trimmed = read_fasta(self._need("alignment.fasta")), read_fasta(self._need("trimmed.fasta"))
        tree = nw.parse(self._need("tree.treefile").read_text())
        rep = parse_iqtree((self.res / "tree.iqtree").read_text()) if (self.res / "tree.iqtree").is_file() else {}
        kind = (self.res / "sequence_type.txt").read_text().strip() if (self.res / "sequence_type.txt").is_file() else "dna"
        sup = [s for s in (nw.support(n.label) for n in nw.inner_branches(tree)) if s]
        strong = sum(1 for s in sup if nw.strong(s)) if sup else None
        info = {"sequences": len(aln), "type": kind, "columns": len(aln[0][1]) if aln else 0, "kept": len(trimmed[0][1]) if trimmed else 0,
                "model": rep.get("best_model") or rep.get("model"), "selected_by": rep.get("criterion") if rep.get("best_model") else None,
                "log_likelihood": rep.get("log_likelihood"), "informative": rep.get("informative"), "tips": len(tree.tips()),
                "branches_with_support": len(sup), "strong": strong}
        self.state["loaded"] = info
        self.state.setdefault("view", self._default_view(tree))
        self.state["step"] = "loaded"
        self._record("read the alignment and tree", **info)
        return info

    def _default_view(self, tree: nw.Node) -> dict:
        out = tip_names(self.params.get("outgroup"), self.res)
        root = {"how": "midpoint"}
        if out:
            try:
                nw.root_outgroup(tree, out)
                root = {"how": "outgroup", "tips": out}
            except ValueError:
                pass
        cols = self.metadata()["columns"]
        return {"root": root, "collapsed": [], "ladderize": True, "lengths": True, "support": "strong", "colour_by": cols[0] if cols else ""}

    def _loaded(self):
        if not self.state.get("loaded"):
            raise ValueError("Read the results first (the first step).")
        return self.state["loaded"]

    # ---------------------------------------------------------------- alignment
    def summary(self):
        info = self._loaded()
        aln, trimmed = read_fasta(self.res / "alignment.fasta"), dict(read_fasta(self.res / "trimmed.fasta"))
        names, seqs = self._names(), dict(read_fasta(self.res / "sequences.fasta")) if (self.res / "sequences.fasta").is_file() else {}
        width = len(trimmed[next(iter(trimmed))]) if trimmed else 0
        cols = list(zip(*trimmed.values())) if width else []
        cons = ["".join(c).replace("-", "") for c in cols]
        cons = [max(set(c), key=c.count) if c else "-" for c in cons]
        rows = []
        for n, s in aln:
            t = trimmed.get(n, "")
            letters = [(a, b) for a, b in zip(t, cons) if a not in GAPS]
            ident = round(100 * sum(a.upper() == b.upper() for a, b in letters) / len(letters), 1) if letters else None
            rows.append({"name": n, "original": names.get(n, n), "length": len(seqs.get(n, s).replace("-", "")),
                         "gaps": round(100 * sum(c in GAPS for c in s) / max(1, len(s)), 1),
                         "gaps_trimmed": round(100 * sum(c in GAPS for c in t) / max(1, len(t)), 1) if t else 100.0, "identity": ident})
        ids = sorted(r["identity"] for r in rows if r["identity"] is not None)
        med = ids[len(ids) // 2] if ids else 0
        for r in rows:
            # Intent: flag what usually needs a second look, in words; never remove anything automatically.
            r["flag"] = ("no letters left after trimming" if r["gaps_trimmed"] >= 100 else
                         "mostly gaps after trimming (partial or poorly aligned)" if r["gaps_trimmed"] > 50 else
                         "unusually different from the rest" if r["identity"] is not None and r["identity"] < med - 25 else "")
        return {**info, "rows": rows, "removed": info["columns"] - info["kept"]}

    def alignment(self, start: int = 0, width: int = 120, first: int = 0, rows: int = 60):
        """A window of the alignment (before trimming), with the columns trimming kept marked."""
        self._loaded()
        aln = read_fasta(self.res / "alignment.fasta")
        total = len(aln[0][1])
        start, width = max(0, min(int(start), max(total - 1, 0))), max(10, min(int(width), 300))
        kept = self._kept(total)
        sel = aln[int(first):int(first) + max(1, min(int(rows), 200))]
        return {"total": total, "start": start, "width": width, "kept": kept[start:start + width], "kept_all": "".join("1" if k else "0" for k in kept),
                "sequences": len(aln), "first": int(first), "rows": [{"name": n, "seq": s[start:start + width]} for n, s in sel]}

    def models(self):
        self._loaded()
        p = self.res / "tree.iqtree"
        rep = parse_iqtree(p.read_text()) if p.is_file() else {"models": []}
        sup = [s for s in (nw.support(n.label) for n in nw.inner_branches(self._tree_raw())) if s]
        return {**rep, "support": sup, "bootstrap": self.params.get("bootstrap"), "alrt": self.params.get("alrt"),
                "demo": bool(self.run.get("demo"))}

    # ---------------------------------------------------------------- the tree
    def _tree_raw(self) -> nw.Node:
        return nw.parse(self._need("tree.treefile").read_text())

    def _current(self) -> nw.Node:
        v = self.state["view"]
        t, r = self._tree_raw(), v["root"]
        if r["how"] == "midpoint":
            t = nw.root_midpoint(t)
        elif r["how"] == "outgroup":
            t = nw.root_outgroup(t, r["tips"])
        if v["ladderize"]:
            t = nw.ladderize(t)
        return t

    def _shown(self, t: nw.Node) -> list[nw.Node]:
        """Nodes in drawing order (parents first); the inside of collapsed groups is left out."""
        closed = {frozenset(c) for c in self.state["view"]["collapsed"]}
        out, stack = [], [t]
        while stack:
            n = stack.pop()
            out.append(n)
            if n.children and frozenset(n.tips()) not in closed:
                stack.extend(reversed(n.children))
        return out

    def _node(self, node: int) -> tuple[nw.Node, nw.Node]:
        t = self._current()
        shown = self._shown(t)
        if not 0 <= int(node) < len(shown):
            raise ValueError("That branch is not on the tree any more; redraw it and try again.")
        return t, shown[int(node)]

    def tree(self):
        self._loaded()
        v, t = self.state["view"], self._current()
        shown = self._shown(t)
        idx = {n: i for i, n in enumerate(shown)}
        closed = {frozenset(c) for c in v["collapsed"]}
        meta, col = self.metadata(), v.get("colour_by") or ""
        value = lambda tip: (meta["rows"].get(tip) or {}).get(col, "") if col else ""
        # x: distance from the root (or, without lengths, steps from the root with tips lined up); y: rows.
        x, height = {}, {}
        for n in reversed(list(t.walk())):
            height[n] = 0 if n.is_tip else 1 + max(height[c] for c in n.children)
        for n in t.walk():
            x[n] = 0.0 if n is t else x[n.parent] + ((n.length or 0.0) if v["lengths"] else 0)
        if not v["lengths"]:
            top = height[t]
            for n in t.walk():
                x[n] = float(top - height[n])
        y, row = {}, 0
        def place(n):                                # tips top to bottom; a collapsed group takes two rows
            nonlocal row
            if n.is_tip or frozenset(n.tips()) in closed:
                y[n] = row + (0.5 if not n.is_tip else 0)
                row += 2 if not n.is_tip else 1
                return
            for c in n.children:
                place(c)
            y[n] = (y[n.children[0]] + y[n.children[-1]]) / 2
        place(t)
        nodes = []
        for n in shown:
            s = nw.support(n.label) if n.children and n is not t else {}
            d = {"i": idx[n], "x": round(x[n], 6), "y": y[n], "parent": idx.get(n.parent, -1)}
            if n.is_tip:
                d.update(tip=n.name, value=value(n.name))
            elif frozenset(n.tips()) in closed:
                tips = n.tips()
                vals = {value(tp) for tp in tips}
                far = max(x[m] for m in n.walk())
                val = vals.pop() if len(vals) == 1 else ""
                # Intent: name a collapsed group by its shared value when that is a name (Scyphozoa), not a yes/no.
                plain = lambda s: s.replace("_", " ")
                label = (f"{val}: {len(tips)} sequences" if val and val.lower() not in ("yes", "no", "true", "false", "0", "1", "y", "n")
                         else f"{len(tips)} sequences: {plain(tips[0])} … {plain(tips[-1])}")
                d.update(collapsed=len(tips), far=round(far, 6), value=val, first=tips[0], last=tips[-1], label=label)
            else:
                d.update(kids=[idx[c] for c in n.children])
            if s:
                d.update(support=s, strong=nw.strong(s))
            nodes.append(d)
        groups = self._groups(t, col) if col else []
        return {"nodes": nodes, "rows": row, "width": max(x.values()) if x else 0, "view": v, "columns": meta["columns"],
                "colour_by": col, "groups": groups, "tips": len(t.tips()), "lengths": v["lengths"]}

    def _groups(self, t: nw.Node, col: str) -> list[dict]:
        """For each value of a column: how many tips have it, and whether they form one group (a clade) on this tree."""
        rows = self.metadata()["rows"]
        by: dict[str, set] = {}
        for tip in t.tips():
            by.setdefault((rows.get(tip) or {}).get(col, "") or "(not in the table)", set()).add(tip)
        out = []
        for val, tips in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            clade = nw.find_clade(t, tips) if 1 < len(tips) < len(t.tips()) else None
            s = nw.support(clade.label) if clade is not None and clade.parent is not None else {}
            # On a rooted tree, a group is a clade only if it is everything below one node.
            below = clade is not None and set(clade.tips()) == tips
            out.append({"value": val, "n": len(tips), "clade": True if len(tips) == 1 else bool(below),
                        "support": s or None})
        return out

    def reroot(self, how: str = "midpoint", tips: list | None = None, node: int | None = None):
        self._loaded()
        if node is not None:
            t, n = self._node(node)
            if n is t:
                raise ValueError("That is already the root.")
            tips, how = n.tips(), "outgroup"
        if how == "outgroup":
            tips = [str(x) for x in (tips or [])]
            try:
                nw.root_outgroup(self._tree_raw(), tips)     # checks the outgroup sits together
            except ValueError as e:
                raise ValueError(str(e).replace("_", " "))
            self.state["view"]["root"] = {"how": "outgroup", "tips": tips}
        elif how in ("midpoint", "as_built"):
            self.state["view"]["root"] = {"how": how}
        else:
            raise ValueError("Root at the midpoint, on an outgroup, or as the tree was built.")
        self._record("rooted the tree", **self.state["view"]["root"])
        return self.tree()

    def collapse(self, node: int):
        t, n = self._node(node)
        if n.is_tip or n is t:
            raise ValueError("Choose a group (an inner branch) to collapse.")
        c = self.state["view"]["collapsed"]
        if sorted(n.tips()) not in c:
            c.append(sorted(n.tips()))
        self._record("collapsed a group", tips=len(n.tips()), first=n.tips()[0], last=n.tips()[-1])
        return self.tree()

    def expand(self, node: int | None = None, all: bool = False):
        self._loaded()
        if all:
            self.state["view"]["collapsed"] = []
        else:
            _, n = self._node(node)
            self.state["view"]["collapsed"] = [c for c in self.state["view"]["collapsed"] if set(c) != set(n.tips())]
        self._save_state()
        return self.tree()

    def view(self, ladderize: bool | None = None, lengths: bool | None = None, support: str | None = None, colour_by: str | None = None):
        self._loaded()
        v = self.state["view"]
        if colour_by is not None and colour_by and colour_by not in self.metadata()["columns"]:
            raise ValueError(f"No column called {colour_by} in the table.")
        if support is not None and support not in ("none", "strong", "values"):
            raise ValueError("Support can be hidden, shown as dots on strong branches, or shown as numbers.")
        for k, val in (("ladderize", ladderize), ("lengths", lengths), ("support", support), ("colour_by", colour_by)):
            if val is not None:
                v[k] = val
        self._save_state()
        return self.tree()

    # ---------------------------------------------------------------- export
    def _svg(self, d: dict) -> str:
        """The tree as it is drawn on screen, as a stand-alone SVG with neutral colours."""
        nodes, rows = d["nodes"], d["rows"]
        names = [n.get("tip") or n["label"] for n in nodes if "tip" in n or "collapsed" in n]
        label_w = 8 + 7 * max((len(x) for x in names), default=10)
        W, top, rowh = 760, 24, 18
        span = d["width"] or 1
        X = lambda v: 20 + v / span * (W - 40 - label_w)
        Y = lambda v: top + v * rowh
        # Colours in the same order as the Groups table on screen, with a legend under the tree.
        values = [g["value"] for g in d["groups"]]
        colour = {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(values)}
        legend_y = top + rows * rowh + (44 if d["lengths"] else 16)
        H = legend_y + (18 * (len(values) + 1) + 10 if values else 0) + 10
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif" font-size="12">',
               '<rect width="100%" height="100%" fill="#ffffff"/>']
        byi = {n["i"]: n for n in nodes}
        for n in nodes:
            if n["parent"] >= 0:
                p = byi[n["parent"]]
                out.append(f'<path d="M{X(p["x"]):.1f},{Y(n["y"]):.1f}H{X(n["x"]):.1f}" stroke="#222" fill="none"/>')
            if n.get("kids"):
                ys = [byi[k]["y"] for k in n["kids"]]
                out.append(f'<path d="M{X(n["x"]):.1f},{Y(min(ys)):.1f}V{Y(max(ys)):.1f}" stroke="#222" fill="none"/>')
            c = colour.get(n.get("value"), "#222")
            if "tip" in n:
                out.append(f'<text x="{X(n["x"]) + 5:.1f}" y="{Y(n["y"]) + 4:.1f}" fill="{c}">{html.escape(n["tip"].replace("_", " "))}</text>')
            elif "collapsed" in n:
                x0, x1, y0 = X(n["x"]), X(n["far"]), Y(n["y"])
                out.append(f'<path d="M{x0:.1f},{y0:.1f}L{x1:.1f},{y0 - 7:.1f}L{x1:.1f},{y0 + 7:.1f}Z" fill="{c}" fill-opacity="0.35" stroke="{c}"/>')
                out.append(f'<text x="{x1 + 5:.1f}" y="{y0 + 4:.1f}" fill="{c}" font-style="italic">{html.escape(n["label"])}</text>')
            if n.get("support") and d["view"]["support"] == "values":
                s = n["support"]
                txt = f'{s["alrt"]:.0f}/{s["ufboot"]:.0f}' if "ufboot" in s else f'{s["support"]:.0f}'
                out.append(f'<text x="{X(n["x"]) - 3:.1f}" y="{Y(n["y"]) - 3:.1f}" text-anchor="end" font-size="9" fill="#555">{txt}</text>')
            elif n.get("strong") and d["view"]["support"] == "strong":
                out.append(f'<circle cx="{X(n["x"]):.1f}" cy="{Y(n["y"]):.1f}" r="3" fill="#222"/>')
        if d["lengths"]:
            bar = 10 ** round(math.log10(span / 5)) if span > 0 else 0.1
            yb = Y(rows) + 16
            out.append(f'<path d="M{X(0):.1f},{yb:.1f}H{X(bar):.1f}" stroke="#222"/><text x="{X(bar) + 5:.1f}" y="{yb + 4:.1f}">{bar:g} substitutions per site</text>')
        if values:
            out.append(f'<text x="20" y="{legend_y:.1f}" font-weight="bold">{html.escape(d["colour_by"].replace("_", " "))}</text>')
            for k, v in enumerate(values, 1):
                y = legend_y + 18 * k
                out.append(f'<rect x="20" y="{y - 9:.1f}" width="10" height="10" fill="{colour[v]}"/><text x="36" y="{y:.1f}">{html.escape(v)}</text>')
        return "\n".join(out + ["</svg>"]) + "\n"

    def export(self):
        d = self.tree()
        out = self.res / "final"
        out.mkdir(exist_ok=True)
        t = self._current()
        (out / "tree_rooted.nwk").write_text(nw.write(t) + "\n")
        (out / "tree_figure.svg").write_text(self._svg(d))
        meta, names = self.metadata(), self._names()
        cols = meta["columns"]
        with open(out / "tips.tsv", "w") as fh:
            fh.write("\t".join(["name", "original_header", *cols]) + "\n")
            for tip in t.tips():
                fh.write("\t".join([tip, names.get(tip, tip), *((meta["rows"].get(tip) or {}).get(c, "") for c in cols)]) + "\n")
        files = ["tree_rooted.nwk", "tree_figure.svg", "tips.tsv"]
        if d["groups"]:
            with open(out / "groups.tsv", "w") as fh:
                fh.write(f"{d['colour_by']}\tsequences\tone_group_on_the_tree\tSH_aLRT\tUFBoot_or_support\n")
                for g in d["groups"]:
                    s = g["support"] or {}
                    fh.write(f"{g['value']}\t{g['n']}\t{'yes' if g['clade'] else 'no'}\t{s.get('alrt', '')}\t{s.get('ufboot', s.get('support', ''))}\n")
            files.append("groups.tsv")
        self.state["step"] = "exported"
        self._record("exported the tree", files=files, root=d["view"]["root"], collapsed=len(d["view"]["collapsed"]),
                     colour_by=d["colour_by"], groups=[{"value": g["value"], "n": g["n"], "clade": g["clade"]} for g in d["groups"]])
        return {"files": files}

    def files(self):
        d = self.res / "final"
        return [{"name": f"final/{p.name}", "size": p.stat().st_size} for p in sorted(d.iterdir())] if d.is_dir() else []
