# P12 r1 recheck and fix: match-replay-desync-audit (board 965f34e)

QC report: QC/reports/match-replay-desync-audit/v1.md (board ebf2870, kit 71a653b2). Live kit HEAD:
71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e (same as the report's kit; no rule ID or wording changed).
Session rename: `name_session.py 965f34e` printed "codex: no match / opencode: ['ses_e968f7e6bffe6DIbO23ZGcLIH0']";
965f34e was not in the list, carried on as instructed.
Start tree sha 2f20060e94d2 (match). Levers in LEVERS.md: L1 green control, L3 running charter allowance, L4 renewal at
live window openings.

## Phase 1 rows

| ID | Label | Rule (live kit) | Evidence (bundle) | Decision | Playbook row | L1 / L3 / L4 | Files changed |
|---|---|---|---|---|---|---|---|
| F-01 AL-2 | REAL | 05_Alignment_Integrity_QC.md:22 "AL-2 Everything promised is graded. For each instruction requirement: point to the test (or criterion) that checks it." | instruction.md:9 "It carries `settling_passes`, an integer."; report-schema.md:66 "passes the identity register took to stabilise"; test_output.py:1182-1214 record_schema_ok checks only `isinstance(..., int)`; record_derivation_ok 2124-2146 never reads it; plan["settling_passes"] set at 694 and unused | FIX: record_derivation_ok adds `type(record["settling_passes"]) is int and record["settling_passes"] == plan["settling_passes"]`. test settling_passes (637-651) and solve.py Register.settling_passes (423-434) both sweep roster rows in file order and count the clean sweep, as charter-scale.md:104-107 says | AL-2 / CL-1 (DO: grade through an observable the program writes, on hidden inputs) | none / none / none | tests/test_output.py |
| F-03 AL-2/AL-10 | REAL | 05:22 (AL-2 above); 05:40 "AL-10 Hardcode shipped answers: ... could an agent score above the honest floor by memorizing them? The negative tests must catch exactly this." | instruction.md:7 "recover the eleven quantities from the calibration notes in the capture directory it is handed each time it runs, rather than carry their values in its source"; replay_plan test_output.py:365 `values = dict(TRUE_VALUES)` for every corpus; only value tweak cadence_modulus 7 (2345). BEFORE score of the new "carry eleven in source" variant: 152/157 = 0.9682 (loses only mutation_cadence) | FIX: held-out corpora draw all eleven values from their candidate sets by seed; calibration notes regenerate per corpus; shipped seed keeps TRUE_VALUES (data byte-identical) | AL-2 / CL-1 | none / none / none (L1 controls still green on every corpus; trap survival below) | tests/test_output.py |
| F-04 AL-2 | REAL | 05:22 (AL-2 above) | report-schema.md:101-103 "It takes the directory holding the capture set as its first argument and the directory to write into as its second. It writes every report named above and nothing else."; _produced test_output.py:1997-2004 opens only the one report it needs; no listing check | FIX: new w1 check test_format_writes_only_named_reports (sorted listing of a staged held-out result dir equals the nine names). Record decision: record_derivation_ok ran only on the shipped record (2157-2160), so test_record_derivation_matches moves to the staged held-out record (also W-06); no second record check | AL-2 / CL-1 | none / none / none | tests/test_output.py, reward.toml, solution/TRUTH.md |
| F-02 JD-5/JD-7 | REAL | 04_Judge_QC.md:71 "JD-5 Each criterion names ONE observable behaviour ... The telltale shape is unrelated observables joined by "and""; 04:76 "JD-7 ... Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle" | judge.toml:144 R11 joins three observables; solve.py:148-157 Capture.__init__ skips unknown lines silently, no named error class anywhere in solve.py | FIX as directed: R11 keeps only the separately named functions clause (same id, weight 3). Oracle meets it: decode_all/Unwinder (solve.py:229,385), Register.owner (410), settle (507), charter_stocks (470) | JD-7 (DO fix oracle for good practice) not used: master chose to drop the clauses under JD-5; see Lessons | none / none / none | tests/judge.toml |
| W-01 DS-25/IN-16 | REAL (warn) | 02_Data_Solution_QC.md:71 "DS-25 The exact output shape is reachable."; checklist 02:111 "(named file per literal)" | report-schema.md section headings 13, 33, 48, 61, 79, 88 never name the file; mapping only by elimination with instruction.md:7 | FIX: one line "Written as `<file>`." under each report section heading, edited in STATIC_NOTE_TEXT and regenerated | no row (master direction) | none / none / none (names are already in instruction.md:7) | tests/test_output.py, environment/data/report-schema.md |
| W-02 DS-21/IN-9 | UNSURE | 02:70 "DS-21 Solvable from what the agent actually receives"; checklist 02:107 "(hard is fine; only genuinely unreachable information fails)"; 01_Instruction_QC.md:39 IN-9 "a licence to withhold, not a licence to make the task unreachable" | control fragment serialization lives only in test_output.py:945-1103; charter-scale.md:30-33 gives key, bar separator, UTF-8; calibration.md:10-25 prose. QC itself rated DS-21 pass "hard, not impossible". LEVERS.md (L1 = controls stay green under misreads) and DESIGN.md:26-29 never name the format search as a lever or stated difficulty | No change. Question in PL_NOTE.md | SUGGEST (not applied; master asked for UNSURE) | none / none / none | none |
| W-03 TS-23 | REAL (warn) | 03_Tests_QC.md:62 "TS-23 Counts and balance: at least 10 checks (fail), at most 35 (warn)"; tests_qc.py run on BUNDLE: "WARN [A3] 41 checks; cap is 35 (warn)" | 41 checks now, 42 after F-04 | KEEP (Ayush approves over 35; folding would make omnibus checks, TS-13 03:44). In PL_NOTE.md | TS-23 (DO KEEP as a warn with the count and 03:62) | none / none / none | none |
| W-04 TS-17 | REAL (warn) | 03:48 "TS-17 Comparisons are exact where the instruction promises exactness ... Watch the Python trap where `True == 1`" | test_output.py:2106 `if produced != wanted:`; 2119 `if value != wanted:`; _first_difference 2077-2097 is type-strict but only builds the message | FIX: both decide with `_first_difference(...) is not None` | no row (master direction) | none / none / none | tests/test_output.py |
| W-05 TS-19 | REAL (warn) | 03:50 "TS-19 Every graded behaviour must be learnable by the agent" | grading runs `python -I -S /app/out/optimize.py` alone (test_output.py _stage); instruction.md:7 never says one file | FIX: instruction.md:7 adds "Keep the whole program in that one file; nothing else under /app/out is imported at grading." | TS-19 (DO add the contract line) | none / none / none | instruction.md |
| W-06 CL-3 | REAL (warn) | Final_checklist.md:490 "CL-3 The graded answer is earned, not copied."; 05:76 "no asserted value liftable verbatim from a shipped file" | record_derivation_ok 2144 `row["produced"] != figures[control]` on the shipped record equals calibration.md:29-39 published column | FIX with F-04: the record check reads a staged held-out record whose figures come from that corpus's own notes, so the produced column is no longer a copy of a shipped figure. The published/produced comparison stays on the held-out record (it is what the agent must reproduce there) | AL-2 / CL-1 | none / none / none | tests/test_output.py |

QC_DEFENCE.md (D1-D8) has no entry for settling_passes, carried quantities, file listing, R11 clauses or fragment
serialization. QC_RULINGS.md rows read: AL-2 / CL-1 cohort v3:42 (AVOID ungraded promise), TS-23 district-heat v4:47
(WARN), JD-7 cohort v3:38, TS-19 schema v3:35.

## What changed (BUNDLE)

- tests/test_output.py: F-01 `settling_passes` equality in `record_derivation_ok`; F-03 `drawn_values(seed, attempt)` (sha256 of "seed:attempt:name" indexes the published candidate range; the shipped seed keeps the shipped values), `pins_separate` repair (every active quantity keeps one witness), `class_draws_renamed` repair (each per cadence held-out set still holds a short draw on a renamed charter in its graded class), `_replay_draw` holds the old body; F-04 `NAMED_REPORTS` + `test_format_writes_only_named_reports` (w1, staged cadence-peak run) and `test_record_derivation_matches` moved to the staged deep chain set (W-06); W-04 `_compare` / `_match_shipped` decide on `_first_difference(...) is not None`; W-01 a "Written as `<file>`." line under each report-schema heading in STATIC_NOTE_TEXT.
- environment/data/report-schema.md regenerated from the generator; `emit` output is byte identical to environment/data.
- instruction.md:7 one-file sentence (W-05). tests/judge.toml R11 wording (F-02). tests/reward.toml 0.5/158. solution/TRUTH.md counts. solve.py unchanged.
- WORK: DESIGN.md, LEVERS.md, QC_DEFENCE.md (D9, D10), XREF.md (25 entries, 0 findings).

## Deviations from master directions

- F-04 record: the derivation record is graded on the staged deep chain mutant, not on a cadence held-out set. Reason: the shipped set and 14 of 16 hidden sets settle in four passes, so a program that writes `"settling_passes": 4` would still pass on cadence-peak (local check: 157/158 on deepchain grading, would be 158/158 on cadence-peak). Deep chain settles in five and differs from shipped in 10 of 11 values. No second record check was added (TS-26).
- F-03 extra repair `class_draws_renamed`: drawing `cadence_modulus` per set first moved the renamed-charter short draws out of the graded class in the steady and latency sets, so the opening-charter variant gained 2 hidden w5 checks. The repair redraws until the graded class holds such a draw; with it every separating case is back. Held-out weights unchanged.

## Gate results

| gate | result |
| --- | --- |
| xref_check before / after | 16 entries 0 findings / 25 entries 0 findings |
| structure_qc | 17 pass, 0 fail (PASS) |
| instruction_qc | 5 pass, 0 fail (PASS) |
| tests_qc | 36 pass, 1 warn `WARN [A3] 42 checks; cap is 35 (warn)`, 0 fail |
| judge_qc | 19 pass, 0 fail (PASS) |
| stacking_check | STACKING PASS (OUT/STACKING_CHECK.md) |
| shipped data regen | byte identical |
| local oracle | 158/158 = 1.0000, 42 checks |
| Docker oracle x3 | 1.0, 1.0, 1.0 |
| Docker owner-only | 1.0 |
| Docker chmod 600 program | 1.0 |
| Docker nop | 0.0 |
| Docker stub | 0.0063 (1/158; before 0.0064 = 1/157) |
| Docker forgery (nine shipped answers as literals) | 0.0127 (2/158; harden r1 0.0127) |

Docker block: /tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9, log copied to docker_block/runs.log (ALL_DONE 21:42:46). Copies built by live kit exe_copy.py (plain, --owner-only, --stub); tests-only reward weight 1/158 in the copies.

Manual checks per fixed ID: oracle that also writes `notes.txt` scores 157/158 and fails only `format_writes_only_named_reports` (F-04); oracle with `"settling_passes": 4` scores 157/158 and fails only `record_derivation_matches` (F-01); carry-eleven variant 6/158 (F-03); R11, schema file lines and one-file sentence present (F-02, W-01, W-05); `_compare` is type strict (W-04).

## Agent program before / after

| program | before (P 157) | after (P 158) |
| --- | --- | --- |
| agent optimize.py as is | 17 = 0.1083 | 18 = 0.1139 |
| agent adapted (`< 1`) | 17 = 0.1083 | 18 = 0.1139 |

The one new point is the w1 listing check. Both still fail every hidden whole-document check.

## Trap survival

Loss of P = (P minus earned) / P, local tests channel scorer WORK/local_score.py, before on WORK/trap/before_r1, after on the fixed bundle.

| variant | before loss of P | after loss of P | ratio | separating cases kept | verdict |
| --- | --- | --- | --- | --- | --- |
| agent as is | 140/157 = 0.8917 | 140/158 = 0.8861 | 0.9937 | y | PASS |
| agent adapted | 140/157 = 0.8917 | 140/158 = 0.8861 | 0.9937 | y | PASS |
| var_perentry (L3) | 140/157 = 0.8917 | 140/158 = 0.8861 | 0.9937 | y | PASS |
| var_norenew (L4) | 140/157 = 0.8917 | 140/158 = 0.8861 | 0.9937 | y | PASS |
| var_opening (L4) | 135/157 = 0.8599 | 140/158 = 0.8861 | 1.0305 | y | PASS |
| var_cancelled_draw | 140/157 = 0.8917 | 140/158 = 0.8861 | 0.9937 | y | PASS |
| var_carry_eleven (new) | 5/157 = 0.0318 | 152/158 = 0.9620 | new, needs >= 0.5 | n/a | PASS |

Reflex before 0.1083, after 0.1139; single-lever max after 0.1139 (<= 0.20). var_cancelled_draw is my rebuild (harden r1 recorded 0.1401 for its version; that program is gone). Carry-eleven loses 152/158 = 96.2% of P, every held-out and mutation point plus both new w1 held-out checks. Trap survival PASS.

## QC_RULINGS rows

- F-01 | AL-2 every promise graded | settling_passes promised, only type checked | QC fail | REAL | now compared to the generator's count on a set that settles in five passes.
- F-03 | AL-2 / AL-10 recover each run | every held-out set reused the shipped eleven | QC fail | REAL | each fresh set draws its own eleven from the published ranges; carrying scores 0.038.
- F-04 | AL-2 writes every report and nothing else | listing ungraded | QC fail | REAL | new w1 listing check on a staged held-out run.
- F-02 | JD-5 / JD-7 one observable, oracle true | R11 had three observables, oracle failed one | QC fail | REAL | R11 keeps only the named functions clause.
- W-01 | DS-25 / IN-16 output shape reachable | file names found by elimination | QC warn | REAL | file name under each schema heading.
- W-02 | DS-21 / IN-9 solvable from inputs | fragment serialization withheld, digest search reaches it | QC warn | UNSURE | not a named lever or stated difficulty; question in PL_NOTE.md.
- W-03 | TS-23 at most 35 checks (warn) | 42 single-property checks | QC warn | REAL, KEEP | approved over 35; folding breaks TS-13.
- W-04 | TS-17 exact comparisons | `!=` let `True == 1` pass | QC warn | REAL | decide on the type strict `_first_difference`.
- W-05 | TS-19 promise graded and learnable | single file grading not stated | QC warn | REAL | one-file sentence in instruction.md:7.
- W-06 | CL-3 earned not copied | record figures equal shipped published column | QC warn | REAL | record graded on a fresh staged set.

## Lessons for the master

- A "recover each run" promise needs held-out data that moves the values, or no test can tell recovery from carrying.
- Drawing values per set can move lever cases out of the graded slice; rerun single-lever variants after any generator change.
- Grade a count on a set where the count differs from shipped, or a hardcoded shipped value passes.
- JD-7 playbook says fix the oracle; a JD-5 row for dropping extra clauses would help.
