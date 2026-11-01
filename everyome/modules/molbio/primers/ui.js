/* Views for primer design: sequence map and region, Primer3 suggestions, checking your own primers, export.
   Uses Everyome's shared sequence map, so it follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, seqMap } = H;
  const lede = t => `<p class="lede">${t}</p>`;
  let info = null;
  const load = async () => (info = await E.call("sequence_info"));
  const mapOf = (extra = {}) => seqMap(info.length, { features: info.features, sites: info.sites, circular: info.circular, title: info.name,
    highlight: info.target ? { start: info.target.start, end: info.target.end, label: "region to amplify" } : null, ...extra });
  const pairPrimers = p => p ? [{ label: `F ${p.left_tm}°`, start: p.left_start, end: p.left_end, strand: 1 },
                                { label: `R ${p.right_tm}°`, start: p.right_start, end: p.right_end, strand: -1 }] : [];

  // ---------------------------------------------------------------- sequence and region
  async function sequence(el) {
    await load();
    const t = info.target || {};
    el.innerHTML = lede("Here is your sequence. Choose the region the PCR product must cover; the primers are placed either side of it.") +
      `<div class="grid g-side"><div class="card"><div class="label">${info.circular ? "Plasmid map" : "Sequence map"}</div><div id="map">${mapOf()}</div>
          <p class="small muted">Enzymes shown cut only once. Hover over a feature for its position.</p></div>
        <div><div class="card"><div class="label">About the sequence</div>
          <div class="metric"><span>Length</span><b>${fmt(info.length)} bp</b></div><div class="metric"><span>GC content</span><b>${info.gc}%</b></div>
          <div class="metric"><span>Shape</span><b>${info.circular ? "circular" : "linear"}</b></div>
          <div class="metric"><span>Single-cut enzymes</span><b>${info.sites.length}</b></div></div>
        <div class="card" style="margin-top:18px"><div class="label">Region to amplify</div>
          ${info.features.length ? `<label class="field"><span>Start from a feature</span><select id="feat"><option value="">Choose…</option>${info.features.map((f, i) => `<option value="${i}">${esc(f.label)} (${f.start}–${f.end})</option>`).join("")}</select></label>` : ""}
          <div class="grid g2"><label class="field"><span>Start</span><input type="number" id="ts" min="1" max="${info.length}" value="${t.start ?? ""}"></label>
            <label class="field"><span>Length</span><input type="number" id="tl" min="1" value="${t.length ?? ""}"></label></div>
          <div class="row"><button class="btn primary" id="set">Use this region</button></div>
          <p class="small muted" style="margin-top:8px">Leave it unset to let Primer3 place a product anywhere.</p></div></div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:design">Design primers →</button></div>`;
    const sel = $("#feat", el);
    if (sel) sel.onchange = () => { const f = info.features[+sel.value]; if (f) { $("#ts", el).value = f.start; $("#tl", el).value = f.end - f.start + 1; } };
    $("#set", el).onclick = e => guarded(e.currentTarget, async () => {
      const f = sel && info.features[+sel.value];
      await E.call("set_target", { start: Number($("#ts", el).value), length: Number($("#tl", el).value), label: f ? f.label : "" });
      await load(); $("#map", el).innerHTML = mapOf(); toast("Region saved.", true);
    });
  }

  // ---------------------------------------------------------------- design
  async function design(el) {
    await load();
    el.innerHTML = lede("Primer3 suggests pairs that flank your region, best first. Change the settings on the run's settings page; this page uses them.") +
      `<div class="row" style="margin-bottom:14px"><button class="btn primary" id="go">${info.pairs.length ? "Design again" : "Design primers"}</button>
        <span class="small muted">${info.target ? `Region ${info.target.start}–${info.target.end}${info.target.label ? " (" + esc(info.target.label) + ")" : ""}` : "No region chosen: anywhere in the sequence"}.</span></div>
      <div id="why"></div><div class="card"><div class="label">Suggested pairs</div><div id="tbl" style="overflow-x:auto"></div></div>
      <div class="card" style="margin-top:18px;max-width:720px"><div class="label">On the map</div><div id="map"></div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
    let pick = info.chosen || 1;
    function draw(pairs, explain) {
      $("#why", el).innerHTML = !pairs.length ? `<div class="notice warn">Primer3 found no pairs with these settings. Try a wider product size range or melting temperature, or a different region.
          ${explain ? `<br><span class="small mono">${Object.entries(explain).map(([k, v]) => `${esc(k)}: ${esc(v)}`).join("<br>")}</span>` : ""}</div>` : "";
      $("#tbl", el).innerHTML = pairs.length ? `<table><thead><tr><th>#</th><th>Forward 5'→3'</th><th>Reverse 5'→3'</th><th class="num">Tm F / R</th><th class="num">GC F / R</th><th class="num">Product</th><th class="num">Penalty</th></tr></thead><tbody>
        ${pairs.map(p => `<tr class="click ${p.n === pick ? "sel" : ""}" tabindex="0" data-n="${p.n}"><td>${p.n}</td><td class="mono small">${esc(p.left)}</td><td class="mono small">${esc(p.right)}</td>
          <td class="num">${p.left_tm} / ${p.right_tm}</td><td class="num">${p.left_gc} / ${p.right_gc}</td><td class="num">${p.product}</td><td class="num">${p.penalty}</td></tr>`).join("")}</tbody></table>
        <p class="small muted" style="margin-top:8px">Click a pair to see it on the map. Lower penalty means a closer fit to your settings.</p>` : `<p class="small muted">No pairs yet.</p>`;
      $("#map", el).innerHTML = mapOf({ primers: pairPrimers(pairs.find(p => p.n === pick)) });
    }
    el.addEventListener("click", e => { const r = e.target.closest("[data-n]"); if (r) { pick = +r.dataset.n; draw(info.pairs, null); } });
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { const r = await E.call("design"); await load(); pick = 1; draw(r.pairs, r.explain); toast(`${r.pairs.length} pairs suggested.`, true); });
    draw(info.pairs, null);
  }

  // ---------------------------------------------------------------- check
  async function check(el) {
    await load();
    el.innerHTML = lede("Paste a primer, or a pair, that you already have. Everyome works out melting temperatures, hairpins and dimers with Primer3, using your reaction conditions, and finds where they bind in this sequence.") +
      `<div class="card"><div class="grid g2"><label class="field"><span>Forward primer (5'→3')</span><input type="text" id="l" class="mono"></label>
        <label class="field"><span>Reverse primer (5'→3', optional)</span><input type="text" id="r" class="mono"></label></div>
        <label class="field" style="max-width:320px"><span>Name</span><input type="text" id="nm" value="my primers"></label>
        <div class="row"><button class="btn primary" id="go">Check</button></div></div><div id="out"></div>`;
    const dg = v => `<span class="${v < -9 ? "warnv" : ""}">${v} kcal/mol</span>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      const r = await E.call("check_primers", { left: $("#l", el).value, right: $("#r", el).value, name: $("#nm", el).value });
      const row = (t, p) => `<tr><td>${t}</td><td class="mono small">${esc(p.seq)}</td><td class="num">${p.length}</td><td class="num">${p.tm} °C</td><td class="num">${p.gc}%</td>
        <td class="num">${dg(p.hairpin_dg)}</td><td class="num">${dg(p.self_dimer_dg)}</td><td class="small">${p.binds_at ? "forward at " + p.binds_at : ""}${p.binds_reverse_at ? " reverse at " + p.binds_reverse_at : ""}${!p.binds_at && !p.binds_reverse_at ? "no exact match" : ""}</td></tr>`;
      const prim = [];
      if (r.left.binds_at) prim.push({ label: "F", start: r.left.binds_at, end: r.left.binds_at + r.left.length - 1, strand: 1 });
      if (r.right?.binds_reverse_at) prim.push({ label: "R", start: r.right.binds_reverse_at, end: r.right.binds_reverse_at + r.right.length - 1, strand: -1 });
      $("#out", el).innerHTML = `<div class="grid g-side" style="margin-top:18px"><div class="card"><table><thead><tr><th></th><th>Sequence</th><th class="num">Length</th><th class="num">Tm</th><th class="num">GC</th><th class="num">Hairpin ΔG</th><th class="num">Self-dimer ΔG</th><th>Binds this sequence</th></tr></thead><tbody>
        ${row("Forward", r.left)}${r.right ? row("Reverse", r.right) : ""}</tbody></table>
        ${r.right ? `<p class="small" style="margin-top:10px">Pair dimer ΔG: ${dg(r.pair_dimer_dg)}. ${r.product ? `Product: <b>${fmt(r.product)} bp</b>.` : "They do not make a product on this sequence (no forward and reverse match in the right order)."}
          ${Math.abs(r.left.tm - r.right.tm) > 5 ? ` <b>The two melting temperatures differ by more than 5 °C.</b>` : ""}</p>` : ""}
        <p class="small muted">ΔG closer to 0 is better; below about −9 kcal/mol (shown in red) the structure is strong enough to cause trouble.</p></div>
        <div class="card"><div class="label">On the map</div>${mapOf({ primers: prim })}</div></div>`;
    });
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    await load();
    if (!info.pairs.length) { el.innerHTML = `<div class="empty">Design primers first.</div>`; return; }
    el.innerHTML = lede("Choose the pairs to order. Everyome saves every suggested pair, an order sheet and a GenBank file with the primers added as features.") +
      `<div class="card"><div class="label">Pairs to order</div><div class="chips">${info.pairs.map(p => `<button class="chip" data-n="${p.n}" aria-pressed="${p.n === (info.chosen || 1)}">Pair ${p.n} · ${p.product} bp</button>`).join("")}</div>
        <div class="row" style="margin-top:14px"><label class="field" style="margin:0;max-width:260px"><span>Name primers as</span><input type="text" id="pre" value="${esc(info.name)}"></label>
        <button class="btn primary" id="go">Export</button></div><div id="files"></div></div>
      <div class="row" style="margin-top:18px"><button class="btn" data-go="record">Record and write-up →</button></div>`;
    el.addEventListener("click", e => { const b = e.target.closest(".chip[data-n]"); if (b) b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true"); });
    async function files() {
      const f = await E.call("files");
      $("#files", el).innerHTML = f.length ? `<table style="margin-top:14px"><thead><tr><th>File</th><th class="num">Size</th><th></th></tr></thead><tbody>${f.map(x =>
        `<tr><td class="mono small">${esc(x.name)}</td><td class="num small">${fmtSize(x.size)}</td><td class="num"><a class="btn small" href="${E.downloadUrl(x.name)}" download>Download</a></td></tr>`).join("")}</tbody></table>` : "";
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      const chosen = $$(".chip[aria-pressed=true]", el).map(b => +b.dataset.n);
      if (!chosen.length) throw new Error("Choose at least one pair.");
      const r = await E.call("export", { chosen, prefix: $("#pre", el).value });
      await files(); toast(`Saved. Order sheet has ${r.order.length} primers.`, true);
    });
    files();
  }

  E.registerViews("molbio.primers", { sequence, design, check, export: exportView });
})();
