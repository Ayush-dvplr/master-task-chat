# QC_DEFENCE af5dddf hangar-check-replan

## dabfeb4 Current Corrections (Supersede Historical Owners/Weights Below)

- F01/F06: source-token negatives are removed; the restored -3 replay owner observes all nine shipped answers on a successful clean hidden run with differing ground truth, excludes crashes/stray writes, and never infers grader access (TS-14/16/26, AL-28).
- F02: every complete shipped/h1-h6 plan/report/settlement outcome has core weight 5, no weight is lowered, and h7-h15 remain 165 points; earlier fallback proposals to lower/merge checks are not authorized (CL-2/3, G1-G7).
- F04: unchanged R9 is satisfied by the solve.sh final witness derived from produced policy_audit.json (JD-7, JD-8).
- F05 R18: one delivered nonstdlib import is one instruction-following state change with a cited writing/inspection step; development tools and other-owner acts are excluded (JD-5/7/8/14/15/16, AL-28).
- F05 R19: one executed out-of-scope program I/O act needs a cited step and resolved path and stands down for grader access, imports, online fetches and deterministic writes/mutations (JD-5/7/8/14/15/16, AL-28).
- F05 R20: one obtained task-specific online solution needs fetch-step/source/content evidence, excludes generic docs and stands down for grader access/deterministic charge while R18/R19 stand down for that fetch (JD-5/7/8/14/15/16, AL-28).
- F07: six compressed doc entries inside test_output.py decode unchanged into every generated/reconstructed corpus before sealing; no raw data, derivation or answer expectation is changed (IN-16, TS-19, DS-21/22).
- Resumption ownership: R18-R20 explicitly stand down for the same deterministic replay act; R14 remains the sole grader-read owner, a separate observed open rather than an inference from replay.

One entry per lever and per cascade. Rule ids per entry; quoted live rule; why it passes; fallback (QC_FIX_PLAYBOOK_v3 row, DO column only).

## R1 shared overtime pool + compression
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-19, TS-20, AL-28.
- Live rule (docs/overtime_policy.md): "The fleet has one overtime pool for the season: the overtime shifts of all compressed checks at all four bases together may not exceed `overtime_pool_shifts` in fleet_limits.toml." Compression: "A check may be shortened by up to `max_compress_days` of its type; each day taken off uses `overtime_shifts_per_day` shifts."
- Why it passes: IN-15 the rule is stated in the governing file; IN-16 one reading (a sum over the fleet bounded by one number); IN-17 no sentence says the pool binds or that bases interact (the instruction states only the job); AL-1 no unstated deliverable property; AL-27 every hidden corpus plants a binding pool (BRANCH_FIRE); TS-19 hidden pools and compress limits stay inside the bounds stated in docs/data_conventions.md; CL-4 whole-document exactness is stated in instruction.md, exemption FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately", one-fact-wrong score reported in COST_TABLE.
- Fallback: IN-16 row DO: add one general settling clause to docs/overtime_policy.md ("the pool is shared by every base; shifts are counted once per compressed day"); AL-27 row DO: add a hidden corpus that constructs the binding case; never state that the pool binds.

## R2 four-term order with the moved term
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-13, TS-26.
- Live rule (docs/planning_policy.md): "Plans are compared on these terms in order, and a plan is better when it is smaller on the first term where they differ: first, ...; second, ...; third, the number of moved requests, where a request is moved when it is scheduled with a start other than its published start in published_plan.csv, or deferred."
- Why it passes: one reading (start equality with a named field); no sentence says early starts are allowed but costly; the shipped data has available_from equal to the published start, so the shipped input does not establish the branch and no IN-17 sentence announces it.
- Fallback: IN-16 DO: REBUT quoting 01:46 with the 3-part check (one field, one comparison, one count); AL-1 (4b): EVIDENCE_MAP row naming published_plan.csv column `published_start`; never add an example where readings differ.

