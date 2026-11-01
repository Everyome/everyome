/* Playground core: a toy SPLiT-seq-like dataset and a simplified version of
   stages 11-15, small enough to run in the browser. No DOM code here. */
const PlayCore = (() => {

  // ---- seeded random numbers (mulberry32) ----
  function rng(seed) {
    let a = seed >>> 0;
    const r = () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    r.normal = () => { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
    r.poisson = lam => { if (lam > 30) return Math.max(0, Math.round(lam + Math.sqrt(lam) * r.normal()));
      const L = Math.exp(-lam); let k = 0, p = 1; do { k++; p *= r(); } while (p > L); return k - 1; };
    r.pick = probs => { let x = r(), i = 0; for (; i < probs.length - 1; i++) { x -= probs[i]; if (x < 0) break; } return i; };
    return r;
  }

  // ---- toy biology ----
  const TYPES = ["Stem", "Progenitor", "Neural", "Gland", "Epithelial A", "Epithelial B", "Muscle", "Responsive"];
  // Share of each type per condition. Treated has more progenitors and a treated-only state.
  const COMP = {
    control: [12, 14, 12, 12, 18, 14, 18, 0],
    treated: [10, 24, 10, 10, 14, 10, 12, 10],
  };
  const N_GENES = 300, MARKERS = 12;

  function makeProfiles(r) {
    // Intent: baseline expression for every gene, then marker programmes per type.
    const base = Array.from({ length: N_GENES }, () => Math.exp(r.normal() * 0.9) * 0.6);
    const marker = TYPES.map((_, t) => Array.from({ length: MARKERS }, (_, k) => 10 + t * MARKERS + k));
    // Epithelial B reuses 8 of Epithelial A's 12 markers, so the two are close.
    marker[5] = marker[4].slice(0, 8).concat(marker[5].slice(0, 4));
    // Marker genes are rarely detected outside their type, strongly inside it.
    const allMarkers = new Set(marker.flat());
    for (const g of allMarkers) base[g] *= 0.12;
    const prof = TYPES.map((_, t) => {
      const p = base.slice();
      for (const g of marker[t]) p[g] = 0.6 * 9 * (0.7 + 0.6 * r());
      return p;
    });
    const batchGenes = Array.from({ length: 10 }, (_, k) => 120 + k);
    const batchFactor = Array.from({ length: N_GENES }, () => Math.exp(r.normal() * 0.35));
    for (const g of batchGenes) batchFactor[g] *= 6;
    // Treatment response: 8 genes raised in every treated cell, whatever its type.
    const responseGenes = Array.from({ length: 8 }, (_, k) => 140 + k);
    return { base, marker, prof, batchFactor, responseGenes };
  }

  function generate({ seed = 1, nCells = 1100, design = "balanced", batchStrength = 1 } = {}) {
    const r = rng(seed), P = makeProfiles(r);
    const cells = [];
    const half = Math.round(nCells / 2);
    for (let i = 0; i < nCells; i++) {
      const condition = i < half ? "control" : "treated";
      // balanced: each condition split across both batches; confounded: batch = condition
      const batch = design === "confounded" ? (condition === "control" ? 1 : 2) : (r() < 0.5 ? 1 : 2);
      const w = COMP[condition], tot = w.reduce((a, b) => a + b, 0);
      const type = r.pick(w.map(x => x / tot));
      cells.push({ condition, batch, type, kind: "cell", pos: r() });
    }
    // Intent: 5% doublets (two cells captured together) and 4% near-empty barcodes.
    const nDbl = Math.round(nCells * 0.05), nLow = Math.round(nCells * 0.04);
    for (let i = 0; i < nDbl; i++) {
      const a = cells[Math.floor(r() * nCells)], b = cells[Math.floor(r() * nCells)];
      cells.push({ condition: a.condition, batch: a.batch, type: a.type, type2: b.type, kind: "doublet", pos: r() });
    }
    for (let i = 0; i < nLow; i++) {
      const c = i % 2 ? "control" : "treated";
      cells.push({ condition: c, batch: design === "confounded" ? (c === "control" ? 1 : 2) : 1 + (i % 2), type: -1, kind: "low", pos: r() });
    }
    const counts = cells.map(c => {
      let p;
      if (c.kind === "low") p = P.base;
      else if (c.type === 1) {
        // Progenitors form a continuum from Stem to Neural.
        p = P.base.map((_, g) => (1 - c.pos) * P.prof[0][g] + c.pos * P.prof[2][g]);
        // Its own markers peak mid-way, so the continuum bridges Stem and Neural.
        const w = 0.35 + 0.65 * Math.sin(Math.PI * c.pos);
        for (const g of P.marker[1]) p[g] = P.base[g] + (P.prof[1][g] - P.base[g]) * w;
      } else p = P.prof[c.type];
      if (c.kind === "doublet") p = p.map((x, g) => x + P.prof[c.type2][g]);
      const lib = Math.exp(Math.log(c.kind === "low" ? 70 : 650) + r.normal() * 0.3) * (c.kind === "doublet" ? 2 : 1);
      const bf = c.batch === 2 ? P.batchFactor.map(f => 1 + (f - 1) * batchStrength) : null;
      const q = p.map((x, g) => x * (bf ? bf[g] : 1));
      if (c.condition === "treated" && c.kind !== "low") for (const g of P.responseGenes) q[g] *= 4;
      const s = q.reduce((a, b) => a + b, 0);
      return Int32Array.from(q, x => r.poisson(lib * x / s));
    });
    cells.forEach((c, i) => { c.umis = counts[i].reduce((a, b) => a + b, 0); c.genes = counts[i].reduce((a, b) => a + (b > 0), 0); });
    return { cells, counts, markers: P.marker.map(m => m[m.length - 1]), types: TYPES };
  }

  // ---- stage 11: QC ----
  const qcFilter = (data, { minUmis, maxUmis }) =>
    data.cells.map((c, i) => i).filter(i => data.cells[i].umis >= minUmis && data.cells[i].umis < maxUmis);

  // ---- stage 12: normalise, HVG, scale, PCA ----
  function normalise(data, idx) {
    return idx.map(i => { const x = data.counts[i], s = data.cells[i].umis || 1;
      return Float64Array.from(x, v => Math.log1p(v / s * 1e4)); });
  }

  function hvg(X, n) {
    const G = X[0].length, mean = new Float64Array(G), v = new Float64Array(G);
    for (const row of X) for (let g = 0; g < G; g++) mean[g] += row[g] / X.length;
    for (const row of X) for (let g = 0; g < G; g++) v[g] += (row[g] - mean[g]) ** 2 / X.length;
    // Simplified: rank genes by variance of log-normalised expression.
    return [...v.keys()].sort((a, b) => v[b] - v[a]).slice(0, n);
  }

  function scale(X, genes) {
    const n = X.length, out = X.map(() => new Float64Array(genes.length));
    genes.forEach((g, j) => {
      let m = 0, s = 0; for (const row of X) m += row[g] / n;
      for (const row of X) s += (row[g] - m) ** 2 / n; s = Math.sqrt(s) || 1;
      X.forEach((row, i) => { out[i][j] = Math.max(-10, Math.min(10, (row[g] - m) / s)); });
    });
    return out;
  }

  function pca(Z, k, seed = 3) {
    // Intent: top-k eigenvectors of the gene covariance by subspace iteration.
    const n = Z.length, d = Z[0].length, C = Array.from({ length: d }, () => new Float64Array(d));
    for (const row of Z) for (let a = 0; a < d; a++) { const ra = row[a]; if (!ra) continue; const Ca = C[a]; for (let b = 0; b < d; b++) Ca[b] += ra * row[b]; }
    const r = rng(seed); k = Math.min(k, d);
    let Q = Array.from({ length: k }, () => Float64Array.from({ length: d }, () => r.normal()));
    const ortho = V => { for (let i = 0; i < V.length; i++) { for (let j = 0; j < i; j++) { let dot = 0; for (let t = 0; t < d; t++) dot += V[i][t] * V[j][t]; for (let t = 0; t < d; t++) V[i][t] -= dot * V[j][t]; }
      let nn = 0; for (let t = 0; t < d; t++) nn += V[i][t] ** 2; nn = Math.sqrt(nn) || 1; for (let t = 0; t < d; t++) V[i][t] /= nn; } return V; };
    Q = ortho(Q);
    let eig = new Float64Array(k);
    for (let it = 0; it < 40; it++) {
      const W = Q.map(q => { const w = new Float64Array(d); for (let a = 0; a < d; a++) { let s = 0; const Ca = C[a]; for (let b = 0; b < d; b++) s += Ca[b] * q[b]; w[a] = s; } return w; });
      eig = Float64Array.from(W, (w, i) => { let s = 0; for (let t = 0; t < d; t++) s += w[t] * Q[i][t]; return s / n; });
      Q = ortho(W);
    }
    const scores = Z.map(row => Float64Array.from(Q, q => { let s = 0; for (let t = 0; t < d; t++) s += row[t] * q[t]; return s; }));
    const total = Z.reduce((acc, row) => acc + row.reduce((a, b) => a + b * b, 0), 0) / n;
    return { scores, varRatio: Array.from(eig, e => e / total) };
  }

  // Simplified batch correction: shift each batch's centroid onto the overall
  // centroid in PC space, by a chosen strength. Stands in for Harmony.
  function correct(scores, batches, strength) {
    if (!strength) return scores;
    const d = scores[0].length, all = new Float64Array(d), byB = {};
    scores.forEach((s, i) => { const b = batches[i]; (byB[b] ||= { m: new Float64Array(d), n: 0 }); byB[b].n++;
      for (let t = 0; t < d; t++) { byB[b].m[t] += s[t]; all[t] += s[t] / scores.length; } });
    for (const b in byB) for (let t = 0; t < d; t++) byB[b].m[t] /= byB[b].n;
    return scores.map((s, i) => Float64Array.from(s, (v, t) => v - strength * (byB[batches[i]].m[t] - all[t])));
  }

  // ---- neighbour graph and Louvain clustering ----
  function knn(P, nPcs, k) {
    const n = P.length, out = new Array(n);
    for (let i = 0; i < n; i++) {
      const d = new Float64Array(n);
      for (let j = 0; j < n; j++) { let s = 0; for (let t = 0; t < nPcs; t++) s += (P[i][t] - P[j][t]) ** 2; d[j] = s; }
      d[i] = Infinity;
      out[i] = [...d.keys()].sort((a, b) => d[a] - d[b]).slice(0, k);
    }
    return out;
  }

  function louvain(nbrs, resolution, seed = 5) {
    // Intent: modularity optimisation with a resolution parameter, then
    // aggregation, repeated until no move improves the partition.
    const r = rng(seed), n0 = nbrs.length;
    let adj = Array.from({ length: n0 }, () => new Map());
    nbrs.forEach((ns, i) => ns.forEach(j => { adj[i].set(j, 1); adj[j].set(i, 1); }));
    let member = Int32Array.from({ length: n0 }, (_, i) => i);
    for (let level = 0; level < 10; level++) {
      const n = adj.length, deg = Float64Array.from(adj, m => { let s = 0; for (const w of m.values()) s += w; return s; });
      const m2 = deg.reduce((a, b) => a + b, 0) || 1;
      const comm = Int32Array.from({ length: n }, (_, i) => i), tot = Float64Array.from(deg);
      const order = [...Array(n).keys()].sort(() => r() - 0.5);
      let moved = true, any = false, guard = 0;
      while (moved && guard++ < 30) {
        moved = false;
        for (const i of order) {
          const ci = comm[i], ki = deg[i], links = new Map();
          for (const [j, w] of adj[i]) if (j !== i) links.set(comm[j], (links.get(comm[j]) || 0) + w);
          tot[ci] -= ki;
          let best = ci, bestGain = (links.get(ci) || 0) - resolution * tot[ci] * ki / m2;
          for (const [c, w] of links) { const g = w - resolution * tot[c] * ki / m2; if (g > bestGain + 1e-12) { bestGain = g; best = c; } }
          tot[best] += ki;
          if (best !== ci) { comm[i] = best; moved = true; any = true; }
        }
      }
      const ids = new Map(); comm.forEach(c => ids.has(c) || ids.set(c, ids.size));
      member = Int32Array.from(member, m => ids.get(comm[m]));
      if (!any) break;
      const next = Array.from({ length: ids.size }, () => new Map());
      adj.forEach((m, i) => { const a = ids.get(comm[i]); for (const [j, w] of m) { const b = ids.get(comm[j]); next[a].set(b, (next[a].get(b) || 0) + w); } });
      adj = next;
    }
    // Relabel by size, largest cluster = 0, as Scanpy does.
    const size = new Map(); member.forEach(c => size.set(c, (size.get(c) || 0) + 1));
    const rank = new Map([...size.entries()].sort((a, b) => b[1] - a[1]).map(([c], i) => [c, i]));
    return Int32Array.from(member, c => rank.get(c));
  }

  // ---- scores ----
  function ari(a, b) {
    const n = a.length, tab = new Map(), ra = new Map(), rb = new Map();
    for (let i = 0; i < n; i++) { const key = a[i] + "|" + b[i]; tab.set(key, (tab.get(key) || 0) + 1); ra.set(a[i], (ra.get(a[i]) || 0) + 1); rb.set(b[i], (rb.get(b[i]) || 0) + 1); }
    const c2 = x => x * (x - 1) / 2;
    let sij = 0; for (const v of tab.values()) sij += c2(v);
    let sa = 0; for (const v of ra.values()) sa += c2(v);
    let sb = 0; for (const v of rb.values()) sb += c2(v);
    const exp = sa * sb / c2(n), max = (sa + sb) / 2;
    return max === exp ? 1 : (sij - exp) / (max - exp);
  }

  // Share of each cell's neighbours from the other batch, relative to chance.
  function mixing(nbrs, batches) {
    const p2 = batches.filter(b => b === 2).length / batches.length, expect = 2 * p2 * (1 - p2);
    let other = 0, tot = 0;
    nbrs.forEach((ns, i) => ns.forEach(j => { other += batches[j] !== batches[i]; tot++; }));
    return expect ? Math.min(1, (other / tot) / expect) : 1;
  }

  // Treatment signal kept: within each true type, how much more often a cell's
  // neighbours share its condition than chance (1 = fully separated, 0 = mixed).
  function conditionSignal(nbrs, cond, type) {
    const byType = new Map(); type.forEach((t, i) => { if (t >= 0 && t < 7) { const m = byType.get(t) || { n: 0, tr: 0 }; m.n++; m.tr += cond[i] === "treated"; byType.set(t, m); } });
    let obs = 0, exp = 0, n = 0;
    nbrs.forEach((ns, i) => { const t = type[i], m = byType.get(t); if (!m) return;
      const same = ns.filter(j => type[j] === t); if (!same.length) return;
      const p = m.tr / m.n, e = cond[i] === "treated" ? p : 1 - p;
      obs += same.filter(j => cond[j] === cond[i]).length / same.length; exp += e; n++; });
    if (!n) return 0; obs /= n; exp /= n;
    return Math.max(0, Math.min(1, (obs - exp) / (1 - exp)));
  }

  return { generate, conditionSignal, qcFilter, normalise, hvg, scale, pca, correct, knn, louvain, ari, mixing, TYPES, rng };
})();
if (typeof module !== "undefined") module.exports = PlayCore;
