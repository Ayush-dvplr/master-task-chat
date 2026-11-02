"""python3 -B docscore.py LABEL BOOKDIR REFOUT PROGOUT VERDICT: per-check result for one hidden-style book.

Checks mirror tests/test_output.py per H book: feasible 3 (cap-aware _feasible: picks subset, no conflict pair,
no shared crew above CAP picks, maximal unless conflict or crew at CAP), optimal 5, summary 5, policy_audit 3, data_quality 3, regions 3, segments 3.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ref", os.path.join(HERE, "solve.py"))
REF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REF)
W = {"feasible": 3, "optimal": 5, "summary": 5, "policy_audit": 3, "data_quality": 3, "regions": 3, "segments": 3}
GROUP = {"summary": ["summary.json"], "policy_audit": ["policy_audit.json"], "data_quality": ["data_quality.json"],
         "regions": ["region_%s.json" % r for r in ("North", "South", "West", "East")],
         "segments": ["segment_commercial.json", "segment_public.json"]}


def load(d, n):
    try:
        with open(os.path.join(d, n)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main(argv):
    label, book, ref, out, verdict = argv[1:6]
    res = {k: False for k in W}
    if verdict in ("EXACT", "WRONG"):
        for g, names in GROUP.items():
            res[g] = all(load(out, n) is not None and load(out, n) == load(ref, n) for n in names)
        got, want = load(out, "summary.json"), load(ref, "summary.json")
        bk = REF.load(book)
        rounds = REF.build(bk)
        try:
            gsel = {r["round"]: r["selected"] for r in got["rounds"]}
            res["optimal"] = all(gsel.get(r["round"]) == r["selected"] for r in want["rounds"] if r["status"] == "planned")
            ok = [r["round"] for r in got["rounds"]] == [r["round"] for r in want["rounds"]]
            for r in rounds:
                if r.fault is not None:
                    continue
                g = gsel.get(r.rid)
                if not isinstance(g, list) or g != sorted(set(g)) or not set(g) <= set(r.ids):
                    ok = False
                    break
                taken = set(g)
                if any(a in taken and b in taken for a, b in r.pairs):
                    ok = False
                    break
                adj = {p: set() for p in r.ids}
                for a, b in r.pairs:
                    adj[a].add(b)
                    adj[b].add(a)
                count = {}
                for p in taken:
                    c = r.detail[p]["crew"]
                    if bk["crews"][c] == "shared":
                        count[c] = count.get(c, 0) + 1
                if any(v > REF.CAP for v in count.values()):
                    ok = False
                    break
                full = {c for c, v in count.items() if v >= REF.CAP}
                if any(p not in taken and not (adj[p] & taken) and r.detail[p]["crew"] not in full for p in r.ids):
                    ok = False
                    break
            res["feasible"] = ok
        except (TypeError, KeyError):
            pass
    pts = sum(W[k] for k in W if res[k])
    print("SCORE", label, os.path.basename(book), verdict, pts, "/25",
          " ".join("%s=%s" % (k, "ok" if res[k] else "X") for k in W), flush=True)


if __name__ == "__main__":
    main(sys.argv)
