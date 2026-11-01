/* Playground for primer design: how length, GC content, salt and magnesium move a primer's melting
   temperature, and why the two primers of a pair should match. Tm uses the same nearest-neighbour model
   as Primer3 (SantaLucia 1998, with the von Ahsen magnesium correction); checked against Primer3 to 0.01 °C. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;

  // SantaLucia (1998) unified nearest-neighbour parameters: dH (kcal/mol), dS (cal/mol/K) for each base step.
  const NN = { AA: [-7.9, -22.2], TT: [-7.9, -22.2], AT: [-7.2, -20.4], TA: [-7.2, -21.3], CA: [-8.5, -22.7], TG: [-8.5, -22.7],
    GT: [-8.4, -22.4], AC: [-8.4, -22.4], CT: [-7.8, -21.0], AG: [-7.8, -21.0], GA: [-8.2, -22.2], TC: [-8.2, -22.2],
    CG: [-10.6, -27.2], GC: [-9.8, -24.4], GG: [-8.0, -19.9], CC: [-8.0, -19.9] };
  // Tm of a perfectly matched primer; salts in mM, primer in nM (as Primer3 takes them).
  function nnTm(s, mv, dv, dntp = 0.6, dna = 50) {
    let h = 0, e = 0;
    for (let i = 0; i < s.length - 1; i++) { const [a, b] = NN[s.slice(i, i + 2)]; h += a; e += b; }
    for (const end of [s[0], s[s.length - 1]]) { if ("GC".includes(end)) { h += 0.1; e += -2.8; } else { h += 2.3; e += 4.1; } }
    const na = mv + 120 * Math.sqrt(Math.max(dv - dntp, 0));          // magnesium as its sodium equivalent
    e += 0.368 * (s.length - 1) * Math.log(na / 1000);
    return h * 1000 / (e + 1.987 * Math.log(dna * 1e-9 / 4)) - 273.15;
  }
  // Wallace rule for short oligos: 2 °C per A or T, 4 °C per G or C.
  const tmWallace = (n, gc) => 2 * n * (1 - gc / 100) + 4 * n * gc / 100;

  // A primer of the chosen length and GC content with exactly `clamp` G/C in its last five bases (deterministic).
  function primer(n, gc, clamp) {
    const g = Math.round(n * gc / 100), tail = Math.min(clamp, 5, g), head = n - 5, headGC = Math.min(g - tail, head);
    // Intent: spread the head's G/C evenly; alternate G/C and A/T so there are no long runs.
    let s = "";
    for (let i = 0; i < head; i++) s += Math.floor((i + 1) * headGC / head) > Math.floor(i * headGC / head) ? "GC"[i % 2] : "AT"[i % 2];
    for (let i = 0; i < 5; i++) s += i >= 5 - tail ? "GC"[i % 2] : "AT"[i % 2];
    return s;
  }

  function render(S, el) {
    const C = H.COL(), seq = primer(S.len, S.gc, S.clamp), seq2 = primer(S.len2, S.gc2, 2);
    const tmOf = q => nnTm(q, S.salt, S.mg), t1 = tmOf(seq), t2 = tmOf(seq2);
    const w = 560, h = 260, L = 44, B = 34, X = n => L + (n - 12) / (35 - 12) * (w - L - 12), Y = t => h - B - (t - 20) / (95 - 20) * (h - B - 10);
    const line = (gc, col, label) => { const pts = []; for (let n = 12; n <= 35; n++) pts.push(`${X(n).toFixed(1)},${Y(tmOf(primer(n, gc, 2))).toFixed(1)}`);
      return `<polyline fill="none" stroke="${col}" stroke-width="2" points="${pts.join(" ")}"/><text x="${w - 10}" y="${Y(tmOf(primer(35, gc, 2))) - 4}" text-anchor="end" class="ax">${label}</text>`; };
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Melting temperature against primer length">
      <rect x="${L}" y="${Y(63)}" width="${w - L - 12}" height="${Y(57) - Y(63)}" fill="${C.gold}" opacity=".18"/>
      ${line(30, C.rule, "30% GC")}${line(50, C.muted, "50% GC")}${line(70, C.plum, "70% GC")}
      <circle cx="${X(S.len)}" cy="${Y(t1)}" r="6" fill="${C.ox}"/><circle cx="${X(S.len2)}" cy="${Y(t2)}" r="6" fill="none" stroke="${C.ox}" stroke-width="2"/>
      <line x1="${L}" x2="${w - 12}" y1="${h - B}" y2="${h - B}" stroke="${C.muted}"/>`;
    for (let n = 15; n <= 35; n += 5) svg += `<text x="${X(n)}" y="${h - B + 15}" text-anchor="middle" class="ax">${n}</text>`;
    for (let t = 30; t <= 90; t += 10) svg += `<text x="${L - 6}" y="${Y(t) + 4}" text-anchor="end" class="ax">${t}</text>`;
    svg += `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">primer length (bases)</text><text x="12" y="${h / 2}" transform="rotate(-90 12 ${h / 2})" text-anchor="middle" class="ax">Tm (°C)</text></svg>`;
    const runs = Math.max(...seq.match(/(.)\1*/g).map(x => x.length)), d = Math.abs(t1 - t2);
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">Your forward primer</div>
        <p class="mono" style="font-size:16px;letter-spacing:.06em;margin:0 0 10px">5'-${esc(seq.slice(0, -5))}<b style="color:${C.ox}">${esc(seq.slice(-5))}</b>-3'</p>
        <div class="metrics">${m("Melting temperature", `${t1.toFixed(1)} °C`, `as Primer3 calculates it; the old 2+4 rule would say ${tmWallace(S.len, S.gc).toFixed(0)} °C`, t1 < 52 || t1 > 68)}
          ${m("G or C in the last 5 bases", S.clamp, S.clamp > 3 ? "more than 3 can make it bind in the wrong places" : S.clamp === 0 ? "no clamp: the 3' end may fray" : "a good clamp", S.clamp > 3 || S.clamp === 0)}
          ${m("Longest run of one base", runs, runs > 4 ? "long runs slip and misprime" : "fine", runs > 4)}</div></section>
      <section class="pg-card"><div class="label">The pair</div><div class="metrics">
          ${m("Reverse primer Tm", `${t2.toFixed(1)} °C`, `${S.len2} bases, ${S.gc2}% GC`)}
          ${m("Difference", `${d.toFixed(1)} °C`, d > 5 ? "too far apart: one primer will be too hot or too cold" : d > 3 ? "workable, but closer is better" : "well matched", d > 5)}</div></section>
      <section class="pg-card"><div class="label">Tm against length at ${S.salt} mM salt and ${S.mg} mM magnesium</div>${svg}
        <p class="note">The shaded band is the 57–63 °C range Everyome uses by default. Filled dot: forward primer; ring: reverse.</p></section>`;
  }

  window.TmPlayground = E.makePlayground({
    defaults: { len: 20, gc: 50, clamp: 2, salt: 50, mg: 1.5, len2: 20, gc2: 50 },
    controls: [
      { group: "Forward primer", items: [
        { key: "len", label: "Length (bases)", type: "range", min: 12, max: 35, step: 1 },
        { key: "gc", label: "GC content (%)", type: "range", min: 20, max: 80, step: 5 },
        { key: "clamp", label: "G or C in the last 5 bases", type: "range", min: 0, max: 5, step: 1, help: "The 3' end, where the polymerase starts." }] },
      { group: "Reverse primer", items: [
        { key: "len2", label: "Length (bases)", type: "range", min: 12, max: 35, step: 1 },
        { key: "gc2", label: "GC content (%)", type: "range", min: 20, max: 80, step: 5 }] },
      { group: "Reaction", items: [
        { key: "salt", label: "Monovalent salt (mM)", type: "range", min: 10, max: 200, step: 5, help: "Na+ and K+ in the buffer." },
        { key: "mg", label: "Magnesium (mM)", type: "range", min: 0, max: 5, step: 0.5, help: "Mg2+ stabilises binding strongly; dNTPs (0.6 mM) take some of it up." }] },
    ],
    presets: [
      ["A well-matched pair (the defaults)", {}, "Two 20-base primers at 50% GC melt at the same temperature, inside the usual range."],
      ["Make the forward primer GC-rich", { gc: 70 }, "Each 10% more GC raises Tm by about 4 °C; the pair no longer matches."],
      ["Shorten the reverse primer to 14 bases", { len2: 14 }, "Short primers melt much lower; lengthen them or raise their GC to compensate."],
      ["Fix it: a longer, AT-rich primer", { gc: 35, len: 26 }, "Length can make up for low GC, bringing Tm back into range."],
      ["No magnesium, low salt", { salt: 10, mg: 0 }, "Without magnesium and with little salt, every primer melts much lower; match the calculation to your buffer."],
      ["Too strong a clamp", { clamp: 5 }, "Five G/C at the 3' end binds too eagerly and can prime from the wrong place."],
    ],
    render,
  });
})();
