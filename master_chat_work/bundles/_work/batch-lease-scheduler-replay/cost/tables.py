"""Write COST_TABLE.md and RULE_COVERAGE.md from the cost runs."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
rows = json.loads((HERE / "final_rows.json").read_text())
rows.update(json.loads((HERE / "extra_rows.json").read_text()))
C = "replay_contract.md"

LEVERS = [
    ("LV-BS-1", "LAZY+FW2: internal events handled at the next external instant, external first"),
    ("LV-BS-2", "PREFAIL+STALE: preemption ends the attempt, stale token applied"),
    ("LV-BS-3", "ANYTERM+REDUP: release on any terminal parent with no cascade, redelivery applied twice"),
]
ALONE = [
    ("LAZY", "LV-BS-1", "internal events processed only at external instants"),
    ("FW2", "LV-BS-1", "external events before completion/expiry at a shared instant"),
    ("PEREVENT", "LV-BS-1", "dispatch after every external event"),
    ("EXPFIRST", "LV-BS-1", "expiry before completion at the same instant"),
    ("FW1", "LV-BS-1", "completion guarded by attempt token only (stale completion after preempt+resume)"),
    ("PREFAIL", "LV-BS-2", "preemption counted as an attempt end"),
    ("STALE", "LV-BS-2", "stale attempt token applied"),
    ("FW4", "LV-BS-2", "heartbeat/fail on a preempted job with the current token applied"),
    ("FW3", "LV-BS-2", "lost units = ticks of the current run only"),
    ("FW3b", "LV-BS-2", "cancel of a running job uses remaining at run start"),
    ("EVICTFAIL", "LV-BS-2", "eviction counted as an attempt end"),
    ("ANYTERM", "LV-BS-3", "dependents released on any terminal parent, no cascade"),
    ("REDUP", "LV-BS-3", "identical redelivery applied a second time"),
    ("FW5", "LV-BS-3", "cascade skips unsubmitted dependents"),
    ("PRECSWAP", "slip", "audit precedence not_running before stale_attempt"),
    ("FW2R", "slip", "checkpoint remaining read from run start (no interpolation)"),
    ("SUBORDER", "slip", "dispatch tie by submission order"),
    ("FIRSTWRITE", "all", "PREMORTEM first-write program (FW3b+FW4+FW5)"),
    ("SHIPPED", "all", "shipped engine defects together"),
]

RULES = [
    ("lease ticks govern deadline s+ticks", C + ":11", "HBFROMDL"),
    ("retry delay: ready at t+delay", C + ":11", "DELAYOFF"),
    ("pool preempt flag", C + ":12", "PREEMPTALL"),
    ("ids compared as numbers (dispatch tie)", C + ":9", "IDTEXT"),
    ("ids compared as numbers (worker choice)", C + ":9", "WORKERTEXT"),
    ("blank lines in events.jsonl carry no meaning", C + ":9", "BLANKCRASH"),
    ("redelivered copy = identical id and content", C + ":25", "REDUP"),
    ("attempt ends -> dead at retry_limit+1", C + ":38", "LIMITOFF"),
    ("lost units = work minus remaining at attempt end", C + ":38", "FW3"),
    ("preemption keeps attempt and remaining", C + ":40", "PREFAIL"),
    ("eviction keeps attempt and remaining", C + ":40", "EVICTFAIL"),
    ("cascade to every non-terminal dependent", C + ":42", "FW5"),
    ("cascade (and no release) on dead/cancelled parent", C + ":42", "ANYTERM"),
    ("every whole-number time is an instant", C + ":46", "LAZY"),
    ("phase 1 completion before external events", C + ":48", "FW2"),
    ("phase 1 completion before phase 2 expiry", C + ":49", "EXPFIRST"),
    ("completion only for the current run", C + ":48", "FW1"),
    ("phase 3 events in ascending id", C + ":50", "EVDESC"),
    ("phase 4 dispatch once per instant", C + ":51", "PEREVENT"),
    ("checkpoint state after phase 4", C + ":53", "SNAPBEFORE"),
    ("worker_down evicts and frees the worker", C + ":60", "DOWNKEEP"),
    ("terminal job events audited finished", C + ":61", "FINLAST"),
    ("release at submit recorded", C + ":62", "NORELREC"),
    ("boost applies to any non-terminal job", C + ":63", "BOOSTSUB"),
    ("cancel lost = work minus current remaining", C + ":64", "FW3b"),
    ("stale_attempt row before not_running", C + ":65", "PRECSWAP"),
    ("stale token audited, no effect", C + ":65", "STALE"),
    ("not_running audit for preempted job", C + ":66", "FW4"),
    ("heartbeat renews to t+ticks", C + ":67", "HBNOP"),
    ("dispatch order priority then job id", C + ":72", "SUBORDER"),
    ("lowest idle worker id", C + ":74", "WORKERHI"),
    ("victim tie: latest start", C + ":75", "VICEARLY"),
    ("victim tie: highest job id", C + ":75", "VICLOWID"),
    ("checkpoint remaining interpolated", C + ":83", "FW2R"),
    ("executed counted through last checkpoint", C + ":87", "EXECLAST"),
    ("edges ordered by parent then child", C + ":90", "EDGEORDER"),
    ("final.other counts non-terminal incl unsubmitted", C + ":94", "OTHERSUB"),
    ("dispatch_sha256 line format", C + ":94", "SHAFMT"),
    ("output deterministic across hash seeds (parsed JSON equal)", C + ":80", "HASHORDER"),
    ("refusal order: MISSING_INPUT file order", C + ":100", "MISSREV"),
    ("MISSING_INPUT names the file", C + ":100", "MISSDETAIL"),
    ("INVALID_POLICY before UNKNOWN_ENTITY", C + ":98", "POLAFTER"),
    ("UNKNOWN_ENTITY for undefined worker", C + ":102", "UNKWORKER"),
    ("EVENT_ID_CONFLICT detected", C + ":103", "NOCONFLICT"),
    ("EVENT_ID_CONFLICT before DEPENDENCY_CYCLE", C + ":98", "CYCLEFIRST"),
    ("DEPENDENCY_CYCLE detected", C + ":104", "NOCYCLE"),
    ("refusal line on standard output", C + ":106", "STDERR"),
    ("refusal status 2", C + ":106", "EXIT1"),
    ("refusal writes no document", C + ":106", "WRITEFIRST"),
    ("python -m leasebook runs main", C + ":80", "NOMAIN"),
    ("__version__ equals pyproject version", C + ":110", "VERSION"),
    ("shipped test files unchanged", C + ":110", "TESTEDIT"),
    ("selftest.json counts from the archive run", C + ":112", "SELFTEST"),
    ("build_report files sorted", C + ":114", "UNSORTED"),
    ("build_report archive_sha256", C + ":114", "SHA"),
]


def cost_table():
    out = ["# COST_TABLE (G10)", "",
           "Real tests (tests/test_output.py, positive 139) on a patched copy of the fixed package; "
           "overall = 0.5 x tests% + 0.5 x 90 (judge assumed 90). One-fact-wrong score = tests% kept "
           "when only that reading is wrong. Every lever alone >= 25% and every all-but-one row < 70.", "",
           "| row | lever | wrong reading | points lost | lost % | one-fact-wrong tests % | predicted overall |",
           "|---|---|---|---|---|---|---|"]
    for name, desc in LEVERS:
        r = rows[name]
        out.append("| %s alone (all but this lever right) | %s | %s | %d | %.1f | %.1f | %.1f |" % (
            name, name, desc, r["lost_points"], r["lost_pct"], 100 - r["lost_pct"], r["overall"]))
    for name, lever, desc in ALONE:
        r = rows[name]
        out.append("| %s | %s | %s | %d | %.1f | %.1f | %.1f |" % (
            name, lever, desc, r["lost_points"], r["lost_pct"], 100 - r["lost_pct"], r["overall"]))
    r = rows["clean"]
    out.append("| clean | none | reference package | %d | %.1f | %.1f | %.1f |" % (
        r["lost_points"], r["lost_pct"], 100 - r["lost_pct"], r["overall"]))
    out += ["", "Slip rows FW2R, FW3 and PRECSWAP stay above 70 overall alone; they are slips inside a lever, "
            "not levers. No row triggers a negative.", ""]
    return "\n".join(out)


def coverage():
    out = ["# RULE_COVERAGE (G11)", "", "| rule | file:line | mutant | tests failed |", "|---|---|---|---|"]
    for rule, where, mutant in RULES:
        out.append("| %s | %s | %s | %d |" % (rule, where, mutant, len(rows[mutant]["lost"])))
    return "\n".join(out) + "\n"


(WORK / "COST_TABLE.md").write_text(cost_table())
(WORK / "RULE_COVERAGE.md").write_text(coverage())
zero = [m for _, _, m in RULES if not rows[m]["lost"]]
print("rules", len(RULES), "zero", zero)
