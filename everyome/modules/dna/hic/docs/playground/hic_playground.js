/* Playground for Hi-C: a 4 Mb chromosome in 20 kb bins with known domains (TADs) and compartments. Contacts are drawn
   from a simple model (distance, domain and compartment effects, a bias per bin) with Poisson sampling, then
   optionally balanced (iterative correction) as the pipeline does. Shows the map, contacts against distance and the
   insulation score with the boundaries it finds, scored against the truth. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const N = 200, RES = 20000;

  // Seeded random numbers, so the same settings always give the same map.
  const rng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const poisson = (lam, r) => {
    if (lam > 30) { const u = Math.max(1e-9, r()), v = r(); return Math.max(0, Math.round(lam + Math.sqrt(lam) * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v))); }
    let L = Math.exp(-lam), k = 0, p = 1; do { k++; p *= r(); } while (p > L); return k - 1;
  };

  function layout(tadKb) {
    // Intent: domains of roughly the chosen size (±40%), compartments switching every 2–4 domains.
    const r = rng(7), bounds = [], comp = new Array(N);
    let i = 0, a = true, left = 2 + Math.floor(r() * 3);
    while (i < N) {
      const len = Math.max(3, Math.round(tadKb * 1000 / RES * (0.6 + 0.8 * r())));
      for (let k = i; k < Math.min(N, i + len); k++) comp[k] = a;
      i += len; if (i < N) bounds.push(i);
      if (--left === 0) { a = !a; left = 2 + Math.floor(r() * 3); }
    }
    const tad = new Array(N); let t = 0; for (let k = 0, b = 0; k < N; k++) { if (b < bounds.length && k === bounds[b]) { t++; b++; } tad[k] = t; }
    return { bounds, comp, tad };
  }

  function simulate(S) {
    const { bounds, comp, tad } = layout(S.tad_kb), r = rng(11);
    const bias = Array.from({ length: N }, () => Math.exp((r() * 2 - 1) * S.bias));
    const raw = Array.from({ length: N }, () => new Float64Array(N));
    for (let i = 0; i < N; i++) for (let j = i; j < N; j++) {
      let mu = Math.pow(j - i + 1, -S.alpha) * (tad[i] === tad[j] ? S.tad : 1) * (comp[i] === comp[j] ? S.comp : 1 / S.comp) * bias[i] * bias[j];
      const v = poisson(mu * S.depth, r); raw[i][j] = raw[j][i] = v;
    }
    return { raw, bounds, comp };
  }

  function balance(m) {
    // Iterative correction: scale rows and columns until every row has the same total (diagonal left out).
    const w = new Float64Array(N).fill(1);
    for (let it = 0; it < 60; it++) {
      const tot = Array.from({ length: N }, (_, i) => { let s = 0; for (let j = 0; j < N; j++) if (j !== i) s += m[i][j] * w[i] * w[j]; return s; });
      const mean = tot.reduce((a, b) => a + b, 0) / N;
      for (let i = 0; i < N; i++) if (tot[i] > 0) w[i] /= Math.sqrt(tot[i] / mean);
    }
    return m.map((row, i) => Float64Array.from(row, (v, j) => v * w[i] * w[j]));
  }

  function insulation(m, win) {
    const s = new Array(N).fill(null);
    for (let i = win; i < N - win; i++) { let t = 0; for (let a = i - win; a < i; a++) for (let b = i + 1; b <= i + win; b++) t += m[a][b]; s[i] = t; }
    const v = s.filter(x => x != null).sort((a, b) => a - b), med = v[Math.floor(v.length / 2)] || 1;
    return s.map(x => x == null || x <= 0 ? null : Math.log2(x / med));
  }

  function dips(s, minDepth) {
    const out = [];
    for (let i = 1; i < N - 1; i++) {
      if (s[i] == null || s[i - 1] == null || s[i + 1] == null || !(s[i] < s[i - 1] && s[i] <= s[i + 1])) continue;
      const side = (a, b) => Math.max(...s.slice(a, b).filter(x => x != null), -Infinity);
      if (Math.min(side(Math.max(0, i - 10), i), side(i + 1, i + 11)) - s[i] >= minDepth) out.push(i);
    }
    return out;
  }

  function render(S, el) {
    const C = H.COL(), sim = simulate(S), m = S.balanced === "yes" ? balance(sim.raw) : sim.raw;
    // decay: mean contact per distance, as a probability
    const dec = []; for (let d = 1; d < N / 2; d++) { let t = 0; for (let i = 0; i + d < N; i++) t += m[i][i + d]; dec.push([d * RES, t / (N - d)]); }
    const tot = dec.reduce((a, p) => a + p[1], 0) || 1, curve = dec.map(([d, v]) => [d, v / tot]).filter(p => p[1] > 0);
    const fit = curve.filter(([d]) => d >= 40000 && d <= 1000000), lx = fit.map(p => Math.log10(p[0])), ly = fit.map(p => Math.log10(p[1]));
    const mx = lx.reduce((a, b) => a + b, 0) / lx.length, my = ly.reduce((a, b) => a + b, 0) / ly.length;
    const slope = lx.reduce((a, x, i) => a + (x - mx) * (ly[i] - my), 0) / lx.reduce((a, x) => a + (x - mx) ** 2, 0);
    const ins = insulation(m, 5), found = dips(ins, 0.2);
    const hit = sim.bounds.filter(b => found.some(f => Math.abs(f - b) <= 1)).length, wrong = found.filter(f => !sim.bounds.some(b => Math.abs(f - b) <= 1)).length;
    const contacts = sim.raw.reduce((a, row) => a + row.reduce((x, y) => x + y, 0), 0) / 2;
    // insulation plot
    const w = 560, h = 150, X = i => 10 + i / N * (w - 20), v = ins.filter(x => x != null), lo = Math.min(...v), hi = Math.max(...v), Y = y => 8 + (hi - y) / ((hi - lo) || 1) * (h - 30);
    let path = ""; ins.forEach((y, i) => { if (y != null) path += `${path && ins[i - 1] != null ? "L" : "M"}${X(i).toFixed(1)},${Y(y).toFixed(1)}`; });
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Insulation score">`;
    sim.bounds.forEach(b => svg += `<path d="M${X(b) - 4},${h - 6} L${X(b) + 4},${h - 6} L${X(b)},${h - 14} Z" fill="${C.ink}"><title>True boundary</title></path>`);
    found.forEach(f => svg += `<line x1="${X(f)}" x2="${X(f)}" y1="8" y2="${h - 18}" stroke="${C.ox}"/>`);
    svg += `<path d="${path}" fill="none" stroke="${C.golddk}" stroke-width="1.6"/></svg>`;
    const mt = (k, val, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${val}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">Contact map (log scale)</div><canvas width="400" height="400" style="width:100%;max-width:400px;aspect-ratio:1" role="img" aria-label="Simulated contact map"></canvas>
        <p class="note">${S.balanced === "yes" ? "Balanced: stripes from uneven bins are gone." : "Raw counts: bins with a high or low bias show as stripes."} Squares on the diagonal are domains; the checkerboard is compartments.</p></section>
      <section class="pg-card"><div class="label">Contacts against distance</div>${H.logLine({ "this chromosome": curve }, { xlab: "Distance (bp)", ylab: "Contact probability", h: 220 })}
        <div class="label" style="margin-top:12px">Insulation score (window 5 bins)</div>${svg}
        <p class="note">Lines: boundaries found (dips at least 0.2 deep). Triangles: the true boundaries.</p>
        <div class="metrics">${mt("Slope (40 kb–1 Mb)", slope.toFixed(2), `the model's own exponent is −${S.alpha}`)}
          ${mt("Boundaries found", `${hit} of ${sim.bounds.length}`, `${wrong} in the wrong place`, hit < sim.bounds.length * 0.7 || wrong > 2)}
          ${mt("Contacts", Math.round(contacts).toLocaleString(), `about ${Math.round(contacts / N).toLocaleString()} per bin`, contacts / N < 200)}</div>
        <p class="note">Domains bend the curve: inside a domain contacts fall more slowly, so the slope you measure is not quite the model's.</p></section>`;
    const cv = el.querySelector("canvas"), ctx = cv.getContext("2d"), px = cv.width / N;
    const a = H.hexRgb(C.parch), b = H.hexRgb(C.ox), logs = m.map(row => Array.from(row, x => x > 0 ? Math.log10(x) : null));
    const all = logs.flat().filter(x => x != null).sort((p, q) => p - q), l0 = all[Math.floor(all.length * 0.02)], l1 = all[Math.floor(all.length * 0.995)];
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      const t = logs[i][j] == null ? 0 : Math.max(0, Math.min(1, (logs[i][j] - l0) / ((l1 - l0) || 1)));
      ctx.fillStyle = `rgb(${a.map((x, k) => Math.round(x + (b[k] - x) * t))})`; ctx.fillRect(j * px, i * px, Math.ceil(px), Math.ceil(px));
    }
  }

  window.HiCPlayground = E.makePlayground({
    defaults: { alpha: 1.0, tad: 2.5, tad_kb: 300, comp: 1.4, depth: 40, bias: 0.3, balanced: "yes" },
    controls: [
      { group: "How the chromosome folds", items: [
        { key: "alpha", label: "How fast contacts fall with distance", type: "range", min: 0.5, max: 1.8, step: 0.1, help: "The exponent: contacts ∝ distance^−exponent." },
        { key: "tad", label: "Domain (TAD) strength", type: "range", min: 1, max: 5, step: 0.1, help: "How many times more contacts inside a domain than across a boundary." },
        { key: "tad_kb", label: "Domain size (kb)", type: "range", min: 100, max: 800, step: 20 },
        { key: "comp", label: "Compartment strength", type: "range", min: 1, max: 2.5, step: 0.05, help: "Extra contacts between stretches of the same compartment." }] },
      { group: "The experiment", items: [
        { key: "depth", label: "Sequencing depth", type: "range", min: 1, max: 400, step: 1, help: "Expected contacts between neighbouring bins." },
        { key: "bias", label: "How uneven the bins are", type: "range", min: 0, max: 1, step: 0.05, help: "Restriction sites, GC content and mappability make some bins seen more often." },
        { key: "balanced", label: "Balance the map", type: "select", options: [["yes", "Yes"], ["no", "No: raw counts"]] }] },
    ],
    presets: [
      ["A typical chromosome (the defaults)", {}, "Clear domains on the diagonal, a faint checkerboard of compartments, and most boundaries found."],
      ["Too shallow to see domains", { depth: 2 }, "With few contacts per bin, the map is speckled and the insulation score finds boundaries in the wrong places."],
      ["Uneven bins, not balanced", { bias: 0.8, balanced: "no" }, "Stripes across the map from bins seen more or less often; balancing removes them."],
      ["No domains, only compartments", { tad: 1, comp: 2 }, "A strong checkerboard but no squares: the insulation score finds little."],
      ["Contacts fall slowly", { alpha: 0.6 }, "Far places touch almost as often as near ones; domains are harder to see against the background."],
    ],
    render,
  });
})();
