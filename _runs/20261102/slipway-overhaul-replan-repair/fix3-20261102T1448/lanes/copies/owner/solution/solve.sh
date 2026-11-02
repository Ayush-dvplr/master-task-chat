#!/bin/bash
# Oracle dispatcher for slipway-overhaul-replan-repair.
set -euo pipefail

SOLUTION_DIR="${SOLUTION_ROOT:-/solution}"
if [ -f /solution/solve.py ]; then
  SOLUTION_DIR=/solution
fi

# Read the two opening papers before any other working paper.
echo "== /app/data/00_open_this_first.txt"
head -n 12 /app/data/00_open_this_first.txt
echo "== /app/data/replan_programme_contract.md"
head -n 12 /app/data/replan_programme_contract.md

python3 "$SOLUTION_DIR/solve.py"

test -s /app/out/patched_engine.zip
test -s /app/out/25_summary.json
test -s /app/out/24_run_manifest.txt

cd /app/project && PYTHONPATH=/app/project/src python3 -m unittest discover -s tests -t tests -q

python3 - <<'PY'
import json
from pathlib import Path

out = Path("/app/out")
required = ["patched_engine.zip"] + [
    "01_identifier_canon.json", "02_precedence_edges.tsv",
    "03_reverse_index.json", "04_normalised_jobs.csv",
    "05_normalised_rules.csv", "06_feasibility_map.csv",
    "07_closure_map.jsonl", "08_demand_vectors.csv",
    "09_conflict_groups.json", "10_charge_contributions.csv",
    "11_baseline_selection.json", "12_baseline_trace.jsonl",
    "13_amendment_classification.csv", "14_invalidation_sets.jsonl",
    "15_reuse_ledger.csv", "16_work_counters.csv", "17_cache_summary.json",
    "18_final_selection.json", "19_rejected_register.csv",
    "20_resource_usage.tsv", "21_amendment_optima.csv",
    "22_defect_register.md", "23_verification_notes.md",
    "24_run_manifest.txt", "25_summary.json"]
missing = [n for n in required if not (out / n).is_file()]
if missing:
    raise SystemExit("missing oracle artifacts: {}".format(missing))

summary = json.loads((out / "25_summary.json").read_text(encoding="utf-8"))
totals = summary["control_totals"]
if totals["jobs_in_force"] <= 0 or totals["edges_accepted"] <= 0:
    raise SystemExit("oracle derived an empty round")
if totals["amendments_applied"] <= 0:
    raise SystemExit("oracle folded in no amendment")
if totals["cells_recomputed_after_build"] >= totals["cells_in_model"]:
    raise SystemExit("oracle rebuilt the whole model after the build")

classes = (out / "13_amendment_classification.csv").read_text(encoding="utf-8").splitlines()[1:]
if not any(row.split(",")[4] == "inert" for row in classes):
    raise SystemExit("oracle classified no amendment as inert")

counters = (out / "16_work_counters.csv").read_text(encoding="utf-8").splitlines()[1:]
if not any(int(row.split(",")[3]) == 0 for row in counters):
    raise SystemExit("oracle reached a cell for every amendment")
if not any(int(row.split(",")[9]) == 0 and int(row.split(",")[8]) > 0
           for row in counters):
    raise SystemExit("oracle never read a value back out of the store")

manifest = (out / "24_run_manifest.txt").read_text(encoding="utf-8").splitlines()
if not manifest[-1].startswith("publication "):
    raise SystemExit("oracle manifest has no closing digest")
PY

# Each judged probe is run once here and prints its witness.
python3 -B - <<'SELFCHECK'
import ast
import csv
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

PROJECT = Path("/app/project")
sys.path.insert(0, str(PROJECT / "src"))
from slwopt import cells, normalise, objective, search  # noqa: E402

DATA = Path("/app/data")
OUT = Path("/app/out")
SCRATCH = Path("/tmp/slipway_selfcheck")
DOCS = sorted(p.name for p in OUT.iterdir() if p.name[:2].isdigit())


