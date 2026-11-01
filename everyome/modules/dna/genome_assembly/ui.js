/* Views for genome assembly: what nf-core/genomeassembler made (Run page), then the shared assembly explorer
   (../shared/assembly_ui.js): compare, contigs, genes, choose and export. */
"use strict";
(() => {
  const E = window.Everyome, { esc, guide } = E.helpers, { views } = E.assembly();

  async function report(el, q) {
    el.innerHTML = `<h2>What the pipeline made</h2><div class="grid g2"><div class="card"><div class="label">Assemblies</div>
        ${q.assemblies.length ? `<ul class="small">${q.assemblies.map(p => `<li><code style="word-break:break-all">${esc(p)}</code></li>`).join("")}</ul>
          <p class="small muted">Compare them in the live session.</p>` : `<div class="notice warn">No assemblies were found. Check the pipeline log.</div>`}</div>
      <div class="card"><div class="label">Pipeline report</div>${q.report ? `<p class="small">nf-core/genomeassembler's report brings together QUAST, BUSCO and Merqury for every assembly.</p>
          <a class="btn primary small" href="/api/run/file?path=${encodeURIComponent(q.report)}" target="_blank" rel="noopener">Open the report</a>` : `<p class="small muted">No report found.</p>`}
        ${E.state().demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster this is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  E.registerViews("dna.assembly", { report, ...views });
})();
