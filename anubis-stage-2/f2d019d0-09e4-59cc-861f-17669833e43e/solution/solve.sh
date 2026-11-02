#!/bin/bash
set -euo pipefail

DATA=/app/data
OUT=/app/out
WORK=/tmp/moeplan-documents

mkdir -p "$OUT" "$WORK"

# The register decides which contract revisions are in force, and the worked
# step states what the sample configuration must show. Both are read before
# the planner is written.
cat "$DATA/revision_register.json"
cat "$DATA/worked_step.md"

cp /solution/solve.py "$OUT/moeplan.py"
python3 "$OUT/moeplan.py" build "$DATA" "$OUT"

for artifact in \
  "$OUT/moeplan.py" \
  "$OUT/route_plan.json" \
  "$OUT/capacity_plan.json" \
  "$OUT/mesh_plan.json" \
  "$OUT/dispatch_ledger.json" \
  "$OUT/drop_ledger.json" \
  "$OUT/alltoall_ledger.json" \
  "$OUT/guard_key_index.json" \
  "$OUT/recompile_report.json" \
  "$OUT/graph_break_ledger.json" \
  "$OUT/cudagraph_report.json" \
  "$OUT/host_memory_report.json" \
  "$OUT/steptime_report.json" \
  "$OUT/warmup_profile.json" \
  "$OUT/sealed_policy_resolution.json" \
  "$OUT/aux_loss_trace.json" \
  "$OUT/loss_curve.json" \
  "$OUT/gradient_ledger.json" \
  "$OUT/optimizer_trace.json" \
  "$OUT/convergence_report.json" \
  "$OUT/baseline_parity.json" \
  "$OUT/settlement_report.json" \
  "$OUT/rejection_ledger.json" \
  "$OUT/sensitivity.json" \
  "$OUT/audit_statistics.json" \
  "$OUT/deployed_diagnosis.json" \
  "$OUT/validation_report.json" \
  "$OUT/stage_manifest.json" \
  "$OUT/replay_manifest.json" \
  "$OUT/final_state.json"

do
  if [ ! -s "$artifact" ]; then
    echo "missing or empty artifact: $artifact" >&2
    exit 1
  fi
done

# Assemble self contained documents: a configuration plus every table of the
# corpus keyed by file name, CSV rows as string dictionaries.
python3 - "$DATA" "$WORK" <<'PY'
import csv
import json
import os
import sys

data, work = sys.argv[1], sys.argv[2]


def table(path):
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    if path.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


tables = {}
for name in sorted(os.listdir(data)):
    if name.endswith((".json", ".jsonl", ".csv")):
        tables[name] = table(os.path.join(data, name))

