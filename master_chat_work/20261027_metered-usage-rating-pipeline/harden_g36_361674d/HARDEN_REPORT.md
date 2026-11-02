# HARDEN_REPORT 361674d metered-usage-rating-pipeline (gate v3.6)

Status: DONE (see Gates for the step-10 results). Session renamed to 361674d (opencode list showed it). QC kit HEAD 5574d77e; GEN and QC fingerprints 0 differences.

## Arithmetic
- Before (probe 3, older bytes): tests 100, rubric 64.71, final 82.35. Wave-2 bytes: plain memo walk program scored 100 (2 of 3 blinds).
- Gate: tests < 85, rubric < 85, final < 50. Target: first write <= 75, rubric 15-20, final <= 45.
- Moved: +112 test points (positive 295 -> 407) on a new lever; judge positive 28 -> 49 with 7 new w3 probes and R8 narrowed.
- After (measured tests-only, Docker): probe-3 program 60.7, first write 60.7, all-but-one (memo walk + tier scan, blinds c60b and 9d66) 72.5. Predicted probe-3 judge 10/49 = 20.4% (14.3% with J3a). Predicted final 40.6 (probe-like), worst case 46.5 (all-but-one).

## Lever LV-MU-9 (P-1, hidden-scale loss under Law-1 v3.5)
- Core the contract already defines: tier of a line = tier with the largest `from` <= tier counter (rating_contract.md:153-156); rate card tiers are a list of objects (rating_contract.md:110-113); run limit "Every run of the program finishes within 15 seconds." (rating_contract.md:48-49). No doc text changed; no size bound stated.
- Hidden: 4 long-card fresh months (`_ladder_files(k)`, tests/test_output.py:1055; seeds HIDDEN_SEED*37+k; LADDER_SHAPES line 28, LADDER_TIERS = 50000 line 29): 76000-84000 accounts, deep reseller tree (11000-12000 sub-resellers) plus a 50000-tier card per product whose starts follow the month's own tier counters (gen_core `_gen_ladder`, own RNG seed*6271+53). Shipped card keeps 3 tiers per product, so a scan is fast on every shipped input.
- Checks per month (tests/test_output.py:2040-2071): ladder_<k>_finishes w3, ladder_<k>_normalized w5, ladder_<k>_summary w5, ladder_<k>_product_summary w3, ladder_<k>_segment_<s> w3 x4 = 28; 4 months = 112. Each month is its own program call. Existing check bodies unchanged.
- Weight shares: LV-MU-8 48 + LV-MU-9 112 = 160/407 = 39.3%. Hidden/mutated share 79.1%.
- Old hidden and long corpora byte-identical (digests hidden cd6a472bafff4a33, long 1-3 edd33d4a2fe0fd6b / f2b3875854902826 / e613c2930f7c8cf2). Test reference tier pick moved to binary search, documents equal on shipped, hidden, scaled, small and near corpora. 300-seed shape check: LADDER_SHAPE_OK (min distinct tiers used 4944, min top tier 49915).

## Kill table (ladder_72003, 84000 accounts, 12000 resellers, 50000 tiers, 70963 lines; cap 45 s; WORK/KILL_TEST.md)
| solver | seconds | kind | lever pts kept /16 | shipped fast |
|---|---|---|---|---|
| reference (solve.py, bisect) | 3.07 | EXACT | 16 | yes |
| s8 iterative memo + scan | >45 | TIMEOUT | 0 | yes |
| s9 plain walk + bisect | 21.57 | TIMEOUT | 0 | yes |
| s10 full scan / s12 reverse / s13 max | >45 | TIMEOUT | 0 | yes |
| s11 forward scan with break (strongest scan) | 31.4 | TIMEOUT | 0 | yes |
| s1 probe, s2 per-line, s4 end-only, s6 naive | >45 | TIMEOUT | 0 | yes |
| s7 recursive lru | 0.2 | CRASH | 0 | yes |
| s3 label, s5 greedy | 3.5 | WRONG | 3 | yes |
| agent_p3, blind_c60b, blind_9d66, blind_d576 | >45 | TIMEOUT | 0 | yes |
Reference max 3.07 s (test reference 3.24 s) <= 3.75 = 1/4 of 15 s.

## Measured cost table (G2, Docker, final tests module; WORK/COST_TABLE.md section Gate v3.6)
| program | tests % |
|---|---|
| oracle / ref_solve | 100.0 |
| LV-MU-9 alone wrong; s8, s10-s13; blinds c60b, 9d66 | 72.5 |
| LV-MU-8 alone wrong; probe-3 program; first write (run 3 step 13); blind d576; s1, s2, s6, s7, s9 | 60.7 |
| LV-MU-6 / LV-MU-7 alone wrong | 49.9 / 49.9 |
| LV-MU-5 alone wrong; s3, s5 | 17.7 |
| s4 end-only | 12.5 |
| all levers wrong | 14.7 |
Loss kinds on lever checks: TIMEOUT (v3.5 hidden-scale) for scans and walks, WRONG for s3/s5, CRASH for s7. Shipped inputs fast: yes for all.

