/* Playground UI: controls, cached pipeline, and the output panels. */
const Playground = (() => {
  const C = PlayCore;
  // Everyome: take colours from the active theme when running inside the app; house colours otherwise.
  const THEME = typeof window !== "undefined" && window.Everyome ? window.Everyome.helpers : null;
  const COL = THEME ? THEME.COL() : { gold: "#C2A24A", golddk: "#8F7529", goldlt: "#DFC684", ox: "#6E1B2B", wine: "#8E2438", plum: "#32203A",
    ink: "#1C1620", muted: "#5A5260", rule: "#D6CBB6", card: "#FBF7EF", parch: "#E7DECC", lav: "#B9AEC0" };
  const lav = () => lav() || COL.gold;
  const clusterCols = () => THEME ? THEME.PALETTE() : CLUSTER_COLS;
  const typeCols = () => THEME ? THEME.PALETTE() : TYPE_COLS;
  const CLUSTER_COLS = ["#C2A24A", "#6E1B2B", "#32203A", "#8F7529", "#A83B50", "#5A5260", "#DFC684", "#0E8F8A",
    "#B9AEC0", "#9C7A3C", "#3A3143", "#93283C", "#CBA75A", "#6B2118", "#7C6A85", "#E0B3A0"];
  const TYPE_COLS = ["#32203A", "#B9AEC0", "#6E1B2B", "#C2A24A", "#8F7529", "#DFC684", "#0E8F8A", "#A83B50"];
  const DEFAULTS = { seed: 1, design: "balanced", minUmis: 200, maxUmis: 1100, nHvg: 150, nPcs: 15, corr: 1, k: 15, res: 1, minDist: 0.3, colorBy: "cluster" };

  const CONTROLS = [
    { group: "Experiment", stage: "", items: [
      { key: "design", label: "Batch design", type: "select", options: [["balanced", "Balanced"], ["confounded", "Confounded (batch = condition)"]],
        help: "Balanced puts each condition in both batches; confounded prepares each condition in its own batch." },
      { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1, help: "Draws a new toy dataset with the same design." }] },
    { group: "Filter cells", stage: "11", items: [
      { key: "minUmis", label: "Minimum UMIs per cell", type: "range", min: 0, max: 400, step: 10, help: "Removes near-empty barcodes." },
      { key: "maxUmis", label: "Maximum UMIs per cell", type: "range", min: 700, max: 3000, step: 50, help: "Removes likely doublets. 3000 keeps them all." }] },
    { group: "Integrate and cluster", stage: "12", items: [
      { key: "nHvg", label: "Highly variable genes", type: "range", min: 20, max: 300, step: 10, help: "Genes used for PCA." },
      { key: "nPcs", label: "Principal components used", type: "range", min: 2, max: 30, step: 1, help: "Dimensions for the neighbour graph." },
      { key: "corr", label: "Batch correction strength", type: "range", min: 0, max: 1, step: 0.1, help: "0 = none. Simplified stand-in for Harmony." },
      { key: "k", label: "Neighbours (k)", type: "range", min: 5, max: 50, step: 1, help: "Size of each cell's neighbourhood." },
      { key: "res", label: "Clustering resolution", type: "range", min: 0.05, max: 5, step: 0.05, help: "Higher = more, smaller clusters." },
      { key: "minDist", label: "UMAP min_dist", type: "range", min: 0.05, max: 0.9, step: 0.05, help: "How tightly points pack. Display only." }] },
  ];

  const PRESETS = [
    ["Start from the defaults", {}, "A balanced design, doublets filtered, correction on. Clusters should match the eight true types closely."],
    ["Turn batch correction off", { corr: 0 }, "Colour by batch: each type splits in two and agreement with the true types drops."],
    ["Lower the resolution to 0.2", { res: 0.2 }, "Epithelial A and B share most markers and merge, so stage 15 composition lumps them together."],
    ["Raise the resolution to 4", { res: 4 }, "The progenitor continuum gets cut into arbitrary pieces. More clusters is not more biology."],
    ["Keep every doublet", { maxUmis: 3000 }, "Colour by QC class: doublets sit between real clusters and can form spurious intermediates."],
    ["Keep near-empty barcodes", { minUmis: 0 }, "Low-quality barcodes collect into a cluster with no real markers."],
    ["Use only 3 principal components", { nPcs: 3 }, "Too few dimensions to separate eight types; several merge."],
    ["Confound batch with condition", { design: "confounded" }, "With correction on, the treatment response is removed along with the batch effect: watch the treatment-signal score fall."],
  ];

  let S = { ...DEFAULTS }, cache = {}, root = null, umapJob = 0, timer = null, umapBusy = false;
  const key = (...ks) => ks.map(k => S[k]).join("|");

  // ---------------- pipeline with caching ----------------
  function compute() {
    if (cache.dataKey !== key("seed", "design")) { cache = { dataKey: key("seed", "design"), data: C.generate({ seed: S.seed, design: S.design }) }; }
    const d = cache.data;
    if (cache.qcKey !== key("minUmis", "maxUmis") || !cache.idx) {
      cache.qcKey = key("minUmis", "maxUmis"); cache.idx = C.qcFilter(d, S); cache.X = C.normalise(d, cache.idx); cache.pcaKey = null;
    }
    const idx = cache.idx;
    if (cache.pcaKey !== key("nHvg")) {
      cache.pcaKey = key("nHvg"); cache.pca = C.pca(C.scale(cache.X, C.hvg(cache.X, S.nHvg)), 30); cache.corrKey = null;
    }
    const batch = idx.map(i => d.cells[i].batch);
    if (cache.corrKey !== key("corr")) { cache.corrKey = key("corr"); cache.Y = C.correct(cache.pca.scores, batch, S.corr); cache.knnKey = null; }
    if (cache.knnKey !== key("nPcs", "k")) { cache.knnKey = key("nPcs", "k"); cache.emb = null; cache.nbrs = C.knn(cache.Y, S.nPcs, S.k); cache.clKey = null; cache.umapKey = null; }
    if (cache.clKey !== key("res")) { cache.clKey = key("res"); cache.cl = C.louvain(cache.nbrs, S.res); }
    const cells = idx.map(i => d.cells[i]);
    const truth = cells.map(c => c.kind === "cell" ? c.type : c.kind === "doublet" ? 100 : 101);
    cache.metrics = {
      kept: idx.length, total: d.cells.length,
      doublets: cells.filter(c => c.kind === "doublet").length, low: cells.filter(c => c.kind === "low").length,
      clusters: new Set(cache.cl).size, ari: C.ari(cache.cl, truth), mixing: C.mixing(cache.nbrs, batch),
      signal: C.conditionSignal(cache.nbrs, cells.map(c => c.condition), cells.map(c => c.kind === "cell" ? c.type : -1)),
    };
    if (cache.umapKey !== key("minDist") + "|" + cache.knnKey) { cache.umapKey = key("minDist") + "|" + cache.knnKey; runUmap(); }
  }

  function runUmap() {
    cache.emb = null; const job = ++umapJob, data = cache.Y.map(r => Array.from(r.slice(0, S.nPcs)));
    const rand = C.rng(11);
    const u = new UMAP.UMAP({ nComponents: 2, nNeighbors: Math.min(S.k, data.length - 1), minDist: S.minDist, nEpochs: window.PG_EPOCHS || 160, random: rand });
    const status = root.querySelector("[data-status]");
    status.textContent = "Laying out cells…"; umapBusy = true;
    setTimeout(() => {
      if (job !== umapJob) return;
      const n = u.initializeFit(data);
      let e = 0;
      const step = () => {
        if (job !== umapJob) return;
        for (let i = 0; i < 8 && e < n; i++, e++) u.step();
        cache.emb = u.getEmbedding(); drawScatter();
        if (e < n) requestAnimationFrame(step); else { status.textContent = ""; umapBusy = false; }
      };
      step();
    }, 20);
  }

  function schedule() {
    clearTimeout(timer);
    root.querySelector("[data-status]").textContent = "Recomputing…";
    timer = setTimeout(() => { compute(); drawAll(); }, 30);
  }

  // ---------------- drawing ----------------
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function colourOf(i) {
    const c = cache.data.cells[cache.idx[i]];
    switch (S.colorBy) {
      case "type": return c.kind === "cell" ? typeCols()[c.type] : COL.rule;
      case "batch": return c.batch === 1 ? COL.gold : COL.ox;
      case "condition": return c.condition === "control" ? lav() : COL.ox;
      case "qc": return c.kind === "cell" ? COL.golddk : c.kind === "doublet" ? COL.wine : COL.muted;
      default: return clusterCols()[cache.cl[i] % clusterCols().length];
    }
  }

  function legendItems() {
    const d = cache.data;
    switch (S.colorBy) {
      case "type": return d.types.map((t, i) => [t, typeCols()[i]]).concat([["doublet / low quality", COL.rule]]);
      case "batch": return [["batch 1", COL.gold], ["batch 2", COL.ox]];
      case "condition": return [["control", lav()], ["treated", COL.ox]];
      case "qc": return [["cell", COL.golddk], ["doublet", COL.wine], ["near-empty", COL.muted]];
      default: return [...new Set(cache.cl)].sort((a, b) => a - b).map(c => [String(c), clusterCols()[c % clusterCols().length]]);
    }
  }

  function drawScatter() {
    const cv = root.querySelector("canvas"); if (!cv || !cache.emb || cache.emb.length !== cache.idx.length) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr; const r = window.PG_DOT || 2.6;
    const g = cv.getContext("2d"); g.scale(dpr, dpr); g.fillStyle = COL.card; g.fillRect(0, 0, W, H);
    const E = cache.emb; let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const [x, y] of E) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    const pad = 16, sx = (W - 2 * pad) / ((x1 - x0) || 1), sy = (H - 2 * pad) / ((y1 - y0) || 1), s = Math.min(sx, sy);
    const ox = (W - s * (x1 - x0)) / 2, oy = (H - s * (y1 - y0)) / 2;
    E.forEach(([x, y], i) => { g.fillStyle = colourOf(i); g.globalAlpha = .85; g.beginPath();
      g.arc(ox + (x - x0) * s, oy + (y - y0) * s, r, 0, 2 * Math.PI); g.fill(); });
    g.globalAlpha = 1;
    if (S.colorBy === "cluster") {
      // Intent: cluster numbers at their centroids, outlined for legibility.
      const cen = new Map(); E.forEach(([x, y], i) => { const c = cache.cl[i], m = cen.get(c) || [0, 0, 0]; m[0] += x; m[1] += y; m[2]++; cen.set(c, m); });
      g.font = "600 13px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.lineWidth = 3; g.strokeStyle = COL.card; g.fillStyle = COL.ink;
      for (const [c, [x, y, n]] of cen) { const px = ox + (x / n - x0) * s, py = oy + (y / n - y0) * s; g.strokeText(c, px, py); g.fillText(c, px, py); }
    }
    root.querySelector("[data-legend]").innerHTML = legendItems().map(([l, c]) => `<span><i style="background:${c}"></i>${esc(l)}</span>`).join("");
  }

  function drawMetrics() {
    const m = cache.metrics, pct = x => Math.round(x * 100) + "%";
    const rows = [
      ["Cells after QC", `${m.kept} of ${m.total}`, "stage 11"],
      ["Doublets kept", m.doublets, m.doublets > 25 ? "warn" : "of " + cache.data.cells.filter(c => c.kind === "doublet").length],
      ["Near-empty kept", m.low, m.low > 10 ? "warn" : "of " + cache.data.cells.filter(c => c.kind === "low").length],
      ["Clusters", m.clusters, "8 true types"],
      ["Agreement with true types", m.ari.toFixed(2), m.ari < 0.8 ? "warn" : "adjusted Rand index"],
      ["Batch mixing", pct(m.mixing), m.mixing < 0.7 ? "warn" : "100% = fully mixed"],
      ["Treatment signal kept", pct(m.signal), m.signal < 0.2 ? "warn" : "within-type separation"],
    ];
    root.querySelector("[data-metrics]").innerHTML = rows.map(([k, v, n]) =>
      `<div class="m${n === "warn" ? " warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n === "warn" ? "check" : n}</span></div>`).join("");
  }

  function svgBars(vals, { w = 360, h = 120, mark = null, color = COL.golddk, xlab = "", ylab = "" }) {
    const max = Math.max(...vals), bw = (w - 30) / vals.length;
    return `<svg viewBox="0 0 ${w} ${h + 26}" class="mini">${vals.map((v, i) => `<rect x="${30 + i * bw}" y="${h - v / max * h}" width="${bw - 1.5}" height="${v / max * h}" fill="${mark !== null && i >= mark ? COL.rule : color}"/>`).join("")}
      ${mark !== null ? `<line x1="${30 + mark * bw - 1}" x2="${30 + mark * bw - 1}" y1="0" y2="${h}" stroke="${COL.ox}" stroke-dasharray="3 3"/>` : ""}
      <line x1="30" x2="${w}" y1="${h}" y2="${h}" stroke="${COL.muted}"/>
      <text x="${30}" y="${h + 18}" class="ax">${xlab}</text><text x="0" y="10" class="ax">${ylab}</text></svg>`;
  }

  function drawQcHist() {
    // Intent: UMIs per barcode on a log axis, stacked by true QC class, with thresholds.
    const d = cache.data, lo = Math.log10(20), hi = Math.log10(4000), nb = 40, w = 360, h = 110;
    const bins = ["cell", "doublet", "low"].map(() => new Array(nb).fill(0));
    d.cells.forEach(c => { const b = Math.max(0, Math.min(nb - 1, Math.floor((Math.log10(Math.max(c.umis, 20)) - lo) / (hi - lo) * nb)));
      bins[c.kind === "cell" ? 0 : c.kind === "doublet" ? 1 : 2][b]++; });
    const tot = bins[0].map((_, i) => bins[0][i] + bins[1][i] + bins[2][i]), max = Math.max(...tot), bw = (w - 10) / nb;
    const xp = v => 10 + (Math.log10(Math.max(v, 20)) - lo) / (hi - lo) * (w - 10);
    let rects = "";
    for (let i = 0; i < nb; i++) { let y = h; [[0, COL.golddk], [1, COL.wine], [2, COL.muted]].forEach(([k, c]) => {
      const hh = bins[k][i] / max * h; y -= hh; if (hh > 0) rects += `<rect x="${10 + i * bw}" y="${y}" width="${bw - 1}" height="${hh}" fill="${c}"/>`; }); }
    const line = (v, lab) => v <= 4000 ? `<line x1="${xp(v)}" x2="${xp(v)}" y1="0" y2="${h}" stroke="${COL.ox}" stroke-dasharray="3 3"/><text x="${xp(v) + 3}" y="10" class="ax">${lab}</text>` : "";
    return `<svg viewBox="0 0 ${w} ${h + 26}" class="mini">${rects}<line x1="10" x2="${w}" y1="${h}" y2="${h}" stroke="${COL.muted}"/>
      ${line(S.minUmis || 20, "min")}${S.maxUmis < 3000 ? line(S.maxUmis, "max") : ""}
      <text x="10" y="${h + 18}" class="ax">UMIs per barcode (log scale), 20 to 4,000</text></svg>
      <div class="legend small"><span><i style="background:${COL.golddk}"></i>cell</span><span><i style="background:${COL.wine}"></i>doublet</span><span><i style="background:${COL.muted}"></i>near-empty</span></div>`;
  }

  function drawDotplot() {
    // Intent: one marker per true type; dot size = share expressing, colour = mean log expression.
    const d = cache.data, X = cache.X, cl = cache.cl, ks = [...new Set(cl)].sort((a, b) => a - b).slice(0, 20);
    const genes = d.markers, cw = 40, rh = 20, left = 34, top = 92, W = left + genes.length * cw + 10, H = top + ks.length * rh + 6;
    const stats = ks.map(k => genes.map(g => { let n = 0, e = 0, s = 0; cl.forEach((c, i) => { if (c !== k) return; n++; const v = X[i][g]; if (v > 0) { e++; s += v; } });
      return { frac: n ? e / n : 0, mean: e ? s / e : 0 }; }));
    // Intent: colour scaled per gene across clusters (Scanpy standard_scale="var").
    const gMin = genes.map((_, j) => Math.min(...stats.map(r => r[j].mean))), gMax = genes.map((_, j) => Math.max(...stats.map(r => r[j].mean)));
    const mix = t => { const a = [231, 222, 204], b = [110, 27, 43], c = a.map((v, i) => Math.round(v + (b[i] - v) * t)); return `rgb(${c})`; };
    let out = `<svg viewBox="0 0 ${W} ${H}" class="dot">`;
    genes.forEach((g, j) => { out += `<text transform="translate(${left + j * cw + cw / 2 + 4},${top - 8}) rotate(-50)" class="ax">${esc(d.types[j])}</text>`; });
    ks.forEach((k, r) => { out += `<text x="${left - 8}" y="${top + r * rh + rh / 2 + 4}" text-anchor="end" class="ax">${k}</text>`;
      stats[r].forEach((s, j) => { if (s.frac > 0.02) out += `<circle cx="${left + j * cw + cw / 2}" cy="${top + r * rh + rh / 2}" r="${1.5 + 7.5 * s.frac}" fill="${mix((s.mean - gMin[j]) / ((gMax[j] - gMin[j]) || 1))}" stroke="${COL.rule}" stroke-width=".5"/>`; }); });
    return out + `</svg><p class="note">Columns: one marker gene per true type. Dot size = share of cells expressing; colour = mean expression, scaled per gene. Rows: clusters${ks.length < new Set(cl).size ? " (first 20)" : ""}.</p>`;
  }

  function drawComposition() {
    // Intent: stage 15 analogue. Each cluster is named after its majority true type, then
    // composition per condition is compared with the truth used to simulate the data.
    const d = cache.data, cells = cache.idx.map(i => d.cells[i]), cl = cache.cl;
    const labelOf = new Map();
    [...new Set(cl)].forEach(k => { const cnt = new Map(); cl.forEach((c, i) => { if (c === k) { const t = cells[i].kind === "cell" ? cells[i].type : -1; cnt.set(t, (cnt.get(t) || 0) + 1); } });
      labelOf.set(k, [...cnt.entries()].sort((a, b) => b[1] - a[1])[0][0]); });
    const rows = [];
    for (const cond of ["control", "treated"]) {
      const est = new Array(8).fill(0), tru = new Array(8).fill(0); let n = 0;
      cells.forEach((c, i) => { if (c.condition !== cond) return; n++; const l = labelOf.get(cl[i]); if (l >= 0) est[l]++; if (c.kind === "cell") tru[c.type]++; });
      rows.push([cond + ", from clusters", est.map(v => v / n)], [cond + ", truth", tru.map(v => v / n)]);
    }
    const w = 520, bh = 18, gap = 10, left = 130;
    let out = `<svg viewBox="0 0 ${w} ${rows.length * (bh + gap) + 8}" class="comp">`;
    rows.forEach(([lab, fr], r) => { let x = left; const y = r * (bh + gap) + (r >= 2 ? 8 : 0);
      out += `<text x="${left - 8}" y="${y + 13}" text-anchor="end" class="ax${lab.endsWith("truth") ? " it" : ""}">${esc(lab)}</text>`;
      fr.forEach((f, t) => { const ww = f * (w - left - 4); if (ww > 0) out += `<rect x="${x}" y="${y}" width="${ww}" height="${bh}" fill="${typeCols()[t]}" opacity="${lab.endsWith("truth") ? .55 : 1}"><title>${esc(d.types[t])}: ${(f * 100).toFixed(1)}%</title></rect>`; x += ww; }); });
    out += `</svg><div class="legend small">${d.types.map((t, i) => `<span><i style="background:${typeCols()[i]}"></i>${esc(t)}</span>`).join("")}</div>`;
    const merged = d.types.filter((_, t) => ![...labelOf.values()].includes(t));
    return out + `<p class="note">${merged.length ? `Not recovered as its own cluster: <b>${merged.map(esc).join(", ")}</b>. Their cells are counted under a neighbouring type.` : "Every true type was recovered as at least one cluster."}</p>`;
  }

  function drawAll() {
    drawMetrics(); drawScatter();
    root.querySelector("[data-qc]").innerHTML = drawQcHist();
    root.querySelector("[data-pca]").innerHTML = svgBars(cache.pca.varRatio, { w: 280, h: 110, mark: S.nPcs, xlab: `PCs 1–30; ${S.nPcs} used`, ylab: "" });
    root.querySelector("[data-dot]").innerHTML = drawDotplot();
    root.querySelector("[data-comp]").innerHTML = drawComposition();
    if (!umapBusy) root.querySelector("[data-status]").textContent = "";
  }

  // ---------------- controls ----------------
  function controlHtml(c) {
    const v = S[c.key];
    if (c.type === "select") return `<label class="ctl"><span class="lab">${c.label}</span>
      <select data-key="${c.key}">${c.options.map(([val, txt]) => `<option value="${val}"${val === v ? " selected" : ""}>${txt}</option>`).join("")}</select><span class="help">${c.help}</span></label>`;
    return `<label class="ctl"><span class="lab">${c.label}<output data-out="${c.key}">${fmt(c.key, v)}</output></span>
      <input type="range" data-key="${c.key}" min="${c.min}" max="${c.max}" step="${c.step}" value="${v}"><span class="help">${c.help}</span></label>`;
  }
  const fmt = (k, v) => k === "maxUmis" && v >= 3000 ? "no limit" : (k === "corr" || k === "res" || k === "minDist") ? Number(v).toFixed(2) : v;

  function setParams(p) {
    Object.assign(S, p);
    root.querySelectorAll("[data-key]").forEach(el => { el.value = S[el.dataset.key]; });
    root.querySelectorAll("[data-out]").forEach(el => { el.textContent = fmt(el.dataset.out, S[el.dataset.out]); });
    root.querySelectorAll("[data-color]").forEach(b => b.setAttribute("aria-pressed", b.dataset.color === S.colorBy));
    schedule();
  }

  function mount(el) {
    root = el;
    el.innerHTML = `
      <div class="pg">
        <div class="pg-controls a-ctl">${CONTROLS.map(g => `<section class="pg-card"><div class="label">${g.stage ? "Stage " + g.stage + " · " : ""}${g.group}</div>${g.items.map(controlHtml).join("")}</section>`).join("")}
          <button type="button" class="pg-reset" data-reset>Reset all settings</button></div>
        <section class="pg-card a-umap">
          <div class="pg-head"><div class="label">Stage 12 · UMAP of the corrected embedding</div><span class="status" data-status aria-live="polite"></span></div>
          <div class="seg-btns" role="group" aria-label="Colour cells by">${[["cluster", "Cluster"], ["type", "True type"], ["batch", "Batch"], ["condition", "Condition"], ["qc", "QC class"]]
            .map(([k, l]) => `<button type="button" data-color="${k}" aria-pressed="${k === S.colorBy}">${l}</button>`).join("")}</div>
          <canvas aria-label="Scatter plot of cells in the UMAP embedding"></canvas>
          <div class="legend" data-legend></div>
        </section>
        <section class="pg-card a-met"><div class="label">How well did it do?</div><div class="metrics" data-metrics></div></section>
        <section class="pg-card a-qc"><div class="label">Stage 11 · UMIs per barcode</div><div data-qc></div></section>
        <section class="pg-card a-pca"><div class="label">Stage 12 · Variance per PC</div><div data-pca></div></section>
        <section class="pg-card a-dot"><div class="label">Stage 13 · Marker dotplot by cluster</div><div data-dot></div></section>
        <section class="pg-card a-comp"><div class="label">Stage 15 · Composition per condition</div><div data-comp></div></section>
      </div>`;
    el.addEventListener("input", e => { const k = e.target.dataset.key; if (!k) return;
      const v = e.target.type === "range" ? Number(e.target.value) : e.target.value; S[k] = v;
      const out = el.querySelector(`[data-out="${k}"]`); if (out) out.textContent = fmt(k, v);
      if (e.target.type !== "range") schedule(); });
    el.addEventListener("change", e => { if (e.target.dataset.key && e.target.type === "range") schedule(); });
    el.addEventListener("click", e => {
      const b = e.target.closest("[data-color]"); if (b) { S.colorBy = b.dataset.color; el.querySelectorAll("[data-color]").forEach(x => x.setAttribute("aria-pressed", x === b)); drawScatter(); }
      if (e.target.closest("[data-reset]")) setParams({ ...DEFAULTS });
    });
    if (!window.__pgResize) { window.__pgResize = true; window.addEventListener("resize", () => root && root.isConnected && drawScatter()); }
    cache.umapKey = null; schedule();
  }

  function presetsHtml() {
    return `<ol class="tries">${PRESETS.map(([t, p, d], i) => `<li><button type="button" data-preset="${i}">${esc(t)}</button><span>${esc(d)}</span></li>`).join("")}</ol>`;
  }
  function applyPreset(i) {
    const p = PRESETS[i][1]; setParams({ ...DEFAULTS, ...p, colorBy: i === 1 ? "batch" : i === 4 || i === 5 ? "qc" : i === 7 ? "condition" : "cluster" });
    root.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }

  return { mount, presetsHtml, applyPreset };
})();
// Everyome: expose the playground so the app can find it by name.
if (typeof window !== "undefined") window.Playground = Playground;
