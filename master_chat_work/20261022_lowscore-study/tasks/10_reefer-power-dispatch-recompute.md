# 10 reefer-power-dispatch-recompute (claude-opus-5, run_1): overall 29.35 %, tests 8.06 %, rubric 50.63 %

T = `tasks_copy_20261022T0105/10_reefer-power-dispatch-recompute/`. Notes: `notes/10.md`. "UNVERIFIED" marks guesses from static reading (no runs).

## 1. Shape
- Bundle: `instruction.md` (23 lines, 793 words), `task.toml`, `environment/Dockerfile` + `environment/data/` (59 files), `solution/` (solve.sh, solve.py 71 KB, TRUTH.md 30 KB), `tests/` (test_output.py 7023 lines / 305 KB, judge.toml 14 KB, reward.toml, test.sh, Dockerfile).
- Data: 22 `.md` (14 stage specs p01-p14, overview, lineage, glossary, traps register, schema reference, serialisation and program contracts, worked examples), 13 csv, 6 toml, 3 txt, 2 yaml, 2 tsv, 2 jsonl, and one each of xml, psv, ndjson, json, db, conf plus three office papers (xlsx with six sheets one live, pdf memo, docx directive). Largest: crane_duty_feed.ndjson 75 KB, ambient_condition_returns.json 50 KB. Three papers that "govern nothing" (reefer_thermal_supplement.csv, legacy_tariff_extract.csv, night_office_audit.db, per data_lineage.md).
- Outputs (task.toml:2): 31 documents + `/app/out/reeferdispatch.py` (32 artifacts).
- Tests: 35 criteria = 16 positive (total 62: all_artifacts_exist 1, core_documents_parse 1, five `shipped_*_exact` blocks x3 = 15, nine `program_*_exact` x5 = 45) + 19 negative (18 x -3, `negative_hardcoded_sample_answers` -5; total -59) (registrations test_output.py:6985-7019). Judge: 35 criteria, positive 79, negative -14 (R32 -3, R33 -5, R34 -3, R35 -3). reward.toml: 0.5/62 and 0.5/79.
- Timeouts: agent 14400 s, verifier 5400 s (task.toml:35, :22), program run 900 s (test_output.py:5977). Run: 42 steps, 35 min, 1.55 M prompt tokens, cost 8.72 USD; verifier 47 s.

## 2. Is the low score genuine? (static screen)
| check | class | deciding line (T/tests/test_output.py) |
| --- | --- | --- |
| all_artifacts_exist, core_documents_parse | READ | `_t_all_artifacts_exist` :6045, `_t_core_documents_parse` :6055 read `/app/out` |
| shipped_p01_p02, p03_p04, p05_p06, p07_p09, p10_p14 (5) | READ | `_shipped_block` :6102-6104 -> `_compare(ref_dir, _delivered(), block)` |
| program_{strained,wide,sparse}_{early,middle,late} (9) | EXEC | `_program_block` :6107-6114 -> `_case_output` :5985-6010 -> `_run_program`: `command = [sys.executable, str(_program()), ...]` :5976, `subprocess.run(_untrusted(command), ...)` :5977 |
| 18 of the 19 negatives | READ against a variant of the shipped day (`_matches_variant` :6231-6249) or EXEC (ignores-input, nondeterminism, filename, dirties) | e.g. :6252-6262 |
| negative_hardcoded_sample_answers | EXEC | `_reproduces_only_the_shipped_day` :6451-6471 |

- No EXEC check passed (all 9 program blocks failed). The rule "if at least one EXEC check passed ..." therefore does not apply; step 2c below.
- How the tests run the program: `_untrusted` (:5857-5864) prefixes `setpriv --reuid=nobody --regid=nogroup --clear-groups` (:5849) when root. The tests chmod the work root 0755 (:5875), cwd 0777 (:5898), minted data 666/777 (`_relax` :5906-5910) and the output directory 0777 (:5967-5970), but never `/app/out/reeferdispatch.py` itself (`_program()` returns the path). `tests/test.sh` chmods only `/logs/verifier` and `/tests`; `tests/Dockerfile` only checks `getent passwd nobody` and `mkdir -p /app`. So the same hazard as tasks 08 and 09 exists here.
- Trajectory vs delivered: the editor created the program (step 21, then `str_replace` 22-31), no `ls -l` of it anywhere (step 40 uses `ls -A`), so the delivered mode is UNVERIFIED. The agent's own runs worked (steps 29, 32, 39, exit 0, 31 documents).
- But here the READ checks already show a genuine failure: four of the five shipped blocks differ from the reference (`shipped_p01_p02`, `p05_p06`, `p07_p09`, `p10_p14` failed; `p03_p04` passed). The hidden days run the same code. A defect in P05/P06 cascades into every later block, and the three early blocks include P05/P06 documents (PROGRAM_EARLY :119), so a runnable program would most likely fail the hidden blocks too (UNVERIFIED which stage is wrong; see step 4).
- Other breakers: runtime not measured by the agent (UNVERIFIED), limit 900 s; no hardcoded path seen in the first 100 lines of the run output (UNVERIFIED for the 86 KB file); stdlib only per judge R3 (met).
- Unlike task 09, the replayer detector here returns False when a run failed (:6451-6471 `if record is None or record["failed"]: return False`), so the permission hazard cannot also brand this agent a cheat.
Label: GENUINE - 4 of 5 READ shipped blocks differ from the reference (ctrf: shipped_p01_p02, p05_p06, p07_p09, p10_p14 failed), so the program is wrong on the shipped day itself regardless of how the EXEC checks ran; permission hazard present but UNVERIFIED and unlikely to change the result.

