#!/usr/bin/env python3
"""Catalogue probe accounting engine.

Usage:  broker.py <input-dir> <output-dir>

Reads pools.csv, indexes.csv, analysts.csv, partitions.csv and lookups.jsonl
from the input directory, resolves every metered lookup into a probe line and
writes probes.jsonl, partitions.json and catalog.json into the output
directory.

The firmware constants of the retired controller are held in the CONSTANTS
block below.  Every figure the engine reports is worked out from the input
files at run time; nothing about a particular run is baked in.
"""
import json
import os
import sys


# --------------------------------------------------------------------------
# firmware constants (recovered from the recorded run)
# --------------------------------------------------------------------------
GAIN = 1075                 # round normalisation gain
PAGE_FACTOR = 4              # base scale when `pages` supplies the base figure
ROUND_OFFSET = 0             # offset applied to the remaining column (rounds)

# plan adjustments (stage 3): one entry per plan value
PLAN_ADJ = {
    "seek": lambda x: x,
    "merge": lambda x: x - 3,
    "stream": lambda x: x + 17,
    "scan": lambda x: x - 75,
    "nested": lambda x: x - 75,
    "fanout": lambda x: x + 44,
    "hybrid": lambda x: (x - 14) // 2,
}
# layout adjustments (stage 4), keyed on the charged layout
LAYOUT_ADJ = {
    "btree": lambda y: y,
    "bitmap": lambda y: y + 39,
    "sparse": lambda y: (5 * y + 130) // 4,
    "column": lambda y: 3 * y - 1,
}
# phase adjustments (stage 5), skipped on the first lookup an index resolves
PHASE_ADJ = {
    "quiet": lambda y: y + 1,
    "shoulder": lambda y: y + 32,
    "peak": lambda y: y + 36,
}
# mode adjustments (stage 6), keyed on the pool's mode
MODE_ADJ = {
    "turbo": lambda y: tdiv(y, 2),
    "cold": lambda y: tdiv(y, 2),
    "paired": lambda y: y,
}

CREDIT_RELEASE = 12         # released from the credit of every lookup (stage 7)
CREDIT_CEILING = 400        # the credit never passes this
DOUBLE_RELIEF_FACTOR = 2    # doubled relief scales the debt by this
WAIVER_DIVISOR = 3          # an unspent waiver divides the cost by this
LOCK_MISSES = 2             # miss count that raises the lock flag
LOCK_RATIO_NUM, LOCK_RATIO_DEN = 3, 2   # lock surcharge scales cost by 3/2
TRAILING = 2                # entries held in the trailing record

BASELINE_FETCH_BUMP = 4     # a fetch raises the index baseline by this
DEBT_CEILING = 2000         # debt never passes this
DEBT_REACH_DIVISOR = 20     # fetch debt is derived from reach
DEBT_REPLICA_MULT = {3: 1}  # replica that multiplies the debt amount
DEBT_REPLICA_EXTRA = {2: 0}  # replica that adds a fixed extra
DEBT_BACK_TO_BACK = 0       # extra debt for a fetch directly after a fetch

BANDS = (("heavy", 260), ("warm", 75), ("light", 1))   # band edges, widest down
BAND_NAMES = ("heavy", "warm", "light", "idle")

BOOKKEEPING_VERBS = ("refresh", "snapshot")   # resolve to setup
SEALING_VERB = "purge"                        # resolves to locked

# per clearance tolerance: debt_before above this resolves to flagged
CLEARANCE_TOLERANCE = {
    "principal": 200,
    "staff": 150,
    "rotational": 100,
    "vendor": 50,
}

COUNTED_STATUSES = ("ok", "flagged", "dropped")   # counted into a partition total
STALL_MISSES = 3              # miss count that stalls a partition
HELD_DEBT = 1                 # index debt above this holds a partition back


