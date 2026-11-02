#!/usr/bin/env python3
"""Catalogue probe accounting engine.

Usage: broker.py INPUT_DIR OUTPUT_DIR

Reads one recorded broker run (pools.csv, indexes.csv, analysts.csv,
partitions.csv, lookups.jsonl) and writes the three reports
(probes.jsonl, partitions.json, catalog.json) into OUTPUT_DIR.
"""
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# firmware constants
# ---------------------------------------------------------------------------

GAIN = 1270                  # stage 2 gain
COUNT_OFFSET = 1             # added to `rounds` before it multiplies the base
PAGE_FACTOR = 4              # `pages` is scaled by this when it supplies the base

# adjustment tables: ("mul", n, d) -> x*n//d, ("add", k) -> x+k, None -> plain
PLAN_ADJ = {
    "seek": None,
    "scan": ("mul", 3, 2),
    "merge": ("mul", 17, 20),
    "fanout": ("mul", 3, 2),
    "stream": ("mul", 2, 1),
    "nested": ("add", -20),
    "hybrid": ("mul", 1, 2),
}
LAYOUT_ADJ = {
    "btree": None,
    "sparse": ("add", -20),
    "bitmap": ("add", 20),
    "column": ("mul", 2, 1),
}
PHASE_ADJ = {
    "quiet": None,
    "shoulder": ("mul", 11, 10),
    "peak": ("mul", 5, 4),
}
MODE_ADJ = {
    "paired": None,
    "turbo": ("mul", 4, 5),
    "cold": ("mul", 1, 2),
}

CREDIT_RELEASE = 25          # stage 7: amount released from credit per lookup
CREDIT_CEILING = 400         # ceiling the credit never passes
RELIEF_FACTOR = 2            # doubled relief scales the debt taken off
WAIVER_DIVISOR = 2           # stage 10
LOCK_MISSES = 3              # miss count that raises the lock flag
LOCK_RATIO = (3, 2)          # stage 11: cost*n//d
TRAIL_SIZE = 3               # entries kept in the trailing record

BAND_EDGES = (320, 160, 32)  # heavy, warm, light (idle below the last)

BOOKKEEPING_VERBS = ("refresh", "snapshot")
SEALING_VERB = "purge"

TOLERANCE = {               # stage 13: debt_before above this resolves to flagged
    "principal": 200,
    "staff": 150,
    "rotational": 100,
    "vendor": 50,
}

DEBT_DIVISOR = 10            # a fetch adds reach//DEBT_DIVISOR to the debt
DEBT_REPLICA_MUL = (3, 2)    # this replica multiplies the amount by n/d
DEBT_REPLICA_EXTRA = (2, 20)  # this replica adds this fixed extra
DEBT_BACK_TO_BACK = 25       # extra when a fetch directly follows a fetch
DEBT_CEILING = 600           # ceiling the debt never passes
FETCH_BASELINE_BUMP = 4      # a fetch raises the index baseline by this

STALL_MISSES = 3             # disposition: stalled once misses reach this
HELD_DEBT = 150              # disposition: held once debt reaches this
COUNTED_STATUSES = ("ok", "flagged")

# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------


