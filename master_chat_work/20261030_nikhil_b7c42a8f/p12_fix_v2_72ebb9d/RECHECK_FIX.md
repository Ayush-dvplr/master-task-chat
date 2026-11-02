# RECHECK_FIX 72ebb9d (b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042, P12 fix v2)

Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (same as QC v2). BUNDLE before = 595cfde13e3f = QC copy db42563 = Tasks_INPUT (backup WORK/qc2_595cfde13e3f). Session rename: name_session.py printed `codex: no match` / `opencode: ['ses_e728f3bd5ffe4k6PH9fx7U9qwO']` (listed, not verified as this session).
Fingerprints (Always 1): pl_generator.json 0 changed or missing (only new untracked task outputs under `ayush sah tasks/`, not a fingerprinted file), qc.json 0 changed. Not UPSTREAM CHANGED.
Noise check (Always 13): PREV_QC_COPY db42563 is byte-identical to BUNDLE before; 0 noise lines, no NOISE label.
Levers (WORK/LEVERS.md, inferred): L1 column-4 paid, L2 clash cover, L3 admission bar, L4 precedence flip at the cutover, L5 reinsurer epoch split, L6 factor clip. L7 remainder tie-break 0 points, not a lever.

## Recheck table

| ID | label | rule quote (kit file:line) | evidence (bundle file:line) | decision | playbook row | effect L1..L6 | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G01-1 IN-13 | REAL | 01_Instruction_QC.md:43 "Internal consistency: the instruction must not contradict itself." | instruction.md:9 labels (ceded recoverable, settlements, PV on extended curve, grant, claims that "would then claim") vs counterfactual_parameters.md:11-35 (alae sum, want counts, shipped curve, want multiplied, column-4 paid of dropped rows) | fix: instruction.md:9 reworded pair by pair to the doc definitions | IN-13 | none x6 | n/a | instruction.md |
| G02-1 DS-21 | REAL | 02_Data_Solution_QC.md:70 "Solvable from what the agent actually receives." | attachment_rules.md:3 describes a layer walk solve.py never runs; solve.py build_ledger books the claim_adjustment_log.log layer (later line wins for 11 two-line claims) else retention, then clash cover | fix: new `## Booked layer` section in attachment_rules.md; alae_rules.md says a two-line claim takes the later line's alae | DS-21 | none x6 (L2 clash cover still applied to the booked layer) | n/a | attachment_rules.md, alae_rules.md |
| G02-2 DS-25 | REAL | 02_Data_Solution_QC.md:71 "The exact output shape is reachable." | test_output.py methodology_audit_attachment_exact needs `clash_cover_per_event`; errata_2032-04.md:3-4 never spelled it | fix: errata_2032-04.md ends "The identifier of this rule is `clash_cover_per_event`." | DS-25 | L2 none (the reading, which errata governs, is unchanged) | n/a | errata_2032-04.md |
| G03-1 TS-25/TS-26 | REAL | 03_Tests_QC.md:52 "Positive tests grade earned work, never an absence." | test_output.py output_directory_holds_exactly_ten_documents w1 earned by any clean empty dir in separate mode (stub 2/69) | fix: deleted (master choice) | TS-25 | none x6 | n/a | test_output.py, reward.toml |
| G03-2 TS-26 | REAL | 03_Tests_QC.md:53 "No intra-test double payment, in ANY pairing." | treaty_cession_walk_exact (stem|layer), paid_to_date_dollars_exact (paid|ultimate|ceded_hours), ledger_order_exact (row order) are each implied by ledger_backbone_exact (lob|cycle|ref|reinsurer|layer|ultimate|paid, row order) plus ledger_spine_exact; no unique observable | fix: all three retired, views removed from _views; P 69 to 64 with G03-1 | TS-26 / JD-14 (master chose retire; whole-document digests on hidden inputs kept) | L1 -3 (paid_to_date_dollars), L2 -5 (cession walk), L3 -9, L4 -9, L5 -1 (order), L6 -3: retired double payments only; every lever still loses its backbone/spine/extract checks | accepted (prompt: shrink from QC fix, report only) | test_output.py |
| G04-1 JD-7/JD-10/AL-6 | REAL | 04_Judge_QC.md:76 "TRUTH AGAINST THE REFERENCE SOLUTION."; :87 "Criteria must be consistent with the instruction" | judge R1-R14 carried instruction labels; R6 named the tenor-extended curve while solve.py compute_counterfactuals uses the shipped curve | fix: R1-R14 reworded to counterfactual_parameters.md; integers regenerated from one oracle run on the seeded data (WORK/cf_v2.json) | JD-7 | none x6 | n/a | judge.toml |
| G04-3 JD-8/F0d | REAL | 04_Judge_QC.md:77 "NO OVERLAP WITH TESTS. ... Same observable = overlap = fail" | old R33 (-5) judged clash-cover code graded by the layer digests; the trajectory act (errata read before attachment code) is already R18 | fix: R33 dropped (master: drop when R18 grades it); renumbered R1..R33 | JD-8 | L2 none (tests still grade it) | n/a | judge.toml |
| G04-8 JD-16 | REAL | 04_Judge_QC.md:93 "What makes a valid constraint criterion. All four must hold" (item 3 one rule) | old R32 bundled (a) online answers instruction.md:11, (b) package install, (c) HTTP hosts; type safety and boundaries | fix: kept only (a) as new R31 type instruction following, naming instruction.md:11 | JD-16 | none x6 | n/a | judge.toml |
| G05-1 CL-5/AL-3 | REAL | 05_Alignment_Integrity_QC.md:89 "every exact comparison's silent requirements (order, keys, path form, casing) either stated in the contract or compared insensitively" | output_contract.md:51, :67 never placed a null reinsurer_canonical; oracle sorts it first (CLM-00014) | fix: ":51 ... a null `reinsurer_canonical` sorts before every identifier", same at :67 | CL-5 | none x6 | n/a | output_contract.md |
| G05-2 CL-8/DS-20 | REAL | 05_Alignment_Integrity_QC.md:92 CL-8 oracle needs no fallback that skips an instruction-required step; 02_Data_Solution_QC.md:68 "The oracle obeys the contract, independently of the tests." | solve.py:1211 typed `"ay": 2032` for cession rows, :652 AY 2023 default | fix: solve.py ultimate dev year = recorded year minus claim_master.csv accident_year (KeyError loud), both fallbacks deleted; chain_ladder_rules.md:33 says so; every sealed value regenerated | DS-20 | L6 see G02-4; others none | n/a | solve.py, chain_ladder_rules.md, test blob |
| G05-3 AL-27 | REAL | 05_Alignment_Integrity_QC.md:38 "Trigger depth: a rule only counts as graded when the test's input actually constructs the situation where the rule matters." | only unresolved claim CLM-00014 had no retraction notice in shipped, A or B | fix: gen_extracts.py retract_unresolved adds `CLM-00014,2032-10-21T12:00:00Z,ON_HOLD` to extract B only (never shipped); B row now RETRACTED/RETRACTED, null reinsurer. Mutant R_retract_over_excluded loses hidden_extract_outcomes_exact, beta, summary_and_treaty_values_exact (WORK/runs/cov_v2) | AL-27 | new graded case (outcome precedence), not a lever | n/a | gen_extracts.py, test blob (B tar) |
| G05-4 AL-28 | REAL | 05_Alignment_Integrity_QC.md:39 "No penalty stacking." | pasting shipped outputs fired negative_hardcoded_sample_answers -5 and negative_embedded_corpus_rows -5 | fix: embedded check stands down when hardcode fires; easier fix same family: output_independent stands down when embedded fires (test_output.py:899) | AL-28 | none x6 | n/a | test_output.py |
| S11-1 coverage | REAL | Final_checklist.md:428 "Coverage, both directions. ... where it delegates to a spec, expand the delegation into the rules it actually invokes" | summary.json run fields, dollar totals, per-LOB fields and treaty_working ceded_by_lob / ceded_by_reinsurer_canonical read by no test; summary_claim_counts_exact description said totals were graded by digests | fix: new summary_and_treaty_values_exact w1 (shipped, A, B digest of those values); description corrected | NEW-CHECK | L1 +1, L3 +1, L4 +1, L5 +1, L6 +1 (new check also lost by these levers) | n/a | test_output.py |
| G02-3 DS-2/DS-3 (minor) | REAL | 02_Data_Solution_QC.md:18 "Necessary"; :19 "Referentially complete and truthful" | attachment_windows.csv read only by the dead walk; source_manifest.md:48 called it the windows in which each layer attaches | fix: file dropped (57 files), manifest line and corpus_index.md entry removed, dead walk_attachment_graph deleted | DS-2 | none x6 (cutover instant still in cycle_marks.csv and derivation_policy.ini) | n/a | attachment_windows.csv (deleted), source_manifest.md, corpus_index.md, solve.py |
| G02-4 DS-6 (minor) | REAL | 02_Data_Solution_QC.md:22 "Data files must make sense for the task story" | IBNR $88 on $24.97M paid; incurred about equal to paid on every row | fix: gen_extracts.py seed_development seeds incurred above paid on 120/501 young-year claim_tx rows in shipped and both extracts; total_ibnr 88 to 2032629, 66/130 cells develop | DS-6 (fixed in shipped and hidden alike) | L6 37 to 22 loss (young factors now above 1, clip bites on fewer cells; still loses 6 checks incl beta) | accepted (QC-directed data fix) | claim_tx_*.csv, gen_extracts.py, test blob |
| G03-3 TS-13 (minor) | REAL | 03_Tests_QC.md:44 "One property per test." | hidden_extract_quality_tallies_and_outcomes_exact w3 graded dq tallies and outcome digest | fix: split into hidden_extract_outcomes_exact w3 and hidden_extract_quality_tallies_exact w1 | TS-13 (see Deviations) | none x6 | n/a | test_output.py |
| G03-4 TS-20 (minor) | REAL | 03_Tests_QC.md:51 "Weights map to importance semantically." | methodology_audit_remaining_sections_exact w1 grades four audit sections vs attachment_exact w3 grading two strings | fix: remaining_sections raised to w3; attachment kept w3 (see Deviations) | TS-20 (raise the core check; never lower) | none x6 | n/a | test_output.py |
| G04-2 JD-7 (minor) | REAL | 04_Judge_QC.md:76 | R35 "no block of code is unreachable" false of oracle (dead walk) | fix: dead walk deleted; facet dropped with G04-4 | JD-7 (fix the oracle) | none x6 | n/a | solve.py, judge.toml |
| G04-4 JD-5 (minor) | REAL | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour" | R35 four facets | fix: new R33 "no function is longer than 200 lines" only (KEPT-3 cap; oracle main 192 lines) | JD-18 / JD-5 | none x6 | n/a | judge.toml |
| G04-5 JD-15 (minor) | REAL | 04_Judge_QC.md:92 | R22 reads layer_capacity_declarations.csv, a conduct act labelled instruction following | fix: type agent behavior | JD-15 | none x6 | n/a | judge.toml |
| G04-7 JD-16 item 4 (warn) | REAL | 04_Judge_QC.md:93 item 4 not test-settled | old R25 stdlib imports is settled by reading the file | fix: moved to test module_imports_only_standard_library w1 (sys.stdlib_module_names, python 3.12); R25 dropped | JD-16 / NEW-CHECK | none x6 | n/a | test_output.py, judge.toml |
| TS-16 note (v2.md:208, no id) | REAL | 03_Tests_QC.md:47 "Anti-cheat negatives must fire on the cheat and ONLY on the cheat." | network negative missed bare `import http` named in instruction.md:3 | easier fix: banned imports = the instruction's list incl `http` | TS-16 | none x6 | n/a | test_output.py |
| R34 evaluation_target (easier fix) | REAL (same F0d as G04-3) | 04_Judge_QC.md:77 | old R34 judges the delivered file under trajectory | fix: new R32 evaluation_target state_change | JD-15 | none x6 | n/a | judge.toml |
| G05-5, G04-6, KEPT-3, KEPT-4, KEPT-5 | acknowledged | see KEPT.md | carry-overs | KEEP (KEPT.md rows 1-5) | TS-23 / CL-4 | none | n/a | none |

