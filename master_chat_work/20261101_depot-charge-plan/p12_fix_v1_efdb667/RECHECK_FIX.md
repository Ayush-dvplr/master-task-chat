LEVER GONE AFTER FAIRNESS FIX

Status PAUSED (master direction: kill row `careful shift search` keeps more than 60% of lever points after DS-21). Only DS-21 is applied; TS-26, JD-5/JD-8, CL-3, AL-2, AL-27 and DS-20 are rechecked (REAL) but not applied.

| kill row | bundle | tests points (of 191) | lever points kept (of 166) | outcome |
|---|---|---|---|---|
| careful shift search (all 96 shifts per depot vs settlements.csv + blind be981e2 exact min-cost flow + lexicographic tie-break) | after DS-21 (tree 7e3ade15a78b) | 191, reward 1.0 | 166 (100%) | EXACT on shipped and all hidden corpora |
| careful shift search | before (tree 6a88219de6f8, backup WORK/qc1_6a88219de6f8) | 191, reward 1.0 | 166 (100%) | EXACT |
| blind be981e2 as saved (six slot readings, no shift search) | after DS-21 | 3, reward 0.0157 | 0 | CRASH on shipped: `Error: cannot read settlements.csv: no tariff application fits depot East`; only missing_settlements_stops_naming_file passes |

Lever points = 32 fresh plan checks (w5) + reordered_copy_policy_audit_exact (w3) + relocated_copy_summary_exact (w3). Runs: Docker `dcp-verifier:1`, `--memory 4g --cpus 2`, scratch `/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/fix1-20261101T041953-b9b9/` (logs careful_after.log, careful_before.log, blind2_after.log, oracle_after.log, each ALL_DONE); program `progs/careful/derive_report.py` = be981e2 with its meter candidates replaced by the 96 whole-slot shifts.

Reading: the shift reader already kept 100% before the fix (WORK/KILL_TEST.md row b+ predicted it); the only defence was that a reader does not think of shifts. Once rule 12 names the family, the meter lever is a 96-way search any careful reader does, and the planner levers (F, T, C) were already solved by blind be981e2. Each lever's points sit on the same fresh checks, so with M reachable no lever separates the careful reader. Blinds ec4f695 and a60099a were not re-scored (stopped per direction); GPT session 4653510 could not score them (RewardFileNotFoundError, its BLINDS.md).

# RECHECK_FIX depot-charge-plan, P12 fix v1 (board efdb667)

QC report: `/Users/mac/Desktop/Terminal Bench/QC/reports/depot-charge-plan/v1.md` (FAIL, 6 fail / 0 minor / 3 warn). Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (same as the QC record). Bundle tree before 6a88219de6f8, equal to QC copy 03ec0bf (`diff -rq` rc 0), so no noise rows. Session rename: `name_session.py efdb667` printed `codex: no match` and `opencode: ['ses_e6be0c307ffeEjTEnFbIoAnwhZ']`; the list does not show efdb667 by name.

Levers: M meter convention (rule 12), F feeder + cabinets (rules 10-11), T lexicographic order + tie-break (rule 15), C coupling (rule 16).

## Phase 1 recheck