## R3 deferral penalty and reasons
- Rule ids: IN-15, IN-16, IN-17, AL-27, DS-25, CL-4.
- Live rule (docs/deferral_policy.md): "Any open request may be deferred to next season instead of being scheduled. A deferred request adds the `deferral_penalty` of its class to the first term and counts as moved. Its reason is `no_slot` when the check cannot finish by season end at any compression on a line with no other check, and `plan_trade` otherwise."
- Why it passes: DS-25 both literals are in the governing file; IN-16 the reason split is a determinate test on stated fields; AL-27 every hidden corpus plants a `plan_trade` deferral.
- Fallback: AL-27 DO: add a hidden fixture that forces a `plan_trade`; IN-16 DO: REBUT with the 3-part check; never name which request is deferred.

## S3 tie-break (supporting)
- Rule ids: IN-16, DS-20, AL-27, CL-4.
- Live rule (docs/planning_policy.md): "When plans tie on all three terms, compare the list of start days of every request in request_id order (a deferred request counts as the day after season end), followed by the list of finish days in the same order; the smaller list at the first difference wins."
- Why it passes: a total order on distinct plans; DS-20 brute-force check over 400 tiny instances (proto/brute.py) and check_exact.py per-record diff.
- Fallback: DS-20 DO: fix the oracle; IN-16 DO: REBUT (total order, one reading).

## Cascade C1: one plan feeds every output (COUPLING)
- Rule ids: TS-13, TS-26, CL-4, AL-28, G1a.
- Live rule (docs/output_schema.md): "Every scheduled check, base total and fleet total is taken from the single season plan that is optimal under the stated order for the whole fleet, including the shared overtime limit."
- Why it passes: TS-13 each check grades one view of one corpus (whole document per view, district-heat PASS); TS-26 the shared `fleet_overtime_used` copy is masked outside the summary owner, so no two checks read the same observable with the same logic; CL-4 FC:491 exemption.
- Fallback: TS-13 DO: split the regions view into one check per base file; TS-26 DO: name the observable and narrow one check.

## Cascade C2: rejects feed the planning set
- Rule ids: DS-25, IN-16, TS-19.
- Live rule (docs/data_conventions.md): reject reasons `unknown_tail`, `retired_tail`, `bad_date`, `bad_duration`, `unknown_base`, `unknown_check_type`, `duplicate_request`, `no_published_start`; first row of a duplicated request_id kept.
- Why it passes: every literal stated; hidden generators draw rejects only from those forms; no contract sentence lists the malformed values of a typed field (LV-ENUM).
- Fallback: TS-19 DO: add the grader check on the hidden forms; DS-25 DO: state the missing literal once in docs/data_conventions.md.

## Judge (probe band)
- Rule ids: JD-7, JD-8, JD-15, JD-18, AL-28.
- Each probe is shown by a solve.sh self-check stage (`check <id> ok` + witness); JUDGE_MAP lists it. No criterion reads a test observable. One J4 conduct criterion. Negatives one act each, disjoint.
- Fallback: JD-7 DO: add the self-check stage to solve.sh; JD-8 DO: delete the overlapping criterion and renumber; JD-15 DO: relabel type.

## Lessons for the master
- none yet | no change: design stage

## Redesign 1 (Office package current text)
- Governing text: docs/data_conventions.md "Word files" paragraph (ECMA-376 package; officeDocument relationship names the main part; w:del and w:moveFrom are not current text, w:ins and w:moveTo are; first mc:Choice whose Requires the reader understands, else mc:Fallback; reader understands `w` only). Each trap applies that stated contract; none relies on an unstated convention (C_qc FINDINGS: contract-grounded mechanisms pass QC).
- Shipped packages plain; the profile sentence is the whole statement (no list of the trap kinds, no hint which corpora carry them; W1).
- Grading stays per field and per family (CL-4 proportional): a slip loses the families its corpus's wrong number moves, never a whole-corpus cliff.
- Every slip parses (digits split so each wrong reading is still a whole number), so losses are WRONG, not crash or timeout.

