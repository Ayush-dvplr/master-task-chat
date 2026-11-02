Replay prediction 19.44 (tests 10.94, judge 27.94), below 35; gate v3.7 held.

# P12 fix v5 (dbe00fc): b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042

QC report: QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v5.md (FAIL 1 fail / 1 minor / 0 warn, 6 acknowledged). Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Session renamed dbe00fc (name_session listed `opencode: ['ses_e6f228511ffetLCTICm1CysRxu']`). Backup: WORK/qc5_7e457f09086a/ (tree 7e457f09086a). Noise diff: BUNDLE == QC/copies/94a3e0a copy (`diff -rq` empty), but the settlement rule was first graded in fix 841c07e, so the v4 round never passed AL-27 for it: no NOISE label applies.

## Findings

| ID | label | rule quote (kit file:line) | evidence (file:line) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| AL-27 (G05-1) | REAL | 05_Alignment_Integrity_QC.md:38 "For every other rule, ask \"which graded input would come out differently if the solver broke exactly this rule?\" - no such input means the rule is ungraded regardless of what the test is called. Fail; name the rule and the missing fixture." (ID and wording unchanged) | environment/data/alae_rules.md:3 and discounting_rules.md:3 settle the readings from the two logs; tests/test_output.py:630 grades `settlement`; WORK/runs/seal_v3/seal_{shipped,A,B}.json all give `{'alae_convention': 'pro_rata', 'discount_curve': 'duration_matched'}`; sha1 of treasury_curve_observations.log e2853040b796 and curve_marks.csv 545fc8542bee identical in shipped/A/B, B claim_adjustment_log.log b6b23a335fcc = shipped | FIX (gen_extracts.py v5: extract A's claim_adjustment_log.log zeroes alae on every `layer=retention` line and pins an explicit `layer=retention alae=0` line for each unlogged shared-event claim, so it settles `excess_only` only; extract B's treasury_curve_observations.log carries pv_factor=(1+curve[10]/100)^-tenor, so it settles `flat_10y` only; shipped corpus bytes unchanged; unique fit by WORK/unique_fit.py (runs/unique_fit_v6/out.jsonl); solve.py settle_alae_convention returns fraction None under excess_only and build_ledger defaults unlogged ALAE to 0 when no fraction; `_EXPECTED_BLOB` and A/B blobs re-sealed (runs/seal_v5, G7_v6_tests_diff.txt hunks 23c23, 26,27c26,27 only). Bite: hard-coded pro_rata 49/64 (loses hidden_extract_outcomes_exact 3, methodology_audit_remaining_sections_exact 3, program_reproduces_unseen_extract_alpha 5, row_order_permutation_changes_nothing 3, summary_and_treaty_values_exact 1 = 15); hard-coded duration_matched 61/64 (loses methodology_audit_remaining_sections_exact 3)) | AL-27 DO (hidden reseeded fixture inside stated bounds) | L1 harder (loss 39 -> 42); L2-L7 none (21, 41, 45, 19, 22, 0 unchanged) | none needed | tests/test_output.py (blobs only), solution/solve.py, solution/TRUTH.md (by script); WORK gen_extracts.py, unique_fit.py, RULE_COVERAGE.md, QC_DEFENCE.md D14/D15, LEVERS.md |
| JD-5 (G04-1) | REAL (minor) | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour ... Clearly compound criteria are a fail; a borderline case (two facets of one act) is a minor." (ID and wording unchanged) | tests/judge.toml:326 R25 "the same `settlement.alae_convention` and `settlement.discount_curve` strings"; :443 R34 "names `claim_adjustment_log.log` as the log that settled the ALAE convention and `treasury_curve_observations.log` as the log that settled the discount curve" | FIX (R25 now the `settlement.alae_convention` string only, new R36 the `settlement.discount_curve` string; R34 now `claim_adjustment_log.log` only, new R37 `treasury_curve_observations.log`; all weight 1, important, user_facing_message; judge positive 66 -> 68; reward.toml judge 0.007575757575757576 -> 0.007352941176470588 = 0.5/68) | JD-5 DO (split, one act each, own label, same family) | none on L1-L7 (judge only, no lever is judged by these criteria) | none needed | tests/judge.toml, tests/reward.toml |
| JD-S12 / judge_qc G3 (new, side effect of the JD-5 split) | REAL (warn, count only) | 04_Judge_QC.md:116 "The file has at least 8 criteria (more than 35 is a warn)" | judge_qc.py on BUNDLE: "WARN [G3] 37 criteria; cap is 35 (warn)" (35 -> 37 because R25 and R34 were split into R25/R36 and R34/R37) | KEEP with the count (Ayush 24 Oct 12:50 / option A 27 Oct: no count cap, never merge or drop a criterion to get under 35; merge only true duplicates, none exist) | TS-23 / TS-26 (count warn = KEEP) | none | none | none |

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| R25 | re-worded (ALAE string only) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS. tests/judge.toml:326 one act (states one string); no banned token (judge_qc J-checks pass); decidable from the final message and methodology_audit.json; oracle writes `settlement.alae_convention` (solve.py methodology dict) and the instruction asks the recap to name each settled reading (instruction.md:9 "name the observation log that settled each methodology reading reported under `methodology_audit.settlement`"); important at weight 1 (JD-13 pass); outcome criterion traced to instruction.md:9; positive, no penalty stacking |
| R34 | re-worded (ALAE log only) | same | PASS. tests/judge.toml:443 one act; promised at instruction.md:9; important w1; no overlap with R16 (:207, reads three log lines in the trajectory) or R28 (:363, -5 contradicted convention) |
| R36 | added (curve string, split from R25) | same + NEW-CHECK hygiene | PASS. tests/judge.toml:469; one act; positive grammar; w1 important; distinct claim from R25 (JD-14 / AL-28: no claim paid twice) |
| R37 | added (curve log, split from R34) | same + NEW-CHECK hygiene | PASS. tests/judge.toml:482; one act; promised at instruction.md:9; w1 important; distinct from R17 (:220 trajectory read) and R29 (:376 -5) |
| reward.toml judge | re-weighted 0.007575757575757576 -> 0.007352941176470588 | R3 channel weight = 0.5 / positive total | PASS. tests_qc.py "pass [R3] channel weights equal 0.5 / positive total"; judge_qc "pass [G6] positive total 68, negative total 25" |
| test checks | none added, split, re-worded or re-weighted (only the sealed blobs at test_output.py:23, 26, 27 changed) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS. tests_qc.py VERDICT PASS (37 pass); weights unchanged (positive 64, negative 23); methodology_audit_remaining_sections_exact (test_output.py:618-637) still one property (audit sections exact) and now bites on A and B |

