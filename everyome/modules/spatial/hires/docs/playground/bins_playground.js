/* Playground for high-resolution spatial: on a strip of cells of two types, how the bin size trades RNA per bin against
   bins that mix cells. Geometry only; RNA per bin is proportional to its area. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;

  function render(S, el) {
    const C = H.COL(), P = H.PALETTE(), L = 240;                          // a 240 µm strip
    // Cells: alternate runs of type A and B, each run S.run cells long, each cell S.cell µm wide.
    const cells = [];
    for (let x = 0, i = 0; x < L; x += S.cell, i++) cells.push({ x0: x, x1: Math.min(L, x + S.cell), t: Math.floor(i / S.run) % 2 });
    const bins = [];
    for (let x = 0; x < L; x += S.bin) {
      const x1 = Math.min(L, x + S.bin), cover = [0, 0];
      cells.forEach(c => { const o = Math.max(0, Math.min(x1, c.x1) - Math.max(x, c.x0)); cover[c.t] += o; });
      const n = new Set(cells.filter(c => Math.min(x1, c.x1) > Math.max(x, c.x0)).map(c => c.x0)).size;
      bins.push({ x0: x, x1, a: cover[0] / (x1 - x), cells: n });
    }
    const w = 560, X = v => 10 + v / L * (w - 20);
    let svg = `<svg class="chart" viewBox="0 0 ${w} 120" role="img" aria-label="Cells and bins along a strip">`;
    cells.forEach(c => svg += `<rect x="${X(c.x0)}" y="14" width="${X(c.x1) - X(c.x0) - 1}" height="34" fill="${P[c.t]}"/>`);
    bins.forEach(b => { const mixed = b.a > 0.05 && b.a < 0.95;
      svg += `<rect x="${X(b.x0)}" y="64" width="${X(b.x1) - X(b.x0) - 1}" height="34" fill="${b.a >= 0.95 ? P[0] : b.a <= 0.05 ? P[1] : C.rule}" stroke="${mixed ? C.ox : "none"}"/>`; });
    svg += `<text x="10" y="10" class="ax">cells</text><text x="10" y="112" class="ax">bins (outlined: mixed)</text></svg>`;
    const mixed = bins.filter(b => b.a > 0.05 && b.a < 0.95).length, multi = bins.filter(b => b.cells > 1).length;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">A strip of tissue</div>${svg}${H.legend([["type A", P[0]], ["type B", P[1]], ["bin mixing both", C.rule]])}</section>
      <section class="pg-card"><div class="label">At ${S.bin} µm</div><div class="metrics">
        ${m("Bins mixing both types", `${Math.round(100 * mixed / bins.length)}%`, "their expression is a blend of the two", mixed / bins.length > 0.3)}
        ${m("Bins touching more than one cell", `${Math.round(100 * multi / bins.length)}%`, "even when the cells are the same type")}
        ${m("RNA per bin", `${(S.bin / 8) ** 2 < 1 ? (S.bin / 8) ** 2 : Math.round((S.bin / 8) ** 2)}×`, "compared with an 8 µm bin (it grows with the area)", S.bin <= 2)}</div>
        <p class="note">Smaller bins mix less but hold little RNA each; larger bins hold more but blur boundaries.</p></section>`;
  }

  window.BinsPlayground = E.makePlayground({
    defaults: { bin: 8, cell: 10, run: 3 },
    controls: [
      { group: "Bins", items: [{ key: "bin", label: "Bin size (µm)", type: "range", min: 2, max: 32, step: 2 }] },
      { group: "The tissue", items: [
        { key: "cell", label: "Cell size (µm)", type: "range", min: 4, max: 30, step: 1 },
        { key: "run", label: "Cells per patch of one type", type: "range", min: 1, max: 10, step: 1, help: "1: the types alternate cell by cell." }] },
    ],
    presets: [
      ["8 µm bins, 10 µm cells (the defaults)", {}, "Most bins hold one cell; those on a boundary mix two."],
      ["16 µm bins", { bin: 16 }, "Four times the RNA per bin, but many more bins blend the two types."],
      ["2 µm bins", { bin: 2 }, "Almost no mixing, but each bin has a sixteenth of the RNA."],
      ["Small interleaved cells", { cell: 6, run: 1, bin: 16 }, "When types alternate cell by cell, large bins mix almost everywhere."],
    ],
    render,
  });
})();
