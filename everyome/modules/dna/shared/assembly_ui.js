/* Shared live-session views for genome assembly modules: compare assemblies, contigs, genes, choose and export.
   The engine side is everyome/modules/dna/explorer.py. A module's own ui.js calls Everyome.assembly() and registers
   these views next to its own Run-page report. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, barChart, stacked, guide } = H;
  const COL = () => H.COL(), PALETTE = () => H.PALETTE();
  const lede = t => `<p class="lede">${t}</p>`;
  // Lengths read better in bases, kb and Mb.
  const bp = n => n >= 1e6 ? (n / 1e6).toFixed(2) + " Mb" : n >= 1e3 ? (n / 1e3).toFixed(1) + " kb" : fmt(n) + " bp";
  const BUSCO = ["Complete", "Fragmented", "Missing"];

  E.assembly = () => {
    const S = { list: null };
    const load = async () => (S.list = S.list || await E.call("assemblies"));
    const pick = (sel, list, cur) => `<select id="${sel}" style="width:auto">${list.map(a => `<option value="${esc(a.id)}" ${a.id === cur ? "selected" : ""}>${esc(a.label)}</option>`).join("")}</select>`;
    // Intent: start from the most contiguous assembly (then the most complete, then the most finished stage).
    const rank = { assembly: 0, polished: 1, scaffold: 2 };
    const best = list => [...list].sort((a, b) => b.n50 - a.n50 || (b.busco?.complete || 0) - (a.busco?.complete || 0) || rank[b.stage] - rank[a.stage])[0];
    const empty = el => { el.innerHTML = `<div class="notice warn">No assemblies were found in this run's results. Check the pipeline log on the Run page.</div>`; };

    // Nx curves: contig length (log) against the share of the genome in contigs at least that long.
    function nxPlot(curves) {
      const w = 760, h = 320, L = 64, B = 36, P = PALETTE(), c = COL();
      const ys = curves.flatMap(s => s.points.map(p => p[1])), lo = Math.log10(Math.max(1, Math.min(...ys))), hi = Math.log10(Math.max(...ys) * 1.1);
      const X = v => L + v / 100 * (w - L - 10), Y = v => h - B - (Math.log10(Math.max(v, 1)) - lo) / (hi - lo || 1) * (h - B - 10);
      let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Nx curves">`;
      for (let e = Math.ceil(lo); e <= hi; e++) svg += `<line x1="${L}" x2="${w - 10}" y1="${Y(10 ** e)}" y2="${Y(10 ** e)}" stroke="${c.rule}"/><text x="${L - 6}" y="${Y(10 ** e) + 4}" text-anchor="end" class="ax">${bp(10 ** e)}</text>`;
      svg += `<line x1="${X(50)}" x2="${X(50)}" y1="10" y2="${h - B}" stroke="${c.ox}" stroke-dasharray="4 3"/><text x="${X(50) + 4}" y="20" class="ax">N50</text>`;
      curves.forEach((s, i) => svg += `<polyline fill="none" stroke="${P[i % P.length]}" stroke-width="2" points="${s.points.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ")}"><title>${esc(s.label)}</title></polyline>`);
      [0, 25, 50, 75, 100].forEach(v => svg += `<text x="${X(v)}" y="${h - B + 16}" text-anchor="middle" class="ax">${v}%</text>`);
      svg += `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">Share of the assembly in contigs at least this long</text></svg>`;
      return svg + `<div class="legend">${curves.map((s, i) => `<span><i style="background:${P[i % P.length]}"></i>${esc(s.label)}</span>`).join("")}</div>`;
    }

    // ---------------------------------------------------------------- compare
    async function compare(el) {
      const list = await load();
      if (!list.length) return empty(el);
      const c = COL(), withB = list.filter(a => a.busco);
      el.innerHTML = lede("Every assembly the pipeline made, side by side (point at a name to see its file). Longer contigs (higher N50, fewer contigs) and higher BUSCO completeness are better; the total size should be close to the genome size you expect.") +
        `<div class="card" style="overflow:auto"><div class="label">Assemblies</div><table><thead><tr><th>Assembly</th><th class="num">Size</th><th class="num">Contigs</th><th class="num">Largest</th>
          <th class="num">N50</th><th class="num">L50</th><th class="num">GC</th><th class="num">Gaps (N)</th><th class="num">BUSCO complete</th><th>Genes</th></tr></thead><tbody>
          ${list.map(a => `<tr><td><b title="${esc(a.path)}">${esc(a.label)}</b></td><td class="num">${bp(a.total)}</td><td class="num">${fmt(a.n)}</td>
            <td class="num">${bp(a.largest)}</td><td class="num">${bp(a.n50)}</td><td class="num">${fmt(a.l50)}</td><td class="num">${(100 * a.gc).toFixed(1)}%</td><td class="num">${fmt(a.ns)}</td>
            <td class="num">${a.busco ? a.busco.complete.toFixed(1) + "%" : "–"}</td><td class="small">${a.annotation ? "yes" : "–"}</td></tr>`).join("")}</tbody></table>${guide("compare")}</div>
        <div class="card" style="margin-top:18px"><div class="label">Contiguity (Nx curves)</div><div id="nx"></div>${guide("nx")}</div>
          <div class="card" style="margin-top:18px"><div class="label">BUSCO completeness${withB[0] ? ` (${esc(withB[0].busco.lineage)}, ${withB[0].busco.markers} genes)` : ""}</div>
            ${withB.length ? stacked(withB.map(a => [a.label, [a.busco.complete, a.busco.fragmented, a.busco.missing].map(v => v / 100)]), BUSCO, [c.golddk, c.gold, c.ox], { w: 760, left: 260, title: "BUSCO" })
              : `<p class="small muted">No BUSCO results. Turn on BUSCO in the pipeline settings to measure completeness.</p>`}${guide("busco")}</div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Choose the final assembly →</button><button class="btn" data-go="step:contigs">Look at contigs</button></div>`;
      $("#nx", el).innerHTML = nxPlot(await E.call("nx_curves"));
    }

    // ---------------------------------------------------------------- contigs
    async function contigs(el) {
      const list = await load();
      if (!list.length) return empty(el);
      el.innerHTML = lede("The contigs of one assembly: how long they are, and their GC content. A group of contigs with unusual GC, low size or few genes can be contamination or a plasmid or organelle.") +
        `<div class="row" style="margin-bottom:12px"><label class="small">Assembly ${pick("as", list, best(list).id)}</label></div><div id="body"></div>`;
      const show = async () => {
        const d = await E.call("contigs", { id: $("#as", el).value, n: 300 }), c = COL(), cs = d.contigs;
        const w = 560, h = 260, L = 50, B = 34, lx = v => Math.log10(Math.max(v, 100)), xm = lx(cs[0]?.length || 1000), xl = lx(cs[cs.length - 1]?.length || 100);
        const gcs = cs.map(x => x.gc), g0 = Math.min(...gcs, .3) - .02, g1 = Math.max(...gcs, .6) + .02;
        const X = v => L + (lx(v) - xl) / (xm - xl || 1) * (w - L - 10), Y = v => h - B - (v - g0) / (g1 - g0) * (h - B - 10);
        $("#body", el).innerHTML = `<div class="grid g2"><div class="card"><div class="label">Largest contigs (${fmt(d.count)} in all, ${bp(d.total)})</div>
            ${barChart(cs.slice(0, 25).map(x => [x.name, x.length]), { w: 560, label: bp, title: "Contig lengths" })}</div>
          <div class="card"><div class="label">GC content against length</div><svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="GC against contig length">
            ${cs.map(x => `<circle cx="${X(x.length).toFixed(1)}" cy="${Y(x.gc).toFixed(1)}" r="${Math.max(2.5, Math.min(9, Math.sqrt(x.length / d.total) * 30))}" fill="${c.golddk}" opacity=".6"><title>${esc(x.name)}: ${bp(x.length)}, GC ${(100 * x.gc).toFixed(1)}%</title></circle>`).join("")}
            <line x1="${L}" x2="${w}" y1="${h - B}" y2="${h - B}" stroke="${c.muted}"/><text x="${(w + L) / 2}" y="${h - 6}" text-anchor="middle" class="ax">Contig length (log)</text>
            <text x="14" y="${h / 2}" transform="rotate(-90 14 ${h / 2})" text-anchor="middle" class="ax">GC content</text>
            ${[g0 + .02, (g0 + g1) / 2, g1 - .02].map(v => `<text x="${L - 4}" y="${Y(v) + 4}" text-anchor="end" class="ax">${(100 * v).toFixed(0)}%</text>`).join("")}</svg>${guide("contigs")}</div></div>
          <div class="card" style="margin-top:18px;max-height:360px;overflow:auto"><table><thead><tr><th>Contig</th><th class="num">Length</th><th class="num">GC</th><th class="num">Gaps (N)</th></tr></thead><tbody>
            ${cs.map(x => `<tr><td class="mono small">${esc(x.name)}</td><td class="num">${bp(x.length)}</td><td class="num">${(100 * x.gc).toFixed(1)}%</td><td class="num">${fmt(x.ns)}</td></tr>`).join("")}</tbody></table></div>`;
      };
      $("#as", el).onchange = show; show();
    }

    // ---------------------------------------------------------------- genes
    async function genes(el) {
      const list = (await load()).filter(a => a.annotation);
      if (!list.length) {
        el.innerHTML = `<div class="notice">No gene annotation in this run. Genes are added when the pipeline annotates the assembly (see the manual).</div>`;
        return;
      }
      el.innerHTML = lede("The genes found on one assembly. Search by name, product or id; the table shows where each gene sits.") +
        `<div class="row" style="margin-bottom:12px"><label class="small">Assembly ${pick("as", list, best(list).id)}</label>
          <input type="text" id="q" placeholder="Search genes…" style="width:220px" aria-label="Search genes"></div><div id="body"></div>`;
      let t;
      const show = async () => {
        const d = await E.call("genes", { id: $("#as", el).value, q: $("#q", el).value.trim(), n: 300 });
        const labels = d.hist.edges.map((e, i) => i < d.hist.edges.length - 1 ? `${fmt(e)}–${fmt(d.hist.edges[i + 1])}` : `${fmt(e)}+`);
        $("#body", el).innerHTML = `<div class="grid g2"><div class="card"><div class="label">Summary</div>
            <div class="metric"><span>Genes</span><b>${fmt(d.genes)}</b></div><div class="metric"><span>With a name or known product</span><b>${fmt(d.with_name)}</b></div>
            ${d.unmapped != null ? `<div class="metric"><span>Not lifted over</span><b>${fmt(d.unmapped)}</b></div>` : ""}
            <p class="small muted">From <code style="word-break:break-all">${esc(d.annotation)}</code>. Features: ${Object.entries(d.counts).map(([k, v]) => `${esc(k)} ${fmt(v)}`).join(", ")}.</p>${guide("genes")}</div>
          <div class="card"><div class="label">Gene lengths (bp)</div>${barChart(labels.map((l, i) => [l, d.hist.counts[i]]), { w: 560, title: "Gene lengths" })}</div></div>
          <div class="card" style="margin-top:18px;max-height:420px;overflow:auto"><div class="label">${q() ? `${fmt(d.matches)} genes match` : "Genes"}${d.matches > d.rows.length ? ` (first ${fmt(d.rows.length)} shown)` : ""}</div>
            <table><thead><tr><th>Gene</th><th>Name</th><th>Product</th><th>Contig</th><th class="num">Start</th><th class="num">End</th><th>Strand</th><th class="num">Length</th></tr></thead><tbody>
            ${d.rows.map(g => `<tr><td class="mono small">${esc(g.id)}</td><td class="small">${esc(g.name)}</td><td class="small">${esc(g.product)}</td><td class="mono small">${esc(g.seqid)}</td>
              <td class="num">${fmt(g.start)}</td><td class="num">${fmt(g.end)}</td><td>${esc(g.strand)}</td><td class="num">${fmt(g.length)}</td></tr>`).join("")}</tbody></table></div>`;
      };
      const q = () => $("#q", el).value.trim();
      $("#as", el).onchange = show;
      $("#q", el).addEventListener("input", () => { clearTimeout(t); t = setTimeout(show, 250); });
      show();
    }

    // ---------------------------------------------------------------- choose and export
    async function exportView(el) {
      const list = await load();
      if (!list.length) return empty(el);
      const st = await E.status(), cur = st.chosen || best(list).id;
      el.innerHTML = lede("Choose the assembly to keep. Everyome copies it (and its genes, if any) to <code>results/final/</code>, with a table comparing every assembly, and notes your choice and reason in the run record.") +
        `<div class="card">${list.map(a => `<label class="row small" style="margin:8px 0;flex-wrap:nowrap;align-items:flex-start"><input type="radio" name="pick" value="${esc(a.id)}" ${a.id === cur ? "checked" : ""}>
            <span><b>${esc(a.label)}</b> · ${bp(a.total)} in ${fmt(a.n)} contigs · N50 ${bp(a.n50)}${a.busco ? ` · BUSCO ${a.busco.complete.toFixed(1)}%` : ""}${a.annotation ? " · with genes" : ""}</span></label>`).join("")}
          <label class="field" style="margin-top:10px"><span>Why this one (optional, goes in the record)</span><input type="text" id="why" placeholder="e.g. most contiguous with complete BUSCO"></label>
          ${guide("choose")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">Choose and export</button></div><div id="files"></div></div>`;
      const files = async () => {
        const f = await E.call("files");
        $("#files", el).innerHTML = f.length ? `<table style="margin-top:14px"><thead><tr><th>File</th><th class="num">Size</th><th></th></tr></thead><tbody>${f.map(x =>
          `<tr><td class="mono small">${esc(x.name)}</td><td class="num small">${fmtSize(x.size)}</td><td class="num"><a class="btn small" href="${E.downloadUrl(x.name)}" download>Download</a></td></tr>`).join("")}</tbody></table>` : "";
      };
      $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
        await E.call("choose", { id: $("input[name=pick]:checked", el).value, reason: $("#why", el).value });
        await E.call("export"); await files(); toast("Final assembly saved to results/final.", true);
      });
      files();
    }

    return { views: { compare, contigs, genes, export: exportView } };
  };
})();