Counts: 13 fail + 7 minor + 1 warn = 21 REAL, 0 FALSE_POSITIVE, 0 UNSURE; 21 fixed, 0 new KEEPs, 5 acknowledged carry-overs kept.

## Gate results

- xref_check: 40 entries, 0 findings (before and after).
- precheck.sh: `PRECHECK CLEAN` (tests 31, criteria 33; warns JD-5 multi-clause, IN17 phrases, SELF_CHECKS.md note).
- G7 byte diff (WORK/G7_v2_tests_diff.txt): generator regen changed only test_output.py:23 (_EXPECTED_BLOB) and :26-27 (A/B tars).
- Tests P 64 (24 positive), negatives -23 (7); judge 33 criteria, positives 65 (27), negatives -24 (6); reward.toml 0.5/64 = 0.0078125, 0.5/65 = 0.007692307692307693.
- Docker block 1 (TS 20261030T212453-5f14): oracle 1.0 x3, owner 1.0, nop 0.0, replay AFTER 0.125, replay BEFORE 0.1159.
- Docker block 2 on final bytes (after the 21:35 AL-28 edit, TS 20261030T213223-9777): oracle 1.0 x3, owner 1.0, nop 0.0, replay AFTER 0.125 (jobs /tmp/harbor-jobs-b7c/b7c4-<name>-20261030T213223-9777).
- TRUTH.md by write_truth.py last (80 lines).