## Vacuity probe

- Tests: the unedited shipped environment with an empty /app/out graded by WORK/harness/grade.py (runs/vacuity_v6/grade.json): earned 0/64, no negative fired.
- Judge: an agent that changes nothing writes no /app/out/methodology_audit.json and no recap, so R25, R34, R36 and R37 (and every other positive, which all require a written artifact, a log read or a recap) read "no" for it: 0/68.
- Result: PASS.

## Side effects

| FIX id | ids re-checked (FIX_SIDE_EFFECTS.md) | result |
|---|---|---|
| JD-5 | JD-2, JD-7, JD-9, JD-15, IN-8 (FIX_SIDE_EFFECTS.md:8) | JD-2 PASS (judge_qc banned-token checks pass); JD-7 PASS (oracle writes both settlement strings; recap promise instruction.md:9); JD-9 unchanged balance, the split adds two outcome criteria to the message family, process criteria R16-R18 untouched; JD-15 PASS (outcome criteria traced to instruction.md:9); IN-8 PASS (strings and log names are in the shipped docs alae_rules.md:3, discounting_rules.md:3). New finding: judge_qc G3 warn 37 > 35, KEPT with count (row above) |
| AL-27 | TS-13 (FIX_SIDE_EFFECTS.md:19) | PASS: no test check added or merged; the audit check still asserts one property. TS-16: the oracle passes every check on the new fixtures (runs/trap_v6_after oracle 64/64) |

## Trap survival

Single-lever variants (WORK/harness/variants.py) on the BEFORE tests (runs/trap_v4_after, P 64) and the fixed tests (runs/trap_v6_after, P 64). Oracle 64/64 on both.

