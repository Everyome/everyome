/* Playground for RNA abundance: why raw read counts and TPM disagree (gene length), and why TPM is a share, so one
   gene rising makes every other gene's TPM fall. Six made-up genes; reads are expected values, not simulated noise. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;
  const GENES = [["actin", 1800], ["rpl7", 700], ["opsin", 1300], ["myosin", 6000], ["sox2", 1000], ["mito-cox1", 1500]];

  function compute(S) {
    // Intent: S.mol_<i> is molecules of each transcript per cell; reads are proportional to molecules × length.
    const mol = GENES.map((g, i) => i === S.which ? S.amount : S["mol" + i]), len = GENES.map(([, l], i) => i === S.which ? S.len : l);
    const reads = mol.map((m, i) => m * len[i]), total = reads.reduce((a, b) => a + b, 0);
    const depth = S.depth * 1e6;
    const counts = reads.map(r => r / total * depth);
    const rate = counts.map((c, i) => c / len[i]), rsum = rate.reduce((a, b) => a + b, 0);
    return GENES.map(([name], i) => ({ name, len: len[i], mol: mol[i], count: counts[i], tpm: rate[i] / rsum * 1e6 }));
  }

  function render(S, el) {
    const C = H.COL(), P = H.PALETTE(), rows = compute(S), base = compute({ ...S, amount: S["mol" + S.which], len: GENES[S.which][1] });
    const w = 560, rowH = 30, h = rows.length * rowH + 40, L = 100, maxT = Math.max(...rows.map(r => r.tpm), ...base.map(r => r.tpm));
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="TPM of each gene">`;
    rows.forEach((r, i) => {
      const y = 10 + i * rowH, x = v => L + v / maxT * (w - L - 70);
      svg += `<text x="${L - 8}" y="${y + 15}" text-anchor="end" class="ax">${esc(r.name)}</text>
        <rect x="${L}" y="${y + 3}" width="${Math.max(1, x(r.tpm) - L)}" height="16" fill="${i === S.which ? C.ox : P[i % P.length]}"/>
        <line x1="${x(base[i].tpm)}" x2="${x(base[i].tpm)}" y1="${y}" y2="${y + 22}" stroke="${C.ink}" stroke-dasharray="3 2"/>
        <text x="${x(r.tpm) + 6}" y="${y + 15}" class="ax">${Math.round(r.tpm).toLocaleString()}</text>`;
    });
    svg += `<text x="${L}" y="${h - 6}" class="ax">TPM (dashed: before you changed ${esc(GENES[S.which][0])})</text></svg>`;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    const g = rows[S.which], others = rows.filter((_, i) => i !== S.which), othersBase = base.filter((_, i) => i !== S.which);
    const drop = 100 * (1 - others.reduce((a, r) => a + r.tpm, 0) / othersBase.reduce((a, r) => a + r.tpm, 0));
    el.innerHTML = `<section class="pg-card"><div class="label">TPM of each gene</div>${svg}
        <p class="note">The other genes did not change at all, yet their TPM moved: TPM is a share of the sample's transcripts.</p></section>
      <section class="pg-card"><div class="label">Counts against TPM</div><table><thead><tr><th>Gene</th><th class="num">Length</th><th class="num">Molecules</th><th class="num">Reads</th><th class="num">TPM</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr${i === S.which ? ' class="sel"' : ""}><td>${esc(r.name)}</td><td class="num">${r.len.toLocaleString()}</td><td class="num">${r.mol}</td><td class="num">${Math.round(r.count).toLocaleString()}</td><td class="num">${Math.round(r.tpm).toLocaleString()}</td></tr>`).join("")}</tbody></table>
        <div class="metrics">${m(`${esc(g.name)}'s TPM`, Math.round(g.tpm).toLocaleString(), `with ${g.mol} molecules per cell and a ${g.len.toLocaleString()} bp transcript`)}
          ${m("Every other gene's TPM", drop >= 0 ? `−${drop.toFixed(0)}%` : `+${(-drop).toFixed(0)}%`, "though none of them changed", Math.abs(drop) > 20)}</div>
        <p class="note">Reads grow with length: a long gene gets more reads for the same number of molecules. TPM divides by length first, so genes of different lengths can be compared.</p></section>`;
  }

  window.AbundancePlayground = E.makePlayground({
    defaults: { which: 5, amount: 10, mol0: 10, mol1: 10, mol2: 10, mol3: 10, mol4: 10, mol5: 10, len: 1500, depth: 20 },
    controls: [
      { group: "The gene you change", items: [
        { key: "which", label: "Gene", type: "select", options: GENES.map(([n], i) => [i, n]) },
        { key: "amount", label: "Its molecules per cell", type: "range", min: 1, max: 400, step: 1, help: "Mitochondrial transcripts can be very abundant in some tissues." },
        { key: "len", label: "Its transcript length (bp)", type: "range", min: 300, max: 8000, step: 100 }] },
      { group: "The other genes", items: [
        { key: "mol0", label: "actin molecules", type: "range", min: 1, max: 100, step: 1 },
        { key: "mol3", label: "myosin molecules (a long gene)", type: "range", min: 1, max: 100, step: 1 }] },
      { group: "Sequencing", items: [
        { key: "depth", label: "Reads per sample (millions)", type: "range", min: 1, max: 100, step: 1, help: "More reads raise every count; TPM stays the same." }] },
    ],
    presets: [
      ["Six genes, ten molecules each (the defaults)", {}, "Same molecules, but the long gene (myosin) gets the most reads; TPM evens them out."],
      ["Mitochondrial transcripts take over", { amount: 300 }, "One gene rising to 300 molecules pulls every other gene's TPM down by about four fifths."],
      ["Sequence deeper", { depth: 80 }, "Four times the reads: every count goes up four times, TPM doesn't move."],
      ["Shorten myosin's transcript", { which: 3, len: 900, amount: 10 }, "Fewer reads for myosin, same TPM for the same number of molecules."],
    ],
    render: (S, el) => { S.which = Number(S.which); if (S.len === 1500 && S.which !== 5) S.len = GENES[S.which][1]; render(S, el); },
  });
})();
