/* Views for the K-mer spectrum test module. */
"use strict";
(() => {
  const E = window.Everyome, { $, fmt, guarded, toast, barChart, guide } = E.helpers;

  async function spectrum(el) {
    const s = await E.call("spectrum");
    el.innerHTML = `<div class="card"><div class="label">${fmt(s.distinct)} distinct ${s.k}-mers, ${fmt(s.total)} in all</div>
      <div id="sp"></div>${guide("spectrum")}<div class="row" style="margin-top:12px"><button class="btn" id="ex">Export table</button></div></div>`;
    $("#sp", el).innerHTML = barChart(s.occurrences.slice(0, 12).map((n, i) => [`seen ${n}×`, s.kmers[i]]), { title: "Distinct k-mers by times seen" });
    $("#ex", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); toast("Saved results/kmers.tsv", true); });
  }

  E.registerViews("community.kmer_spectrum", { spectrum });
})();
