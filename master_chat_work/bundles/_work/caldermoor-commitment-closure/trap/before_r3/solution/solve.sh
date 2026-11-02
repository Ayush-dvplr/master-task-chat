#!/bin/bash
# Oracle dispatcher for caldermoor-commitment-closure.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/reconcile.py
python3 /app/out/reconcile.py /app/data /app/out

# Self-check of the delivered program on small extracts built in a temporary directory.
python3 - /app/data /app/out <<'PY'
"""Self-check for the delivered reconcile.py on small extracts built here.

Run from solve.sh as: python3 - DATA_DIR OUT_DIR

OUT_DIR is the closure the program already wrote over DATA_DIR. Every extract
and every run of this check lives in a temporary directory; OUT_DIR is only read.
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
CLOSED = ("SETTLED", "WITHDRAWN")


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


def run_program(program, extract, out):
    result = subprocess.run(
        [sys.executable, "-B", program, extract, out],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit("self-check run failed on %s: %s" % (extract, result.stderr))


def minutes(stamp):
    moment = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%MZ")
    return int((moment - datetime.datetime(1970, 1, 1)).total_seconds()) // 60


def first_row(path, marker):
    with open(path, encoding="utf-8") as handle:
        return next(line for line in handle if line.startswith(marker))


def check_closed_dependent(program, data, base, scratch):
    ledger = {row["commitment_key"]: row
              for row in read_jsonl(os.path.join(base, "commitment_ledger.jsonl"))}
    states = {key: row["resolved_state"] for key, row in ledger.items()}
    holding = sorted(key for key, state in states.items() if state in HOLDING)
    edges = sorted(read_csv(os.path.join(base, "live_edges.csv")), key=lambda r: r["edge_id"])
    tried = 0
    for row in edges:
        dependent = row["dependent_key"]
        if states.get(dependent) not in CLOSED:
            continue
        blocker = next((key for key in holding if key != dependent
                        and ledger[key]["obligor_actor"] == row["blocker_actor"]), None)
        if blocker is None:
            continue
        tried += 1
        if tried > 8:
            break
        extract = os.path.join(scratch, "closed_dependent_%d" % tried)
        copy_extract(data, extract, keep_docs=True)
        for name in os.listdir(extract):
            if name.startswith("edges_"):
                filter_feed(os.path.join(extract, name), "EDG-", lambda line: False)
        with open(os.path.join(extract, "edges_desk_01.csv"), "a", encoding="utf-8") as handle:
            handle.write("EDG-990001,%s,%s,%s\n" % (dependent, blocker, row["asserted_at"]))
        out = extract + "_out"
        run_program(program, extract, out)
        if not read_csv(os.path.join(out, "live_edges.csv")):
            continue
        with open(os.path.join(out, "blocked_commitments.csv"), encoding="utf-8") as handle:
            body = handle.read().splitlines()[1:]
        want = "%s,1,1,1,%s,0" % (dependent, blocker)
        if body != [want]:
            raise SystemExit("closed dependent check: got %r, want %r" % (body, [want]))
        print("check 1 ok: %s (%s) with one live edge to %s (%s) is blocked: %s" % (
            dependent, states[dependent], blocker, states[blocker], want))
        return
    raise SystemExit("closed dependent check: no constructed edge stayed live")


def waiver_matches(cadence, period=None):
    def keep(line):
        fields = line.rstrip("\n").replace("|", ",").split(",")
        return fields[1] == cadence and (period is None or fields[2] == str(period))
    return keep


def only_waivers(data, extract, keep):
    copy_extract(data, extract, keep_docs=True)
    for name in os.listdir(extract):
        if name.startswith("waivers_"):
            filter_feed(os.path.join(extract, name), "WVR-", keep)


def check_inert_waiver(program, data, base, scratch):
    governing = {}
    for row in read_csv(os.path.join(data, "cadence_register.csv")):
        held = governing.get(row["cadence_id"])
        if held is None or int(row["revision"]) > int(held["revision"]):
            governing[row["cadence_id"]] = row
    settled = sorted(
        (row for row in read_jsonl(os.path.join(base, "commitment_ledger.jsonl"))
         if row["commitment_class"] == "SETTLED" and row["cadence_ref"] in governing),
        key=lambda r: r["commitment_key"])
    for row in settled:
        plan = governing[row["cadence_ref"]]
        width = int(plan["period_days"]) * 1440
        period = (minutes(row["due_at"]) - minutes(plan["anchor_at"])) // width
        if period >= 0:
            break
    else:
        raise SystemExit("inert waiver check: no settled commitment discharges a period")
    cadence = row["cadence_ref"]
    stamp = first_row(os.path.join(data, "waivers_desk.csv"), "WVR-").split(",")[4].strip()
    extract = os.path.join(scratch, "inert_waiver")
    only_waivers(data, extract, lambda line: False)
    with open(os.path.join(extract, "waivers_desk.csv"), "a", encoding="utf-8") as handle:
        handle.write("WVR-99001,%s,%d,AGREED,%s\n" % (cadence, period, stamp))
    out = os.path.join(scratch, "inert_waiver_out")
    run_program(program, extract, out)
    trace = read_jsonl(os.path.join(out, "waiver_trace.jsonl"))
    got = [(row["cadence_id"], row["period_index"], row["effect"]) for row in trace]
    if got != [(cadence, period, "INERT")]:
        raise SystemExit("inert waiver check: trace %r" % (got,))
    debt = {row["cadence_id"]: row for row in read_csv(os.path.join(out, "cadence_debt.csv"))}
    if debt[cadence]["periods_waived"] != "0":
        raise SystemExit("inert waiver check: periods_waived %s" % debt[cadence]["periods_waived"])
    print("check 2 ok: waiver on period %d of %s, discharged by %s, is INERT and periods_waived is 0" % (
        period, cadence, row["commitment_key"]))


def check_allowance(program, data, base, scratch):
    trace = read_jsonl(os.path.join(base, "waiver_trace.jsonl"))
    counts = {}
    for row in trace:
        counts.setdefault(row["cadence_id"], []).append(row["effect"])
    cadence = next(key for key in sorted(counts)
                   if len(counts[key]) > 4 and "LAPSED" in counts[key])
    extract = os.path.join(scratch, "allowance")
    only_waivers(data, extract, waiver_matches(cadence))
    out = os.path.join(scratch, "allowance_out")
    run_program(program, extract, out)
    got = [row["effect"] for row in read_jsonl(os.path.join(out, "waiver_trace.jsonl"))]
    drawn = len(counts[cadence])
    if len(got) != drawn or "LAPSED" in got[:4] or set(got[4:]) != {"LAPSED"}:
        raise SystemExit("allowance check: effects %r for %d waivers" % (got, drawn))
    with open(os.path.join(out, "run_manifest.json"), encoding="utf-8") as handle:
        lapsed = json.load(handle)["waivers_lapsed"]
    debt = {row["cadence_id"]: row for row in read_csv(os.path.join(out, "cadence_debt.csv"))}
    waived = int(debt[cadence]["periods_waived"])
    if lapsed != drawn - 4 or waived != got.count("SUPPRESSED"):
        raise SystemExit("allowance check: waivers_lapsed %s periods_waived %s" % (lapsed, waived))
    print("check 4 ok: %s alone carries %d waivers; the first four by period start are granted, "
          "%d are LAPSED and periods_waived is %d" % (cadence, drawn, lapsed, waived))


def check_other_extract(program, data, base, scratch):
    extract = os.path.join(scratch, "data_only")
    copy_extract(data, extract, keep_docs=False)
    out = os.path.join(scratch, "data_only_out")
    run_program(program, extract, out)
    names = sorted(name for name in os.listdir(base) if name != "reconcile.py")
    differ = []
    for name in names:
        with open(os.path.join(base, name), "rb") as one, open(os.path.join(out, name), "rb") as two:
            if one.read() != two.read():
                differ.append(name)
    if differ:
        raise SystemExit("other extract check: outputs differ %r" % (differ,))
    print("check 3 ok: extract without the eight documents gives the same %d outputs" % len(names))


def main(argv):
    if len(argv) != 3:
        print("usage: python3 - DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, base = argv[1], argv[2]
    program = os.path.join(base, "reconcile.py")
    scratch = tempfile.mkdtemp(prefix="selfcheck-")
    try:
        check_closed_dependent(program, data, base, scratch)
        check_inert_waiver(program, data, base, scratch)
        check_other_extract(program, data, base, scratch)
        check_allowance(program, data, base, scratch)
    finally:
        shutil.rmtree(scratch)
    for name in sorted(os.listdir(base)):
        print("wrote %s" % os.path.join(base, name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
PY
