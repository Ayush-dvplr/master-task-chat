"""Second, independent recomputation of the nine documents (G9).

usage: python3 check_exact.py <data_dir> <out_dir> [--probes <solve.py>]

Reads the inputs with the prototype reader (proto/solve_proto.read_inputs/build_season, written from the
docs, not from solution/solve.py), solves every lane with proto/lane.py reference (forward and backward
day sweep plus a lexicographic fixing pass, a different algorithm from solve.py's lex-carrying sweep),
then diffs every record of <out_dir> and asserts the policy invariants.
With --probes it also runs override-removal probes: each correction mechanism is removed from a copy of
the data and solve.py must produce different documents.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "proto"))
import solve_proto as SP  # noqa: E402
from lane import Lane, reference  # noqa: E402

DOCS = ["policy_audit.json", "summary.json", "data_quality.json", "segment_commercial.json", "segment_public.json"] + [
    "region_%s.json" % R for R in SP.REGIONS]


def expected(data):
    S = SP.build_season(SP.read_inputs(data))
    start = {}
    for R in SP.REGIONS:
        for T in SP.TYPES:
            rs = [r for r in S["reqs"] if r["region"] == R and r["type"] == T]
            pos = {r["id"]: k for k, r in enumerate(rs)}
            d = dict(H=SP.H, cap=S["cap"][(R, T)], factor=S["fac"][R], blackout=sorted(S["black"][R]), defer=S["defer"],
                     reqs=[dict(id=r["id"], crews=r["crews"], dur=r["dur"], e=r["e"], l=r["l"], w=r["w"], pub=r["pub"])
                           for r in rs],
                     incompat=[(min(pos[a], pos[b]), max(pos[a], pos[b])) for a, b in S["inc"] if a in pos and b in pos],
                     prec=[(pos[a], pos[b]) for a, b in S["prec"] if a in pos and b in pos])
            L = Lane(d)
            plan = reference(L)
            assert L.feasible(plan), (R, T)
            for r, s in zip(rs, plan):
                start[r["id"]] = s
    # the prototype writer computes the documents from a given start map
    SP_solve = SP.solve_lane
    try:
        def fixed(rs, *a):
            return tuple(start[r["id"]] for r in rs)
        SP.solve_lane = fixed
        S2, audit = SP.derive(SP.read_inputs(data))
    finally:
        SP.solve_lane = SP_solve
    tmp = tempfile.mkdtemp()
    SP.write_outputs(S2, audit, tmp)
    docs = {n: json.load(open(os.path.join(tmp, n))) for n in DOCS}
    shutil.rmtree(tmp)
    return S, start, docs


def invariants(S, start):
    by = {r["id"]: r for r in S["reqs"]}
    DEF = SP.DEF
    for R in SP.REGIONS:
        for T in SP.TYPES:
            use = [0] * (SP.H + 2)
            for r in S["reqs"]:
                if (r["region"], r["type"]) != (R, T) or start[r["id"]] == DEF:
                    continue
                s = start[r["id"]]
                assert r["e"] <= s and s + r["dur"] - 1 <= r["l"], r["id"]
                assert s not in S["black"][R], r["id"]
                for d in range(s, s + r["dur"]):
                    use[d] += r["crews"]
            assert all(use[d] <= S["cap"][(R, T)][d] for d in range(1, SP.H + 1)), (R, T)
    for a, b in S["inc"]:
        if start[a] != DEF and start[b] != DEF:
            A, B = by[a], by[b]
            assert start[a] + A["dur"] - 1 < start[b] or start[b] + B["dur"] - 1 < start[a], (a, b)
    for a, b in S["prec"]:
        if start[b] != DEF:
            assert start[a] != DEF and start[b] > start[a] + by[a]["dur"] - 1, (a, b)


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return path or "/"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return path + "/" + str(k)
            p = first_diff(a[k], b[k], path + "/" + str(k))
            if p:
                return p
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            p = first_diff(x, y, "%s/%d" % (path, i))
            if p:
                return p
        return None if len(a) == len(b) else path + "/len"
    return None if a == b else (path or "/")


def compare(docs, out):
    bad = 0
    for n in DOCS:
        got = json.load(open(os.path.join(out, n)))
        p = first_diff(docs[n], got)
        print("%-24s %s" % (n, "EXACT" if p is None else "DIFF at " + p))
        bad += p is not None
    return bad


def run_solve(solve, data):
    out = tempfile.mkdtemp()
    subprocess.run([sys.executable, "-B", solve, "--data", data, "--out", out], check=True, capture_output=True)
    docs = {n: open(os.path.join(out, n)).read() for n in DOCS}
    shutil.rmtree(out)
    return docs


def probes(solve, data):
    base = run_solve(solve, data)
    log = open(os.path.join(data, "control_room.log")).read().splitlines()
    pub_at = json.load(open(os.path.join(data, "published_plan.json")))["published_at"]

    def edited(name, fn):
        tmp = tempfile.mkdtemp()
        d = os.path.join(tmp, "data")
        shutil.copytree(data, d)
        fn(d)
        docs = run_solve(solve, d)
        shutil.rmtree(tmp)
        moved = [n for n in DOCS if docs[n] != base[n]]
        print("probe %-34s %s" % (name, ("moves " + ",".join(moved)) if moved else "NO CHANGE (FAIL)"))
        return bool(moved)

    def write_log(d, lines):
        open(os.path.join(d, "control_room.log"), "w").write("\n".join(lines) + "\n")

    ok = True
    ok &= edited("drop post-publication CREW_LOSS", lambda d: write_log(
        d, [x for x in log if not (" CREW_LOSS " in x and x.split()[0] > pub_at)]))
    ok &= edited("drop WITHDRAW", lambda d: write_log(d, [x for x in log if " WITHDRAW " not in x]))
    ok &= edited("drop NEW_REQUEST", lambda d: write_log(d, [x for x in log if " NEW_REQUEST " not in x]))

    def earlier_pub(d):
        p = os.path.join(d, "published_plan.json")
        j = json.load(open(p))
        j["published_at"] = "2026-02-26T00:00:00Z"
        json.dump(j, open(p, "w"))
    ok &= edited("publication moved before pre-pub events", earlier_pub)

    def no_dup(d):
        p = os.path.join(d, "requests.json")
        j = json.load(open(p))
        seen, keep = set(), []
        for r in j["requests"]:
            if r["asset_id"] in seen:
                continue
            seen.add(r["asset_id"])
            keep.append(r)
        j["requests"] = keep
        json.dump(j, open(p, "w"))
    ok &= edited("drop duplicate requests.json records", no_dup)

    def no_blackout(d):
        p = os.path.join(d, "region_calendar.json")
        j = json.load(open(p))
        for R in j:
            j[R]["blackout_days"] = []
        json.dump(j, open(p, "w"))
    ok &= edited("drop blackout days", no_blackout)

    def no_prec(d):
        p = os.path.join(d, "network_constraints.json")
        j = json.load(open(p))
        j["precedence"] = []
        j["incompatible"] = []
        json.dump(j, open(p, "w"))
    ok &= edited("drop network constraints", no_prec)
    return ok


def main():
    data, out = sys.argv[1], sys.argv[2]
    S, start, docs = expected(data)
    invariants(S, start)
    print("invariants ok: %d requests, %d deferred" % (len(start), sum(1 for s in start.values() if s == SP.DEF)))
    bad = compare(docs, out)
    ok = True
    if "--probes" in sys.argv:
        ok = probes(sys.argv[sys.argv.index("--probes") + 1], data)
    print("CHECK_EXACT", "PASS" if bad == 0 and ok else "FAIL")
    sys.exit(0 if bad == 0 and ok else 1)


if __name__ == "__main__":
    main()