## 3. Instruction anatomy
- Same template as task 09: goal and withdrawn publication (instruction.md:1), reading order readme_first -> overview -> lineage (:3), three non-text papers with "take the live sheet by matching its key cell against the day reference, not by name and not by position" (:5), a one-paragraph stage procedure (:7: "Allocate against the nominal capacity, then withhold the standing reserve of each feeder before any free capacity is counted and spill what the reserve no longer admits. Take the confirmed crane duty off the capacity left for reefers rather than adding it to their load, work the battery against the reconciled load carrying its state of charge forward, and settle the discretionary allowance over the passes the budget allows."), number form (:9), 31 documents by path (:11), schema and serialisation (:13), program contract (:15), scratch rule "Use /tmp" (:17), sentinel pointer (:19), final report list (:21).
- It names several of the traps in the stage paragraph (reserve before free capacity, crane taken off capacity, damped iterate truncated by a pass budget), so the "hidden composition" is in the order of application and in values from the office papers, not in the existence of the rules.
- Asks for in the final message (:21): rung counts, live sheet key and sheet, reefers whose energy return declared nothing, a feeder and interval where crane duty took adjusted capacity to zero, "the pass count the reconciliation ran to with one share still moving at the last pass" (judge R6 wants one named reefer still moving), the seven objective components.
- Style vs ours: 793 words, longer than all four of ours (350-571) and more procedural; ours state the end state and rules of engagement and end with a required account. Ours give some inline conventions (district "whole ticks, whole cents, basis points"); this one gives number form too (:9).
- Hypothesis check (ours over-specify): AGAINST for this task. It is as precise as ours or more, and still scored 29 %; the cost came from byte-exact multi-stage equality and judge examples.

## 4. Every failed positive check and every fired negative
ctrf: 35 tests, 13 failed positives, 0 fired negatives; all covered below. (Passed positives: all_artifacts_exist, core_documents_parse, shipped_p03_p04_exact. Passed = not fired for all 19 negatives; weighted 5/62 = 8.06 %.)

Cause key: X = real divergence of the agent's program on the shipped day, exact stage UNVERIFIED; P = EXEC hazard (unrunnable program), UNVERIFIED and not needed to explain the failure.

