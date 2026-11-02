"""Score a program's outputs against reference outputs, per check family, per field.
Usage: scoreblind.py scratch_root   (expects <c>/ref_out, <c>/blind_out, <c>/abstract.json)
Hidden families per corpus: audit w5, regions w5, segments w5, summary w5 (empty-axis corpora:
live part w4 + empty part w1 for regions, segments, summary); data_quality w3 (not a lever family)."""
import json
import os
import sys

BASES = ["North", "South", "West", "East"]
SEGS = ["commercial", "public"]


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:  # missing or bad file counts as wrong
        return {"__error__": str(e)}


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return path or "/"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return path + "/" + k
            d = first_diff(a[k], b[k], path + "/" + k)
            if d:
                return d
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None if len(a) == len(b) else path + "[len]"
    return None if a == b else path or "/"


def corpus(root, name):
    d = os.path.join(root, name)
    meta = load(os.path.join(d, "abstract.json")).get("meta", {})
    eb = meta.get("empty_base")
    es = "public" if meta.get("empty_segment") else None
    R = lambda f: load(os.path.join(d, "ref_out", f))
    B = lambda f: load(os.path.join(d, "blind_out", f))
    rows = []

    def chk(fam, w, fr, ref, got):
        fd = first_diff(ref, got)
        rows.append((name, fam, w, fd is None, fd and fr + fd))

    chk("audit", 5, "check_plan.json", R("check_plan.json"), B("check_plan.json"))
    rf = lambda b: "regions/region_%s.json" % b.lower()
    sf = lambda s: "segments/segment_%s.json" % s
    live_b = [b for b in BASES if b != eb]
    live_s = [s for s in SEGS if s != es]
    wl = 4 if eb else 5
    chk("regions", wl, "regions", [R(rf(b)) for b in live_b], [B(rf(b)) for b in live_b])
    if eb:
        chk("region_empty", 1, rf(eb), R(rf(eb)), B(rf(eb)))
    chk("segments", 4 if es else 5, "segments", [R(sf(s)) for s in live_s], [B(sf(s)) for s in live_s])
    if es:
        chk("segment_empty", 1, sf(es), R(sf(es)), B(sf(es)))
    rs, bs = R("plan_summary.json"), B("plan_summary.json")
    if eb or es:
        def split(s):
            s = dict(s)
            emp = {"bases": [x for x in s.get("bases", []) if x.get("base") == eb],
                   "segments": [x for x in s.get("segments", []) if x.get("segment") == es]}
            s["bases"] = [x for x in s.get("bases", []) if x.get("base") != eb]
            s["segments"] = [x for x in s.get("segments", []) if x.get("segment") != es]
            return s, emp
        (rl, re_), (bl, be) = split(rs), split(bs)
        chk("summary", 4, "plan_summary.json", rl, bl)
        chk("summary_empty_rows", 1, "plan_summary.json", re_, be)
    else:
        chk("summary", 5, "plan_summary.json", rs, bs)
    chk("data_quality", 3, "data_quality.json", R("data_quality.json"), B("data_quality.json"))
    t = lambda s: s.get("plan_terms") if isinstance(s, dict) else None
    return rows, t(rs), t(bs)


root = sys.argv[1]
tot = {}
for name in sorted(os.listdir(root)):
    if not os.path.isdir(os.path.join(root, name, "ref_out")):
        continue
    rows, rt, bt = corpus(root, name)
    lever = [r for r in rows if r[1] != "data_quality"]
    kept = sum(r[2] for r in lever if r[3])
    allw = sum(r[2] for r in lever)
    print("CORPUS %s ref_terms=%s blind_terms=%s lever_kept=%d/%d" % (name, rt, bt, kept, allw))
    for r in rows:
        print("  %-20s w%d %s %s" % (r[1], r[2], "EXACT" if r[3] else "WRONG", r[4] or ""))
    if name != "shipped":
        tot["k"] = tot.get("k", 0) + kept
        tot["a"] = tot.get("a", 0) + allw
print("HIDDEN lever kept %d/%d = %.0f%%" % (tot["k"], tot["a"], 100.0 * tot["k"] / tot["a"]))
