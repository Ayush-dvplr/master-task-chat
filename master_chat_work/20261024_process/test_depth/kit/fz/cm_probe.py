import json, os, sys, shutil, tempfile
sys.path.insert(0, "/fz")
import fz_cm as F
T = F.T


def runs(files, tag):
    tmp = tempfile.mkdtemp(prefix="cmp")
    data = os.path.join(tmp, "data")
    F.write(files, data, reverse=False)
    ref = os.path.join(tmp, "ref")
    os.makedirs(ref)
    T.write_all(T.compute(data), ref)
    out = {}
    for who, prog in (("agent", "/progs/agent/reconcile.py"), ("oracle", "/progs/oracle/solve.py")):
        o = os.path.join(tmp, "o_" + who, "out")
        os.makedirs(os.path.dirname(o))
        pd = os.path.join(tmp, "p_" + who)
        os.makedirs(pd)
        p = shutil.copy(prog, os.path.join(pd, "reconcile.py"))
        code, err, secs = F.run(p, data, o, tmp)
        out[who] = (code, err.strip().splitlines()[-1:] if code else "", o)
    return tmp, ref, out


mode = sys.argv[1]
if mode == "malformed":
    for variant in ("blank", "short", "long"):
        files, _ = T.build_all(4100011)
        T._add_small_envelopes(files)
        extra = {"blank": "", "short": "ACT-0001|2032-09", "long": "ACT-0001|2032-09|20|x"}[variant]
        files["budget_overrides.psv"] = files["budget_overrides.psv"].rstrip("\n") + "\n" + extra + "\n"
        tmp, ref, out = runs(files, variant)
        print(variant, {w: out[w][:2] for w in out})
        shutil.rmtree(tmp, ignore_errors=True)
elif mode == "group":
    case = json.loads(sys.argv[2])
    files, _ = T.build_all(case["seed"])
    F.fixtures(files, case["fix"], case["seed"])
    import random
    rng = random.Random(case["seed"] * 17 + 3)
    for m in case.get("muts", []):
        {"waivers": F.m_waivers, "revision": F.m_revision}[m](files, rng)
    tmp, ref, out = runs(files, "g")
    want = open(os.path.join(ref, "attention_allocation.csv")).read().split("\n")
    got = open(os.path.join(out["agent"][2], "attention_allocation.csv")).read().split("\n")
    mli_w = open(os.path.join(ref, "month_load_index.csv")).read().split("\n")
    print(want[0])
    bad = set()
    for a, b in zip(want, got):
        if a != b:
            bad.add(tuple(a.split(",")[:2]))
    for ym, act in sorted(bad):
        print("GROUP", ym, act)
        for a, b in zip(want, got):
            if a.split(",")[:2] == [ym, act]:
                print("  want", a, " | got", b)
        for l in mli_w:
            if l.split(",")[:2] == [ym, act]:
                print("  month_load_index want", l)
    print(mli_w[0])
    shutil.rmtree(tmp, ignore_errors=True)
