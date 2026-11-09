"""Draft methods text for a qPCR analysis run, written from its record."""
from __future__ import annotations


def _and(xs: list) -> str:
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def methods(rec: dict) -> str:
    s = {x["id"]: x["value"] for x in rec["settings"]}
    hist = (rec.get("session") or {}).get("history", [])
    v = rec["software"].get("python") or {}
    last = lambda a: next((h for h in reversed(hist) if h["action"] == a), None)  # noqa: E731
    ex = last("exported results")
    if not ex:
        return f"qPCR analysis with the Everyome qPCR module (version {rec['module']['version']}) has not been exported yet.\n"
    refs = ex.get("references") or []
    control = ex.get("control") or "control"
    left = ex.get("excluded") or []
    sw = f"Everyome (version {rec['everyome']})" + (f" with SciPy {v['scipy']} and pandas {v['pandas']}" if v.get("scipy") and v.get("pandas") else "")
    text = f"Quantification cycle (Cq) values exported from the instrument were analysed with the qPCR module of {sw}. "
    text += (f"Technical replicates were averaged after checking their spread (standard deviation above {s['replicate_sd']} cycles flagged)"
             + (f"; {len(left)} well{'s' if len(left) != 1 else ''} ({', '.join(left)}) {'were' if len(left) != 1 else 'was'} left out. " if left else ". "))
    text += f"No-template controls were checked for signal before cycle {s['ntc_cutoff']}. "
    if s.get("method") == "delta_delta_cq":
        text += ("Relative expression was calculated with the 2^−ΔΔCq method (Livak & Schmittgen, 2001), assuming an amplification "
                 f"efficiency of {s['default_efficiency']}% for every primer pair")
    else:
        text += ("Amplification efficiencies were estimated from standard curves of serial dilutions as E = 10^(−1/slope) − 1, "
                 f"with {s['default_efficiency']}% assumed for targets without one, and relative quantities were calculated with "
                 "efficiency correction (Pfaffl, 2001; Hellemans et al., 2007)")
    if refs:
        text += f", normalised to the geometric mean of {'the reference gene' if len(refs) == 1 else 'the reference genes'} {_and(refs)}"
        if len(refs) > 1:
            text += ", whose stability was assessed with geNorm M values (Vandesompele et al., 2002)"
    text += (f". Fold changes are relative to the mean of the {control} samples. Groups were compared with Welch's t-test on "
             "log2 normalised relative quantities, with 95% confidence intervals from the same test and p-values adjusted across "
             "targets with the Benjamini–Hochberg method.")
    return text + "\n"