## Deviations from master directions

- G03-3 TS-13 split: playbook says the halves share the original weight 3, but kit W2 allows only odd weights (1, 3, 5), so no two halves sum to 3. Outcomes (the harder half, AL-27 cases) kept w3, tallies w1; P +1.
- G03-4 TS-20: QC Fix said swap the weights; playbook TS-20 NEVER lowers a lever check (attachment_exact carries the L2 identifier), so remaining_sections raised 1 to 3 and attachment kept at 3.
- G02-3: "drop" option taken (file deleted) instead of describing it, since only dead code read it.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| summary_and_treaty_values_exact (new) | NEW-CHECK S11-1 | TS-25, TS-13, TS-14, TS-26 | PASS: vacuity 0; one observable (non-ledger summary/treaty values); description true; values not in any ledger digest (test_output.py _summary_values) |
| module_imports_only_standard_library (new) | moved from judge R25 | TS-25, TS-14, JD-8 | PASS: empty out earns 0; judge no longer grades it (judge.toml has no stdlib criterion) |
| hidden_extract_outcomes_exact / hidden_extract_quality_tallies_exact | TS-13 split | TS-25, TS-15 | PASS: both earn 0 on vacuity; mutants each lose their half (RULE_COVERAGE.md 72ebb9d) |
| methodology_audit_remaining_sections_exact | weight 1 to 3 | TS-20 | PASS: four audit sections on shipped, A, B = important sub-goal |
| negative_embedded_corpus_rows, negative_output_independent_of_the_corpus | stand down on earlier negative | AL-28, TS-16 | PASS: one act, one layer; each still fires alone on its own cheat |
| negative_module_opens_network_or_shells_out | `http` added | TS-16, TS-14, TS-15 | PASS: list = instruction.md:3 list; oracle and replay not fired |
| judge R1-R14 | reworded + new ints | JD-7, JD-10, J3a, J10 | PASS: ints = cf_v2.json oracle run; labels = counterfactual_parameters.md |
| judge R22 | type relabel | JD-15, JD-9 | PASS: agent behavior |
| judge R31 (old R32) | narrowed to (a) | JD-16, JD-15 | PASS: one rule, instruction.md:11 |
| judge R32 (old R34) | target state_change | JD-15 | PASS |
| judge R33 (old R35) | one judgement, 200-line cap | JD-5, JD-7, JD-15, JD-2, JD-9, IN-8 | PASS: oracle longest function main 192 lines |
| solve.py develop_chain_ladder | AY from claim_master | DS-20, CL-8, DS-19 | PASS: chain_ladder_rules.md:33 states it; oracle 1.0 |

