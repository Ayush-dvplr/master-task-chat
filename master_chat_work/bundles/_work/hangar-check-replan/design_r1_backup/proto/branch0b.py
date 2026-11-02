"""Phase 0b BRANCH_FIRE on absgen instances. Usage: branch0b.py mode n empty(0|1) seeds..."""
import sys
import time

import absgen
import ref
import wrong


def flags(inst):
    S = inst["S"]
    r0 = ref.solve(inst)
    ru = ref.solve(dict(inst, K=10 ** 6))
    out = {"binds": int(ru["used"] > inst["K"] and ru["T"] != r0["T"])}
    noslot = noslot_closure = trade = ps_late = 0
    for ch in inst["checks"]:
        s, f, x = r0["plan"][ch["id"]]
        closed = set(inst["closed"].get(ch["base"], []))
        nost = set(inst["nostart"].get(ch["base"], []))
        xmax = min(inst["types"][ch["type"]]["c"], ch["p"] - 1)
        if s > S:
            if ref.earliest_start(ch["r"], ch["p"] - xmax, closed, nost, S) is None:
                noslot += 1
                noslot_closure += int(ch["r"] + ch["p"] - xmax - 1 <= S)
            else:
                trade += 1
        elif s == ch["ps"] and ch["r"] < ch["ps"]:
            ps_late += 1
    out.update(ps_kept_late=ps_late, plan_trade=trade, no_slot=noslot, no_slot_closure=noslot_closure)
    bases_seen = {c["base"] for c in inst["checks"]}
    segs_seen = {"public" if c["cls"] == "regional" else "commercial" for c in inst["checks"]}
    out["empty_base"] = 4 - len(bases_seen)
    out["empty_segment"] = 2 - len(segs_seen)
    for name in ["split_fcfs", "split_prorata", "split_marginal", "exact_first_tie", "exact_rev_tie",
                 "exact_asap_only", "exact_defer_noslot"]:
        out[name] = int(not wrong.same(wrong.SOLVERS[name](inst), r0))
    out["used"], out["K"], out["S"], out["n"] = r0["used"], inst["K"], S, len(inst["checks"])
    return out


if __name__ == "__main__":
    mode, n, empty = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "1"
    for seed in [int(s) for s in sys.argv[4:]]:
        t = time.time()
        inst = absgen.make(mode, seed, n, empty)
        f = flags(inst)
        print("BF0b", mode, n, int(empty), seed, " ".join("%s=%s" % kv for kv in f.items()),
              "sec=%.1f" % (time.time() - t), flush=True)
    print("ALL_DONE", flush=True)
