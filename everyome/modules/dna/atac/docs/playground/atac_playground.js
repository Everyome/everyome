/* Playground for ATAC-seq: how a peak caller tells open sites from background, and why FRiP (the fraction of reads in
   peaks) falls when a library is noisy. A 20 kb stretch with known open sites; reads are simulated (seeded), and each
   200 bp window is tested against the average background with a Poisson test, as MACS2 does in spirit. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;
  const LEN = 20000, WIN = 200, NW = LEN / WIN;
  // Open sites: centre (bp), width (bp), relative strength. Two are weak, so they test depth and threshold.
  const SITES = [[1800, 400, 1], [5200, 300, 0.6], [8000, 600, 1.4], [11500, 300, 0.15], [14600, 400, 0.8], [17800, 300, 0.25]];

  // Seeded random numbers (mulberry32), so a setting always gives the same reads.
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function poisson(lam, r) {
    if (lam > 50) { const u = r(), v = r(); return Math.max(0, Math.round(lam + Math.sqrt(lam) * Math.sqrt(-2 * Math.log(u || 1e-12)) * Math.cos(2 * Math.PI * v))); }
    let k = 0, p = 1; const L = Math.exp(-lam); do { k++; p *= r(); } while (p > L); return k - 1;
  }
  const LOGF = [0]; for (let i = 1; i < 5000; i++) LOGF[i] = LOGF[i - 1] + Math.log(i);
  // −log10 P(X ≥ k) for X ~ Poisson(lam).
  function score(k, lam) {
    if (k <= 0) return 0;
    let s = 0; for (let i = k; i < Math.min(k + 400, LOGF.length); i++) s += Math.exp(i * Math.log(lam) - lam - LOGF[i]);
    return Math.min(300, -Math.log10(Math.max(s, 1e-300)));
  }

  function simulate(S) {
    const r = rng(1000 + S.seed), total = S.reads * 1000, bg = S.background / 100;
    const inSite = w => SITES.findIndex(([c, wd]) => Math.abs((w + 0.5) * WIN - c) < wd / 2 + WIN / 2);
    const strength = SITES.reduce((a, [, wd, s]) => a + s * wd, 0);
    const counts = Array.from({ length: NW }, (_, w) => {
      const i = inSite(w), sig = i >= 0 ? (1 - bg) * total * SITES[i][2] * Math.min(WIN, SITES[i][1]) / strength : 0;
      return poisson(bg * total / NW + sig, r);
    });
    const lam = Math.max(1e-6, counts.reduce((a, b) => a + b, 0) / NW);           // genome-wide average, as MACS2's λBG
    const called = counts.map(k => score(k, lam) >= S.threshold);
    // Merge neighbouring called windows into peaks; a peak is true if it overlaps an open site.
    const peaks = []; called.forEach((c, w) => { if (!c) return; const last = peaks[peaks.length - 1]; if (last && last.b === w - 1) last.b = w; else peaks.push({ a: w, b: w }); });
    peaks.forEach(p => { p.site = SITES.findIndex(([c, wd]) => (p.a * WIN) < c + wd / 2 && ((p.b + 1) * WIN) > c - wd / 2); });
    const found = new Set(peaks.filter(p => p.site >= 0).map(p => p.site));
    const inPeaks = peaks.reduce((a, p) => { for (let w = p.a; w <= p.b; w++) a += counts[w]; return a; }, 0);
    let kmin = 0; while (score(kmin, lam) < S.threshold && kmin < 5000) kmin++;
    return { counts, lam, peaks, found, falsePeaks: peaks.filter(p => p.site < 0).length, frip: inPeaks / Math.max(1, counts.reduce((a, b) => a + b, 0)), kmin };
  }

  function render(S, el) {
    const C = H.COL(), r = simulate(S), w = 720, h = 250, L = 46, B = 46, T = 10, R = 10;
    const maxC = Math.max(r.kmin * 1.2, ...r.counts), X = i => L + i / NW * (w - L - R), Y = v => T + (1 - v / maxC) * (h - B - T);
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Reads in each 200 bp window, with the open sites and the called peaks">`;
    r.counts.forEach((k, i) => svg += `<rect x="${X(i)}" y="${Y(k)}" width="${(w - L - R) / NW - 0.5}" height="${Y(0) - Y(k)}" fill="${C.rule}"><title>${i * WIN}–${(i + 1) * WIN} bp: ${k} reads</title></rect>`);
    svg += `<line x1="${L}" x2="${w - R}" y1="${Y(r.kmin)}" y2="${Y(r.kmin)}" stroke="${C.ox}" stroke-dasharray="4 3"/><text x="${w - R}" y="${Y(r.kmin) - 4}" text-anchor="end" class="ax">called above ${r.kmin} reads</text>`;
    SITES.forEach(([c, wd], i) => svg += `<rect x="${X((c - wd / 2) / WIN)}" y="${h - B + 6}" width="${Math.max(3, wd / LEN * (w - L - R))}" height="8" fill="${r.found.has(i) ? C.golddk : C.muted}"><title>open site ${i + 1}${r.found.has(i) ? " (found)" : " (missed)"}</title></rect>`);
    r.peaks.forEach(p => svg += `<rect x="${X(p.a)}" y="${h - B + 18}" width="${Math.max(3, X(p.b + 1) - X(p.a))}" height="8" fill="${p.site >= 0 ? C.ox : C.plum || C.ink}"><title>${p.site >= 0 ? "peak at an open site" : "false peak (background)"}</title></rect>`);
    svg += `<text x="${L - 6}" y="${h - B + 14}" text-anchor="end" class="ax">sites</text><text x="${L - 6}" y="${h - B + 26}" text-anchor="end" class="ax">peaks</text>
      <text x="${L}" y="${h - 4}" class="ax">0</text><text x="${w - R}" y="${h - 4}" text-anchor="end" class="ax">20 kb</text>
      <text x="12" y="${(h - B) / 2}" transform="rotate(-90 12 ${(h - B) / 2})" text-anchor="middle" class="ax">reads per 200 bp</text></svg>`;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">Reads along the region</div>${svg}
        <p class="note">Grey bars are reads; the gold marks under the axis are the true open sites (pale when missed), the red marks the called peaks (purple when false).</p></section>
      <section class="pg-card"><div class="label">How the caller did</div><div class="metrics">
        ${m("Open sites found", `${r.found.size} of ${SITES.length}`, "weak sites need depth or a lower threshold", r.found.size < SITES.length)}
        ${m("False peaks", r.falsePeaks, "peaks in background only", r.falsePeaks > 0)}
        ${m("FRiP", (r.frip * 100).toFixed(1) + "%", "reads in called peaks; ENCODE asks for 20% or more", r.frip < 0.2)}
        ${m("Background per window", r.lam.toFixed(1), "average reads per 200 bp, the caller's baseline")}</div>
        <p class="note">A noisier library (more background) raises the baseline, so weak sites sink into it and FRiP falls even where peaks are found. A lower threshold finds weak sites but lets background through.</p></section>`;
  }

  window.AtacPlayground = E.makePlayground({
    defaults: { reads: 20, background: 50, threshold: 5, seed: 1 },
    controls: [
      { group: "The library", items: [
        { key: "reads", label: "Reads in this region (thousands)", type: "range", min: 1, max: 100, step: 1, help: "Deeper sequencing gives every window more reads." },
        { key: "background", label: "Reads that fall at random (%)", type: "range", min: 10, max: 95, step: 1, help: "Dead cells, too much Tn5 or too few nuclei raise the background." }] },
      { group: "The peak caller", items: [
        { key: "threshold", label: "Threshold (−log10 P)", type: "range", min: 1, max: 20, step: 0.5, help: "Here the threshold is on each window's own P value. MACS2 instead uses a q-value of 0.01 by default, which corrects for the many places it tests." }] },
      { group: "Chance", items: [
        { key: "seed", label: "Another library with the same settings", type: "range", min: 1, max: 20, step: 1 }] },
    ],
    presets: [
      ["A good library (the defaults)", {}, "Strong sites are found, the weakest is missed, FRiP is well above 20%."],
      ["A noisy library", { background: 85 }, "Most reads fall at random: FRiP drops and the weak sites vanish into the background."],
      ["Sequence deeper", { reads: 80 }, "Four times the reads: the weak sites rise above the background and are found."],
      ["A loose threshold", { threshold: 1.5 }, "Weak sites are found, but so are runs of background: false peaks appear."],
    ],
    render,
  });
})();
