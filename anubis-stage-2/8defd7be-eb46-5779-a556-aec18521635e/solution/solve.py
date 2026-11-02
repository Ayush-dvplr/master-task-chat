#!/usr/bin/env python3
"""Reference solve for 8defd7be-eb46-5779-a556-aec18521635e.

The engine below is written against the contract in data/broker.md and
data/reports.md, the same notes the agent is given. It carries the same
constants as the verifier, so its agreement with the grader is not evidence
that the task is solvable; that rests on the identifiability sweep recorded in
TRUTH.md. The harness underneath it does the checking the instruction asks for:
a held back block replayed, a counterfactual input that separates the later
lookup reading of the top_query tie break from the larger query reading, a pair
of partitions that narrows the scan offset, a longhand second walk for
total_debt, and a byte for byte comparison against both shipped reference
rollups.
"""

import json
import os
import subprocess
import sys

BROKER_SOURCE = r'''#!/usr/bin/env python3
import csv
import json
import pathlib
import sys

FEE_SCALE = 1440
PAGE_FACTOR = 4
COUNT_DIVISOR = 40
RELEASE_CAP = 36
CREDIT_CAP = 90
DEBT_CAP = 120
BASELINE_BUMP = 4
LOCK_AFTER = 2
STALL_AFTER = 3
HELD_ABOVE = 39
WINDOW = 4
COLD_CEILING = 540

# The keyed steps floor every division, so a figure the scan plan pushed below
# zero rounds away from zero on the way through the later ratios.
PLAN_STEP = {
    "scan": lambda n: n - 7,
    "merge": lambda n: n * 2 // 3,
    "fanout": lambda n: n + 11,
    "stream": lambda n: n - (n % 9),
    "nested": lambda n: n * 13 // 11,
    "hybrid": lambda n: n // 3,
}
LAYOUT_STEP = {
    "sparse": lambda n: n * 8 // 9,
    "bitmap": lambda n: n + 17,
    "column": lambda n: n * 3 // 2,
}
PHASE_STEP = {
    "shoulder": lambda n: n - n // 6,
    "peak": lambda n: n + 9,
}
MODE_STEP = {
    "turbo": lambda n: n * 19 // 17,
    "cold": lambda n: min(n, COLD_CEILING) - 13,
}

BAND_FLOORS = (("heavy", 320), ("warm", 160), ("light", 30))
CLEARANCE_ALLOWANCE = {"principal": 48, "staff": 30, "rotational": 14}
SETUP_VERBS = ("refresh", "snapshot")
BAND_KEYS = ("heavy", "idle", "light", "warm")
STATUS_KEYS = ("dropped", "flagged", "locked", "ok", "setup")
COUNTED = ("ok", "flagged")


def _table(path):
    return list(csv.DictReader(pathlib.Path(path).read_text(encoding="utf-8").splitlines()))


def _records(path):
    body = pathlib.Path(path).read_text(encoding="utf-8")
    return [json.loads(ln) for ln in body.splitlines() if ln.strip()]


def load_corpus(data_dir):
    root = pathlib.Path(data_dir)
    pools = {
        r["pool"]: {"mode": r["mode"], "lag": int(r["lag"])}
        for r in _table(root / "pools.csv")
    }
    indexes = {
        r["index"]: {
            "layout": r["layout"],
            "parent": r["parent"],
            "warmup": int(r["warmup"]),
        }
        for r in _table(root / "indexes.csv")
    }
    analysts = {r["analyst"]: {"clearance": r["clearance"]} for r in _table(root / "analysts.csv")}
    partitions = {
        r["partition"]: {
            "pool": r["pool"],
            "index": r["index"],
            "plan": r["plan"],
            "replica": int(r["replica"]),
        }
        for r in _table(root / "partitions.csv")
    }
    lookups = [
        {
            "seq": int(r["seq"]),
            "partition": r["partition"],
            "query": r["query"],
            "analyst": r["analyst"],
            "verb": r["verb"],
            "phase": r["phase"],
            "cursor": int(r["cursor"]),
            "reach": int(r["reach"]),
            "pages": int(r["pages"]),
            "rounds": int(r["rounds"]),
        }
        for r in _records(root / "lookups.jsonl")
    ]
    return {
        "pools": pools,
        "indexes": indexes,
        "analysts": analysts,
        "partitions": partitions,
        "lookups": lookups,
    }


def charged_layout(indexes, index):
    entry = indexes[index]
    owner = entry["parent"]
    return indexes[owner]["layout"] if owner else entry["layout"]


def _governing(lookup):
    head = lookup["pages"] * PAGE_FACTOR if lookup["pages"] > 0 else lookup["reach"]
    return head * (lookup["rounds"] + 1)


def _keyed(table, key, n):
    step = table.get(key)
    return n if step is None else step(n)


def _band_of(cost):
    for name, floor in BAND_FLOORS:
        if cost >= floor:
            return name
    return "idle"


def _allowance(clearance):
    return CLEARANCE_ALLOWANCE.get(clearance, 0)


def _verdict(verb, band, debt_in, clearance):
    if verb in SETUP_VERBS:
        return "setup"
    if verb == "purge":
        return "locked"
    if band == "idle":
        return "dropped"
    return "flagged" if debt_in > _allowance(clearance) else "ok"


def _debt_step(reach, replica, run):
    step = reach // COUNT_DIVISOR
    if replica == 3:
        step *= 2
    elif replica == 2:
        step += 7
    return step + 5 if run >= 1 else step


def _release(credit):
    return min(credit, RELEASE_CAP) if credit > 0 else 0


def _fresh_slot(warmup):
    return {
        "baseline": warmup,
        "debt": 0,
        "credit": 0,
        "misses": 0,
        "run": 0,
        "seen": 0,
        "waiver": 0,
        "doubled": 0,
        "locked": 0,
        "recent": [],
    }


def resolve(corpus):
    pools, indexes = corpus["pools"], corpus["indexes"]
    analysts, partitions = corpus["analysts"], corpus["partitions"]

    ledger = {}
    for part in partitions.values():
        ledger.setdefault(part["index"], _fresh_slot(indexes[part["index"]]["warmup"]))

    probes = []
    for lookup in sorted(corpus["lookups"], key=lambda r: r["seq"]):
        part = partitions[lookup["partition"]]
        slot = ledger[part["index"]]
        query = lookup["query"]

        figure = max(0, lookup["cursor"] - slot["baseline"])
        figure = max(0, figure * FEE_SCALE // _governing(lookup))
        figure = _keyed(PLAN_STEP, part["plan"], figure)
        figure = _keyed(LAYOUT_STEP, charged_layout(indexes, part["index"]), figure)
        if slot["seen"]:
            figure = _keyed(PHASE_STEP, lookup["phase"], figure)
        figure = _keyed(MODE_STEP, pools[part["pool"]]["mode"], figure)

        handed = _release(slot["credit"])
        figure += handed
        debt_in = slot["debt"]
        owed = debt_in * 2 if slot["doubled"] else debt_in
        if slot["doubled"]:
            slot["doubled"] = 0
        cost = max(0, figure - owed)

        repeat = next((c for q, c in reversed(slot["recent"]) if q == query), None)
        if repeat is not None:
            cost = repeat
        if slot["waiver"]:
            cost //= 2
            slot["waiver"] = 0
        if slot["locked"]:
            cost = cost * 3 // 2

        band = _band_of(cost)
        verdict = _verdict(lookup["verb"], band, debt_in, analysts[lookup["analyst"]]["clearance"])
        probes.append({
            "analyst": lookup["analyst"],
            "band": band,
            "cost": cost,
            "debt_before": debt_in,
            "partition": lookup["partition"],
            "query": query,
            "seq": lookup["seq"],
            "status": verdict,
            "verb": lookup["verb"],
        })

        if verdict == "dropped":
            slot["misses"] += 1
            if slot["misses"] >= LOCK_AFTER:
                slot["locked"] = 1
        slot["credit"] -= handed

        verb = lookup["verb"]
        if verb == "refresh":
            slot["baseline"] = lookup["cursor"]
            slot["run"] = 0
        elif verb == "snapshot":
            slot["credit"] = min(slot["credit"] + slot["debt"], CREDIT_CAP)
            slot["debt"] = 0
            slot["waiver"] = 1
            slot["run"] = 0
        elif verb == "fetch":
            grown = slot["debt"] + _debt_step(lookup["reach"], part["replica"], slot["run"])
            slot["debt"] = min(grown, DEBT_CAP)
            slot["baseline"] += BASELINE_BUMP
            slot["run"] += 1
        else:
            slot["doubled"] = 1
            slot["run"] = 0

        slot["recent"].append((query, cost))
        slot["recent"] = slot["recent"][-WINDOW:]
        slot["seen"] = 1

    partition_rows = []
    for name in sorted(partitions):
        slot = ledger[partitions[name]["index"]]
        mine = [row for row in probes if row["partition"] == name]
        kept = [row for row in mine if row["status"] in COUNTED]
        leader = None
        for row in kept:
            if leader is None or (row["cost"], row["seq"]) > (leader["cost"], leader["seq"]):
                leader = row
        misses, debt_out = slot["misses"], slot["debt"]
        if misses >= STALL_AFTER:
            outcome = "stalled"
        elif debt_out > HELD_ABOVE:
            outcome = "held"
        else:
            outcome = "open"
        spread = {key: 0 for key in BAND_KEYS}
        for row in mine:
            spread[row["band"]] += 1
        partition_rows.append({
            "bands": spread,
            "baseline_end": slot["baseline"],
            "cost_total": sum(row["cost"] for row in kept),
            "disposition": outcome,
            "fetched": sum(1 for row in mine if row["verb"] == "fetch"),
            "flagged": sum(1 for row in mine if row["status"] == "flagged"),
            "lookups": len(mine),
            "misses": misses,
            "partition": name,
            "peak_cost": max((row["cost"] for row in kept), default=0),
            "top_query": leader["query"] if leader is not None else None,
        })
    partition_rows.sort(key=lambda row: (-row["cost_total"], row["partition"]))

    band_tally = {key: 0 for key in BAND_KEYS}
    status_tally = {key: 0 for key in STATUS_KEYS}
    for row in probes:
        band_tally[row["band"]] += 1
        status_tally[row["status"]] += 1

    front = None
    for row in partition_rows:
        if front is None or (row["cost_total"], row["partition"]) > (
            front["cost_total"], front["partition"]
        ):
            front = row

    catalog = {
        "by_band": band_tally,
        "by_status": status_tally,
        "cost_total": sum(row["cost_total"] for row in partition_rows),
        "lookups": len(probes),
        "partitions": len(partition_rows),
        "stalled": sorted(
            row["partition"] for row in partition_rows if row["disposition"] == "stalled"
        ),
        "top_partition": front["partition"] if front is not None else None,
    }
    return probes, partition_rows, catalog


def derive(data_dir):
    return resolve(load_corpus(data_dir))


def render_probes(probes):
    packed = [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in probes]
    return "".join(line + "\n" for line in packed)


def render_document(payload):
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def write_reports(out_dir, probes, partition_rows, catalog):
    target = pathlib.Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "probes.jsonl").write_text(render_probes(probes), encoding="utf-8", newline="")
    (target / "partitions.json").write_text(
        render_document({"partitions": partition_rows}), encoding="utf-8", newline=""
    )
    (target / "catalog.json").write_text(render_document(catalog), encoding="utf-8", newline="")


def main(argv):
    probes, partition_rows, catalog = derive(argv[0])
    write_reports(argv[1], probes, partition_rows, catalog)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


FIGURE_NAMES = [
    "total_cost",
    "ok_cost",
    "dropped_cost",
    "setup_cost",
    "locked_cost",
    "heavy_band_cost",
    "warm_band_cost",
    "light_band_cost",
    "fetch_cost",
    "peak_phase_cost",
    "shoulder_phase_cost",
    "sparse_cost",
    "stream_cost",
    "turbo_cost",
    "cold_cost",
    "shared_index_cost",
    "derived_view_cost",
    "replica3_cost",
    "total_debt",
    "flagged_debt",
]

DATA_DIR = "/app/data"
OUT_DIR = "/app/out"
SCRIPT = "/app/out/broker.py"
REFERENCE = (("partitions.json", "ref_partitions.json"),
             ("catalog.json", "ref_catalog.json"))
REPORTS = ("probes.jsonl", "partitions.json", "catalog.json")


def load_engine():
    namespace = {"__name__": "broker_reference"}
    exec(compile(BROKER_SOURCE, SCRIPT, "exec"), namespace)
    return namespace


def closing_figures(engine, corpus, probes):
    partitions = corpus["partitions"]
    pools = corpus["pools"]
    indexes = corpus["indexes"]
    phases = {}
    for row in corpus["lookups"]:
        phases[row["seq"]] = row["phase"]

    def part_of(row):
        return partitions[row["partition"]]

    shared = shared_indexes(corpus)
    figures = {}
    figures["total_cost"] = sum(row["cost"] for row in probes)
    for status in ("ok", "dropped", "setup", "locked"):
        figures["%s_cost" % status] = sum(
            row["cost"] for row in probes if row["status"] == status)
    for band in ("heavy", "warm", "light"):
        figures["%s_band_cost" % band] = sum(
            row["cost"] for row in probes if row["band"] == band)
    figures["fetch_cost"] = sum(
        row["cost"] for row in probes if row["verb"] == "fetch")
    for phase in ("peak", "shoulder"):
        figures["%s_phase_cost" % phase] = sum(
            row["cost"] for row in probes if phases[row["seq"]] == phase)
    figures["sparse_cost"] = sum(
        row["cost"] for row in probes
        if engine["charged_layout"](indexes, part_of(row)["index"]) == "sparse")
    figures["stream_cost"] = sum(
        row["cost"] for row in probes if part_of(row)["plan"] == "stream")
    for mode in ("turbo", "cold"):
        figures["%s_cost" % mode] = sum(
            row["cost"] for row in probes
            if pools[part_of(row)["pool"]]["mode"] == mode)
    figures["shared_index_cost"] = sum(
        row["cost"] for row in probes if part_of(row)["index"] in shared)
    figures["derived_view_cost"] = sum(
        row["cost"] for row in probes if indexes[part_of(row)["index"]]["parent"])
    figures["replica3_cost"] = sum(
        row["cost"] for row in probes if part_of(row)["replica"] == 3)
    figures["total_debt"] = sum(row["debt_before"] for row in probes)
    figures["flagged_debt"] = sum(
        row["debt_before"] for row in probes if row["status"] == "flagged")
    return figures


def reference_text(name):
    with open(os.path.join(DATA_DIR, name), "rb") as handle:
        return handle.read().decode("utf-8")


def reference_partitions():
    rows = {}
    for row in json.loads(reference_text("ref_partitions.json"))["partitions"]:
        rows[row["partition"]] = row
    return rows


def subset(corpus, keep):
    return {
        "pools": corpus["pools"],
        "indexes": corpus["indexes"],
        "analysts": corpus["analysts"],
        "partitions": dict((name, corpus["partitions"][name]) for name in keep),
        "lookups": [row for row in corpus["lookups"] if row["partition"] in keep],
    }


def shared_indexes(corpus):
    seen = {}
    for name, partition in corpus["partitions"].items():
        seen.setdefault(partition["index"], []).append(name)
    return set(index for index, names in seen.items() if len(names) > 1)


def holdout_check(engine, corpus, reference):
    shared = shared_indexes(corpus)
    order = [name for name in sorted(corpus["partitions"])
             if corpus["partitions"][name]["index"] not in shared]
    split = len(order) - 11
    kept = order[:split] + [name for name in sorted(corpus["partitions"])
                            if corpus["partitions"][name]["index"] in shared]
    held = order[split:]
    _probes, partial, _catalog = engine["resolve"](subset(corpus, kept))
    for row in partial:
        if row != reference[row["partition"]]:
            raise SystemExit("a kept partition disagrees with the reference at %s"
                             % row["partition"])
    print("set aside %d partitions and resolved the other %d: every kept rollup "
          "matches the reference" % (len(held), len(kept)))

    _probes, replay, _catalog = engine["resolve"](corpus)
    checked = 0
    for row in replay:
        if row["partition"] in held:
            if row != reference[row["partition"]]:
                raise SystemExit("a set aside partition disagrees at %s"
                                 % row["partition"])
            checked = checked + 1
    print("replayed the set aside block: all %d held back rollups match the reference"
          % checked)
    return replay


def rival_top_query(probes, partition_id):
    best = None
    for row in probes:
        if row["partition"] != partition_id:
            continue
        if row["status"] != "ok" and row["status"] != "flagged":
            continue
        if best is None:
            best = row
        elif row["cost"] > best["cost"]:
            best = row
        elif row["cost"] == best["cost"] and row["query"] > best["query"]:
            best = row
    return best["query"] if best is not None else None


def counterfactual_check(engine, probes, partition_rows):
    probe = {
        "pools": {"CF-POOL": {"mode": "paired", "lag": 30}},
        "indexes": {"CF-INDEX": {"layout": "btree", "parent": "", "warmup": 100}},
        "analysts": {"CF-ANALYST": {"clearance": "principal"}},
        "partitions": {"CF-PART": {"pool": "CF-POOL", "index": "CF-INDEX",
                                   "plan": "seek", "replica": 1}},
        "lookups": [
            {"seq": 1, "partition": "CF-PART", "query": "CF-Q2",
             "analyst": "CF-ANALYST", "verb": "fetch", "phase": "quiet",
             "cursor": 1300, "reach": 1200, "pages": 0, "rounds": 1},
            {"seq": 2, "partition": "CF-PART", "query": "CF-Q1",
             "analyst": "CF-ANALYST", "verb": "fetch", "phase": "quiet",
             "cursor": 1354, "reach": 1200, "pages": 0, "rounds": 1},
            {"seq": 3, "partition": "CF-PART", "query": "CF-Q3",
             "analyst": "CF-ANALYST", "verb": "fetch", "phase": "quiet",
             "cursor": 900, "reach": 1200, "pages": 0, "rounds": 1},
        ],
    }
    probe_probes, probe_rows, _catalog = engine["resolve"](probe)
    taken = probe_rows[0]["top_query"]
    rival = rival_top_query(probe_probes, "CF-PART")
    if taken == rival:
        raise SystemExit("the counterfactual input leaves the two tie break readings together")
    print("built a two lookup tie on CF-PART at cost %d: the later lookup reading gives "
          "%s, the larger query reading gives %s" % (probe_rows[0]["peak_cost"], taken, rival))

    disagree = sum(1 for row in partition_rows
                   if row["top_query"] != rival_top_query(probes, row["partition"]))
    if disagree == 0:
        raise SystemExit("the recorded run leaves the two tie break readings together")
    print("over the recorded run the two readings disagree on %d partitions, and the "
          "later lookup reading is the one the reference carries" % disagree)


def longhand_total_debt(corpus):
    partitions = corpus["partitions"]
    debt = {}
    credit = {}
    run = {}
    for partition in partitions.values():
        debt[partition["index"]] = 0
        credit[partition["index"]] = 0
        run[partition["index"]] = 0
    running = 0
    for lookup in sorted(corpus["lookups"], key=lambda row: row["seq"]):
        partition = partitions[lookup["partition"]]
        index = partition["index"]
        running = running + debt[index]
        held = credit[index]
        used = 0
        if held > 0:
            used = 36 if held > 36 else held
        credit[index] = held - used
        verb = lookup["verb"]
        if verb == "fetch":
            step = lookup["reach"] // 40
            if partition["replica"] == 3:
                step = step + step
            elif partition["replica"] == 2:
                step = step + 7
            if run[index] >= 1:
                step = step + 5
            total = debt[index] + step
            debt[index] = 120 if total > 120 else total
            run[index] = run[index] + 1
        elif verb == "snapshot":
            banked = credit[index] + debt[index]
            credit[index] = 90 if banked > 90 else banked
            debt[index] = 0
            run[index] = 0
        else:
            run[index] = 0
    return running


def keyed_triples(engine, corpus):
    keyed = {}
    for name, partition in corpus["partitions"].items():
        keyed[name] = (
            partition["plan"],
            engine["charged_layout"](corpus["indexes"], partition["index"]),
            corpus["pools"][partition["pool"]]["mode"],
        )
    return keyed


def paired_survey(engine, corpus, reference):
    keyed = keyed_triples(engine, corpus)
    order = sorted(corpus["partitions"])
    pairs = []
    for left in order:
        for right in order:
            if left >= right:
                continue
            gaps = [position for position in range(3)
                    if keyed[left][position] != keyed[right][position]]
            if len(gaps) == 1:
                pairs.append((left, right, ("plan", "layout", "mode")[gaps[0]],
                              keyed[left][gaps[0]], keyed[right][gaps[0]]))
    if not pairs:
        raise SystemExit("the recorded run holds no pair of partitions differing in one keyed column")
    shown = 0
    seen = set()
    for left, right, column, left_value, right_value in pairs:
        if (column, left_value, right_value) in seen:
            continue
        seen.add((column, left_value, right_value))
        print("%s and %s share two keyed columns and differ on %s (%s against %s): "
              "cost totals %d and %d"
              % (left, right, column, left_value, right_value,
                 reference[left]["cost_total"], reference[right]["cost_total"]))
        shown = shown + 1
        if shown >= 8:
            break
    print("read %d keyed differences off pairs of partitions that share their other "
          "two keyed columns" % shown)
    return pairs


def narrow_by_pair(engine, corpus, reference, pairs):
    shared = shared_indexes(corpus)
    for left, right, column, left_value, right_value in pairs:
        if (column == "plan" and set((left_value, right_value)) == set(("seek", "scan"))
                and corpus["partitions"][left]["index"] not in shared
                and corpus["partitions"][right]["index"] not in shared):
            break
    else:
        raise SystemExit("no seek and scan pair to narrow the scan offset with")
    keep = subset(corpus, [left, right])
    original = engine["PLAN_STEP"]["scan"]
    survivors = []
    try:
        for offset in range(0, 21):
            engine["PLAN_STEP"]["scan"] = lambda n, offset=offset: n - offset
            _probes, rows, _catalog = engine["resolve"](keep)
            if all(row == reference[row["partition"]] for row in rows):
                survivors.append(offset)
    finally:
        engine["PLAN_STEP"]["scan"] = original
    if len(survivors) != 1 or original(0) != -survivors[0]:
        raise SystemExit("the pair did not narrow the scan offset to the program's value")
    print("narrowed the scan offset from 21 candidates to %s with %s (%s) against %s (%s)"
          % (survivors, left, left_value, right, right_value))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    engine = load_engine()
    corpus = engine["load_corpus"](DATA_DIR)
    print("read %d lookups over %d partitions from %s"
          % (len(corpus["lookups"]), len(corpus["partitions"]), DATA_DIR))

    with open(SCRIPT, "w", encoding="utf-8", newline="") as handle:
        handle.write(BROKER_SOURCE)
    print("put the program in place at %s before checking the fit" % SCRIPT)

    reference = reference_partitions()
    partition_rows = holdout_check(engine, corpus, reference)
    probes, _rows, _catalog = engine["resolve"](corpus)
    counterfactual_check(engine, probes, partition_rows)
    pairs = paired_survey(engine, corpus, reference)
    narrow_by_pair(engine, corpus, reference, pairs)

    figures = closing_figures(engine, corpus, probes)
    longhand = longhand_total_debt(corpus)
    if longhand != figures["total_debt"]:
        raise SystemExit("the longhand debt walk disagrees with the ledger")
    print("worked total_debt out a second time, through a separate walk over the "
          "lookups: %d" % longhand)

    result = subprocess.run([sys.executable, SCRIPT, DATA_DIR, OUT_DIR])
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    matched = 0
    for name, expected_name in REFERENCE:
        with open(os.path.join(OUT_DIR, name), "rb") as handle:
            produced = handle.read().decode("utf-8")
        if produced != reference_text(expected_name):
            raise SystemExit("%s differs from %s" % (name, expected_name))
        matched = matched + 1
    print("compared both of my own rollups against the shipped reference files byte "
          "for byte and all %d match" % matched)

    rerun_dir = os.path.join(OUT_DIR, "rerun")
    result = subprocess.run([sys.executable, SCRIPT, DATA_DIR, rerun_dir])
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    for name in REPORTS:
        with open(os.path.join(OUT_DIR, name), "rb") as handle:
            first = handle.read()
        with open(os.path.join(rerun_dir, name), "rb") as handle:
            again = handle.read()
        if first != again:
            raise SystemExit("%s differs between two runs over one input" % name)
    print("ran the program a second time over the same input directory and compared "
          "all %d report files byte for byte: identical" % len(REPORTS))

    print("closing report for the shipped catalogue run:")
    for name in FIGURE_NAMES:
        print("%s = %d" % (name, figures[name]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
