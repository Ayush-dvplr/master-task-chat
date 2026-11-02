"""check_exact.py: second, independent recomputation of the reports (G9) plus uniqueness and override probes.

Usage (inside Docker, proto2 mounted at /p, solution at /s):
  check_exact.py diff <data_dir> <out_dir>      per-record diff of out_dir against proto2 + invariants
  check_exact.py brute <n>                      tiny instances: enumerate all plans, the best is unique and
                                                 equals solve.py make_plan and proto2 core.solve_flow
  check_exact.py override <data_dir> <tmp>      drop each correction mechanism, show the output moves
"""
import importlib.util, itertools, json, os, random, re, shutil, sys, tempfile

sys.path.insert(0, os.environ.get("PROTO", "/p"))
import core, solve_proto  # noqa: E402


def recompute(data, out):
    inst, rej, pd, ts = solve_proto.load(data)
    x = core.solve_flow(inst)
    solve_proto.write(inst, x, rej, pd, ts, out)
    return inst, x


def invariants(inst, x):
    load = [0] * inst["S"]
    dl = {d: [0] * inst["S"] for d in core.DEPOTS}
    byb = {b["id"]: b for b in inst["buses"]}
    for (bid, s), k in x.items():
        b = byb[bid]
        assert b["a"] <= s < b["e"] and 0 < k <= b["rate"], (bid, s, k)
        load[s] += k
        dl[b["depot"]][s] += k
    for b in inst["buses"]:
        assert sum(k for (bid, s), k in x.items() if bid == b["id"]) <= b["need"], b["id"]
    for s in range(inst["S"]):
        assert load[s] <= inst["feeder"][s], ("feeder", s)
        for d in core.DEPOTS:
            assert dl[d][s] <= inst["cap"][d][s], ("cabinets", d, s)


def diff(data, out):
    tmp = tempfile.mkdtemp()
    inst, x = recompute(data, tmp)
    invariants(inst, x)
    bad = 0
    for name in sorted(os.listdir(tmp)):
        a = json.load(open(os.path.join(tmp, name)))
        try:
            b = json.load(open(os.path.join(out, name)))
        except FileNotFoundError:
            print("  MISSING", name)
            bad += 1
            continue
        if a == b:
            continue
        bad += 1
        if name == "policy_audit.json":
            rb = {r["bus_id"]: r for r in b["buses"]}
            rows = [r["bus_id"] for r in a["buses"] if rb.get(r["bus_id"]) != r]
            print("  DIFF %s: %d bus records differ, first %s" % (name, len(rows), rows[:1]))
        else:
            keys = [k for k in a if a[k] != b.get(k)]
            print("  DIFF %s: keys %s" % (name, keys))
    print("DIFF %s records_bad_files %d invariants ok" % (out, bad))
    return bad


def tiny(seed):
    rng = random.Random(seed)
    S = 5
    price = [rng.choice([2, 2, 3]) for _ in range(S)]
    buses = []
    for i in range(rng.randint(2, 3)):
        a = rng.randint(0, 2)
        e = rng.randint(a + 1, S)
        rate = rng.randint(1, 2)
        pub = {str(s): rng.randint(1, rate) for s in range(a, e) if rng.random() < 0.4}
        buses.append({"id": "B%d" % (10 + i), "depot": rng.choice(core.DEPOTS[:2]), "a": a, "e": e,
                      "need": rng.randint(1, 4), "rate": rate, "w": rng.choice([1, 4]), "pub": pub})
    cap = {d: [rng.randint(1, 3) for _ in range(S)] for d in core.DEPOTS}
    feeder = [rng.randint(1, 4) for _ in range(S)]
    dprice = {d: [rng.choice([2, 2, 3]) for _ in range(S)] for d in core.DEPOTS}
    return {"S": S, "price": price, "dprice": dprice, "feeder": feeder, "cap": cap, "buses": buses}


