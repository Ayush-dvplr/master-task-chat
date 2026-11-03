FOLD DECISIONS (fold review of tmp/W1-029/TRIAGE.md, items T1 to T46). Applied to RULES_IN_FORCE.md and the old files only after all batches and after PROCEED. Card size is checked when they are applied.

BATCH 1, LEVERS AND DESIGN (ENTRY 51, 52)
T1 DROP. T2 DROP (keep "at least one hidden rerun per output family" as how to text). T6 DROP. T8 DROP.
T3 CHANGE: "Misread rule levers are allowed under CR7; the other paused kinds stay paused until the lever audit."
T4 CHANGE: carrier variation removed from the rejected sources (PATTERNS D2).
T5 CHANGE: "Bounded induction counts under PATTERNS D1 only when the finite family is stated or shown in the shipped files."
T7 KEEP: "A shipped instance may hide a case, never the rule: every hidden branch has its sentence in the docs."
T9 KEEP: add "no rule count" to RIF LEVERS.
T10 KEEP: "Every lever names in DESIGN.md the oracle branch, the careful program branch and a saved input where they differ."
T11 CASE BY CASE (Q127, ENTRY 52): holes are not a standing rule; each case is decided with Ayush, Claude says plainly whether it can help and proposes the valid near form.

BATCH 2, GRADING AND TESTS (ENTRY 53)
T12 KEEP: "Every task states the exact bar sentence; tests compare whole documents per hidden run."
T13 KEEP: "Never grade a key, field or value form the shipped contract does not name." (default; holes case by case, T11)
T14 KEEP: "The instruction states the exact command the tests use to run the program."
T15 KEEP: "Nothing in environment/ shows the answer for a graded document, and the oracle never contradicts the contract."
T16 CHANGE: "Every criterion traces to an instruction sentence that asks for the output; that sentence never names the trap, the probe or the method."
T17 CHANGE: "A worked example uses invented toy values, never a graded figure; when one is graded, the instruction asks for it."
T18 KEEP: "Rules of engagement are always stated in a file the agent reads."
T19 KEEP: "Every instruction keeps the finish time sentence; no effort cap."
T20 CHANGE: "DESIGN READY needs a predicted final under the gate minus design_margin (settings.json, 5 points: under 35 today)."
T21 DROP.

BATCHES 3 AND 6, QC FIXES, REPOS AND SAFETY (ENTRY 54)
T22 CHANGE: "No fix softens a lever just to pass QC unless Ayush says so for that finding. A real defect is always fixed: the shipped docs decide the value in one sentence and the hardness is rebuilt in a valid form (Q126)."
T23 CHANGE: issue.py refusals after a QC pass become logged warnings; RIF:7 "stop at the first pass" stays.
T39 KEEP: "Never run generate_bundle.py --force, playground.py --model, or anything that uploads files or keys."
T40 CHANGE: "Mine passing teammate tasks only from anubis-stage-2 (the current source Ayush named)."

BATCH 4, RUNS AND PUSH (ENTRY 55)
T24 CHANGE: "Order: design, build, full QC until it passes, 1 paid run on the frozen bytes. No hardening between the QC pass and the paid run. After a gate miss: harden from what the run got wrong with the fix map, QC again, 1 new run."
T25 CHANGE (Q128, ENTRY 56): "By day the master stops at DESIGN READY and waits for Ayush's go. In auto mode (AUTO_POLICY.md) it checks DESIGN READY against the rules in force and the kit and sends the go itself or a correction, writes it to prompts/issued/<slug>/<ts>_go.md and lists it in REPORT.md." R7 gets the same auto mode exception (auto.py starts sessions itself).
T26 KEEP: "Before diagnosing a run, diff its staged copy against the bundle; a score from another tree is no baseline."
T27 KEEP: "A regrade is diagnostic only, except a judge only edit on a valid run with Ayush's written OK, repackaged by repackage_one.py."
T28 KEEP: "Only valid runs (no grader error) count as baselines."
T29 KEEP: "A pushed bundle is packaged from exactly the frozen bytes of the gate run, with that run's scores."
T30 KEEP: "Before push, QC Step 10 (oracle, nop, stub, owner only) is complete on the frozen bytes."
T31 KEEP: "Every freeze records the tree sha; a gate run counts only on that sha."
T32 KEEP: "Only real runs measure hardness; a reviewer rating never gates."
T33 CHANGE: runs per task while building (1) and on final approval (8) move into settings.json.
T34 KEEP: "No task is parked except on Ayush's word."

AUTO_POLICY BATCH (auto/AUTO_POLICY.md against RULES_IN_FORCE.md, checked by Claude 3 Nov; A1 to A13 as suggested, ENTRY 57)
A1 line 3 "README still applies: same read order, caps": CHANGE to the state card read order and RULES_IN_FORCE.md; caps are warnings.
A2 line 22 DESIGN READY go: DECIDED by T25 (Q128): check against the rules in force and current LEVER_RULES.
A3 line 23 blind read after DESIGN BLIND READY: depends on T45 (blinds before QC or none on route 1).
A4 line 24 no third redesign, stop and write under Needs Ayush: KEEP (asks Ayush, does not park).
A5 line 25 auto Step 10 = 2 oracle and 1 nop; the rest owed before push: KEEP, oracle count follows T46, push condition T30.
A6 line 26 QC PASS or minors only, then freeze: CHANGE to RIF:7 (1 complete QC pass with no fail, ENTRY 57; any CL fail blocks; minors as PL notes; false positive review after every QC result).
A7 line 27 QC FAIL, one fix session with G1 to G7: CHANGE to "one fix session with the fix map (T22, Q125, Q126), then QC recheck".
A8 line 28 gate 85, 85, 40 written out: CHANGE to "gate from settings.json".
A9 line 29 gate miss, fix prompt in QC-safe form: CHANGE to T24 order with the fix map.
A10 line 30 round limit override by the master: DROP (caps are warnings, Q120).
A11 Limits (5 workers, 2 harness, 2 new builds per run, last spawn 20 min before Until): CHANGE, values into settings.json (Q122, R21).
A12 Budget (6 paid runs a day; start a paid run only with at most 2 busy workers, at most 3 while it runs): CHANGE, values into settings.json (R24).
A13 Workers model "claude-opus-5-5, variant high": CHANGE, model per step from settings.json (R32).
Kept as they are (match the rules in force): hard rules 1 to 6, interruptions table, restart and scheduled start, REPORT.md layout. No line stops a working session (ENTRY 47).