| lever | loss before | loss after | kept | separating checks removed | verdict |
|---|---|---|---|---|---|
| L1 paid_to_date column 7 | 39 | 42 | 108% | none (adds hidden_extract_outcomes_exact) | PASS |
| L2 individual retention | 21 | 21 | 100% | none | PASS |
| L3 no admission bar | 41 | 41 | 100% | none | PASS |
| L4 single precedence | 45 | 45 | 100% | none | PASS |
| L5 no epoch split | 19 | 19 | 100% | none | PASS |
| L6 unclipped factor | 22 | 22 | 100% | none | PASS |
| L7 remainder tiebreak (not a lever, judge-only) | 0 | 0 | n/a | none | n/a |

Stacking: OUT/STACKING_CHECK.md (stacking_check.py: tests 31, positive 64, negative 23; judge 37, positive 68; verdict PASS after by-hand notes).

## Score band

Saved teammate run (original_backup/trajectories/claude-opus-5/run_1, its /app/out) re-graded by WORK/harness/v5_replay.sh in the verifier image (runs/replay_v5/grades.jsonl); judge read by hand from the same trajectory.

| side | tests | judge (positive) | predicted final |
|---|---|---|---|
| BEFORE (QC copy 94a3e0a tests, 66 judge positive) | 7/64 = 10.94 | 17/66 = 25.76 (R25 1, R34 1, R35 0) | 18.35 (= last round) |
| AFTER (fixed bundle, 68 judge positive) | 7/64 = 10.94 | 19/68 = 27.94 (R25 1, R36 1, R34 1, R37 1, R35 0) | 19.44 |

- Tests unchanged for this program: it fails both unseen-extract checks and the audit check before and after (same 19 lost checks), so the new A/B settlement fixtures cost it nothing extra.
- The +1.09 comes only from JD-5: the agent's recap stated both strings (`pro_rata`, `duration_matched`) and named both logs, so the split pays two criteria where one was paid before. AL-27 moved nothing.
- Gate v3.7 (tests < 85, rubric < 85, final < 40): 10.94 / 27.94 / 19.44, all inside; prediction below 35.

## Gate results

- Docker block `_runs/20261031/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/fixgate-20261031T132558-e653/` (copies from live kit exe_copy.py, plain and `--owner-only`; tests image and environment image warmed first, WARM_EXIT=0, WARMENV_EXIT=0; dockfree START=yes before each lane; bundle lock taken and removed; chain.log ALL_DONE). oracle-1/2/3 reward 1.0, 1.0, 1.0; owner-1 1.0; nop-1 0.0.
- Kit scripts on BUNDLE: tests_qc.py VERDICT PASS (37 pass); structure_qc.py PASS; instruction_qc.py PASS; judge_qc.py 18 pass, 1 warn "[G3] 37 criteria; cap is 35 (warn)" (KEPT row 7).
- xref_check.py: 45 entries, 0 findings.
- precheck.sh last line: `PRECHECK: 1 finding(s)`. The one finding is the judge_qc G3 count warn above (precheck.sh:17 exempts only the X1/A3/S6 warns). It cannot be cleared without merging or dropping a non-duplicate criterion, which the no-count-cap rule forbids. Remaining NOTE lines are the same kind as last round (DS-22 notes for the blob/extract sha lines, which have no file of that name; EVIDENCE_MAP and SELF_CHECKS missing notes).
- stacking_check.py: PASS (OUT/STACKING_CHECK.md).
- Tasks_INPUT synced (`rsync -a --delete` BUNDLE/ -> Tasks_INPUT/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/): BUNDLE 2bbee90c2a47, Tasks_INPUT 2bbee90c2a47.

## Fix receipt

