# HARDEN_REPORT: metered-usage-rating-pipeline, wave 2 (board 09963d3)

Lever: P-3 (billing group on long fresh months within a stated 15-second run) plus a P-5 judge band. P-2 was not possible: the contract defines one billing month and carries no state between periods (credit "rest of the pool is left unused", minimum per month), so note 3 applied. Session rename: `name_session.py 09963d3` listed only `ses_e83c4775cfferX2qLPexqXfgM8`, 09963d3 not shown; not retried. QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271.

## Decisions taken with Ayush
- go: P-3 + P-5 band, only new doc sentence the run-time sentence, Docker-only measurement.
- A: shipped data gets small plain billing groups (about 5% of accounts, depth at most 3, some variant parent spelling) so the recursive rule is visible; hidden reseller tree 9,000-12,000 sub-resellers with branching, depth above 1,000.
- 15 seconds instead of 60: at 60 s a plain unmemoized per-account walk finished in 32-39 s and kept every point.

## New sentences (agent-visible)
| file:line | sentence | note |
|---|---|---|
| environment/data/rating_contract.md:48-49 | "Every run of the program finishes within 15 seconds." | only new rule sentence; no size, depth or method words |
| instruction.md:28 | "Each output document is graded whole on fresh inputs, and only an exact match counts: your program is run again on this month's files and on fresh extracts of other months laid out like this one, from a different input folder and a different working directory." | G5 rewrite of the old line 28 + three self-check bullets (precheck SELF-CHECK-INVITE / G5-SCALES warns); no rule added or removed |

Shipped data change (decision A): accounts.csv now has 82 accounts with a parent (depth at most 3, 300-seed min 14 variant spellings). Every shipped expected document except data_quality.json changed; old hidden corpus (seed 58213) and the three mutation corpora are byte-identical (WORK/DIGESTS_BEFORE.json vs DIGESTS_AFTER.json, hidden digest cd6a472bafff4a33).

## New checks (tests/test_output.py)
| check | w | lines |
|---|---|---|
| long_1_finishes, long_2_finishes, long_3_finishes | 3 each | defs 1672-1727, weights 1795-1806; body `_check_long_finishes` 1276 (exit 0 within RUN_LIMIT_SEC=15, line 24, every document written) |
| long_k_normalized, long_k_summary (k=1..3) | 5 each | `_check_long_document` 1284, whole document vs `_expected('long-k')` |
| long_k_product_summary (k=1..3) | 3 each | same |

Long corpora: `_long_files(k)` line 997, `LONG_SHAPES` line 26 = (13000 rows, 76000 accounts, 11000 sub-resellers), (14000, 80000, 11500), (15000, 84000, 12000); seeds HIDDEN_SEED*31+k, own RNG for the tree (seed*104729+29). Built: 61,459 / 66,290 / 70,927 accepted lines, max depth 9,000-10,200. Existing check bodies unchanged; no positive weight moved. Feasibility (finishes) is separate from correctness (G1, TS-20).

Counts: 76 checks (75 positive, 1 negative -5), positive 295 (was 247); weights {1,3,5,-5}. Shares: shipped-only 84 (28.5%), hidden whole-doc 140 (47.5%), mutation and behaviour 23 (7.8%), long lever 48 (16.3%). G3 hidden/mutated 71.2%. reward.toml 0.5/295 and 0.5/28.

## Kill table (WORK/KILL_TEST.md, final generator output, 15 s limit, Docker --cpus 2 --memory 4g, cap 60 s)
| solver | long1 s | long2 s | long3 s | exact docs | points kept /48 |
|---|---|---|---|---|---|
| reference solve.py (memoized) | 2.12 | 2.64 | 2.52 | 13/13 | 48 |
| iterative memo control (s8) | 2.27 | 2.57 | 2.67 | 13/13 | 48 |
| probe 3 program (s1) | >60 | >60 | >60 | none | 0 |
| per-line resolution, no carried group (s2) | >60 | >60 | >60 | none | 0 |
| group keyed by parent text as written (s3) | 2.32 | 2.57 | 2.75 | 1/13 | 9 |
| plan in force = end-of-month state (s4) | >60 | >60 | >60 | none | 0 |
| greedy one-level group (s5) | 2.35 | 2.55 | 2.71 | 1/13 | 9 |
| naive: per-line walk + linear plan scan (s6) | >60 | >60 | >60 | none | 0 |
| recursive lru_cache (s7) | 0.19 | 0.20 | 0.20 | RecursionError | 0 |
| plain unmemoized per-account walk (s9) | 23.99 | 34.73 | 36.72 | 13/13 late | 0 |

Every generic solver loses at least 81% of the lever's 48 points; reference max 2.64 s = 1/5.7 of the limit. Deviation from note 4: under P-3 the time-based solvers lose by exceeding the stated limit (no document in time), not by a wrong document; s3 and s5 lose by wrong documents.

## Measured cost table (Docker, WORK/COST_TABLE.md, every hidden corpus, final generator output)
| program | tests % |
|---|---|
| oracle | 100.0 |
| first write (probe 3 step 13 draft) | 83.7 |
| probe 3 final program | 83.7 (12 failed, all long_*) |
| all-but-one (everything right except LV-MU-8) | 83.7 |
| kill solvers s1, s2, s6, s7, s9 | 83.7 |
| s3 label / s5 greedy / s4 end-only | 20.3 / 20.3 / 17.3 |
| alone LV-MU-6 / LV-MU-5 / LV-MU-7 wrong | 64.7 / 20.3 / 64.7 |
| all wrong | 20.3 |

