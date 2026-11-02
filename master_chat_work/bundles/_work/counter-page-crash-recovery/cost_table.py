"""Analytic cost table: each variant run on the exact books the tests build; points lost per graded document check."""
import importlib.util
import json
import sys
import time
import types

import variants

stub = types.ModuleType("rewardkit")
stub.criteria = types.SimpleNamespace(**{})


class _C:
    def __getattr__(self, name):
        return lambda weight: None


stub.criteria = _C()
stub.criterion = lambda description: (lambda fn: fn)
sys.modules["rewardkit"] = stub
spec = importlib.util.spec_from_file_location("t", sys.argv[1])
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

CORE, MET, DEP, SUM = T.DOCUMENTS
CHECKS = [("shipped", d, 3) for d in T.DOCUMENTS] + [("dense", d, 5) for d in T.DOCUMENTS] \
    + [("restart", d, 5) for d in T.DOCUMENTS] + [("max", CORE, 5), ("max", SUM, 3), ("rejection", CORE, 5),
                                                  ("relocated", CORE, 5), ("scaled", SUM, 5)]
POSITIVE = 95
BOOKS = sorted({b for b, _, _ in CHECKS})
start = time.time()
books = {b: T._book(b) for b in BOOKS}
want = {b: T._expected(b) for b in BOOKS}
rows = {}
for name, flags in variants.VARS.items():
    got = {b: variants.documents(books[b], flags) for b in BOOKS}
    lost, failed, wrong_imgs = 0, [], {}
    for b, d, w in CHECKS:
        if got[b][d] != want[b][d]:
            lost += w
            failed.append("%s/%s" % (b, d.split(".")[0]))
    for b in BOOKS:
        wrong_imgs[b] = sum(1 for k, v in want[b][CORE]["images"].items() if got[b][CORE]["images"].get(k) != v)
    overall = 0.5 * (POSITIVE - lost) / POSITIVE + 0.45
    rows[name] = {"lost": lost, "alone_pct": round(100.0 * lost / POSITIVE, 1),
                  "all_but_one_overall": round(100 * overall, 1), "failed": failed, "core_wrong_images": wrong_imgs}
    print("%-22s lost %2d alone %5.1f%% overall %5.1f  %s" % (name, lost, 100.0 * lost / POSITIVE, 100 * overall,
                                                             " ".join(failed)), flush=True)
    print("   core wrong images:", wrong_imgs, flush=True)
# sanity: no flags equals reference
ref = {b: variants.documents(books[b], set()) == want[b] for b in BOOKS}
print("reference_equal", ref)
json.dump(rows, open("cost_table.json", "w"), indent=1, sort_keys=True)
print("%.1fs" % (time.time() - start))
print("ALL_DONE")
