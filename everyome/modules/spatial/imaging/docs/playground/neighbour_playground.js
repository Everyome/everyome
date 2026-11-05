/* Playground for neighbourhood enrichment: two cell types on a grid, more or less patchy; how often they are
   neighbours against labels shuffled at random. Deterministic (a seeded generator), so a setting change is the only change. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const N = 30;

  function rand(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

  // Smooth a random field `passes` times, then call the top `share` of cells type B: more passes, bigger patches.
  function tissue(S) {
    const r = rand(7 + S.seed);
    let f = Array.from({ length: N * N }, () => r());
    for (let p = 0; p < S.patch; p++) {
      f = f.map((_, i) => { const x = i % N, y = Math.floor(i / N); let s = 0, n = 0;
        for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) { const a = x + dx, b = y + dy; if (a >= 0 && a < N && b >= 0 && b < N) { s += f[b * N + a]; n++; } }
        return s / n; });
    }
    const cut = [...f].sort((a, b) => b - a)[Math.floor(N * N * S.share / 100)];
    return f.map(v => (v > cut ? 1 : 0));
  }
  function contacts(t) {
    let ab = 0;
    for (let i = 0; i < t.length; i++) { const x = i % N; if (x + 1 < N && t[i] !== t[i + 1]) ab++; if (i + N < t.length && t[i] !== t[i + N]) ab++; }
    return ab;
  }

  function render(S, el) {
    const t = tissue(S), real = contacts(t), r = rand(99), perm = [];
    for (let p = 0; p < 200; p++) { const s = [...t]; for (let i = s.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [s[i], s[j]] = [s[j], s[i]]; } perm.push(contacts(s)); }
    const mean = perm.reduce((a, b) => a + b, 0) / perm.length, sd = Math.sqrt(perm.reduce((a, b) => a + (b - mean) ** 2, 0) / perm.length) || 1;
    const z = (real - mean) / sd, P = H.PALETTE(), C = H.COL(), cell = 12;
    let svg = `<svg class="chart" viewBox="0 0 ${N * cell} ${N * cell}" style="max-width:360px" role="img" aria-label="Two cell types on a grid">`;
    t.forEach((v, i) => svg += `<rect x="${(i % N) * cell}" y="${Math.floor(i / N) * cell}" width="${cell - 1}" height="${cell - 1}" fill="${v ? P[1] : P[0]}"/>`);
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">The tissue</div>${svg}</svg>${H.legend([["type A", P[0]], ["type B", P[1]]])}</section>
      <section class="pg-card"><div class="label">A next to B</div><div class="metrics">
        ${m("Real contacts", real, "pairs of neighbouring cells of different types")}
        ${m("With shuffled labels", `${Math.round(mean)} ± ${Math.round(sd)}`, "the same cells, types placed at random (200 times)")}
        ${m("z-score", z.toFixed(1), z < -2 ? "fewer contacts than chance: the types keep apart" : z > 2 ? "more contacts than chance: the types intermingle" : "about what chance gives", Math.abs(z) > 2)}</div>
        <p class="note">The module does this for every pair of types (and each type with itself) on each cell's nearest neighbours.</p></section>`;
  }

  window.NeighbourPlayground = E.makePlayground({
    defaults: { patch: 4, share: 35, seed: 1 },
    controls: [
      { group: "The tissue", items: [
        { key: "patch", label: "Patchiness", type: "range", min: 0, max: 12, step: 1, help: "0: the types are mixed at random; higher: they form larger patches." },
        { key: "share", label: "Share of type B (%)", type: "range", min: 5, max: 50, step: 5 },
        { key: "seed", label: "Another random tissue", type: "range", min: 1, max: 9, step: 1 }] },
    ],
    presets: [
      ["Patches (the defaults)", {}, "Each type forms patches, so A and B touch far less often than chance: a strongly negative z-score."],
      ["Mixed at random", { patch: 0 }, "No arrangement: contacts match chance and the z-score sits near 0."],
      ["A rare type in large patches", { patch: 10, share: 10 }, "A few big patches: even a rare type gives a clear signal."],
    ],
    render,
  });
})();
