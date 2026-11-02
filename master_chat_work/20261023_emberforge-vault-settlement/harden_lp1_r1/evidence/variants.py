"""Lever variants of the tests engine and per-document separation table.
usage: variants.py <bundle> [season...]   (seasons from T.SEASONS; 'visible' allowed)"""
import sys, pathlib, tempfile, shutil, json
from tk import load_T
B = pathlib.Path(sys.argv[1])
SUBS = {
 "L7_total_then_ops": [('        value = art["base_charge"]\n', '        value = art["base_charge"] * entry["units"]\n'),
                       ('        return value * entry["units"]\n', '        return value\n')],
 "L6_window_all_settled": [('                    and f["entry_id"] not in redeemed\n', '')],
 "L3_no_release": [('                released[src["workshop_id"]] += rec[src["entry_id"]]["charge"]\n', '                pass\n')],
}
SUBS["REFLEX_all3"] = SUBS["L7_total_then_ops"] + SUBS["L6_window_all_settled"] + SUBS["L3_no_release"]
src = (B / "tests/test_output.py").read_text()
def make(name, subs):
    s = src
    for a, b in subs:
        assert s.count(a) == 1, (name, a)
        s = s.replace(a, b)
    d = pathlib.Path(tempfile.mkdtemp()) / "tests"; d.mkdir()
    (d / ("v_%s.py" % name)).write_text(s)
    return load_T(d.parent, "v_%s" % name)
T = load_T(B)
V = {n: make(n, s) for n, s in SUBS.items()}
FAM = lambda f: "workshop_*" if f.startswith("workshop_") else "guild_*" if f.startswith("guild_") else f
def docs(res):
    out = {}
    for f, v in res.items():
        out.setdefault(FAM(f), {})[f] = v
    return out
def table(name):
    root = pathlib.Path(tempfile.mkdtemp()); d = root / "data"
    if name == "visible":
        T._build_corpus_dir(d); params = T.TRUE
    else:
        seed, params, mut = T.SEASONS[name]
        T._build_corpus_dir(d, params=params, mutate=mut, main_seed=seed)
    corp = T.load(d, "")
    want = docs(T.settle(corp, params))
    row = {}
    for vn, VT in V.items():
        try:
            got = docs(VT.settle(VT.load(d, ""), VT.Params(params.schedule, params.quantiser, params.order, params.base)))
        except ValueError:
            got = {}
        row[vn] = sorted(k for k in want if json.dumps(want[k], sort_keys=True) != json.dumps(got.get(k), sort_keys=True))
    return row
if __name__ == "__main__":
    names = sys.argv[2:] or ["visible"] + list(T.SEASONS)
    for n in names:
        r = table(n)
        print(n)
        for vn, diff in r.items():
            print("   %-24s %d %s" % (vn, len(diff), ",".join(diff)))
