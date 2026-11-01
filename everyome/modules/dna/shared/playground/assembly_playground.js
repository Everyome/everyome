/* Playground for genome assembly: a simulated genome with repeats of known sizes. Choose the reads and see where the
   assembly breaks, how N50 changes and how accurate the consensus is. Runs in the browser; built with Everyome's
   shared playground builder. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc, fmt } = H;
  const bp = n => n >= 1e6 ? (n / 1e6).toFixed(2) + " Mb" : n >= 1e3 ? (n / 1e3).toFixed(1) + " kb" : fmt(n) + " bp";

  function rng(seed) {
    let a = seed >>> 0;
    const r = () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    r.poisson = lam => { const L = Math.exp(-lam); let k = 0, p = 1; do { k++; p *= r(); } while (p > L); return k - 1; };
    return r;
  }
  const lnC = (n, k) => { let s = 0; for (let i = 1; i <= k; i++) s += Math.log((n - k + i) / i); return s; };

  // Intent: three chromosomes with repeat families of 0.3, 1.5, 6, 18 and 40 kb; reads cross a repeat only if longer than it.
  function genome(seed) {
    const r = rng(seed), chroms = [3e6, 2.2e6, 1.4e6], fam = [[300, 120], [1500, 40], [6000, 12], [18000, 5], [40000, 2]], reps = [];
    fam.forEach(([len, n]) => { for (let i = 0; i < n; i++) { const c = Math.floor(r() * 3); reps.push({ c, pos: Math.floor(r() * chroms[c]), len }); } });
    return { chroms, reps };
  }

  function assemble(S) {
    const g = genome(S.seed), r = rng(S.seed * 7 + 1), cuts = g.chroms.map(() => []);
    g.reps.forEach(x => { if (x.len >= S.len * 0.9) cuts[x.c].push(x.pos); });                 // a repeat the reads cannot span
    // Coverage gaps: stretches no read starts in long enough to leave a hole (Lander–Waterman).
    g.chroms.forEach((n, c) => { const holes = r.poisson(n / S.len * S.cov * Math.exp(-S.cov)); for (let i = 0; i < holes; i++) cuts[c].push(Math.floor(r() * n)); });
    const contigs = [];
    g.chroms.forEach((n, c) => { const e = [0, ...cuts[c].sort((a, b) => a - b), n]; for (let i = 1; i < e.length; i++) if (e[i] - e[i - 1] > 200) contigs.push({ c, a: e[i - 1], b: e[i], len: e[i] - e[i - 1] }); });
    contigs.sort((x, y) => y.len - x.len);
    const total = contigs.reduce((s, x) => s + x.len, 0); let acc = 0, n50 = 0, l50 = 0;
    for (const x of contigs) { acc += x.len; l50++; if (acc >= total / 2) { n50 = x.len; break; } }
    // Consensus error: a base is wrong when most reads covering it are wrong at that base (majority vote).
    const k = Math.max(1, Math.round(S.cov)), e = S.err / 100; let wrong = 0;
    for (let i = Math.ceil(k / 2); i <= k; i++) wrong += Math.exp(lnC(k, i) + i * Math.log(e) + (k - i) * Math.log(1 - e));
    const qv = Math.min(60, -10 * Math.log10(Math.max(wrong, 1e-6)));
    return { g, contigs, total, n50, l50, qv, breaksRepeat: g.reps.filter(x => x.len >= S.len * 0.9).length };
  }

  function render(S, el) {
    const C = H.COL(), a = assemble(S), w = 640, rowH = 34, L = 50;
    const scale = (w - L - 10) / Math.max(...a.g.chroms);
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${a.g.chroms.length * rowH + 30}" role="img" aria-label="Contigs along each chromosome">`;
    a.g.chroms.forEach((n, c) => {
      const y = c * rowH + 8;
      svg += `<text x="${L - 6}" y="${y + 14}" text-anchor="end" class="ax">chr${c + 1}</text><rect x="${L}" y="${y + 18}" width="${n * scale}" height="3" fill="${C.rule}"/>`;
      a.contigs.filter(x => x.c === c).forEach((x, i) => svg += `<rect x="${L + x.a * scale + 1}" y="${y}" width="${Math.max(1, x.len * scale - 2)}" height="14" fill="${i % 2 ? C.gold : C.golddk}"><title>${bp(x.len)}</title></rect>`);
      a.g.reps.filter(x => x.c === c && x.len >= 6000).forEach(x => svg += `<line x1="${L + x.pos * scale}" x2="${L + x.pos * scale}" y1="${y + 16}" y2="${y + 24}" stroke="${x.len >= S.len * 0.9 ? C.ox : C.muted}" stroke-width="2"><title>repeat ${bp(x.len)}</title></line>`);
    });
    svg += `<text x="${L}" y="${a.g.chroms.length * rowH + 24}" class="ax">Contigs (gold) above each chromosome; ticks mark repeats of 6 kb or more, red where the reads are too short to cross them.</text></svg>`;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">The assembly</div><div class="metrics">
        ${m("Contigs", fmt(a.contigs.length), "3 chromosomes in truth", a.contigs.length > 30)}
        ${m("N50", bp(a.n50), `L50 ${fmt(a.l50)} contigs`)}
        ${m("Repeats that break it", fmt(a.breaksRepeat), `of ${fmt(a.g.reps.length)} repeat copies`)}
        ${m("Accuracy (QV)", a.qv.toFixed(0), a.qv >= 40 ? "one error in 10,000 bases or better" : "polishing would help", a.qv < 30)}</div></section>
      <section class="pg-card"><div class="label">Where the assembly breaks</div>${svg}</section>`;
  }

  window.AssemblyPlayground = E.makePlayground({
    defaults: { seed: 2, len: 15000, err: 0.5, cov: 30 },
    controls: [
      { group: "Reads", items: [
        { key: "len", label: "Read length (bp)", type: "range", min: 150, max: 60000, step: 50, help: "Illumina about 150; PacBio HiFi about 15,000; Nanopore 10,000 to over 50,000." },
        { key: "err", label: "Read error rate (%)", type: "range", min: 0.1, max: 12, step: 0.1, help: "HiFi under 1%; Nanopore 1–5% (newer chemistry) or more; Illumina about 0.1%." },
        { key: "cov", label: "Coverage (×)", type: "range", min: 2, max: 80, step: 1, help: "How many times each base is read, on average." },
        { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1 }] },
    ],
    presets: [
      ["PacBio HiFi, 30×", {}, "Long, accurate reads: only the longest repeats break the assembly, and the consensus is very accurate."],
      ["Nanopore ultra-long, 30×", { len: 50000, err: 4 }, "Reads cross every repeat, so chromosomes come out almost whole, but each read has more errors."],
      ["Nanopore, low coverage", { len: 50000, err: 4, cov: 6 }, "Too few reads: gaps in coverage break the assembly and the consensus is less accurate. Polishing and more data help."],
      ["Illumina only", { len: 150, err: 0.1, cov: 50 }, "Short reads cannot cross repeats: hundreds of short contigs, even though every base is accurate."],
      ["Hybrid thinking", { len: 50000, err: 4, cov: 40 }, "Long reads give the structure; accurate short or HiFi reads then polish the errors away. That is why hybrid and polished assemblies score best."],
    ],
    render,
  });
})();
