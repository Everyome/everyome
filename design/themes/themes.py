"""Everyome themes, named after cnidarians (carried over from SPLiTscape).

Each theme has light and dark token sets plus the species colours it is
drawn from. Palettes are built from each species' documented colouring;
see `source` for which part of the animal each colour represents.
"""

THEMES = [
    {"id": "gothic", "name": "Gothic Cream", "species": "House style", "common": "Cnidofest 2026 design system",
     "story": "The current SPLiTscape look, kept as the default.",
     "fonts": {"display": "Playfair Display", "body": "Source Serif 4", "label": "Work Sans", "mono": "JetBrains Mono",
               "note": "Desktop uses Didot / Georgia / Optima where installed."},
     "source": [("#0B090E", "crypt"), ("#32203A", "plum"), ("#C2A24A", "gold"), ("#8F7529", "gold dark"), ("#6E1B2B", "oxblood"), ("#F2ECE1", "bone")],
     "light": {"bg": "#F2ECE1", "surface": "#FBF7EF", "surface2": "#E7DECC", "ink": "#1C1620", "body": "#241C28", "muted": "#5A5260", "rule": "#D6CBB6",
               "primary": "#7A6322", "rulecol": "#C2A24A", "accent": "#6E1B2B", "highlight": "#C2A24A", "topbar": "#0B090E", "topbar_ink": "#F4EFE4", "topbar_accent": "#C2A24A"},
     "dark": {"bg": "#0E0A13", "surface": "#181222", "surface2": "#221A2C", "ink": "#F2ECE1", "body": "#E4DCCF", "muted": "#B9AEC0", "rule": "#3A3143",
              "primary": "#C9A24A", "rulecol": "#C9A24A", "accent": "#D2687B", "highlight": "#DFC684", "topbar": "#07050A", "topbar_ink": "#F4EFE4", "topbar_accent": "#C9A24A"},
     "data": ["#C2A24A", "#6E1B2B", "#32203A", "#8F7529", "#A83B50", "#5A5260", "#DFC684", "#0E8F8A"]},

    {"id": "hydractinia", "name": "Hydractinia", "species": "Hydractinia symbiolongicarpus", "common": "snail fur",
     "story": "Salmon feeding polyps and orange gonophores on a pale stolon mat, growing over a hermit crab's umber shell.",
     "fonts": {"display": "Fraunces", "body": "Source Serif 4", "label": "Work Sans", "mono": "JetBrains Mono"},
     "source": [("#E07A64", "feeding polyp"), ("#E99A6B", "gonophore"), ("#F4E3D3", "hypostome"), ("#F7F2EC", "stolon mat"), ("#6B4A34", "shell"), ("#5E7C74", "seawater")],
     "light": {"bg": "#F7F2EC", "surface": "#FFFDF9", "surface2": "#EFE4D8", "ink": "#2B1F1A", "body": "#33251F", "muted": "#6E5E55", "rule": "#E3D5C8",
               "primary": "#B4513C", "rulecol": "#E07A64", "accent": "#4E6B63", "highlight": "#E99A6B", "topbar": "#3A2A21", "topbar_ink": "#F7F2EC", "topbar_accent": "#F0A58C"},
     "dark": {"bg": "#1B1411", "surface": "#261C17", "surface2": "#30241E", "ink": "#F4E3D3", "body": "#EAD8C8", "muted": "#BFA898", "rule": "#3D2E26",
              "primary": "#E58A72", "rulecol": "#E58A72", "accent": "#8FB2A6", "highlight": "#F0B48A", "topbar": "#120D0B", "topbar_ink": "#F4E3D3", "topbar_accent": "#E58A72"},
     "data": ["#E07A64", "#6B4A34", "#5E7C74", "#E99A6B", "#A8503E", "#C9A88A", "#2F4A44", "#D9B8A8"]},

    {"id": "acropora", "name": "Acropora", "species": "Acropora spp.", "common": "staghorn coral",
     "story": "Violet and cobalt branch tips over ochre, algae-brown bases, in a turquoise lagoon above white sand.",
     "fonts": {"display": "Space Grotesk", "body": "IBM Plex Sans", "label": "Space Grotesk", "mono": "IBM Plex Mono"},
     "source": [("#6E5BB8", "branch tip"), ("#2D5DA8", "cobalt morph"), ("#C9A46B", "branch base"), ("#8A6A3F", "zooxanthellae"), ("#2FA4A8", "lagoon"), ("#F4F1EA", "sand")],
     "light": {"bg": "#F4F1EA", "surface": "#FFFFFF", "surface2": "#ECE8DF", "ink": "#1A1F33", "body": "#262B40", "muted": "#5B6178", "rule": "#DCD8CF",
               "primary": "#4F46A8", "rulecol": "#6E5BB8", "accent": "#1C7F83", "highlight": "#C9A46B", "topbar": "#1E2350", "topbar_ink": "#F4F1EA", "topbar_accent": "#9C8CF0"},
     "dark": {"bg": "#0E1222", "surface": "#171C33", "surface2": "#1F2541", "ink": "#EEF0FA", "body": "#DCE0F0", "muted": "#A7ADC8", "rule": "#2B3150",
              "primary": "#A397F2", "rulecol": "#8C7EEA", "accent": "#4CC6C8", "highlight": "#D9B57A", "topbar": "#080B17", "topbar_ink": "#EEF0FA", "topbar_accent": "#4CC6C8"},
     "data": ["#6E5BB8", "#2FA4A8", "#C9A46B", "#2D5DA8", "#8A6A3F", "#A99BE0", "#1C5E62", "#E2CFA4"]},

    {"id": "aurelia", "name": "Aurelia", "species": "Aurelia aurita", "common": "moon jelly",
     "story": "A milky, translucent bell with four lilac gonad rings and faint blue canals, drifting in open-water navy.",
     "fonts": {"display": "Cormorant Garamond", "body": "Karla", "label": "Karla", "mono": "JetBrains Mono"},
     "source": [("#E6ECF3", "bell"), ("#A98BD0", "gonad ring"), ("#E3A3C2", "rose morph"), ("#9BB7D4", "radial canal"), ("#5E7FA6", "oral arm"), ("#0E2238", "open water")],
     "light": {"bg": "#EEF2F7", "surface": "#FAFBFD", "surface2": "#E2E8F0", "ink": "#1B2436", "body": "#253047", "muted": "#5E6880", "rule": "#D5DCE7",
               "primary": "#6E50A8", "rulecol": "#A98BD0", "accent": "#B0507E", "highlight": "#9BB7D4", "topbar": "#0E2238", "topbar_ink": "#E6ECF3", "topbar_accent": "#C9B3EC"},
     "dark": {"bg": "#0A1626", "surface": "#12233A", "surface2": "#1A2D47", "ink": "#E6ECF3", "body": "#D5DEEA", "muted": "#9FB0C8", "rule": "#24364F",
              "primary": "#B79BE6", "rulecol": "#B79BE6", "accent": "#EBA6C8", "highlight": "#9BC2E6", "topbar": "#060E19", "topbar_ink": "#E6ECF3", "topbar_accent": "#B79BE6"},
     "data": ["#A98BD0", "#5E7FA6", "#E3A3C2", "#9BB7D4", "#6E50A8", "#C9D6E6", "#B0507E", "#2E4A6E"]},

    {"id": "physalia", "name": "Physalia", "species": "Physalia physalis", "common": "Portuguese man o' war",
     "story": "An iridescent float shading from blue through violet to a magenta crest, trailing ultramarine tentacles.",
     "fonts": {"display": "Syne", "body": "Manrope", "label": "Manrope", "mono": "JetBrains Mono"},
     "source": [("#4A78D8", "float base"), ("#8B5CD6", "float"), ("#D1479E", "crest"), ("#2A2F9E", "tentacles"), ("#5BC6E6", "sea surface"), ("#0B0D24", "deep")],
     "light": {"bg": "#F3F4FB", "surface": "#FFFFFF", "surface2": "#E8EAF6", "ink": "#15183A", "body": "#1F2347", "muted": "#595E85", "rule": "#D9DCF0",
               "primary": "#5B3FC4", "rulecol": "#8B5CD6", "accent": "#B0307A", "highlight": "#2C86B8", "topbar": "#1A1D5E", "topbar_ink": "#F3F4FB", "topbar_accent": "#F07CC4"},
     "dark": {"bg": "#0B0D24", "surface": "#151838", "surface2": "#1D2147", "ink": "#EEF0FF", "body": "#DCDFF7", "muted": "#A6AAD6", "rule": "#2A2E5C",
              "primary": "#A08BFF", "rulecol": "#A08BFF", "accent": "#F06FBE", "highlight": "#6FD0F0", "topbar": "#06071A", "topbar_ink": "#EEF0FF", "topbar_accent": "#F06FBE"},
     "data": ["#8B5CD6", "#4A78D8", "#D1479E", "#5BC6E6", "#2A2F9E", "#B79AF0", "#F2A3D3", "#1F6F9E"]},

    {"id": "actinia", "name": "Actinia", "species": "Actinia equina", "common": "beadlet anemone",
     "story": "A deep red column ringed with bright blue acrorhagi, closed on slate rock among olive rockweed.",
     "fonts": {"display": "DM Serif Display", "body": "DM Sans", "label": "DM Sans", "mono": "JetBrains Mono"},
     "source": [("#A1192B", "column"), ("#5C0E1A", "contracted"), ("#2E6BD6", "acrorhagi"), ("#3E444B", "slate rock"), ("#6C6B3A", "rockweed"), ("#ECEBE7", "barnacle")],
     "light": {"bg": "#F1EFEB", "surface": "#FFFFFF", "surface2": "#E6E2DC", "ink": "#241416", "body": "#2E1D1F", "muted": "#625557", "rule": "#DDD6D2",
               "primary": "#9E1A2C", "rulecol": "#A1192B", "accent": "#2559B8", "highlight": "#6C6B3A", "topbar": "#3A0A12", "topbar_ink": "#F1EFEB", "topbar_accent": "#6E9CF0"},
     "dark": {"bg": "#151012", "surface": "#21181A", "surface2": "#2B2022", "ink": "#F1ECEA", "body": "#E3DBD9", "muted": "#B5A6A8", "rule": "#3A2C2F",
              "primary": "#EE5A6E", "rulecol": "#E0485C", "accent": "#6E9CF0", "highlight": "#B5B37A", "topbar": "#0C0809", "topbar_ink": "#F1ECEA", "topbar_accent": "#6E9CF0"},
     "data": ["#A1192B", "#2E6BD6", "#6C6B3A", "#3E444B", "#D9606E", "#8DB0EE", "#5C0E1A", "#A9A88A"]},

    {"id": "tubastraea", "name": "Tubastraea", "species": "Tubastraea coccinea", "common": "orange cup coral, sun coral",
     "story": "Vivid orange polyps with yellow tentacles, opening at night in the shadow of reef overhangs.",
     "fonts": {"display": "Archivo", "body": "Work Sans", "label": "Archivo", "mono": "JetBrains Mono"},
     "source": [("#F08A1C", "polyp"), ("#F6C445", "tentacle"), ("#C9461B", "ember"), ("#E9B08A", "skeleton"), ("#5B3A26", "overhang"), ("#1E1612", "night reef")],
     "light": {"bg": "#FBF4EA", "surface": "#FFFFFF", "surface2": "#F3E6D4", "ink": "#2A1A10", "body": "#33221A", "muted": "#6F5A4A", "rule": "#EBDCC8",
               "primary": "#B53D0C", "rulecol": "#F08A1C", "accent": "#8A5A12", "highlight": "#F6C445", "topbar": "#2A1A10", "topbar_ink": "#FBF4EA", "topbar_accent": "#F6C445"},
     "dark": {"bg": "#17100B", "surface": "#231812", "surface2": "#2E2018", "ink": "#FBEFE1", "body": "#F0E2D2", "muted": "#C8AF98", "rule": "#3C2A1E",
              "primary": "#F59A3A", "rulecol": "#F59A3A", "accent": "#F6C445", "highlight": "#E2622B", "topbar": "#0D0805", "topbar_ink": "#FBEFE1", "topbar_accent": "#F6C445"},
     "data": ["#F08A1C", "#C9461B", "#F6C445", "#5B3A26", "#E9B08A", "#9C2F12", "#B88A2E", "#3A2418"]},

    {"id": "nematostella", "name": "Nematostella", "species": "Nematostella vectensis", "common": "starlet sea anemone",
     "story": "A translucent tan body with white-banded tentacles in brackish marsh mud; GFP and DAPI from the lab bench.",
     "fonts": {"display": "IBM Plex Serif", "body": "IBM Plex Sans", "label": "IBM Plex Sans", "mono": "IBM Plex Mono"},
     "source": [("#E7DAC1", "body wall"), ("#F6F1E6", "tentacle band"), ("#C99787", "mesentery"), ("#4E4433", "marsh mud"), ("#39B54A", "GFP"), ("#3F5FD9", "DAPI")],
     "light": {"bg": "#F4EFE5", "surface": "#FFFDF8", "surface2": "#EAE2D3", "ink": "#22201A", "body": "#2B2820", "muted": "#655E50", "rule": "#DED5C3",
               "primary": "#2E7D3A", "rulecol": "#39B54A", "accent": "#3550C4", "highlight": "#C99787", "topbar": "#2B261C", "topbar_ink": "#F4EFE5", "topbar_accent": "#7EE08C"},
     "dark": {"bg": "#0E0F0C", "surface": "#181A15", "surface2": "#20231C", "ink": "#EAE6DA", "body": "#DAD6CA", "muted": "#A9A493", "rule": "#2E3028",
              "primary": "#5BE36E", "rulecol": "#5BE36E", "accent": "#8C9EFF", "highlight": "#E0A99A", "topbar": "#050605", "topbar_ink": "#EAE6DA", "topbar_accent": "#5BE36E"},
     "data": ["#39B54A", "#3F5FD9", "#C99787", "#4E4433", "#E7DAC1", "#1F6B2A", "#8FA3F0", "#9C6B5E"]},
]


