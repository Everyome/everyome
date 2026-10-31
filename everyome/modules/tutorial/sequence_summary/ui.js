/* Views for the Sequence summary module: explore GC content and choose a range to keep.
   Uses only the shared helpers Everyome provides, so it follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, { $, esc, fmt, guarded, toast, followTask, histChart } = E.helpers;

  async function explore(el) {
    const s = await E.call("summary");
    let [lo, hi] = s.gc_range;
    el.innerHTML = `<p class="lede">GC content is the share of bases that are G or C. Most genomes sit in a narrow band;
        a second peak can mean contamination or a mix of organisms. Choose the range to keep, then export.</p>
      <div class="grid g-side"><div class="card"><div class="label">GC content of each sequence</div><div id="gch"></div>
        <div class="grid g2" style="margin-top:12px">
          <label class="field"><span>Lowest GC kept</span><input type="range" id="lo" min="0" max="1" step="0.01" value="${lo}"><small id="lov"></small></label>
          <label class="field"><span>Highest GC kept</span><input type="range" id="hi" min="0" max="1" step="0.01" value="${hi}"><small id="hiv"></small></label>
        </div></div>
      <div class="card"><div class="label">Summary</div><div id="sum"></div>
        <div class="row" style="margin-top:14px"><button class="btn primary" id="apply">Keep this range</button><button class="btn" id="export">Export table</button></div>
        <div id="prog"></div>
        <p class="small muted" style="margin-top:12px">Very short sequences give unreliable GC values; the run left out sequences below its <i>Shortest sequence kept</i> setting.</p></div></div>
      <div class="card" style="margin-top:18px"><div class="label">Sequence lengths</div><div id="lh"></div></div>`;
    const gc = await E.call("histogram", { field: "gc", bins: 25 });
    const len = await E.call("histogram", { field: "length", bins: 20 });
    $("#lh", el).innerHTML = histChart(len.edges, len.counts, { xlab: "Length (bases)", digits: 0 });
    const summary = x => {
      $("#sum", el).innerHTML = [["Sequences", fmt(x.sequences)], ["Kept in range", fmt(x.kept)], ["Mean length", fmt(Math.round(x.mean_length)) + " bases"], ["Mean GC", x.mean_gc.toFixed(3)]]
        .map(([k, v]) => `<div class="metric"><span>${k}</span><b>${esc(v)}</b></div>`).join("");
    };
    const draw = () => {
      lo = Math.min(+$("#lo", el).value, +$("#hi", el).value); hi = Math.max(+$("#lo", el).value, +$("#hi", el).value);
      $("#lov", el).textContent = lo.toFixed(2); $("#hiv", el).textContent = hi.toFixed(2);
      $("#gch", el).innerHTML = histChart(gc.edges, gc.counts, { lo, hi, xlab: "GC fraction" });
    };
    ["#lo", "#hi"].forEach(id => $(id, el).addEventListener("input", draw));
    $("#apply", el).onclick = e => guarded(e.currentTarget, async () => { summary(await E.call("set_gc_range", { lo, hi })); toast("Range saved.", true); });
    $("#export", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("export"); const st = await followTask($("#prog", el)); toast(st.task.message || "Exported.", true);
    });
    summary(s); draw();
  }

  E.registerViews("tutorial.sequence_summary", { explore });
})();
