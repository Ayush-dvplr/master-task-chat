# P12 fix v13, schema-migration-plan-repair (board 6ebf33a)

QC report: QC/reports/schema-migration-plan-repair/v13.md (FAIL: 1 fail, 1 minor, 1 warn, 2 acknowledged). Live kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (rule IDs and wording below quoted from the live kit; none changed against the report). Session renamed 6ebf33a (opencode ok, codex no match). Bundle backed up to WORK/qc13_589d2aa9c1e0 (tree 589d2aa9c1e0 = bundle = QC copy 68bec9e = Tasks_INPUT).

## Findings

| ID | label | rule quote (live kit) | evidence quote | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| DS-20 (fail) | REAL | 02_Data_Solution_QC.md:68 "DS-20 The oracle obeys the contract, independently of the tests." | environment/ci/repository_contract.md:88-93 "Inside these limits every `plan_migration` call must return within 10 seconds on a machine with 2 CPUs"; solution/solve.py:153 `_STATE_SEARCH_LIMIT = 200_000`, :163 "grows past ``_STATE_SEARCH_LIMIT`` steps, every reachable edge is kept"; QC v13.md:173-182 g2 286.06 s, g4 61.68/74.30 s. Not noise: QC built a new in-limit graph; the cited code is the code QC timed | FIX (option a, master direction): oracle planner rewritten (exact backward cost search over bit sets of field states, no give-up limit), contract and docs unchanged | DS-20 DO "Fix the oracle" | none on every lever (oracle only; identical plans on every reference call, see DS-20 evidence) | none | solution/solve.py (planner repair hunk), solution/TRUTH.md (by script) |
| DS-22 (minor) | REAL | 02_Data_Solution_QC.md:78 "DS-22 TRUTH.md describes the bundle that actually shipped." | solution/TRUTH.md:156-157 "The reference solution runs every probe and prints `check <description> ok` with its witness."; solve.py prints `check` lines for the three probe-band checks only, contract checks print `<description>: ok (<seen>)`, self-check probes print nothing | FIX: TRUTH prose rewritten by script, last | DS-22 DO "Rewrite TRUTH.md to the shipped code and data, sha256 by script last" | none on every lever (TRUTH.md is not agent visible) | none | solution/TRUTH.md |
| AL-17 / TS-11 (warn) | REAL | 05_Alignment_Integrity_QC.md:74 "AL-17 Timeout story coherent: instruction's \"You have N seconds\" == agent timeout_sec; verifier timeout plausible for what test.sh does." (the live kit's TS-11 is determinism, 03_Tests_QC.md:41; AL-17 governs) | task.toml:22 `timeout_sec = 3600.0`; tests/test_output.py:8083-8106 `_run` serialises every child under one flock; QC v13 serialised worst case 5,010 s > 3,600 s | FIX (master direction): one shared child-time budget in `_run`; task.toml unchanged | AL-17 / row NEW (shared deadline; no playbook row names it) | none on every lever: per-child caps, worlds, checks and weights unchanged; the budget binds only above 3,000 s of child time, which no measured program reaches | none | tests/test_output.py |
| TS-23 (warn, acknowledged) | REAL, KEEP | 03_Tests_QC.md:62 "TS-23 Counts and balance: at least 10 checks (fail), at most 35 (warn)" | tests/test_output.py 141 checks, unchanged count; previous KEPT row (v12) | KEEP with the count (no count cap, Ayush 24 Oct 12:50, option A 27 Oct) | TS-23 DO "KEEP as a warn with the count and kit line 03:62: there is no cap" | none | none | none |

## DS-20 evidence

Graphs (all in WORK/p12v13, built by `qc_graph13.py`): QC g2 and g4 rebuilt byte for byte from QC's own generator (seed 11; all seven files equal QC's ds20/g2, ds20/g4); 24 random stress graphs `graphs/s00..s23` (57 to 1,127 schemas, 209 to 5,571 edges, 8 prerequisite fields, cast/rename/add/drop over 10 fields, back edges, has/lacks exits, bypass edges cost 500 or 100000, explicit_null absent, absent_or_null fill and per-field null_counts_as variants, reachable and unreachable starts); 4 adversarial QC-layout graphs `adv/a0..a3` (a dear exit with no prerequisite from every last-layer schema, so every reached state stays live); 8 hard graphs `hard/h00..h07` (1,187 schemas, about 5,930 edges, 79 layers, back edges, dear exits), 8 unreachable twins `u00..u07`, and 16 wide-cost twins `wh00..07`, `wu00..07` (every cost 1 to 1000).

Design tries (Docker, 4 GB, 2 CPUs):
1. Exact goal-state sets per schema plus the existing A*: g2 0.017 s, g4 0.004 s, but adv/a0 ran past 10 minutes (killed). Failed.
2. Exact backward cost-to-go over bit sets of field states, then a forward rebuild of the smallest edge-id list among cheapest plans: every graph exact; the first version took 12.3 s on wh01. Refined in the same design (schema-only forward lower bound as A* order for the backward search, compiled backward edge steps, one AND per settle): this is the shipped planner (WORK/p12v13/repo_try7 = WORK/repo_fixed).

