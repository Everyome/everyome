/* Playground for Ribo-seq: where the 3-nucleotide rhythm comes from (ribosomes step one codon at a time, and the
   P-site offset turns a read's 5' end back into the codon being read), and why translational efficiency needs the
   matched mRNA. Exact expected values, no simulated noise. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;
  const TRUE = { 29: 12, 32: 13 };          // the real distance from a footprint's 5' end to its P-site, by length

  // Share of footprints whose 5' end is shifted by d nt from the ideal cut, for trimming spread sd (a discrete normal).
  function jitter(sd) {
    const out = {};
    let tot = 0;
    for (let d = -6; d <= 6; d++) { const w = sd < 0.05 ? (d === 0 ? 1 : 0) : Math.exp(-d * d / (2 * sd * sd)); out[d] = w; tot += w; }
    for (const d in out) out[d] /= tot;
    return out;
  }

  // Share of P-sites in frames 0, 1, 2 when footprints of this length are read with the chosen offset.
  function frames(len, offset, sd) {
    const f = [0, 0, 0], J = jitter(sd);
    for (const d in J) { const shift = offset - TRUE[len] - Number(d); f[((shift % 3) + 3) % 3] += J[d]; }
    return f;
  }

  function bars(rows, { w = 520, max = 1, fmt = v => (100 * v).toFixed(0) + "%", colors }) {
    const L = 150, rh = 26;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${rows.length * rh + 8}" role="img" aria-label="Bar chart">`;
    rows.forEach(([k, v], i) => {
      const y = 4 + i * rh, bw = Math.max(0, (w - L - 70) * v / max);
      s += `<text x="${L - 8}" y="${y + 15}" text-anchor="end" class="ax">${esc(k)}</text><rect x="${L}" y="${y + 3}" width="${bw}" height="16" fill="${colors[i]}"/>
        <text x="${L + bw + 6}" y="${y + 15}" class="ax">${fmt(v)}</text>`;
    });
    return s + "</svg>";
  }

  function render(S, el) {
    const C = H.COL(), fc = [C.ox, C.golddk, C.rule];
    const f29 = frames(29, S.off29, S.sd), f32 = frames(32, S.off32, S.sd), share = S.share32 / 100;
    const all = f29.map((v, i) => (1 - share) * v + share * f32[i]);
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    // TE: a gene with 100 mRNA molecules and 100 footprints in the control.
    const mrnaT = 100 * S.mrna, fpT = 100 * S.mrna * S.te;
    const top = Math.max(100, mrnaT, fpT);
    el.innerHTML = `<section class="pg-card"><div class="label">P-sites in each reading frame</div>
        ${bars([["29 nt, frame 0", f29[0]], ["29 nt, frame 1", f29[1]], ["29 nt, frame 2", f29[2]], ["32 nt, frame 0", f32[0]], ["32 nt, frame 1", f32[1]], ["32 nt, frame 2", f32[2]]],
          { colors: [fc[0], fc[1], fc[2], fc[0], fc[1], fc[2]] })}
        <div class="metrics">${m("All footprints in frame 0", (100 * all[0]).toFixed(0) + "%", "33% would mean no rhythm at all", all[0] < 0.5)}
          ${m("Offsets used", `${S.off29} and ${S.off32} nt`, `the true ones are ${TRUE[29]} and ${TRUE[32]}`, S.off29 !== TRUE[29] || S.off32 !== TRUE[32])}</div>
        <p class="note">Ribosomes read one codon at a time, so their P-sites sit three nucleotides apart. A wrong offset for one length moves all its P-sites into another frame; uneven trimming smears them across frames.</p></section>
      <section class="pg-card"><div class="label">One gene, control against treated</div>
        ${bars([["mRNA, control", 100], ["mRNA, treated", mrnaT], ["footprints, control", 100], ["footprints, treated", fpT]],
          { max: top, fmt: v => Math.round(v).toString(), colors: [C.golddk, C.golddk, C.ox, C.ox] })}
        <div class="metrics">${m("Footprints alone say", "×" + (fpT / 100).toFixed(2), "more ribosomes on this gene")}
          ${m("Translational efficiency", "×" + S.te.toFixed(2), "footprints per mRNA", Math.abs(Math.log2(S.te)) < 0.01 && Math.abs(Math.log2(S.mrna)) > 0.5)}</div>
        <p class="note">${Math.abs(Math.log2(S.te)) < 0.01 && S.mrna !== 1 ? "The footprints changed only because the mRNA did: translation per mRNA is the same. Without the RNA-seq this would look like a change in translation." :
          "Divide footprints by mRNA to see translation itself. That is why each Ribo-seq library needs its RNA-seq partner."}</p></section>`;
  }

  window.RiboseqPlayground = E.makePlayground({
    defaults: { sd: 0.3, off29: 12, off32: 13, share32: 30, mrna: 1, te: 1 },
    controls: [
      { group: "Footprints", items: [
        { key: "sd", label: "Trimming spread (nt)", type: "range", min: 0, max: 3, step: 0.1, help: "How unevenly the nuclease trims the ends of footprints." },
        { key: "share32", label: "Share of 32 nt footprints (%)", type: "range", min: 0, max: 100, step: 5 }] },
      { group: "P-site offsets used", items: [
        { key: "off29", label: "Offset for 29 nt footprints", type: "range", min: 9, max: 16, step: 1 },
        { key: "off32", label: "Offset for 32 nt footprints", type: "range", min: 9, max: 16, step: 1, help: "Longer footprints usually need a longer offset." }] },
      { group: "One gene in a treated sample", items: [
        { key: "mrna", label: "mRNA change (×)", type: "range", min: 0.25, max: 4, step: 0.25 },
        { key: "te", label: "Translational efficiency change (×)", type: "range", min: 0.25, max: 4, step: 0.25 }] },
    ],
    presets: [
      ["Sharp footprints, correct offsets (the defaults)", {}, "Most P-sites land in frame 0: a strong rhythm."],
      ["One offset for every length", { off32: 12 }, "The 32 nt footprints move into another frame, and the overall rhythm weakens."],
      ["Uneven digestion", { sd: 1.6 }, "Even with the right offsets, P-sites spread across all three frames."],
      ["More mRNA, same translation", { mrna: 3, te: 1 }, "Three times the footprints, but TE is unchanged: the gene is transcribed more, not translated better."],
      ["Translation switched on", { mrna: 1, te: 3 }, "Same mRNA, three times the footprints: a change in translation."],
    ],
    render: (S, el) => { for (const k of ["sd", "off29", "off32", "share32", "mrna", "te"]) S[k] = Number(S[k]); render(S, el); },
  });
})();
