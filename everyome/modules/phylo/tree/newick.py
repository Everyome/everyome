"""Newick trees: read, write, re-root and lay out. Pure Python, so it runs on any cluster Python.

Support values belong to branches (a branch splits the tips in two), not to
nodes. Each node here carries the length and support of the branch above it,
so re-rooting moves support with its branch and never attaches it to the
wrong group. IQ-TREE writes support as `SH-aLRT/UFBoot` when both were asked
for, or a single number when only one was.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(eq=False)
class Node:
    name: str = ""
    length: float | None = None     # length of the branch above this node
    label: str = ""                 # support of the branch above this node, as written in the file
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = None

    @property
    def is_tip(self) -> bool:
        return not self.children

    def walk(self):
        """Every node, parents before children."""
        stack = [self]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(reversed(n.children))

    def tips(self) -> list[str]:
        return [n.name for n in self.walk() if n.is_tip]


# ------------------------------------------------------------------ reading and writing
TOKEN = re.compile(r"\s*('(?:[^']|'')*'|\[[^\]]*\]|[(),:;]|[^\s(),:;\[\]']+)")


def parse(text: str) -> Node:
    toks = [t for t in TOKEN.findall(text.strip()) if not t.startswith("[")]   # comments are dropped
    root = cur = Node()
    stack: list[Node] = []
    i = 0
    # Intent: '(' turns the current node into a parent and moves to its first child; ',' starts a sibling;
    # ')' goes back up; ':' gives the length of the branch above; a bare word names a tip or labels a branch.
    while i < len(toks) and toks[i] != ";":
        t = toks[i]
        if t == "(":
            stack.append(cur)
            cur = Node(parent=cur)
            stack[-1].children.append(cur)
        elif t == ",":
            if not stack:
                raise ValueError("Not a Newick tree: a comma outside brackets.")
            cur = Node(parent=stack[-1])
            stack[-1].children.append(cur)
        elif t == ")":
            if not stack:
                raise ValueError("Not a Newick tree: too many closing brackets.")
            cur = stack.pop()
        elif t == ":":
            i += 1
            try:
                cur.length = float(toks[i])
            except (IndexError, ValueError):
                raise ValueError("Not a Newick tree: a ':' without a branch length.")
        else:
            name = t[1:-1].replace("''", "'") if t.startswith("'") else t
            if cur.is_tip:
                cur.name = name
            else:
                cur.label = name
        i += 1
    if stack:
        raise ValueError("Not a Newick tree: brackets do not match.")
    for n in root.walk():
        if n.is_tip and not n.name:
            raise ValueError("Not a Newick tree: a tip has no name.")
    names = root.tips()
    if len(names) != len(set(names)):
        raise ValueError("The tree has two tips with the same name.")
    return root


def _q(name: str) -> str:
    return f"'{name.replace(chr(39), chr(39) * 2)}'" if re.search(r"[\s(),:;\[\]']", name) else name


def write(root: Node) -> str:
    def w(n: Node) -> str:
        s = f"({','.join(w(c) for c in n.children)}){_q(n.label) if n.label else ''}" if n.children else _q(n.name)
        return s + (f":{n.length:.6g}" if n.length is not None and n is not root else "")
    return w(root) + ";"


# ------------------------------------------------------------------ support
def support(label: str) -> dict:
    """{'alrt': .., 'ufboot': ..} or {'support': ..} from an IQ-TREE node label; {} if there is none."""
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", label or "")]
    if len(nums) >= 2 and "/" in label:
        return {"alrt": nums[-2], "ufboot": nums[-1]}
    return {"support": nums[0]} if nums else {}


def strong(s: dict, alrt_min: float = 80, ufboot_min: float = 95, single_min: float = 70) -> bool | None:
    """IQ-TREE's rule of thumb: a group is well supported if SH-aLRT >= 80% and UFBoot >= 95%."""
    if "ufboot" in s:
        return s["alrt"] >= alrt_min and s["ufboot"] >= ufboot_min
    if "support" in s:
        return s["support"] >= single_min
    return None


# ------------------------------------------------------------------ rooting
def _edges(root: Node):
    """Undirected neighbours: node -> [(other, length, label)]."""
    adj: dict[Node, list] = {n: [] for n in root.walk()}
    for n in root.walk():
        if n.parent is not None:
            adj[n].append((n.parent, n.length, n.label))
            adj[n.parent].append((n, n.length, n.label))
    return adj


def _build(adj, start: Node, came_from: Node | None, length, label) -> Node:
    """Re-hang the tree from start, copying nodes; branches keep their length and support."""
    out = Node(name=start.name, length=length, label=label)
    for other, ln, lb in adj[start]:
        if other is not came_from:
            c = _build(adj, other, start, ln, lb)
            c.parent = out
            out.children.append(c)
    return out