| check (w) | what it checks / rule and file:line | what the agent did (step / artifact) | cause |
| --- | --- | --- | --- |
| shipped_p01_p02_exact (3) | normalised_reefers.jsonl, availability_lattice.csv, interval_demand.csv (BLOCK_P01_P02 :98-99). Rules RULE P02.a-f at spec_stage_p02_availability_lattice.md:5-31; P02.f (:29-31): the demand "counts every reefer whose lattice holds that interval ... The count is taken before the admission ladder runs" | artifact `interval_demand.csv` built by reeferdispatch.py:743-800, which skips every reefer whose feeder is not in force (`if feeder_id not in corpus.feeders_in_force_set: continue`, in stage_p02) although the ladder (rung DR_FEEDER_OUT_OF_FORCE) has not run at P02; normalisation not inspected in detail | misapplied (two rules combined: ladder applied early) - candidate, UNVERIFIED |
| shipped_p05_p06_exact (3) | provisional_allocation.psv, feeder_load_ledger.csv, feeder_violation_ledger.csv, spill_decisions.tsv (BLOCK_P05_P06). RULES P05.a-f (spec_stage_p05_provisional_allocation.md:7-29) and P06.a-f (spec_stage_p06_feeder_reconciliation.md:6-38) | P06 code (reeferdispatch.py:1027-1075) removes the highest rank until load <= reserved and tries to spill to the next lattice interval whose provisional load plus draw fits; result: all 101 removals `unspilled` (step 42: "all 101 removals published `unspilled`"), derating/windows per P05.b-c not inspected | X, misapplied or combined wrongly; candidate: spill test uses provisional (unreduced) loads of later intervals - UNVERIFIED |
| shipped_p07_p09_exact (3) | crane_adjusted_capacity.csv, battery_schedule.csv, soc_ledger.psv, reconciliation_iterations.csv. P07 crane (spec_stage_p07_crane_interaction.md), P08 battery, P09.a-m (spec_stage_p09_load_reconciliation.md:5-72; damping P09.h, min step P09.i, half-up rounding each pass P09.j) | adjusted capacity clamped to 0 in 103 feeder-intervals (step 39); reconciliation 5 passes, 89 of 90 moving at pass 5 | inherits P05/P06 errors (cascade) and/or own errors; UNVERIFIED |
| shipped_p10_p14_exact (3) | 18 documents of the last stages: tariff, correction, cycle break, objective, final schedule, publication (BLOCK_P10_P14 :105-116) | objective hard_violations 120, unmet 172631 Wh (steps 32, 39) | cascade from upstream; UNVERIFIED |
| program_strained_early_exact (5) | stages P01-P06 documents (PROGRAM_EARLY :119) of unseen strained day, run with options reversed and no precreated out dir (:6001 awkward) | program ran on shipped data only; options reversal untested | X (same early defects) + P |
| program_strained_middle_exact (5) | BLOCK_P07_P09 on strained day | none | X + P |
| program_strained_late_exact (5) | BLOCK_P10_P14 on strained day | none | X + P |
| program_wide_early_exact, program_wide_middle_exact, program_wide_late_exact (5 each) | same three blocks on the wide day | none | X + P |
| program_sparse_early_exact, program_sparse_middle_exact, program_sparse_late_exact (5 each) | same three blocks on the sparse day | none | X + P |
Points: 13 failed positives lose 57 of 62 weight (91.9 %): shipped 12, program 45. Fired negatives: none, so the penalty side costs 0; the reason none fired is that a wrong program rarely matches a specific named wrong variant (`_matches_variant` :6231-6249) - they are "negative weight sits on wrong paths no detector reaches" by design (TRUTH.md "four negative criteria sit on wrong paths no detector reaches").
Checks that a lazy agent also passes: `all_artifacts_exist` and `core_documents_parse` (cheap), and `shipped_p03_p04_exact` (energy floor and queue, an early stage); all 19 negatives are free for any program that does not match a named wrong reading.

## 5. Levers
| lever | family | where documented | weight share lost | triggered |
| --- | --- | --- | --- | --- |
| Staged allocation: allocate at nominal (P05), withhold reserve and unpick (P06), take crane off capacity (P07); an early error voids every block after it | B dependent chain | instruction.md:7; TRUTH.md defect 1 (solution/TRUTH.md:14-19); spec_stage_p05:3-5 | up to 57/62 = 91.9 % of tests (46 pp overall) incl. cascade | yes (4 shipped blocks, 9 program blocks) |
| Stage-ordered scoring blocks, each compared byte for byte | E stacked constraints / D size ladder (three hidden days of different profile) | test_output.py:98-121 | 45/62 = 72.6 % (program blocks) | yes |
| Damped iterate truncated by a pass budget living in the pdf, half-up rounding every pass | A hidden composition (value in office paper + rule in spec) | spec_stage_p09:25-47; TRUTH.md defects 2-3 | part of p07_p09 3/62 + program middle 15/62 | UNVERIFIED which part wrong |
| Live sheet by key cell, values in xlsx/pdf/docx | A | instruction.md:5 | 0 (judge R5, R14-R16 mostly met; R14 failed on cell references) | handled |
| Unreached branches reached by hidden days (7 of 8 sentinel outcomes) | F/D | corpus_sentinel_note.txt; TRUTH.md "Seven of the eight outcomes ... are reached by a graded day" | in program blocks | UNVERIFIED |
| "Narrate one example" judge criteria (R6, R14, R18, R20-R27, R29, R30) | NEW | judge.toml | 37/79 = 46.8 % of judge (23.4 pp) | yes |
| Process-order criterion R1 (wc -c on all files before the entry papers) | NEW conduct | judge R1 | 1/79 | yes |
| Hidden-day execution under dropped uid on an editor-written program | NEW (harness) | test_output.py:5857-5864, :5970 | not needed to explain the score | possible, UNVERIFIED |

