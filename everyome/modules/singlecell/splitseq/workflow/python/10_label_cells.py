"""Stage 10 — attach sample metadata to every cell.

Input : combined 10x matrix from stage 09 (atlas + your sublibraries)
Output: fully_labelled.h5ad with obs columns
        Experiment, Library, <labelling.columns ...>, Unique

How values are assigned (all set in config/analysis.yaml -> labelling):
  1. The cell ID is split into experiment, library and barcode (cell_id_regex).
  2. Each library's row in `libraries` supplies one value per metadata column.
  3. "from_barcodes" values are looked up per cell: the first 8 nt of the
     barcode is the round-1 well, mapped to a value by a barcode sheet.
  4. `overrides` rules are applied in order.
  5. `unique_id` columns are joined into one sample ID per cell.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scanpy as sc

import common

FROM_BARCODES = "from_barcodes"


def parse_cell_ids(obs_names: pd.Index, pattern: str) -> pd.DataFrame:
    """Split cell IDs into experiment / library / barcode with a named regex."""
    parts = obs_names.to_series().str.extract(pattern)
    unparsed = parts["library"].isna()
    if unparsed.any():
        examples = ", ".join(obs_names[unparsed][:3])
        raise ValueError(f"{unparsed.sum()} cell IDs do not match cell_id_regex, e.g. {examples}")
    return parts


def read_barcode_sheet(path) -> dict[str, str]:
    """Headerless two-column sheet (barcode, value) -> {barcode: value}."""
    sheet = pd.read_excel(path, header=None)
    sheet = sheet.iloc[:, -2:]            # tolerate a leading index column
    sheet.columns = ["bc", "value"]
    common.log.info("barcode sheet %s: %s", path.name, sheet["value"].value_counts().to_dict())
    return dict(zip(sheet["bc"].astype(str), sheet["value"].astype(str)))


def label_from_barcodes(barcodes: pd.Series, bc_map: dict[str, str]) -> pd.Series:
    """Value for each cell whose barcode starts with a round-1 well barcode."""
    out = pd.Series(np.nan, index=barcodes.index, dtype=object)
    for bc, value in bc_map.items():
        out[barcodes.str.startswith(bc)] = value
    return out


def apply_overrides(obs: pd.DataFrame, rules: list[dict]) -> None:
    """Rules like {when: {col: value}, set: {col: value}}, applied in order."""
    for rule in rules or []:
        mask = pd.Series(True, index=obs.index)
        for col, val in rule["when"].items():
            mask &= obs[col].astype(str) == str(val)
        for col, val in rule["set"].items():
            obs.loc[mask, col] = val
        common.log.info("override %s -> %s: %d cells", rule["when"], rule["set"], mask.sum())


def build_obs(adata, cfg) -> pd.DataFrame:
    lab = cfg["labelling"]
    parts = parse_cell_ids(adata.obs_names, lab["cell_id_regex"])

    unknown = set(parts["library"]) - set(lab["libraries"])
    if unknown:
        raise ValueError(f"libraries missing from labelling.libraries: {sorted(unknown)}")

    # Intent: broadcast the per-library table onto cells.
    lib_table = pd.DataFrame.from_dict(lab["libraries"], orient="index").astype(str)
    meta = lib_table.reindex(parts["library"]).set_index(adata.obs_names)

    obs = pd.DataFrame(index=adata.obs_names)
    obs["Experiment"] = parts["experiment"]
    obs["Library"] = parts["library"]
    for col in lab["columns"]:
        obs[col] = meta[col]

    # Intent: resolve well-level values from round-1 barcode sheets.
    for col in lab["columns"]:
        needs = obs[col] == FROM_BARCODES
        if not needs.any():
            continue
        sheet = lab.get("barcode_sheets", {}).get(col)
        if sheet is None:
            raise ValueError(f"column '{col}' uses from_barcodes but has no barcode sheet")
        bc_map = read_barcode_sheet(common.resolve(sheet))
        obs.loc[needs, col] = label_from_barcodes(parts.loc[needs, "barcode"], bc_map)
        missing = needs & obs[col].isna()
        if missing.any():
            common.log.warning("%d cells have no round-1 match for '%s' -> 'Unassigned'", missing.sum(), col)
            obs.loc[missing, col] = "Unassigned"

    apply_overrides(obs, lab.get("overrides"))
    obs["Unique"] = obs[lab["unique_id"]].astype(str).agg("_".join, axis=1)
    return obs.astype("category")


def main():
    cfg = common.start("10_label", __doc__)
    adata = sc.read_10x_mtx(cfg.path("combined_10x"), var_names="gene_symbols", cache=False)
    adata.var_names_make_unique()
    common.log.info("combined matrix: %d cells x %d genes", adata.n_obs, adata.n_vars)

    adata.obs = build_obs(adata, cfg)
    common.log_counts(adata)
    common.write_h5ad(adata, cfg, "fully_labelled")


if __name__ == "__main__":
    main()