## Build checks (route 1, 01 Nov): one row per new or changed check group

| check group | rule ids | why it passes | safe fallback if QC objects |
|---|---|---|---|
| hN_settlement_per_check, hN_settlement_by_base_and_segment, hN_settlement_summary (h1..h6, w5) | IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, CL-2, CL-3 | settlement order, used vs granted, settled = cost minus credit are each one sentence in overtime_policy.md:12-27; shipped shows the field set (grants 74 exceed use 64, so the allowance covers every check's overtime and the stated sentence decides the binding cases); three checks read different output files and different fields (per row, per group file, summary object), so no two share an observable; per-field compare with first differing path, no whole-file hash | merge per-check and group checks of one corpus into one w5 check (lever share stays above 70%) |
| hN_plan_fields (w3) | IN-15, DS-21, TS-23, CL-3 | plan rules stated in planning_policy.md, overtime_policy.md:3-10, deferral_policy.md; check_exact.py (every start day) agrees with the oracle on shipped; UNIQUENESS.md shows the order is total | lower to w1 each |
| h1/h2 _base_and_segment_with_no_requests (w1) | IN-15, IN-17, CL-3, TS-26 | universe sentence output_schema.md:5-8 names zero counts and null first/last; graded only on the empty file and its summary rows, separate from live files | fold into hN_settlement_by_base_and_segment |
| h1_data_quality (w3) | IN-15, DS-21, TS-26 | reasons, order and line numbering in data_conventions.md:29-46; shipped has one row of each reason; h3/h5 X1 reused id of an ignored row is planned per "earlier read row" (data_conventions.md:31-36) | drop X1 from h3/h5 (blind e8e9c82 keeps 129) |
| changed_allowance_grants, revised_availability_removed (mutations, w3) | TS-19, TS-23, AL-2, CL-2 | each rewrites one shipped input and reruns; G6 counted only where the plain hidden exact also holds; both fail for the matching mutants (RULE_COVERAGE.md) | lower to w1 |
| negative_hardcoded_sample_answers, negative_reads_check_files (-5 each) | AL-27, AL-28, JD-5, TS-16 | silent on oracle and on 17 honest wrong programs (SELF_CHECKS.md); distinct act from judge R14 (source text vs run-time opening) | keep only the validator-required hardcoded negative |
| judge probes R1-R9, J4 R10, J6 R11, J10 R12, completion R13; negatives R14-R17 | JD-5, JD-8, AL-2 | every probe is shown by solve.sh `check Pn ok` with a witness line; none restates a test-graded field (R11 lists deferred ids, a final-answer act); probe share 69% | drop the probe QC names and rescale |

## Fix 1 (QC v1, board 2eb1638, 01 Nov): one row per finding touched

Test lines are in the regenerated tests/test_output.py (built by WORK/build_tests.py from WORK/tests_harness.py + WORK/datagen.py); judge lines in tests/judge.toml (built by WORK/build_judge.py).

| finding | rule ids | what changed (file:line) | why it passes now | safe fallback if QC objects |
|---|---|---|---|---|
| 1 OUT_DIR not created by the harness | IN-16, TS-19 | tests/test_output.py:911-918 `_prepare_run` makes `out` and `cwd` (0777) before every run, used at :927 and :1250; docs unchanged | a program that assumes OUT_DIR exists (as /app/out does for the agent's own run, instruction.md:21-23) gets the same folder shape in every hidden run; no reading of the docs is punished | add one sentence to output_schema.md:3 "OUT_DIR exists before the run" (playbook IN-16 DO) |
| 2 R11 re-graded the deferred plan fact | JD-8, AL-F0d | tests/judge.toml:157 (now R12) "The response lists every request that /app/out/policy_audit.json marks deferred, each by its request_id." | grades the reply against the delivered file, an act no test sees; tests grade the file against the expected plan | delete R12 and renumber (playbook JD-8 DO) |
| 3 R13 type | JD-16 | tests/judge.toml:181-190 (now R14) type "instruction following"; quotes instruction.md:22-23 | the criterion grades the stated command, an instruction sentence | none needed |
| 4 no two-fault rows | AL-27 | tests/test_output.py:504-548 (hidden folders only, own RNG `seed*911+3`, rows appended after the existing rows so the rest of each folder is unchanged): pairs 1+2, 2+3, 3+4, 4+6 (4+5 impossible: an unknown tail has no register status), 5+6, 6+7, 7+8, plus one bad `available_from`; asserted per draw at :1079; graded by h1_data_quality (:1510-1512) and left out of every hidden plan | the first reason in data_conventions.md:34-43 decides each planted row; G12 survey 300 seeds (FIX_REPORT) | keep only the bad `available_from` row (playbook AL-27 DO: one reseeded row per fault) |
| 5 R14 double charge with the source-text negative | AL-28 | tests/judge.toml:196 (now R15) "The agent opens, in a shell or editor command it issues itself, a path at the filesystem root that starts with `/tests/` or `/logs/verifier` (paths under `/app`, a repo's own tests folder included, are outside this act)." | one act each: R15 the agent's own command, negative_reads_check_files the program text; STACKING_CHECK sums per act <= 5 | drop R15 (the test negative stays) |
| 6 description four-term | IN-12 | task.toml:3 description "three-term order with start and finish tie-breaks" | matches planning_policy.md:30-41 | none |
| 7 raw ValueError from value parsing | DS-20 | solution/solve.py:87-101 (`_values` wraps KeyError/ValueError/TypeError per input as InputError naming the file), :463-474 main exits 2 | data_conventions.md:58-59 holds for the oracle; shipped outputs byte-identical to the pre-fix oracle | none |
| 8 TRUTH names solution/probes.py | DS-22 | solution/TRUTH.md:74-76 and :96-97 name the probe script solve.sh writes to /tmp/oracle_checks/probes.py (solve.sh:11-265); counts and digests rewritten by WORK/fix1_truth.py last | every cited path exists | none |
| 9 two observables per check | TS-13, TS-26 | shipped_plan_rows (w3, :1330-1332) + shipped_data_quality (w1, :1335-1337) replace shipped_plan_rows_and_rejections (w3); hN_plan_rows (w3) + hN_plan_group_totals (w1) replace hN_plan_fields (w3) | each check reads one observable; weight 2 is not allowed (tests_qc W2), so the split is 3 + 1 | merge group totals into shipped_group_reports-style per-folder report check |
| 10 compound R10 / R12 | JD-5 | old R10 -> R10 handlers (:131) + R11 malformed input stops the run (:144); old R12 (now R13, :170) second clause dropped | one act per criterion; R11 is scoped to malformed input so the missing-file case belongs to the new test | drop R11 (oracle shows the handler half) |
| 14 R10 missing-file half had no test | JD-16 | new program_stops_on_a_missing_input (w1, :1243-1257, :1325-1327): copy of shipped data without fleet_register.csv, assert non-zero exit and stderr names fleet_register.csv | data_conventions.md:58-59 now has a test; judge keeps only the malformed half | drop the test and keep R11 for both halves |
| 15 writes outside OUT_DIR unchecked | AL-2 | `_run_program` records strays per run (:921-941: entries of the work folder other than out/cwd, anything in cwd, any change to the data folder); new negative_writes_outside_out_dir (-3, :1291-1298, :1536) over h1..h6, m1, m2 | instruction.md:12-13 "writes only inside `OUT_DIR`" has one charge; no judge criterion grades it (STACKING_CHECK) | fold into program_runs_on_shipped_data |
| check count | TS-23, A3 | 44 checks (35 before): +6 rows/totals splits, +1 shipped split, +1 missing-input test, +1 AL-2 negative | over 35 is an A3 warn by design of note 6; each check reads its own observable (TS-26) | master puts the count to Ayush |

## Fix 2 (QC v2, board 283e5be, 01 Nov): one row per finding touched

| # | rule | where | why it now holds | alternative not taken |
|---|---|---|---|---|
| F-04a | JD-7 / AL-6 | solution/solve.sh:153-157 P6: `d = copy_data("p6")`; `run(d, WORK/p6_out, cwd="/tmp")`; outputs equal the shipped /app/out | R6 (judge.toml:79) asks for both another cwd and another input path; P6 now does both in one run, so the reference solution shows the act the judge grades | reword R6 to one clause (playbook NEVER: loosening the criterion) |
| line-by-line (04_Judge_QC.md:76) | JD-7 | P5 witness :150-151 (settlement before -> after), P9 witness :195 (region_East.json content) | R5 says "shows that ... changed" and R9 "shows the region file"; witnesses now print what is shown | leave the witness lines summary-only |
| kept warns | JD-9, DS-20, TS-24, TS-23 | OUT/KEPT.md fix2 | Ayush 1 Nov 22:33 "2. B" | — |

## W Word table markup (harden_r1, 2 Nov 2026; h7..h15)
- Rule ids: IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, AL-2, AL-27, CL-2, CL-3, CL-4, JD-5, JD-8.
- Live rule (docs/data_conventions.md:20-23): "`disruption_notice.docx` and `planning_limits.docx` are Word documents (WordprocessingML packages as ECMA-376 defines them). The package relationship of type officeDocument names the main document part, and the tables are read from that part. A table cell's value is its text with surrounding spaces removed. Each table is found by its header row."
- Why it passes: IN-15 the format is named in the governing file and the standard it names fixes the rows of a table (ECMA-376 Part 1 CT_Tbl content `tr | customXml | sdt`; Part 3 keeps one branch of `mc:AlternateContent`). IN-16 one reading: the forms change markup only; `_reform` (tests/test_output.py:675) asserts the text-level undo gives back the plain document byte for byte, so every value is the plain folder's value and the expected outputs are derive() on the plain folder (old reference code byte-identical, WORK/h1_a1/digest_old.txt). IN-17 nothing in docs or instruction announces the forms (docs unchanged in harden_r1). DS-21 the reader the oracle uses (solution/solve.py:35-65) is independent of the test's text undo (`_form_plain` :665). TS-19 every hidden folder is drawn by the existing generator inside the stated bounds; the forms add no value outside them; 300 seeds per form asserted (WORK/h1_a1/gen300.py, G12). TS-23 each form is its own folder, own seed, own calls (FORMS :906); no lever assert moved into an old check (G2). TS-26 per-form checks grade different field groups (plan rows, group totals, per-check settlement, summary), the same split the old hN checks use. AL-27 `_reform` asserts the naive direct-child reading differs on every folder (BRANCH_FIRE). AL-2 no new penalty. CL-2/CL-3 Docker kill table OUT/DESIGN.md section 3 (a1 WRONG on all 33 W checks; solve_ext/oracle EXACT). CL-4 instruction.md:32-34 grades each field group exactly; one-fact-wrong cost in COST_TABLE.md.
- Weak point recorded: Word 2010 and later drop customXml tags on open (the row text stays), so h8/h11/h14 are the forms a reviewer may call dated; sdt (Word repeating section) and AlternateContent are current Word output.
- Fallback: IN-16 DO: REBUT quoting ECMA-376 Part 1 17.4.38 (tbl content) and Part 3 10.2 (AlternateContent); TS-26 DO: merge h10..h15 plan_group_totals into plan_rows if flagged; never add a docs sentence naming the forms (IN-17).

## J harden_r1 judge changes
- Dropped R6, R8, R9 (JD-8: each restated what a test grades). Added reruns_with_a_closure_added and reruns_with_a_revised_availability (now R12, R13 after the sequential renumber judge_qc J2 asks for) (P-d altered copy, JD-5 one act each, oracle shown at solve.sh P10/P11). Probe share 24/39 = 61.5% (JUDGE_MAP.md).