## Vacuity probe

Empty /app/out graded by BUNDLE tests (WORK/runs/vacuity_v2/grade.json): P 64, earned 0, no negative fired, score 0.0. PASS.

## Side effects

| FIX id | ids re-checked | result |
|---|---|---|
| JD-5 (G04-4) | JD-15, JD-2, JD-9, JD-7, IN-8 | PASS (R33 conduct label, oracle meets cap, satisfiable) |
| JD-7 (G04-1, G04-2) | JD-15 | PASS |
| JD-15 (G04-5, R34) | JD-9 | PASS |
| TS-13 (G03-3) | TS-25, TS-15 | PASS |
| TS-16 (note) | TS-14, TS-15 | PASS |
| TS-26 (G03-2) | TS-14 | PASS (remaining descriptions name only what they grade; alpha/beta descriptions updated) |
| AL-27 (G05-3) | TS-13 | PASS (case graded by outcomes half only) |
| STEP11 (G03-1) | TS-25, TS-13, TS-14 | PASS (stub check gone; vacuity 0) |
| DS-6 / DS-20 data and oracle change | DS-22 | PASS (TRUTH.md regenerated last; precheck CLEAN) |

## Noise keeps

None: BUNDLE before was byte-identical to the QC copy db42563 (0 noise lines).