def _lum(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)




# ----------------------------------------------------------------------------
# Vivid, sans-serif themes: zoanthids and other fluorescent cnidarians.
# Dark mode suits these best: it reads like a reef tank under actinic light.
# ----------------------------------------------------------------------------
VIVID = [
    {"id": "anthopleura", "name": "Anthopleura", "species": "Anthopleura elegantissima", "common": "aggregating anemone",
     "story": "Hot-pink tentacle tips over a green column, in clonal carpets on intertidal rock; colours chosen to echo GitHub's pink and green.",
     "fonts": {"display": "Hanken Grotesk", "body": "Instrument Sans", "label": "Hanken Grotesk", "mono": "JetBrains Mono"},
     "source": [("#DB61A2", "tentacle tip"), ("#BF3989", "tip, deeper"), ("#2DA44E", "column"), ("#216E39", "column, shaded"), ("#9BE9A8", "pale morph"), ("#0D1117", "night rock")],
     "light": {"bg": "#F6F8FA", "surface": "#FFFFFF", "surface2": "#EFF2F5", "ink": "#1F2328", "body": "#24292F", "muted": "#59636E", "rule": "#D1D9E0",
               "primary": "#1A7F37", "rulecol": "#2DA44E", "accent": "#BF3989", "highlight": "#DB61A2", "topbar": "#1F2328", "topbar_ink": "#F6F8FA", "topbar_accent": "#3FB950"},
     "dark": {"bg": "#0D1117", "surface": "#161B22", "surface2": "#21262D", "ink": "#E6EDF3", "body": "#C9D1D9", "muted": "#9198A1", "rule": "#30363D",
              "primary": "#3FB950", "rulecol": "#2EA043", "accent": "#F778BA", "highlight": "#DB61A2", "topbar": "#010409", "topbar_ink": "#E6EDF3", "topbar_accent": "#F778BA"},
     "data": ["#2DA44E", "#BF3989", "#216E39", "#DB61A2", "#9BE9A8", "#8C1D5D", "#40C463", "#FFADDA"]},
    {"id": "zoanthus", "name": "Zoanthus", "species": "Zoanthus sociatus", "common": "green button polyp (zoanthid)",
     "story": "Fluorescent green oral discs with magenta skirts and orange mouths, glowing under actinic blue light.",
     "fonts": {"display": "Unbounded", "body": "Figtree", "label": "Figtree", "mono": "JetBrains Mono"},
     "source": [("#39E05C", "oral disc"), ("#E0219A", "skirt"), ("#FF7A1A", "mouth"), ("#F5E52A", "inner ring"), ("#3D4CFF", "actinic light"), ("#05070F", "tank night")],
     "light": {"bg": "#F4F7F2", "surface": "#FFFFFF", "surface2": "#E8EEE6", "ink": "#0E1410", "body": "#18201A", "muted": "#4F5B52", "rule": "#D3DDD4",
               "primary": "#0F7A2E", "rulecol": "#39E05C", "accent": "#B0127A", "highlight": "#FF7A1A", "topbar": "#05070F", "topbar_ink": "#F4F7F2", "topbar_accent": "#39E05C"},
     "dark": {"bg": "#05070F", "surface": "#0D1120", "surface2": "#141A2E", "ink": "#F2F5FF", "body": "#E0E5F5", "muted": "#9AA3C0", "rule": "#232A44",
              "primary": "#4DF07A", "rulecol": "#39E05C", "accent": "#FF5FC0", "highlight": "#FF9A3D", "topbar": "#020309", "topbar_ink": "#F2F5FF", "topbar_accent": "#4DF07A"},
     "data": ["#39E05C", "#E0219A", "#FF7A1A", "#3D4CFF", "#F5E52A", "#1FB5A8", "#A23CE0", "#FF5A5A"]},

    {"id": "kuroshio", "name": "Kuroshio", "species": "Zoanthus kuroshio", "common": "Kuroshio button polyp (zoanthid)",
     "story": "Hot-pink oral discs with orange centres and teal tentacle tips on purple columns.",
     "fonts": {"display": "Sora", "body": "Albert Sans", "label": "Sora", "mono": "JetBrains Mono"},
     "source": [("#FF3E8A", "oral disc"), ("#FF8A2B", "centre"), ("#19C2B0", "tentacle tip"), ("#7A2E8E", "column"), ("#F6C1D6", "disc edge"), ("#120A16", "crevice")],
     "light": {"bg": "#FBF3F5", "surface": "#FFFFFF", "surface2": "#F3E3E8", "ink": "#1E0F17", "body": "#2A1620", "muted": "#6B5560", "rule": "#EBD5DD",
               "primary": "#B3165A", "rulecol": "#FF3E8A", "accent": "#0B7268", "highlight": "#FF8A2B", "topbar": "#2A0E22", "topbar_ink": "#FBF3F5", "topbar_accent": "#FF7AB0"},
     "dark": {"bg": "#120A16", "surface": "#1D1222", "surface2": "#27192D", "ink": "#FBEFF4", "body": "#F0DFE7", "muted": "#C3A8B6", "rule": "#3A2640",
              "primary": "#FF6FA5", "rulecol": "#FF3E8A", "accent": "#3EE0CC", "highlight": "#FFA25A", "topbar": "#0A050C", "topbar_ink": "#FBEFF4", "topbar_accent": "#FF6FA5"},
     "data": ["#FF3E8A", "#19C2B0", "#FF8A2B", "#7A2E8E", "#F6C1D6", "#0E7F74", "#FFC53D", "#C2185B"]},

    {"id": "parazoanthus", "name": "Parazoanthus", "species": "Parazoanthus axinellae", "common": "yellow cluster anemone (zoanthid)",
     "story": "Bright yellow polyps carpeting blue-grey sponges in deep Mediterranean blue, beside green seagrass.",
     "fonts": {"display": "Bricolage Grotesque", "body": "Rubik", "label": "Rubik", "mono": "JetBrains Mono"},
     "source": [("#FFD21F", "polyp"), ("#FFA81A", "tentacle base"), ("#6E86A6", "sponge"), ("#0F3D7A", "deep water"), ("#3E6B3A", "seagrass"), ("#F7F4E6", "sunlit sand")],
     "light": {"bg": "#F7F6EE", "surface": "#FFFFFF", "surface2": "#EEEBDD", "ink": "#121A2B", "body": "#1C2436", "muted": "#545D70", "rule": "#DCD8C8",
               "primary": "#0F3D7A", "rulecol": "#FFC300", "accent": "#7A4F00", "highlight": "#FFD21F", "topbar": "#0F3D7A", "topbar_ink": "#F7F6EE", "topbar_accent": "#FFD21F"},
     "dark": {"bg": "#061229", "surface": "#0D1D3A", "surface2": "#142748", "ink": "#F4F1E2", "body": "#E3E1D3", "muted": "#A3AEC4", "rule": "#22355A",
              "primary": "#FFD21F", "rulecol": "#FFD21F", "accent": "#FFA81A", "highlight": "#8FB0DA", "topbar": "#030A18", "topbar_ink": "#F4F1E2", "topbar_accent": "#FFD21F"},
     "data": ["#FFD21F", "#0F3D7A", "#FFA81A", "#6E86A6", "#3E6B3A", "#FFE98A", "#2F6FBF", "#B07A10"]},

    {"id": "palythoa", "name": "Palythoa", "species": "Palythoa grandis", "common": "giant sea mat (zoanthid)",
     "story": "Violet and electric-purple discs edged in bright green, with blue glints under reef lights.",
     "fonts": {"display": "Outfit", "body": "Plus Jakarta Sans", "label": "Outfit", "mono": "JetBrains Mono"},
     "source": [("#8E3FE0", "oral disc"), ("#B266FF", "disc glow"), ("#2FD67B", "rim"), ("#3A6BFF", "glint"), ("#C9A3E8", "tentacles"), ("#0D0A1A", "shadow")],
     "light": {"bg": "#F5F3FA", "surface": "#FFFFFF", "surface2": "#EAE6F4", "ink": "#17122A", "body": "#211B36", "muted": "#5C5576", "rule": "#DCD6EA",
               "primary": "#6A23C2", "rulecol": "#8E3FE0", "accent": "#0F6E3F", "highlight": "#3A6BFF", "topbar": "#1C1238", "topbar_ink": "#F5F3FA", "topbar_accent": "#3FE38F"},
     "dark": {"bg": "#0D0A1A", "surface": "#17122A", "surface2": "#201A38", "ink": "#F3F0FF", "body": "#E2DDF5", "muted": "#A9A2C8", "rule": "#2F2850",
              "primary": "#B98AFF", "rulecol": "#B266FF", "accent": "#3FE38F", "highlight": "#6F95FF", "topbar": "#07050F", "topbar_ink": "#F3F0FF", "topbar_accent": "#3FE38F"},
     "data": ["#8E3FE0", "#2FD67B", "#3A6BFF", "#C9A3E8", "#B266FF", "#1F9E5C", "#6F95FF", "#E07AFF"]},

    {"id": "corynactis", "name": "Corynactis", "species": "Corynactis viridis", "common": "jewel anemone",
     "story": "Neon pink, emerald and orange polyps with white club-tipped tentacles, packed on dark Atlantic rock.",
     "fonts": {"display": "Red Hat Display", "body": "Red Hat Text", "label": "Red Hat Display", "mono": "JetBrains Mono"},
     "source": [("#FF4FA3", "pink morph"), ("#12C77A", "emerald morph"), ("#FF7B29", "orange morph"), ("#B98CE8", "lilac morph"), ("#FFF6F0", "club tips"), ("#1A1D24", "rock")],
     "light": {"bg": "#F6F6F4", "surface": "#FFFFFF", "surface2": "#ECECE8", "ink": "#15171C", "body": "#1F2228", "muted": "#565A63", "rule": "#DADBD6",
               "primary": "#C0186E", "rulecol": "#FF4FA3", "accent": "#0A7348", "highlight": "#FF7B29", "topbar": "#1A1D24", "topbar_ink": "#F6F6F4", "topbar_accent": "#FF7AB8"},
     "dark": {"bg": "#101216", "surface": "#191C22", "surface2": "#22262E", "ink": "#F6F6F4", "body": "#E4E5E2", "muted": "#A8ABB2", "rule": "#30343D",
              "primary": "#FF6FB5", "rulecol": "#FF4FA3", "accent": "#2EE596", "highlight": "#FF9A55", "topbar": "#08090B", "topbar_ink": "#F6F6F4", "topbar_accent": "#2EE596"},
     "data": ["#FF4FA3", "#12C77A", "#FF7B29", "#B98CE8", "#FFD0E6", "#0B7F4E", "#FFB27A", "#7A4FC4"]},

    {"id": "ricordea", "name": "Ricordea", "species": "Ricordea florida", "common": "Florida false coral (mushroom)",
     "story": "Neon-green bubbly discs with orange centres and electric-blue edges, on a purple base.",
     "fonts": {"display": "Urbanist", "body": "Chivo", "label": "Urbanist", "mono": "JetBrains Mono"},
     "source": [("#6BE33A", "disc"), ("#FF8C1A", "centre"), ("#2F7BFF", "edge"), ("#22D3E0", "bubbles"), ("#6A3FA0", "base"), ("#071019", "reef night")],
     "light": {"bg": "#F3F7F4", "surface": "#FFFFFF", "surface2": "#E5EEE8", "ink": "#0F1A16", "body": "#18241F", "muted": "#4E5E57", "rule": "#D2DFD8",
               "primary": "#2A7012", "rulecol": "#6BE33A", "accent": "#1F5FD0", "highlight": "#FF8C1A", "topbar": "#071019", "topbar_ink": "#F3F7F4", "topbar_accent": "#6BE33A"},
     "dark": {"bg": "#071019", "surface": "#0E1A25", "surface2": "#152433", "ink": "#EEF6F2", "body": "#DCE8E2", "muted": "#9DB2AA", "rule": "#1F3242",
              "primary": "#7FF04F", "rulecol": "#6BE33A", "accent": "#5FA2FF", "highlight": "#FFA040", "topbar": "#03080C", "topbar_ink": "#EEF6F2", "topbar_accent": "#22D3E0"},
     "data": ["#6BE33A", "#2F7BFF", "#FF8C1A", "#22D3E0", "#6A3FA0", "#C7F59E", "#1F5FD0", "#FFC680"]},
]
THEMES = THEMES + VIVID


if __name__ == "__main__":
    # Intent: check WCAG contrast for the pairs the interface relies on.
    for t in THEMES:
        for mode in ("light", "dark"):
            m = t[mode]
            checks = {"ink/bg": (m["ink"], m["bg"], 7), "body/surface": (m["body"], m["surface"], 7), "muted/surface": (m["muted"], m["surface"], 4.5),
                      "primary/surface": (m["primary"], m["surface"], 4.5), "accent/surface": (m["accent"], m["surface"], 4.5),
                      "topbar ink": (m["topbar_ink"], m["topbar"], 7), "topbar accent": (m["topbar_accent"], m["topbar"], 4.5)}
            bad = {k: round(contrast(a, b), 2) for k, (a, b, need) in checks.items() if contrast(a, b) < need}
            print(f"{t['id']:12s} {mode:5s}", "OK" if not bad else bad)
