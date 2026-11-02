#!/bin/bash
# Oracle dispatcher for b5c7b14c-12b7-543c-8e92-9c19419626bb.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/reconcile.py
python3 /app/out/reconcile.py /app/data /app/out

# Self-check of the delivered program on extracts built in a temporary directory.
python3 - /app/data /app/out <<'PY'
"""Self-check for the delivered reconcile.py on extracts built here.

Run from solve.sh as: python3 - DATA_DIR OUT_DIR

OUT_DIR is the closure the program already wrote over DATA_DIR. Every extract
and every run of this check lives in a temporary directory; OUT_DIR is only read.
Each check prints `check <id> ok` and one witness line.
"""

import csv
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOLDING = ("OPEN", "DEFERRED")
WINDOW_SHUT = "2032-12-01T00:00Z"
FLOOR = 15


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def copy_extract(data, dest, keep_docs):
    os.makedirs(dest)
    for name in sorted(os.listdir(data)):
        if name.endswith(".md") and not keep_docs:
            continue
        shutil.copyfile(os.path.join(data, name), os.path.join(dest, name))


def filter_feed(path, marker, keep_row):
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()
    kept = [line for line in lines if marker not in line or keep_row(line)]
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(kept)


def run_program(program, extract, out, cwd=None):
    result = subprocess.run(
        [sys.executable, "-B", program, extract, out],
        capture_output=True, text=True, cwd=cwd,
    )
    if result.returncode != 0:
        raise SystemExit("self-check run failed on %s: %s" % (extract, result.stderr))


def minutes(stamp):
    moment = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%MZ")
    return int((moment - datetime.datetime(1970, 1, 1)).total_seconds()) // 60


def ledger_of(out):
    return {row["commitment_key"]: row
            for row in read_jsonl(os.path.join(out, "commitment_ledger.jsonl"))}


def blocking_steps(out, ledger):
    """Blocking edges, rebuilt here from live_edges.csv and the ledger states."""
    steps = {}
    for row in read_csv(os.path.join(out, "live_edges.csv")):
        if ledger[row["blocker_key"]]["resolved_state"] in HOLDING:
            steps.setdefault(row["dependent_key"], set()).add(row["blocker_key"])
    return steps


def walk_waits(blocked, steps):
    """Wait of every blocked commitment, walked here from the blocking edges."""
    waits = {}

    def wait(key):
        if key not in blocked:
            return 0
        if key not in waits:
            waits[key] = 1 + max(wait(nxt) for nxt in steps.get(key, ()))
        return waits[key]

    for key in sorted(blocked):
        wait(key)
    return waits


