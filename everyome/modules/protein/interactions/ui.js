/* Views for interaction prediction: the interfaces of every predicted complex, scored, then the structure prediction
   views (../structure/ui.js, shared through E.proteinViews) on the same predictions. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, $$, esc, fmt, guarded, toast, guide, lede } = H;
  const V = E.proteinViews;
  const VERDICT = { "likely binds as predicted": "ok", "uncertain": "warn", "unlikely to bind as predicted": "bad" };
  const chip = v => { const C = H.COL(), col = { ok: C.ok, warn: C.gold, bad: C.ox }[VERDICT[v]]; return `<span class="chip" style="cursor:inherit;border-color:${col}"><i style="background:${col}"></i>${esc(v)}</span>`; };
  const num = (v, d = 2) => v == null ? "–" : (+v).toFixed(d);

  async function interfaces(el) {
    el.innerHTML = lede("Every predicted complex, pair of chains by pair of chains: how much of each chain touches the other, how confident the predictor is there, and what the scores together suggest. Click a row to look closer.") +
      `<div class="card"><div class="label">Interfaces</div><div id="tbl"><p class="small muted">Scoring…</p></div>${guide("interfaces", { open: true })}</div><div id="detail"></div>`;
    const r = await E.call("interfaces");
    const rows = r.complexes.flatMap(m => m.pairs.map(q => ({ m, q })));
    $("#tbl", el).innerHTML = rows.length ? `<table><thead><tr><th>Complex</th><th>Method</th><th>Chains</th><th class="num">Contacts</th><th class="num">Interface pLDDT</th><th class="num">Interface PAE (Å)</th><th class="num">ipTM</th><th class="num">pDockQ</th><th>Reading</th></tr></thead><tbody>
      ${rows.map(({ m, q }, i) => `<tr class="click" tabindex="0" data-i="${i}"><td>${esc(m.id)}</td><td>${esc(m.method)}</td><td>${esc(q.a)}–${esc(q.b)}</td><td class="num">${fmt(q.contacts)}</td>
        <td class="num">${num(q.interface_plddt, 1)}</td><td class="num">${num(q.interface_pae, 1)}</td><td class="num">${num(q.iptm)}</td><td class="num">${num(q.pdockq)}</td><td>${chip(q.verdict)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="notice warn">No predicted complexes were found: every structure has one chain. Check each FASTA file holds the complex's chains.</div>`;
    if (r.single.length) $("#tbl", el).insertAdjacentHTML("beforeend", `<p class="small muted">Single chains (no interface): ${r.single.map(esc).join(", ")}.</p>`);
    const open = async i => {
      $$("#tbl tr.sel", el).forEach(t => t.classList.remove("sel")); $(`#tbl tr[data-i="${i}"]`, el)?.classList.add("sel");
      const { m, q } = rows[i], d = await E.call("interface", { key: m.key, a: q.a, b: q.b }), s = await E.call("structure", { key: m.key });
      const at = new Set(d.interface), P = H.PALETTE(), C = H.COL();
      const side = (n, list) => `<div><div class="label" style="margin-bottom:4px">Chain ${esc(n)}: ${list.length} residues at the interface</div><p class="small mono" style="word-break:break-word">${list.map(x => `${x.aa}${x.num}`).join(" ") || "none"}</p></div>`;
      $("#detail", el).innerHTML = `<div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">${esc(m.id)} · chains ${esc(q.a)} and ${esc(q.b)}</div>
          <div style="position:relative"><canvas id="mol" style="width:100%;height:380px;border-radius:6px;touch-action:none;cursor:grab" aria-label="3D structure with the interface highlighted"></canvas>
          <div id="tip" class="small" style="position:absolute;left:10px;top:8px;background:${C.card};padding:2px 6px;border-radius:4px"></div></div>
          ${H.legend([[`chain ${q.a}`, P[0]], [`chain ${q.b}`, P[1]], ["at the interface", C.ox]])}${guide("viewer")}</div>
        <div class="card"><div class="label">The interface</div>${side(q.a, d.side_a)}${side(q.b, d.side_b)}
          <div class="label" style="margin-top:10px">Predicted error between the chains</div><div id="blk"></div>${guide("interface_detail")}</div></div>`;
      V.viewer($("#mol", el), s.residues, (r, i) => at.has(i) ? C.ox : P[s.chains.indexOf(r.chain) % P.length] + "99",
        r => { $("#tip", el).textContent = r ? `${r.chain}${r.num} ${r.aa} · pLDDT ${r.plddt}` : ""; });
      if (d.pae_block) {
        const b = d.pae_block, nr = b.cells.length, nc = b.cells[0].length, cell = Math.max(2, Math.min(6, 300 / Math.max(nr, nc)));
        const lo = H.hexRgb(C.plum), hi = H.hexRgb(C.card), col = v => `rgb(${lo.map((x, k) => Math.round(x + (hi[k] - x) * Math.min(1, v / 30)))})`;
        $("#blk", el).innerHTML = `<svg class="chart" viewBox="0 0 ${nc * cell} ${nr * cell}" style="max-width:${nc * cell}px" role="img" aria-label="PAE between the chains">${b.cells.map((row, i) => row.map((v, j) =>
          `<rect x="${j * cell}" y="${i * cell}" width="${cell}" height="${cell}" fill="${col(v)}"/>`).join("")).join("")}</svg>
          <p class="small muted">Rows: chain ${esc(b.rows)}; columns: chain ${esc(b.cols)}${b.step > 1 ? ` (blocks of ${b.step})` : ""}. Dark: confidently placed relative to each other.</p>`;
      } else $("#blk", el).innerHTML = `<p class="small muted">This method gives no predicted aligned error.</p>`;
    };
    $("#tbl", el).addEventListener("click", e => { const t = e.target.closest("tr[data-i]"); if (t) open(+t.dataset.i); });
    $("#tbl", el).addEventListener("keydown", e => { if (e.key === "Enter") e.target.closest("tr[data-i]")?.click(); });
    if (rows.length) open(0);
  }

  E.registerViews("protein.interactions", { report: V.report, interfaces, overview: V.overview, structure: V.structure, compare: V.compare, export: V.export });
})();