for label, source in (("deployed", "deployed_config.json"), ("sample", "sample_run_config.json")):
    document = {"config": tables[source], "tables": tables}
    with open(os.path.join(work, label + ".json"), "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    print("assembled %s document from %s with %d tables" % (label, source, len(tables)))
PY

# The recompilation storm, shown by executing the planner over the deployed
# configuration rather than by reading the published summary.
python3 "$OUT/moeplan.py" trace "$WORK/deployed.json" > "$WORK/deployed_trace.json"
python3 - "$WORK" "$OUT" <<'PY'
import json
import os
import sys

work, out = sys.argv[1], sys.argv[2]
with open(os.path.join(work, "deployed_trace.json"), "r", encoding="utf-8") as handle:
    traced = json.load(handle)
report = traced["recompile_report"]
bound = report["warmup_bound"]
late = [event for event in report["recompile_events"] if event["step"] > bound]
print("deployed trace: warmup bound %d, first step over budget %s, %d recompilation events after the bound, %d evictions"
      % (bound, report["first_step_over_budget"], len(late), report["evictions"]))
for event in late[:5]:
    print("  step %d rank %d %s guard_key %s evicted %s"
          % (event["step"], event["rank"], event["code_object"], event["guard_key"], event["evicted_key"]))
if not late or len(late) != report["recompiles_after_warmup"]:
    raise SystemExit("the deployed trace must recompile past the warmup bound")
with open(os.path.join(out, "recompile_report.json"), "r", encoding="utf-8") as handle:
    if json.load(handle) != report:
        raise SystemExit("the trace verb disagrees with the built recompile report")
PY

# The worked step: trace and replay the sample configuration and check the
# printed capacities and per step recompile counts against worked_step.md.
python3 "$OUT/moeplan.py" trace "$WORK/sample.json" > "$WORK/sample_trace.json"
python3 "$OUT/moeplan.py" replay "$WORK/sample.json" > "$WORK/sample_replay.json"
python3 - "$WORK" <<'PY'
import json
import math
import os
import sys

work = sys.argv[1]


def load(name):
    with open(os.path.join(work, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


traced, replayed = load("sample_trace.json"), load("sample_replay.json")
plan = traced["capacity_plan"]
bucket, floor = plan["capacity_bucket"], plan["min_capacity"]
demands = {row["step"]: row["demand"] for row in replayed["route_plan"]["steps"]}
for row in plan["steps"]:
    demand = demands[row["step"]]
    print("sample step %d demand %s capacity %s" % (row["step"], demand, row["capacity"]))
    for want, got in zip(demand, row["capacity"]):
        expected = floor if want == 0 else bucket * math.ceil(want / bucket)
        if got != expected or got % bucket:
            raise SystemExit("sample capacity %s disagrees with worked_step.md for demand %s" % (got, want))
counts = [(row["step"], row["count"]) for row in traced["recompile_report"]["recompiles_by_step"]]
print("sample recompiles by step %s, evictions %d, dropped assignments %d"
      % (counts, traced["recompile_report"]["evictions"], replayed["drop_ledger"]["dropped_tokens"]))
if any(count for step, count in counts if step > 1):
    raise SystemExit("worked_step.md says nothing recompiles after the first step")
if traced["recompile_report"]["evictions"] or replayed["drop_ledger"]["dropped_tokens"]:
    raise SystemExit("worked_step.md says nothing is evicted and nothing is dropped")
print("sample configuration agrees with every property worked_step.md states")
PY

# The sealed decisions, recovered by enumerating every candidate order.
python3 "$OUT/moeplan.py" resolve "$WORK/deployed.json" > "$WORK/resolution.json"
python3 - "$WORK" "$OUT" <<'PY'
import json
import os
import sys

work, out = sys.argv[1], sys.argv[2]
with open(os.path.join(work, "resolution.json"), "r", encoding="utf-8") as handle:
    found = json.load(handle)
print("enumerated %d tie break orders, %d reproduce every sealed digest, key %s"
      % (found["tie_break_candidates_enumerated"], found["tie_break_matches"], found["tie_break_key"]))
print("enumerated %d precedence orders, %d reproduce every sealed digest, order %s"
      % (found["precedence_candidates_enumerated"], found["precedence_matches"], found["precedence_order"]))
with open(os.path.join(out, "sealed_policy_resolution.json"), "r", encoding="utf-8") as handle:
    if json.load(handle) != found:
        raise SystemExit("the resolve verb disagrees with the built resolution record")
PY

python3 - "$OUT" <<'PY'
import hashlib
import json
import os
import sys

OUT = sys.argv[1]


def load(name):
    with open(os.path.join(OUT, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def raw(name):
    with open(os.path.join(OUT, name), "rb") as handle:
        return handle.read()


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


stage = load("stage_manifest.json")
replay = load("replay_manifest.json")
final = load("final_state.json")

for name, want in sorted(stage["artifact_sha256"].items()):
    if digest(raw(name)) != want:
        raise SystemExit("stage manifest digest mismatch for " + name)
for name, want in sorted(replay["artifact_sha256"].items()):
    if digest(raw(name)) != want:
        raise SystemExit("replay manifest digest mismatch for " + name)

if replay["stage_manifest_sha256"] != digest(raw("stage_manifest.json")):
    raise SystemExit("replay manifest does not fold the stage manifest bytes")

folded = {
    "replay": digest(raw("replay_manifest.json")),
    "salt": digest(canonical(final["settled_configuration"])),
    "stage": digest(raw("stage_manifest.json")),
}
if final["digest_of_digests"] != digest(canonical(folded)):
    raise SystemExit("final state does not fold the two manifest digests")
if final["settlement_salt"] != folded["salt"]:
    raise SystemExit("final state salt disagrees with the settled configuration")

diagnosis = load("deployed_diagnosis.json")
if diagnosis["admissible"] is not False:
    raise SystemExit("the deployed configuration must be inadmissible")
if diagnosis["published_agrees_with_replay"]:
    raise SystemExit("the published figures must disagree with a correct replay")
if not diagnosis["departing_settings"]:
    raise SystemExit("the deployed configuration must depart from the contracts in force")

recompiles = load("recompile_report.json")
if recompiles["recompiles_after_warmup"] <= 0:
    raise SystemExit("the deployed replay must recompile past the warmup bound")
if recompiles["evictions"] <= 0:
    raise SystemExit("the deployed replay must evict cached entries")

memory = load("host_memory_report.json")
if memory["memory_gate_met"]:
    raise SystemExit("the deployed replay must breach the host ceiling")

settlement = load("settlement_report.json")
if settlement["settled_configuration"]["compile_mode"] == "eager":
    raise SystemExit("abandoning compilation is not a settlement")
for gate, verdict in sorted(settlement["gates_met"].items()):
    if not verdict:
        raise SystemExit("the settled configuration misses the gate " + gate)

convergence = load("convergence_report.json")
if convergence["verdict"] != "met":
    raise SystemExit("the settled run must converge")

resolution = load("sealed_policy_resolution.json")
if resolution["tie_break_matches"] < 1 or resolution["precedence_matches"] < 1:
    raise SystemExit("a sealed policy was not recovered")


def shown(value):
    return "none" if value == [] else ", ".join(value) if isinstance(value, list) else str(value)


changes = "; ".join(
    "%s from %s to %s" % (row["setting"], shown(row["from"]), shown(row["to"]))
    for row in settlement["changed_settings"]
)
memory_verdict = "met" if settlement["gates_met"]["memory"] else "not met"
sys.stdout.write(
    "Hashed %d records. The deployed run first exceeds its recompilation budget at step %s "
    "and records %s recompilation events after the warmup bound. "
    "The settlement changed %s. "
    "The settled configuration measures a throughput ratio of %s and its host memory gate is %s. "
    "The closing loss is %s and the convergence verdict is %s. "
    "%s admissible candidates survived the sweep and %s were removed before any rejection cause was weighed.\n"
    % (
        len(stage["artifact_sha256"]) + len(replay["artifact_sha256"]),
        recompiles["first_step_over_budget"],
        recompiles["recompiles_after_warmup"],
        changes,
        settlement["settled_gate_figures"]["speedup"],
        memory_verdict,
        convergence["closing_loss"],
        convergence["verdict"],
        settlement["admissible_count"],
        settlement["prefiltered_count"],
    )
)
PY