def adjust(form, value):
    if form is None:
        return value
    kind = form[0]
    if kind == "add":
        return value + form[1]
    if kind == "mul":
        prod = value * form[1]
        den = form[2]
        if prod >= 0:
            return prod // den
        return -((-prod) // den)
    raise ValueError(form)


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


class Index(object):
    __slots__ = ("baseline", "debt", "credit", "misses", "seen", "prev_fetch",
                 "waiver", "relief", "locked", "trail")

    def __init__(self, warmup):
        self.baseline = warmup
        self.debt = 0
        self.credit = 0
        self.misses = 0
        self.seen = False
        self.prev_fetch = False
        self.waiver = False
        self.relief = False
        self.locked = False
        self.trail = []


def governing_count(lk):
    if lk["pages"] > 0:
        base = lk["pages"] * PAGE_FACTOR
    else:
        base = lk["reach"]
    return base * (lk["rounds"] + COUNT_OFFSET)


def band_of(cost):
    heavy, warm, light = BAND_EDGES
    if cost >= heavy:
        return "heavy"
    if cost >= warm:
        return "warm"
    if cost >= light:
        return "light"
    return "idle"


def run(indir, outdir):
    pools = {r["pool"]: r for r in read_csv(os.path.join(indir, "pools.csv"))}
    indexes = {r["index"]: r for r in read_csv(os.path.join(indir, "indexes.csv"))}
    analysts = {r["analyst"]: r["clearance"]
                for r in read_csv(os.path.join(indir, "analysts.csv"))}
    partitions = {r["partition"]: r
                  for r in read_csv(os.path.join(indir, "partitions.csv"))}

    lookups = []
    with open(os.path.join(indir, "lookups.jsonl")) as fh:
        for line in fh:
            line = line.strip()
            if line:
                lookups.append(json.loads(line))
    lookups.sort(key=lambda r: r["seq"])

    charged = {}
    for name, row in indexes.items():
        parent = row["parent"]
        charged[name] = indexes[parent]["layout"] if parent else row["layout"]

    state = {name: Index(int(row["warmup"])) for name, row in indexes.items()}

    probes = []
    for lk in lookups:
        part = partitions[lk["partition"]]
        ixname = part["index"]
        ix = state[ixname]
        mode = pools[part["pool"]]["mode"]
        layout = charged[ixname]

        # 1 offset
        value = lk["cursor"] - ix.baseline
        if value < 0:
            value = 0
        # 2 round normalisation
        value = (value * GAIN) // governing_count(lk)
        if value < 0:
            value = 0
        # 3 plan
        value = adjust(PLAN_ADJ[part["plan"]], value)
        # 4 layout
        value = adjust(LAYOUT_ADJ[layout], value)
        # 5 phase (skipped on the index's first lookup)
        if ix.seen:
            value = adjust(PHASE_ADJ[lk["phase"]], value)
        # 6 mode
        value = adjust(MODE_ADJ[mode], value)
        # 7 credit release
        release = ix.credit if ix.credit < CREDIT_RELEASE else CREDIT_RELEASE
        ix.credit -= release
        value += release
        # 8 debt relief
        debt_before = ix.debt
        taken = debt_before
        if ix.relief:
            taken = debt_before * RELIEF_FACTOR
            ix.relief = False
        value -= taken
        if value < 0:
            value = 0
        cost = value
        # 9 repeat query
        for query, remembered in reversed(ix.trail):
            if query == lk["query"]:
                cost = remembered
                break
        # 10 waiver
        if ix.waiver:
            cost = cost // WAIVER_DIVISOR
            ix.waiver = False
        # 11 lock surcharge
        if ix.locked:
            cost = (cost * LOCK_RATIO[0]) // LOCK_RATIO[1]
        # 12 banding
        band = band_of(cost)
        # 13 status
        verb = lk["verb"]
        if verb in BOOKKEEPING_VERBS:
            status = "setup"
        elif verb == SEALING_VERB:
            status = "locked"
        elif band == "idle":
            status = "dropped"
        elif debt_before > TOLERANCE[analysts[lk["analyst"]]]:
            status = "flagged"
        else:
            status = "ok"

        probes.append({
            "analyst": lk["analyst"],
            "band": band,
            "cost": cost,
            "debt_before": debt_before,
            "partition": lk["partition"],
            "query": lk["query"],
            "seq": lk["seq"],
            "status": status,
            "verb": verb,
        })

        # 14 carry update
        if status == "dropped":
            ix.misses += 1
            if ix.misses >= LOCK_MISSES:
                ix.locked = True
        if verb == "refresh":
            ix.baseline = lk["cursor"]
        if verb == "snapshot":
            moved = ix.debt
            room = CREDIT_CEILING - ix.credit
            if moved > room:
                moved = room
            ix.credit += moved
            ix.debt = 0
            ix.waiver = True
        if verb == "fetch":
            amount = lk["reach"] // DEBT_DIVISOR
            replica = int(part["replica"])
            if replica == DEBT_REPLICA_MUL[0]:
                amount = (amount * DEBT_REPLICA_MUL[1]) // 1
            if replica == DEBT_REPLICA_EXTRA[0]:
                amount += DEBT_REPLICA_EXTRA[1]
            if ix.prev_fetch:
                amount += DEBT_BACK_TO_BACK
            ix.debt += amount
            if ix.debt > DEBT_CEILING:
                ix.debt = DEBT_CEILING
            ix.baseline += FETCH_BASELINE_BUMP
        if verb == SEALING_VERB:
            ix.relief = True
        ix.prev_fetch = (verb == "fetch")
        ix.seen = True
        ix.trail.append((lk["query"], cost))
        if len(ix.trail) > TRAIL_SIZE:
            del ix.trail[0]

    rows = []
    stalled = []
    for name in sorted(partitions):
        part = partitions[name]
        mine = [p for p in probes if p["partition"] == name]
        counted = [p for p in mine if p["status"] in COUNTED_STATUSES]
        ix = state[part["index"]]
        bands = {b: 0 for b in ("heavy", "idle", "light", "warm")}
        for p in mine:
            bands[p["band"]] += 1
        peak = 0
        top = None
        for p in counted:
            if top is None or p["cost"] > peak:
                peak = p["cost"]
                top = p["query"]
        if ix.misses >= STALL_MISSES:
            disposition = "stalled"
        elif ix.debt >= HELD_DEBT:
            disposition = "held"
        else:
            disposition = "open"
        if disposition == "stalled":
            stalled.append(name)
        rows.append({
            "bands": bands,
            "baseline_end": ix.baseline,
            "cost_total": sum(p["cost"] for p in counted),
            "disposition": disposition,
            "fetched": sum(1 for p in mine if p["verb"] == "fetch"),
            "flagged": sum(1 for p in mine if p["status"] == "flagged"),
            "lookups": len(mine),
            "misses": ix.misses,
            "partition": name,
            "peak_cost": peak,
            "top_query": top,
        })

    rows.sort(key=lambda r: (-r["cost_total"], r["partition"]))

    by_band = {b: 0 for b in ("heavy", "idle", "light", "warm")}
    for p in probes:
        by_band[p["band"]] += 1
    by_status = {s: 0 for s in ("dropped", "flagged", "locked", "ok", "setup")}
    for p in probes:
        by_status[p["status"]] += 1
    top_partition = None
    best = None
    for r in rows:
        if best is None or r["cost_total"] > best or (
                r["cost_total"] == best and r["partition"] > top_partition):
            best = r["cost_total"]
            top_partition = r["partition"]
    if not rows:
        top_partition = None
    catalog = {
        "by_band": by_band,
        "by_status": by_status,
        "cost_total": sum(r["cost_total"] for r in rows),
        "lookups": len(probes),
        "partitions": len(partitions),
        "stalled": sorted(stalled),
        "top_partition": top_partition,
    }

    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    with open(os.path.join(outdir, "probes.jsonl"), "w") as fh:
        for p in probes:
            fh.write(json.dumps(p, sort_keys=True, separators=(",", ":")) + "\n")
    with open(os.path.join(outdir, "partitions.json"), "w") as fh:
        fh.write(json.dumps({"partitions": rows}, sort_keys=True, indent=2) + "\n")
    with open(os.path.join(outdir, "catalog.json"), "w") as fh:
        fh.write(json.dumps(catalog, sort_keys=True, indent=2) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: broker.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
