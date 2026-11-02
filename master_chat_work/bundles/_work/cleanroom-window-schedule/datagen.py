"""Shipped book generator (WORK only). Seeded, stdlib. Writes BUNDLE/environment/data/.

Every accepted night is redrawn until it has exactly one maximum-net-value plan
(counted by cw.solve_night with the bay families carried from earlier nights)."""
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bookgen  # noqa: E402
import cw  # noqa: E402

SEED = 666278
DATA = os.path.join(HERE, "..", "..", "cleanroom-window-schedule", "environment", "data")
SCAFFOLD = ["calendar.csv", "customers.csv", "discount_rules.json", "fx_rates.csv", "policy.json",
            "rate_table.csv", "regions.csv", "schema.md", "tax_rules.json", "thresholds.json",
            "transactions.csv"]
DEFECTS = [["dup"], ["win_missing"], ["win_reversed"], ["win_late"], ["unk_family"], ["unk_client"],
           ["fee_missing"], ["dup", "win_missing"], ["win_reversed", "fee_missing"],
           ["unk_client", "fee_missing"], ["dup", "unk_family"], ["win_late", "unk_family"]]
THRESHOLDS = (int(os.environ.get("CW_CREW_LIMIT", "75")), int(os.environ.get("CW_FLOOR", "1500")))


def specs():
    r = bookgen._Rng(SEED + 1)
    out = []
    for _ in range(360):
        n = r.randint(4, 10)
        out.append({"jobs": n, "overlap": min(n, r.randint(3, 5)), "mand": r.randint(0, 2),
                    "crew": (15, 60), "fee": (20, 200), "values": (200, 900), "dur": (30, 180)})
    for _ in range(25):
        n = r.randint(11, 30)
        out.append({"jobs": n, "overlap": r.randint(4, 6), "mand": r.randint(1, 3),
                    "crew": (20, 50), "fee": (30, 180), "values": (200, 900), "dur": (30, 180)})
    for _ in range(15):
        n = r.randint(31, 72)
        out.append({"jobs": n, "overlap": r.randint(6, 7), "mand": r.randint(2, 4),
                    "crew": (25, 60), "fee": (20, 160), "values": (200, 900), "dur": (30, 180)})
    for d in DEFECTS:
        out.append({"jobs": r.randint(5, 9), "overlap": 4, "mand": 1, "crew": (15, 60), "fee": (20, 200),
                    "values": (200, 900), "dur": (30, 180), "defects": d})
    for _ in range(3):
        out.append({"jobs": 0, "overlap": 1, "mand": 0, "crew": (15, 60), "fee": (20, 200),
                    "values": (200, 900), "dur": (30, 180)})
    r.shuffle(out)
    return out


def to_cw(n):
    return {"night_id": n["night_id"], "jobs": n["jobs"], "mand": set(n["mand"]),
            "fee": {(a, b): (f, c) for a, b, f, c in n["fees"]}, "reject": bool(n["defects"])}


def build(specs_list, seed, n_clients, n_sites, thresholds, start_day, log=None):
    """Sequential redraw; returns (files, attempts, nights, plans)."""
    max_jobs = sum(s["jobs"] for s in specs_list)
    ctx = bookgen.book_setup(seed, len(specs_list), n_clients, n_sites, max_jobs, thresholds, start_day)
    bays = [(b["bay_id"], b["minute_rate"]) for b in ctx["bays"]]
    quals = {b: set(q) for b, q in ctx["quals"].items()}
    fam = {b["bay_id"]: b["initial_family"] for b in ctx["bays"]}
    attempts, nights, plans = [], [], []
    for k, sp in enumerate(specs_list):
        mark = (ctx["next_job"], ctx["next_win"])
        a = 0
        while True:
            ctx["next_job"], ctx["next_win"] = mark
            n = bookgen.night_data(ctx, k, sp, a)
            if n["defects"]:
                plan = None
                break
            net, plan, cnt = cw.solve_night(to_cw(n), bays, quals, fam, count=True)
            if cnt == 1:
                break
            a += 1
            assert a < 200, k
        attempts.append(a)
        nights.append(n)
        plans.append(plan)
        if plan:
            J = {j["job_id"]: j for j in n["jobs"]}
            for b, _ in bays:
                seq = sorted((J[i] for i, x in plan.items() if x == b), key=lambda j: (j["start"], j["job_id"]))
                if seq:
                    fam[b] = seq[-1]["family"]
        if log:
            log(k, n, a)
    return bookgen.render(ctx, nights), attempts, nights, plans, ctx


def main():
    t0 = time.time()
    sp = specs()
    files, attempts, nights, plans, ctx = build(sp, SEED, 3000, 2600, THRESHOLDS, 60)
    for name in SCAFFOLD:
        p = os.path.join(DATA, name)
        if os.path.exists(p):
            os.remove(p)
    total = 0
    for name, text in files.items():
        with open(os.path.join(DATA, name), "w", newline="\n") as fh:
            fh.write(text)
        lines = text.count("\n")
        total += lines
        if name.endswith((".csv", ".tsv", ".jsonl")):
            assert lines >= 2000, (name, lines)
        print("%-20s %6d lines" % (name, lines))
    assert total >= 20500, total
    meta = {"seed": SEED, "attempts": attempts, "redrawn": sum(1 for a in attempts if a),
            "total_lines": total, "seconds": round(time.time() - t0, 1)}
    with open(os.path.join(HERE, "shipped_meta.json"), "w") as fh:
        json.dump(meta, fh)
    print("total", total, "redrawn", meta["redrawn"], "seconds", meta["seconds"])


if __name__ == "__main__":
    main()
