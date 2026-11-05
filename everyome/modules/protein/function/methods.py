"""Draft methods section for a protein function annotation run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last, setting


def _version(rec: dict) -> str:
    c = next((x for x in rec.get("containers") or [] if x["name"] == "interproscan"), None)
    return " " + c["image"].split(":")[1] if c else ""


def methods(rec: dict) -> str:
    hist = (rec.get("session") or {}).get("history", [])
    apps = setting(rec, "applications", "")
    extra = [x for x, k in (("GO terms", "goterms"), ("pathways (MetaCyc, Reactome)", "pathways")) if setting(rec, k, True)]
    P = [f"Proteins were annotated with InterProScan{_version(rec)} (Jones et al., 2014; Blum et al., 2025), run through Everyome "
         f"(version {rec['everyome']}) in its official container image, searching "
         + (f"{apps}" if apps else "all member databases available in its data release")
         + (" and adding " + " and ".join(extra) if extra else "") + "."
         + ("" if setting(rec, "lookup", False) else " The lookup service for precalculated matches was disabled, so all searches ran locally.")]
    ov = last(hist, "read InterProScan results")
    if ov:
        P.append(f"Of {ov['proteins']:,} proteins, {ov['with_match']:,} ({100 * ov['with_match'] / max(1, ov['proteins']):.0f}%) matched at least one "
                 f"signature, {ov['with_interpro']:,} an InterPro entry and {ov['with_go']:,} at least one GO term "
                 f"({ov['matches']:,} matches in total).")
    return "\n\n".join(P) + "\n"
