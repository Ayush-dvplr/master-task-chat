import sys
p = sys.argv[1]; s = open(p).read()
R = [
('''CONV_TIERS = (("conv_1", 91019, "Site/Dune"), ("conv_2", 85041, "Site/Dune"), ("conv_3", 93029, "Site/Ember"),
              ("conv_4", 96043, "Site/Cobalt"), ("conv_5", 92023, "Site/Brisk"), ("conv_6", 98053, "Site/Brisk"),
              ("conv_7", 94031, "Site/Arden"), ("conv_8", 99061, "Site/Arden"))''',
'''CONV_TIERS = (("conv_1", 91019, "Site/Dune", "half"), ("conv_2", 85041, "Site/Dune", "closed"),
              ("conv_3", 93029, "Site/Ember", "half"), ("conv_4", 96043, "Site/Cobalt", "half"),
              ("conv_5", 92023, "Site/Brisk", "half"), ("conv_6", 98053, "Site/Brisk", "closed"),
              ("conv_7", 94031, "Site/Arden", "half"), ("conv_8", 99061, "Site/Arden", "closed"))


def _conv_of(name: str) -> dict:
    for tier, _, zone, window in CONV_TIERS:
        if tier == name:
            return {"hr": "zone:" + zone, "start": "requested", "window": window}
    raise KeyError(name)'''),
('''        for tier, seed, zone in CONV_TIERS:
            if tier == name:
                root = _scratch(f"warrant-{tier}-")
                build(root, seed, 0.05, "conv", {"hr": "zone:" + zone, "start": "requested"})''',
'''        for tier, seed, _, _ in CONV_TIERS:
            if tier == name:
                root = _scratch(f"warrant-{tier}-")
                build(root, seed, 0.05, "conv", _conv_of(name))'''),
('''        zone = dict((tier, z) for tier, _, z in CONV_TIERS)[name]
        cfg, profiles, audit, summary, _ = everything(root, {"hr": "zone:" + zone, "start": "requested"})''',
'''        cfg, profiles, audit, summary, _ = everything(root, _conv_of(name))'''),
]
for a, b in R:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(p, "w").write(s)
print("edit_conv ok")
