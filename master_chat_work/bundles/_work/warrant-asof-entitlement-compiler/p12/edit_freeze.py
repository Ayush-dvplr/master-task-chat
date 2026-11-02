import sys
p = sys.argv[1]; s = open(p).read()
a = '''def build(root: Path, seed: int, scale: float, variant: str = "heldout", conv=None) -> None:
    g = generate(root, seed, scale, variant)
    attest_from_reference(root, g, seed)'''
b = '''def plant_freeze_ends(root: Path, seed: int, conv: dict) -> None:
    """Close a prod freeze window exactly where an approved grant in effect at as_of begins."""
    D = load(root)
    cfg = settle_config(D)[0]
    W = World(D, cfg, dict(conv, window="half"))
    W.profile("prod")
    E, spans = W.E, [(stamp(w["start"]), stamp(w["end"])) for w in D["freeze"] if w["env"] == "prod"]
    begins = sorted(t["begin"] for t in W.tk.values() if t["env"] == "prod" and "begin" in t)
    picks = []
    for rid in sorted(W.tk):
        t = W.tk[rid]
        if t["env"] != "prod" or t.get("state") != "approved" or not E - 20 * DAY < t["begin"] < E < t["end"]:
            continue
        lo = t["begin"] - 2 * HOUR
        if any(a <= t["begin"] + 2 * HOUR and lo <= b for a, b in spans + picks):
            continue
        if bisect.bisect_left(begins, lo) != bisect.bisect_left(begins, t["begin"]):
            continue
        picks.append((lo, t["begin"]))
    r = random.Random(seed * 11 + 5)
    picks = sorted(r.sample(picks, min(3, len(picks))))
    path = root / "freeze_windows.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["windows"] += [{"env": "prod", "start": iso_z(lo), "end": iso_z(hi), "reason": "change review"} for lo, hi in picks]
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


def build(root: Path, seed: int, scale: float, variant: str = "heldout", conv=None) -> None:
    g = generate(root, seed, scale, variant)
    if variant == "conv" and conv and conv.get("window") == "closed":
        plant_freeze_ends(root, seed, conv)
    attest_from_reference(root, g, seed)'''
assert s.count(a) == 1
s = s.replace(a, b)
open(p, "w").write(s); print("edit_freeze ok")