Shipped planner, quiet timings (`p12v13/quick_try7.txt`): g2 0.007 s E_UNREACHABLE (QC: 286 s), g4 0.002 s ['E01257'] (QC: 62-74 s); stress s00..s23 max 0.223 s; adv max 0.209 s; h max 0.29 s; u max 0.458 s; wh max 2.599 s (wh01; others at most 1.657 s); wu max 3.355 s (wu01; others at most 1.571 s). Every graph is inside the K14 10 s promise; 70 of 72 are inside the 2.5 s bar.

Correctness: stress 24 of 24 equal an exact reference (plain uniform-cost search where it finished, else the v12 planner; `cmp7_part1.txt`); the other 38 graphs equal an independent implementation of design 2 without the bound or compilation (`cmp7c.txt`: same 38, diff 0).

Equivalence on every reference call (`p12v13/equiv13.py`, `p12v13/equiv.json`): 2,696 calls = 1,110 from the current tests (worlds 1..106, ladders, plan cases; 120 calls on worlds 47..106), 987 old calls from the frozen g37 tests, and 599 from gate seeds 1001..1300. Old (v12) and new planner plan differences 0; new planner against the test reference 0. Gate worlds max 1.03 s (old 2.26 s); sum over all calls 265.7 s (old 1,059.1 s).

## Deviations from master directions

- DS-20 bar: the 2.5 s bar is met on QC's g2 and g4, the 24-graph stress family and 46 of 48 extra graphs I built; two adversarial wide-cost graphs I built (wh01 2.60 s, wu01 3.36 s, quiet) exceed 2.5 s but stay inside the 10 s K14 promise. Ayush's 00:55 option b (contract wording change) applies only when the oracle cannot keep the 10 s promise; it keeps it on every graph built, so no doc was changed (docs unchanged; no fresh blinds needed for this finding). The fastest result and the graphs that beat 2.5 s are listed above.
- AL-17: the report filed it with TS-11; the live kit's TS-11 (03_Tests_QC.md:41) is determinism, AL-17 (05_Alignment_Integrity_QC.md:74) governs. Fixed as directed.
- No other deviation.

## Touched rules

No test check or judge criterion was added, split, re-worded, re-weighted or deleted. tests/test_output.py differs from the QC copy 68bec9e only in the `_run` helper (child-time budget, shown below); tests/judge.toml and tests/reward.toml are byte-identical. So TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 and JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 carry over from v12/v13 (PASS there). Rows: 0.

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| `_run` (helper, not a check) | budget added | TS-11 determinism, TS-14/TS-16 honest-untrippable, TS-19 caps unchanged | per-child caps unchanged at every caller (test_output.py `_child` callers, CLI 120, unittest 120); budget binds only after 3,000 s of child time; oracle uses 41.5 s (timing/run.log) |

## Vacuity probe

- Tests: no check changed; the nop run (unedited shipped tool and data, no agent edit) is the script run of every positive check: result in Gate results (must be 0.000). The shipped-package forgery (QC cl2/forge.py: shipped repo zipped unchanged plus well-formed claim files) is the stronger probe; its tests share is under Budget arithmetic.
- Judge positives: unchanged from v12; R1-R11 and R19-R21 each need an agent run of the repaired package; R12 (J4) reads /app/out/patched-repo.zip, which nothing ships. Result: PASS (0 points).

## Noise keeps

None. Every cited line changed in 08741c4 (solve.py planner, TRUTH.md, task.toml:22), so no finding is variance.

## QC_RULINGS rows

None: the findings are DS-20, DS-22, AL-17 and TS-23, none of the listed rules (IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7, JD-15).

## Budget arithmetic (AL-17)

The diff of tests/test_output.py against the QC copy 68bec9e is the `_run` hunk only (lines 8083-8116): `_CHILD_SECONDS = {"left": 3000.0}`, one comment line ("All children share these seconds, so the whole verifier ends inside the 3600 s of task.toml."), and inside the existing flock `allowed = min(timeout, left)`, no start once `left <= 0` (raises `subprocess.TimeoutExpired`, the same path a timeout takes today, caught by `_holds` as a failed check), and each child's measured wall time charged in `finally`. Per-child caps, worlds, checks and weights are unchanged; reward.toml and judge.toml are byte-identical.

Measured with the direct runner (WORK/run_checks.py, verifier image, 4 GB and 2 CPUs, tests copy instrumented with an atexit print; WORK/p12v13/timing/):
| run | tests | wall s | child s (3000 - left) | non-child s |
|---|---|---|---|---|
| oracle | 591/591 = 1.0000 | 153.7 | 41.5 | 112.2 |
| shipped, unrepaired package (QC cl2 forgery: shipped repo zipped, well-formed claims) | 6/591 = 0.0102 | 2,172.3 | 2,098.3 (left 901.7, budget did not bind) | 74.0 |

