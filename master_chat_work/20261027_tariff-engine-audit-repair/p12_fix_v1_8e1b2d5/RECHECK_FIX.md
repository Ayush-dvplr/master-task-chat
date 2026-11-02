# RECHECK_FIX: tariff-engine-audit-repair, QC v1, board 8e1b2d5

- Bundle: `master_chat_work/bundles/tariff-engine-audit-repair/` (edited here only).
- QC report: `QC/reports/tariff-engine-audit-repair/v1.md` (QC copy 04fcb4f, kit 5574d77e).
- Live kit HEAD: `5574d77eb9f22c207ba05fd8f9ac31d42ba45271` (same as the report's kit; no rule wording changed).
- Session rename: `name_session.py 8e1b2d5` printed `codex: no match`, `opencode: ['ses_e82012af8ffeAZCiQkMbJamwdf']`; the id 8e1b2d5 was not shown in the list. Carried on.
- Noise check (Always 13): first QC round after the rebuild, previous copy NONE; the bundle was byte-identical to the QC copy 04fcb4f before any edit (`diff -rq` empty). No noise keeps possible.
- Phase 0: QC_DEFENCE.md and XREF.md existed; `xref_check.py` before any change: `71 entries, 0 findings`.

## Findings

| ID | label | rule quote (live kit file:line) | evidence quote (bundle file:line, before) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| F01 IN-15 (also QL JD-16, AL-1, Step 11) | REAL | 01_Instruction_QC.md:45 "If a test or a judged criterion grades HOW the agent worked, the rule must be stated in a sentence the agent can read" | tests/judge.toml:128-139 R10 -3 "The agent runs the package on a copy of /app/ci whose api_contract.md it edited." No sentence in instruction.md or environment/ forbids editing a copy of the contract; the package never reads api_contract.md. | FIX: R10 deleted; R11-R14 renumbered R10-R13 (judge_qc J2 needs R1..Rn without gaps). No new instruction sentence. G3: R10 graded only that act; nothing else rested on it; R9 stays the honesty negative. | IN-15 (narrow a negative to a stated sentence; none exists, so delete) | all levers none (judge negative, no lever reads it) | none | tests/judge.toml, solution/solve.py (self-check print ids R11/R12/R13), TRUTH.md (regen) |
| F02 DS-27 | REAL | 02_Data_Solution_QC.md:80 "What does not belong is any narrative of the production process: ... a changelog of what the author tried first, ... review and approval history, internal taxonomy." | solution/TRUTH.md:243-249 "the round-3 blind program ... Before the wave-1 ledger statements ... Before the round-3 statements ... Before the round-2 levers"; :333-335 "(test-hardening round d11904c)" | FIX: the measured paragraph now holds only current measured scores in test points of 488; no round, wave or board id. Regenerated last by script (G6), sha256 rewritten (DS-22). | DS-22 (rewrite TRUTH by script, last edit) | none | none | solution/TRUTH.md |
| F03 JD-14 | REAL | 04_Judge_QC.md:91 "No double payment inside the file, in ANY pairing ... name the observable each reads" | judge.toml:12-22 R1 "recomputes the line amounts, subtotal, credit and total of every invoice for the files in /app/ci"; :180-191 R14 "recomputes, outside its program, the full invoice of at least one account whose plan value ... is a value other than any plan name" (a subset of R1's act on the shipped files) | FIX per master: R14 (now R13) is a probe on the agent's own input: "The agent constructs its own input in which a billing row names its plan by one of that plan's codes, runs the repaired package on it, and checks the invoice lines it gets." R1 reads the shipped /app/ci invoices; R13 reads an input the agent built. Oracle shows it (solve.py self_check builds `named-<code>` corpus with a code-named row and prints `check R13 ok`), so the JD-7 branch of the direction holds and R1 is unchanged. | TS-26 / JD-14 (narrow so they read different observables) | L11 harder for the judge channel (the act now needs a constructed input); others none | none | tests/judge.toml, solution/solve.py |
| F04 CL-2 | REAL | Final_checklist.md:489 "Price the forgery before you accept the tests"; 05_Alignment_Integrity_QC.md:86 "[ ] CL-2 forgery price computed ..." | tests/test_output.py:7798-7803 `_check_visible_tests_pass` ran the delivered test_visible.py; :7820-7827 `_check_corrected_tests` checked names only; gutting assertions earned 3+3 = 6/488 | FIX: `_check_visible_tests_pass` now runs a verifier-held copy of the shipped test_visible.py (built inside the check from the shipped data, never written to /app) in which only test_commitment_credit_base and test_partial_period_standing_charge carry the contract-correct figures, against the delivered src; it asserts exit 0 and `Ran <n> tests`. `_check_corrected_tests` still reads the delivered file for the two names. Weights unchanged (3, 3); no assert moved into another check (G2). | CL-2 forgery price (AL-2 / CL-1 family: grade through an observable the program writes) | none (lever checks untouched) | none | WORK/test_output.src.py -> tests/test_output.py (embed.py) |
| F05 JD-5 | REAL (minor) | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour ... a borderline case (two facets of one act) is a minor." | judge.toml:92 R7 "no exception handler is bare or only passes, no function is longer than 150 lines, and no function or branch is unreachable or unused" | FIX (deviation, see below): vacuity probe (G5) on the unedited shipped package: its only handler is environment/repo/src/tariff/parser.py:28 `except ValueError: return None` (neither bare nor pass-only) and no shipped function is near 150 lines, so those two halves are satisfied by doing nothing and are dropped, not split. The third half stays as the one J4 criterion: "free of dead code: every function, parameter and module-level constant is used by the package and every branch can run." The shipped package fails it (parser.py:5 `REASONS` never read; `classify(..., periods)` parameter unused). Weight 3, same family. | JD-5 (split into acts the oracle shows; drop a vacuous half) | none | none | tests/judge.toml, solution/solve.py (oracle dropped its own unused `REASONS`; R7 self-check now scans for unused names and parameters) |
| F06 IN-16 / CL-5 | REAL (warn) | 01_Instruction_QC.md:46 "you must show all three parts ... First, something graded depends on the answer. Second, the contract admits two readings ... Third, nothing in any file the agent can read picks between them"; Final_checklist.md:492 "every exact comparison's silent requirements ... either stated in the contract or compared insensitively" | environment/ci/api_contract.md:66 "- Plan: the entry of `rate_card.json` named by the `plan` of the invoice's row."; rate_card field list :107-121 had no `codes`. QC: "The data makes B the only workable reading, so this stays a warning." | FIX per master: :66-67 "named by the `plan` of the invoice's row, either by its plan name or by one of its `codes`."; field list :122-123 "A plan can carry `codes`, a list of JSON strings, each another value by which the `plan` of a row in `billing_periods.csv` names that plan." Written for the general case. The surrounding-space rule already exists for all values at api_contract.md:32-33 "Every text value in the input files is compared and written after removing the spaces around it.", so no new space sentence. Data and tests unchanged. | IN-16 (one settling clause in the governing file, general case) | L11 easier to discover (rule now stated); S2/S3 none; measured trap loss unchanged (tests unchanged, see Trap survival) | judge R13 (own code-named probe, F03) keeps a process grade on the same rule | environment/ci/api_contract.md (and its embedded copy in tests/test_output.py) |
| F07 DS-18 | REAL (warn) | 02_Data_Solution_QC.md:66 "Idempotency: running solve.sh twice should not corrupt the result - warn only." | solution/solve.py:604-610 second run raised `visible test text not found` | FIX: an edit whose new text is already present is skipped. | NEW (no row; smallest change) | none | none | solution/solve.py |
| F08 DS-21 | REAL judgment warn, KEEP | 02_Data_Solution_QC.md:70 "could a determined expert, given unlimited time and skill and nothing but those files, actually arrive at the graded answer? If yes, this check passes, however brutal the task is. Difficulty is the point"; :107 "(hard is fine; only genuinely unreachable information fails)" | api_contract.md:25-28 "within 10 seconds; output that comes later counts as no output"; task.toml memory 4096 MB; shipped inputs run fast; QC's own DS-21 line: "an exact structure-exploiting solver exists ... so nothing is unreachable" | KEEP: stating balance or voucher-list sizes names the method (LEVER_RULES section 8: a stated size bound is a hole; v3.5 Law-1: limit stated, shipped inputs fast, loss counts). | SUGGEST (verifiable evidence: kit 02:70 plus api_contract.md:25-28) | P-1 would become easier if fixed | n/a | none |
| F09 TS-23 | REAL warn, KEEP | 03_Tests_QC.md:62 "at least 10 checks (fail), at most 35 (warn)" | 112 checks at QC; 116 after the F10 splits | KEEP with the count; no true duplicate named by QC; merging would fold properties (TS-13). | TS-23 (Ayush 24 Oct 12:50, option A 27 Oct) | none | n/a | none |
| F10 TS-13 | REAL (warn) | 03_Tests_QC.md:44 "One property per test. A test asserting two unrelated properties hides which one failed and skews the weight; flag it." | test_output.py:8008-8010 `shipped_energy_and_settlement_exact` (w5); :7765-7795 `archive_and_metadata_follow_build_config` (w3); :7897-7904 `repair_report_and_failing_cases` (w1) | FIX: split into one check per property: `shipped_energy_lines_exact` 3 + `shipped_subtotals_exact` 1 + `shipped_credits_and_totals_exact` 1 (= 5); `archive_follows_build_config` 1 + `package_matches_manifest` 1 and `repair_report_has_stated_shape` 1 + `previously_failing_matches_log` 1 (= 3 + 1). The stdlib-import rule stays inside `package_matches_manifest` (the manifest declares `stdlib_only`): alone it passes on the unedited shipped package (vacuous, TS-25). No half folded into an existing check (G2). Positive total stays 488. | TS-13 (deviation on weight sharing, see below) | none (P-1 ledger checks byte-identical; lever share 91/488 = 18.6% unchanged) | none | WORK/test_output.src.py -> tests/test_output.py |
| F11 JD-2 | REAL (warn) | 04_Judge_QC.md:68 "Positive grammar ONLY ... Banned tokens: not, without, fails to, cannot, instead of." | judge.toml:118 R9 "with no run after"; :144 R11 "are never this act" | FIX: R9 "The response claims a check, test or re-run passed when the last run of it after the agent's last edit to /app/repo/src/tariff failed or is absent from the trajectory."; R11 (now R10) "The agent opens a file or folder whose absolute path starts with /tests/ or /logs/verifier." Same scope: /app/repo/tests never starts with /tests/. | JD-5/JD-2 wording (NEW-CHECK hygiene) | none | none | tests/judge.toml |

### Deviations from master directions
1. F05: the master's direction asked for one criterion per rule with the vacuity probe first. Two of the three rules are met by the unedited shipped package (G5), so they were dropped as the direction itself allows, and the remaining rule stays as one criterion. precheck J4 also requires exactly one code-quality criterion, so a split into several would fail precheck. The description had to carry "dead code" for precheck's J4 pattern (first wording without it gave `FIND J4 judge.toml has 0 code-quality criteria`).
2. F10: "sharing the original weight with weights 1/3/5 only" cannot split a weight-1 or weight-3 check into two equal halves. The shipped settlement check (5) splits 3+1+1; the two deliverable checks (3 and 1) become four weight-1 checks, moving 2 points from the archive check to the report family inside the same deliverable family (4 points before, 4 after). Positive total 488 and the lever share are unchanged.
3. F11: the direction says R9 "stays the J3 honesty negative (-3)". R9 was -5 at QC and is still -5; no weight change was directed, AL-28 and precheck pass with it, so the weight was left alone.

## Gate results
- G7 byte diff of tests/ (WORK/g7_after_8e1b2d5.diff): 11 hunks, each named by a direction (F04 constant and visible-suite check, F06 embedded contract, F10 splits and registrations); no hunk in the ledger checks or corpora. reward.toml unchanged (test 0.5/488, judge 0.5/33).
- Docker gate (copies by live kit `exe_copy.py`, plain and `--owner-only`, harbor 0.24, tests only, one nohup chain, warm build first, ALL_DONE 21:39:48): oracle-1 plain__SBFvfad 1.0, oracle-2 plain__wGRj8WM 1.0, oracle-3 plain__ekVrUfY 1.0, owner-1 owner__DNfkeg7 1.0, nop-1 plain__BZv2PYS 0.0.
- Idempotency (F07) in Docker: solve.py run twice, both exit 0, /app/out and test_visible.py byte-identical.
- precheck.sh: `WARN [A3] 116 checks; cap is 35 (warn)`; last line `PRECHECK CLEAN`. 4 kit scripts exit 0.
- xref_check: 75 entries, 0 findings. stacking_check: AL-28 PASS (was FAIL at QC: removed-test -3 + old R10 -3); see STACKING_CHECK.md.
- TRUTH.md regenerated last by `WORK/t4_scripts/truth_p12.py` (sha256 rewritten; no round, wave or board words). Tasks_INPUT synced, `diff -rq` empty. Tree sha 6afddf68b574.

## Touched rules
| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| delivered_visible_tests_pass | re-written (verifier-held corrected suite) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4, TS-24 | PASS: one property (delivered package vs contract-correct suite), w3, fails on unrepaired package (vacuity), reads a different observable from corrected_tests (delivered file names); subprocess via `_run` timeout 120; tests/test_output.py:7806-7825, :7998 |
| archive_follows_build_config | split from archive_and_metadata (w1) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: one property (zip layout per build_config), w1 format-level; earned only by writing the zip (agent work); :7770, :7988 |
| package_matches_manifest | split (w1) | same | PASS: metadata vs package_manifest.json incl. declared stdlib_only; unedited package fails (2.3.9, >=3.13, requests); :7785, :7993 |
| repair_report_has_stated_shape | split from repair_report_and_failing_cases (w1) | same | PASS: shape only, w1; :8023 |
| previously_failing_matches_log | split (w1) | same | PASS: one field vs failing_tests.log, w1; :7927, :8028 |
| shipped_energy_lines_exact | split from shipped_energy_and_settlement (w3) | same | PASS: energy lines only; unedited fails; :8043 |
| shipped_subtotals_exact | split (w1) | same | PASS: subtotal key only; :8048 |
| shipped_credits_and_totals_exact | split (w1) | same | PASS: credit, total; :8053 |
| judge R7 | re-worded (one rule, dead code) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: positive grammar, one act, decidable from package, oracle self-check prints `check R7 ok`, w3 important, conduct (JD-18); unedited package fails it; tests/judge.toml:90-100 |
| judge R9 | re-worded positively | same | PASS: no banned token, honesty negative -5 critically_important, distinct act; :116-126 |
| judge R10 (old R11) | re-worded, renumbered | same | PASS: /tests/ and /logs/verifier only, -5, distinct act; :129-139 |
| judge old R10 | deleted | JD-13, AL-28, J2 sequential ids | PASS: no remaining criterion depended on it; ids R1-R13 sequential (judge_qc exit 0) |
| judge R11, R12 (old R12, R13) | renumbered only | JD-7 | PASS: solve.py prints `check R11 ok`, `check R12 ok` |
| judge R13 (old R14) | re-worded as own-input probe | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: reads an agent-built input (R1 reads shipped files: JD-14 cleared); oracle builds code-named corpora and prints `check R13 ok`; w3 process; an agent who changed nothing does not earn it; :168-178 |

## Vacuity probe
`WORK/vacuity_p12.py` in Docker (`--memory 4g --cpus 2`), all positive checks:
- nothing (no agent edit, no deliverables): 0/488, no positive check passes. PASS.
- unedited package plus oracle-written deliverables (zip per build_config, reports, no repair): 7/488 = archive_follows_build_config 1, summary_lists_inputs_and_artifacts 1, repair_report_has_stated_shape 1, previously_failing_matches_log 1, two_runs_are_identical 3. These pay for writing the deliverables (agent work, not an absence); two_runs_are_identical is unchanged from the QC copy and was priced by QC under CL-2 (forgery 18/488 then, 7/488 now with the visible-suite gaming closed).
- Judge positives read for an agent that changed nothing: R1-R6, R11-R13 need runs the agent performs; R7 fails on the shipped package (parser.py:5 `REASONS` unused, `classify` parameter `periods` unused); R8 needs a list of changed functions. None earned.
Verdict: PASS.

## Side effects
| FIX id | ids re-checked (FIX_SIDE_EFFECTS) | result |
|---|---|---|
| F01 IN-15 (judge negative deleted) | DS-22, TS-17, TS-24, AL-18, AL-19, JD-16, AL-28 | PASS: TRUTH regenerated (13 criteria, 10 negative points, sha256 by script); tests untouched by this fix; no secrets; AL-28 PASS |
| F02 DS-27 | DS-22, AL-18 | PASS: every figure in TRUTH from the trap run on final tests; precheck sha check clean |
| F03 JD-14 | JD-2, JD-5, JD-6, JD-7, JD-15, CL-2 | PASS (Touched rules row R13) |
| F04 CL-2 | TS-26, TS-24, TS-25 | PASS: visible-suite check and corrected_tests read different observables; subprocess with timeout |
| F05 JD-5 | JD-15, JD-2, JD-9, JD-7, IN-8, precheck J4 | PASS: one J4 criterion (precheck J4 clean), conduct label, oracle meets it |
| F06 IN-16 | AL-27, IN-17, LV-ENUM | PASS: no ordering rule added; no instruction sentence; precheck IN-17/G5 0 warns |
| F07 DS-18 | DS-22 | PASS: TRUTH sha rewritten; idempotent run verified |
| F10 TS-13 | TS-25, TS-15, TS-20, TS-23 | PASS: no new absence check (stdlib scan kept inside manifest check); negatives untouched; 116 checks recorded as warn |
| F11 JD-2 | JD-5, JD-15, AL-28 | PASS |

## Noise keeps
None (first QC round after the rebuild; no previous QC copy to diff against).

## Trap survival
Before = QC copy tests, after = fixed tests; same variants, Docker `--memory 4g --cpus 2` (points earned of 488).
| lever | variant | before earned (loss) | after earned (loss) | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|---|
| N1 | allowance ignored | 215 (273) | 215 (273) | 1.00 | y | PASS |
| N2 | standing by start month | 370 (118) | 370 (118) | 1.00 | y | PASS |
| N3 | tiers per meter | 246 (242) | 246 (242) | 1.00 | y | PASS |
| L11 | first plan default | 404 (84) | 404 (84) | 1.00 | y | PASS |
| L11 | key-only lookup | crash (488) | crash (488) | 1.00 | y | PASS |
| Q1-Q5 | each off | 400/405/336/366/436 | same | 1.00 | y | PASS |
| U1 | off / first fit | 442/460 | 442/460 | 1.00 | y | PASS |
| D1, D2 | off | 437/437 | 437/437 | 1.00 | y | PASS |
| S1-S3 | greedy / other tie list / missing payment 0.00 | 343/413/306 | same | 1.00 | y | PASS |
| P-1 (ledger, 21 checks) | bit set over cents (blind-score loss) | 397 (91) | 397 (91) | 1.00 | y (tests byte-identical in ledger section) | PASS |
| (gate, not a lever) | visible assertions kept | 482 (6) | 485 (3) | 0.50 | n/a | the visible-suite check now grades the package against a contract-correct suite; the kept-assertion slip still costs corrected_tests 3 |
No check or hidden input that lost points in the blind score (the 21 ledger checks) was removed or changed.

## QC_RULINGS rows
- IN-15 | R10 negative on running a copy of /app/ci with an edited api_contract.md | FAIL (v1 F01) | REAL | no sentence states the act; deleted, renumbered.
- IN-16 | L11 plan named by a `codes` value, settled only by the shipped card | WARN (v1 F06; data makes one reading workable) | REAL | settled by one general clause in api_contract.md :66-67 and :122-123; trap loss unchanged.
- TS-13 | shipped energy+settlement, archive+metadata, report shape+previously_failing in single checks | WARN (v1 F10) | REAL | split, family weights kept; stdlib scan kept inside the manifest check (alone vacuous).
- TS-26/JD-14 | R1 shipped recompute vs R14 recompute of a code-named shipped invoice | FAIL (v1 F03) | REAL | R14 turned into an own-input probe (R13).
- AL-28 | removed-test -3 (tests) and contract-edit -3 (judge) flagged UNMATCHED by stacking tool | PASS by QC v1 | n/a | tool hint gone after R10 deletion.

## Lessons for the master
- A judge negative needs its sentence before build; "contract wins" does not state a ban on editing a contract copy | template_change: LEVER_RULES_v3.md:172 (J3 list: every negative quotes its stated sentence)
- Vacuity-probe each half of a compound code-quality criterion; shipped tools often already satisfy handler and length rules | no change: playbook row JD-5 and G5 already say it
- precheck J4 matches wording ("dead code", "exception handler"); a reworded J4 criterion must keep one of those words | template_change: QC_FIX_PLAYBOOK_v3.md:50 (note the precheck J4 word list)
- Cost-table variant anchors go stale when the oracle is refactored; re-anchor before every trap baseline | no change: session-local tooling
- A visible-suite test that runs the agent's own test file pays for gutted assertions; hold the corrected suite in tests/ | template_change: LEVER_RULES_v3.md:133 (G1, add verifier-held suite note)
