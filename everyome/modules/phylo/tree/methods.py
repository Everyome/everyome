"""Draft methods section for an alignment and tree building run, written from its record. The user edits it before use."""
from __future__ import annotations

STRATEGY = {"auto": "the strategy MAFFT chose automatically (--auto)", "linsi": "the L-INS-i strategy", "ginsi": "the G-INS-i strategy",
            "einsi": "the E-INS-i strategy", "fftns2": "the FFT-NS-2 strategy"}


def _version(rec: dict, name: str) -> str:
    c = next((x for x in rec.get("containers") or [] if x["name"] == name), None)
    return " " + c["image"].split(":")[1].split("--")[0] if c else ""


def _last(hist, action):
    return next((h for h in reversed(hist) if h["action"] == action), None)


def methods(rec: dict) -> str:
    s = {x["id"]: x["value"] for x in rec["settings"]}
    hist = (rec.get("session") or {}).get("history", [])
    info = _last(hist, "read the alignment and tree") or {}
    kind = "protein" if info.get("type") == "protein" else "DNA"
    n = f"{info['sequences']} {kind} sequences" if info.get("sequences") else f"{kind} sequences"
    P = []
    if s.get("already_aligned"):
        P.append(f"An existing alignment of {n} was used.")
    else:
        P.append(f"{n[0].upper() + n[1:]} were aligned with MAFFT{_version(rec, 'mafft')} (Katoh and Standley, 2013) using {STRATEGY.get(s.get('mafft_strategy'), s.get('mafft_strategy'))}"
                 + (f" and the options {s['mafft_extra']}" if s.get("mafft_extra") else "") + ".")
    cols = f" ({info['kept']:,} of {info['columns']:,} columns kept)" if info.get("columns") else ""
    tm = s.get("trim_method")
    if tm == "none":
        P[0] += f" The whole alignment{cols.replace(' kept', '')} was used without trimming."
    else:
        how = f"keeping columns in which at least {100 * float(s.get('min_present', 0.9)):g}% of sequences had a residue (-gt {s.get('min_present')})" if tm == "gap_threshold" else f"the {tm} method"
        P[0] += f" Poorly aligned and gap-rich columns were removed with trimAl{_version(rec, 'trimal')} (Capella-Gutiérrez et al., 2009) using {how}{cols}."
    model = info.get("model") or s.get("model")
    chosen = (f"the {model} model, selected by ModelFinder (Kalyaanamoorthy et al., 2017) according to {info.get('selected_by') or 'BIC'}"
              if str(s.get("model", "")).upper().startswith("MF") else f"the {model} model")
    sup = [x for x in ((f"{int(s['bootstrap']):,} ultrafast bootstrap replicates (UFBoot2; Hoang et al., 2018)" if s.get("bootstrap") else ""),
                       (f"the SH-like approximate likelihood ratio test with {int(s['alrt']):,} replicates (SH-aLRT; Guindon et al., 2010)" if s.get("alrt") else "")) if x]
    P.append(f"A maximum-likelihood tree was inferred with IQ-TREE{_version(rec, 'iqtree')} (Wong et al., 2025) under {chosen}"
             + (f"; branch support was assessed with {' and '.join(sup)}" if sup else "") + f" (random seed {s.get('seed')})."
             + (f" Other IQ-TREE options: {s['iqtree_extra']}." if s.get("iqtree_extra") else ""))
    if rec.get("containers") and not rec["run"].get("demo"):
        P.append("Each tool ran in a BioContainers image pinned by its SHA-256 digest ("
                 + "; ".join(c["label"] for c in rec["containers"]) + "), with Apptainer (Kurtzer et al., 2017), through Everyome "
                 f"(version {rec['everyome']}).")
    else:
        P.append(f"The analysis was run through Everyome (version {rec['everyome']}).")
    root = _last(hist, "rooted the tree") or ({"how": "outgroup", "tips": [x.strip() for x in s["outgroup"].split(",")]} if s.get("outgroup") else {"how": "midpoint"})
    ex = _last(hist, "exported the tree")
    if ex:
        root = ex.get("root") or root
    if hist:
        r = ("rooted on " + ", ".join(t.replace("_", " ") for t in root["tips"]) + " as the outgroup" if root["how"] == "outgroup"
             else "rooted at its midpoint (halfway along the longest path between two tips)" if root["how"] == "midpoint" else "shown as built (unrooted)")
        text = f"The tree was {r} and drawn in Everyome."
        if ex and ex.get("groups"):
            split = [g["value"] for g in ex["groups"] if g["n"] > 1 and not g["clade"]]
            text += (f" Sequences were grouped by {ex['colour_by']}" + (f"; {', '.join(split)} did not form a single clade." if split else "; each group formed a single clade."))
        P.append(text)
    return "\n\n".join(P) + "\n"
