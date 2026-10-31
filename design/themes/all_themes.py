"""Every Everyome theme, ordered by group."""
from themes import THEMES
from species import SPECIES, G_ANEM, G_CORAL, G_ZOA, G_OCTO, G_BLACK, G_HYD, G_SCY, G_BOX, G_PARA
from derive import build

GROUPS = ["House style", G_ANEM, G_ZOA, G_CORAL, G_OCTO, G_BLACK, G_HYD, G_SCY, G_BOX, G_PARA]
HAND = {"gothic": "House style", "hydractinia": G_HYD, "acropora": G_CORAL, "aurelia": G_SCY, "physalia": G_HYD,
        "actinia": G_ANEM, "tubastraea": G_CORAL, "nematostella": G_ANEM, "zoanthus": G_ZOA, "kuroshio": G_ZOA,
        "parazoanthus": G_ZOA, "palythoa": G_ZOA, "corynactis": G_ZOA, "ricordea": G_ZOA}
VIVID_IDS = {"zoanthus", "kuroshio", "parazoanthus", "palythoa", "corynactis", "ricordea"}

ALL = [{**t, "group": HAND[t["id"]], "style": "vivid" if t["id"] in VIVID_IDS else "classic"} for t in THEMES] + [build(s) for s in SPECIES]
ALL.sort(key=lambda t: (GROUPS.index(t["group"]), t["id"] != "gothic", t["name"]))
