/* Views for protein function annotation: what InterProScan made (Run page), then the live session: an overview, one
   protein's domain architecture with its matches and GO terms, the GO terms across all proteins, export. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, $$, esc, fmt, toast, guarded, guide, lede, filesTable, barChart } = H;
  let current = null;

  async function report(el, q) {
    el.innerHTML = `<h2>What InterProScan made</h2><div class="card"><div class="label">Matches</div>
      ${q.tsv ? `<p class="small">${fmt(q.matches)} matches in ${fmt(q.proteins)} proteins: <code>${esc(q.tsv)}</code>.</p>` : `<div class="notice warn">No results were found. Check the stage log.</div>`}
      ${E.state().demo ? `<p class="small muted">On the demo cluster, a quick stand-in replaces InterProScan.</p>` : ""}${guide("run_report")}</div>`;
  }

  async function overview(el) {
    const o = await E.call("overview");
    el.innerHTML = lede("What InterProScan recognised in your proteins. Most proteins of a well-studied kind match something; proteins with no match are often new, fast-evolving or wrongly predicted.") +
      `<div class="grid g2"><div class="card"><div class="label">Proteins</div>
          <div class="metric"><span>Proteins</span><b>${fmt(o.proteins)}</b></div>
          <div class="metric"><span>With any match</span><b>${fmt(o.with_match)} (${Math.round(100 * o.with_match / Math.max(1, o.proteins))}%)</b></div>
          <div class="metric"><span>With an InterPro entry</span><b>${fmt(o.with_interpro)}</b></div>
          <div class="metric"><span>With GO terms</span><b>${fmt(o.with_go)}</b></div>
          <div class="label" style="margin-top:12px">Matches per database</div>${barChart(Object.entries(o.databases), { w: 420, title: "Matches per database" })}${guide("overview")}</div>
        <div class="card"><div class="label">Most common InterPro entries</div>${o.top_entries.length ? barChart(o.top_entries.slice(0, 15).map(e => [e.name || e.entry, e.proteins]), { w: 520, label: v => `${v} proteins`, title: "Most common InterPro entries" }) : `<p class="small muted">None.</p>`}</div></div>
      <div class="card" style="margin-top:18px"><div class="row" style="justify-content:space-between"><div class="label">Every protein</div>
          <input type="text" id="q" placeholder="Search name, domain, InterPro or GO…" style="width:280px"></div>
        <div id="list" style="max-height:420px;overflow:auto"></div></div>`;
    const draw = ids => { const set = ids ? new Set(ids) : null;
      $("#list", el).innerHTML = `<table><thead><tr><th>Protein</th><th class="num">Length</th><th class="num">Matches</th><th>What it has</th></tr></thead><tbody>${o.proteins_list.filter(p => !set || set.has(p.id)).map(p =>
        `<tr class="click" tabindex="0" data-p="${esc(p.id)}"><td class="mono">${esc(p.id)}</td><td class="num">${fmt(p.length)}</td><td class="num">${p.matches}</td><td class="small">${p.entries.map(esc).join("; ") || '<span class="muted">no match</span>'}</td></tr>`).join("")}</tbody></table>`; };
    let t; $("#q", el).oninput = e => { clearTimeout(t); t = setTimeout(async () => draw(e.target.value.trim().length >= 2 ? await E.call("search", { q: e.target.value }) : null), 250); };
    $("#list", el).addEventListener("click", e => { const r = e.target.closest("[data-p]"); if (r) { current = r.dataset.p; H.go("step:protein"); } });
    draw(null);
  }

  // Domain architecture: the protein as a line, each database's matches on its own track, InterPro entries on top.
  function architecture(p) {
    const C = H.COL(), P = H.PALETTE(), dbs = [...new Set(p.matches.map(m => m.database))], w = 640, L = 110, X = v => L + v / p.length * (w - L - 10);
    const entries = [...new Set(p.matches.map(m => m.interpro).filter(Boolean))], col = e => P[entries.indexOf(e) % P.length] || C.muted;
    const rows = [["InterPro", p.matches.filter(m => m.interpro)], ...dbs.map(d => [d, p.matches.filter(m => m.database === d)])];
    const h = 30 + rows.length * 26;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Domain architecture of ${esc(p.id)}"><line x1="${L}" x2="${w - 10}" y1="14" y2="14" stroke="${C.ink}" stroke-width="3"/>
      <text x="${L}" y="${h - 2}" class="ax">1</text><text x="${w - 10}" y="${h - 2}" text-anchor="end" class="ax">${fmt(p.length)}</text>`;
    rows.forEach(([name, ms], i) => { const y = 26 + i * 26;
      s += `<text x="${L - 8}" y="${y + 12}" text-anchor="end" class="ax">${esc(name)}</text>`;
      ms.forEach(m => s += `<rect x="${X(m.start)}" y="${y}" width="${Math.max(2, X(m.end) - X(m.start))}" height="16" rx="4" fill="${col(m.interpro)}" opacity="${name === "InterPro" ? 1 : .7}">
        <title>${esc(m.accession)} ${esc(m.description)} (${m.start}–${m.end})${m.interpro ? ` · ${esc(m.interpro)} ${esc(m.interpro_name)}` : ""}</title></rect>`); });
    return s + "</svg>";
  }

  async function protein(el) {
    const o = await E.call("overview");
    current = current || (o.proteins_list.find(p => p.matches) || o.proteins_list[0])?.id;
    el.innerHTML = lede("One protein: where each database found a domain or family along its sequence, the InterPro entries that bring them together, and the GO terms they imply.") +
      `<div class="card"><label class="small">Protein <select id="pick" style="width:auto">${o.proteins_list.map(p => `<option ${p.id === current ? "selected" : ""}>${esc(p.id)}</option>`).join("")}</select></label>
        <div id="arch" style="margin-top:10px"></div>${guide("architecture")}</div><div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">Matches</div><div id="m"></div></div>
        <div class="card"><div class="label">GO terms</div><div id="g"></div></div></div>`;
    const show = async () => {
      const p = await E.call("protein", { id: current });
      $("#arch", el).innerHTML = p.matches.length ? architecture(p) : `<p class="small muted">${esc(p.id)} (${fmt(p.length)} residues) has no match in the databases searched.</p>`;
      $("#m", el).innerHTML = p.matches.length ? `<table class="small"><thead><tr><th>Database</th><th>Signature</th><th class="num">From–to</th><th>InterPro</th></tr></thead><tbody>${p.matches.map(m =>
        `<tr><td>${esc(m.database)}</td><td><b>${esc(m.accession)}</b> ${esc(m.description)}</td><td class="num">${m.start}–${m.end}</td><td>${m.interpro ? `${esc(m.interpro)} ${esc(m.interpro_name)}` : "–"}</td></tr>`).join("")}</tbody></table>` : `<p class="small muted">None.</p>`;
      $("#g", el).innerHTML = p.go.length ? `<table class="small"><tbody>${p.go.map(g => `<tr><td class="mono">${esc(g.id)}</td><td>${esc(g.name || "")}</td><td class="muted">${esc(g.aspect || "")}</td></tr>`).join("")}</tbody></table>` : `<p class="small muted">None.</p>`;
    };
    $("#pick", el).onchange = e => { current = e.target.value; show(); };
    show();
  }

  async function go(el) {
    const t = await E.call("go_terms");
    const asp = [...new Set(t.map(x => x.aspect).filter(Boolean))];
    el.innerHTML = lede("GO terms across all your proteins, from the InterPro entries they match. A term here means a domain or family usually linked to it, not proof of the function in your organism.") +
      `<div class="card">${t.length ? asp.map(a => `<div class="label" style="margin-top:8px">${esc(a)}</div><table class="small"><thead><tr><th>GO term</th><th>Name</th><th class="num">Proteins</th></tr></thead><tbody>${t.filter(x => x.aspect === a).map(x =>
        `<tr><td class="mono">${esc(x.id)}</td><td>${esc(x.name)}</td><td class="num" title="${esc(x.proteins.join(", "))}">${x.proteins.length}</td></tr>`).join("")}</tbody></table>`).join("") +
        (t.some(x => !x.aspect) ? `<p class="small muted">${t.filter(x => !x.aspect).length} more terms without names in the results.</p>` : "") : `<p class="small muted">No GO terms (turn on Add GO terms in the settings).</p>`}${guide("go")}</div>`;
  }

  async function exportView(el) {
    el.innerHTML = lede("Save the annotations as tables for your own analysis, a genome paper's supplement or an enrichment tool.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>protein_annotations.csv</b>: each protein's InterPro entries, descriptions and GO terms (one row per protein).</li>
        <li><b>domains.csv</b>: every match with its position and score.</li>
        <li><b>go_terms.csv</b>: each GO term and the proteins that have it (for enrichment tools).</li></ul>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Tables saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("protein.function", { report, overview, protein, go, export: exportView });
})();
