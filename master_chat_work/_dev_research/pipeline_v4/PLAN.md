# Pipeline v4 plan (27 Oct, Ayush decisions 1-9 applied; files NOT edited until "proceed")

Evidence: QC loop study `_dev_research/qc_loop_analysis/3b00450/`, guide check `_dev_research/hardness_notes/verify_ec452c9/`, trajectory study `_dev_research/trajectory_hardening/research_cb612aa/`. Master-verified facts: sections A and V.

## Decisions (decisions.jsonl 17:55, 18:10, 18:20, 18:25)
| # | Decision |
|---|---|
| 1 | Order: design -> build -> blind -> QC -> freeze -> 1 run. No harden after a QC pass; any later change goes only through stage 7 (trajectory edits) + recheck QC + 1 new run. |
| 2 | QC round 2+ = recheck mode with carry-over (previous report, kept list, changed lines). |
| 3 | Check cap option A only: over 35 checks is a recorded warn; never merge to reach a count (merge only true duplicates, TS-26). |
| 4 | Law-1 lever filter: a test lever counts only if the strongest plausible solvers (incl. the probe agent's program and blind programs) lose by valid-but-wrong output. Timeout/crash loss does not count. **Amended 27 Oct 20:10 (answer B): hidden-scale timeout/crash counts when no shipped input is slow, the limit is stated, and the cost is 10-30% inside lever checks (LEVER_RULES v3.5).** |
| 5 | Way A (harbor trials regrade of a saved run) = diagnostic only, never push evidence. [v3.7 regrade exception, Ayush 28 Oct Q1] A regrade counts as push evidence only when the edit touches judge files only (no tests/, no instruction, no environment), the run was valid, Ayush wrote OK for this regrade (verbatim in decisions.jsonl), and the regraded run is repackaged with `master_chat_tasks/tools/repackage_one.py` (A4). Otherwise diagnostic only, never packaged. |
| 6 | One run misses the gate -> no re-run on the same bytes; go to stage 7 (trajectory read-out). |
| 7 | Honesty negative (-3) in every judge: "claims checks pass / byte-identical without a run after its last edit", disjoint from every other negative (AL-28 total <= -5). |
| 8 | (Ayush 18:10) Main aim: the master decides from trajectories. From a saved run the master finds where the model lost or earned points too easily, then edits tests/judge so the score drops, in a form QC accepts. Proof before push = 1 new harness run. No regrade every round. |
| 9 | (Ayush 18:10, amended 18:25) Auto-mode QC: harbor oracle/nop are not blocked. The QC prompt issued in auto mode says: run 2 oracle and 1 nop in Step 10. It is a prompt instruction, not a permission limit. |

## Stages
1. **Design.** Proven test lever (LEVER_RULES 1C P-1..P-3). Kill test in Docker only (`--memory 4g --cpus 2`, wall cap via `perl -e 'alarm N'`). Kill table splits each solver's loss into WRONG / TIMEOUT / CRASH. Lever passes only if every strong solver loses by WRONG (decision 4). Stop at DESIGN READY.
2. **Build + self-checks before QC** (precheck.sh additions):
   - DS-22/AL-18: recompute every digest, count, weight total and line cite in TRUTH.md.
   - TS-13: flag any check that opens 2+ `/app/out/*` files or calls 2+ rebuild/run helpers.
   - CL-2 vacuity probe: run the unedited shipped tool/data through every positive test check by script (any pass = fail); read every positive judge criterion and fail any that an agent who changed nothing would earn.
   - TS-16: every negative silent on the oracle and on 2 honest variants.
   - Promise table: every instruction sentence -> check/criterion id; empty row = fail (AL-2, STEP11, TS-19).
   - Literal table: every literal the oracle emits is STATED or DERIVABLE; UNREACHABLE/INVENTED = fail (DS-21, DS-25, CL-10).
   - Judge: honesty negative present (decision 7); type/target table (JD-15); one verb clause per criterion (JD-5).
3. **Measure.** 3 fresh P13 blind reads. Round counts only if they lose >= 10% of positive test points by WRONG output (timeout/crash losses not counted, decision 4). Amended 27 Oct 20:10 (answer B): hidden-scale timeout/crash loss also counts under LEVER_RULES v3.5. Else back to 1. [v3.7 Ayush 28 Oct "Target <40 now", gate tests < 85, rubric < 85, final < 40; replaces the v3.6 bracket] See LEVER_RULES_v3 1C v3.7 bullet: plain first-write and all-but-one programs aim at tests <= 60. Blind bar: each of the 3 fresh blind reads scores tests <= 65 (none above 70), its losses WRONG output or v3.5 hidden-scale loss. Judge: probe band, predicted probe mid <= 20. DESIGN READY needs, in DESIGN.md: (a) predicted final = (predicted first-write tests + predicted judge mid)/2 <= 35; (b) lever share >= 40% of positive test weight (held-out w5 tier >= 50% in the N2 shape); (c) no blind program above tests 65; (d) verifier worst case <= 90% of the stated verifier limit; (e) kill table unchanged: every generic solver and every blind program loses >= 15% of lever points by WRONG output (or v3.5 hidden-scale loss), shipped inputs fast, reference <= 1/4 of the stated limit. Overnight auto runs: the master may send "go" at DESIGN READY; otherwise Needs Ayush.
4. **QC full (once).** Fix-all in one pass under guard rules:
   - G1 never paste QC's "Fix:" text as the direction; restate the property and list side-effect rules.
   - G2 never move an assert into an existing check or weight onto a conduct/route criterion.
   - G3 never delete a clause/sentence/grader without naming what grades the rest.
   - G4 re-check every touched check/criterion against its rule set (TS-13/14/20/25/26, CL-2/4; JD-2/5/6/7/9/13/15, AL-28); one row each in RECHECK_FIX.md.
   - G5 vacuity probe again.
   - G6 docs/TRUTH regenerated last, by script.
   - G7 never regenerate tests from a generator without a byte diff; unnamed hunks stop the session.
5. **QC recheck (round 2+).** Reviewer gets previous report, KEPT.md, CHANGED_LINES (diff -U0 of QC copies). A finding on an unchanged line or a kept item must answer the earlier pass/keep reason, else "acknowledged". Kit scripts run in full. 0 fails -> **freeze** (tree sha recorded).
6. **One harness run on the frozen bytes.** Before push Step 10 must be complete on those bytes: if QC ran in auto mode (2 oracle + 1 nop), the master runs the rest (oracle 3-5, stub, owner-only). Gate (v3.7 Ayush 28 Oct "Target <40 now": tests < 85 AND rubric < 85 AND final < 40) met -> package from exactly those bytes, check Output_RFP tests/ == frozen tests/ and scores came from that run -> push.
7. **Gate missed -> trajectory read-out first** (failed checks, skipped behaviours, false success claims). tests >= 85 -> new test lever (back to 1). tests < 85, rubric >= 85 or final >= 40 -> judge band (mid <= 20) + honesty negative, plus more test lever if needed (gate v3.7). Allowed edits: raise a core weight to TS-20 importance; add a test on a stated rule the fixture never built (AL-27); add a criterion for an odds-raising act the oracle shows; remove/down-weight only to undo double payment (TS-26/TS-13). Never fit a check to one run's quirk (AL-1/AL-4). Optional: Ayush regrades the old run to see the change. Then stage 5 recheck, then stage 6 one new run.

## T. Master decides from the trajectory (decision 8)
Inputs per run (`jobs/<slug>/trajectory/claude-opus-5/Run N/`): `verifier/reward-details.json` (check values; report.json "passed" on negatives is unreliable), `verifier/test-stdout.txt` (assert messages), `judge_response.txt` (per criterion verdict + reason), `agent/trajectory.json` (steps, files written, own checks, stress tests, final message), `artifacts/` (what the agent shipped).
Read-out the master writes (TRIP table, one row per lost or easy point):
| step | what the agent did | what the docs require (file:line) | check/criterion | class |
Classes: LOST_GRADED (lost, graded), WRONG_UNGRADED (wrong on a stated rule nothing grades), EASY (earned with no effort), SKIPPED (odds-raising habit not done), FALSE_CLAIM (final message claims success the scores deny).
Decisions from the table:
1. **Why it scored this:** points lost/earned per lever family; first-write step; did it stress-test, notice slowness, self-check.
2. **What to change (QC-safe form only; a direct edit is flagged):**
   | Edit | QC-safe form | Flagged if done directly |
   |---|---|---|
   | Raise points | only a core check of the main job, to the TS-20 level the instruction ordering supports | raised because the run failed it (TS-20; QC_FIX_PLAYBOOK_v2:42) |
   | Add test | only for a rule the docs already state that the old data never tried (AL-27), on hidden data from the same generator, one observable (TS-13) | test on an unstated rule or one run's quirk (AL-1, AL-4) |
   | Add judge item | an odds-raising habit the oracle shows, w1/w3, observable in trajectory or a declared artifact (JD-6, JD-7, JD-15) | w5 preference or "used method X" (JD-15) |
   | Add penalty | FALSE_CLAIM negative -3, disjoint from other negatives (AL-28) | stacked on an act another negative already charges |
   | Lower easy points | only where one observable is paid twice: merge or split (TS-26, JD-14, TS-13) | lowered because the model passed it (TS-20, CL-4) |
3. **Next step (gate v3.7):** tests >= 85 -> new test lever; tests < 85 and (rubric >= 85 or final >= 40) -> judge items + penalty (+ test lever if needed); gate met -> push.
4. **Write the fix prompt** directly from the table (guard rules G1-G7), then recheck QC, then 1 new harness run.
Tool: promote `_dev_research/trajectory_hardening/research_cb612aa/trip_points.py` to `tools/trajectory_readout.py`, reading reward-details.json; drop its keyword WRONG_UNGRADED detection (about 0% precise; the master classifies those rows by reading).
Regrade (`harbor trials regrade`) is optional, run by Ayush when he wants to see a change on the old run; never push evidence. [v3.7 regrade exception, Ayush 28 Oct Q1] A regrade counts as push evidence only when the edit touches judge files only (no tests/, no instruction, no environment), the run was valid, Ayush wrote OK for this regrade (verbatim in decisions.jsonl), and the regraded run is repackaged with `master_chat_tasks/tools/repackage_one.py` (A4). Otherwise diagnostic only, never packaged.

## A. Auto-mode harbor (decision 9)
Verified: `auto/auto.py:104` WORKER_PERMISSION has `"*harbor run*": "deny"`, so auto QC sessions skipped Step 10 (auto/runs/20261027T0200_night/REPORT.md:16, :57; BOARD rows d7661db, 56a292b "Step 10 not run (harbor blocked)"). Manual QC Step 10 runs only `harbor run --agent oracle|nop` (Final_checklist.md:357-364), no paid model.
Fix (opencode: last matching rule wins): after the deny line add `"*harbor run*--agent oracle*": "allow"` and `"*harbor run*--agent nop*": "allow"`. Real model runs stay denied (`*harbor run*` with any other agent, `*master_queue.py*`). Prompt line added to every QC prompt issued in auto mode (Step 10): "Auto mode: run 2 oracle runs and 1 nop run (oracle-1, oracle-2, nop-1 on the tests-only copy). Pass = both oracle 1.000 and nop 0.000." No extra permission rule limits the count.
Verified 27 Oct 18:30 (opencode 1.19.0, real `opencode run` with OPENCODE_PERMISSION = auto.py WORKER_PERMISSION + the 2 allow lines, harmless echo commands): `...--agent oracle...` ALLOWED; `export OPENAI_API_KEY=unused && yes | ...--agent nop...` ALLOWED; `...--agent openhands...` DENIED; `master_queue.py` DENIED. Today, without the 2 lines, all harbor runs are denied (BOARD d7661db/56a292b).
Guard: 3 Docker runs per auto QC session, run one after another; auto keeps max 2 Docker-heavy jobs at once (lock + `docker ps`), else the 14:35 hang repeats.
Note: Final_checklist Step 10 asks for oracle x5, nop, stub, owner-only (:357-364). An auto-mode QC sign-off therefore records Step 10 as reduced (2 oracle + 1 nop); the remaining runs (oracle 3-5, stub, owner-only) are owed before push and are run by the master or a manual QC.

## Rule-file edits (on "proceed")
| File | Change |
|---|---|
| knowledge/LEVER_RULES_v3.md -> v3.4 | Law-1 filter in 1C P-1/P-3; P-2 counts only with a p<1 stage; line 207 push = 1 valid run of frozen QC-passed bytes; Way A diagnostic only; stage 7 read-out; no re-run on same bytes |
| knowledge/QC_FIX_PLAYBOOK_v2.md -> v3 | Fix line 57 (TS-23 count) to match line 41 (option A); guard rules G1-G7 |
| knowledge/QC_RULINGS.md | Carry-over section; TS-23 option A row (sentinel v7 "merge to 35" rejected); counterfactual figure criteria AVOID |
| prompts/templates/P11_full_qc_v2.md -> v3 | STEP 0.4 carry-over inputs; MODE full/recheck; AUTO MODE Step 10 block (2 oracle + 1 nop) |
| auto/auto.py | WORKER_PERMISSION: add the 2 allow lines after `"*harbor run*": "deny"` (section A). Takes effect for workers spawned after an auto restart |
| auto/AUTO_POLICY.md | (a) a QC prompt issued in auto mode carries the Step 10 line "run 2 oracle and 1 nop" (master adds it at issue time; P11 v3 has the line as an AUTO MODE block); (b) master spawns at most 2 Docker-heavy workers (QC, harden, kill test) at once (auto.py has no Docker cap today; MAX_BUSY_WORKERS=4) |
| tools/trajectory_readout.py (new) | TRIP table from a run folder (section T) |
| master knowledge (KNOWLEDGE.md / INDEX.md) | Section T as the master's trajectory decision method |
| prompts/templates/P12_recheck_fix_v3.md -> v4 | G1-G7 + touched-rule table |
| prompts/templates/_COMMON_RULES_v4.md -> v5 | Order (decision 1), freeze, packaging integrity, Docker-only capped solver runs, variance note (same bytes: ±17.5 tests / ±20 final) |
| prompts/templates/P2_build_v4.md -> v5, P9_harden_from_results_v3.md -> v4 | Stage 2 self-checks; kill table WRONG/TIMEOUT/CRASH split; Docker-only capped solver runs; honesty negative; P9 starts with the section T read-out |
| tools/precheck.sh | Stage 2 checks |
| GOALS.md, README.md | Push = 1 run; order; decisions 1-9 |

## Current tasks under v4
| Task | Action |
|---|---|
| sentinel (pushed 07363dd) | Revise held fix 3eb08a6: drop F4 merges (option A), drop R10, apply G1-G7, merge QL findings when they come. Recheck QC -> 1 run -> re-package and re-push. |
| schema e3e74e6 | Blind score caa031b decides Law-1 (Opus/blind planners lose by TIMEOUT only = fails decision 4 unless blind loses by wrong output). QC full with J4 + A3 warn kept. |
| tariff d11904c | Losses are wrong-output (passes Law-1). Wait 185c588. QC full -> 1 run. Regrade not eligible (instruction+env changed). |
| cold-chain 678c839 | Wait 185c588. Regrade not eligible (core.py not in run manifest; instruction+env changed). QC -> 1 run. |
| district 7d95b18 | Building. Law-1 check on its final kill table (designed "LATE or feasible-only" = mostly timeout: likely needs a wrong-output stage). Regrade not eligible (env changed). |
| metered 09963d3 | Building. Its kill table fails Law-1 as designed (probe/naive/per-line TIMEOUT; label/greedy 9/48 wrong). Needs a wrong-output stage before QC. Regrade not eligible after its shipped-data change. |

## V. Regrade facts (for Ayush's optional use; verified 27 Oct, static)
- harbor 0.24.0 has `harbor trials regrade SOURCE -p TASK` (cli/trials.py:995; trial/regrade.py): copies agent/ + artifacts/, re-runs tests + judge, labels the result as a regrade, never touches the source run.
- Eligible now (latest run vs Tasks_INPUT): sentinel, schema, metered (until its build syncs). Not: district (environment changed), tariff (instruction+environment), cold-chain (core.py not in run manifest).
- The judge needs the runner's proxy (`OPENAI_BASE_URL=http://host.docker.internal:55176`, `REWARDKIT_JUDGE=gpt-5.6-sol`), so run it in the harness environment.
- `scripts/package_rfp_bundles.py` copies scores without recomputing (line 73) and does not know regrade output: never package a regrade, except under the v3.7 regrade exception (decision 5) via `master_chat_tasks/tools/repackage_one.py`.