| ID | label | rule quote (live kit file:line) | evidence (bundle file:line) | decision | playbook row | effect M / F / T / C | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| DS-21 (AL-F0e, CL-10) fail | REAL | 02_Data_Solution_QC.md:70 "name the exact piece of information the solver cannot obtain, and show that it appears in no agent-visible file and follows from nothing in them" | environment/data/docs/charging_rules.md:27 "Each depot's meter has its own way of applying a tariff ... and the settlements allow exactly one" (no family named); tests/test_output.py:174-182 `conv()` prices hidden depots at `price[(s+k)%96]`, k from range(4,92); shipped `ks = {d: 0}` (L177-178), so shipped settlements fit identity and confirm nothing about shifts | FIX: state the shift family in rule 12; ship one depot with a non-zero shift its settlements pin; hidden corpora keep their own shifts | DS-21 / IN-15 (state once, neutrally, in the governing file) | M easier (family named), F none, T none, C none | none possible inside DS-21: kill row keeps 100% => PAUSED | docs_master/charging_rules.md, gen_core.py, environment/data, tests/test_output.py, solution/TRUTH.md |
| TS-26 fail | REAL | 03_Tests_QC.md:53 "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice" | tests/test_output.py:3422-3434 `_relocated()` copies the h3 tree (same seed as `fresh_h3_summary_exact`) and `_run_program` (L3345-3352) already runs every fresh run from a foreign `elsewhere-` cwd with absolute paths | FIX: relocated run passes relative `--data`/`--out` from its own cwd (weight 3 kept) | TS-26/JD-14 (name observable, narrow one) | none / none / none / none | none | tests_src/infra.py, tests/test_output.py |
| JD-5 / JD-8 R9 fail | REAL | 04_Judge_QC.md:71 "If a judge would need to check two separate things, split it"; 04_Judge_QC.md:77 "Same observable = overlap = fail" | tests/judge.toml:118 R9 clause (b) "a missing or malformed declared input stops the run with a message naming the file" reads the same exit status + stderr as test `missing_settlements_stops_naming_file` (`_check_missing_input`) | FIX: cut R9 to clause (a); clause (b) stays graded by the rule-22 test (G3 named) | JD-5 + JD-8 | none on all levers | none | tests_src/judge_spec.py, tests/judge.toml |
| CL-3 fail | REAL | Final_checklist.md:490 "ask whether they can be lifted straight out of something the agent already has" | shipped plan equals published_plan.csv (QC v1: changed false for 123 buses, moved 0, feeder peak 975 of 1300); environment/data/disruption_notice.md:9 derating 170 kWh/slot 20:00-22:00 does not bind | FIX: shipped derating/outage below the published load in its window so the shipped plan moves kWh off published_plan.csv; hidden corpora unchanged | CL-3 (shipped value must be derived, not copied) | M none, F harder on shipped (binds), T none, C none | none | gen_core.py, environment/data, tests/test_output.py, solution/TRUTH.md |
| AL-2 fail | REAL | 05_Alignment_Integrity_QC.md:33 "Everything promised is graded. Enumerate from `instruction.md` alone" | instruction.md:9 flag defaults and "writes only into the output folder"; instruction.md:23 "the totals from `/app/out/summary.json`"; no check or criterion reads them | FIX: flagless run in a sandboxed /app copy (w1-2); fresh run asserts its cwd temp dir and data folder unchanged; R10 also names the summary totals | AL-2/CL-1 (grade via observable on hidden inputs) | none on all levers | none | tests_src/infra.py, tools/assemble_tests.py, tests_src/judge_spec.py, tests/ |
| AL-27 fail | REAL | 05_Alignment_Integrity_QC.md:38 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" | charging_rules.md:13 rule 4 order; QC v1: no roster row in any corpus meets two of the four conditions | FIX: hidden corpora get roster rows meeting two conditions (retired + bad window, duplicate + bad window, unknown id duplicated) | AL-27 (hidden reseeded rows constructing both faults) | none on all levers | none | gen_core.py, tests/test_output.py |
| DS-20 warn | REAL | 02_Data_Solution_QC.md:68 "Walk the oracle's logic against every rule the contract states" | charging_rules.md:28 rule 13 silent on published rows for a bus not on the plan; solution/solve.py:308-310 skips them; tests/test_output.py:685 `byid[r["bus_id"]]` would raise KeyError | FIX: one sentence in rule 13 (such rows are ignored); reference load() skips them like solve.py | DS-20 (fix oracle/contract agreement) | none on all levers | none | docs_master/charging_rules.md, proto2/solve_proto.py, tests/ |
| TS-23 warn | REAL (count) | 03_Tests_QC.md:62 "at most 35 (warn)" | 45 checks registered (tests/test_output.py registrations); count after fix recorded in Fix receipt | KEEP with count, no cap (master direction, _COMMON_RULES_v5 score rule) | TS-23 KEEP | none | n/a | none |
| JD-16 warn | REAL in kit terms, test not buildable | 04_Judge_QC.md:93 item 4 "Scope over undeclared paths is invisible to the verifier, so the judged channel owns it." | task.toml:2 artifacts list only /app/out files; task.toml:24 `environment_mode = "separate"`; tests/Dockerfile copies only tests/ (no /app/data in the verifier) | KEEP R16 as the owner; no test (deviation from master direction, see below) | JD-16 KEEP | none | n/a | none |
| oracle x3 (kit x5) | acknowledged | Starter/kit oracle x5 | QC ran oracle x3 = 1.0 | KEEP (Ayush acknowledged) | ACK | none | n/a | none |

## Deviations from master directions
- JD-16: master asked for a test comparing /app/data with `_shipped_files()` bytes. The verifier never receives /app/data (task.toml:2 artifacts, task.toml:24 separate verifier, tests/Dockerfile has no data), and the kit gives undeclared-path scope to the judge (04_Judge_QC.md:93 item 4). Adding /app/data to artifacts would let a positive test pay the nop run (gate nop 0) or make a negative test stack with R16 (AL-28). Kept R16; KEPT.md row.

Note on the table: only the DS-21 row is applied. For TS-26, JD-5/JD-8, CL-3, AL-2, AL-27 and DS-20 the "files changed" column lists the planned files; none of them was edited (paused).

