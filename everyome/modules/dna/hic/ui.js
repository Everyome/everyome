/* Views for Hi-C: pipeline report, library checks and distance decay, contact maps, compartments, TAD boundaries, export.
   Uses only Everyome's shared helpers, so every chart follows the active theme. Maps are drawn on a canvas (up to
   400 × 400 bins), coloured from the theme's background to its accent. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, esc, fmt, toast, guarded, followTask, barChart, logLine, guide, legend, lede, filesTable } = H;
  const COL = () => H.COL(), PAL = () => H.PALETTE();
  let st = null, ov = null;
  const V = { sample: null, chrom: null, start: 0, end: null, res: "", balanced: true };
  const refresh = async () => (st = await E.status());
  // Intent: the overview is read once per session (it lists samples, resolutions and chromosomes).
  const overview = async () => (ov && ov.run === st.run ? ov : (ov = { ...(await E.call("overview")), run: st.run }));
  const kb = bp => bp >= 1e6 ? `${+(bp / 1e6).toFixed(2)} Mb` : `${+(bp / 1e3).toFixed(1)} kb`;
  const opts = (items, sel) => items.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(sel) ? "selected" : ""}>${esc(t)}</option>`).join("");
  const pct = v => v == null ? "–" : `${v}%`;
  const flag = (v, bad) => v != null && bad(v) ? ` class="warn"` : "";

  // ---------------------------------------------------------------- pipeline report (Run page)
  async function report(el, q) {
    const state = E.state();
    el.innerHTML = `<h2>What the pipeline made</h2>
      <div class="grid g2"><div class="card"><div class="label">Read pairs per sample</div>
        ${q.samples.some(s => s.pairs) ? `<table><thead><tr><th>Sample</th><th class="num">Read pairs</th><th class="num">Valid</th><th class="num">Duplicates</th><th class="num">Within chromosomes</th></tr></thead><tbody>
          ${q.samples.map(s => `<tr><td>${esc(s.sample)}</td><td class="num">${fmt(s.pairs)}</td><td class="num">${pct(s.valid_pct)}</td><td class="num">${pct(s.duplicates_pct)}</td><td class="num">${pct(s.cis_pct)}</td></tr>`).join("")}</tbody></table>
          ${barChart(q.samples.map(s => [s.sample, s.unique || 0]), { label: v => (v / 1e6).toFixed(2) + " M", title: "Valid pairs without duplicates" })}`
          : `<div class="notice warn">No HiC-Pro statistics were found. Check the pipeline log.</div>`}</div>
      <div class="card"><div class="label">Maps and quality report</div>
        ${q.maps.length ? `<p class="small">${q.maps.length} contact map files in <code>results/contact_maps/cool</code>${q.compartments ? ", with compartments" : ""}${q.tads ? " and TADs" : ""}.</p>`
          : `<div class="notice warn">No contact maps were found; the live session needs them.</div>`}
        ${q.multiqc ? `<a class="btn primary small" href="/api/run/file?path=${encodeURIComponent(q.multiqc)}" target="_blank" rel="noopener">Open the MultiQC report</a>` : `<p class="small muted">No MultiQC report found.</p>`}
        ${state.demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster the MultiQC report is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  // ---------------------------------------------------------------- check libraries
  async function qc(el) {
    await refresh(); const o = await overview();
    el.innerHTML = lede("First, check each library: how many read pairs were valid ligation products, and how contacts fall with distance.") +
      `<div class="card"><div class="label">Libraries</div><table><thead><tr><th>Sample</th><th class="num">Read pairs</th><th class="num">Aligned pairs</th><th class="num">Valid pairs</th>
        <th class="num">Duplicates</th><th class="num">Within chromosomes</th><th class="num">Of those, over 20 kb</th><th class="num">Unique valid pairs</th></tr></thead><tbody>
        ${o.stats.map(s => `<tr><td>${esc(s.sample)}</td><td class="num">${fmt(s.pairs)}</td><td class="num">${pct(s.aligned_pct)}</td><td class="num"${flag(s.valid_pct, v => v < 25)}>${pct(s.valid_pct)}</td>
          <td class="num"${flag(s.duplicates_pct, v => v > 30)}>${pct(s.duplicates_pct)}</td><td class="num"${flag(s.cis_pct, v => v < 60)}>${pct(s.cis_pct)}</td>
          <td class="num"${flag(s.long_pct, v => v < 30)}>${pct(s.long_pct)}</td><td class="num">${fmt(s.unique)}</td></tr>`).join("")}</tbody></table>
        <p class="small muted" style="margin-top:8px">Maps at ${o.resolutions.map(kb).join(", ")} on ${o.chroms.length} sequences. Values in red are worth a look (see below).</p>${guide("library", { open: true })}</div>
      <div class="card" style="margin-top:18px"><div class="label">Contacts against distance</div>
        <div class="row"><label class="field"><span>Map resolution</span><select id="dres">${opts(o.resolutions.map(r => [r, kb(r)]), o.suggest.decay)}</select></label></div>
        <div id="decay"></div>${guide("decay")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:map">Look at the maps →</button></div>`;
    const draw = async () => {
      const d = await E.call("decay", { res: Number($("#dres", el).value) });
      $("#decay", el).innerHTML = logLine(d.curves, { xlab: "Distance (bp)", ylab: "Contact probability" }) +
        `<p class="small">Slope between ${kb(d.range[0])} and ${kb(d.range[1])}: ${Object.entries(d.slopes).map(([s, v]) => `<b>${esc(s)}</b> ${v ?? "–"}`).join(", ")}.</p>`;
    };
    $("#dres", el).onchange = () => draw().catch(e => toast(e.message));
    await draw();
  }

  // ---------------------------------------------------------------- contact maps
  // Draw a map onto a canvas: log10 values from lo (background) to hi (accent); grey where a bin is masked.
  function drawMap(canvas, m, { marks = [] } = {}) {
    const n = m.values.length, size = canvas.width, px = size / n, ctx = canvas.getContext("2d"), c = COL();
    const a = H.hexRgb(c.parch), b = H.hexRgb(c.ox), mask = H.hexRgb(c.rule || c.muted);
    ctx.clearRect(0, 0, size, size);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const v = m.values[i][j];
      let rgb = mask;
      if (v != null) { const t = Math.max(0, Math.min(1, (v - m.lo) / ((m.hi - m.lo) || 1))); rgb = a.map((x, k) => Math.round(x + (b[k] - x) * t)); }
      else if (m.values[i].some(x => x != null) && m.values.some(r => r[j] != null)) rgb = a;      // a zero, not a masked bin
      ctx.fillStyle = `rgb(${rgb})`; ctx.fillRect(j * px, i * px, Math.ceil(px), Math.ceil(px));
    }
    // Intent: a TAD boundary is where one triangle along the diagonal ends and the next begins; mark it there.
    ctx.strokeStyle = c.ink; ctx.lineWidth = 1.5;
    marks.forEach(p => { const k = (p - m.start) / m.res * px; ctx.beginPath(); ctx.moveTo(k - 6, k + 6); ctx.lineTo(k + 6, k - 6); ctx.stroke(); });
  }

  async function map(el) {
    await refresh(); const o = await overview();
    V.sample = V.sample || o.samples[0]; V.chrom = V.chrom || o.chroms[0].name;
    const len = () => o.chroms.find(c => c.name === V.chrom).length;
    if (V.end == null) V.end = len();
    el.innerHTML = lede("Each square is a pair of places on the chromosome; the darker it is, the more often they touched. The diagonal is each place with itself.") +
      `<div class="card"><div class="grid g3">
          <label class="field"><span>Sample</span><select id="s">${opts(o.samples.map(s => [s, s]), V.sample)}</select></label>
          <label class="field"><span>Chromosome</span><select id="c">${opts(o.chroms.map(c => [c.name, `${c.name} (${kb(c.length)})`]), V.chrom)}</select></label>
          <label class="field"><span>Resolution</span><select id="r"><option value="">Automatic</option>${opts(o.resolutions.map(r => [r, kb(r)]), V.res)}</select></label>
          <label class="field"><span>From (kb)</span><input type="number" id="a" min="0" step="10" value="${V.start / 1000}"></label>
          <label class="field"><span>To (kb)</span><input type="number" id="b" min="0" step="10" value="${V.end / 1000}"></label>
          <label class="field"><span>Balanced</span><select id="bal"><option value="1" ${V.balanced ? "selected" : ""}>Yes (recommended)</option><option value="0" ${V.balanced ? "" : "selected"}>No: raw counts</option></select></label></div>
        <div class="row"><button class="btn primary" id="show">Show</button><button class="btn" id="zin">Zoom in</button><button class="btn" id="zout">Zoom out</button>
          <button class="btn" id="left">←</button><button class="btn" id="right">→</button></div></div>
      <div class="grid g-side" style="margin-top:18px"><div class="card"><canvas id="cv" width="520" height="520" style="width:100%;max-width:520px;aspect-ratio:1" role="img" aria-label="Contact map"></canvas>
          <p class="small muted" id="cap"></p></div>
        <div class="card">${guide("contact_map", { open: true })}${guide("balancing")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:compartments">Compartments →</button></div>`;
    const read = () => { V.sample = $("#s", el).value; V.chrom = $("#c", el).value; V.res = $("#r", el).value;
      V.start = Math.max(0, Number($("#a", el).value) * 1000); V.end = Math.min(len(), Number($("#b", el).value) * 1000); V.balanced = $("#bal", el).value === "1"; };
    const show = async () => {
      const m = await E.call("contact_map", { sample: V.sample, chrom: V.chrom, start: V.start, end: V.end, res: V.res ? Number(V.res) : null, balanced: V.balanced });
      drawMap($("#cv", el), m, { marks: m.boundaries || [] });
      $("#a", el).value = m.start / 1000; $("#b", el).value = m.end / 1000;
      $("#cap", el).textContent = `${m.sample}, ${m.chrom}:${kb(m.start)}–${kb(m.end)} at ${kb(m.res)} bins (${m.values.length} × ${m.values.length}), ${m.balanced ? "balanced" : "raw counts"}, log scale.` +
        (m.boundaries?.length ? ` Crosses mark the TAD boundaries found in step 4.` : "");
    };
    const move = f => guarded(null, async () => { read(); const w = V.end - V.start, mid = (V.start + V.end) / 2; f(w, mid); V.start = Math.max(0, Math.round(V.start)); V.end = Math.min(len(), Math.round(V.end));
      $("#a", el).value = V.start / 1000; $("#b", el).value = V.end / 1000; V.res = ""; $("#r", el).value = ""; await show(); });
    $("#show", el).onclick = e => guarded(e.currentTarget, async () => { read(); await show(); });
    $("#c", el).onchange = () => { V.chrom = $("#c", el).value; V.start = 0; V.end = len(); $("#a", el).value = 0; $("#b", el).value = V.end / 1000; };
    $("#zin", el).onclick = () => move((w, mid) => { V.start = mid - w / 4; V.end = mid + w / 4; });
    $("#zout", el).onclick = () => move((w, mid) => { V.start = mid - w; V.end = mid + w; });
    $("#left", el).onclick = () => move(w => { const s = Math.min(V.start, w / 2); V.start -= s; V.end -= s; });
    $("#right", el).onclick = () => move(w => { const s = Math.min(len() - V.end, w / 2); V.start += s; V.end += s; });
    await show().catch(e => toast(e.message));
  }

  // ---------------------------------------------------------------- compartments
  function track(values, res, length, { h = 70, w = 620, label = "" } = {}) {
    const c = COL(), mx = Math.max(0.01, ...values.filter(v => v != null).map(Math.abs)), mid = h / 2, bw = w / values.length;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h + 16}" role="img" aria-label="${esc(label)}"><line x1="0" x2="${w}" y1="${mid}" y2="${mid}" stroke="${c.muted}"/>`;
    values.forEach((v, i) => { if (v == null) return; const y = v > 0 ? mid - v / mx * (mid - 2) : mid;
      s += `<rect x="${(i * bw).toFixed(2)}" y="${y.toFixed(1)}" width="${Math.max(0.6, bw - 0.3).toFixed(2)}" height="${(Math.abs(v) / mx * (mid - 2)).toFixed(1)}" fill="${v > 0 ? c.ox : (c.plum || c.ink)}"><title>${kb(i * res)}: ${v}</title></rect>`; });
    return s + `<text x="0" y="${h + 13}" class="ax">0</text><text x="${w}" y="${h + 13}" text-anchor="end" class="ax">${kb(length)}</text></svg>`;
  }

  async function compartments(el) {
    await refresh(); const o = await overview(); const prev = st.compartments;
    el.innerHTML = lede("Along each chromosome, stretches of open, active DNA (A) contact each other, and so do closed stretches (B). The first eigenvector of the map shows which is which.") +
      `<div class="card"><div class="row" style="align-items:flex-end">
        <label class="field"><span>Resolution</span><select id="r">${opts(o.resolutions.map(r => [r, kb(r) + (o.compartment_files.includes(r) ? " (from the pipeline)" : "")]), prev?.res || o.suggest.compartments)}</select></label>
        <button class="btn primary" id="go">${prev ? "Find again" : "Find compartments"}</button></div><div id="prog"></div>
        ${o.fasta ? "" : `<div class="notice warn">The genome FASTA can't be read from the session, so the sign of each chromosome (which side is A) can't be set from GC content.</div>`}</div>
      <div id="out"></div>`;
    const draw = async () => {
      const t = await E.call("compartment_track"), chroms = o.chroms.filter(c => o.samples.some(s => t.samples[s]?.[c.name]));
      const ch = $("#ch", el)?.value || chroms[0]?.name, len = o.chroms.find(c => c.name === ch).length;
      $("#out", el).innerHTML = `<div class="card" style="margin-top:18px"><div class="row" style="align-items:flex-end"><label class="field"><span>Chromosome</span><select id="ch">${opts(chroms.map(c => [c.name, c.name]), ch)}</select></label></div>
        ${o.samples.map(s => `<div class="label" style="margin-top:10px">${esc(s)}</div>${track(t.samples[s]?.[ch] || [], t.res, len, { label: `Compartments of ${s} on ${ch}` })}`).join("")}
        ${legend([["A: open, GC-rich (positive)", COL().ox], ["B: closed (negative)", COL().plum || COL().ink]])}
        <p class="small muted">At ${kb(t.res)}; ${t.source === "pipeline" ? "eigenvectors from the pipeline (cooltools)" : "eigenvectors computed in the session"}; ${t.oriented === "gc" ? "sign set from the genome's GC content" : "sign as computed (not oriented)"}.
          A share of bins: ${Object.entries(t.a_share).map(([s, v]) => `${esc(s)} ${v ?? "–"}%`).join(", ")}.
          ${Object.entries(t.flipped || {}).filter(([, f]) => f.length).map(([s, f]) => `For ${esc(s)}, the sign was flipped on ${f.map(esc).join(", ")} to match GC content.`).join(" ")}</p>
        ${guide("compartments", { open: true })}</div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:tads">TAD boundaries →</button></div>`;
      $("#ch", el).onchange = () => draw().catch(e => toast(e.message));
    };
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("compartments", { res: Number($("#r", el).value) }); await followTask($("#prog", el)); await refresh(); await draw();
      $("#go", el).textContent = "Find again"; toast("Compartments found.", true);
    });
    if (prev) await draw();
  }

  // ---------------------------------------------------------------- TADs
  function insulationPlot(t, length) {
    const c = COL(), w = 620, h = 170, L = 40, B = 24, v = t.score.filter(x => x != null);
    if (!v.length) return `<p class="small muted">This chromosome is too short for the window.</p>`;
    const lo = Math.min(...v), hi = Math.max(...v), X = i => L + i / t.score.length * (w - L - 6), Y = y => 8 + (hi - y) / ((hi - lo) || 1) * (h - B - 8);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Insulation score along ${esc(t.chrom)}">`, path = "";
    t.score.forEach((y, i) => { if (y != null) path += `${path && t.score[i - 1] != null ? "L" : "M"}${X(i + .5).toFixed(1)},${Y(y).toFixed(1)}`; });
    s += `<path d="${path}" fill="none" stroke="${c.golddk}" stroke-width="1.6"/>`;
    t.boundaries.forEach(b => { const x = X(b.pos / t.res); s += `<line x1="${x}" x2="${x}" y1="8" y2="${h - B}" stroke="${c.ox}" stroke-width="1.2"><title>Boundary at ${kb(b.pos)} (strength ${b.strength})</title></line>`; });
    t.hicexplorer.forEach(p => { const x = X(p / t.res); s += `<path d="M${x - 4},${h - B + 9} L${x + 4},${h - B + 9} L${x},${h - B + 2} Z" fill="${c.ink}"><title>HiCExplorer boundary at ${kb(p)}</title></path>`; });
    return s + `<text x="${L - 4}" y="${Y(hi) + 4}" text-anchor="end" class="ax">${hi.toFixed(1)}</text><text x="${L - 4}" y="${Y(lo) + 4}" text-anchor="end" class="ax">${lo.toFixed(1)}</text>
      <text x="${L}" y="${h - 2}" class="ax">0</text><text x="${w - 6}" y="${h - 2}" text-anchor="end" class="ax">${kb(length)}</text></svg>`;
  }

  async function tads(el) {
    await refresh(); const o = await overview(); const prev = st.tads;
    el.innerHTML = lede("Topologically associating domains (TADs) are stretches that contact themselves more than their neighbours. Their edges show as dips in the insulation score.") +
      `<div class="card"><div class="grid g3">
          <label class="field"><span>Resolution</span><select id="r">${opts(o.resolutions.map(r => [r, kb(r)]), prev?.res || o.suggest.tads)}</select></label>
          <label class="field"><span>Window (bins)</span><input type="number" id="w" min="2" max="50" value="${prev?.window || 5}"><small>About the size of the smallest domains you expect.</small></label>
          <label class="field"><span>Minimum boundary strength</span><input type="number" id="m" min="0" step="0.05" value="${prev?.min_strength ?? 0.2}"><small>How deep a dip must be (log2).</small></label></div>
        <div class="row"><button class="btn primary" id="go">${prev ? "Find again" : "Find boundaries"}</button></div><div id="prog"></div></div>
      <div id="out"></div>`;
    const draw = async () => {
      await refresh(); const T = st.tads;
      const s = $("#ts", el)?.value || o.samples[0], ch = $("#tc", el)?.value || o.chroms[0].name, len = o.chroms.find(c => c.name === ch).length;
      const t = await E.call("tad_track", { sample: s, chrom: ch });
      const end = Math.min(len, T.res * 300);
      $("#out", el).innerHTML = `<div class="card" style="margin-top:18px"><table><thead><tr><th>Sample</th><th class="num">Boundaries</th><th class="num">Median domain</th><th class="num">HiCExplorer boundaries matched</th></tr></thead><tbody>
          ${o.samples.map(x => `<tr><td>${esc(x)}</td><td class="num">${fmt(T.boundaries[x])}</td><td class="num">${T.median_size[x] ? kb(T.median_size[x]) : "–"}</td><td class="num">${pct(T.hicexplorer_agree[x])}</td></tr>`).join("")}</tbody></table>
          <div class="row" style="margin-top:12px;align-items:flex-end"><label class="field"><span>Sample</span><select id="ts">${opts(o.samples.map(x => [x, x]), s)}</select></label>
            <label class="field"><span>Chromosome</span><select id="tc">${opts(o.chroms.map(c => [c.name, c.name]), ch)}</select></label></div>
          <div class="label" style="margin-top:8px">Insulation score along ${esc(ch)}</div>${insulationPlot(t, len)}
          ${legend([["insulation score", COL().golddk], ["boundary found here", COL().ox], ["HiCExplorer's boundary (▲)", COL().ink]])}${guide("insulation", { open: true })}</div>
        <div class="card" style="margin-top:18px"><div class="label">${esc(ch)}: ${kb(0)}–${kb(end)} with the boundaries</div>
          <canvas id="cv" width="460" height="460" style="width:100%;max-width:460px;aspect-ratio:1" role="img" aria-label="Contact map with TAD boundaries"></canvas></div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
      const m = await E.call("contact_map", { sample: s, chrom: ch, start: 0, end, res: T.res });
      drawMap($("#cv", el), m, { marks: m.boundaries || [] });
      $("#ts", el).onchange = $("#tc", el).onchange = () => draw().catch(e => toast(e.message));
    };
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("tads", { res: Number($("#r", el).value), window: Number($("#w", el).value), min_strength: Number($("#m", el).value) });
      await followTask($("#prog", el)); await draw(); $("#go", el).textContent = "Find again"; toast("Boundaries found.", true);
    });
    if (prev) await draw();
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    await refresh();
    el.innerHTML = lede("Save the tracks for a genome browser (IGV, HiGlass) or your own analysis. Everything goes in the run's results folder; the balanced .mcool maps are already in results/contact_maps/cool.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>libraries.csv</b>: read pairs, valid pairs, duplicates and cis share for each sample.</li>
        <li><b>distance_decay.csv</b>: contact probability against distance for each sample.</li>
        <li><b>&lt;sample&gt;_compartments_&lt;res&gt;.bedgraph</b>: the eigenvector (positive = A)${st.compartments ? "" : " (after step 3)"}.</li>
        <li><b>&lt;sample&gt;_tad_boundaries_&lt;res&gt;.bed</b> and <b>_tads_&lt;res&gt;.bed</b>: boundaries with their strength, and the domains between them${st.tads ? "" : " (after step 4)"}.</li></ul>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Files saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("dna.hic", { report, qc, map, compartments, tads, export: exportView });
})();
