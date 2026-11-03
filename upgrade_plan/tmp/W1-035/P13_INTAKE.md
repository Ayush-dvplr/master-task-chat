P13 OUTSIDE BUNDLE INTAKE (W1-035, draft, 3 Nov 2026). Nothing applied. Built from ANSWERS.md ENTRY 64, 65, 66, 68, 70, 71; drafts/P1/RULES_IN_FORCE.md, BUILD_RULES.md, settings.json; tmp/W1-030/FIX_MAP.md and REGRESSION_CHECK.md; tmp/W1-033/ADAPTER.md; the live tools in master_chat_tasks/tools. Guesses are marked UNVERIFIED.

Name clash: "P13" here is the upgrade plan item. The prompt template family P13 in prompts/templates (P13_blind_solve_v1.md, v2) is the blind solve and has nothing to do with this intake. Board rows whose step starts with "P13" are blinds.

SCOPE (ENTRY 65, Q132)
1. own_outside: a bundle Ayush built himself outside the system.
2. assigned: a task the PL or QL assigned to Ayush to fix (the "QC assigned/" folder on his Mac).
3. teammate_agreed: a teammate's task fixed with the teammate's agreement, under the PL's oversight.
Each may arrive with or without a trajectory. A trajectory is a harness run folder: trajectories/<model>/pass_summary.json plus Run N/verifier/reward-details.json (the anubis-stage-2 layout, STAGE2_STUDY_PLAN.md:8, and the layout under master_chat_work/*/trajectory/claude-opus-5/).

FIXED RULES FOR EVERY OUTSIDE BUNDLE
1. Provenance is recorded once, at intake, and never rewritten: origin, original_author as Ayush gives it, source path, trajectory path, received tree sha.
2. The system never edits author fields (task.toml author lines, any author name or email anywhere). Intake stores a fingerprint of the author lines; the regression check and the push check compare it and stop on any change.
3. counts_for_ayush is false by default. Only Ayush's own words turn it on for one task; the words are stored verbatim (the b7c42a8f rule, today held only as free text in pipeline.next).
4. The source folder is read only. "QC assigned/" and "my tasks/" are never edited without Ayush's "proceed" (R35). All work happens on a copy in master_chat_work/bundles/<slug>/, with the original kept in master_chat_work/<date>_outside_<slug>/original_backup/, as was done for b7c42a8f (decisions.jsonl:566).
5. Ayush runs every push (R34). Who is named as author at push is settled between Ayush, the teammate and the PL; the system takes no part in it.
6. A teammate_agreed intake is refused without an agreement line: Ayush's own words that the teammate agreed and the PL oversees it, stored verbatim.

THE FLOW
Step 1. Register (script, no AI tokens).
  intake.py --outside SRC --origin own_outside|assigned|teammate_agreed --author "<as given>" [--traj DIR] [--slug SLUG] [--agreement "<Ayush's words>"] [--assigned-by PL|QL] [--band N] [--apply]
  a. Copies SRC to master_chat_work/bundles/<slug>/ without trajectories/, and SRC whole to original_backup/.
  b. Computes received_tree_sha of the copy (intake.py tree_sha) and author_fp (sha256 of the task.toml lines whose key starts with author; the values themselves are not copied into any record).
  c. Writes the registry provenance block (new, top level in the task object, beside pipeline):
     provenance: { origin, original_author, source_path, trajectory_path, received_ist, received_tree_sha, author_fp, counts_for_ayush: false, counts_words: "", agreement: "<verbatim or empty>", assigned_by: "", score_band: null }
  d. Sets pipeline kind=intake, stage=qc, next="first checks".
  e. Without --apply it prints the would be block and writes nothing, as intake.py does today.
Step 2. First checks (scripts, no AI tokens except the solvability judgement).
  a. tools/precheck.sh on the copy; the findings list goes to FIRST_CHECKS.md.
  b. Oracle and nop through the dockslot QC fast lane (kinds oracle and nop, fast true, settings.docker.kinds): oracle 1.000 on settings.oracle_runs.day runs (auto mode: oracle_runs.auto), nop exactly 0.000. A failing oracle or a nop above 0 is a real defect and is fixed before anything else.
  c. Solvability of every graded value: the REGRESSION_CHECK step 7 procedure applied to the whole bundle, not only to changed values. A script lists every graded value (expected constants and literals in tests/test_output.py, generator parameters and bounds, judge criteria naming a value or shape); a session writes DECIDING_MAP.md with the shipped file:line that decides each value, judged against the determinate table (05:22 to 32). A value no shipped line decides is a real defect (Q126 fix from FIX_MAP).
  d. Lever reading: an outside bundle has no DESIGN.md. The same session writes LEVERS_FOUND.md: what makes the task hard today, the checks that pay for it and their share of positive test weight, and one wrong reading program per lever (WORK/wrong/), so the regression check can measure lever survival (REGRESSION_CHECK step 2, lever_keep_pct 90). Without this the fix map's "keep the hardening" cannot be checked.
Step 3a. With a trajectory.
  a. trajectory_readout.py "<trajectory>/<model>/Run N" --out OUT/TRIP_runN.md for every run folder; loss.py on the same folder for points lost per check and per hidden input.
  b. Gate check from settings.gate (today tests 85, rubric 85, final 40) on pass_summary.json, never the constants now in intake.py:33 and :147. The model in pass_summary.json must equal settings.models.paid_run (claude-opus-5); another model is shown but is not gate evidence.
  c. The scores row is written with event outside_baseline, valid false for the gate, artefact_reason "outside bytes" unless step 3a d proves the bytes.
  d. Bytes proof: when the run folder carries a job config whose staged task tree equals received_tree_sha, the row is marked bytes_match true. It still counts as a gate run only if QC then passes with no byte change and Ayush says so (open point 3).
  e. Result: the master knows where the task stands against the gate before spending a QC round, and which checks the paid model lost (what to keep hard).
Step 3b. Without a trajectory: QC first. Score prediction waits until QC passes; no paid run before a QC pass (ORDER, T24).
Step 4. QC and fixes, the same as an own task from QC onward.
  a. Full QC (P11 full QC template), false positive review after every result (R16).
  b. Fix with the fix map (FIX_MAP.md rows; BUILD_RULES QC FIXES and QC FIX STEPS), one direction line per finding.
  c. Regression check (REGRESSION_CHECK.md steps 1 to 9) after every fix round, before the QC recheck. Two extra lines for outside bundles: step 1 also compares author_fp (any change stops the round); step 2 uses LEVERS_FOUND.md in place of DESIGN.md.
  d. QC again until the first pass (R16, R18, Q129).
  e. QL QC. On a QL report the system prepares the triage table (prompts/templates/P16_ql_report_triage_v1.md): per finding, the diff since the passed copy, the kit line read in full, and a suggestion real, false positive or vague. Ayush decides; only real ones are fixed; QC again (Q133, ENTRY 66).
  f. Freeze: status.py set SLUG tree_sha=<tree>; 1 paid run on the frozen bytes (runs_per_task.build = 1), gate from settings; intake.py --job SLUG --event gate_run.
  g. After a miss: harden from what the run got wrong with the fix map, QC again, 1 new run (T25). Never the same bytes twice.
  h. Score band (teammate_agreed, when Ayush sets one, as for b7c42a8f "fixes keep final within +-5", decisions.jsonl:565): every fix direction states the predicted final, and a fix that leaves the band is reported to Ayush before QC.
Step 5. Push: Step 10 on the frozen bytes; the push check compares author_fp with the received one and prints counts_for_ayush; Ayush runs the push.

WHAT IS DIFFERENT FROM AN OWN BUILD
1. No design step, no design card, no DESIGN READY stop, no family choice (NEW DESIGNS, P9, Q137, do not apply). The master starts at first checks.
2. The design is kept. A teammate_agreed task keeps its design and its levers unless the owner agrees to a change; the agreement is stored verbatim beside the provenance. An assigned task keeps its design unless the assigner's report asks for a change. An own_outside task may be redesigned on Ayush's word.
3. BUILD_RULES design rules (primary lever at least 40 percent, NO CORE, family order) are read as notes on an outside task, never as refusals; a gap is reported to Ayush, who decides case by case.
4. LEVERS_FOUND.md stands in for DESIGN.md as the lever list for the regression check.
5. Records: provenance block, counts_for_ayush false, author_fp checked at every fix round and at push.
6. Progress counts (state_card.py pushed today and this week, GOALS targets) skip a task whose counts_for_ayush is false.
7. The trajectory, when given, is a diagnostic baseline, not a gate run (open point 3).

TOOL CHANGES (detail in TOOL_CHANGES.md)
| tool | change |
|---|---|
| intake.py | new --outside mode (copy, backup, tree sha, author_fp, provenance block); --traj reads trajectories/<model>/pass_summary.json; gate and paid model from settings.json, not FINAL_GATE and literals |
| status.py | new "provenance SLUG k=v" subcommand: write once for origin, original_author, source_path, received_tree_sha, author_fp; counts_for_ayush only with --ayush "<words>"; table column "origin" |
| trajectory_readout.py | no change to the read out; accepts the outside run folder as is (it already reads Run N/verifier/reward-details.json) |
| loss.py | accept a trajectory folder path (it already takes SLUG_OR_JOB_DIR); print the share of positive test points lost per lever when given LEVERS_FOUND.md or DESIGN.md (feeds lever_loss_pct) |
| issue.py | warn when kind is build or rebuild on a task with provenance origin teammate_agreed and no owner agreement for a design change; new kinds none (first checks run as kind qc or adhoc) |
| registry_check.py | check the provenance block: required keys, origin in the three values, counts_for_ayush bool, original_author unchanged from the first recorded value (compare with decisions.jsonl intake row) |
| state_card.py (draft) | pushed_since counts only tasks without provenance or with counts_for_ayush true |
| regression check script (REGRESSION_CHECK step 1) | compare author_fp before and after; stop on change |
| precheck.sh | no change |
| board.py | no change for P13 |

MIGRATION OF TODAY'S RECORDS (Ayush decides, open point 1)
Six registry tasks carry pipeline.kind "intake" today. One is the teammate task b7c42a8f (not Ayush's, never counted; pipeline.next free text). Two of the six were pushed by Ayush himself. pipeline.kind "intake" therefore does not mean "not Ayush's", and runner_report.py shows these six as intake_unclassified until each gets a provenance block.

OPEN POINTS FOR AYUSH
1. Classify the six "intake" tasks: origin and counts_for_ayush for each (b7c42a8f: teammate_agreed, false, as recorded).
2. original_author: store it as given, or store only a reference (for example "teammate, see agreement") so no name sits in the registry? The task wording says "kept as given"; the study files refer to tasks by id only.
3. Outside trajectory as a gate run: count it when its staged tree equals the frozen tree and QC passed with no byte change (saves one paid run), or always diagnostic only (UNVERIFIED that outside run folders carry a job config).
4. Teammate source path: RULES_IN_FORCE says teammate tasks only from anubis-stage-2 (T39, T40). Does a teammate_agreed bundle handed over directly fall under that rule, or is the agreement enough?
5. Score band for teammate_agreed tasks: a default (plus or minus 5, as for b7c42a8f) or only when Ayush names one.
6. Does an assigned task count for Ayush by default (it was given to him to fix), or false like the others?
