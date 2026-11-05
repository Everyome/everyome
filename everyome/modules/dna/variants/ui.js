/* Views for variant calling: pipeline report, samples and callers, filters with a variant table, groups, export.
   Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, esc, fmt, toast, guarded, guide, legend, lede, filesTable, barChart } = H;
  const COL = () => H.COL(), PAL = () => H.PALETTE();
  let ov = null;
  const overview = async () => (ov = ov || await E.call("overview"));
  const callerColour = c => PAL()[ov.callers.indexOf(c) % PAL().length];

  // A genotype as a small glyph: hollow (not carried), half (one copy), full (two copies), ? (no call passed the filters).
  function gt(d) {
    const c = COL(), t = { "-1": "uncertain", 0: "not carried (0/0)", 1: "one copy (0/1)", 2: "two copies (1/1)" }[d];
    if (d === -1) return `<span class="muted" title="${t}">?</span>`;
    const fill = d === 2 ? c.ox : "none", half = d === 1 ? `<path d="M7 1 A6 6 0 0 1 7 13 Z" fill="${c.ox}"/>` : "";
    return `<svg width="14" height="14" viewBox="0 0 14 14" role="img" aria-label="${t}"><title>${t}</title><circle cx="7" cy="7" r="6" fill="${fill}" stroke="${d ? c.ox : c.muted}" stroke-width="1.5"/>${half}</svg>`;
  }

  // Grouped bars: one group per bin, one bar per series (a caller or a sample).
  function bars(edges, series, { xlab = "", h = 200, label = "" } = {}) {
    const names = Object.keys(series), n = edges.length, w = 560, L = 44, B = 34, T = 10;
    const max = Math.max(1, ...names.flatMap(k => series[k])), gw = (w - L - 10) / n, bw = Math.max(2, (gw - 4) / names.length);
    const y = v => T + (1 - v / max) * (h - B - T);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${COL().muted}"/>`;
    s += `<text x="${L - 6}" y="${T + 8}" text-anchor="end" class="ax">${fmt(max)}</text><text x="${L - 6}" y="${h - B}" text-anchor="end" class="ax">0</text>`;
    edges.forEach((e, i) => {
      names.forEach((k, j) => { const v = series[k][i] || 0;
        s += `<rect x="${L + i * gw + 2 + j * bw}" y="${y(v)}" width="${bw - 1}" height="${h - B - y(v)}" fill="${PAL()[j % PAL().length]}"><title>${esc(k)}, ${esc(String(e))}: ${fmt(v)}</title></rect>`; });
      s += `<text x="${L + i * gw + gw / 2}" y="${h - B + 14}" text-anchor="middle" class="ax">${esc(String(e))}</text>`;
    });
    return s + `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">${esc(xlab)}</text></svg>` + legend(names.map((k, j) => [k, PAL()[j % PAL().length]]));
  }

  // ---------------------------------------------------------------- pipeline report (Run page)
  async function report(el, q) {
    const st = E.state(), callers = [...new Set(q.vcfs.map(v => v.caller))], samples = [...new Set(q.vcfs.map(v => v.sample))];
    el.innerHTML = `<h2>What the pipeline made</h2>
      <div class="grid g2"><div class="card"><div class="label">Variant calls</div>
        ${q.vcfs.length ? `<p class="small">${callers.length} caller${callers.length > 1 ? "s" : ""} (${callers.map(esc).join(", ")}) × ${samples.length} samples: ${q.vcfs.length} VCF files in <code>results/variant_calling/</code>.</p>`
          : `<div class="notice warn">No variant calls were found. Check the pipeline log; the live session needs them.</div>`}
        ${q.coverage.length ? barChart(q.coverage.map(c => [c.sample, c.mean]), { label: v => v.toFixed(1) + "×", title: "Mean read depth per sample (mosdepth)" }) +
          `<p class="small muted">Germline calls need about 15× or more for confident genotypes; 30× is typical for whole genomes.</p>` : ""}</div>
      <div class="card"><div class="label">Quality report</div>
        ${q.multiqc ? `<p class="small">nf-core/sarek's MultiQC report brings together every check: read quality, mapping, duplicates, coverage and variant statistics.</p>
          <a class="btn primary small" href="/api/run/file?path=${encodeURIComponent(q.multiqc)}" target="_blank" rel="noopener">Open the MultiQC report</a>`
          : `<p class="small muted">No MultiQC report found.</p>`}
        ${st.demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster this is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  // ---------------------------------------------------------------- samples and callers
  async function overviewView(el) {
    const o = await overview(), names = c => o.caller_names[c] || c;
    const many = o.callers.length > 1;
    el.innerHTML = lede(`${fmt(o.variants)} candidate variants from ${o.callers.length} caller${many ? "s" : ""} in ${o.samples.length} samples. First, check each sample and how far the callers agree.`) +
      `<div class="card"><div class="label">Calls per sample (before any filter)</div><div style="overflow:auto"><table><thead><tr><th>Caller</th><th>Sample</th><th>Group</th><th class="num">Mean depth</th><th class="num">Variants</th><th class="num">SNVs</th><th class="num">Indels</th><th class="num">Ti/Tv</th><th class="num">Het</th><th class="num">Hom</th></tr></thead><tbody>
        ${o.per.map(p => `<tr><td>${esc(names(p.caller))}</td><td>${esc(p.sample)}</td><td>${esc(o.groups[p.sample] || "")}</td><td class="num">${o.coverage[p.sample] != null ? o.coverage[p.sample].toFixed(1) + "×" : ""}</td><td class="num">${fmt(p.variants)}</td><td class="num">${fmt(p.snv)}</td><td class="num">${fmt(p.indel)}</td><td class="num">${p.titv ?? ""}</td><td class="num">${fmt(p.het)}</td><td class="num">${fmt(p.hom)}</td></tr>`).join("")}</tbody></table></div>${guide("titv")}</div>
      <div class="grid g2" style="margin-top:18px">
        <div class="card"><div class="label">How many callers found each variant</div>
          ${many ? bars(o.samples, Object.fromEntries(o.callers.map((_, k) => [`${k + 1} caller${k ? "s" : ""}`, o.agree.map(a => a.by[k])])), { xlab: "Sample", label: "Variants by number of callers agreeing" })
            : `<p class="small muted">Only one caller ran, so there is nothing to compare. Add a second caller (the Tools setting) to see where they agree.</p>`}
          ${guide("callers", { open: true })}</div>
        <div class="card"><div class="label">Call quality (QUAL) by caller</div>
          ${bars(o.qual_hist.edges, Object.fromEntries(o.callers.map(c => [names(c), o.qual_hist.counts[c]])), { xlab: "QUAL", label: "Distribution of call quality" })}
          <div class="label" style="margin-top:12px">Read depth at calls, by sample</div>
          ${bars(o.dp_hist.edges.slice(0, -1).map((e, i) => i === o.dp_hist.edges.length - 2 ? `${e}+` : e), o.dp_hist.counts, { xlab: "Reads covering the variant", label: "Distribution of read depth" })}
          ${guide("quality")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:filter">Filter variants →</button></div>`;
  }

  // ---------------------------------------------------------------- filter and browse
  async function filter(el) {
    const o = await overview(), f = o.filters, names = c => o.caller_names[c] || c;
    const chosen = f.callers.length ? f.callers : o.callers;
    el.innerHTML = lede("Keep the calls you trust. Stricter filters remove false calls but also some real variants; the defaults suit 20–40× germline data.") +
      `<div class="card"><div class="grid g4">
          <div class="field"><span>Callers</span>${o.callers.map(c => `<label class="small"><input type="checkbox" class="cl" value="${esc(c)}" ${chosen.includes(c) ? "checked" : ""}> ${esc(names(c))}</label>`).join("<br>")}</div>
          <label class="field"><span>Called by at least</span><input type="number" id="agree" min="1" max="${o.callers.length}" value="${f.agree}"><small>of the chosen callers</small></label>
          <label class="field"><span>Variant type</span><select id="vtype">${[["all", "All"], ["snv", "SNVs only"], ["indel", "Indels only"]].map(([v, l]) => `<option value="${v}" ${f.vtype === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label class="field"><span>Region</span><input type="text" id="region" placeholder="all, or chr2:18000-24000" value="${esc(f.region)}"></label>
          <label class="field"><span>Minimum QUAL</span><input type="number" id="qual" min="0" step="5" value="${f.min_qual}"></label>
          <label class="field"><span>Minimum depth</span><input type="number" id="dp" min="0" value="${f.min_dp}"><small>reads in that sample</small></label>
          <label class="field"><span>Minimum GQ</span><input type="number" id="gq" min="0" max="99" value="${f.min_gq}"><small>genotype quality</small></label>
          <label class="field"><span>Caller's own filters</span><label class="small"><input type="checkbox" id="pass" ${f.pass_only ? "checked" : ""}> keep only calls that passed them</label></label></div>
        <div class="row"><button class="btn primary" id="go">Apply filters</button></div><div id="sum"></div>${guide("filters", { open: true })}</div>
      <div class="grid g-side" style="margin-top:18px"><div class="card"><div class="label" id="count">Variants</div><div id="table" style="max-height:560px;overflow:auto"></div>
          <div class="row" id="pager" style="margin-top:8px"></div></div>
        <div class="card"><div class="label">One variant</div><div id="one"><p class="small muted">Click a variant to see each caller's call in each sample.</p></div>${guide("genotypes")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:groups">Compare groups →</button></div>`;
    let offset = 0;
    const page = async () => {
      const r = await E.call("variants", { offset, n: 100 });
      $("#count", el).textContent = `${fmt(r.total)} variants kept`;
      $("#table", el).innerHTML = `<table><thead><tr><th>Position</th><th>Change</th><th class="num">QUAL</th><th>Callers</th>${r.samples.map(s => `<th title="${esc(o.groups[s] || "")}">${esc(s)}</th>`).join("")}</tr></thead><tbody>
        ${r.rows.map(v => `<tr class="click" tabindex="0" data-i="${v.i}"><td>${esc(v.chrom)}:${fmt(v.pos)}</td><td><code>${esc(v.ref.slice(0, 8))}${v.ref.length > 8 ? "…" : ""}→${esc(v.alt.slice(0, 8))}${v.alt.length > 8 ? "…" : ""}</code></td><td class="num">${v.qual}</td>
          <td>${v.callers.map(c => `<i class="dot" title="${esc(names(c))}" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${callerColour(c)};margin-right:2px"></i>`).join("")}</td>${v.gt.map(d => `<td>${gt(d)}</td>`).join("")}</tr>`).join("")}</tbody></table>
        ${legend(o.callers.map(c => [names(c), callerColour(c)]))}`;
      $("#pager", el).innerHTML = (offset > 0 ? `<button class="btn small" id="prev">← Previous 100</button>` : "") + (offset + 100 < r.total ? `<button class="btn small" id="next">Next 100 →</button>` : "");
      if ($("#prev", el)) $("#prev", el).onclick = () => { offset -= 100; page(); };
      if ($("#next", el)) $("#next", el).onclick = () => { offset += 100; page(); };
    };
    const one = async i => {
      const v = await E.call("variant", { i });
      $("#one", el).innerHTML = `<p><b>${esc(v.chrom)}:${fmt(v.pos)}</b> <code>${esc(v.ref)} → ${esc(v.alt)}</code> (${v.type === "snv" ? "single-nucleotide" : v.type === "indel" ? (v.alt.length > v.ref.length ? "insertion" : "deletion") : "other"})</p>
        <table><thead><tr><th>Caller</th><th>Sample</th><th>Genotype</th><th class="num">Ref reads</th><th class="num">Alt reads</th><th class="num">Depth</th><th class="num">GQ</th><th class="num">QUAL</th><th>Caller filter</th></tr></thead><tbody>
        ${v.calls.map(c => `<tr><td>${esc(names(c.caller))}</td><td>${esc(c.sample)}</td><td>${gt(c.dose)}</td><td class="num">${c.ref_reads >= 0 ? c.ref_reads : ""}</td><td class="num">${c.alt_reads >= 0 ? c.alt_reads : ""}</td><td class="num">${c.dp >= 0 ? c.dp : ""}</td><td class="num">${c.gq >= 0 ? c.gq : ""}</td><td class="num">${c.qual}</td><td>${c.passed ? "passed" : "failed"}</td></tr>`).join("")}</tbody></table>
        <p class="small muted">Samples not listed had no call at this position.</p>`;
    };
    el.addEventListener("click", e => { const r = e.target.closest("[data-i]"); if (r) one(Number(r.dataset.i)).catch(err => toast(err.message)); });
    el.addEventListener("keydown", e => { const r = e.target.closest("[data-i]"); if (r && e.key === "Enter") one(Number(r.dataset.i)).catch(err => toast(err.message)); });
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      const cl = [...el.querySelectorAll(".cl:checked")].map(x => x.value);
      const r = await E.call("apply_filters", { callers: cl.length === o.callers.length ? [] : cl, agree: Number($("#agree", el).value), min_qual: Number($("#qual", el).value),
        min_dp: Number($("#dp", el).value), min_gq: Number($("#gq", el).value), pass_only: $("#pass", el).checked, vtype: $("#vtype", el).value, region: $("#region", el).value });
      ov.filters = r.filters;
      $("#sum", el).innerHTML = `<p style="margin-top:12px"><b>${fmt(r.kept)}</b> of ${fmt(r.total)} variants kept: ${fmt(r.snv)} SNVs, ${fmt(r.indel)} indels${r.titv ? `, Ti/Tv ${r.titv}` : ""}.</p>
        <table><thead><tr><th>Sample</th><th class="num">One copy (het)</th><th class="num">Two copies (hom)</th><th class="num">Uncertain</th></tr></thead><tbody>
        ${r.per_sample.map(p => `<tr><td>${esc(p.sample)}</td><td class="num">${fmt(p.het)}</td><td class="num">${fmt(p.hom)}</td><td class="num">${fmt(p.uncertain)}</td></tr>`).join("")}</tbody></table>`;
      offset = 0; await page(); toast("Filters applied.", true);
    });
    await page();
  }

  // ---------------------------------------------------------------- groups
  async function groups(el) {
    const o = await overview(), gs = [...new Set(Object.values(o.groups).filter(Boolean))];
    if (gs.length < 2) {
      el.innerHTML = lede("Find variants that separate two groups of samples.") + `<div class="notice">Your samples table has ${gs.length ? "only one group" : "no groups"}. Give the samples a Group (for example mutant and wildtype) in the samples table to compare them.</div>${guide("groups")}`;
      return;
    }
    el.innerHTML = lede("Find variants every sample of one group carries and no sample of the other does: how a mutation, and the DNA linked to it, shows up.") +
      `<div class="card"><div class="grid g3">
          <label class="field"><span>Group</span><select id="a">${gs.map((g, i) => `<option ${i === gs.length - 1 ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></label>
          <label class="field"><span>Against</span><select id="b">${gs.map((g, i) => `<option ${i === 0 ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></label></div>
        <div class="row"><button class="btn primary" id="go">Compare</button></div><p class="small muted">Uses the filters from the previous step.</p></div><div id="out"></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      const r = await E.call("groups", { a: $("#a", el).value, b: $("#b", el).value });
      const C = COL(), w = 560, h = 150, L = 36, B = 28;
      const charts = r.windows.map(win => {
        const n = win.all.length, bw = (w - L - 10) / n, max = Math.max(1, ...win.separating);
        let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Separating variants along ${esc(win.chrom)}"><line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${C.muted}"/>`;
        win.separating.forEach((v, i) => { const y = 10 + (1 - v / max) * (h - B - 10);
          s += `<rect x="${L + i * bw}" y="${y}" width="${bw - 1}" height="${h - B - y}" fill="${C.ox}"><title>${esc(win.chrom)}:${fmt(i * win.size)}–${fmt((i + 1) * win.size)}: ${v} of ${win.all[i]} variants separate the groups</title></rect>`; });
        s += `<text x="${L - 6}" y="18" text-anchor="end" class="ax">${max}</text><text x="${L}" y="${h - 8}" class="ax">${esc(win.chrom)}: 0</text><text x="${w - 10}" y="${h - 8}" text-anchor="end" class="ax">${fmt(win.all.length * win.size)} bp</text></svg>`;
        return s;
      }).join("");
      $("#out", el).innerHTML = `<div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">${fmt(r.separating)} variants separate ${esc(r.a)} from ${esc(r.b)}</div>
          <p class="small">${fmt(r.carried_by_a)} carried by every ${esc(r.a)} sample, ${fmt(r.carried_by_b)} by every ${esc(r.b)} sample, out of ${fmt(r.kept)} kept variants.</p>${charts}
          <p class="small muted">Bars count separating variants in each window along the chromosome. A tall cluster points to a region linked to what differs between the groups.</p>${guide("groups", { open: true })}</div>
        <div class="card"><div class="label">The separating variants</div><div id="list" style="max-height:520px;overflow:auto"></div></div></div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
      const v = await E.call("variants", { only: "separating", n: 500 });
      $("#list", el).innerHTML = `<table><thead><tr><th>Position</th><th>Change</th>${v.samples.map(s => `<th>${esc(s)}<br><span class="small muted">${esc(o.groups[s] || "")}</span></th>`).join("")}</tr></thead><tbody>
        ${v.rows.map(x => `<tr><td>${esc(x.chrom)}:${fmt(x.pos)}</td><td><code>${esc(x.ref.slice(0, 8))}→${esc(x.alt.slice(0, 8))}</code></td>${x.gt.map(d => `<td>${gt(d)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      toast("Groups compared.", true);
    });
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    el.innerHTML = lede("Save the filtered variants. Everything goes in the run's results folder.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>variants_filtered.vcf</b>: the kept variants with each sample's genotype and which callers found them; the filters are written in its header.</li>
        <li><b>variants_filtered.csv</b>: the same as a table, for a spreadsheet.</li>
        <li><b>separating_&lt;group&gt;_vs_&lt;group&gt;.csv</b>: the variants that separate two groups (after Compare groups).</li></ul>
        <p class="small muted">The callers' own VCFs, with every annotation, stay in <code>results/variant_calling/</code>.</p>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Variants saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("dna.variants", { report, overview: overviewView, filter, groups, export: exportView });
})();
