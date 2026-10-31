"""Export every theme to the app: static/themes.json, static/fonts/*.woff2 and fonts.css.

Run after editing themes.py or species.py:  python design/themes/export_app_themes.py
Fonts are read from FONT_SRC (Fontsource woff2 files, SIL OFL).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from all_themes import ALL, GROUPS          # noqa: E402
from derive import mix, until               # noqa: E402
from themes import contrast                 # noqa: E402

STATIC = HERE.parents[1] / "everyome" / "static"
FONT_SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else STATIC / "fonts"   # default: reuse the fonts already bundled
SERIF = {"Playfair Display", "Source Serif 4", "Fraunces", "Cormorant Garamond", "DM Serif Display", "IBM Plex Serif", "Lora", "Crimson Pro",
         "EB Garamond", "Libre Baskerville", "Spectral", "Instrument Serif", "Young Serif", "Newsreader", "Bodoni Moda", "Gloock", "Alegreya"}


def stack(name, role, theme_id):
    # Intent: the house style prefers the desktop fonts named in the design system.
    if theme_id == "gothic":
        return {"display": 'Didot,"Bodoni 72","Playfair Display",Georgia,serif', "body": 'Georgia,"Source Serif 4",serif',
                "label": 'Optima,"Gill Sans","Gill Sans MT","Work Sans",sans-serif', "mono": '"JetBrains Mono","SF Mono",Menlo,monospace'}[role]
    generic = "monospace" if role == "mono" else "serif" if name in SERIF else "sans-serif"
    return f'"{name}",{generic}'


def palette(base, surface, need, toward):
    # Intent: 18 cluster colours from the species' 8, each readable against the plot background.
    ext = list(base)
    for i in range(len(base)):
        ext.append(mix(base[i], base[(i + 3) % len(base)], .5))
    ext += [mix(base[0], toward, .35), mix(base[1], toward, .35)]
    return [until(c, surface, need, toward) for c in ext[:18]]


def mode_vars(t, mode):
    m = t[mode]
    dark = mode == "dark"
    ok = until("#7FBF5A" if dark else "#3F6B2E", m["surface"], 4.6, "#FFFFFF" if dark else "#000000")
    return {
        "bone": m["bg"], "card": m["surface"], "parch": m["surface2"], "ink": m["ink"], "ink2": m["body"], "muted": m["muted"], "rule": m["rule"],
        "golddk": m["primary"], "gold": m["rulecol"], "goldlt": m["topbar_accent"], "crypt": m["topbar"], "plum": mix(m["topbar"], m["primary"], .28),
        "ox": m["accent"], "wine": m["accent"], "tinta": mix(m["surface"], m["rulecol"], .10), "tintb": mix(m["surface"], m["accent"], .09),
        "ok": ok, "topink": m["topbar_ink"], "disabled": mix(m["muted"], m["bg"], .45),
        "palette": palette(t["data"], m["surface"], 2.2 if dark else 2.0, "#FFFFFF" if dark else "#000000"),
    }


def main():
    out, families = [], set()
    for t in ALL:
        f = t["fonts"]
        families |= {f["display"], f["body"], f.get("label", f["body"]), f["mono"]}
        out.append({"id": t["id"], "name": t["name"], "species": t["species"], "common": t["common"], "group": t["group"],
                    "style": t.get("style", "classic"), "swatches": [c for c, _ in t["source"]],
                    "fonts": {r: stack(f.get(r, f["body"]), r, t["id"]) for r in ("display", "body", "label", "mono")},
                    "light": mode_vars(t, "light"), "dark": mode_vars(t, "dark")})
    (STATIC / "themes.json").write_text(json.dumps({"groups": GROUPS, "themes": out}, separators=(",", ":")))

    fdir = STATIC / "fonts"
    fdir.mkdir(exist_ok=True)
    css = ["/* Open-licensed fonts (SIL OFL) from Fontsource; licences in this folder. */"]
    for fam in sorted(families):
        slug = fam.lower().replace(" ", "-")
        for src in sorted(FONT_SRC.glob(f"{slug}-latin-*.woff2")):
            if src.resolve() != (fdir / src.name).resolve():
                shutil.copy(src, fdir / src.name)
            w, style = src.stem.split("-latin-")[1].split("-")
            css.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:{style};font-display:swap;src:url('{src.name}') format('woff2')}}")
        lic = FONT_SRC / f"{slug}-LICENSE"
        if lic.exists() and lic.resolve() != (fdir / lic.name).resolve():
            shutil.copy(lic, fdir / lic.name)
    (fdir / "fonts.css").write_text("\n".join(css) + "\n")
    print(len(out), "themes,", len(families), "font families,", len(list(fdir.glob('*.woff2'))), "font files")


if __name__ == "__main__":
    main()
