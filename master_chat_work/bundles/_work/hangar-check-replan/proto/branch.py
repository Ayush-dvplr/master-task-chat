"""BRANCH_FIRE counter: per seed, how often each hard branch fires in the reference plan."""
import sys

import gen
import ref
import wrong

if __name__ == "__main__":
    mode, n, frac = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
    for seed in [int(s) for s in sys.argv[4:]]:
        inst = gen.make(mode, seed, n)
        inst["K"] = 10 ** 6
        ru = ref.solve(inst)
        inst["K"] = ru["used"] if frac >= 1 else int(ru["used"] * frac)
        r0 = ref.solve(inst)
        S = inst["S"]
        binds = int(ru["used"] > inst["K"] and ru["T"] != r0["T"])
        noslot = trade = ps_late = 0
        for ch in inst["checks"]:
            s, f, x = r0["plan"][ch["id"]]
            closed = set(inst["closed"].get(ch["base"], []))
            nost = set(inst["nostart"].get(ch["base"], []))
            ty = inst["types"][ch["type"]]
            xmax = min(ty["c"], ch["p"] - 1)
            if s > S:
                if ref.earliest_start(ch["r"], ch["p"] - xmax, closed, nost, S) is None:
                    noslot += 1
                else:
                    trade += 1
            elif s == ch["ps"] and ch["r"] < ch["ps"]:
                ps_late += 1
        nonconvex = int(not wrong.same(wrong.split_marginal(inst), r0))
        tie = int(not wrong.same(wrong.exact_variant(inst, tie="rev"), r0))
        asap = int(not wrong.same(wrong.exact_variant(inst, allow_ps=False), r0))
        print("BF", mode, n, seed, "binds", binds, "nonconvex", nonconvex, "tie", tie, "asap_differs", asap,
              "ps_kept_late", ps_late, "plan_trade", trade, "no_slot", noslot, flush=True)
