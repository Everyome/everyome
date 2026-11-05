/* Playground for interaction prediction: pDockQ (Bryant et al., 2022) from the interface's size and confidence, and how
   it reads alongside ipTM. The published formula on the numbers you set. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const pdockq = (plddt, n) => n < 1 ? 0.018 : 0.724 / (1 + Math.exp(-0.052 * (plddt * Math.log10(n) - 152.611))) + 0.018;

  function render(S, el) {
    const C = H.COL(), q = pdockq(S.plddt, S.contacts), iptm = S.iptm / 100;
    const good = q >= 0.5 || iptm >= 0.8, poor = q < 0.23 && iptm < 0.6;
    const reading = good ? "likely binds as predicted" : poor ? "unlikely to bind as predicted" : "uncertain";
    // pDockQ against contacts, at the chosen pLDDT and at two others.
    const w = 540, h = 240, L = 40, B = 30, X = n => L + Math.log10(n) / Math.log10(400) * (w - L - 10), Y = v => h - B - v / 0.75 * (h - B - 10);
    const line = (p, col, lab) => { const pts = []; for (let n = 1; n <= 400; n *= 1.15) pts.push(`${X(n).toFixed(1)},${Y(pdockq(p, n)).toFixed(1)}`);
      return `<polyline fill="none" stroke="${col}" stroke-width="2" points="${pts.join(" ")}"/><text x="${w - 12}" y="${Y(pdockq(p, 400)) - 4}" text-anchor="end" class="ax">${lab}</text>`; };
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="pDockQ against the number of contacts">
      <rect x="${L}" y="${Y(0.75)}" width="${w - L - 10}" height="${Y(0.5) - Y(0.75)}" fill="${C.ok}" opacity=".12"/>
      <rect x="${L}" y="${Y(0.23)}" width="${w - L - 10}" height="${Y(0) - Y(0.23)}" fill="${C.ox}" opacity=".08"/>
      ${line(60, C.rule, "pLDDT 60")}${line(80, C.muted, "pLDDT 80")}${line(95, C.plum, "pLDDT 95")}
      <circle cx="${X(Math.max(1, S.contacts))}" cy="${Y(q)}" r="6" fill="${C.ox}"/>
      <line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${C.muted}"/>`;
    [1, 10, 100, 400].forEach(n => svg += `<text x="${X(n)}" y="${h - B + 15}" text-anchor="middle" class="ax">${n}</text>`);
    svg += `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">contacts across the interface (log)</text></svg>`;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">pDockQ</div>${svg}<p class="note">Green band: likely correct (0.5 or more); red band: likely wrong (below 0.23).</p></section>
      <section class="pg-card"><div class="label">Reading</div><div class="metrics">
        ${m("pDockQ", q.toFixed(2), q >= 0.5 ? "high" : q < 0.23 ? "low" : "in between")}
        ${m("ipTM", iptm.toFixed(2), iptm >= 0.8 ? "high" : iptm < 0.6 ? "low" : "in between")}
        ${m("Together", reading, good ? "a hypothesis worth testing" : poor ? "the predictor doesn't believe this arrangement" : "look at the structure and the PAE", !good)}</div></section>`;
  }

  window.PdockqPlayground = E.makePlayground({
    defaults: { contacts: 60, plddt: 85, iptm: 75 },
    controls: [
      { group: "The predicted interface", items: [
        { key: "contacts", label: "Residue pairs in contact", type: "range", min: 0, max: 400, step: 5 },
        { key: "plddt", label: "Mean pLDDT at the interface", type: "range", min: 30, max: 98, step: 1 }] },
      { group: "The predictor's own score", items: [{ key: "iptm", label: "ipTM (× 100)", type: "range", min: 5, max: 95, step: 1 }] },
    ],
    presets: [
      ["A decent interface (the defaults)", {}, "Sixty contacts at pLDDT 85: pDockQ in between, ipTM in between: uncertain."],
      ["A large, confident interface", { contacts: 200, plddt: 92, iptm: 88 }, "Both scores high: likely correct."],
      ["Two chains just touching", { contacts: 8, plddt: 80, iptm: 40 }, "Few contacts: pDockQ stays low whatever the confidence."],
      ["Big but unsure", { contacts: 200, plddt: 55, iptm: 50 }, "Many contacts, low confidence: the scores disagree with a quick look at the size."],
    ],
    render,
  });
})();
