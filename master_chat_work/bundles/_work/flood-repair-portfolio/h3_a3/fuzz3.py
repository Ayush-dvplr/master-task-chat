"""Fuzz a program against the reference program (solution/solve.py).

usage: python3 -B fuzz3.py PROGRAM PART [SEED0 COUNT]
PART = gen-<profile> (generator branches) or targeted (documented cases the generator never plants).
Bundle mounted at /b. Prints one line per case: tag MATCH|DIFF|BOTHFAIL|REFFAIL|PROGFAIL ... then ALL_DONE.
"""
import json
import random
import subprocess
import sys
import tempfile
import types
from pathlib import Path

stub = types.ModuleType("rewardkit")


class _Any:
    def __getattr__(self, name):
        return lambda *a, **k: None


stub.criteria = _Any()
stub.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = stub
sys.path.insert(0, "/b/tests")
import test_output as T  # noqa: E402

REF = "/b/solution/solve.py"
prog = sys.argv[1]
part = sys.argv[2]


def run(p, data, out):
    proc = subprocess.run([sys.executable, "-I", "-S", p, str(data), str(out)],
                          capture_output=True, text=True, timeout=300)
    docs = {}
    if proc.returncode == 0:
        for name in T.ARTIFACT_NAMES:
            f = out / name
            docs[name] = json.loads(f.read_text()) if f.exists() else None
    else:
        for name in T.ARTIFACT_NAMES:
            if (out / name).exists():
                docs[name] = "PRESENT"
    return proc.returncode, proc.stderr.strip().splitlines()[-1:] if proc.stderr.strip() else [], docs


def ref_docs(files):
    with tempfile.TemporaryDirectory() as td:
        data = T._write_book(Path(td) / "book", files)
        return run(REF, data, Path(td) / "o_ref")


def compare(tag, files, base=None):
    with tempfile.TemporaryDirectory() as td:
        data = T._write_book(Path(td) / "book", files)
        rc_r, err_r, d_r = run(REF, data, Path(td) / "o_ref")
        rc_p, err_p, d_p = run(prog, data, Path(td) / "o_prog")
    if base is not None:
        tag += " eff=%s" % ("no" if (rc_r, err_r, d_r) == base else "yes")
    if rc_r != 0 and rc_p != 0:
        same = (err_r == err_p and d_r == d_p)
        print(tag, "BOTHFAIL", "same" if same else "differ", "ref=%s prog=%s" % (err_r, err_p), flush=True)
        return
    if rc_r != 0:
        print(tag, "REFFAIL", rc_r, err_r, flush=True)
        return
    if rc_p != 0:
        print(tag, "PROGFAIL", rc_p, err_p, flush=True)
        return
    for name in T.ARTIFACT_NAMES:
        found = T.first_difference(d_p[name], d_r[name])
        if found:
            print(tag, "DIFF", name, found, flush=True)
            return
    print(tag, "MATCH", flush=True)


PROFILES = {
    "random": None,
    "faults": dict(k=(0, 1), faults=19, small=(30, 50), ties=(0, 4)),
    "ties": dict(k=(0, 2), faults=(0, 4), small=(20, 40), ties=12),
    "large": dict(k=(2, 3), faults=(0, 8), small=(20, 30), ties=(0, 6)),
    "fixed": dict(k=(0, 3), faults=(0, 19), small=(20, 60), ties=(0, 12), order="fixed", blank_row=0),
}


