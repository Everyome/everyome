/* Playground for cell types in spots: a spot's expression is a mixture of its cells' expression. Mix three cell
   types, add counting noise, and work the shares back out with a non-negative least-squares fit. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;
  const TYPES = ["Keratinocyte", "Fibroblast A", "Fibroblast B"];
  const GENES = 12;

  // Each type's profile over twelve genes; Fibroblast B moves towards Fibroblast A as `similar` rises (0..1).
  function profiles(similar) {
    const k = Array.from({ length: GENES }, (_, g) => g < 4 ? 30 : 2);
    const a = Array.from({ length: GENES }, (_, g) => g >= 4 && g < 8 ? 30 : 2);
    const b0 = Array.from({ length: GENES }, (_, g) => g >= 8 ? 30 : 2);
    const b = b0.map((v, g) => v * (1 - similar) + a[g] * similar);
    return [k, a, b].map(p => { const s = p.reduce((x, y) => x + y, 0); return p.map(v => v / s); });
  }

  // A small seeded random generator, so the same settings give the same noise.
  function rng(seed) { let t = seed >>> 0; return () => { t += 0x6D2B79F5; let r = Math.imul(t ^ t >>> 15, 1 | t); r ^= r + Math.imul(r ^ r >>> 7, 61 | r); return ((r ^ r >>> 14) >>> 0) / 4294967296; }; }
  function poisson(lam, u) { if (lam > 30) { const z = Math.sqrt(-2 * Math.log(u() || 1e-9)) * Math.cos(2 * Math.PI * u()); return Math.max(0, Math.round(lam + Math.sqrt(lam) * z)); }
    let L = Math.exp(-lam), k = 0, p = 1; do { k++; p *= u(); } while (p > L); return k - 1; }

  // Non-negative least squares by projected gradient: shares w >= 0 with P'w ≈ observed profile, then scaled to sum 1.
  function nnls(P, y) {
    let w = P.map(() => 1 / P.length);
    for (let it = 0; it < 3000; it++) {
      const fit = y.map((_, g) => P.reduce((s, p, k) => s + p[g] * w[k], 0));
      const grad = P.map(p => p.reduce((s, v, g) => s + v * (fit[g] - y[g]), 0));
      w = w.map((v, k) => Math.max(0, v - 2 * grad[k]));
    }
    const s = w.reduce((a, b) => a + b, 0) || 1;
    return w.map(v => v / s);
  }

  function render(S, el) {
    const C = H.COL(), P3 = H.PALETTE(), P = profiles(S.similar);
    const raw = [S.k, S.a, S.b], tot = raw.reduce((a, b) => a + b, 0) || 1, truth = raw.map(v => v / tot);
    const mix = Array.from({ length: GENES }, (_, g) => P.reduce((s, p, k) => s + p[g] * truth[k], 0));
    const u = rng(S.seed), counts = mix.map(m => poisson(m * S.umis, u)), n = counts.reduce((a, b) => a + b, 0) || 1;
    const est = nnls(P, counts.map(c => c / n));
    const w = 560, h = 180, L = 30, bw = (w - L - 10) / GENES, max = Math.max(...counts, 1);
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="The spot's counts for each gene">`;
    counts.forEach((c, g) => { const y = 10 + (1 - c / max) * (h - 40);
      const owner = g < 4 ? 0 : g < 8 ? 1 : 2;
      svg += `<rect x="${L + g * bw + 2}" y="${y}" width="${bw - 4}" height="${h - 30 - y}" fill="${P3[owner % P3.length]}"><title>gene ${g + 1}: ${c} molecules</title></rect>`; });
    svg += `<text x="${L}" y="${h - 10}" class="ax">genes 1–4 mark keratinocytes, 5–8 fibroblast A, 9–12 fibroblast B</text></svg>`;
    const rows = TYPES.map((t, k) => `<tr><td><span class="chip" style="cursor:inherit"><i style="background:${P3[k % P3.length]}"></i>${esc(t)}</span></td><td class="num">${(truth[k] * 100).toFixed(0)}%</td><td class="num">${(est[k] * 100).toFixed(0)}%</td></tr>`).join("");
    const err = Math.max(...truth.map((t, k) => Math.abs(t - est[k])));
    const m = (k, v, note, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${note}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">What the spot captured</div>${svg}
        <p class="note">${n} molecules in all. Every gene's count is a mixture of the three types' expression, plus counting noise.</p></section>
      <section class="pg-card"><div class="label">Shares worked back out</div><table><thead><tr><th>Cell type</th><th class="num">True share</th><th class="num">Estimated</th></tr></thead><tbody>${rows}</tbody></table>
        <div class="metrics">${m("Largest error", (err * 100).toFixed(0) + " points", "between a true and an estimated share", err > 0.1)}
          ${m("Fibroblast A + B", `${((truth[1] + truth[2]) * 100).toFixed(0)}% → ${((est[1] + est[2]) * 100).toFixed(0)}%`, "their sum is steadier than either")}</div>
        <p class="note">With few molecules, or two cell types that look alike, the split between similar types wanders; the total for the pair stays close.</p></section>`;
  }

  window.MixturePlayground = E.makePlayground({
    defaults: { k: 5, a: 3, b: 2, umis: 2000, similar: 0, seed: 1 },
    controls: [
      { group: "Cells in the spot", items: [
        { key: "k", label: "Keratinocytes", type: "range", min: 0, max: 10, step: 1 },
        { key: "a", label: "Fibroblasts A", type: "range", min: 0, max: 10, step: 1 },
        { key: "b", label: "Fibroblasts B", type: "range", min: 0, max: 10, step: 1 }] },
      { group: "Measurement", items: [
        { key: "umis", label: "Molecules captured in the spot", type: "range", min: 50, max: 10000, step: 50, help: "Visium spots often capture a few thousand." },
        { key: "similar", label: "How alike the two fibroblasts are", type: "range", min: 0, max: 0.95, step: 0.05 },
        { key: "seed", label: "Another draw of the noise", type: "range", min: 1, max: 20, step: 1 }] },
    ],
    presets: [
      ["A clear mixture (the defaults)", {}, "Distinct cell types and plenty of molecules: the shares come back close."],
      ["A shallow spot", { umis: 150 }, "Few molecules: the estimate wanders from draw to draw (try another draw)."],
      ["Two fibroblasts that look alike", { similar: 0.85 }, "The split between them is unreliable; their total holds."],
      ["Only keratinocytes", { a: 0, b: 0 }, "Absent types still get a small share now and then, from noise alone."],
    ],
    render: (S, el) => render(Object.fromEntries(Object.entries(S).map(([k, v]) => [k, Number(v)])), el),
  });
})();
