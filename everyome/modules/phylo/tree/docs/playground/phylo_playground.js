/* Playground for tree building: sequences evolve along a true tree of six species, a tree is rebuilt from them by
   neighbour joining with bootstrap support, and the two are compared. Shows what alignment length, short inner
   branches, fast-evolving (long) branches and the distance correction do. Runs in the browser; built with Everyome's
   shared playground builder. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc, fmt } = H;
  const TIPS = ["A", "B", "C", "D", "E", "F"], ALL = (1 << TIPS.length) - 1;

  function rng(seed) {
    let a = seed >>> 0;
    const r = () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    // Gamma(shape, 1/shape) by Marsaglia and Tsang (boosted for shape < 1), so rates average 1.
    r.gamma = k => { const b = k < 1 ? k + 1 : k, d = b - 1 / 3, c = 1 / Math.sqrt(9 * d); let v, x;
      for (;;) { do { const u1 = r() || 1e-12, u2 = r(); x = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2); v = 1 + c * x; } while (v <= 0);
        v = v * v * v; const u = r(); if (Math.log(u) < 0.5 * x * x + d - d * v + Math.log(v)) break; }
      return d * v * (k < 1 ? Math.pow(r(), 1 / k) : 1) / k; };
    return r;
  }

  // The true tree: three pairs (A,B), (C,D), (E,F) joined at a centre. A and C sit in different pairs; making
  // their branches long is the classic trap (long-branch attraction).
  function trueTree(S) {
    const t = 0.06 * S.rate, inner = S.inner * S.rate, long = t * S.long;
    const tip = (name, len) => ({ name, len, kids: [] });
    return { len: 0, kids: [{ len: inner, kids: [tip("A", long), tip("B", t)] }, { len: inner, kids: [tip("C", long), tip("D", t)] }, { len: inner, kids: [tip("E", t), tip("F", t)] }] };
  }

  // Jukes–Cantor change along a branch, site by site (rates vary between sites if gamma is on).
  function evolve(S) {
    const r = rng(S.seed), n = S.sites, rates = Array.from({ length: n }, () => S.gamma === "yes" ? r.gamma(0.5) : 1);
    const out = {};
    const go = (node, seq) => {
      const s = seq.map((b, i) => { const p = 0.75 * (1 - Math.exp(-4 / 3 * node.len * rates[i])); return r() < p ? (b + 1 + Math.floor(r() * 3)) % 4 : b; });
      if (!node.kids.length) out[node.name] = s; else node.kids.forEach(k => go(k, s));
    };
    go(trueTree(S), Array.from({ length: n }, () => Math.floor(r() * 4)));
    return TIPS.map(t => out[t]);
  }

  function distances(seqs, cols, how) {
    const n = seqs.length, D = Array.from({ length: n }, () => new Array(n).fill(0));
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      let diff = 0;
      for (const c of cols) if (seqs[i][c] !== seqs[j][c]) diff++;
      const p = Math.min(diff / cols.length, 0.7499);
      // p: share of sites that differ. JC corrects for changes hidden by later changes; +gamma also for fast sites.
      const d = how === "p" ? p : how === "jc" ? -0.75 * Math.log(1 - 4 / 3 * p) : 0.75 * 0.5 * (Math.pow(1 - 4 / 3 * p, -1 / 0.5) - 1);
      D[i][j] = D[j][i] = d;
    }
    return D;
  }

  // Neighbour joining; returns a tree with the last three groups joined at a centre, and its groups as bit sets.
  function nj(D) {
    let nodes = TIPS.map((name, i) => ({ name, kids: [], set: 1 << i, len: 0 })), M = D.map(r => r.slice());
    while (nodes.length > 3) {
      const n = nodes.length, R = M.map(r => r.reduce((a, b) => a + b, 0));
      let bi = 0, bj = 1, best = Infinity;
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) { const q = (n - 2) * M[i][j] - R[i] - R[j]; if (q < best) { best = q; bi = i; bj = j; } }
      const li = Math.max(0, 0.5 * M[bi][bj] + (R[bi] - R[bj]) / (2 * (n - 2))), lj = Math.max(0, M[bi][bj] - li);
      nodes[bi].len = li; nodes[bj].len = lj;
      const u = { kids: [nodes[bi], nodes[bj]], set: nodes[bi].set | nodes[bj].set, len: 0 };
      const du = M.map((r, k) => 0.5 * (M[bi][k] + M[bj][k] - M[bi][bj]));
      const keep = nodes.map((_, k) => k).filter(k => k !== bi && k !== bj);
      M = keep.map(a => keep.map(b => M[a][b]).concat([du[a]])).concat([keep.map(a => du[a]).concat([0])]);
      nodes = keep.map(k => nodes[k]).concat([u]);
    }
    const [a, b, c] = nodes;
    a.len = Math.max(0, (M[0][1] + M[0][2] - M[1][2]) / 2); b.len = Math.max(0, M[0][1] - a.len); c.len = Math.max(0, M[0][2] - a.len);
    return { len: 0, kids: [a, b, c], set: ALL };
  }
  // A group as the side of its split without F, so groups compare however the tree is drawn.
  const norm = s => (s & (1 << 5)) ? ALL ^ s : s;
  function splits(tree) {
    const out = new Set(), walk = n => { if (n.kids.length) { n.kids.forEach(walk); const s = norm(n.set); if (n !== tree && bits(s) > 1 && bits(s) < 5) out.add(s); } };
    walk(tree); return out;
  }
  const bits = s => s.toString(2).split("").filter(x => x === "1").length;
  const name = s => TIPS.filter((_, i) => s & (1 << i)).join("+");
  function setTips(n) { if (!n.kids.length) { n.set = 1 << TIPS.indexOf(n.name); return n.set; } n.set = n.kids.reduce((a, k) => a | setTips(k), 0); return n.set; }

  function treeSvg(tree, support, truth, title) {
    const C = H.COL(), w = 300, h = 210;
    const tips = [], x = new Map();
    const lay = (n, d) => { x.set(n, d); if (!n.kids.length) tips.push(n); n.kids.forEach(k => lay(k, d + k.len)); };
    lay(tree, 0);
    const span = Math.max(...[...x.values()], 1e-6), X = v => 46 + v / span * (w - 80), y = new Map();
    tips.forEach((t, i) => y.set(t, 18 + i * (h - 36) / (tips.length - 1)));
    const yy = n => n.kids.length ? (y.has(n) ? y.get(n) : (y.set(n, n.kids.reduce((a, k) => a + yy(k), 0) / n.kids.length), y.get(n))) : y.get(n);
    yy(tree);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" style="max-width:${w}px" role="img" aria-label="${esc(title)}">`;
    const draw = n => {
      if (n.kids.length) {
        const ys = n.kids.map(k => y.get(k));
        s += `<path d="M${X(x.get(n))},${Math.min(...ys)}V${Math.max(...ys)}" stroke="${C.ink}" fill="none"/>`;
        n.kids.forEach(k => { s += `<path d="M${X(x.get(n))},${y.get(k)}H${X(x.get(k))}" stroke="${C.ink}" fill="none" stroke-width="1.5"/>`; draw(k); });
        const sp = norm(n.set);
        if (n !== tree && support && support.has(sp)) {
          const ok = !truth || truth.has(sp);
          s += `<text x="${X(x.get(n)) - 3}" y="${y.get(n) - 4}" text-anchor="end" style="font-size:10px;font-weight:600" fill="${ok ? C.ink : C.ox}">${support.get(sp)}%${ok ? "" : " ✗"}</text>`;
        }
      } else s += `<text x="${X(x.get(n)) + 5}" y="${y.get(n) + 4}" style="font-size:12px;font-weight:600" fill="${C.ink}">${n.name}</text>`;
    };
    draw(tree);
    return s + "</svg>";
  }

  function render(S, el) {
    const seqs = evolve(S), cols = Array.from({ length: S.sites }, (_, i) => i), truth = trueTree(S);
    setTips(truth);
    const trueSplits = splits(truth), built = nj(distances(seqs, cols, S.distance)), got = splits(built);
    // Bootstrap: rebuild the tree from alignments resampled column by column; support = share containing each group.
    const r = rng(S.seed + 7), counts = new Map();
    for (let b = 0; b < S.reps; b++) {
      const c = cols.map(() => Math.floor(r() * S.sites));
      for (const s of splits(nj(distances(seqs, c, S.distance)))) counts.set(s, (counts.get(s) || 0) + 1);
    }
    const sup = new Map([...got].map(s => [s, S.reps ? Math.round(100 * (counts.get(s) || 0) / S.reps) : "–"]));
    const trueSup = new Map([...trueSplits].map(s => [s, S.reps ? Math.round(100 * (counts.get(s) || 0) / S.reps) : "–"]));
    const wrong = [...got].filter(s => !trueSplits.has(s)), right = wrong.length === 0;
    let diff = 0; for (let i = 0; i < S.sites; i++) if (seqs[0][i] !== seqs[2][i]) diff++;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    const minTrue = Math.min(...[...trueSup.values()].map(Number).filter(v => !isNaN(v)));
    el.innerHTML = `<section class="pg-card"><div class="label">What the rebuilt tree says</div><div class="metrics">
        ${m("Tree", right ? "correct" : "wrong", right ? "every group matches the true tree" : `wrongly groups ${wrong.map(name).join(", ")}`, !right)}
        ${m("Weakest true group", S.reps && isFinite(minTrue) ? minTrue + "%" : "–", "bootstrap support; 70% or more is usually trusted", S.reps && minTrue < 70)}
        ${m("Wrong group's support", wrong.length && S.reps ? sup.get(wrong[0]) + "%" : "–", !wrong.length ? "no wrong group" : S.reps && sup.get(wrong[0]) >= 70 ? "strong support for a wrong group: a systematic error, not too little data" : "weak: the data cannot tell", wrong.length && sup.get(wrong[0]) >= 70)}
        ${m("A and C differ at", Math.round(100 * diff / S.sites) + "%", "of sites (unrelated random sequences differ at 75%)", diff / S.sites > 0.6)}</div></section>
      <section class="pg-card"><div class="label">The true tree and the rebuilt tree (support in %; ✗ marks a group that is not in the true tree)</div>
        <div class="row" style="gap:18px;flex-wrap:wrap"><div><div class="small muted">True tree</div>${treeSvg(truth, trueSup, null, "True tree")}</div>
        <div><div class="small muted">Rebuilt by neighbour joining (${S.distance === "p" ? "uncorrected distances" : S.distance === "jc" ? "Jukes–Cantor distances" : "Jukes–Cantor + gamma distances"})</div>${treeSvg(built, sup, trueSplits, "Rebuilt tree")}</div></div>
        <p class="small muted">Support on the true tree is how often the bootstrap trees contained each true group.</p></section>`;
  }

  window.PhyloPlayground = E.makePlayground({
    defaults: { seed: 1, sites: 1000, rate: 1, inner: 0.05, long: 1, gamma: "no", distance: "jc", reps: 100 },
    controls: [
      { group: "Data", items: [
        { key: "sites", label: "Alignment length (sites)", type: "range", min: 50, max: 5000, step: 50, help: "More sites, more evidence for each group." },
        { key: "rate", label: "Speed of evolution", type: "range", min: 0.2, max: 6, step: 0.1, help: "Scales every branch. Fast genes change so much that later changes hide earlier ones (saturation)." },
        { key: "gamma", label: "Rates vary between sites", type: "select", options: [["no", "No"], ["yes", "Yes (strongly, gamma shape 0.5)"]], help: "In real genes some positions barely change and others change fast." }] },
      { group: "True tree", items: [
        { key: "inner", label: "Inner branch length", type: "range", min: 0.002, max: 0.2, step: 0.002, help: "How long the pairs had to themselves before splitting. Short inner branches leave few changes to find them by." },
        { key: "long", label: "A and C evolve faster (times)", type: "range", min: 1, max: 15, step: 0.5, help: "Lengthens the branches to A and C, which are not each other's closest relatives." }] },
      { group: "Method", items: [
        { key: "distance", label: "Distance", type: "select", options: [["p", "Uncorrected (share of sites that differ)"], ["jc", "Jukes–Cantor corrected"], ["jcg", "Jukes–Cantor + gamma corrected"]],
          help: "Corrections estimate the changes that later changes have hidden. Model-based methods (IQ-TREE) do this as part of the model." },
        { key: "reps", label: "Bootstrap replicates", type: "range", min: 0, max: 200, step: 10 },
        { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1 }] },
    ],
    presets: [
      ["Plenty of data (the defaults)", {}, "1,000 sites and clear inner branches: the tree is right and every group is strongly supported."],
      ["Short alignment", { sites: 100 }, "With 100 sites support drops, and the tree may come out wrong. More data helps."],
      ["Very short inner branch", { inner: 0.004 }, "Even with 1,000 sites, a very short inner branch leaves few changes to find the pairs by: support is low. Low support means 'cannot tell', not 'wrong'."],
      ["Long-branch attraction", { long: 10, inner: 0.03, gamma: "yes", distance: "p", sites: 3000, reps: 50 }, "A and C evolve fast. Their many changes make them look alike by chance, so A and C are grouped together, wrongly and with strong support. More data only makes it worse."],
      ["A model that fits", { long: 10, inner: 0.03, gamma: "yes", distance: "jcg", sites: 3000, reps: 50 }, "The same data with distances corrected for hidden changes and for rate variation between sites: the true pairs come back, with less certainty. This is why IQ-TREE fits a model (+G4 is rate variation)."],
    ],
    render,
  });
})();
