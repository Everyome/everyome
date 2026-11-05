/* Playground for function annotation: one protein, two domains, several member databases each drawing them a little
   differently, and InterPro bringing their signatures together. Illustrative signatures and positions. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const LEN = 520;
  const DBS = {
    Pfam: [["PF00018", "SH3 domain", 22, 70, "SH3"], ["PF00069", "Protein kinase domain", 182, 440, "Kinase"]],
    SMART: [["SM00326", "SH3", 18, 74, "SH3"], ["SM00220", "S_TKc", 178, 446, "Kinase"]],
    PROSITE: [["PS50002", "SH3 domain profile", 16, 76, "SH3"], ["PS50011", "Protein kinase domain profile", 180, 445, "Kinase"]],
    CDD: [["cd00174", "SH3", 21, 71, "SH3"]],
  };
  const ENTRY = { SH3: ["IPR001452", "SH3 domain"], Kinase: ["IPR000719", "Protein kinase domain"] };

  function render(S, el) {
    const C = H.COL(), P = H.PALETTE(), on = Object.keys(DBS).filter(d => S[d]), w = 600, L = 90, X = v => L + v / LEN * (w - L - 10);
    const hits = on.flatMap(d => DBS[d].map(m => [d, ...m])), groups = [...new Set(hits.map(h => h[5]))];
    const rows = [["InterPro", groups.map(g => { const ms = hits.filter(h => h[5] === g); return ["InterPro", ...ENTRY[g], Math.min(...ms.map(m => m[3])), Math.max(...ms.map(m => m[4])), g]; })], ...on.map(d => [d, hits.filter(h => h[0] === d)])];
    const h = 30 + rows.length * 26, col = g => P[["SH3", "Kinase"].indexOf(g) % P.length];
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Signatures from each database"><line x1="${L}" x2="${w - 10}" y1="14" y2="14" stroke="${C.ink}" stroke-width="3"/>`;
    rows.forEach(([name, ms], i) => { const y = 26 + i * 26; s += `<text x="${L - 8}" y="${y + 12}" text-anchor="end" class="ax">${name}</text>`;
      ms.forEach(m => s += `<rect x="${X(m[3])}" y="${y}" width="${X(m[4]) - X(m[3])}" height="16" rx="4" fill="${col(m[5])}" opacity="${name === "InterPro" ? 1 : .7}"><title>${m[1]} ${m[2]} (${m[3]}–${m[4]})</title></rect>`); });
    s += "</svg>";
    const m = (k, v, n) => `<div class="m"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">A 520-residue protein</div>${s}${H.legend([["SH3 domain", col("SH3")], ["protein kinase domain", col("Kinase")]])}</section>
      <section class="pg-card"><div class="label">Counting</div><div class="metrics">${m("Matches", hits.length, `from ${on.length} database${on.length === 1 ? "" : "s"}`)}
        ${m("InterPro entries", groups.length, "what the protein actually has")}</div>
        <p class="note">Each database draws the domain's ends a little differently; InterPro groups signatures for the same domain into one entry. Count entries, not matches.</p></section>`;
  }

  window.DomainsPlayground = E.makePlayground({
    defaults: { Pfam: 1, SMART: 1, PROSITE: 1, CDD: 1 },
    controls: [{ group: "Member databases searched (0 off, 1 on)", items: Object.keys(DBS).map(d => ({ key: d, label: d, type: "range", min: 0, max: 1, step: 1 })) }],
    presets: [
      ["All four databases (the defaults)", {}, "Seven matches, but only two domains: InterPro brings them together."],
      ["Pfam only", { SMART: 0, PROSITE: 0, CDD: 0 }, "One match per domain; the boundaries are Pfam's."],
      ["One database alone", { Pfam: 0, SMART: 0, PROSITE: 0 }, "A single database can miss a domain the others find (in this toy, its kinase signature is left out); searching several catches more."],
    ],
    render,
  });
})();
