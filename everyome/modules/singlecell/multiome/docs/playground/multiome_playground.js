/* Playground for multiome: four made-up cell types placed by their RNA, by their open chromatin, and by both. Shows
   why two measurements of the same cells can separate types that either alone cannot. Deterministic point clouds. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;
  const TYPES = ["epidermis", "gastrodermis", "cnidocyte", "neuron"];

  // A fixed cloud of offsets (no randomness, so the picture only moves when a setting does).
  const OFF = Array.from({ length: 40 }, (_, i) => { const a = i * 2.39996, r = Math.sqrt((i + 0.5) / 40); return [r * Math.cos(a), r * Math.sin(a)]; });

  function centres(S) {
    // RNA: epidermis vs gastrodermis apart by S.rnaEG; cnidocytes and neurons apart by S.rnaCN. ATAC likewise.
    return {
      rna: [[-S.rnaEG / 2, 1], [S.rnaEG / 2, 1], [-S.rnaCN / 2, -1.5], [S.rnaCN / 2, -1.5]],
      atac: [[-S.atacEG / 2, 1.5], [S.atacEG / 2, 1.5], [-S.atacCN / 2, -1], [S.atacCN / 2, -1]],
    };
  }

  function separable(c, spread) {
    // Two types are told apart when their centres are further apart than their clouds are wide.
    const pairs = [[0, 1], [2, 3], [0, 2], [1, 3]];
    return pairs.map(([i, j]) => Math.hypot(c[i][0] - c[j][0], c[i][1] - c[j][1]) > 2.2 * spread);
  }

  function panel(title, cs, spread) {
    const C = H.COL(), P = H.PALETTE(), w = 240, h = 220, X = x => w / 2 + x * 36, Y = y => h / 2 - y * 36;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}"><rect x="1" y="1" width="${w - 2}" height="${h - 2}" fill="none" stroke="${C.rule}"/>`;
    cs.forEach((c, k) => OFF.forEach(([dx, dy]) => s += `<circle cx="${X(c[0] + dx * spread).toFixed(1)}" cy="${Y(c[1] + dy * spread).toFixed(1)}" r="2.4" fill="${P[k % P.length]}" opacity=".75"/>`));
    return `<div><div class="label" style="margin-bottom:4px">${esc(title)}</div>${s}</svg></div>`;
  }

  function render(S, el) {
    const c = centres(S), spread = S.noise / 10;
    const joint = c.rna.map((r, k) => [(r[0] + c.atac[k][0]) / Math.SQRT2, (r[1] + c.atac[k][1]) / Math.SQRT2]);
    // Intent: joining the two maps is like using both coordinates; a type pair separates if either measurement separates it.
    const sr = separable(c.rna, spread), sa = separable(c.atac, spread), sj = sr.map((v, i) => v || sa[i]);
    const names = ["epidermis vs gastrodermis", "cnidocyte vs neuron"];
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="grid g3">${panel("By RNA", c.rna, spread)}${panel("By open chromatin", c.atac, spread)}${panel("Both together", joint, spread * 0.85)}</div>
        ${H.legend(TYPES.map((t, k) => [t, H.PALETTE()[k % H.PALETTE().length]]))}</section>
      <section class="pg-card"><div class="label">Which types can be told apart</div><div class="metrics">
        ${names.map((n, i) => m(n, sj[i] ? "yes" : "no", `RNA: ${sr[i] ? "yes" : "no"} · chromatin: ${sa[i] ? "yes" : "no"}`, !sj[i])).join("")}</div>
        <p class="note">A pair separates in the joint view when either measurement separates it: two measurements of the same cells add up.</p></section>`;
  }

  window.MultiomePlayground = E.makePlayground({
    defaults: { rnaEG: 3, rnaCN: 0, atacEG: 0, atacCN: 3, noise: 6 },
    controls: [
      { group: "How different the RNA is", items: [
        { key: "rnaEG", label: "Epidermis vs gastrodermis", type: "range", min: 0, max: 4, step: 0.25 },
        { key: "rnaCN", label: "Cnidocyte vs neuron", type: "range", min: 0, max: 4, step: 0.25 }] },
      { group: "How different the open chromatin is", items: [
        { key: "atacEG", label: "Epidermis vs gastrodermis", type: "range", min: 0, max: 4, step: 0.25 },
        { key: "atacCN", label: "Cnidocyte vs neuron", type: "range", min: 0, max: 4, step: 0.25 }] },
      { group: "Measurement", items: [
        { key: "noise", label: "Noise (how wide each cloud is)", type: "range", min: 2, max: 14, step: 1, help: "Shallower sequencing makes clouds wider." }] },
    ],
    presets: [
      ["Each measurement sees half (the defaults)", {}, "RNA splits epidermis from gastrodermis, chromatin splits cnidocytes from neurons; only together are all four apart."],
      ["RNA alone would do", { rnaCN: 3, atacCN: 0 }, "If the RNA separates every pair, the chromatin adds little for finding types."],
      ["Too noisy", { noise: 14 }, "With wide clouds even real differences blur; deeper sequencing helps both measurements."],
    ],
    render,
  });
})();
