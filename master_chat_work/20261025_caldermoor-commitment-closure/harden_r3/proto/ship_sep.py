"""Find shipped-seed edges whose removal leaves 0 blocked commitments with wait != chain_depth. In verifier image."""
import os, shutil, sys, tempfile
sys.path.insert(0, "/tests")
import test_output as T
extra = set()
for it in range(10):
    drop = T._SHIPPED_DROP | frozenset(extra)
    files, w = T.build_corpus(T.SHIPPED_SEED, drop)
    ex, _ = T.build_extra(T.SHIPPED_SEED, w, T.RETIRED, drop)
    files.update(ex)
    tmp = tempfile.mkdtemp()
    for n, t in files.items():
        open(os.path.join(tmp, n), "w", encoding="utf-8", newline="").write(t)
    st = T.compute(tmp); shutil.rmtree(tmp)
    sep = [r for r in st["blocked_rows"] if r["chain_depth"] != st["wait"][r["commitment_key"]]]
    print("iter", it, "blocked", len(st["blocked_rows"]), "separating", [(r["commitment_key"], r["chain_depth"], st["wait"][r["commitment_key"]]) for r in sep])
    if not sep:
        break
    adj, cyc = st["adj"], st["in_cycle"]
    def reaches_cycle(n, seen=None):
        seen = seen or set()
        if n in cyc: return True
        seen.add(n)
        return any(reaches_cycle(m, seen) for m in adj.get(n, ()) if m not in seen)
    for r in sep:
        k = r["commitment_key"]
        for e in st["live_edges"]:
            if e["dependent_key"] == k and e["blocker_key"] in adj.get(k, ()) and reaches_cycle(e["blocker_key"]):
                extra.add(e["edge_id"])
print("EXTRA", sorted(extra))
