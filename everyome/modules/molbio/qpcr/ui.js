/* Views for qPCR analysis: the plate and its replicates, primer efficiency, reference genes and groups, fold changes,
   export. Charts are drawn in SVG with the active theme's colours. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, toast, guarded, guide, lede, legend, filesTable, barChart } = H;
  const COL = () => H.COL();
  const mix = (a, b, t) => { const x = H.hexRgb(a), y = H.hexRgb(b); return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * Math.max(0, Math.min(1, t))))})`; };

  // ---------------------------------------------------------------- the plate
  function plateSvg(p) {
    const C = COL(), rows = "ABCDEFGHIJKLMNOP".slice(0, p.size === 384 ? 16 : 8).split(""), cols = p.size === 384 ? 24 : 12;
    const cell = p.size === 384 ? 22 : 40, L = 22, T = 18, w = L + cols * cell + 4, h = T + rows.length * cell + 4;
    const byWell = Object.fromEntries(p.wells.map(x => [x.well, x]));
    const cqs = p.wells.filter(x => x.cq != null && x.task !== "ntc").map(x => x.cq), lo = Math.min(...cqs), hi = Math.max(...cqs);
    let s = `<svg class="chart" style="max-width:${w}px" viewBox="0 0 ${w} ${h}" role="img" aria-label="The plate, each well coloured by its Cq">`;
    for (let c = 1; c <= cols; c++) s += `<text x="${L + (c - 0.5) * cell}" y="${T - 5}" text-anchor="middle" class="ax">${c}</text>`;
    rows.forEach((r, i) => {
      s += `<text x="${L - 6}" y="${T + (i + 0.5) * cell + 4}" text-anchor="end" class="ax">${r}</text>`;
      for (let c = 1; c <= cols; c++) {
        const x = byWell[r + c], cx = L + (c - 0.5) * cell, cy = T + (i + 0.5) * cell, rad = cell * 0.42;
        if (!x) { s += `<circle cx="${cx}" cy="${cy}" r="${rad}" fill="none" stroke="${C.muted}" stroke-opacity="0.3"/>`; continue; }
        // Intent: early Cq (more template) is darker; wells with no Cq are left open; left-out wells are crossed.
        const fill = x.cq == null ? "none" : mix(C.parch, C.ox, (hi - x.cq) / ((hi - lo) || 1));
        const ring = x.task === "ntc" ? C.ink : x.task === "standard" ? C.gold : C.muted;
        s += `<circle cx="${cx}" cy="${cy}" r="${rad}" fill="${fill}" stroke="${ring}" stroke-width="${x.task === "unknown" ? 1 : 2}" data-w="${esc(x.well)}" style="cursor:pointer">
          <title>${esc(x.well)} · ${esc(x.sample)} · ${esc(x.target)} · ${x.cq == null ? "no Cq" : "Cq " + x.cq}${x.excluded ? " · left out" : ""} (click to ${x.excluded ? "put back" : "leave out"})</title></circle>`;
        if (x.excluded) s += `<path d="M${cx - rad * 0.7} ${cy - rad * 0.7}L${cx + rad * 0.7} ${cy + rad * 0.7}M${cx + rad * 0.7} ${cy - rad * 0.7}L${cx - rad * 0.7} ${cy + rad * 0.7}" stroke="${C.ink}" stroke-width="2" pointer-events="none"/>`;
      }
    });
    return s + "</svg>";
  }

  async function plate(el) {
    const [o, p] = await Promise.all([E.call("overview"), E.call("plate")]);
    const C = COL(), bad = p.ntc.filter(n => n.verdict !== "clean");
    el.innerHTML = lede(`${fmt(o.wells)} wells from <b>${esc(o.file)}</b>: ${o.targets.length} targets in ${o.samples.length} samples, ${o.standards} standard wells and ${o.ntc} no-template controls. First, check the replicates and controls.`) +
      `<div class="card"><div class="label">The plate</div><div style="overflow:auto" id="pl">${plateSvg(p)}</div>
        ${legend([["early Cq (more template)", C.ox], ["late Cq", C.parch], ["standard (gold ring)", C.gold], ["no-template control (dark ring)", C.ink]])}
        <p class="small muted">Click a well to leave it out of the analysis, or to put it back. ${guide("plate")}</p></div>
      <div class="grid g-side" style="margin-top:18px"><div class="card"><div class="label">Technical replicates</div><div id="reps"></div>${guide("replicates", { open: true })}</div>
        <div class="card"><div class="label">No-template controls</div>
          <table><thead><tr><th>Well</th><th>Target</th><th class="num">Cq</th><th>Verdict</th></tr></thead><tbody>
          ${p.ntc.map(n => `<tr><td>${esc(n.well)}</td><td>${esc(n.target)}</td><td class="num">${n.cq ?? "—"}</td><td class="${n.verdict === "contaminated" ? "warnv" : ""}">${esc(n.verdict)}</td></tr>`).join("")}</tbody></table>
          ${bad.length ? `<p class="small">${bad.length} control${bad.length > 1 ? "s" : ""} gave a signal; see the guide below before going on.</p>` : `<p class="small">All controls are clean.</p>`}${guide("ntc")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:efficiency">Primer efficiency →</button></div>`;
    const reps = q => {
      const flagged = q.replicates.filter(r => r.flag || r.missing);
      $("#reps", el).innerHTML = `<p class="small">${q.replicates.length} replicate sets; ${q.flagged} spread more than ${q.replicate_sd} cycles${flagged.some(r => r.missing) ? ", and some wells gave no Cq" : ""}.</p>` +
        (flagged.length ? `<table><thead><tr><th>Sample</th><th>Target</th><th>Cq of each well</th><th class="num">SD</th><th></th></tr></thead><tbody>
          ${flagged.map(r => `<tr><td>${esc(r.sample)}</td><td>${esc(r.target)}</td><td class="small mono">${r.wells.map((w, i) => `${esc(w)}: ${r.cq[i] ?? "no Cq"}`).join(", ")}</td>
            <td class="num ${r.flag ? "warnv" : ""}">${r.sd ?? "—"}</td><td>${r.suggest ? `<button class="btn small" data-out="${esc(r.suggest)}">Leave out ${esc(r.suggest)}</button>` : ""}</td></tr>`).join("")}</tbody></table>`
          : `<p class="small muted">No replicate set needs a look.</p>`);
    };
    reps(p);
    let cur = p;                                                        // Intent: the latest plate, so a click knows a well's state
    const toggle = async (well, include) => {
      await E.call("exclude", { wells: [well], include });
      cur = await E.call("plate"); $("#pl", el).innerHTML = plateSvg(cur); reps(cur);
      toast(include ? `${well} is back in.` : `${well} left out.`, true);
    };
    el.addEventListener("click", e => {
      const b = e.target.closest("[data-out]");
      if (b) return guarded(b, () => toggle(b.dataset.out, false));
      const c = e.target.closest("[data-w]");
      if (c) toggle(c.dataset.w, !!cur.wells.find(x => x.well === c.dataset.w)?.excluded).catch(err => toast(err.message));
    });
  }

  // ---------------------------------------------------------------- efficiency
  function curve(t) {
    const C = COL(), w = 260, h = 170, L = 36, B = 28, T = 8, R = 8, pts = t.points_xy || [];
    if (!pts.length) return `<p class="small muted">No standard curve on this plate; ${Math.round(t.efficiency * 100)}% is assumed.</p>`;
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), x0 = Math.min(...xs) - 0.1, x1 = Math.max(...xs) + 0.1, y0 = Math.min(...ys) - 0.5, y1 = Math.max(...ys) + 0.5;
    const X = v => L + (v - x0) / (x1 - x0) * (w - L - R), Y = v => T + (y1 - v) / (y1 - y0) * (h - B - T);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Standard curve for ${esc(t.target)}">
      <line x1="${L}" x2="${w - R}" y1="${h - B}" y2="${h - B}" stroke="${C.muted}"/><line x1="${L}" x2="${L}" y1="${T}" y2="${h - B}" stroke="${C.muted}"/>
      <line x1="${X(x0)}" y1="${Y(t.intercept + t.slope * x0)}" x2="${X(x1)}" y2="${Y(t.intercept + t.slope * x1)}" stroke="${C.ox}" stroke-width="1.5"/>`;
    pts.forEach(p => s += `<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="3" fill="${C.golddk}"><title>log10 quantity ${p[0]}, Cq ${p[1]}</title></circle>`);
    return s + `<text x="${(w + L) / 2}" y="${h - 6}" text-anchor="middle" class="ax">log10 quantity</text><text x="10" y="${h / 2}" transform="rotate(-90 10 ${h / 2})" text-anchor="middle" class="ax">Cq</text>
      <text x="${w - R}" y="${T + 10}" text-anchor="end" class="ax">${esc(t.target)} · ${(t.efficiency * 100).toFixed(1)}%</text></svg>`;
  }

  async function efficiency(el) {
    const r = await E.call("efficiencies");
    const pct = v => v == null ? "—" : `${(v * 100).toFixed(1)}%`;
    el.innerHTML = lede(r.method === "delta_delta_cq" ? `This run uses 2<sup>−ΔΔCq</sup>, so every primer pair is taken to be ${pct(r.assumed)} efficient. The standard curves below show how close that is.`
        : "Each primer pair's efficiency, from its standard curve. A perfect pair doubles its product every cycle (100%).") +
      `<div class="card"><table><thead><tr><th>Target</th><th class="num">Dilutions</th><th class="num">Slope</th><th class="num">R²</th><th class="num">Measured</th><th class="num">Used</th></tr></thead><tbody>
        ${r.targets.map(t => { const off = t.measured != null && (t.measured < 0.9 || t.measured > 1.1);
          return `<tr><td>${esc(t.target)}</td><td class="num">${t.dilutions}</td><td class="num">${t.slope ?? "—"}</td><td class="num ${t.r2 != null && t.r2 < 0.98 ? "warnv" : ""}">${t.r2 ?? "—"}</td>
            <td class="num ${off ? "warnv" : ""}">${pct(t.measured)}</td><td class="num">${pct(t.efficiency)}<span class="small muted"> (${esc(t.source)})</span></td></tr>`; }).join("")}</tbody></table>${guide("efficiency", { open: true })}</div>
      <div class="grid g3" style="margin-top:18px">${r.targets.map(t => `<div class="card">${curve(t)}</div>`).join("")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:references">Reference genes and groups →</button></div>`;
  }

  // ---------------------------------------------------------------- reference genes and groups
  async function references(el) {
    const [r, o] = await Promise.all([E.call("references"), E.call("overview")]);
    const groups = [...new Set(Object.values(r.groups))];
    el.innerHTML = lede("Normalise to genes that stay steady across your samples. geNorm ranks every target: the lower its M, the steadier it is against the others.") +
      `<div class="grid g2"><div class="card"><div class="label">How steady each gene is (geNorm M)</div>
          ${r.genes.length ? barChart(r.genes.map(g => [g.target, g.m]), { label: v => v.toFixed(2), title: "geNorm M, steadiest first", colors: r.genes.map(g => g.chosen ? COL().ox : COL().golddk) }) : `<p class="small muted">Needs at least two targets measured in every sample.</p>`}
          ${r.genes.length ? legend([["chosen as a reference", COL().ox], ["not chosen", COL().golddk]]) : ""}
          <div class="chips" style="margin-top:10px">${o.targets.map(t => `<button class="chip" data-ref="${esc(t)}" aria-pressed="${r.chosen.includes(t)}">${esc(t)}</button>`).join("")}</div>
          <div class="row" style="margin-top:10px"><button class="btn primary" id="saveRefs">Use these reference genes</button>
            <span class="small muted" id="cm">${r.chosen_m != null ? `M of the chosen set: ${r.chosen_m}` : ""}</span></div>${guide("references", { open: true })}</div>
        <div class="card"><div class="label">Groups</div><p class="small">Each sample's group, guessed from its name. Biological replicates of one condition share a group.</p>
          <table><thead><tr><th>Sample</th><th>Group</th></tr></thead><tbody>${Object.entries(r.groups).map(([s, g]) => `<tr><td>${esc(s)}</td><td><input type="text" data-s="${esc(s)}" value="${esc(g)}" style="max-width:180px"></td></tr>`).join("")}</tbody></table>
          <label class="field" style="max-width:260px;margin-top:10px"><span>Compare every group with</span><select id="ctrl">${groups.map(g => `<option ${g === r.control ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></label>
          <div class="row"><button class="btn primary" id="saveGroups">Save groups</button></div></div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:expression">Fold changes →</button></div>`;
    el.addEventListener("click", e => { const b = e.target.closest(".chip[data-ref]"); if (b) b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true"); });
    $("#saveRefs", el).onclick = e => guarded(e.currentTarget, async () => {
      const genes = $$(".chip[data-ref][aria-pressed=true]", el).map(b => b.dataset.ref);
      await E.call("set_references", { genes });
      const q = await E.call("references"); $("#cm", el).textContent = q.chosen_m != null ? `M of the chosen set: ${q.chosen_m}` : "";
      toast(`Normalising to ${genes.join(", ")}.`, true);
    });
    $$("input[data-s]", el).forEach(i => i.addEventListener("input", () => {
      const gs = [...new Set($$("input[data-s]", el).map(x => x.value.trim()).filter(Boolean))], cur = $("#ctrl", el).value;
      $("#ctrl", el).innerHTML = gs.map(g => `<option ${g === cur ? "selected" : ""}>${esc(g)}</option>`).join("");
    }));
    $("#saveGroups", el).onclick = e => guarded(e.currentTarget, async () => {
      const groups = Object.fromEntries($$("input[data-s]", el).map(i => [i.dataset.s, i.value]));
      await E.call("set_groups", { groups, control: $("#ctrl", el).value }); toast("Groups saved.", true);
    });
  }

  // ---------------------------------------------------------------- fold changes
  function dots(r, target) {
    const C = COL(), pal = H.PALETTE(), pts = r.points.filter(p => p.target === target), gs = r.groups;
    const w = 300, h = 200, L = 40, B = 30, T = 10, vals = pts.map(p => p.log2_rel), y0 = Math.min(-1, ...vals) - 0.3, y1 = Math.max(1, ...vals) + 0.3;
    const X = i => L + (i + 0.5) * (w - L - 10) / gs.length, Y = v => T + (y1 - v) / (y1 - y0) * (h - B - T);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(target)}: log2 expression of each sample relative to the control mean">
      <line x1="${L}" x2="${w - 10}" y1="${Y(0)}" y2="${Y(0)}" stroke="${C.muted}" stroke-dasharray="4 3"/>`;
    for (let v = Math.ceil(y0); v <= Math.floor(y1); v++) s += `<text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v}</text>`;
    gs.forEach((g, i) => {
      const mine = pts.filter(p => p.group === g), m = mine.reduce((a, p) => a + p.log2_rel, 0) / (mine.length || 1);
      s += `<line x1="${X(i) - 22}" x2="${X(i) + 22}" y1="${Y(m)}" y2="${Y(m)}" stroke="${C.ink}" stroke-width="2"/>`;
      mine.forEach((p, k) => s += `<circle cx="${X(i) + (k - (mine.length - 1) / 2) * 9}" cy="${Y(p.log2_rel)}" r="4" fill="${pal[i % pal.length]}"><title>${esc(p.sample)}: log2 ${p.log2_rel}</title></circle>`);
      s += `<text x="${X(i)}" y="${h - 10}" text-anchor="middle" class="ax">${esc(g)}</text>`;
    });
    return s + `<text x="12" y="${h / 2}" transform="rotate(-90 12 ${h / 2})" text-anchor="middle" class="ax">log2 vs ${esc(r.control)}</text><text x="${L + 4}" y="${T + 10}" class="ax">${esc(target)}</text></svg>`;
  }

  async function expression(el) {
    const r = await E.call("expression");
    const targets = [...new Set(r.comparisons.map(c => c.target))];
    const p = v => v == null ? "—" : v < 0.001 ? v.toExponential(1) : v.toFixed(3);
    el.innerHTML = lede(`Expression of each target relative to <b>${esc(r.control)}</b>, normalised to ${r.references.map(esc).join(" and ")}. Each dot is one biological replicate; the bar is the group mean.`) +
      `<div class="grid g3">${targets.map(t => `<div class="card">${dots(r, t)}</div>`).join("")}</div>
      <div class="card" style="margin-top:18px"><div class="label">Fold changes</div><div style="overflow:auto"><table><thead><tr><th>Group</th><th>Target</th><th class="num">n</th><th class="num">Fold change</th><th class="num">95% CI</th><th class="num">log2</th><th class="num">p</th><th class="num">Adjusted p</th></tr></thead><tbody>
        ${r.comparisons.map(c => `<tr><td>${esc(c.group)}</td><td>${esc(c.target)}</td><td class="num">${c.n} vs ${c.n_control}</td><td class="num"><b>${c.fold_change ?? "—"}</b></td>
          <td class="num">${c.ci_low != null ? `${c.ci_low}–${c.ci_high}` : "—"}</td><td class="num">${c.log2_fc ?? "—"}</td><td class="num">${p(c.p)}</td><td class="num">${p(c.p_adj)}</td></tr>`).join("")}</tbody></table></div>
        ${guide("foldchange", { open: true })}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    el.innerHTML = lede("Save the tables. Everything goes in the run's results folder.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>fold_changes.csv</b>: each group against the control, with 95% confidence interval and p-values.</li>
        <li><b>relative_expression.csv</b>: normalised relative quantity of every target in every sample, for your own plots.</li>
        <li><b>efficiencies.csv</b>: standard-curve slope, R² and the efficiency used for each target.</li>
        <li><b>replicates.csv</b> and <b>excluded_wells.csv</b>: every replicate set with its spread, and the wells you left out.</li></ul>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>
      <div class="row" style="margin-top:18px"><button class="btn" data-go="record">Record and write-up →</button></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Tables saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("molbio.qpcr", { plate, efficiency, references, expression, export: exportView });
})();
