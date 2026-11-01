"""Shared methods text for the genome assembly modules: the choice made in the live session. Kept free of heavy imports."""
from __future__ import annotations


def bp(n: int) -> str:
    return f"{n / 1e6:.2f} Mb" if n >= 1e6 else f"{n / 1e3:.1f} kb" if n >= 1e3 else f"{n} bp"


def assembly_paragraphs(hist: list) -> list[str]:
    chosen = [h for h in hist if h["action"] == "chose the final assembly"]
    if not chosen:
        return []
    c = chosen[-1]
    text = (f"Assembly statistics were computed in Everyome, and {c['label']} was chosen as the final assembly "
            f"({bp(c['total'])} in {c['contigs']:,} contigs, N50 {bp(c['n50'])}"
            + (f"; BUSCO {c['busco']:.1f}% complete, {c['lineage']}" if c.get("busco") is not None else "") + ").")
    if c.get("reason"):
        text += f" Reason recorded: {c['reason'].rstrip('.')}."
    return [text]
