"""Turn six species colours into full light and dark token sets.

Text colours are pushed darker (light mode) or lighter (dark mode) until they
meet WCAG AA against the surface they sit on; decorative colours keep the
animal's own hue.
"""
from themes import contrast


def rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def hexs(c):
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in c)


def mix(a, b, t):
    """t=0 -> a, t=1 -> b."""
    return hexs([x + (y - x) * t for x, y in zip(rgb(a), rgb(b))])


def until(c, against, need, toward):
    """Move colour c toward black/white in small steps until contrast >= need."""
    for k in range(41):
        out = mix(c, toward, k / 40)
        if contrast(out, against) >= need:
            return out
    return toward


def build(sp):
    src = [h for h, _ in sp["source"]]
    sig, acc, hl, pale, dark = src[0], src[1], src[2], src[4], src[5]
    vivid = sp["style"] == "vivid"

    # ---------------- light mode
    bg = mix("#FFFFFF", mix(pale, sig, .15), .10 if vivid else .16)
    surface = mix("#FFFFFF", bg, .25)
    ink = until(mix(dark, sig, .12), bg, 12, "#000000")
    light = {
        "bg": bg, "surface": surface, "surface2": mix(bg, sig, .08), "ink": ink, "body": mix(ink, bg, .08),
        "muted": until(mix(ink, bg, .62), surface, 4.6, ink), "rule": mix(bg, ink, .13),
        "primary": until(sig, surface, 4.6, "#000000"), "rulecol": sig,
        "accent": until(acc, surface, 4.6, "#000000"), "highlight": hl,
        "topbar": until(mix(dark, sig, .18), "#FFFFFF", 12, "#000000"), "topbar_ink": mix("#FFFFFF", pale, .4),
    }
    light["topbar_accent"] = until(mix(sig, "#FFFFFF", .15), light["topbar"], 4.6, "#FFFFFF")

    # ---------------- dark mode
    dbg = until(mix(dark, sig, .06), "#FFFFFF", 16, "#000000")
    dsurf = mix(dbg, sig, .07)
    dink = until(mix(pale, "#FFFFFF", .5), dbg, 13, "#FFFFFF")
    dark_t = {
        "bg": dbg, "surface": dsurf, "surface2": mix(dbg, sig, .12), "ink": dink, "body": mix(dink, dbg, .08),
        "muted": until(mix(dink, dbg, .45), dsurf, 4.6, dink), "rule": mix(dbg, dink, .14),
        "primary": until(sig, dsurf, 4.8, "#FFFFFF"), "rulecol": until(sig, dbg, 3.2, "#FFFFFF"),
        "accent": until(acc, dsurf, 4.8, "#FFFFFF"), "highlight": until(hl, dsurf, 3.2, "#FFFFFF"),
        "topbar": mix(dbg, "#000000", .45), "topbar_ink": dink,
    }
    dark_t["topbar_accent"] = until(sig, dark_t["topbar"], 4.8, "#FFFFFF")

    data = [src[0], src[1], src[2], src[3], mix(src[0], src[1], .5), mix(src[2], src[0], .5), mix(src[3], "#FFFFFF", .35), mix(src[1], "#000000", .3)]
    return {**sp, "fonts": {"display": sp["display"], "body": sp["body"], "label": sp["body"], "mono": "JetBrains Mono"},
            "light": light, "dark": dark_t, "data": data}


if __name__ == "__main__":
    from species import SPECIES
    bad = 0
    for sp in SPECIES:
        t = build(sp)
        for mode in ("light", "dark"):
            m = t[mode]
            for k, a, b, need in [("ink", m["ink"], m["bg"], 7), ("body", m["body"], m["surface"], 7), ("muted", m["muted"], m["surface"], 4.5),
                                  ("primary", m["primary"], m["surface"], 4.5), ("accent", m["accent"], m["surface"], 4.5),
                                  ("topbar", m["topbar_ink"], m["topbar"], 7), ("top accent", m["topbar_accent"], m["topbar"], 4.5)]:
                if contrast(a, b) < need:
                    bad += 1; print(sp["id"], mode, k, round(contrast(a, b), 2))
    print(len(SPECIES), "species,", bad, "contrast failures")
