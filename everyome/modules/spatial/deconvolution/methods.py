"""Draft methods section for a cell-type mapping run, written from its record."""
from __future__ import annotations

from everyome.core.writeup import join_and, last, setting, table, version

MEASURE = {"share": "share of each spot", "mean": "estimated number of cells", "q05": "cautious (5% quantile) number of cells"}


def methods(rec: dict) -> str:
    sections = [r["sample"] for r in table(rec, "samples")]
    hist, sw = (rec.get("session") or {}).get("history", []), rec["software"]
    ref = next((str(x["value"]) for x in rec["inputs"] if x["id"] == "reference"), "").split("/")[-1] or "a single-cell reference"
    labels, batch = setting(rec, "labels_key", "cell_type"), setting(rec, "batch_key", "")
    o = last(hist, "read the cell-type abundances") or {}
    n_types = len(o.get("types", []))
    P = [f"Cell types in {len(sections)} 10x Visium section{'s' if len(sections) != 1 else ''} ({join_and(sections)}) were mapped with "
         f"cell2location{version(sw, 'cell2location', 'Kleshchevnikov et al., 2022')}, run through Everyome (version {rec['everyome']}). "
         f"The expression of each {'of ' + str(n_types) + ' ' if n_types else ''}cell type{'s' if n_types != 1 else ''} was first estimated from "
         f"a single-cell reference ({ref}; cell types from the '{labels}' column"
         + (f", with '{batch}' as the batch" if batch else "") + ") with cell2location's negative binomial regression model, trained for "
         f"{setting(rec, 'reference_epochs', 250)} rounds after the authors' gene filter. Spots were then mapped with an expected "
         f"{setting(rec, 'cells_per_spot', 30)} cells per spot and a detection alpha of {setting(rec, 'detection_alpha', 20)}, trained for "
         f"{setting(rec, 'mapping_epochs', 30000)} rounds with each section as a batch; the abundance of each cell type in each spot is the "
         "posterior mean, with the 5% quantile as a cautious estimate."]
    t = last(hist, "compared cell types across spots")
    if t:
        pairs = "; ".join(f"{a} and {b} (r = {r:.2f})" for a, b, r in t["top"])
        P.append(f"Cell types found together were assessed by the Pearson correlation of their {MEASURE.get(t['measure'], t['measure'])} across "
                 f"the {t['spots']:,} spots with at least {t['min_cells']:g} estimated cells; the most strongly correlated pairs were {pairs}.")
    ex = last(hist, "exported cell-type tables")
    if ex:
        P.append("Per-spot cell abundances, cell-type shares and the main cell type of each spot were exported as tables.")
    return "\n\n".join(P) + "\n"
