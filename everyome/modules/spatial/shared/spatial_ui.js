/* Shared views for the spatial modules: observations (spots, bins or cells) in their place on the tissue, coloured by
   anything, with spatially variable genes; and which types sit next to which (neighbourhood enrichment).
   E.spatial({ words }) returns { tissueSvg, tissue, neighbourhood }, used by each spatial module's ui.js. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, toast, guarded, followTask, legendFor, guide } = H;
  const lede = t => `<p class="lede">${t}</p>`;

  E.spatial = ({ S, refresh, reached, words = {} }) => {
    const W = { unit: "spot", units: "spots", count: "UMIs per spot", features: "Genes per spot", ...words };

    // A colour for observation i: categories use their own colours; numbers run from pale to the theme's strong colour.
    function colourOf(c, i) {
      const C = H.COL();
      if (c.kind === "cat") return c.colors[c.codes[i]] || C.rule;
      const t = Math.min(1, c.values[i] / (c.max || 1)), a = H.hexRgb(C.parch), m = H.hexRgb(C.gold), b = H.hexRgb(C.ox);
      const mix = (p, q, s) => p.map((v, k) => Math.round(v + (q[k] - v) * s));
      return `rgb(${t < .5 ? mix(a, m, t * 2) : mix(m, b, (t - .5) * 2)})`;
    }
    function tissueSvg(d, { opacity = 0.85, maxW = 560, size = 1.4 } = {}) {
      const c = H.themed(d.colour);
      const order = d.x.map((_, i) => i);
      if (c.kind === "num") order.sort((i, j) => c.values[i] - c.values[j]);      // strongest drawn last, on top
      return `<svg class="chart" viewBox="0 0 ${d.width} ${d.height}" style="max-width:${maxW}px;background:${H.COL().card}" role="img" aria-label="${esc(W.units)} on the tissue">
        ${d.image ? `<image href="${d.image}" x="0" y="0" width="${d.width}" height="${d.height}"/>` : ""}
        ${order.map(i => `<circle cx="${d.x[i]}" cy="${d.y[i]}" r="${(d.r * size).toFixed(2)}" fill="${colourOf(c, i)}" fill-opacity="${opacity}"><title>${esc(c.kind === "cat" ? c.categories[c.codes[i]] : `${c.gene}: ${c.values[i]}`)}</title></circle>`).join("")}</svg>`;
    }

    // ---------------------------------------------------------------- on the tissue
    async function tissue(el) {
      await refresh();
      const sections = Object.keys(await E.call("spots_per_sample")), cols = S.an.obs_columns || [];
      const keys = [...(reached("clustered") ? ["cluster", "annotation"] : []), "total_counts", "n_genes", ...cols.filter(c => !["cluster"].includes(c))];
      const label = { cluster: "Cluster", annotation: `${W.typeNames || "Region names"}`, total_counts: W.count, n_genes: W.features };
      el.innerHTML = lede(`Every ${W.unit} in its place on the tissue. Colour by ${W.typeWord || "region"}, by a gene, or by a quality measure, and look for genes whose expression follows the tissue's structure.`) +
        `<div class="grid g-side"><div class="card"><div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
            <label class="small">Section <select id="sec" style="width:auto">${sections.map(s => `<option>${esc(s)}</option>`).join("")}</select></label>
            <label class="small">Colour by <select id="key" style="width:auto">${keys.map(k => `<option value="${esc(k)}">${esc(label[k] || k)}</option>`).join("")}</select></label>
            <input type="text" id="gq" placeholder="Gene…" style="width:140px" list="gl" aria-label="Colour by gene"><datalist id="gl"></datalist>
            <label class="small">Opacity <input type="range" id="op" min="0" max="1" step="0.05" value="0.9" style="width:80px"></label>
            <label class="small" title="1 is the true size; larger is easier to see">Size <input type="range" id="sz" min="1" max="2" step="0.1" value="1.4" style="width:80px"></label></div>
          <div id="view" style="margin-top:10px"></div><div id="leg"></div>${guide("tissue")}</div>
          <div><div class="card"><div class="label">Spatially variable genes</div>
            <p class="small muted">Genes whose expression is similar in neighbouring ${W.units} (Moran's I, from 0 for no pattern up to 1).</p>
            <div id="svg"></div><div class="row" style="margin-top:10px"><button class="btn" id="find">${S.an.spatial_genes ? "Find again" : "Find them"}</button></div><div id="sprog"></div>${guide("spatial_genes")}</div></div></div>`;
      let key = reached("clustered") ? "cluster" : "total_counts";
      $("#key", el).value = key;
      const draw = async () => {
        const d = await E.call("tissue", { sample: $("#sec", el).value, key });
        $("#view", el).innerHTML = tissueSvg(d, { opacity: +$("#op", el).value, size: +$("#sz", el).value, maxW: 640 });
        $("#leg", el).innerHTML = legendFor(d.colour) + `<p class="small muted">${fmt(d.spots)} ${W.units}.</p>`;
      };
      const list = () => {
        const g = S.an.spatial_genes;
        $("#svg", el).innerHTML = g ? `<table class="small"><thead><tr><th>Gene</th><th class="num">Moran's I</th><th class="num">Detected</th></tr></thead><tbody>${g.slice(0, 25).map(x =>
          `<tr class="click" tabindex="0" data-g="${esc(x.gene)}"><td class="mono">${esc(x.gene)}</td><td class="num">${x.morans_i.toFixed(2)}</td><td class="num">${x.detected}%</td></tr>`).join("")}</tbody></table>` : "";
      };
      $("#sec", el).onchange = draw;
      $("#key", el).onchange = e => { key = e.target.value; draw(); };
      $("#op", el).oninput = draw; $("#sz", el).oninput = draw;
      $("#svg", el).addEventListener("click", e => { const r = e.target.closest("[data-g]"); if (r) { key = r.dataset.g; $("#gq", el).value = key; draw(); } });
      $("#svg", el).addEventListener("keydown", e => { if (e.key === "Enter") e.target.click(); });
      let gt; $("#gq", el).addEventListener("input", e => { clearTimeout(gt); gt = setTimeout(async () => {
        const q = e.target.value.trim(); if (q.length < 2) return;
        const g = await E.call("genes", { q }).catch(() => []);
        $("#gl", el).innerHTML = g.map(x => `<option value="${esc(x.gene)}">`).join("");
        if (g.some(x => x.gene === q)) { key = q; draw(); } }, 250); });
      $("#find", el).onclick = e => guarded(e.currentTarget, async () => {
        await E.call("spatial_genes", {}); await followTask($("#sprog", el)); await refresh(); list(); toast("Spatially variable genes found.", true);
      });
      list(); draw();
    }

    // ---------------------------------------------------------------- neighbourhoods
    async function neighbourhood(el) {
      await refresh();
      el.innerHTML = lede(`Which ${W.typeWord || "types"} sit next to which. Each square compares how often two ${W.typeWord || "types"} are neighbours with what chance alone would give.`) +
        `<div class="grid g-side"><div class="card"><div class="label">Neighbourhood enrichment</div><div id="nh" style="overflow:auto"><p class="small muted">${reached("clustered") ? "Press Compute." : "Cluster first."}</p></div>${guide("neighbourhood")}</div>
          <div class="card"><div class="label">Settings</div>
            <label class="field"><span>Group by</span><select id="by"><option value="annotation">Names (where given)</option><option value="cluster">Cluster</option></select></label>
            <label class="field"><span>Neighbours per ${W.unit}</span><input type="number" id="k" min="3" max="30" value="10"></label>
            <div class="row"><button class="btn primary" id="go" ${reached("clustered") ? "" : "disabled"}>Compute</button></div><div id="nprog"></div></div></div>`;
      const draw = r => {
        // Intent: colour by the size of the effect (log2 of contacts against chance); z-scores grow with cell numbers.
        const M = r.log2_ratio || r.z, C = H.COL(), n = r.groups.length, cw = 34, left = 130, top = 110, lim = r.log2_ratio ? 3 : Math.max(3, ...M.flat().map(Math.abs));   // 3 = eight times chance, either way
        const a = H.hexRgb(C.parch), pos = H.hexRgb(C.ox), neg = H.hexRgb(C.plum || C.ink);
        const col = v => { const t = Math.min(1, Math.abs(v) / lim), b = v >= 0 ? pos : neg; return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t))})`; };
        let s = `<svg class="chart" style="min-width:${left + n * cw + 20}px;max-width:${left + n * cw + 20}px" viewBox="0 0 ${left + n * cw + 20} ${top + n * cw + 10}" role="img" aria-label="Neighbourhood enrichment">`;
        r.groups.forEach((g, j) => s += `<text transform="translate(${left + j * cw + cw / 2 + 4},${top - 6}) rotate(-55)" class="ax">${esc(g)}</text>`);
        r.groups.forEach((g, i) => { s += `<text x="${left - 6}" y="${top + i * cw + cw / 2 + 4}" text-anchor="end" class="ax">${esc(g)}</text>`;
          r.z[i].forEach((v, j) => s += `<rect x="${left + j * cw}" y="${top + i * cw}" width="${cw - 1}" height="${cw - 1}" fill="${col(M[i][j])}"><title>${esc(g)} next to ${esc(r.groups[j])}: ${r.log2_ratio ? `${(2 ** r.log2_ratio[i][j]).toFixed(2)}× chance, ` : ""}z = ${v}</title></rect>`); });
        $("#nh", el).innerHTML = s + `</svg>` + H.legend([["more often neighbours than by chance", C.ox], ["less often", C.plum || C.ink]]);
      };
      $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
        await E.call("neighbourhood", { by: $("#by", el).value, k: Number($("#k", el).value) }); await followTask($("#nprog", el)); await refresh();
        draw(S.an.neighbourhood); toast("Neighbourhoods compared.", true);
      });
      if (S.an.neighbourhood) draw(S.an.neighbourhood);
    }

    return { tissueSvg, tissue, neighbourhood };
  };
})();