def tdiv(a, b):
    """Division truncating towards zero."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def read_csv(path):
    rows = []
    with open(path) as handle:
        header = handle.readline().rstrip("\n").split(",")
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split(",")
            rows.append(dict(zip(header, fields)))
    return rows


class IndexState(object):
    """The ten pieces of carried state, owned by the index."""

    __slots__ = ("baseline", "debt", "credit", "misses", "resolved_any",
                 "prev_was_fetch", "waiver", "doubled_relief", "locked",
                 "trailing")

    def __init__(self, warmup):
        self.baseline = warmup
        self.debt = 0
        self.credit = 0
        self.misses = 0
        self.resolved_any = False
        self.prev_was_fetch = False
        self.waiver = False
        self.doubled_relief = False
        self.locked = False
        self.trailing = []          # list of (query, cost), newest last


def resolve(indir, outdir):
    pools = {r["pool"]: r for r in read_csv(os.path.join(indir, "pools.csv"))}
    indexes = {r["index"]: r for r in read_csv(os.path.join(indir, "indexes.csv"))}
    analysts = {r["analyst"]: r for r in read_csv(os.path.join(indir, "analysts.csv"))}
    parts = {r["partition"]: r for r in read_csv(os.path.join(indir, "partitions.csv"))}
    lookups = []
    with open(os.path.join(indir, "lookups.jsonl")) as handle:
        for line in handle:
            line = line.strip()
            if line:
                lookups.append(json.loads(line))
    lookups.sort(key=lambda r: r["seq"])

    def charged_layout(index_name):
        parent = indexes[index_name]["parent"]
        if parent:
            return indexes[parent]["layout"]
        return indexes[index_name]["layout"]

    state = {}
    for name in indexes:
        state[name] = IndexState(int(indexes[name]["warmup"]))

    probes = []
    per_part = {}

    for look in lookups:
        part = parts[look["partition"]]
        index_name = part["index"]
        st = state[index_name]
        layout = charged_layout(index_name)
        mode = pools[part["pool"]]["mode"]
        verb = look["verb"]
        phase = look["phase"]

        # 1. offset
        figure = look["cursor"] - st.baseline
        if figure < 0:
            figure = 0
        # 2. round normalisation
        if look["pages"] > 0:
            base = look["pages"] * PAGE_FACTOR
        else:
            base = look["reach"]
        count = base * (look["rounds"] + ROUND_OFFSET)
        figure = tdiv(figure * GAIN, count) if count else 0
        if figure < 0:
            figure = 0
        # 3. plan
        figure = PLAN_ADJ[part["plan"]](figure)
        # 4. layout
        figure = LAYOUT_ADJ[layout](figure)
        # 5. phase (skipped on the first lookup an index resolves)
        if st.resolved_any:
            figure = PHASE_ADJ[phase](figure)
        # 6. mode
        figure = MODE_ADJ[mode](figure)
        # 7. credit release
        released = min(st.credit, CREDIT_RELEASE)
        st.credit -= released
        figure += released
        # 8. debt relief
        debt_before = st.debt
        if st.doubled_relief:
            figure -= debt_before * DOUBLE_RELIEF_FACTOR
            st.doubled_relief = False
        else:
            figure -= debt_before
        if figure < 0:
            figure = 0
        working = figure
        # 9. repeat query
        for query, cost in reversed(st.trailing):
            if query == look["query"]:
                working = cost
                break
        # 10. waiver
        if st.waiver:
            working = tdiv(working, WAIVER_DIVISOR)
            st.waiver = False
        # 11. lock surcharge
        if st.locked:
            working = tdiv(working * LOCK_RATIO_NUM, LOCK_RATIO_DEN)
        cost = working

        # 12. banding
        band = "idle"
        for name, edge in BANDS:
            if cost >= edge:
                band = name
                break

        # 13. status ladder
        if verb in BOOKKEEPING_VERBS:
            status = "setup"
        elif verb == SEALING_VERB:
            status = "locked"
        elif band == "idle":
            status = "dropped"
        elif debt_before > CLEARANCE_TOLERANCE[analysts[look["analyst"]]["clearance"]]:
            status = "flagged"
        else:
            status = "ok"

        probes.append({
            "analyst": look["analyst"],
            "band": band,
            "cost": cost,
            "debt_before": debt_before,
            "partition": look["partition"],
            "query": look["query"],
            "seq": look["seq"],
            "status": status,
            "verb": verb,
        })

        bucket = per_part.setdefault(look["partition"], [])
        bucket.append(probes[-1])

        # 14. carry update
        if status == "dropped":
            st.misses += 1
            if st.misses >= LOCK_MISSES:
                st.locked = True
        if verb == "refresh":
            st.baseline = look["cursor"]
        elif verb == "snapshot":
            moved = min(st.debt, CREDIT_CEILING - st.credit)
            if moved > 0:
                st.credit += moved
            st.debt = 0
            st.waiver = True
        elif verb == "fetch":
            amount = look["reach"] // DEBT_REACH_DIVISOR
            if look.get("replica_extra") is None:
                pass
            rep = int(part["replica"])
            if rep in DEBT_REPLICA_MULT:
                amount *= DEBT_REPLICA_MULT[rep]
            if rep in DEBT_REPLICA_EXTRA:
                amount += DEBT_REPLICA_EXTRA[rep]
            if st.prev_was_fetch:
                amount += DEBT_BACK_TO_BACK
            st.debt = min(st.debt + amount, DEBT_CEILING)
            st.baseline += BASELINE_FETCH_BUMP
        elif verb == SEALING_VERB:
            st.doubled_relief = True
        st.prev_was_fetch = (verb == "fetch")
        st.resolved_any = True
        st.trailing.append((look["query"], cost))
        if len(st.trailing) > TRAILING:
            del st.trailing[0]

    # ---------------- per partition rollup ----------------
    rows = []
    for pname, plist in per_part.items():
        index_name = parts[pname]["index"]
        st = state[index_name]
        counted = [p for p in plist if p["status"] in COUNTED_STATUSES]
        bands = {name: 0 for name in BAND_NAMES}
        for p in plist:
            bands[p["band"]] += 1
        if counted:
            peak = max(p["cost"] for p in counted)
            best = [p for p in counted if p["cost"] == peak]
            best.sort(key=lambda p: p["seq"])
            top_query = best[0]["query"]
        else:
            peak = 0
            top_query = None
        if st.misses >= STALL_MISSES:
            disposition = "stalled"
        elif st.debt > HELD_DEBT:
            disposition = "held"
        else:
            disposition = "open"
        rows.append({
            "bands": bands,
            "baseline_end": st.baseline,
            "cost_total": sum(p["cost"] for p in counted),
            "disposition": disposition,
            "fetched": sum(1 for p in plist if p["verb"] == "fetch"),
            "flagged": sum(1 for p in plist if p["status"] == "flagged"),
            "lookups": len(plist),
            "misses": st.misses,
            "partition": pname,
            "peak_cost": peak,
            "top_query": top_query,
        })
    rows.sort(key=lambda r: (-r["cost_total"], r["partition"]))

    catalog = {
        "by_band": {name: 0 for name in BAND_NAMES},
        "by_status": {name: 0 for name in ("dropped", "flagged", "locked", "ok", "setup")},
        "cost_total": 0,
        "lookups": len(probes),
        "partitions": len(rows),
        "stalled": sorted(r["partition"] for r in rows if r["disposition"] == "stalled"),
        "top_partition": None,
    }
    for p in probes:
        catalog["by_band"][p["band"]] += 1
        catalog["by_status"][p["status"]] += 1
    for r in rows:
        catalog["cost_total"] += r["cost_total"]
        if catalog["top_partition"] is None or r["cost_total"] >= catalog["top_partition_cost"]:
            catalog["top_partition"] = r["partition"]
            catalog["top_partition_cost"] = r["cost_total"]
    del catalog["top_partition_cost"]

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "probes.jsonl"), "w") as handle:
        for p in probes:
            handle.write(json.dumps(p, sort_keys=True, separators=(",", ":")) + "\n")
    with open(os.path.join(outdir, "partitions.json"), "w") as handle:
        handle.write(json.dumps({"partitions": rows}, sort_keys=True, indent=2) + "\n")
    with open(os.path.join(outdir, "catalog.json"), "w") as handle:
        handle.write(json.dumps(catalog, sort_keys=True, indent=2) + "\n")
    return probes, rows, catalog


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: broker.py <input-dir> <output-dir>\n")
        return 2
    resolve(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
