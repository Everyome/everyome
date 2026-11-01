/* Views for bacterial assembly: what nf-core/bacass made (Run page), then the shared assembly explorer
   (../shared/assembly_ui.js): compare, contigs, genes, choose and export. */
"use strict";
(() => {
  const E = window.Everyome, { esc, guide } = E.helpers, { views } = E.assembly();

  async function report(el, q) {
    const list = xs => `<ul class="small">${xs.map(p => `<li><code style="word-break:break-all">${esc(p)}</code></li>`).join("")}</ul>`;
    el.innerHTML = `<h2>What the pipeline made</h2><div class="grid g2"><div class="card"><div class="label">Assemblies and annotations</div>
        ${q.assemblies.length ? list(q.assemblies) : `<div class="notice warn">No assemblies were found. Check the pipeline log.</div>`}
        ${q.annotations.length ? `<div class="label" style="margin-top:10px">Gene annotations</div>${list(q.annotations)}` : ""}</div>
      <div class="card"><div class="label">Quality report</div>${q.multiqc ? `<p class="small">nf-core/bacass's MultiQC report brings together read quality, QUAST and BUSCO for every assembly.</p>
          <a class="btn primary small" href="/api/run/file?path=${encodeURIComponent(q.multiqc)}" target="_blank" rel="noopener">Open the MultiQC report</a>` : `<p class="small muted">No MultiQC report found.</p>`}
        ${E.state().demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster this is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  E.registerViews("dna.bacterial", { report, ...views });
})();