def largest_remainder(total, weights):
    """Split total in proportion to weights; ties of remainder go to the lower key."""
    whole = sum(weights.values())
    shares = {key: total * value // whole for key, value in weights.items()}
    rest = total - sum(shares.values())
    order = sorted(weights, key=lambda key: (-((total * weights[key]) % whole), key))
    for key in order[:rest]:
        shares[key] += 1
    return shares


def waiver_matches(cadence, periods):
    def keep(line):
        fields = line.rstrip("\n").replace("|", ",").split(",")
        return fields[1] == cadence and fields[2] in periods
    return keep


def check_allocation(program, data, base, scratch):
    """P1: allocated minutes of one principal-month recomputed by a separate split."""
    asked = {}
    for row in read_csv(os.path.join(base, "attention_allocation.csv")):
        slot = (row["year_month"], row["obligor_actor"])
        asked.setdefault(slot, {})[row["commitment_key"]] = row
    for row in read_csv(os.path.join(base, "month_load_index.csv")):
        slot = (row["year_month"], row["obligor_actor"])
        lines = asked.get(slot, {})
        demand = {key: int(line["demand_minutes"]) for key, line in lines.items()
                  if int(line["demand_minutes"]) > 0}
        free = max(0, int(row["budget_minutes"]) - int(row["reserve_minutes"]))
        if len(demand) < 3 or sum(demand.values()) <= free or free == 0:
            continue
        shares = largest_remainder(free, demand)
        held = {key: value for key, value in demand.items() if shares[key] >= FLOOR}
        want = dict.fromkeys(demand, 0)
        if held:
            want.update(largest_remainder(free, held))
        got = {key: int(lines[key]["allocated_minutes"]) for key in demand}
        if got != want:
            raise SystemExit("allocation check %r: got %r, want %r" % (slot, got, want))
        print("check R1 ok: %s %s splits %d distributable minutes over %d commitments by a "
              "separate largest remainder and matches attention_allocation.csv" % (
                  slot[0], slot[1], free, len(demand)))
        print("  witness: %s" % ", ".join("%s=%d" % (key, want[key]) for key in sorted(want)))
        return
    raise SystemExit("allocation check: no principal-month asks more than it can be given")


def check_cadence_debt(program, data, base, scratch):
    """P2: debt and streak of one cadence recomputed by a separate walk."""
    governing = {}
    for row in read_csv(os.path.join(data, "cadence_register.csv")):
        held = governing.get(row["cadence_id"])
        if held is None or int(row["revision"]) > int(held["revision"]):
            governing[row["cadence_id"]] = row
    waived = {row["cadence_id"] for row in read_jsonl(os.path.join(base, "waiver_trace.jsonl"))}
    settled = {}
    for row in ledger_of(base).values():
        if row["commitment_class"] == "SETTLED" and row["cadence_ref"]:
            settled.setdefault(row["cadence_ref"], []).append(minutes(row["due_at"]))
    shut = minutes(WINDOW_SHUT)
    debts = {row["cadence_id"]: row for row in read_csv(os.path.join(base, "cadence_debt.csv"))}
    for cadence in sorted(debts):
        if cadence in waived or cadence not in governing or len(settled.get(cadence, ())) < 2:
            continue
        plan = governing[cadence]
        width = int(plan["period_days"]) * 1440
        start = minutes(plan["anchor_at"])
        elapsed = discharged = debt = streak = longest = 0
        while start + elapsed * width < shut:
            low = start + elapsed * width
            high = min(low + width, shut)
            if any(low <= due < high for due in settled[cadence]):
                discharged += 1
                streak = 0
            else:
                debt += 1
                streak += 1
                longest = max(longest, streak)
            elapsed += 1
        row = debts[cadence]
        want = [str(elapsed), str(discharged), "0", str(debt), str(longest)]
        got = [row["periods_elapsed"], row["periods_discharged"], row["periods_waived"],
               row["debt"], row["max_streak"]]
        if got != want:
            raise SystemExit("cadence debt check %s: got %r, want %r" % (cadence, got, want))
        print("check R2 ok: %s walked here from cadence_register.csv and the settled ledger "
              "matches cadence_debt.csv" % cadence)
        print("  witness: elapsed %s discharged %s waived %s debt %s max_streak %s" % tuple(want))
        return
    raise SystemExit("cadence debt check: no waiver-free cadence with two settled commitments")


def check_reserve(program, data, base, scratch):
    """P3: reserve of every principal-month recomputed from walked waits, waivers removed."""
    extract = os.path.join(scratch, "no_waivers")
    copy_extract(data, extract, keep_docs=True)
    for name in os.listdir(extract):
        if name.startswith("waivers_"):
            filter_feed(os.path.join(extract, name), "WVR-", lambda line: False)
    out = extract + "_out"
    run_program(program, extract, out)
    ledger = ledger_of(out)
    blocked = {row["commitment_key"] for row in read_csv(os.path.join(out, "blocked_commitments.csv"))}
    waits = walk_waits(blocked, blocking_steps(out, ledger))
    held = {}
    for key, value in waits.items():
        slot = (ledger[key]["commitment_day"][:7], ledger[key]["obligor_actor"])
        held[slot] = held.get(slot, 0) + value
    rows = read_csv(os.path.join(out, "month_load_index.csv"))
    for row in rows:
        slot = (row["year_month"], row["obligor_actor"])
        if int(row["reserve_minutes"]) != 30 * held.get(slot, 0):
            raise SystemExit("reserve check %r: got %s, want %d" % (
                slot, row["reserve_minutes"], 30 * held.get(slot, 0)))
    top = max(rows, key=lambda row: (int(row["reserve_minutes"]), row["year_month"], row["obligor_actor"]))
    print("check R3 ok: with no waivers every reserve_minutes of %d month_load_index.csv lines "
          "equals thirty minutes per unit of wait walked here" % len(rows))
    print("  witness: %s %s reserve %s" % (top["year_month"], top["obligor_actor"], top["reserve_minutes"]))


def check_closure(program, data, base, scratch):
    """P4: closure of one blocked commitment recomputed by a separate breadth-first walk."""
    ledger = ledger_of(base)
    steps = blocking_steps(base, ledger)
    lines = read_csv(os.path.join(base, "blocked_commitments.csv"))
    target = next(row for row in lines if int(row["chain_depth"]) >= 3)
    key = target["commitment_key"]
    hops = {}
    layer, depth = {key}, 0
    while layer:
        depth += 1
        nxt = set()
        for item in layer:
            for blocker in steps.get(item, ()):
                if blocker not in hops and blocker != key:
                    hops[blocker] = depth
                    nxt.add(blocker)
        layer = nxt
    want = sorted((blocker, hop, "no" if steps.get(blocker) else "yes") for blocker, hop in hops.items())
    got = sorted((row["blocker_key"], row["hop_distance"], row["terminal"])
                 for row in read_jsonl(os.path.join(base, "blocking_closure.jsonl"))
                 if row["dependent_key"] == key)
    if got != want:
        raise SystemExit("closure check %s: got %r, want %r" % (key, got, want))
    print("check R4 ok: %s reaches %d blockers by a separate breadth-first walk, matching its "
          "blocking_closure.jsonl lines" % (key, len(want)))
    print("  witness: %s" % ", ".join("%s@%d" % (blocker, hop) for blocker, hop, _ in want))


def check_altered_copy(program, data, base, scratch):
    """P5: a changed registered budget changes the month_load_index.csv line that reads it."""
    lines = {(row["year_month"], row["obligor_actor"]): row
             for row in read_csv(os.path.join(base, "month_load_index.csv"))}
    slot = next(slot for slot in sorted(lines)
                if lines[slot]["budget_source"] == "REGISTERED"
                and int(lines[slot]["demand_minutes"]) > int(lines[slot]["allocated_minutes"]))
    month, actor = slot
    budget = int(lines[slot]["budget_minutes"]) + 600
    extract = os.path.join(scratch, "altered_budget")
    copy_extract(data, extract, keep_docs=True)
    path = os.path.join(extract, "attention_budget.csv")
    with open(path, encoding="utf-8") as handle:
        rows = handle.readlines()
    marker = "%s,%s," % (actor, month)
    changed = ["%s%d\n" % (marker, budget) if line.startswith(marker) else line for line in rows]
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(changed)
    out = extract + "_out"
    run_program(program, extract, out)
    after = {(row["year_month"], row["obligor_actor"]): row
             for row in read_csv(os.path.join(out, "month_load_index.csv"))}[slot]
    if int(after["budget_minutes"]) != budget or after["allocated_minutes"] == lines[slot]["allocated_minutes"]:
        raise SystemExit("altered copy check %r: budget %s, want %d" % (slot, after["budget_minutes"], budget))
    print("check R5 ok: attention_budget.csv copy with %s %s set to %d moves its month_load_index.csv line" % (
        actor, month, budget))
    print("  witness: before %s / after %s" % (
        ",".join(lines[slot].values()), ",".join(after.values())))


def check_relocated(program, data, base, scratch):
    """P6: a copy of the shipped extract at another path, run from another directory."""
    extract = os.path.join(scratch, "elsewhere", "extract")
    copy_extract(data, extract, keep_docs=False)
    out = os.path.join(scratch, "elsewhere", "closure")
    run_program(program, extract, out, cwd=scratch)
    names = sorted(name for name in os.listdir(base) if name != "reconcile.py")
    differ = []
    for name in names:
        with open(os.path.join(base, name), "rb") as one, open(os.path.join(out, name), "rb") as two:
            if one.read() != two.read():
                differ.append(name)
    if differ:
        raise SystemExit("relocated check: outputs differ %r" % (differ,))
    print("check R6 ok: copy of the shipped extract without its documents, at another path and run "
          "from another directory, gives the same %d outputs byte for byte" % len(names))
    print("  witness: %s run from %s matches %s" % (extract, scratch, base))


def check_shared_allowance(program, data, base, scratch):
    """P7: one principal owns two cadences whose waivers together exceed the allowance."""
    trace = read_jsonl(os.path.join(base, "waiver_trace.jsonl"))
    owned = sorted({row["cadence_id"] for row in trace if row["effect"] == "LAPSED"})
    cadence = owned[0]
    periods = sorted({row["period_index"] for row in trace
                      if row["cadence_id"] == cadence and row["effect"] != "INERT"})[:3]
    twin = "CAD-990"
    extract = os.path.join(scratch, "shared_allowance")
    copy_extract(data, extract, keep_docs=True)
    kept = waiver_matches(cadence, {str(period) for period in periods})
    sample = None
    for name in sorted(os.listdir(extract)):
        if name.startswith("waivers_"):
            path = os.path.join(extract, name)
            filter_feed(path, "WVR-", kept)
            with open(path, encoding="utf-8") as handle:
                found = [line for line in handle if "WVR-" in line]
            sample = sample or (found[0] if found else None)
    reason, stamp = sample.rstrip("\n").replace("|", ",").split(",")[3:5]
    register = os.path.join(extract, "cadence_register.csv")
    with open(register, encoding="utf-8") as handle:
        plans = [line for line in handle if line.startswith(cadence + ",")]
    with open(register, "a", encoding="utf-8") as handle:
        handle.writelines(twin + line[len(cadence):] for line in plans)
    with open(os.path.join(extract, "waivers_desk.csv"), "a", encoding="utf-8") as handle:
        for number, period in enumerate(periods):
            handle.write("WVR-99%03d,%s,%d,%s,%s\n" % (number + 1, twin, period, reason, stamp))
    out = extract + "_out"
    run_program(program, extract, out)
    got = sorted((row["period_start"], row["cadence_id"], row["period_index"], row["effect"])
                 for row in read_jsonl(os.path.join(out, "waiver_trace.jsonl")))
    effects = [row[3] for row in got]
    if len(got) != 6 or effects != ["SUPPRESSED"] * 4 + ["LAPSED"] * 2:
        raise SystemExit("shared allowance check: trace %r" % (got,))
    print("check R7 ok: %s and its twin %s share one owner and carry three waivers each; the "
          "first four by period start are granted and the last two are LAPSED" % (cadence, twin))
    print("  witness: %s" % ", ".join("%s/%d %s" % (row[1], row[2], row[3]) for row in got))


def check_shortcut_chain(program, data, base, scratch):
    """P8: a blocked commitment reaches one blocker by chains of two lengths."""
    ledger = ledger_of(base)
    blocked = {row["commitment_key"] for row in read_csv(os.path.join(base, "blocked_commitments.csv"))}
    steps = blocking_steps(base, ledger)
    stamp = {}
    for row in read_csv(os.path.join(base, "live_edges.csv")):
        stamp[(row["dependent_key"], row["blocker_key"])] = row["asserted_at"]
    added = []
    for first in sorted(blocked):
        if len(added) == 6:
            break
        for middle in sorted(steps.get(first, set()) & blocked):
            far = sorted((steps.get(middle, set()) & blocked) - steps[first] - {first})
            if far:
                added.append((first, far[0], stamp[(first, middle)]))
                break
    if not added:
        raise SystemExit("shortcut check: no chain offers a step to skip")
    extract = os.path.join(scratch, "shortcut")
    copy_extract(data, extract, keep_docs=True)
    with open(os.path.join(extract, "edges_desk_01.csv"), "a", encoding="utf-8") as handle:
        for number, (first, far, when) in enumerate(added):
            handle.write("EDG-99%04d,%s,%s,%s\n" % (number + 1, first, far, when))
    out = extract + "_out"
    run_program(program, extract, out)
    ledger = ledger_of(out)
    lines = {row["commitment_key"]: row for row in read_csv(os.path.join(out, "blocked_commitments.csv"))}
    waits = walk_waits(set(lines), blocking_steps(out, ledger))
    hop = {(row["dependent_key"], row["blocker_key"]): row["hop_distance"]
           for row in read_jsonl(os.path.join(out, "blocking_closure.jsonl"))}
    for first, far, _ in added:
        if hop.get((first, far)) != 1:
            raise SystemExit("shortcut check: %s reaches %s at %r hops" % (first, far, hop.get((first, far))))
    parted = [key for key in sorted(lines) if int(lines[key]["chain_depth"]) != waits[key]]
    if not parted:
        raise SystemExit("shortcut check: no blocked commitment parts its wait from its chain depth")
    first, far, _ = added[0]
    print("check R8 ok: %d shortcut edges; each shortcut blocker sits at hop 1 and %d blocked "
          "commitments part their wait from their chain depth" % (len(added), len(parted)))
    print("  witness: %s reaches %s directly; line %s; wait %d" % (
        first, far, ",".join(lines[first].values()), waits[first]))


def report_identities(base):
    with open(os.path.join(base, "validation_report.json"), encoding="utf-8") as handle:
        report = json.load(handle)
    print("identities: %s" % ", ".join(
        "%s residual %s" % (name, report["identities"][name]) for name in report["identities_checked"]))


def main(argv):
    if len(argv) != 3:
        print("usage: python3 - DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, base = argv[1], argv[2]
    program = os.path.abspath(os.path.join(base, "reconcile.py"))
    scratch = tempfile.mkdtemp(prefix="selfcheck-")
    try:
        check_allocation(program, data, base, scratch)
        check_cadence_debt(program, data, base, scratch)
        check_reserve(program, data, base, scratch)
        check_closure(program, data, base, scratch)
        check_altered_copy(program, data, base, scratch)
        check_relocated(program, data, base, scratch)
        check_shared_allowance(program, data, base, scratch)
        check_shortcut_chain(program, data, base, scratch)
    finally:
        shutil.rmtree(scratch)
    report_identities(base)
    for name in sorted(os.listdir(base)):
        print("wrote %s" % os.path.join(base, name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
PY