(a) Tree sha (`find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`): before (QC copy 94a3e0a) 7e457f09086a, after 2bbee90c2a47. Changed files: solution/TRUTH.md, solution/solve.py, tests/judge.toml, tests/reward.toml, tests/test_output.py (sealed blobs only). environment/ is byte-unchanged.
(b) Test checks: none changed (positive 64, negative 23, before = after). Judge: R25 1 -> 1 (re-worded), R34 1 -> 1 (re-worded), R36 - -> 1, R37 - -> 1; judge positive 66 -> 68, negative 25 -> 25; reward.toml judge 0.007575757575757576 -> 0.007352941176470588, test_output 0.0078125 unchanged.
(c) Oracle 1.0 x3 -> 1.0 x3; owner 1.0 -> 1.0; nop 0.0 -> 0.0.
(d) Saved teammate program (original_backup run_1): tests 7/64 before and 7/64 after, the same 19 lost checks, no lever check moved (runs/replay_v5). Hard-coded mutants on the fixed tests: hard pro_rata 49/64 (was 61/64 on v4 fixtures), hard duration_matched 61/64 (was 64/64 on v4 fixtures; WORK/runs/hyg_v6, cov_v6).
(e) Rescan after the last edit:
- AL-18 / DS-22 / DS-27: PASS. TRUTH.md regenerated by write_truth.py as the last bundle edit; precheck shows no DS-22 sha mismatch (only "no file of that name" notes for the blob/extract lines); TRUTH item 9 states the A/B settlement split, which matches runs/seal_v5.
- JD-14 / AL-28: PASS. R25/R36 pay the two strings, R34/R37 the two logs, R16/R17 the trajectory log reads, and R28/R29 penalise a contradicted reading. No claim is paid twice (stacking_check AL-28 UNMATCHED line is the known tool artefact, checked by hand in STACKING_CHECK.md).
- AL-1 / AL-2: PASS. instruction.md:9 promises the recap naming each settled reading's log, graded by R25/R34/R36/R37. The settlement section is graded by methodology_audit_remaining_sections_exact (test_output.py:618-637). Nothing new is graded that the instruction does not promise.
- AL-27: PASS. RULE_COVERAGE.md `## Update dbe00fc (QC v5)` has no 0 row: alae_rules.md:3 R_alae_skip_settle 5 checks (15 pts); alae_rules.md:7 R_alae_reversed 9 checks; discounting_rules.md:3 R_curve_skip_settle 1 check (3 pts); discounting_rules.md:5 R_curve_reversed 1 check.

## Noise keeps

None. The settlement rule was first graded in 841c07e, so no earlier round passed AL-27 on these lines.

## Deviations from master directions

- "curve_marks.csv if the generator ties them": the generator does not tie them, so curve_marks.csv is unchanged in extract B. B's treasury log is rebuilt from the unchanged curve_marks 10y mark (3.80), so flat_10y fits exactly (max deviation 0.0).
- Extract A also pins an explicit `layer=retention alae=0` log line for each unlogged claim whose event is shared with another claim. Without these lines, a claim moved by the clash cover to working_excess with no log row would have no ALAE amount stated under excess_only (alae_rules.md:7). The oracle's A ledger did not change (seal_v5 = seal_v4 digests). See QC_DEFENCE D15.
- solve.py changed (settle_alae_convention returns no fraction under excess_only; build_ledger defaults unlogged ALAE to 0 when no fraction fits). Without this, the oracle could not settle excess_only. The shipped outputs are byte-identical (seal shipped unchanged), so R1-R14 were not regenerated.
- precheck is not CLEAN: the JD-5 split takes the judge to 37 criteria (judge_qc G3 warn). The warn is kept with the count, per the no-count-cap rule.
- One rule breach in WORK: the seal_v5 container (2.4 s, WORK scratch only) was started in the same command after dockfree printed START=no (FREE_MB=610). It is recorded in LOG.md. Every gate lane started on START=yes.

## QC_RULINGS rows

- AL-28 | split judge criteria R25/R36 (strings) and R34/R37 (logs), one settled reading each | QC v5 JD-5 minor on the joined form | REAL | split as directed; each criterion is now one claim, so no stacking.
- (No finding this round on IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, JD-7 or JD-15. TS-13 was re-checked as the AL-27 side effect and passed.)

## Lessons for the master

- A settlement fixture also needs the oracle to support the rival reading (the solver here raised on excess_only) | template_change: QC_FIX_PLAYBOOK_v3.md AL-27 row DO: add "run the oracle on the fixture before sealing; a raise means the solver lacks the rival path"
- A rival reading can leave rows the docs give no amount for (clash-moved unlogged claims under excess_only); pin them in the hidden fixture | no change: covered by W5 hidden-fixture rule once checked by hand
- Splitting compound judge criteria pushes the count over 35 and makes precheck.sh print a finding | template_change: precheck.sh:17 also exempt judge_qc G3 count warn (like A3)