## DS-21 as applied
- WORK/docs_master/charging_rules.md rule 12 (shipped as environment/data/docs/charging_rules.md:27): "Each depot's meter reads the tariff as if its clock were shifted by a whole number of slots: for one whole number k from 0 to 95, the same on every day, it applies to the slot that starts at time t the price the bands give the time k times `slot_minutes` minutes after t, wrapping past midnight. A depot's k is the one under which every row of `settlements.csv` for that depot is billed exactly its `cents` by the version in force on the row's `settled_date`; the settlements fit exactly one k per depot."
- WORK/gen_core.py conv(): shipped shifts North 0, South 0, West 0, East 28 (East pinned uniquely by its shipped settlements); hidden corpora keep distinct shifts from range(4, 92).
- Regenerated by script: environment/data (datagen.py; only docs/charging_rules.md and settlements.csv changed), tests/test_output.py (assemble_tests.py; G7 diff WORK/g7/ds21_tests.diff, 3 hunks: ks line, embedded charging_rules.md, embedded settlements.csv, all DS-21), solution/TRUTH.md last (tools/truth.py). reward.toml unchanged (P 191, judge 35). solve.py unchanged (fit_meters already tries every shift).

## Gate results (DS-21 bundle, smoke only)
- Oracle smoke x1 (scratch runner, verifier image, judge removed): solve rc 0, 9 self-check stages ok, tests reward 1.0 (logs/oracle_after.log). The formal fix gate (exe_copy oracle x3 / owner x1 / nop x1) was not run: paused before Phase 2.
- xref_check: 14 entries, 0 findings. precheck.sh last line: PRECHECK CLEAN (45 tests, 16 criteria; one existing WARN JD-5 R15, not new). No __pycache__.
- STACKING_CHECK not re-run (no check or criterion changed).

## Side effects
| FIX id | ids re-checked | result |
|---|---|---|
| DS-21 (rule text + data regen) | DS-22, TS-17, TS-24, AL-18, AL-19 (FIX_SIDE_EFFECTS IN-15 regen) | DS-22 PASS (precheck TRUTH sha256 lines match); AL-18 PASS (TRUTH regenerated after data); TS-17/TS-24 no check changed; AL-19 PASS (rule 12 stated once, in its own rule) |

## Noise keeps
None: bundle before equals QC copy 03ec0bf byte for byte, every finding is on current bytes.

## Trap survival
| lever | before loss (single wrong-reading variant) | after | ratio | verdict |
|---|---|---|---|---|
| M meter | 166 (L_meter_identity) | careful shift reader loses 0 of 166; identity variant not re-measured | n/a | lever reachable by a stated search; accepted this round per direction, reported as the pause reason |
| F feeder + cabinets | 166 | not re-measured (no check changed) | n/a | planner already solved by be981e2 |
| T tie-break | 166 | not re-measured | n/a | planner already solved by be981e2 |
| C coupling | 166 | not re-measured | n/a | planner already solved by be981e2 |

## QC_RULINGS rows
- TS-26 | relocated_copy_summary_exact re-runs the h3 tree from a foreign cwd with absolute paths, like every fresh run | QC fail (same observable as fresh_h3_summary_exact) | REAL | the relocation never reached the program's path handling; planned fix: relative --data/--out from the new cwd (not applied, paused).

## Touched rules
None: no test check or judge criterion was added, split, re-worded, re-weighted or deleted (DS-21 regenerated only embedded data and a generator constant).

## Vacuity probe
Not run as a separate pass (paused before Phase 2). The nop gate on the QC copy scored 0 and DS-21 changed no check; the formal probe belongs to the fix gate after the master's decision.

## Fix receipt
- (a) tree before 6a88219de6f8 (QC copy 03ec0bf), after 7e3ade15a78b (same command).
- (b) no test or criterion changed; positive totals tests 191 -> 191, judge 35 -> 35.
- (c) oracle 1.0 x3 / owner 1.0 / nop 0 before (QC v1); after: oracle smoke x1 1.0, owner and nop not run (paused).
- (d) be981e2 (blind2): before not re-scored by me (GPT 4653510 blocked); after 3/191, all 166 lever points lost by CRASH on shipped East. careful shift search: 191/191 before and after. ec4f695 and a60099a: not re-scored (paused).
- (e) AL-18/DS-22/DS-27 PASS (TRUTH regenerated, sha256 lines match, precheck); JD-14/AL-28 unchanged from QC v1 (JD-8 R9 overlap still open, not applied); AL-1/AL-2 finding still open (instruction.md:9, :23 ungraded, not applied); AL-27 finding still open (charging_rules.md:13, not applied).

## Lessons for the master
- A meter family the shipped data never exercises is both unfair (DS-21) and the lever's only defence; naming it turns the lever into a 96-way search | template_change: /Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md:87 (add: a hidden-convention lever must survive a kill row that searches the stated family on visible data before the design blind)
- Run the stated-family kill row (row b+ here) as a blocking gate at design time, not as an observation | no change: KILL_TEST already lists b+; the gap was treating it as a risk note instead of a stop