Worst case: every child hitting its cap would need 5,010 s (QC v13.md:298), now cut to at most 3,000 s of child time plus at most one child's kill overshoot (`_stop` + `communicate`, about 1 s), plus non-child work (at most 112.2 s measured), plus rewardkit start and test.sh (a few seconds): 3,000 + 1 + 112.2 + 10 = 3,123 s, under the 3,240 s bar (90% of task.toml:22 3,600 s).

Programs cannot gain: the budget only replaces a child's run with a timeout, and a timed-out check fails, so a score can only stay the same or drop. It binds only when the summed child time passes 3,000 s. The whole verifier time of every kill-table program (HARDEN_REPORT.md:46-58: a5 2,060 s, the slowest blind 2,163 s, exhaustive 2,348 s) is below 3,000 s, so its child time is too and its test points are unchanged. The oracle (41.5 s of child time) and the owner-only run are unaffected. A delivery that hangs now gets a low score instead of no reward.

## Side effects

| FIX id | ids re-checked | result |
|---|---|---|
| DS-20 | FIX_SIDE_EFFECTS.md has no DS-20 row; checked DS-15 (oracle 1.0), DS-22 and AL-18 (TRUTH rewritten by p13_truth.py, sha256 by truth_sha.py, PRECHECK CLEAN), JD-7 (probe lines in solve.py unchanged) | no finding |
| DS-22 | DS-22 / AL-18 (counts, print forms match solve.py:1167 and :1229) | no finding |
| AL-17 / TS-11 | no row; checked TS-11 (the budget binds only above 3,000 s of child time, which no measured program reaches, so repeat runs score the same), TS-14 / TS-16 (honest oracle 1.0, owner-only 1.0), TS-19 (caps and the K14 10 s bound unchanged) | no finding |

Side-effect findings: 0.

## Trap survival

Trap survival = identical plans plus no check removed. The new oracle gives the same plans as the v12 oracle and the test reference on all 2,696 recorded calls: the current tests' 1,110 calls (the 1,109 checked in 08741c4 plus one), the 987 old reference calls of the frozen g37 tests, and 599 calls from gate seeds 1001-1300 (0 differences, WORK/p12v13/equiv.json). tests/test_output.py changes only in the `_run` budget, which no kill-table program reaches. No check, world or hidden input was removed (worlds 47-106 all present, 141 checks).

| lever | before (test points lost by the single wrong-reading variant) | after | ratio | separating kept | verdict |
|---|---|---|---|---|---|
| P-3 GATE (world_47..106) | 300 (every kill-table program, HARDEN_REPORT.md:46-58) | 300 (same checks, same expected plans; budget not binding) | 1.00 | yes, 60 worlds | PASS |
| P-3 CORE (world_29..46) | as HARDEN_REPORT | same | 1.00 | yes | PASS |
| STATE, TIE, SCALE, NULL, POLICY, TOKENS, CORR, REPLAY, FEED, REPORT, CLI, RECEIPT, L2, L5, L6 (LEVERS.md variants) | as measured | same expected outputs, same checks | 1.00 | yes | PASS |

## Gate results

Docker block D=/tmp/smpr-p13-gate-20261030T020745-9710 (copies by live kit exe_copy.py: plain and --owner-only; warm build rc=0 cached; pairs; chain.log ends `ALL_DONE Fri Oct 30 02:27:30 IST 2026`). Tests-only (no judge key).

| run | reward | verifier s |
|---|---|---|
| oracle-1 | 1.0 | 120 |
| oracle-2 | 1.0 | 114 |
| oracle-3 | 1.0 | 101 |
| owner-1 (--owner-only) | 1.0 | 99 |
| nop-1 | 0.0 | 75 |

Timed unrepaired run (direct runner on the fixed tests, p12v13/timing/run.log): shipped package 0.0102 (6/591), wall 2,172 s < 3,240 s, budget left 902 s (not binding). PRECHECK last line: `PRECHECK CLEAN`. xref 50 entries, 0 findings. STACKING PASS (OUT/STACKING_CHECK.md). Docs changed: none (option b not used). Tasks_INPUT synced: bundle tree 6cfdda6f8959 = Tasks_INPUT tree 6cfdda6f8959 (was 589d2aa9c1e0).

## Lessons for the master

- A stated per-call time bound on a state-product search needs an oracle whose work is bounded by states x edges (backward cost search over bit sets of field states), not a pruned forward search with a give-up limit | no change: LEVER_RULES_v3 Always 17 reference <= 1/4 limit already covers it.
- Children serialised under one lock need one shared wall budget, else the worst verifier is the sum of caps | template_change: prompts/templates/_COMMON_RULES_v5.md:58 (add: "when checks share a lock, cap total child time below 90% of the verifier timeout").
- `perl alarm` as container PID 1 never fires; use `docker run --init` | no change: tool habit, noted here.