## 6. Judge
Rubric 40/79 = 50.63 %. Negatives R32-R35 not fired.
| id | w | met | note |
| --- | --- | --- | --- |
| R1 entry papers before registers | 1 | NO | step 3 ran `ls -la /app/data && wc -c /app/data/*` before reading |
| R2 stage order | 3 | yes | |
| R3 stdlib only | 5 | yes | |
| R4 sentinel note | 3 | yes | step 4 |
| R5 live sheet key + sheet | 3 | yes | final message |
| R6 pass count + one reefer still moving | 3 | NO | reported 5 passes and "89 shares" but no reefer, and wrote "no pass at which exactly one share was still moving" (misread of the item); its own step 39 output listed rf_0017, rf_0031, ... |
| R7 rung counts | 3 | yes | |
| R8 empty returns | 1 | yes | 11 reefers listed |
| R9 objective order | 1 | yes | |
| R10 out-of-force feeder | 1 | yes | fd_03, fd_11 named |
| R11 crane clamp | 3 | yes | fd_01 interval 2 |
| R12 fourteen named steps | 1 | yes | |
| R13 data untouched | 3 | yes | |
| R14 workbook parts / cell | 3 | NO | opened the zip, did not show cell references |
| R15 memo text | 3 | yes | |
| R16 directive keys | 3 | yes | |
| R17 reserved capacity of a named feeder | 3 | yes | |
| R18 reefer need, target, share at last pass | 3 | NO | no named reefer |
| R19 share rounded and next pass opens from it | 3 | yes | |
| R20 MJ/h conversion for a named reefer | 3 | NO | implemented, not shown |
| R21 redistribution cell and reefer | 3 | NO | |
| R22 cluster-rung reefer on four-reefer plug | 3 | NO | only counts |
| R23 boundary disconnect reefer | 3 | NO | only the worked example |
| R24 soc at reserve interval with discharge | 3 | NO | counts only |
| R25 withdrawn highest revision vessel | 3 | NO | |
| R26 superseded return higher sequence | 3 | NO | |
| R27 removed placement with landing interval | 3 | NO | "all 101 unspilled" |
| R28 dead code | 1 | NO | several unread bindings listed by judge |
| R29 sweep budget = depth + 2 reconciled | 3 | NO | |
| R30 inert papers | 1 | NO | |
| R31 rerun compare | 1 | yes | |
Failed weight 39 (R1 1, R6 3, R14 3, R18 3, R20-R27 24, R28 1, R29 3, R30 1). Criteria avoid double-paying: figures in documents are graded by tests; the judge asks for a named case drawn from the session (trajectory) or final message. They are not paid for text copied from the docs because each asks for a specific derived value of a real entity.

## 7. How it passes QC and still beats the agent
- Everything is documented in 14 stage specs with `RULE Pxx.y` numbering, six workbook sheets with a key cell, a pdf with the budget, a docx with key positions; the instruction names the staged order. TRUTH.md lists focal defects (allocation staging, truncated damped iterate, rounding every pass, live sheet) and traps (boundary disconnect, absent ambient, battery reserve).
- Traps documented but easy to miss: P02.f "count is taken before the admission ladder runs" (cross-stage ordering); P06.c spill condition and which load is compared; P09.i-j rounding per pass; P05.b-c derating span. Placement: each rule is in one spec, but the effect appears in a different document several stages later.
- Anti-cheat: 11 named wrong readings, each detected by recomputing the shipped day with one decision flipped and matching the delivered bytes (`_variant`/`_matches_variant` :6211-6249); replayer detector requires the delivery to be right on the shipped day and to write those same bytes on unseen days (:6451-6471); corpus-name scan (`_names_this_day` :6435); input-blind, nondeterminism, filename, dirtied-directory and module-shadowing detectors.
- Design note: the detector is written so a failed run never fires a charge (`record["failed"]` -> False), which avoids task 09's false brand.

## 8. Trajectory story
- 42 steps, 35 min. Read: `ls`/`wc -c` of all data (3), navigation and glossary (4), policies and registers (5), all specs (6), schema reference (7), office papers via a script (8-12), ladder (13), registers (14-16), day dumps (17-20; 10:00 -> 10:20 gap of 20 min), then ONE `create` of the 86 KB program at step 21.
- Four fix runs (23-29: KeyError on register sequence field, missing `calls`), status check (30), fix of core document names (31-32); a verify script (34-35) that found two key-order faults, repaired by 36-39; final run and report script (39); cleanup (40-41); finish (42).
- Never read the decoys? `reefer_thermal_supplement`, `legacy_tariff_extract`, `night_office_audit.db` not opened (judge R30: not named as inert).
- Self-test: schema conformance, determinism, renamed copy, manifest digests (step 35). No check of any rule against a worked value; no cross-check of the 101 `unspilled` result against P06.c, though step 42 says "on this day no removed placement finds a later interval of its own lattice that is free under the reserved capacity" and the agent labelled the 120 hard violations "structural" and moved on (anomaly rationalised, not debugged).
- Final message claims: rung counts, live sheet `Berthing` at position 3 of 6, 11 reefers with undeclared energy, crane clamp `fd_01` interval 2, 5 passes, objective vector. Nothing contradicts delivered documents (R33 not fired). It misreads the "one share still moving" item.

