"""BRANCH_FIRE on rendered files. Usage: bf.py <data_dir> <out_root>
Prints one BF line: branch counts for the reference plan and which solvers agree with it."""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core, solve_proto  # noqa: E402

data, root = sys.argv[1], sys.argv[2]
inst, rej, pd, ts = solve_proto.load(data)
t0 = time.time()
xr = core.SOLVERS["ref"](inst)
tr = time.time() - t0
solve_proto.write(inst, xr, rej, pd, ts, os.path.join(root, "ref"))
bf, bc = core.check_feasible(inst, xr)
fam_r, obj = core.families(inst, xr)
short = sum(1 for b in inst["buses"] if b["need"] > sum(k for (bid, s), k in xr.items() if bid == b["id"]))
win = sum(1 for b in inst["buses"] if b["need"] > b["rate"] * (b["e"] - b["a"]))
reasons = {}
for r in rej:
    reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
agree = {}
for sv in ("bigint_min", "flow_plain", "greedy_id", "ref_nofeed", "ref_nocab"):
    x = core.SOLVERS[sv](inst)
    fam, _ = core.families(inst, x)
    agree[sv] = sum(fam[k] == fam_r[k] for k in fam)
print("BF", data, "buses", len(inst["buses"]), "ref_sec %.2f" % tr, "obj", obj, "bindF", bf, "bindC", bc,
      "short", short, "window_short", win, "rej", json.dumps(reasons, sort_keys=True), "agree/8", json.dumps(agree), flush=True)
