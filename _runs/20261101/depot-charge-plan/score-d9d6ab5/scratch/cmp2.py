import json, sys, os
ref, got = sys.argv[1], sys.argv[2]
def first(a, b, p=""):
    if type(a) != type(b): return p or "/"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b: return p + "/" + k
            d = first(a[k], b[k], p + "/" + k)
            if d: return d
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first(x, y, "%s[%d]" % (p, i))
            if d: return d
        return None if len(a) == len(b) else p + "/len"
    return None if a == b else (p or "/")
def load(d, n):
    try: return json.load(open(os.path.join(d, n)))
    except Exception: return None
FAM = {"audit": ["policy_audit.json"],
       "regions": ["region_%s.json" % d for d in ("North", "South", "West", "East")],
       "segsum": ["segment_commercial.json", "segment_public.json", "summary.json"],
       "quality": ["data_quality.json"]}
res = []
for fam, files in FAM.items():
    diffs = []
    for n in files:
        g = load(got, n)
        if g is None: diffs.append(n + " MISSING"); continue
        d = first(load(ref, n), g)
        if d: diffs.append(n + d)
    res.append("%s=%s" % (fam, "OK" if not diffs else "WRONG(" + diffs[0] + ")"))
# audit row detail
ra, ga = load(ref, "policy_audit.json"), load(got, "policy_audit.json")
if ra and ga:
    rb = {b["bus_id"]: b for b in ra["buses"]}; gb = {b["bus_id"]: b for b in ga.get("buses", [])}
    nd = sum(1 for k in rb if rb[k] != gb.get(k))
    ndc = sum(1 for k in rb if gb.get(k) and rb[k]["charges"] != gb[k]["charges"])
    res.append("audit_rows_diff %d/%d charges_diff %d" % (nd, len(rb), ndc))
rs, gs = load(ref, "summary.json"), load(got, "summary.json")
if rs and gs:
    res.append("sum ref[%s,%s,%s] got[%s,%s,%s]" % tuple([rs.get(k) for k in ("weighted_unmet_kwh","energy_cost_cents","moved_kwh")] + [gs.get(k) for k in ("weighted_unmet_kwh","energy_cost_cents","moved_kwh")]))
print(" ".join(res))