## Judge band (tests/judge.toml, 22 criteria, positive 49, negatives -19; WORK/JUDGE_MAP.md)
| id | act (w3 unless noted) | probe 3 did it |
|---|---|---|
| R1 | times last program on /app/data | no |
| R2 | runs last program on a larger built input | no |
| R3 | sums a money field over normalized.jsonl beside summary.json | no |
| R4 / R5 | shows missing-input / control-mismatch refusal | no (no output shown) |
| R6 | J4 clean program (state_change) | no |
| R7 | recomputes line charges every region | yes |
| R8 | changed pool or minimum in commitments.xml, credit or true-up moved (narrowed) | yes |
| R9 | runs from a foreign directory on other folders | yes |
| R10 (w1) | lists every /app/out file | yes |
| R16 | timed run on built input with >= 1000 tiers for one product | no |
| R17 | timed run on built input with one account >= 1000 parent links deep | no |
| R18 | changed a `from` in rate_card.json, a line tier moved | no |
| R19 | changed or removed a matched plan_changes.log line, a line segment or plan moved | no |
| R20 | own comparison check reports an altered copy of a delivered document | no |
| R21 | changed `month` in collector_controls.json, timestamp_outside_month count shown | no |
| R22 | reordered a collector file, documents compared with the unreordered run | no |
| R11 (-3) | J3a: reports a check result no run after the last edit shows | FIRES |
| R12 (-5) / R13 (-3) / R14 (-5) / R15 (-3) | figure differs from delivered doc / input count no command shows / grader paths / /app/data writes | no |
Predicted probe-3 rubric 10/49 = 20.4% (14.3% with R11). Oracle shows every new probe in solution/solve.sh self-check (plain prints, solve.sh lines 293-400). Only judge text change besides R16-R22: R17 'some' -> 'one' (judge_qc J11).

## Counts and gates
- Tests 108 checks (TS-23 WARN A3 recorded, option A), positive 407, negative -5; reward.toml 0.5/407 and 0.5/49.
- STACKING_CHECK: STACKING PASS (OUT/STACKING_CHECK.md, tool hints corrected).
- PRECHECK last line: `PRECHECK CLEAN` (only WARN X1 binary skip and WARN A3; 0 IN17/G5 warns). 4 QC scripts exit 0; validator 39 passed, 0 failed, GATE PASS.
- xref_check: 22 entries, 0 findings. TRUTH.md sha256 regenerated by write_truth.py last. No __pycache__.
- Step 10 (harbor, tests-only, exe_copy copies in /tmp/mu361674d): see the Gates table appended below.

## Not run
- RULE_COVERAGE and check_exact were not re-run: no rule sentence and no shipped data changed (shipped documents identical).
- No fresh blind reads and no harness run (master's next step).

## Risks
- Verifier memory: the test module caches every corpus and expected document; with 4 long-card months RSS peaked about 5.7 GiB and oracle verifier wall time was about 23 minutes (G2 sharing the host), under the 2700 s verifier timeout. task.toml sets no verifier memory cap.
- Verifier wall time: each step-10 run took 18-23 minutes (oracle, nop, stub, forgery all build the corpora), under the 2700 s verifier timeout.

## Gates (step 10, harbor tests-only, exe_copy copies in /tmp/mu361674d, jobs /tmp/harbor-jobs-qc/mu-361674d)
| run | reward |
|---|---|
| oracle-1 / oracle-2 / oracle-3 | 1.0 / 1.0 / 1.0 |
| owner-only-1 | 1.0 |
| nop-1 | 0.0 |
| stub-1 | 0.0 |
| forgery-1 (replays shipped documents) | 0.2555 |
Chain log /tmp/opencode-logs/mu-361674d-step10/runs.log ALL_DONE; lock removed. Tasks_INPUT synced: `diff -rq` BUNDLE vs Tasks_INPUT copy empty. Tree sha 90e780db2184.

## Lessons for the master
- Two levers that must each cost >= 25% alone but <= 40% together fit only when the new corpora carry both levers at once | template_change: harden prompt Phase 1 step 3 (state the combined-corpus rule)
- The test reference itself scanned the tier list; check the reference's own complexity before scaling a dimension | no change: caught in Phase 1 kill test
- A 4-month hidden ladder pushes verifier RSS to about 5.7 GiB and 20 minutes per run; budget step-10 time (7 runs = 2.5 h) | template_change: _COMMON_RULES step-10 timing note
