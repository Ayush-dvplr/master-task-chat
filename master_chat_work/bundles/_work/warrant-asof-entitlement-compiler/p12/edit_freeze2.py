import sys
p = sys.argv[1]; s = open(p).read()
R = [
('''    W.profile("prod")
    E, spans''', '''    keys = W.profile("prod")["keys"]
    E, spans'''),
('''        if bisect.bisect_left(begins, lo) != bisect.bisect_left(begins, t["begin"]):
            continue
        picks.append((lo, t["begin"]))
    r = random.Random(seed * 11 + 5)
    picks = sorted(r.sample(picks, min(3, len(picks))))''',
'''        if bisect.bisect_left(begins, lo) != bisect.bisect_left(begins, t["begin"]):
            continue
        t["state"] = "frozen"
        moved = W.profile("prod")["keys"] != keys
        t["state"] = "approved"
        if moved:
            picks.append((lo, t["begin"]))
    r = random.Random(seed * 11 + 5)
    picks = sorted(r.sample(picks, min(3, len(picks))))'''),
('''    if variant == "conv" and conv and conv.get("window") == "closed":
        plant_freeze_ends(root, seed, conv)
    attest_from_reference(root, g, seed)''', '''    attest_from_reference(root, g, seed)
    if variant == "conv" and conv and conv.get("window") == "closed":
        plant_freeze_ends(root, seed, conv)'''),
]
for a, b in R:
    assert s.count(a) == 1, a[:50]
    s = s.replace(a, b)
open(p, "w").write(s); print("edit_freeze2 ok")