def key_of(inst, x):
    unmet = cost = moved = 0
    byb = {b["id"]: b for b in inst["buses"]}
    for b in inst["buses"]:
        got = sum(x.get((b["id"], s), 0) for s in range(inst["S"]))
        unmet += b["w"] * (b["need"] - got)
        for s, p in b["pub"].items():
            moved += max(0, p - x.get((b["id"], int(s)), 0))
    for (bid, s), k in x.items():
        cost += k * inst["dprice"][byb[bid]["depot"]][s]
    vec = [-x.get((bid, s), 0) for s, bid in sorted((s, b["id"]) for b in inst["buses"] for s in range(inst["S"]))]
    return (unmet, cost, moved, vec)


def brute(n):
    spec = importlib.util.spec_from_file_location("oracle", os.environ.get("SOLVE", "/s/solve.py"))
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)

    class Clk:
        count = 5

    bad = checked = 0
    seed = -1
    while checked < n:
        seed += 1
        inst = tiny(seed)
        vars_ = [(b, s) for b in inst["buses"] for s in range(b["a"], b["e"])]
        space = 1
        for b, s in vars_:
            space *= b["rate"] + 1
        if space > 40000:
            continue
        checked += 1
        best, bestx, nbest = None, None, 0
        for vals in itertools.product(*[range(b["rate"] + 1) for b, s in vars_]):
            x = {(b["id"], s): v for (b, s), v in zip(vars_, vals) if v}
            try:
                invariants(inst, x)
            except AssertionError:
                continue
            k = key_of(inst, x)
            if best is None or k < best:
                best, bestx, nbest = k, x, 1
            elif k == best:
                nbest += 1
        buses = []
        for b in inst["buses"]:
            ob = oracle.Bus(b["id"], b["depot"], b["rate"], b["a"], b["e"], b["need"], "c", b["w"])
            ob.published = {int(s): p for s, p in b["pub"].items()}
            buses.append(ob)
        ox = oracle.make_plan(sorted(buses, key=lambda o: o.bus_id), Clk, inst["cap"], inst["feeder"], inst["dprice"])
        px = core.solve_flow(inst)
        if nbest != 1 or ox != bestx or px != bestx:
            bad += 1
            print("MISMATCH seed", seed, best, nbest, key_of(inst, ox), key_of(inst, px))
    print("BRUTE checked %d mismatches %d (every best unique, solve.py and proto2 equal it)" % (n, bad))
    return bad


def override(data, tmp):
    base = os.path.join(tmp, "base")
    recompute(data, base)
    notice = open(os.path.join(data, "disruption_notice.md")).read()
    probes = {
        "cabinet_outages": lambda t: re.sub(r"(?m)^- \w+: \d+ cabinets out of service.*\n", "", t),
        "feeder_derating": lambda t: re.sub(r"(?m)^- from .*feeder limit.*\n", "", t),
        "extra_trips": lambda t: re.sub(r"(?m)^- \w+: extra trip on.*\n", "", t),
    }
    for name, edit in probes.items():
        d = os.path.join(tmp, name, "data")
        shutil.copytree(data, d)
        open(os.path.join(d, "disruption_notice.md"), "w").write(edit(notice))
        o = os.path.join(tmp, name, "out")
        recompute(d, o)
        moved = [f for f in sorted(os.listdir(base)) if open(os.path.join(base, f)).read() != open(os.path.join(o, f)).read()]
        print("OVERRIDE %s removed: %d reports move %s" % (name, len(moved), moved[:3]))
    # meter convention removed: price every depot by the tariff as written (shift 0)
    inst, rej, pd, ts = solve_proto.load(data)
    plain = dict(inst)
    plain["dprice"] = {d: inst["price"] for d in core.DEPOTS}
    o = os.path.join(tmp, "meter", "out")
    x = core.solve_flow(plain)
    solve_proto.write(plain, x, rej, pd, ts, o)
    moved = [f for f in sorted(os.listdir(base)) if open(os.path.join(base, f)).read() != open(os.path.join(o, f)).read()]
    print("OVERRIDE meter_convention removed: %d reports move %s" % (len(moved), moved[:3]))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "diff":
        sys.exit(1 if diff(sys.argv[2], sys.argv[3]) else 0)
    if cmd == "brute":
        sys.exit(1 if brute(int(sys.argv[2])) else 0)
    if cmd == "override":
        override(sys.argv[2], sys.argv[3])
