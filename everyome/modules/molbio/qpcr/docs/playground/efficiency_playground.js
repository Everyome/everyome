/* Playground for qPCR: two samples that differ by a known fold change, their amplification curves and Cq values,
   and the fold change you would report if you assumed a different efficiency from the true one. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const FMAX = 1, CYCLES = 45;

  // Logistic amplification: exponential at efficiency e (a fraction) from n0, levelling off at FMAX.
  const signal = (n0, e, c) => FMAX / (1 + (FMAX / n0 - 1) * Math.pow(1 + e, -c));
  // The cycle where the curve crosses the threshold t (solved from the same model).
  const cq = (n0, e, t) => Math.log((FMAX / n0 - 1) / (FMAX / t - 1)) / Math.log(1 + e);

  function render(S, el) {
    const C = H.COL(), P = H.PALETTE(), e = S.eff / 100, ea = S.assumed / 100, thr = Math.pow(10, -S.thr);
    const n0 = Math.pow(10, -S.start), a = { n0, label: "control" }, b = { n0: n0 * S.fc, label: "treated" };
    [a, b].forEach(x => x.cq = cq(x.n0, e, thr));
    const dcq = a.cq - b.cq, reported = Math.pow(1 + ea, dcq), err = (reported / S.fc - 1) * 100;
    const w = 560, h = 260, L = 52, B = 42, T = 10, R = 12;
    const X = c => L + c / CYCLES * (w - L - R), Y = v => T + (1 - (Math.log10(v) + 12) / 12) * (h - B - T);
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Amplification curves of two samples on a log scale">`;
    for (let k = -12; k <= 0; k += 2) svg += `<text x="${L - 6}" y="${Y(Math.pow(10, k)) + 4}" text-anchor="end" class="ax">1e${k}</text>`;
    for (let c = 0; c <= CYCLES; c += 5) svg += `<text x="${X(c)}" y="${h - B + 15}" text-anchor="middle" class="ax">${c}</text>`;
    svg += `<line x1="${L}" x2="${w - R}" y1="${Y(thr)}" y2="${Y(thr)}" stroke="${C.muted}" stroke-dasharray="4 3"/><text x="${w - R}" y="${Y(thr) - 4}" text-anchor="end" class="ax">threshold</text>`;
    [a, b].forEach((x, i) => {
      const pts = [];
      for (let c = 0; c <= CYCLES; c += 0.5) pts.push(`${X(c).toFixed(1)},${Y(Math.max(1e-12, signal(x.n0, e, c))).toFixed(1)}`);
      svg += `<polyline fill="none" stroke="${P[i % P.length]}" stroke-width="2" points="${pts.join(" ")}"/>`;
      if (x.cq > 0 && x.cq < CYCLES) svg += `<line x1="${X(x.cq)}" x2="${X(x.cq)}" y1="${Y(thr)}" y2="${h - B}" stroke="${P[i % P.length]}" stroke-dasharray="2 2"/>`;
    });
    svg += `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">cycle</text></svg>`;
    const m = (k, v, note, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${note}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">Amplification curves</div>${svg}
        ${H.legend([[`control: Cq ${a.cq.toFixed(2)}`, P[0]], [`treated: Cq ${b.cq.toFixed(2)}`, P[1 % P.length]]])}
        <p class="note">The treated sample starts with ${S.fc}× as much template, so it crosses the threshold ${dcq.toFixed(2)} cycles earlier.</p></section>
      <section class="pg-card"><div class="label">The fold change you would report</div>
        <div class="metrics">${m("True fold change", `${S.fc}×`, "what is really in the tubes")}
          ${m("Reported", `${reported.toFixed(2)}×`, `(1 + ${S.assumed}%)^ΔCq with ΔCq = ${dcq.toFixed(2)}`)}
          ${m("Error", `${err >= 0 ? "+" : ""}${err.toFixed(0)}%`, "from assuming the wrong efficiency", Math.abs(err) > 10)}</div>
        <p class="note">ΔCq does not depend on the threshold or the starting amount, only on the fold change and the true efficiency. The error comes from the efficiency you assume, and grows with ΔCq.</p></section>`;
  }

  window.EfficiencyPlayground = E.makePlayground({
    defaults: { fc: 8, eff: 100, assumed: 100, start: 10, thr: 3 },
    controls: [
      { group: "The samples", items: [
        { key: "fc", label: "True fold change (treated vs control)", type: "range", min: 1, max: 64, step: 1 },
        { key: "start", label: "Starting template (10^−x of the plateau)", type: "range", min: 7, max: 12, step: 0.5, help: "Less template means a later Cq." }] },
      { group: "Efficiency", items: [
        { key: "eff", label: "True efficiency (%)", type: "range", min: 70, max: 110, step: 1, help: "100% doubles the product every cycle." },
        { key: "assumed", label: "Efficiency you assume (%)", type: "range", min: 70, max: 110, step: 1, help: "2^−ΔΔCq assumes 100%." }] },
      { group: "Instrument", items: [
        { key: "thr", label: "Threshold (10^−x of the plateau)", type: "range", min: 1, max: 4, step: 0.25 }] },
    ],
    presets: [
      ["A perfect pair (the defaults)", {}, "True and assumed efficiency are both 100%: the reported fold change is exact."],
      ["A 90% pair treated as 100%", { eff: 90 }, "ΔΔCq overstates the change; the error grows with the fold change."],
      ["Correct for the efficiency", { eff: 90, assumed: 90 }, "Using the measured efficiency gives the true fold change back."],
      ["Move the threshold", { thr: 1.5 }, "Both Cq values shift together; their difference, and the fold change, stay the same."],
    ],
    render: (S, el) => render(Object.fromEntries(Object.entries(S).map(([k, v]) => [k, Number(v)])), el),
  });
})();
