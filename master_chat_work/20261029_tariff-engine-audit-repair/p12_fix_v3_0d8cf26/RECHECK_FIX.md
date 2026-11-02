# RECHECK_FIX 0d8cf26 — tariff-engine-audit-repair (QC v3, result_a4ffe55.json)

Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Bundle before = PREV_QC_COPY a4ffe55 (tree 7d8861ab1d7a), so the ql1 kill table (harden_r_ql1/HARDEN_REPORT.md, WORK/KILL_TEST.md:150+) is the trap baseline on the current tests. Phase 0 xref: 78 entries, 0 findings.

Session rename: `name_session.py 0d8cf26` printed `codex: no match` / `opencode: ['ses_e78fad857ffe2j5nC79ZWnWdaZ']`; the list did not show 0d8cf26 by name. Carried on, no retry.

## Findings

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| DS-22 (= AL-18) ❌ | REAL | 02_Data_Solution_QC.md:78 "Read the `Verification` section against the weight registrations ... A TRUTH.md that describes ... grading that does not exist is worse than none ... Fail, and name the section and the contradiction." | before: TRUTH.md:231-236 statements bullet names `_assert_statements` (no such function in tests/test_output.py) and only seed x 53 + 29; batch (x 61 + 37) and cycle (x 67 + 41) streams of `_SCALE_RNG` missing; TRUTH.md:146-147 "three pairs of equal amounts" vs `_scale_once` `range(SCALE_COUNT - 6)` + `amounts += amounts[:6]` (six pairs). Not noise: the tests under the prose changed in the ql1 round (QC v3 changed hunks 7532-7656, 8563-8772). | FIX: TRUTH.md:146-147 "six pairs"; Verification statements bullet rewritten to the shipped code: shipped document (5), three sets statement / batch / cycle from `_scale_texts` over the seven quiet-rule corpora with `_SCALE_RNG` seeds x 53 + 29, x 61 + 37, x 67 + 41, per corpus feasible 3 / due 5 / redeemed 5 = 21 checks, 91 points per set (273 over three; with ledger 364), one `--statements` child per corpus document shared by its three checks, `_scale_once` 36-voucher account with six repeated amounts, `_assert_scale` = `_assert_ledger` + the 36-voucher conditions. Count and sha lines re-derived by script last (G6). WORK DESIGN.md:235 and LEVERS.md:191 "three/3 pairs" -> six. | DS-22 / AL-18 recipe | S1H none, S1T none, all older levers none (prose only) | none | solution/TRUTH.md |
| TS-11 ⚠️ | REAL | 03_Tests_QC.md:41 "... timing margins tight enough to lose on a slow machine ... Name the specific line, not the general worry." | tests/test_output.py:5586-5595 (before) `_memo` = plain dict, no lock; rewardkit 0.2.1 runs checks on 8 threads (QC measured 82 `--statements` children for 28 memo keys); the 10 s bound (STATEMENT_SECONDS, 7147) was therefore met under avoidable self-contention. | FIX: per-key `threading.RLock` in `_memo` (`_MEMO_LOCKS` + `_MEMO_GUARD`, `import threading`); first caller builds, the others wait for the same result. STATEMENT_SECONDS = 10, every check, input and weight unchanged (G7 diff WORK/p12v3/G7_tests.diff: 1 import + 2 globals + lock in `_memo`). Serial behaviour identical by construction. | none specific (TS-11 is a test-hygiene fix; G1-G7 respected) | S1H none (see Trap survival), S1T none, others none | none | tests/test_output.py |
| TS-20 ⚠️ | FALSE_POSITIVE | 03_Tests_QC.md:51 "5 = a core outcome ... 3 = an important sub-goal ... Then check the ORDERING ... Mild imbalance within the right ordering is a minor." | 369/670 on `--statements` = shipped 5 + 4 sets x 7 corpora x 13. Ordering is right: whole-document due/redeemed on hidden inputs w5, feasible w3; invoices keep w5 for whole documents. QC v3:142 "Not an ordering contradiction (instruction ranks nothing)". Weight share is the approved lever cap (Ayush 29 Oct 09:12 "C. Raise the limit for tariff only.: okay", CRASH+TIMEOUT cap 60%; HARDEN_REPORT kill table: agent_program 306/670, all 364 lost on these checks). | KEEP (playbook NEVER "Lowering a lever check to fix the order"; QC's fix "drop batch/cycle or weight 1" cuts 182 lever points) | TS-20 | none (kept) | n/a | none |
| TS-26 ⚠️ | FALSE_POSITIVE | 03_Tests_QC.md:53 "Two tests reading the same observable with the same decisive logic pay ... twice ... What is NOT a duplicate: two tests reading genuinely different aspects of the same object" | batch/cycle read different hidden documents: `_SCALE_RNG` (53,29) / (61,37) / (67,41) -> different 36-voucher accounts and tie positions per corpus; each document's statements are a separate observable (per-set split from the threaded kill run below, Trap survival). QC v3:144 itself: "Different inputs, so not the kit's strict 'same observable' duplicate (03:53)". QC_RULINGS TS-26 cohort v2:183 (fixtures vs hidden_* on different studies PASS), district-heat v3:185 (4 extracts x 4 views PASS). | KEEP (playbook TS-26 NEVER "Deleting the whole-document test on hidden inputs"; not a true duplicate so the merge DO does not apply) | TS-26 | none (kept) | n/a | none |

No ❌/🟡 rows besides DS-22; QL coverage table had no FAIL row (v3:274).

## Noise keeps

None. All four findings sit on lines changed in the ql1 round (QC v3 changed-hunk list, v3:263-266) or on prose that became stale because those lines changed; none is a flip on bytes that passed before.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| TS-11 | tests/test_output.py:16 `import threading`; :5505-5506 `_MEMO_LOCKS` / `_MEMO_GUARD`; :5589-5604 `_memo` builds each key once under a per-key RLock | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4; judge untouched | PASS: no check body, name, input, weight or limit changed (G7 diff = lock only; STATEMENT_SECONDS = 10 at :7159; `_SCALE_RNG` :7548 unchanged; 158 registrations, 670 positive, -8 negative). TS-13/TS-14/TS-25 read the same single fields as before (QC v3:141,146 ✅). TS-20/TS-26 weights unchanged (kept rows above). CL-2 forgery and CL-4 variant scores unchanged by construction (memo results identical; serial path identical); threaded kill numbers in Trap survival. Judge (tests/judge.toml, 16 criteria) not touched. |
| DS-22 / AL-18 | solution/TRUTH.md:146-147 "six pairs"; :231-245 Verification statements bullet rewritten | DS-22, AL-18, AL-19, DS-21, TS-20, TS-26 (TRUTH numbers vs registrations) | PASS: TRUTH.md:232-233 names `_scale_texts`, `_SCALE_RNG` x 53 + 29 / x 61 + 37 / x 67 + 41 = tests :7548; :239 "six amounts drawn twice" = `_scale_once` `range(SCALE_COUNT - 6)` + `amounts += amounts[:6]`; :240 `_assert_scale` exists in tests; 21 checks / 91 points per set = registration script. :188 and :352-353 counts (156 / 670 / -8; judge 16 / 42 / -10) re-derived by script, unchanged; :341-342 sha lines rewritten by WORK/ql1/truth_sha.py (values unchanged, solve files untouched). |

## Side effects

| FIX id | ids re-checked (FIX_SIDE_EFFECTS + own) | result |
|---|---|---|
| DS-22 | DS-22, AL-18, AL-19, DS-21, JD-7 | CLEAN: no other `_assert_statements` / "three pairs" text in bundle (grep); precheck DS-22 cite stage CLEAN; DS-21 = KEPT F08 unchanged; JD-7 judge criteria untouched. |
| TS-11 | TS-11, TS-13, TS-14, TS-15, TS-17, TS-23, TS-24, TS-25, TS-26 | CLEAN: no generator regen, G7 diff lock-only; check names / weights / count 158 unchanged (TS-23 = KEPT F09); `__pycache__` removed from bundle after compile (0 left). |

Side-effect findings: 0.

## QC_RULINGS rows

- IN-15 | rule: judge criteria must not re-grade instruction-following beyond one criterion | our design: R8 only instruction-following (instruction.md:15), R14-R16 conduct | QC verdict ✅ (v3:106) | label: n/a (pass) | reason: no finding.
- IN-16 | rule: graded tie rule must be stated with example | our design: api_contract.md:223-225 rule, :228-231 example | QC ✅ (v3:107) | n/a | no finding.
- TS-13 | rule: one check reads one observable | our design: feasible / due / redeemed each one field | QC ✅ (v3:141) | n/a | unchanged by lock fix.
- TS-19 | rule: every graded rule quoted in docs | our design: api_contract.md:21-28, 211-231 | QC PASS (v3:193) | n/a | unchanged.
- TS-20 | rule: 03_Tests_QC.md:51 ordering | our design: 369/670 on `--statements` = approved lever cap | QC ⚠️ (v3:142) | FALSE_POSITIVE | ordering right, QC itself "not an ordering contradiction"; playbook NEVER lowering lever checks.
- TS-26 | rule: 03_Tests_QC.md:53 same observable | our design: statement/batch/cycle are three seeded hidden documents | QC ⚠️ (v3:144) | FALSE_POSITIVE | QC itself "different inputs, so not the kit's strict duplicate"; QC_RULINGS cohort v2:183, district-heat v3:185 PASS.
- AL-28 | rule: negatives must not stack above 5 | our design: -5 hardcoding, -3 visible test removed, judge R9 -5, R10 -5 | QC ✅ (v3:183) | n/a | unchanged.
- JD-7 | rule: oracle must earn every judge criterion | our design: solve.py:1049-1077 | QC ✅ (v3:157) | n/a | solve untouched.
- JD-15 | rule: conduct criteria are conduct only | our design: R14-R16 | QC ✅ (v3:162) | n/a | judge untouched.

## Gate results
- xref after all edits: `xref_check: 78 entries, 0 findings`.
- precheck: last line `PRECHECK CLEAN` (only WARN A3 158 checks = KEPT F09).
- stacking_check.py: STACKING PASS (OUT/STACKING_CHECK.md; tests weights and judge unchanged).
- TS-11 measurement (Docker `--cpus 2 --memory 4g`, 8 threads like rewardkit, WORK/p12v3/checks_threads.py): before fix, oracle: 83 `--statements`/`--ledger` children for 29 memo keys, slowest 1.79 s, 670/670. After fix, oracle: 29 children for 29 keys, slowest 1.25 s, 670/670. Every after-fix kill run: children == keys (29/29).
- Harbor gates (copies from live kit exe_copy.py, R=/tmp/opencode-logs/tariff-0d8cf26-20261029T151732-c7ef/jobs): oracle x3 = 1.0 / 1.0 / 1.0 (plain__vwQbTos, plain__njiCky2, plain__SNfoR4o); owner-only x1 = 1.0 (owner__jMouY47); nop x1 = 0.0 (plain__i5tT3X8). chain3.log ends `ALL_DONE Thu Oct 29 16:34:35 IST 2026`.
- TRUTH.md golden_score_trial_id -> plain__vwQbTos; sha lines regenerated last by WORK/ql1/truth_sha.py (values unchanged: solve.sh / solve.py untouched).

## Trap survival
Before = ql1 serial kill table (tree 7d8861ab1d7a = tests before this fix). After = fixed tests, 8 threads, Docker 4g/2cpu. Loss is the number of points lost out of 670.

| lever / solver | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| agent_program (harden_r_ql1) | 364 | 364 (39T 325C) | 1.00 | y | PASS, 306/670 = 45.67, no gain |
| bitset | 364 | 364 (26T 338C; serial cross-check 13T 351C) | 1.00 | y | PASS |
| gcd_split | 273 | 273 (ledger set 0, other three 91 each) | 1.00 | y | PASS |
| mitm_only | 364 | 364 (364T) | 1.00 | y | PASS |
| tie_naive | 145 | 145 (145W) | 1.00 | y | PASS |
| greedy | 285 | 285 (285W) | 1.00 | y | PASS |
| mitm_dedupe | 364 | 364 (364T) | 1.00 | y | PASS |
| branch_bound | 364 | 364 (364T) | 1.00 | y | PASS |
| first_write | 482 | 482 (statement 78, batch 91, cycle 78, ledger 91) | 1.00 | y | PASS |
| first_write+bitset | 508 | 508 | 1.00 | y | PASS |
| blind_r3 | 364 | 364 (13T 351C) | 1.00 | y | PASS |
| combined (control) | 0 | 0 | n/a | n/a | full marks kept |

Every score matches the ql1 table. Only the WRONG/TIMEOUT/CRASH mix moved, and every lever check still fails. TS-26 per-set evidence: first_write loses 91 on batch but 78 on statement and cycle, so batch catches corpora the others miss. gcd_split loses 0 on ledger but 91 on each scale set. One k2 attempt was lost when 8 bitset children ran out of memory and the cgroup OOM killer ended the checker. It did not happen again on rerun (k2a / k2b / k2c above), and the QL run_1 verifier with a bitset agent survived (TRIP.md).

## Vacuity probe
WORK/vacuity_p12.py in Docker against the fixed tests ($R/vacuity.json). With nothing built, 0 of 670 positive points pass. With the unedited shipped tool, 7 of 670 pass, from 5 non-lever checks: archive_follows_build_config, summary_lists_inputs_and_artifacts, repair_report_has_stated_shape, previously_failing_matches_log, two_runs_are_identical. No `--statements` or ledger check passes on the unedited tool. Judge criteria were not changed (judge.toml has 16 criteria). PASS.

## Lessons for the master
- An unlocked memo dict under rewardkit's 8-thread pool starts duplicate children (83 for 29 keys). A per-key RLock keeps serial results identical, so serial kill tables still apply | template_change: no change: LEVER_RULES_v3 G12 already names thread-unsafe test caches. Check for G12 at harden time.
- Running threaded kill runs of a memory-heavy solver (bitset) can OOM-kill the checker itself inside a 4g container. Rerun before reading the result as a lever loss | no change: one-off, noted in the report.
- Chain logs must end with a unique `ALL_DONE <date>` line, because inner scripts also print a bare ALL_DONE | no change: the round notes already say to trust the final dated line.
