import sys, re
p = sys.argv[1]; s = open(p).read()
i = s.index("def plant_freeze_ends("); j = s.index("\ndef build(", i)
new = '''def plant_freeze_ends(root: Path, seed: int, conv: dict) -> None:
    """End a freeze window exactly where a grant in effect at as_of begins."""
    D = load(root)
    cfg = settle_config(D)[0]
    W = World(D, cfg, dict(conv, window="half"))
    E, picks = W.E, []
    for env in GATE_ENVS:
        if not cfg[env + ".freeze_applies"]:
            continue
        keys = W.profile(env)["keys"]
        spans = [(stamp(w["start"]), stamp(w["end"])) for w in D["freeze"] if w["env"] == env]
        begins = sorted(t["begin"] for t in W.tk.values() if t["env"] == env and "begin" in t)
        for rid in sorted(W.tk):
            t = W.tk[rid]
            if t["env"] != env or t.get("state") != "approved" or not E - 20 * DAY < t["begin"] < E < t["end"]:
                continue
            lo = t["begin"] - 2 * HOUR
            if any(a <= t["begin"] + 2 * HOUR and lo <= b for a, b in spans + [(x, y) for e, x, y in picks if e == env]):
                continue
            if bisect.bisect_left(begins, lo) != bisect.bisect_left(begins, t["begin"]):
                continue
            t["state"] = "frozen"
            moved = W.profile(env)["keys"] != keys
            t["state"] = "approved"
            if moved:
                picks.append((env, lo, t["begin"]))
    r = random.Random(seed * 11 + 5)
    picks = sorted(r.sample(picks, min(3, len(picks))))
    path = root / "freeze_windows.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["windows"] += [{"env": env, "start": iso_z(lo), "end": iso_z(hi), "reason": "change review"} for env, lo, hi in picks]
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\\n", encoding="utf-8")

'''
s = s[:i] + new + s[j:]
open(p, "w").write(s); print("edit_freeze3 ok")
