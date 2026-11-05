"""Run one stage of cell-type mapping for an Everyome run.

Called by each job as `python -m everyome.modules.spatial.deconvolution.stage <reference|map>` inside the run folder.
cell2location 0.1.5 runs in Everyome's own Python on the cluster (the 'deconvolution' extra: no maintained container
image exists), on a GPU when the job has one. On the demo cluster, stand-ins write the same files from the demo truth.

results/
  reference/signatures.csv       each cell type's expression per gene (the reference model's estimate)
  reference/training.csv         the reference model's training curve (round, loss)
  cell2location/abundance_mean.csv, abundance_q05.csv   cells of each type per spot (mean; 5% quantile, a cautious value)
  cell2location/training.csv     the mapping model's training curve
  cell2location/spots.h5ad       every spot with the full posterior summaries (real runs only)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _need_c2l():
    try:
        import cell2location  # noqa: F401
    except ImportError:
        raise RuntimeError("cell2location is not installed in Everyome's Python on the cluster. Ask IT to install "
                           "everyome[deconvolution] there (see the manual).") from None


def _accelerator() -> str:
    import torch
    return "gpu" if torch.cuda.is_available() else "cpu"


def _train(mod, **kw):
    """Train on the GPU when there is one (scvi-tools' newer 'accelerator' argument, or the older 'use_gpu')."""
    acc = _accelerator()
    if acc == "cpu":
        print("No GPU found: training on the CPU, which can take many hours.", flush=True)
    try:
        mod.train(accelerator=acc, **kw)
    except TypeError:
        mod.train(use_gpu=acc == "gpu", **kw)


def _history(mod, path: Path):
    h = mod.history.get("elbo_train")
    if h is not None:
        h.reset_index().set_axis(["round", "loss"], axis=1).to_csv(path, index=False)


def reference(params: dict, res: Path) -> None:
    out = res / "reference"
    out.mkdir(parents=True, exist_ok=True)
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.reference(params, out)
        return
    _need_c2l()
    import anndata as ad
    import scipy.sparse as sp
    from cell2location.models import RegressionModel
    from cell2location.utils.filtering import filter_genes
    a = ad.read_h5ad(params["reference"])
    labels, batch = params.get("labels_key") or "cell_type", (params.get("batch_key") or "").strip() or None
    for k in [labels] + ([batch] if batch else []):
        if k not in a.obs:
            raise ValueError(f"The reference has no column '{k}' in its cell table. Its columns: {', '.join(map(str, a.obs.columns))}.")
    X = a.X.data if sp.issparse(a.X) else a.X
    if (X % 1 != 0).any():
        raise ValueError("The reference's values are not whole numbers. cell2location needs raw counts; export the reference with raw counts.")
    print(f"Reference: {a.n_obs:,} cells, {a.obs[labels].nunique()} cell types, {a.n_vars:,} genes", flush=True)
    # Intent: the cell2location authors' gene filter (keep genes expressed in enough cells or highly in a few).
    a = a[:, filter_genes(a, cell_count_cutoff=5, cell_percentage_cutoff2=0.03, nonz_mean_cutoff=1.12)].copy()
    RegressionModel.setup_anndata(a, batch_key=batch, labels_key=labels)
    mod = RegressionModel(a)
    _train(mod, max_epochs=int(params.get("reference_epochs") or 250))
    a = mod.export_posterior(a, sample_kwargs={"num_samples": 1000, "batch_size": 2500})
    names = a.uns["mod"]["factor_names"]
    sig = a.varm["means_per_cluster_mu_fg"][[f"means_per_cluster_mu_fg_{n}" for n in names]].copy()
    sig.columns = names
    sig.to_csv(out / "signatures.csv", index_label="gene")
    _history(mod, out / "training.csv")
    print(f"Signatures for {len(names)} cell types over {len(sig):,} genes written.", flush=True)


def map_spots(params: dict, res: Path) -> None:
    out = res / "cell2location"
    out.mkdir(parents=True, exist_ok=True)
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.map_spots(params, out)
        return
    _need_c2l()
    import anndata as ad
    import pandas as pd
    from cell2location.models import Cell2location

    from everyome.modules.spatial.visium.engine import read_spaceranger
    sig = pd.read_csv(res / "reference" / "signatures.csv", index_col=0)
    parts = []
    for r in params["samples"]:
        a, _ = read_spaceranger(Path(r["outs"]))
        a.obs["sample"] = r["sample"]
        a.obs_names = [f"{r['sample']}:{b}" for b in a.obs_names]
        parts.append(a)
    vis = ad.concat(parts, join="inner")
    shared = vis.var_names.intersection(sig.index)
    if len(shared) < 200:
        raise ValueError(f"Only {len(shared)} genes are named the same in the reference and the sections. Check both use the same gene names (symbols or IDs).")
    print(f"{vis.n_obs:,} spots in {len(parts)} sections; {len(shared):,} genes shared with the reference", flush=True)
    vis, sig = vis[:, shared].copy(), sig.loc[shared]
    Cell2location.setup_anndata(vis, batch_key="sample")
    mod = Cell2location(vis, cell_state_df=sig, N_cells_per_location=float(params.get("cells_per_spot") or 30),
                        detection_alpha=float(params.get("detection_alpha") or 20))
    _train(mod, max_epochs=int(params.get("mapping_epochs") or 30000), batch_size=None, train_size=1)
    vis = mod.export_posterior(vis, sample_kwargs={"num_samples": 1000, "batch_size": mod.adata.n_obs})
    names = vis.uns["mod"]["factor_names"]
    for kind, key in (("mean", "means_cell_abundance_w_sf"), ("q05", "q05_cell_abundance_w_sf")):
        df = pd.DataFrame(vis.obsm[key].to_numpy(), columns=names)
        df.insert(0, "barcode", [n.split(":", 1)[1] for n in vis.obs_names])
        df.insert(0, "sample", vis.obs["sample"].values)
        df.to_csv(out / f"abundance_{kind}.csv", index=False, float_format="%.4f")
    _history(mod, out / "training.csv")
    vis.write_h5ad(out / "spots.h5ad")
    print("Cell abundance per spot written.", flush=True)


STAGES = {"reference": reference, "map": map_spots}


def main(name: str) -> None:
    run_dir = os.environ["EVERYOME_RUN_DIR"]
    params = json.loads(Path(os.environ["EVERYOME_PARAMS"]).read_text())
    res = Path(run_dir) / "results"
    res.mkdir(exist_ok=True)
    try:
        STAGES[name](params, res)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
