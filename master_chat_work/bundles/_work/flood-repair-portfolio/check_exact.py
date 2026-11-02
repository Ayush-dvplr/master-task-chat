"""G9 exactness check (WORK only).

1. For SHIPPED, H1-H3, M, MS, MR: run solution/solve.py and the test reference, diff every
   document record by record.
2. Brute force every planned round of up to 22 proposals (max benefit, then smallest sorted id list).
3. Invariants on the program's documents (conflict-free, maximal, sums, partitions).
4. 300 small generated books: program == reference == brute force.
5. Override-removal probes on the shipped book: each correction mechanism removed changes rounds.
usage: python3 -B check_exact.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "flood-repair-portfolio"
sys.path.insert(0, str(HERE))
import run_tests  # noqa: E402

run_tests.stub()
spec = importlib.util.spec_from_file_location("test_output", BUNDLE / "tests" / "test_output.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
SOLVE = BUNDLE / "solution" / "solve.py"


def run_program(files):
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "d"
        data.mkdir()
        for k, v in files.items():
            (data / k).write_text(v)
        out = Path(td) / "o"
        r = subprocess.run([sys.executable, "-I", "-S", str(SOLVE), str(data), str(out)],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        return {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}


def brute(info, joined):
    names = sorted(info)
    n = len(names)
    near = [0] * n
    for pair in joined:
        a, b = (names.index(p) for p in pair)
        near[a] |= 1 << b
        near[b] |= 1 << a
    best = [None]

    def rec(i, mask, total):
        if i == n:
            ids = [names[k] for k in range(n) if mask >> k & 1]
            cur = best[0]
            if cur is None or total > cur[0] or (total == cur[0] and ids < cur[1]):
                best[0] = (total, ids)
            return
        if not near[i] & mask:
            rec(i + 1, mask | 1 << i, total + info[names[i]]["benefit"])
        rec(i + 1, mask, total)

    rec(0, 0, 0)
    return best[0][1]


def count_diffs(got, want):
    bad = {}
    for doc, w in want.items():
        g = got.get(doc)
        if g == w:
            continue
        if isinstance(w, dict) and isinstance(w.get("rounds") or w.get("rows"), list):
            key = "rounds" if "rounds" in w else "rows"
            gl = g.get(key, []) if isinstance(g, dict) else []
            bad[doc] = sum(1 for a, b in zip(gl, w[key]) if a != b) + abs(len(gl) - len(w[key])) or "header"
        else:
            bad[doc] = t.first_difference(g, w)
    return bad


def invariants(docs, led):
    s = docs["summary.json"]
    assert s["total_benefit"] == sum(r["total_benefit"] for r in s["rounds"])
    assert s["selected_proposals"] == sum(len(r["selected"]) for r in s["rounds"])
    regions = {}
    for d in t.REGION_DOCS:
        for r in docs[d]["rounds"]:
            regions.setdefault(r["round"], []).extend(r["selected"])
    for r in s["rounds"]:
        x = led.rounds[r["round"]]
        if r["status"] == "rejected":
            assert r["selected"] == [] and r["total_benefit"] == 0
            continue
        sel = set(r["selected"])
        assert sorted(regions[r["round"]]) == r["selected"], "regions partition"
        for pair in x["joined"]:
            assert not pair <= sel, "conflict inside portfolio"
        for p in x["info"]:
            if p not in sel:
                assert any(frozenset((p, q)) in x["joined"] for q in sel), "not maximal"
        assert r["total_benefit"] == sum(x["info"][p]["benefit"] for p in sel)
        for d in t.SEGMENT_DOCS:
            seg = d[8:-5]
            row = next(e for e in docs[d]["rounds"] if e["round"] == r["round"])
            assert row["selected"] == [p for p in r["selected"] if x["info"][p]["segment"] == seg]


def main():
    print("== 1-3 books")
    brute_rounds = 0
    for name in ("SHIPPED", "H1", "H2", "H3", "M", "MS", "MR"):
        files = t.book_files(name)
        led = t._Ledger(files)
        want = led.documents()
        got = run_program(files)
        diffs = count_diffs(got, want)
        invariants(got, led)
        for rid, x in led.rounds.items():
            if x["fault"] is None and len(x["info"]) <= 22:
                assert brute(x["info"], x["joined"]) == x["chosen"], (name, rid)
                brute_rounds += 1
        planned = sum(1 for x in led.rounds.values() if x["fault"] is None)
        print(name, "rounds", len(led.rounds), "planned", planned, "record diffs", diffs or 0)
    print("brute-forced rounds", brute_rounds)

    print("== 4 small books")
    small = {"small": 12, "large": [], "sites": 150, "crews": 260, "permits": 200, "faults": 4,
             "ties": 2, "audit_small": 4, "audit_large": 0, "order": "shuffle"}
    bad = 0
    for seed in range(1, 301):
        files, _ = t.make_book(900000 + seed, small)
        led = t._Ledger(files)
        if run_program(files) != led.documents():
            bad += 1
        for rid, x in led.rounds.items():
            if x["fault"] is None:
                if brute(x["info"], x["joined"]) != x["chosen"]:
                    bad += 1
    print("small books 300, bad", bad)

    print("== 5 override-removal probes (shipped book, reference)")
    files = t.book_files("SHIPPED")
    base = t._Ledger(files)

    def changed(new_files):
        led = t._Ledger(new_files)
        return sum(1 for rid in base.rounds
                   if base.rounds[rid].get("chosen") != led.rounds[rid].get("chosen")
                   or base.rounds[rid]["fault"] != led.rounds[rid]["fault"])

    lines = files["proposals.csv"].splitlines()
    blank = [lines[0]] + [",".join(l.split(",")[:5] + [""]) for l in lines[1:] if l]
    probes = {
        "risk_override blanked": dict(files, **{"proposals.csv": "\n".join(blank) + "\n"}),
        "withdrawn read as held": dict(files, **{"permits.csv": files["permits.csv"].replace(",withdrawn", ",held")}),
        "shared crews read as exclusive": dict(files, **{"crews.tsv": files["crews.tsv"].replace("\tshared", "\texclusive")}),
    }
    ex = json.loads(files["exclusions.json"])
    keep = [e for e in ex if not (e["first"].startswith("S") or e["second"].startswith("S"))]
    probes["site-named exclusions dropped"] = dict(files, **{"exclusions.json": json.dumps(keep)})
    for k, v in probes.items():
        print(k, "rounds changed", changed(v))
    print("ALL_DONE")


if __name__ == "__main__":
    main()
