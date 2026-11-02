/* Playground for structure prediction: a simulated protein with two domains, a linker and loose ends. Set how ordered
   each part really is and whether the domains hold each other; see the pLDDT and predicted aligned error a
   well-calibrated predictor would report, the domains Everyome would find, and pTM. Runs in the browser; built with
   Everyome's shared playground builder. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc, fmt } = H;
  const BAND = [["very high", 90, "#0053D6"], ["confident", 70, "#65CBF3"], ["low", 50, "#FFDB13"], ["very low", 0, "#FF7D45"]];

  function rng(seed) {
    let a = seed >>> 0;
    const r = () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    r.norm = () => Math.sqrt(-2 * Math.log(r() || 1e-12)) * Math.cos(2 * Math.PI * r());
    return r;
  }

  // The protein: N tail, domain A, linker, domain B, C tail. Each residue gets a region and a pLDDT.
  function protein(S) {
    const r = rng(S.seed), parts = [["tail", S.tails], ["A", 110], ["linker", S.linker], ["B", 90], ["tail", S.tails]];
    const region = parts.flatMap(([k, n]) => Array(n).fill(k));
    // Order 0–1 becomes pLDDT: ordered domains near 92, disordered parts near 35 (with a little noise).
    const level = { A: 35 + 57 * S.orderA, B: 35 + 57 * S.orderB, linker: 32 + 20 * S.linkerOrder, tail: 32 };
    const plddt = region.map(k => Math.max(15, Math.min(98, level[k] + 3.5 * r.norm())));
    const n = region.length, pae = Array.from({ length: n }, () => new Float32Array(n));
    const firm = S.packed === "yes";
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const a = region[i], b = region[j], ci = plddt[i], cj = plddt[j];
      let v;
      if (i === j) v = 0.25;
      // Inside a confident domain real PAE is about 1–2 Å; across a firm interface a little more.
      else if (a === b && (a === "A" || a === "B")) v = 0.5 + (100 - Math.min(ci, cj)) * 0.08 + Math.abs(i - j) / n * 1.5;
      else if ((a === "A" || a === "B") && (b === "A" || b === "B")) v = firm ? 1.8 + (100 - Math.min(ci, cj)) * 0.1 : 18 + 8 * (1 - S.linkerOrder);
      else v = 14 + 14 * (1 - Math.min(ci, cj) / 100);
      pae[i][j] = Math.min(31.75, Math.max(0.25, v + 0.6 * r.norm()));
    }
    return { region, plddt, pae, n };
  }

  // The same rule the module uses: confident stretches, joined where the mean PAE between them is below 5 Å.
  function domains(p) {
    const runs = [];
    for (let i = 0; i < p.n;) {
      if (p.plddt[i] >= 70) { let j = i; while (j + 1 < p.n && p.plddt[j + 1] >= 70) j++; if (j - i + 1 >= 5) runs.push([[i, j]]); i = j + 1; } else i++;
    }
    const idx = g => g.flatMap(([a, b]) => Array.from({ length: b - a + 1 }, (_, k) => a + k));
    const mean = (I, J) => { let s = 0; for (const i of I) for (const j of J) s += p.pae[i][j]; return s / (I.length * J.length); };
    for (let merged = true; merged && runs.length > 1;) {
      merged = false; let best = null;
      for (let x = 0; x < runs.length; x++) for (let y = x + 1; y < runs.length; y++) {
        const I = idx(runs[x]), J = idx(runs[y]), m = (mean(I, J) + mean(J, I)) / 2;
        if (m < 5 && (!best || m < best[0])) best = [m, x, y];
      }
      if (best) { runs[best[1]] = runs[best[1]].concat(runs[best[2]]).sort((a, b) => a[0] - b[0]); runs.splice(best[2], 1); merged = true; }
    }
    return runs.filter(g => idx(g).length >= 20);
  }

  // pTM as AlphaFold defines it from the aligned error: the best residue to align on, scored by the TM-score kernel.
  function ptm(p) {
    const d0 = 1.24 * Math.cbrt(Math.max(p.n, 19) - 15) - 1.8;
    let best = 0;
    for (let i = 0; i < p.n; i++) { let s = 0; for (let j = 0; j < p.n; j++) s += 1 / (1 + (p.pae[i][j] / d0) ** 2); best = Math.max(best, s / p.n); }
    return best;
  }

  function plddtSvg(p, doms) {
    const C = H.COL(), w = 560, h = 170, L = 34, X = i => L + i / (p.n - 1) * (w - L - 8), Y = v => 8 + (100 - v) / 100 * (h - 34);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="pLDDT along the sequence">`;
    BAND.forEach(([, lo, col], i) => { const hi = i ? BAND[i - 1][1] : 100; s += `<rect x="${L}" y="${Y(hi)}" width="${w - L - 8}" height="${Y(lo) - Y(hi)}" fill="${col}" opacity=".14"/>`; });
    [0, 50, 70, 90].forEach(v => s += `<text x="${L - 5}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v}</text>`);
    let run = 0;
    for (let i = 1; i <= p.n; i++) if (i === p.n || p.region[i] !== p.region[run]) {
      s += `<text x="${(X(run) + X(i - 1)) / 2}" y="${h - 6}" text-anchor="middle" class="ax">${p.region[run] === "A" ? "domain A" : p.region[run] === "B" ? "domain B" : p.region[run]}</text>`; run = i; }
    doms.forEach(g => g.forEach(([a, b]) => s += `<rect x="${X(a)}" y="${h - 26}" width="${X(b) - X(a)}" height="5" fill="${C.golddk}"/>`));
    s += `<polyline fill="none" stroke="${C.ink}" stroke-width="1.5" points="${Array.from(p.plddt, (v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`;
    return s + "</svg>";
  }

  // The protein drawn as two blobs on a linker; with a loose linker, faint copies show other arrangements it could take.
  function cartoon(S, p) {
    const C = H.COL(), P = H.PALETTE(), w = 300, h = 170, r = rng(S.seed + 3), firm = S.packed === "yes";
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" style="max-width:${w}px" role="img" aria-label="Sketch of the protein">`;
    const ax = 95, ay = 90, ra = 26 + 4 * S.orderA, rb = 22 + 4 * S.orderB;
    const blob = (x, y, rad, col, order, o = 1) => `<circle cx="${x}" cy="${y}" r="${rad}" fill="${col}" fill-opacity="${(0.25 + 0.6 * order) * o}" stroke="${col}" stroke-opacity="${o}" ${order < 0.5 ? 'stroke-dasharray="4 3"' : ""}/>`;
    const where = k => firm ? [ax + ra + rb - 6, ay] : [ax + 95 + 25 * Math.cos(k), ay + 45 * Math.sin(k)];
    if (!firm) for (let k = 0; k < 5; k++) { const [x, y] = where(r() * 6.28); s += blob(x, y, rb, P[1], S.orderB, 0.25); }
    const [bx, by] = firm ? where(0) : [ax + 110, ay - 10];
    if (!firm) s += `<path d="M${ax + ra},${ay} C${ax + ra + 30},${ay - 40} ${bx - rb - 30},${by + 40} ${bx - rb},${by}" fill="none" stroke="${C.muted}" stroke-width="2" stroke-dasharray="${S.linkerOrder > .5 ? "0" : "3 3"}"/>`;
    s += blob(ax, ay, ra, P[0], S.orderA) + blob(bx, by, rb, P[1], S.orderB);
    s += `<path d="M${ax - ra},${ay} q-14,${-10 - S.tails / 3} -${10 + S.tails / 2},${-5}" fill="none" stroke="${C.muted}" stroke-dasharray="3 3"/>`;
    s += `<text x="${ax}" y="${ay + 4}" text-anchor="middle" class="ax">A</text><text x="${bx}" y="${by + 4}" text-anchor="middle" class="ax">B</text>`;
    return s + `</svg><p class="small muted">${firm ? "The domains hold each other: one arrangement." : "The linker lets domain B move: faint copies show other places it could be."} Dashed: disordered.</p>`;
  }

  function render(S, el) {
    const p = protein(S), doms = domains(p), score = ptm(p), C = H.COL();
    const mean = p.plddt.reduce((a, b) => a + b, 0) / p.n, conf = p.plddt.filter(v => v >= 70).length / p.n;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">What the prediction would say</div><div class="metrics">
        ${m("Mean pLDDT", mean.toFixed(1), "over every residue, loose ends included", mean < 70 && conf > 0.4)}
        ${m("Confident residues", Math.round(100 * conf) + "%", "pLDDT 70 or more")}
        ${m("Domains found", doms.length, doms.length === 2 ? "A and B, each rigid, not fixed to each other" : doms.length === 1 ? (S.packed === "yes" && S.orderA > .6 && S.orderB > .6 ? "A and B move as one unit" : "one confident unit") : "nothing both confident and rigid", false)}
        ${m("pTM", score.toFixed(2), score > 0.7 ? "a confident overall fold" : score > 0.4 ? "parts are confident, the whole is not" : "no confident overall fold", score < 0.4 && conf > 0.5)}</div></section>
      <section class="pg-card"><div class="label">pLDDT along the sequence (bars under the line: domains found)</div>${plddtSvg(p, doms)}</section>
      <section class="pg-card"><div class="label">Predicted aligned error, and the protein</div><div class="row" style="gap:18px;flex-wrap:wrap;align-items:flex-start">
        <div><canvas id="pg-pae" style="width:260px;height:260px" aria-label="Predicted aligned error"></canvas>
          <div class="legend"><span><i style="background:${C.plum}"></i>0 Å</span><span><i style="background:${C.card};border:1px solid ${C.rule}"></i>30 Å</span></div></div>
        <div>${cartoon(S, p)}</div></div></section>`;
    const cv = el.querySelector("#pg-pae"), dpr = window.devicePixelRatio || 1, ctx = cv.getContext("2d"), size = 260;
    cv.width = cv.height = size * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const lo = H.hexRgb(C.plum), hi = H.hexRgb(C.card), step = Math.ceil(p.n / 130), cells = Math.ceil(p.n / step), cs = size / cells;
    for (let a = 0; a < cells; a++) for (let b = 0; b < cells; b++) {
      const t = Math.min(1, p.pae[Math.min(p.n - 1, a * step)][Math.min(p.n - 1, b * step)] / 30);
      ctx.fillStyle = `rgb(${lo.map((v, k) => Math.round(v + (hi[k] - v) * t))})`; ctx.fillRect(b * cs, a * cs, cs + .6, cs + .6);
    }
    ctx.strokeStyle = C.gold; ctx.lineWidth = 2;
    doms.forEach(g => { const a = g[0][0], b = g[g.length - 1][1] + 1; ctx.strokeRect(a / step * cs, a / step * cs, (b - a) / step * cs, (b - a) / step * cs); });
  }

  window.ProteinPlayground = E.makePlayground({
    defaults: { seed: 1, orderA: 1, orderB: 1, packed: "no", linker: 15, linkerOrder: 0.1, tails: 10 },
    controls: [
      { group: "Domains", items: [
        { key: "orderA", label: "How ordered domain A really is", type: "range", min: 0, max: 1, step: 0.05, help: "1: a well-folded domain the predictor knows well. 0: disordered." },
        { key: "orderB", label: "How ordered domain B really is", type: "range", min: 0, max: 1, step: 0.05, help: "Lower it for a domain with few relatives in the databases, which predictors find harder." },
        { key: "packed", label: "The domains pack against each other", type: "select", options: [["no", "No: joined only by the linker"], ["yes", "Yes: a firm interface"]] }] },
      { group: "Linker and ends", items: [
        { key: "linker", label: "Linker length (residues)", type: "range", min: 5, max: 80, step: 1 },
        { key: "linkerOrder", label: "How ordered the linker is", type: "range", min: 0, max: 1, step: 0.05, help: "A stiff linker holds the domains more firmly than a floppy one." },
        { key: "tails", label: "Disordered ends (residues each)", type: "range", min: 0, max: 120, step: 5 },
        { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1 }] },
    ],
    presets: [
      ["Two domains on a flexible linker (the defaults)", {}, "Each domain is confident and has low PAE inside, but the PAE between them is high: their arrangement in the model is one of many. Two domains are found; pTM is middling."],
      ["Domains that pack together", { packed: "yes" }, "With a firm interface the PAE between the domains is low, so they come out as one unit and pTM is high."],
      ["Long disordered ends", { tails: 110 }, "The domains are just as confident, but the long floppy ends drag the mean pLDDT and pTM down. A low average does not mean the folded parts are wrong: look along the sequence."],
      ["A poorly known domain", { orderB: 0.35 }, "Domain B has low pLDDT, as for a domain with few relatives in the databases: only domain A is found."],
      ["A disordered protein", { orderA: 0.1, orderB: 0.1, tails: 40 }, "Nothing is confident and no domain is found. For a truly disordered protein, this is the right answer, not a failure."],
    ],
    render,
  });
})();