def fail(check, why):
    raise SystemExit("self-check " + check + " failed: " + why)


def report(check, witness):
    print("check " + check + " ok")
    print("  " + witness)


def copy_data(tag):
    dest = SCRATCH / ("data_" + tag)
    shutil.copytree(DATA, dest)
    return dest


def run(data, tag):
    out = SCRATCH / ("out_" + tag)
    env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"))
    done = subprocess.run([sys.executable, "-B", "-m", "slwopt", "--data", str(data),
                           "--out", str(out)], env=env, capture_output=True, text=True)
    return done, out


def moved(out):
    return [n for n in DOCS if (out / n).read_bytes() != (OUT / n).read_bytes()]


def table(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_error_handling():
    handlers = 0
    for path in sorted((PROJECT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                handlers += 1
                if not any(isinstance(n, ast.Raise) for n in ast.walk(node)):
                    fail("R2", "a handler in " + str(path) + " swallows its error")
    report("R2", str(handlers) + " exception handlers, every one raises")


def check_crosswalk_copy():
    with open(DATA / "identifier_crosswalk.tsv", newline="", encoding="utf-8") as handle:
        legacy = {}
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["status"] == "active":
                legacy.setdefault(row["canonical_id"], row["legacy_id"])
    data = copy_data("crosswalk")
    path = data / "precedence_edge_journal.psv"
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("|")
    jobs = cells.Round(DATA).jobs
    for at, line in enumerate(lines[1:], start=1):
        row = dict(zip(head, line.split("|")))
        if row["status"] == "active" and row["requiring_job"] in jobs \
                and row["requiring_job"] in legacy:
            break
    else:
        fail("R9", "no active precedence row names a job the crosswalk maps")
    job = row["requiring_job"]
    row["requiring_job"] = legacy[job]
    lines[at] = "|".join(row[h] for h in head)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    done, out = run(data, "crosswalk")
    if done.returncode != 0:
        fail("R9", done.stderr.strip())
    changed = moved(out)
    if "18_final_selection.json" in changed:
        fail("R9", "a legacy identifier moved the final selection")
    report("R9", row["edge_id"] + " requiring " + job + " written as " + legacy[job]
           + ": differ " + (",".join(n[:2] for n in changed) or "none"))


def feasible_sets(model, precinct):
    seen = model.cells
    names = model.in_precinct(precinct)
    norms = {n: seen["norm|" + n]["value"] for n in names}
    closures = {n: seen["closure|" + n]["value"]["closure"] for n in names}
    own = {n: seen["demand|" + n]["value"]["own"] for n in names}
    charges = {n: seen["charge|" + n]["value"] for n in names}
    selectable = [n for n in names if not seen["closure|" + n]["value"]["blocked"]]
    binding = [seen["group|" + g]["value"]["members"] for g in sorted(model.groups)
               if model.groups[g]["precinct"] == precinct
               and seen["group|" + g]["value"]["binding"]]
    rules = [seen["rule|" + r]["value"] for r in sorted(model.rules)
             if model.rules[r]["precinct"] == precinct]
    available = search.available_of(model, precinct)
    charter = [n for n in selectable if norms[n]["standing"] == "charter"]
    weights = {pool: Fraction(top, bottom)
               for pool, (top, bottom) in model.params["pool_weights"].items()}
    found = {}
    passing = []
    for mask in range(1 << len(selectable)):
        chosen = [selectable[i] for i in range(len(selectable)) if mask >> i & 1]
        closed = set(chosen)
        for name in chosen:
            closed.update(closures[name])
        closed = tuple(sorted(closed))
        if any(len(set(m) & set(closed)) > 1 for m in binding):
            continue
        usage = {pool: sum(own[n][pool] for n in closed) for pool in normalise.POOLS}
        if any(usage[pool] > available[pool] for pool in normalise.POOLS):
            continue
        base = sum(charges[n]["scaled_charge_mills"] for n in closed)
        surcharge = objective.surcharge_of(list(closed), rules, usage, norms)
        rebate = objective.rebate_of(list(closed), rules, closures, base + surcharge)
        penalty = sum(charges[n]["deferral_penalty_mills"] for n in charter
                      if n not in closed)
        weighted = sum(weights[pool] * usage[pool] for pool in normalise.POOLS)
        found[closed] = (base + surcharge - rebate + penalty, weighted)
        passing.append(base + surcharge - rebate + penalty)
    return found, passing, len(selectable)


def check_tie_and_count():
    model = cells.Round(DATA)
    model.open_round()
    for precinct in model.precincts:
        found, passing, width = feasible_sets(model, precinct)
        best = min(total for total, _ in found.values())
        level = {closed: weighted for closed, (total, weighted) in found.items()
                 if total == best}
        if len(set(level.values())) < 2:
            continue
        kept = min(level, key=lambda closed: (level[closed], closed))
        body = model.cells["solve|" + precinct]["value"]
        if list(kept) != list(body["closed_set"]):
            fail("R4", "the engine kept another set in " + precinct)
        other = min((closed for closed in level if level[closed] != level[kept]),
                    key=lambda closed: (level[closed], closed))
        report("R4", precinct + " charge " + str(best) + " mills: set {"
               + ", ".join(kept) + "} weighted " + normalise.ratio(level[kept])
               + "; set {" + ", ".join(other) + "} weighted "
               + normalise.ratio(level[other]) + "; the pool weights keep {"
               + ", ".join(kept) + "}")
        if body["total_mills"] != best:
            fail("R10", "the engine's winning charge in " + precinct + " is not " + str(best))
        report("R10", precinct + " " + str(sum(1 for t in passing if t == best))
               + " subsets of its " + str(width)
               + " selectable jobs pass the group and capacity tests at the winning"
               " charge " + str(best) + " mills (" + str(len(passing))
               + " pass at any charge)")
        return
    fail("R4", "no precinct holds two sets of one charge")


def check_drafting_copy():
    params = normalise.parameters(DATA)
    params["header"] = dict(params["header"],
                            register_in_force="berth_job_register_current.csv")
    drafting, _ = normalise.register(DATA, params, normalise.crosswalk(DATA))
    live = cells.Round(DATA).jobs
    reasons = {row["identifier"]: row["reason"]
               for row in table(OUT / "19_rejected_register.csv") if row["scope"] == "job"}
    adds = sorted(set(drafting) - set(live))
    if not adds or any(name not in reasons for name in adds):
        fail("R5", "a drafting add has no reason code in the rejection register")
    report("R5", "; ".join(name + " " + reasons[name] for name in adds))


def check_counters():
    mine = {(r["stage"], r["sequence"]): r for r in table(OUT / "16_work_counters.csv")}
    old = {(r["stage"], r["sequence"]): r
           for r in table(DATA / "withdrawn_counter_publication.csv")}
    fields = ("cells_visited", "cells_recomputed", "subsets_examined")
    differ = [key for key in sorted(mine) if key in old
              and any(mine[key][f] != old[key][f] for f in fields)]
    if not differ:
        fail("R6", "no stage differs from the withdrawn counter publication")
    print("  stage/sequence: mine visited,recomputed,subsets | withdrawn visited,recomputed,subsets")
    for key in sorted(mine):
        if key not in old:
            continue
        mark = " DIFFERS" if key in differ else ""
        print("  " + "/".join(key) + ": "
              + ",".join(mine[key][f] for f in fields) + " | "
              + ",".join(old[key][f] for f in fields) + mark)
    report("R6", str(len(differ)) + " stages differ: "
           + "; ".join("/".join(key) for key in differ))


def check_altered_copy():
    data = copy_data("altered")
    path = data / "pool_capacity_history.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    first = dict(zip(head, lines[1].split("\t")))
    target = (first["precinct"], first["pool"])
    rows = []
    for line in lines[1:]:
        row = dict(zip(head, line.split("\t")))
        if (row["precinct"], row["pool"]) == target:
            row["capacity"] = str(int(row["capacity"]) + 1000)
        rows.append("\t".join(row[h] for h in head))
    path.write_text("\n".join([lines[0]] + rows) + "\n", encoding="utf-8")
    done, out = run(data, "altered")
    if done.returncode != 0:
        fail("R7", done.stderr.strip())
    changed = moved(out)
    if not changed:
        fail("R7", "raising one capacity moved no document")
    report("R7", "/".join(target) + " capacity +1000 moved " + ",".join(n[:2] for n in changed))


def check_reversal_kind():
    data = copy_data("reversal")
    path = data / "amendment_journal.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    lodged = [r for r in records if r["state"] == "lodged"]
    by_id = {r["amendment_id"]: r for r in lodged}
    named = {by_id[r["payload"]["amendment_id"]]["kind"] for r in lodged
             if r["kind"] == "reversal" and r["payload"].get("amendment_id") in by_id}
    skip = named | {"reversal", "restatement", "job_note_revision"}
    target = next(r for r in sorted(lodged, key=lambda r: r["sequence"])
                  if r["kind"] not in skip)
    last = max(lodged, key=lambda r: r["sequence"])
    top = max(r["sequence"] for r in records)
    added = dict(last, amendment_id="AMD-990", kind="reversal",
                 sequence=top + 1,
                 payload={"amendment_id": target["amendment_id"]})
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(added, sort_keys=True) + "\n")
    done, out = run(data, "reversal")
    if done.returncode != 0:
        fail("R8", done.stderr.strip())
    row = next(r for r in table(out / "13_amendment_classification.csv")
               if r["amendment_id"] == "AMD-990")
    if row["applied_kind"] != target["kind"] or row["reason"]:
        fail("R8", "the reversal was not applied as the kind it names")
    report("R8", "AMD-990 reverses " + target["amendment_id"] + " " + target["kind"]
           + ": " + row["classification"] + " seeds " + row["seed_cells"])


def check_reordered_rows():
    data = copy_data("reordered")
    path = data / "exclusive_slot_groups.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0]] + lines[1:][::-1]) + "\n", encoding="utf-8")
    done, out = run(data, "reordered")
    if done.returncode != 0:
        fail("R11", done.stderr.strip())
    changed = [n for n in moved(out) if n != "24_run_manifest.txt"]
    if changed:
        fail("R11", "reordering rows moved " + ",".join(changed))
    report("R11", "exclusive_slot_groups.csv reversed: " + str(len(DOCS) - len(moved(out)))
           + " of " + str(len(DOCS)) + " equal")


def check_empty_journal():
    data = copy_data("empty")
    (data / "amendment_journal.jsonl").write_text("", encoding="utf-8")
    done, out = run(data, "empty")
    if done.returncode != 0:
        fail("R12", done.stderr.strip())
    final = json.loads((out / "18_final_selection.json").read_text(encoding="utf-8"))
    base = json.loads((out / "11_baseline_selection.json").read_text(encoding="utf-8"))
    if final["total_mills"] != base["total_mills"]:
        fail("R12", "an empty journal moved the final selection")
    report("R12", "final " + str(final["total_mills"]) + " beside baseline "
           + str(base["total_mills"]))


shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True)
check_error_handling()
check_crosswalk_copy()
check_tie_and_count()
check_drafting_copy()
check_counters()
check_altered_copy()
check_reversal_kind()
check_reordered_rows()
check_empty_journal()
shutil.rmtree(SCRATCH, ignore_errors=True)
SELFCHECK

echo "[oracle] repaired slwopt and published 25 documents under /app/out"

# Owner-only variant (QC Step 10): leave every file this run wrote readable by its
# owner alone, the mode an agent editor leaves behind, keeping the owner execute bit.
find /app -xdev -type f -user 1000 -perm -u+x -print0 2>/dev/null | xargs -0 -r chmod 700 || true
find /app -xdev -type f -user 1000 ! -perm -u+x -print0 2>/dev/null | xargs -0 -r chmod 600 || true