def spec_for(profile, seed):
    r = random.Random(seed * 7 + len(profile))
    pr = PROFILES[profile] or dict(k=(0, 3), faults=(0, 19), small=(20, 60), ties=(0, 12))

    def pick(v):
        return r.randint(*v) if isinstance(v, tuple) else v
    k = pick(pr["k"])
    spec = {"audit_large": r.choice([0, 10, 60]), "audit_small": r.choice([0, 5, 12]),
            "blank_row": pr.get("blank_row", r.choice([0, 50])), "crews": 300 + 60 * k,
            "faults": pick(pr["faults"]), "order": pr.get("order", r.choice(["shuffle", "fixed"])),
            "permits": 300 + 80 * k, "sites": 300 + 60 * k, "small": pick(pr["small"]),
            "ties": 2 * (pick(pr["ties"]) // 2), "large": [(r.randint(20, 60), r.randint(3, 8)) for _ in range(k)]}
    spec["faults"] = min(spec["faults"], spec["small"] - spec["ties"])
    return spec


def base_book(seed=4242, small=8, faults=0, ties=0):
    spec = {"audit_large": 0, "audit_small": 6, "blank_row": 0, "crews": 300, "faults": faults,
            "order": "fixed", "permits": 300, "sites": 300, "small": small, "ties": ties, "large": []}
    files, _ = T.make_book(seed, spec)
    return dict(files)


def lines(text):
    return text.split("\n")


def table(files, name):
    ls = [x for x in files[name].split("\n") if x]
    return ls[0], ls[1:]


def put(files, name, head, rows, sep):
    files[name] = head + "\n" + "".join(r + "\n" for r in rows)


def sep_of(name):
    return "\t" if name.endswith(".tsv") else ","


def rounds_of(files):
    _, rows = table(files, "proposals.csv")
    out = []
    for r in rows:
        rid = r.split(",")[0]
        if rid not in out:
            out.append(rid)
    return out


def props_of(files, rid):
    _, rows = table(files, "proposals.csv")
    return [r.split(",") for r in rows if r.split(",")[0] == rid]


def edit_prop(files, idx_pred, col, val):
    head, rows = table(files, "proposals.csv")
    n = 0
    for i, r in enumerate(rows):
        f = r.split(",")
        if idx_pred(i, f):
            f[col] = val
            rows[i] = ",".join(f)
            n += 1
    put(files, "proposals.csv", head, rows, ",")
    return n


def targeted():
    cases = []

    def case(tag):
        def deco(fn):
            cases.append((tag, fn))
            return fn
        return deco

    for hh in ["01", "060", "0", "61", " 5", "5.0", "+5", "\u0663", "60", "1"]:
        def f(b, hh=hh):
            edit_prop(b, lambda i, f: i == 3, 4, hh)
        cases.append(("households=%r" % hh, f))
    for ov in ["a", "E", "AB", " A", "D"]:
        def f(b, ov=ov):
            edit_prop(b, lambda i, f: i == 2, 5, ov)
        cases.append(("override=%r" % ov, f))

    @case("all_rounds_rejected_dup")
    def _(b):
        head, rows = table(b, "proposals.csv")
        seen = set()
        extra = []
        for r in rows:
            rid = r.split(",")[0]
            if rid not in seen:
                seen.add(rid)
                extra.append(r)
        put(b, "proposals.csv", head, rows + extra, ",")

    @case("empty_exclusions")
    def _(b):
        b["exclusions.json"] = "[]\n"

    @case("empty_audit")
    def _(b):
        b["audit_queries.txt"] = ""

    @case("audit_pair_same")
    def _(b):
        rid = rounds_of(b)[0]
        p = props_of(b, rid)[0][1]
        b["audit_queries.txt"] = "PAIR %s %s %s\nVALUE %s %s\n" % (rid, p, p, rid, p)

    @case("audit_pair_reversed_order")
    def _(b):
        rid = rounds_of(b)[1]
        ps = sorted(x[1] for x in props_of(b, rid))
        b["audit_queries.txt"] = "PAIR %s %s %s\nPAIR %s %s %s\n" % (rid, ps[-1], ps[0], rid, ps[0], ps[-1])

    @case("audit_rejected_round")
    def _(b):
        rid = rounds_of(b)[0]
        p = props_of(b, rid)[0]
        head, rows = table(b, "proposals.csv")
        put(b, "proposals.csv", head, rows + [",".join(p)], ",")
        b["audit_queries.txt"] = "VALUE %s %s\nPAIR %s %s %s\n" % (rid, p[1], rid, p[1], props_of(b, rid)[1][1])

    @case("segment_upper")
    def _(b):
        head, rows = table(b, "segment_codes.tsv")
        f = rows[1].split("\t")
        f[2] = f[2].capitalize()
        rows[1] = "\t".join(f)
        put(b, "segment_codes.tsv", head, rows, "\t")

    @case("permit_other_round_rows")
    def _(b):
        head, rows = table(b, "permits.csv")
        put(b, "permits.csv", head, rows + ["R99999,M99999,P999999,held"], ",")

    @case("segment_other_round_rows")
    def _(b):
        head, rows = table(b, "segment_codes.tsv")
        put(b, "segment_codes.tsv", head, rows + ["R99999\tP999999\tbogus"], "\t")

    @case("exclusion_other_round")
    def _(b):
        ex = json.loads(b["exclusions.json"])
        ex.append({"round": "R99999", "first": "P999999", "second": "P999999"})
        b["exclusions.json"] = json.dumps(ex) + "\n"

    @case("same_permit_two_rounds")
    def _(b):
        r0, r1 = rounds_of(b)[:2]
        p0 = props_of(b, r0)[0][1]
        p1 = props_of(b, r1)[0][1]
        head, rows = table(b, "permits.csv")
        put(b, "permits.csv", head, rows + ["%s,M88888,%s,held" % (r0, p0), "%s,M88888,%s,held" % (r1, p1)], ",")

    @case("exclusion_site_and_own_proposal")
    def _(b):
        rid = rounds_of(b)[2]
        ps = props_of(b, rid)
        ex = json.loads(b["exclusions.json"])
        ex.append({"round": rid, "first": ps[0][2], "second": ps[0][1]})
        b["exclusions.json"] = json.dumps(ex) + "\n"

    @case("exclusion_site_same_site")
    def _(b):
        rid = rounds_of(b)[2]
        ps = props_of(b, rid)
        ex = json.loads(b["exclusions.json"])
        ex.append({"round": rid, "first": ps[0][2], "second": ps[0][2]})
        b["exclusions.json"] = json.dumps(ex) + "\n"

    @case("exclusion_proposal_of_other_round")
    def _(b):
        r0, r1 = rounds_of(b)[:2]
        ex = json.loads(b["exclusions.json"])
        ex.append({"round": r0, "first": props_of(b, r0)[0][1], "second": props_of(b, r1)[0][1]})
        b["exclusions.json"] = json.dumps(ex) + "\n"

    @case("single_proposal_round")
    def _(b):
        head, rows = table(b, "proposals.csv")
        f = rows[0].split(",")
        f[0], f[1] = "R00001", "P000001"
        put(b, "proposals.csv", head, rows + [",".join(f)], ",")
        h2, r2 = table(b, "segment_codes.tsv")
        put(b, "segment_codes.tsv", h2, r2 + ["R00001\tP000001\tpublic"], "\t")

    @case("one_crew_clique_ties")
    def _(b):
        rid = rounds_of(b)[3]
        crew = None
        head, rows = table(b, "crews.tsv")
        for r in rows:
            c, m = r.split("\t")
            if m == "exclusive":
                crew = c
                break
        edit_prop(b, lambda i, f: f[0] == rid, 3, crew)
        edit_prop(b, lambda i, f: f[0] == rid, 4, "10")
        edit_prop(b, lambda i, f: f[0] == rid, 5, "B")

    @case("var_width_ids")
    def _(b):
        rid = rounds_of(b)[3]
        ps = [x[1] for x in props_of(b, rid)]
        ren = {ps[0]: "P9", ps[1]: "P10"}
        for name in ("proposals.csv", "segment_codes.tsv", "permits.csv", "audit_queries.txt", "exclusions.json"):
            t = b[name]
            for o, n in ren.items():
                t = t.replace(o, n)
            b[name] = t
        edit_prop(b, lambda i, f: f[0] == rid and f[1] in ("P9", "P10"), 4, "12")
        edit_prop(b, lambda i, f: f[0] == rid and f[1] in ("P9", "P10"), 5, "C")

    @case("var_width_rounds")
    def _(b):
        rs = rounds_of(b)
        ren = {rs[0]: "R7", rs[1]: "R10"}
        for name in ("proposals.csv", "segment_codes.tsv", "permits.csv", "audit_queries.txt", "exclusions.json"):
            t = b[name]
            for o, n in ren.items():
                t = t.replace(o, n)
            b[name] = t

    @case("benefit_exactly_1")
    def _(b):
        edit_prop(b, lambda i, f: i == 4, 4, "1")

    for drop in ["proposals.csv", "benefits.ini", "audit_queries.txt", "two_missing"]:
        def f(b, drop=drop):
            if drop == "two_missing":
                b.pop("crews.tsv")
                b.pop("permits.csv")
            else:
                b.pop(drop)
        cases.append(("missing_%s" % drop, f))

    @case("manifest_reordered_two_missing")
    def _(b):
        m = json.loads(b["manifest.json"])
        m["files"] = list(reversed(m["files"]))
        b["manifest.json"] = json.dumps(m) + "\n"
        b.pop("crews.tsv")
        b.pop("permits.csv")

    @case("manifest_exclusions_first_with_faults")
    def _(b):
        m = json.loads(b["manifest.json"])
        fl = m["files"]
        fl.remove("exclusions.json")
        fl.insert(0, "exclusions.json")
        b["manifest.json"] = json.dumps(m) + "\n"

    @case("trailing_blank_lines")
    def _(b):
        for name in ("proposals.csv", "permits.csv", "segment_codes.tsv", "crews.tsv", "region_codes.csv"):
            b[name] = b[name] + "\n\n"

    @case("shared_crew_everyone")
    def _(b):
        rid = rounds_of(b)[4]
        head, rows = table(b, "crews.tsv")
        crew = [r.split("\t")[0] for r in rows if r.split("\t")[1] == "shared"][0]
        edit_prop(b, lambda i, f: f[0] == rid, 3, crew)

    @case("withdrawn_only_permit")
    def _(b):
        rid = rounds_of(b)[5]
        ps = [x[1] for x in props_of(b, rid)]
        head, rows = table(b, "permits.csv")
        put(b, "permits.csv", head, rows + ["%s,M77777,%s,withdrawn" % (rid, p) for p in ps], ",")

    @case("dup_permit_row")
    def _(b):
        rid = rounds_of(b)[5]
        p = props_of(b, rid)[0][1]
        head, rows = table(b, "permits.csv")
        put(b, "permits.csv", head, rows + ["%s,M66666,%s,held" % (rid, p)] * 2, ",")

    @case("region_without_selection")
    def _(b):
        head, rows = table(b, "region_codes.csv")
        put(b, "region_codes.csv", head, [r.rsplit(",", 1)[0] + ",North" for r in rows], ",")

    @case("exclusion_dup_and_reverse")
    def _(b):
        rid = rounds_of(b)[6]
        ps = [x[1] for x in props_of(b, rid)]
        ex = json.loads(b["exclusions.json"])
        ex += [{"round": rid, "first": ps[0], "second": ps[1]}, {"round": rid, "first": ps[1], "second": ps[0]}]
        b["exclusions.json"] = json.dumps(ex) + "\n"

    @case("faulty_row_in_later_round_of_earlier_file")
    def _(b):
        rs = rounds_of(b)
        head, rows = table(b, "segment_codes.tsv")
        put(b, "segment_codes.tsv", head, rows + ["%s\tP555555\tpublic" % rs[0]], "\t")
        edit_prop(b, lambda i, f: f[0] == rs[0] and f[1] == props_of(b, rs[0])[1][1], 4, "0")

    for seed in (4242, 777, 9001):
        base = ref_docs(base_book(seed))
        for tag, fn in cases:
            b = base_book(seed)
            try:
                fn(b)
            except Exception as exc:  # report the planter failure
                print("%s/%d PLANTFAIL %s" % (tag, seed, exc), flush=True)
                continue
            compare("%s/%d" % (tag, seed), b, base)


if part == "targeted":
    targeted()
else:
    profile = part.split("-", 1)[1]
    seed0, count = int(sys.argv[3]), int(sys.argv[4])
    for seed in range(seed0, seed0 + count):
        spec = spec_for(profile, seed)
        tag = "%s/%d k%d f%d s%d t%d %s" % (profile, seed, len(spec["large"]), spec["faults"], spec["small"],
                                            spec["ties"], spec["order"])
        try:
            files, _ = T.make_book(10_000 + seed, spec)
        except (AssertionError, ValueError) as exc:
            print(tag, "GENFAIL", type(exc).__name__, exc, flush=True)
            continue
        compare(tag, files)
print("ALL_DONE")
