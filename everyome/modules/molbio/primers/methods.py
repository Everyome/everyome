"""Draft methods text for a primer design run, written from its record."""
from __future__ import annotations


def methods(rec: dict) -> str:
    s = {x["id"]: x["value"] for x in rec["settings"]}
    hist = (rec.get("session") or {}).get("history", [])
    v = (rec["software"].get("python") or {})
    p3 = v.get("primer3")
    designs = [h for h in hist if h["action"] == "designed primers"]
    if not designs:
        return f"Primer design with the Everyome Primer design module (version {rec['module']['version']}) has not been run yet.\n"
    d = designs[-1]
    t = d.get("target")
    where = f" flanking positions {t['start']}–{t['end']}" + (f" ({t['label']})" if t.get("label") else "") if t else ""
    text = (f"PCR primers{where} were designed with Primer3 (Untergasser et al., 2012) through primer3-py"
            f"{f' (version {p3})' if p3 else ''} in Everyome (version {rec['everyome']}), for products of {s['product_min']}–{s['product_max']} bp, "
            f"primers of {s['size_min']}–{s['size_max']} nt (optimum {s['size_opt']}), melting temperatures of {s['tm_min']}–{s['tm_max']} °C "
            f"(optimum {s['tm_opt']} °C) and {s['gc_min']}–{s['gc_max']}% GC, calculated for {s['mv_conc']} mM monovalent cations, "
            f"{s['dv_conc']} mM Mg2+, {s['dntp_conc']} mM dNTPs and {s['dna_conc']} nM primer.")
    extra = [ln.strip() for ln in (s.get("extra_primer3") or "").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if extra:
        text += " Other Primer3 settings: " + "; ".join(extra) + "."
    ex = [h for h in hist if h["action"] == "exported primers"]
    if ex:
        text += f" The pair{'s' if len(ex[-1]['chosen']) > 1 else ''} used {'were' if len(ex[-1]['chosen']) > 1 else 'was'} " \
                f"{', '.join(ex[-1]['order'])}."
    return text + "\n"