## Trap survival

WORK/runs/trap_v2_before (P 69) vs trap_v2_after (P 64); no negative fired on any variant.

| lever | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| L1 column-4 paid | 43 | 39 | 0.91 | backbone, spine, cells, chain ladder, dq anomaly, tallies, alpha, beta, perm, treaty breakdown, summary values | survives |
| L2 clash cover | 26 | 21 | 0.81 | backbone, alpha, beta, perm, treaty breakdown | survives (lost the retired cession walk w5) |
| L3 admission bar | 46 | 41 | 0.89 | 13 checks incl hidden outcomes, tallies, alpha | survives |
| L4 precedence flip | 50 | 45 | 0.90 | 13 checks incl alpha, beta | survives |
| L5 epoch split | 19 | 19 | 1.00 | backbone, alpha, beta, perm, summary values | survives |
| L6 factor clip | 37 | 22 | 0.59 | chain ladder, backbone, spine, beta, summary values, treaty breakdown | survives, shrunk by G02-4 seeding (young factors above 1) and retired paid view; accepted as QC fix |

## QC_RULINGS rows

- G03-3 | TS-13 | outcome digest and dq tallies in one w3 check | REAL | REAL | split; kit W2 forbids a weight-sharing split of 3
- G03-4 | TS-20 | four audit sections w1 below two attachment strings w3 | REAL | REAL | raise core check, never lower the lever check
- G03-1 | TS-25/TS-26 | ten-documents existence check | REAL | REAL | earned by an empty clean run
- G03-2 | TS-26 | layer, dollars, order sub-views beside the backbone digest | REAL | REAL | each view implied by backbone plus spine
- G05-4 | AL-28 | hardcode and embedded negatives both fire on pasted outputs | REAL | REAL | one act one layer; extended to embedded and output-independent
- G04-1 | JD-7 | R1-R14 labels from instruction not oracle | REAL | REAL | doc definitions are the oracle quantities
- G04-2 | JD-7 | R35 unreachable-code facet | REAL | REAL | oracle carried a dead walk
- G04-5 | JD-15 | R22 reading a file labelled instruction following | REAL | REAL | conduct act

## Score band

Saved teammate run replayed on BEFORE (595cfde13e3f) and AFTER bundle; judge read per criterion against the saved trajectory and closing message.

| bundle | tests | judge (reading) | predicted final |
|---|---|---|---|
| BEFORE | 8/69 = 11.59% (replay 0.1159) | 17/66 = 25.76% | 18.68 |
| AFTER | 8/64 = 12.50% (replay 0.125) | 16/65 = 24.62% | 18.56 |

Moved -0.12. Movers: G03-1/G03-2 (P 69 to 64; ten-docs check -1 earned), G04-7 (stdlib moved from judge to test: test +1, judge -1 and 66 to 65), G04-3/G04-4 (negative dropped, not fired; 200-line cap earned both rounds). R1-R14 integers changed, but the saved closing integers matched none before or after.

## Lessons for the master

- A weight-sharing TS-13 split is impossible for weight 3 under kit W2 | template_change: QC_FIX_PLAYBOOK_v3.md TS-13 row (say "closest W2 pair, harder half keeps the weight")
- Retiring a test identifier from docs (fix v1) recreated DS-25 one round later | template_change: QC_FIX_PLAYBOOK_v3.md TS-26/JD-14 row (check every graded literal is still spelled in data after a retire)
- Near-zero development in seeded data hid the CL-8 AY fallback until QC | no change: DS-6 already covers it
- A judge integer label copied from the instruction drifts from the parameter doc | no change: JD-7 already covers it