## 9. Reusable patterns / things to avoid
- Stage-ordered scoring blocks (here five shipped, three hidden days x three blocks) give partial credit and a clear cascade map; keep, but let the first block cover only an early stage so an upstream mistake costs little.
- Put the checksum-like cue ("a feeder and interval where crane took adjusted capacity to zero", "pass count with one share still moving") in the final report: it forces the agent to read its own documents, and it did surface anomalies here that the agent rationalised.
- A spec rule whose scope depends on another stage's timing (P02.f "before the ladder runs") is a cheap, fully documented trap.
- Judge "name one concrete case" criteria are 47 % of the channel here; they penalise silence not error. Phrase them as "when you explain X, you must cite a real entity" or tie them to the final report.
- Avoid the hazard shared with 08/09: EXEC checks on a program the test never makes readable to the dropped uid. Here it probably did not matter only because the agent was already wrong on the shipped day.

```json
[
  {"task":"10_reefer-power-dispatch-recompute","name":"staged_allocation_cascade","family":"B","mechanism":"allocate at nominal capacity (P05), withhold reserve and unpick (P06), take crane off capacity (P07); a defect upstream voids every later block","where_documented":"instruction.md:7; spec_stage_p05:3-5; spec_stage_p06:3-4; TRUTH.md defect 1","weight_share":0.919,"triggered":true,"cause_of_failure":"two rules combined wrongly or misapplied (stage UNVERIFIED)","evidence":"ctrf: shipped_p01_p02, p05_p06, p07_p09, p10_p14 failed, p03_p04 passed; 101 of 101 removals unspilled (traj step 42)"},
  {"task":"10_reefer-power-dispatch-recompute","name":"hidden_day_blocks_by_stage","family":"D","mechanism":"three unseen days (strained, wide, sparse) each graded in three stage-ordered blocks of byte-exact documents","where_documented":"tests/test_output.py:98-121,6107-6114","weight_share":0.726,"triggered":true,"cause_of_failure":"hidden-input generalisation failed / inherits shipped errors","evidence":"9 of 9 program_* checks failed"},
  {"task":"10_reefer-power-dispatch-recompute","name":"count_before_ladder_ordering","family":"A","mechanism":"interval demand counts reefers before the admission ladder runs; applying the ladder early removes rows","where_documented":"spec_stage_p02_availability_lattice.md:29-31","weight_share":0.048,"triggered":true,"cause_of_failure":"misapplied (UNVERIFIED)","evidence":"reeferdispatch.py stage_p02 skips reefers whose feeder is not in force when summing interval demand"},
  {"task":"10_reefer-power-dispatch-recompute","name":"damped_truncated_reconciliation","family":"A","mechanism":"pass budget in the pdf, damping fraction in the live xlsx sheet, minimum step, half-up rounding at each pass","where_documented":"spec_stage_p09_load_reconciliation.md:25-47; instruction.md:5","weight_share":0.048,"triggered":false,"cause_of_failure":"UNVERIFIED","evidence":"negatives run_to_convergence and rounds_once not fired; reconciliation_iterations in failed block p07_p09"},
  {"task":"10_reefer-power-dispatch-recompute","name":"narrate_one_example_judge_criteria","family":"NEW","mechanism":"judge asks for a named real case (reefer, interval, vessel, cell) from the session or final message","where_documented":"judge.toml R6,R14,R18,R20-R27,R29,R30","weight_share":0.468,"triggered":true,"cause_of_failure":"other: output/narration not asked for","evidence":"score.json: 13 of these criteria failed for lack of a named case"},
  {"task":"10_reefer-power-dispatch-recompute","name":"exec_under_dropped_uid_on_agent_file","family":"NEW","mechanism":"9 program_* checks run reeferdispatch.py as nobody; tests never chmod it","where_documented":"tests/test_output.py:5857-5864,5970","weight_share":0.0,"triggered":false,"cause_of_failure":"possible but not needed to explain score (UNVERIFIED)","evidence":"READ shipped blocks already fail"}
]
```