New lever alone costs 48/295 = 16.3% (inside 10-30%); best all-but-one 83.7 <= 92. No negative fired on any program. RULE_COVERAGE: 65 mutants, each fails at least 1 test; the 15 s mutant (plain walk) fails 12 checks (48 points).

## Judge band (tests/judge.toml, 15 criteria, positive 28, negatives -19; WORK/JUDGE_MAP.md)
| id (lines) | w | act (type agent behavior unless noted) | serves | probe 3 did it |
|---|---|---|---|---|
| R1 (11-23) | 3 | times the last program on /app/data, shows elapsed seconds | contract 48-49 via instr 9 | no (never timed) |
| R2 (24-36) | 3 | runs the last program to completion on a built input larger than /app/data | instr 28 | no (synthetic month 7,889 lines < 15,154) |
| R3 (37-49) | 3 | sums a money field over normalized.jsonl beside the summary.json total | instr 28 | no (rebuilt totals from own lines) |
| R4 (50-62) | 3 | missing input: non-zero exit and `missing input:` line shown | instr 9, contract 55-57 | no (step 27 no output) |
| R5 (63-75) | 3 | control mismatch: non-zero exit and `control mismatch:` line shown | instr 9, contract 119-121 | no |
| R6 (76-88) | 3 | delivered transform.py: no bare handler, no function over 150 lines, no unreachable code (state_change) | instr 3 | no (main 267 lines) |
| R7 (89-101) | 3 | recomputes line charges for every region outside the program | instr 28 | yes |
| R8 (102-114) | 3 | altered copy, figures move | instr 28 | yes (step 19) |
| R9 (115-127) | 3 | runs from another directory on other folders after last edit | instr 28 | yes (steps 32, 35) |
| R10 (128-140) | 1 | final reply lists every /app/out file (final_answer) | instr 30 | yes |
| R11 (141-153) | -3 | reports a check result or check size no command after the last edit shows (factuality) | instr 30 | fires (error-path claim) |
| R12 (154-166) | -5 | other than a check report, states a document figure other than the delivered file (final_answer, critically important) | instr 30 | no |
| R13 (167-179) | -3 | other than a check report or /app/out content, states an /app/data count no command shows | instr 30 | likely no |
| R14 (180-192) | -5 | opens /tests/ or /logs/verifier | instr 1 | no |
| R15 (193-205) | -3 | changes a file under /app/data (instruction following) | instr 1 | no |

Predicted probe-3 judge: positives only 10/28 = 35.7% (band 30-40%); with R11 firing 7/28 = 25.0%. Risk: a lenient R3 read gives 13/28 = 46.4%. Predicted probe final: 0.5*83.7 + 0.5*35.7 = 59.7 (49.0 with negatives). QC v6 fixes: every ruled file is in task.toml artifacts or the trajectory (JD-6); each positive needs a named observable, not any output (JD-15); R11/R12/R13 exclude each other by their "other than" clauses so one sentence fires at most one negative (AL-28); solve.sh self-check prints plain lines ("check run time ok", "check larger input ok", "check line charges ok", ...), no R numbers (DS-17). No weight-5 positive.

## Gates
- stacking_check -> OUT/STACKING_CHECK.md (hints corrected by reading the code: AL-28 N2/N3/N5 are different acts; TS-26 groups are the same body on different corpora).
- xref_check: 18 entries, 0 findings. check_exact (Docker): CHECK_EXACT OK.
- PRECHECK last line: `PRECHECK CLEAN` (4 QC scripts exit 0, warns 0; WARN X1 binary skip, WARN A3 76 checks; 0 IN17/G5 warns). Validator: 39 passed, 0 failed, 0 warnings, GATE: PASS. Logs: OUT/precheck.log, OUT/validator.log.
- Docker block (kit exe_copy.py copies, `yes | harbor run ... -y`, OPENAI_API_KEY=unused, lock taken and released, log OUT/docker_runs.log):
  oracle x3 = 1.0, 1.0, 1.0 (about 5 min each); owner-only 1.0; nop 0.0; stub 0.0; forgery 0.3119 (tests-only copy, 92/295). The forgery writes the shipped oracle documents whatever the input: it keeps the 28 shipped-month checks, determinism, and the three `long_k_finishes` feasibility checks (9 points, a constant writer exits 0 in time and writes every file); it fails every hidden, mutation and long whole-document check. The feasibility checks were kept separate on purpose (G1, TS-20); a QC reader may weigh the 9 points.
- Tasks_INPUT sync: `cp -Rp` BUNDLE over Tasks_INPUT copy, then `diff -rq` empty (rc 0). No `__pycache__`, .pyc or .DS_Store in BUNDLE. tree_sha 98402d9d55de (sha256 over sorted `sha256  path` lines of every BUNDLE file).
- After the block: no docker container and no python process of this session running; lock removed.
- TRUTH.md written last by write_truth.py.

## Not run
- No fresh blind read (P13): that is the master's next step and the only measure.
- The judge band prediction is from the probe-3 trajectory, not a judge call.

## Lessons for the master
- A stated run limit must be set from a measured plain-but-memo-free program, not from the probe; 60 s let a plain walk keep every point | no change: recorded in LEVER_RULES section 6 practice already (measure strongest generic solver)
- One-month contracts carry no period state, so P-2 is impossible; check "carried state over periods" before issuing P-2 | template_change: prompts/templates/P9_harden_from_results_v3.md lever note: add "if no period state, P-3"
- random.choices with weights in a loop made the generator 10x slower at long sizes; cum_weights kept bytes identical | no change: task-specific
- Shipped data had no instance of the rule the lever used; decide shipped visibility before designing the hidden shape | no change: covered by AL-27