def _suppress(root: Node) -> Node:
    """Remove inner nodes left with one child (the old root after re-rooting), joining their branches."""
    for n in list(root.walk()):
        if n is not root and not n.is_tip and len(n.children) == 1:
            c, p = n.children[0], n.parent
            c.length = (c.length or 0) + (n.length or 0)
            c.label = c.label or n.label
            c.parent = p
            p.children[p.children.index(n)] = c
    return root


def root_on(root: Node, below: Node, fraction: float = 0.5) -> Node:
    """A new tree rooted on the branch above `below` (a node of root), `fraction` of the way up from it."""
    if below.parent is None:
        raise ValueError("That is already the root.")
    adj = _edges(root)
    p, ln, lb = below.parent, below.length or 0.0, below.label
    adj[below] = [e for e in adj[below] if e[0] is not p]
    adj[p] = [e for e in adj[p] if e[0] is not below]
    new = Node()
    a = _build(adj, below, None, ln * fraction, lb)
    b = _build(adj, p, None, ln * (1 - fraction), lb)
    for c in (a, b):
        c.parent = new
        new.children.append(c)
    return _suppress(new)


def find_clade(root: Node, tips: set[str]) -> Node | None:
    """The node whose tips are exactly `tips`, or whose other side is (so it works on any rooting)."""
    every = set(root.tips())
    for n in root.walk():
        if n is root:
            continue
        below = set(n.tips())
        if below == tips:
            return n
        if every - below == tips:
            return n
    return None


def root_outgroup(root: Node, outgroup: list[str]) -> Node:
    every = set(root.tips())
    missing = [t for t in outgroup if t not in every]
    if missing:
        raise ValueError(f"Not in the tree: {', '.join(missing)}.")
    want = set(outgroup)
    if not want or want == every:
        raise ValueError("Choose some, but not all, of the tips as the outgroup.")
    n = find_clade(root, want)
    if n is None:
        raise ValueError(f"{', '.join(sorted(want))} do not form a group on this tree (they are not monophyletic), so they "
                         "cannot root it together. Choose one of them, or a group that does sit together.")
    new = root_on(root, n)
    # Intent: draw the outgroup first (at the top), so the rest of the tree reads as the ingroup.
    if set(new.children[0].tips()) != want:
        new.children.reverse()
    return new


def _dist_from(adj, start: Node) -> dict:
    out, stack = {start: 0.0}, [start]
    while stack:
        u = stack.pop()
        for v, ln, _ in adj[u]:
            if v not in out:
                out[v] = out[u] + (ln or 0.0)
                stack.append(v)
    return out


def root_midpoint(root: Node) -> Node:
    """Root halfway along the longest path between two tips."""
    adj = _edges(root)
    tips = [n for n in root.walk() if n.is_tip]
    d0 = _dist_from(adj, tips[0])
    a = max(tips, key=lambda t: d0[t])
    da = _dist_from(adj, a)
    b = max(tips, key=lambda t: da[t])
    half = da[b] / 2
    # The path from b up to the common ancestor and down to a, with the distance from b at each node.
    up_b, up_a = _ancestors(b), _ancestors(a)
    top = next(n for n in up_b if n in set(up_a))
    path = up_b[:up_b.index(top) + 1] + list(reversed(up_a[:up_a.index(top)]))
    db = [0.0]
    for u, v in zip(path, path[1:]):
        db.append(db[-1] + ((u.length if u.parent is v else v.length) or 0.0))
    for k, (u, v) in enumerate(zip(path, path[1:])):
        if db[k] <= half <= db[k + 1]:
            ln = db[k + 1] - db[k]
            child = u if u.parent is v else v          # a branch is named by its lower node
            if ln == 0:
                return root_on(root, child)
            from_u = half - db[k]
            return root_on(root, child, (from_u if child is u else ln - from_u) / ln)
    return root


def _ancestors(n: Node) -> list[Node]:
    out = [n]
    while out[-1].parent is not None:
        out.append(out[-1].parent)
    return out


def ladderize(root: Node) -> Node:
    """Smaller groups above larger ones at every split, so the tree reads top to bottom."""
    size = {}
    for n in reversed(list(root.walk())):
        size[n] = 1 if n.is_tip else sum(size[c] for c in n.children)
    for n in root.walk():
        n.children.sort(key=lambda c: size[c])
    return root


def inner_branches(root: Node) -> list[Node]:
    """Nodes below each inner branch, one per split: on a tree rooted on a branch, its two halves are one split."""
    out = [n for n in root.walk() if n is not root and not n.is_tip]
    if len(root.children) == 2 and all(not c.is_tip for c in root.children):
        out.remove(root.children[1])
    return out


def mrca(root: Node, tips: set[str]) -> Node:
    best = root
    for n in root.walk():
        if tips <= set(n.tips()):
            best = n
    return best
