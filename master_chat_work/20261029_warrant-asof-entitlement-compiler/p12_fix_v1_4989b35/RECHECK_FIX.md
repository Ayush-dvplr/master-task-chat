No doc and no instruction.md change (environment/data and instruction.md byte-identical to QC copy bdd41f8).

# RECHECK_FIX warrant-asof-entitlement-compiler (P12, board 4989b35)

QC report: /Users/mac/Desktop/Terminal Bench/QC/reports/warrant-asof-entitlement-compiler/v1.md (FAIL 11/4/5). Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271, all rule IDs and wordings found unchanged at the lines below. Bundle before = QC copy bdd41f8 (tree 95232d923d75), so no cited line differs from PREV_QC_COPY; this is the first QC round of the bundle, so no finding qualifies as NOISE (no earlier pass of the same check). Backup: WORK/qc1_95232d923d75.

Lever (LEVERS.md): per-corpus gateway conventions (hr clock H, grant start S, window boundary W) inferred from access_attestations.csv; 8 conv tiers x dev/prod = 80 test points.

## Findings

| # | ID | label | rule quote (kit file:line) | evidence (bundle file:line) | decision | playbook row | effect H / S / W | compensation | files changed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | IN-12 / AL-26 | REAL | 01_Instruction_QC.md:42 "`[metadata] category` must name that dominant kind of work ... (a Debugging task with a security flavour declared as \"Security\" fails)"; same at 05_Alignment_Integrity_QC.md:59 | task.toml:12 `category = "Security"`; instruction.md:1-3 is repair of a drifted CLI to a written contract | FIX: `category = "Software Engineering"`; keywords keep the security words | IN-12 DO | none / none / none | none | task.toml |
| 2 | DS-20 | REAL | 02_Data_Solution_QC.md:68 "The oracle obeys the contract, independently of the tests ... Walk the oracle's logic against every rule the contract states" | access_contract.md:40 "Every window in this contract (memberships, bindings, grants, shifts, freeze windows, contract cover, key values) follows the one boundary convention the gateway enforces."; oracle only routed grants and key values (solve.py FIXES freeze `lo <= start < hi`, bindings `lo <= self.E < hi`, membership `added <= self.E < removed`); verifier the same (test_output.py:578, :623, :663, :812, :949 hard half-open) | FIX both sides: oracle adds `Compiler.inw` and routes contract cover, memberships, bindings, freeze windows and on-call shifts through the settled window; `variant()` rebuilds memberships and bindings when the window reading changes (solve.py, 8 new FIXES entries). Verifier `World.inw` routes the same five windows (grants already routed, now through `inw`). Half reading gives byte-identical results by construction | DS-20 DO (fix oracle, add graded hidden case = row 11) | none / none / harder | n/a | solution/solve.py, tests/test_output.py |
| 3 | DS-27 | REAL | 02_Data_Solution_QC.md:80 "TRUTH.md describes the task, not how the task was made" | solution/TRUTH.md:55 "Reference authoring: the shipped tool is the reference implementation with these defects injected" | FIX: line rewritten as a task fact (repair in place, independent recomputation in the verifier), by script | DS-27 DO | none | none | solution/TRUTH.md |
| 4 | TS-17 | REAL | 03_Tests_QC.md:48 "Comparisons are exact where the instruction promises exactness ... Watch the Python trap where `True == 1`" | test_output.py:29988, :29990, :30063 dict `!=`/`==`; config_contract.md:20 "an integer key takes JSON integers only, a boolean key JSON booleans only" | FIX: `_same(a, b)` compares `json.dumps(sort_keys=True)` texts (bool and int differ); used for config, summary, self check, reproduce and the new checks | TS-17 DO | none | none | tests/test_output.py |
| 5 | JD-7 / AL-4 / AL-6 | REAL | 04_Judge_QC.md:76 "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle"; 05:35 AL-4; 05:37 AL-6 | judge.toml:118 R9 "... a missing or malformed declared input stops the run with a message naming the file."; cli_contract.md:14 promises only non-zero exit and no output file; oracle gateway.py `except wtime.BadTime: continue` skips an observation row with an unreadable instant, which time_rules.md:5 names ("a record carrying one in a field the compiler must read is rejected `bad_timestamp`") | FIX: input-error clause dropped (graded by negative_partial_output_on_missing_input); handler clause reworded so rejecting or skipping a record under a rule an /app/data contract names counts as acting on the error. True of the oracle (engine BadTime handlers record `bad_timestamp`, policy.py rejects, cli.py exits 2 on CorpusError, gateway skip is the time_rules.md:5 rejection). Weight 3 kept | JD-7 DO (fix criterion to the oracle) | none | none | tests/judge.toml |
| 6 | JD-14 | REAL | 04_Judge_QC.md:91 "No double payment inside the file, in ANY pairing" | judge.toml:222 R17 vs R1 :14, R2 :27, R3 :40 (same comparison observable) | FIX: R17 deleted; it was last, so no renumber needed after it (R16 moved, see row 8 and Touched rules) | JD-14 DO (delete) | none (R1-R3 keep paying the comparison) | none | tests/judge.toml |
| 7 | JD-16 | REAL | 04_Judge_QC.md:93 "What makes a valid constraint criterion. All four must hold" | judge.toml:170 R13 "The agent runs a package install or an online lookup during its run." vs instruction.md:9 "Use only the Python standard library, install nothing, and do not look anything up online." | FIX: split into R13 "The agent runs a package install command during its run." and R14 "The agent runs an online lookup during its run.", -1 each, type instruction following, each quoting instruction.md:9 | JD-16 / JD-5 DO | none | none | tests/judge.toml |
| 8 | JD-13 | REAL | 04_Judge_QC.md:90 "judge the labels and magnitudes semantically" | judge.toml:209 R16 (success claim against a failed run) -1 important vs :196 R15 -3 critically_important | FIX: now R17 claims_success_against_evidence -3 critically_important; negative sum 15 <= positive 26 | JD-13 DO | none | none | tests/judge.toml |
| 9 | CL-4 | FALSE_POSITIVE | Final_checklist.md:491 "One wrong fact should cost about one fact's worth of reward" and the same item: "An instruction that states out loud that only an exact match counts has set that bar deliberately." | instruction.md:7 "A profile, a list in the validation report, the self check, the configuration and the summary each count only when every unit in them is exact: one wrong key, value, entry or count makes that part wrong." Unit of grading = one part per corpus per env (each conv check 5/155); a wrong rule that touches every corpus is a wrong fact repeated on every corpus | REBUT (per-tier table below); QC_RULINGS Q3 (stated all-corpora gate is fine when the keys are named in the contract) | CL-4 REBUT | none | none | none |
| 10 | AL-2 | REAL | 05_Alignment_Integrity_QC.md:33 "Everything promised is graded. Enumerate from `instruction.md` alone ... follow the pointer" | instruction.md:3 "take everything from --data and --config"; cli_contract.md:12 "Every setting except the file layout comes from the `--config` file, anchors included"; `_run_all` feeds the tool's own config (test_output.py:29839-29843); output_contract.md:3 serialization and :26 list orders ungraded (`_rows` sorts) | FIX: `altered_config_outputs_exact` w3 (tier_b compiled and audited under a --config with anchors 2 days earlier and another prod.approvals_required, dev/prod profiles and every validation-report part compared with the verifier's recomputation under that config); `artifacts_contract_layout` w1 (each JSON artifact byte-equal to the contract serialization; validation-report lists in the contract orders with no exact repeats; summary inputs sorted) | AL-2 DO (grade through observable on hidden inputs) | none | none | tests/test_output.py |
| 11 | AL-27 | REAL | 05_Alignment_Integrity_QC.md:38 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" | CONV_TIERS all window half (test_output.py:29766, :29777); SHIPPED_CONV half | FIX: conv_2, conv_6, conv_8 planted with window closed (CONV_TIERS 4-tuples); generator plants freeze windows that end exactly on an approved ticket's start in closed tiers; observe() keeps killing the half rival on each (window kills 2 per tier); WORK/RULE_COVERAGE.md written | AL-27 DO | none / none / harder (W wrong now loses 30 points, P7w on t7; was 0); conv_6 reseeded 98053 -> 98123 so the start reading is planted there too (Deviations) | n/a | tests/test_output.py |
| 12 | TS-13 / TS-20 | REAL | 03_Tests_QC.md:44 "One property per test"; 03:51 "Weights map to importance semantically" | config_resolution_exact :29985-29992 w3 shipped + 3 unseen; summary_identity_triangle w5; profile_dev_values_exact w3 vs prod values w5 | FIX: split into config_shipped_exact w1 + config_heldout_resolution_exact w3 (kit W2 allows only 1/3/5, see Deviations); profile_dev_values_exact 3 -> 5; summary_identity_triangle 5 -> 3 | TS-13 split sharing weight + TS-20 raise core | none (lever 80 kept) | none | tests/test_output.py, tests/reward.toml (test_output weight 0.5/155) |
| 13 | JD-5 | REAL | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour" | judge.toml:118 R9 two observables | FIX: same edit as row 5 (second observable dropped, already graded by negative_partial_output_on_missing_input) | JD-5 DO | none | none | tests/judge.toml |
| 14 | JD-15 (R6) | REAL | 04_Judge_QC.md:92 | judge.toml:79 R6 perturbing decided_at at weight 3 | FIX: weight 3 -> 1, wording kept | JD-15 relabel/reweight | none | none | tests/judge.toml |
| 15 | JD-15 (R8) | REAL | 04_Judge_QC.md:92 | judge.toml:105 R8 count of readings at weight 3 | FIX: weight 3 -> 1 | JD-15 | none | none | tests/judge.toml |
| 16 | X1 | FALSE_POSITIVE (warn) | structure_qc.py:71 "X1 no em/en dash in any text file; binary-skipped files warn." | environment/data/tool.zip is the legacy tool archive the task repairs; its text members carry no dash (QC gate 02 read them) | KEEP | SUGGEST/NOISE keep with evidence | none | none | none |
| 17 | TS-23 / A3 | REAL warn, KEEP | 03_Tests_QC.md:62 "at most 35 (warn)" | 47 checks after the splits; conv dev/prod checks are distinct corpora and envs (no duplicates: each tier has its own seed and readings) | KEEP with count (Ayush 24 Oct 12:50, option A 27 Oct: never merge or drop to get under 35) | TS-23 KEEP | none | none | none |
| 18 | TS-24 | REAL | 03_Tests_QC.md:68 "If any check in test_output.py executes agent-produced code, verify all of the following" | test_output.py:29826 `subprocess.run(... timeout=900 ...)` no process group kill | FIX: `_invoke` uses Popen(start_new_session=True), communicate(timeout), killpg SIGKILL on timeout and after return (ProcessLookupError/PermissionError ignored); setpriv nobody kept; same return values | TS-24 DO | none | none | tests/test_output.py |
| 19 | TS-27 | REAL | 03_Tests_QC.md:43 "Reading the agent's source is not proof" | report_transcript_complete :30068-30098 w3 trusts reported return codes | FIX: weight 3 -> 1 and cross-check with the verifier's own run of the delivered tool on the shipped corpus (all five commands exit 0) | TS-27 DO | none | none | tests/test_output.py |
| 20 | AL-17 | REAL | 05_Alignment_Integrity_QC.md:74 "verifier timeout plausible for what test.sh does" | per-call 900 s over about 80 calls vs verifier 2700 s | FIX: per-call 450 s (reference slowest call measured 111.6 s, audit, in python:3.12-slim 4g/2cpu (p12/runs/s3_eng1.txt); above 30 s, so 4 x 111.6 = 446, rounded to 450) and a global 2400 s budget after which calls return None (checks fail, reward still written) | AL-17 DO | none | none | tests/test_output.py |
| 21 | Step 10 (oracle x3) | KEEP | Ayush rule (oracle x3) | report Step 10 | KEEP | KEPT row | none | none | none |

## CL-4 per-tier table (row 9 REBUT)

Each conv tier is graded as two parts (dev profile, prod profile), each 5 of 155. A program with one convention reading wrong loses only the tiers on which that reading was planted, and on each such tier only the parts it changes. Measured on the final tests (t7): column A = the verifier reference with every window half open and everything else right (p12/runs/exp2_t7.txt, differing units dev/prod); column B = kill program P7w end to end (hr and start inferred, window fixed half; p12/runs/s6_P7w.txt).

| tier | planted (hr, start, window) | dev part | prod part | A: window-only wrong, units dev/prod -> parts lost | B: P7w lost |
|---|---|---|---|---|---|
| conv_1 | zone:Site/Dune, requested, half | 5 | 5 | 0 | 0 (half) |
| conv_2 | zone:Site/Dune, requested, closed | 5 | 5 | 12/137 -> 10 | 10 |
| conv_3 | zone:Site/Ember, requested, half | 5 | 5 | 0 | 0 (half) |
| conv_4 | zone:Site/Cobalt, requested, half | 5 | 5 | 0 | 0 (half) |
| conv_5 | zone:Site/Brisk, requested, half | 5 | 5 | 0 | 0 (half) |
| conv_6 (seed 98123) | zone:Site/Brisk, requested, closed | 5 | 5 | 20/0 -> 5 | 10 |
| conv_7 | zone:Site/Arden, requested, half | 5 | 5 | 0 | 0 (half) |
| conv_8 | zone:Site/Arden, requested, closed | 5 | 5 | 105/59 -> 10 | 10 |

One wrong fact (the window reading) costs 25/155 = 16.1% when everything else is right, spread over the five parts it actually changes (P7w loses 30 because no world fits its fixed half window on the closed tiers and it falls back to the shipped readings); a wrong hr or start reading is wrong on every corpus because every corpus plants its own zone and the requested start, and instruction.md:7 states that one wrong key makes that part wrong. Final_checklist.md:491 accepts an exact bar the instruction states out loud; QC_RULINGS Q3 accepts a stated all-corpora gate when the keys are named in the contract (access_contract.md:40, corpus_index.md:53).

## Deviations from master directions

- G08 (AL-2, TS-13/20) asked for config_shipped_exact w2 + config_heldout_resolution_exact w2 and the altered-config check at w2. The kit gate tests_qc W2 fails any weight outside [-5, -3, -1, 1, 3, 5] (precheck at 09:44: `FAIL [W2] weight 2 must be integer literal in [-5,-3,-1,1,3,5]`). Used config_shipped_exact 1 + config_heldout_resolution_exact 3 (sum 4 vs old 3; held-out resolution is the core) and altered_config_outputs_exact 3. Positive total 155 (the w2 plan would have given 154), lever share 80/155 = 51.6%.
- G08 altered check compares compile AND audit outputs (direction says "compile and audit"), hence the name altered_config_outputs_exact.
- G08 altered check leaves out the policy_change_journal.jsonl rows and the journal self-check counts: under a --config whose recorded_cutoff differs from the corpus anchor, the contract does not say whether journal visibility follows the passed cutoff or the corpus anchor (a1 and two blinds got every profile and every other audit row exact and differed only there, p12/dbg_alt.py), so grading it would grade an unstated reading.
- G02: conv_6 reseeded 98053 -> 98123 (same zone, same closed window). At 98053 no start reading changed any output (p12/exp8.py: decided, recorded and latest each 0/0 differing units), so the start-wrong kill row P4o passed conv_6 and kept only 70/80 of its lever loss (87.5% < 90%). At 98123 decided/recorded/latest differ by 10/12, 21/12, 7/1 units (p12/runs/exp9.txt) and the unique fit still holds (UNIQUE_FIT.md).
- Re-scoring: master stopped the session at 10:23 and killed s3 (P3b, P6o) and s5; P3b, P6o, P7w were re-scored on the final tests (t7) instead of t4. The three blind delivered dirs lived under /tmp/blind, which was cleared, so the blinds could not be re-run on conv_6 at seed 98123; their after-scores come from s3 + s4 (t6 checks, final weights) with conv_6 counted lost, which it was at 98053 and which their stated fixed readings (site clock, decided start, half windows) cannot pass at 98123 either (exp9: site clock 950/536, decided start 10/12 differing units).
- P7w (window fixed half) calls take about 370 s each, so its full run was stopped and its closed-window tiers were scored with the 2400 s verifier budget lifted (harness BUDGET env, p12/runs/s6_P7w.txt), so the lever and not the budget decides.
- G02: contract cover and on-call shift windows are routed on both sides but not planted at a boundary (no conv tier puts as_of on a local midnight of a contract end or on a rota boundary); the direction's list (memberships, bindings, freeze windows, grant ends) is planted. WORK/RULE_COVERAGE.md records which mutants fail which checks.

## Side effects

FIX_SIDE_EFFECTS.md (qc_reverse/B) rows for the ids fixed here, each re-checked on the edited bundle:

| FIX id | ids re-checked | result |
|---|---|---|
| JD-5 (R9 split/drop) | JD-15, JD-2, JD-9, JD-7, IN-8 | JD-2 PASS (no banned token in any of 17 descriptions, script over judge.toml); JD-7 PASS (R9 true of the oracle, row 5); JD-15 PASS (R9 is the one JD-18 code-quality criterion, conduct, w3 kept); JD-9 PASS (process share unchanged except R6/R8 w1); IN-8 PASS (dropped clause removes a demand, adds none) |
| JD-7 (R9 reword) | JD-15 | PASS: R9 stays a conduct criterion on the delivered code, not a hidden convention |
| JD-15 (R6, R8 -> w1) | JD-9 | PASS: both kept as trajectory criteria, only weight changed |
| TS-13 (config split) | TS-25, TS-15, TS-14 | TS-25 PASS (both halves compare present artifacts / tool runs with the recomputation; missing output fails); TS-15 n/a (positives); TS-14 PASS (names state the property, no negative_ prefix, descriptions match bodies) |
| AL-2 (two new checks) | TS-25, TS-26, TS-17, TS-16, TS-24, IN-8 | TS-25 PASS (altered check needs the tool's outputs to equal recomputed values; layout check reads the six JSON artifacts and fails when any is missing); TS-26 PASS (altered = profiles and audit under another config, heldout_resolution = resolve-config output, parse_shapes = shapes, layout = bytes and list order: four observables); TS-17 PASS (`_same`); TS-16 n/a; TS-24 PASS (through the new `_invoke`); IN-8 PASS (cli_contract.md:12, output_contract.md:3, :26) |
| AL-27 (closed tiers) | TS-13 | PASS: the conv checks stay one tier x one env each; no check gained a second property |
| TS-24 / AL-17 (`_invoke`) | TS-19, TS-17 | TS-19 PASS (oracle calls 0.3 to 111.6 s vs 450 s cap; oracle passes every check in s3_eng1); TS-17 unaffected |
| DS-20 / AL-27 (World.inw) | DS-21, IN-16, DS-22 | DS-21 PASS (rule is access_contract.md:40, already shipped); IN-16 PASS (UNIQUE_FIT S3: 1/56 readings fit on conv_2/6/8); DS-22 PASS (TRUTH regenerated by script last, fix_patch_sha256 / solve_py_sha256 rewritten) |

NEW-CHECK hygiene for config_shipped_exact, config_heldout_resolution_exact, altered_config_outputs_exact, artifacts_contract_layout: TS-13 one property each; TS-25 earned; TS-14 names match; TS-16 n/a (positives); TS-26 distinct observables (above); TS-17 strict `_same`; TS-24 via `_invoke`. Precheck after all edits: `PRECHECK CLEAN`.

## Noise keeps

None. Bundle before = QC copy bdd41f8 (tree 95232d923d75); this is the bundle's first QC round, so no finding repeats an earlier pass.

## QC_RULINGS rows

| finding | rule | our design | QC verdict | our label | reason |
|---|---|---|---|---|---|
| 12 | TS-13 | config_resolution_exact checked shipped config + three unseen configs in one check | FAIL | REAL | two properties (artifact vs resolution on unseen corpora); split per playbook TS-13 |
| 12 | TS-20 | profile_dev_values_exact w3 while prod values w5; triangle w5 | FAIL | REAL | importance mapping inverted; raised core, lowered triangle, lever untouched |
| 5 | JD-7 | R9 demanded a file-naming message the oracle never prints, and called the gateway skip an unhandled error | FAIL | REAL | criterion fixed to what the contract promises and the oracle does |
| 14 | JD-15 | R6 (re-run on altered decided_at copy) w3 | minor | REAL | method habit, not core outcome; w1 |
| 15 | JD-15 | R8 (counts fitting start readings) w3 | minor | REAL | same; w1 |

No findings on IN-15, IN-16, TS-19, TS-26 or AL-28 in v1.

## Touched rules

| id | touched how | rules re-checked | verdict file:line |
|---|---|---|---|
| IN-12 | task.toml:12 category -> Software Engineering | IN-12, AL-26 | PASS task.toml:12 |
| DS-20 | solve.py 8 FIXES (inw, cover, membership, binding, freeze, on-call, variant) | DS-20, JD-7, DS-22 | PASS solution/solve.py FIXES tail; repaired engine passes every positive check (s3 at t4, s4 altered at t6, s5 conv_6 at t7); Harbor gate below |
| DS-20 / AL-27 | test_output.py World.inw (:563) routing :583, :628, :668, :817, :954, :991 | DS-20, DS-21, IN-16, AL-27 | PASS (identity.txt half tiers unchanged; UNIQUE_FIT 1/56) |
| AL-27 | CONV_TIERS 4-tuples, plant_freeze_ends before build() | AL-27, IN-16, DS-4 | PASS (window kills 2 per closed tier; only freeze_windows.json rows appended, no answers) |
| TS-17 | `_same` in summary, config, self check, reproduce, tier and conv profile compares | TS-17, TS-25 | PASS tests/test_output.py `_same` |
| TS-13 / TS-20 | config split, dev values 5, triangle 3 | TS-13, TS-20, TS-25, TS-14, W2 | PASS registrations block |
| AL-2 | altered_config_outputs_exact (3), artifacts_contract_layout (1) | AL-2, TS-25, TS-26, IN-8 | PASS tests/test_output.py:30076, :30123 |
| TS-24 / AL-17 | `_invoke` Popen + killpg, per call 450 s, budget 2400 s | TS-24, AL-17, TS-19 | PASS tests/test_output.py `_invoke` |
| TS-27 | report_transcript_complete w1 + own-run cross-check | TS-27, TS-26 | PASS |
| JD-5 / JD-7 | R9 reworded, one clause | JD-5, JD-7, JD-2, JD-18 | PASS tests/judge.toml R9 |
| JD-16 | R13 split into R13 install, R14 online lookup | JD-16, JD-15, IN-15, JD-2 | PASS (instruction.md:9) |
| JD-14 | old R17 deleted, R14-R16 renumbered to R15-R17 | JD-14, J2 sequential ids | PASS R1..R17 sequential |
| JD-13 | R17 success-against-evidence -3 critically_important | JD-13, AL-28 | PASS (R16/R17 disjoint triggers; STACKING_CHECK.md by-hand) |
| DS-27 | TRUTH.md:55 line rewritten by script | DS-27, DS-22 | PASS solution/TRUTH.md |

## Vacuity probe

- Tests: the unedited shipped tool.zip with the shipped data was run through every check by script (WORK/p12/runs/s3_legacy.txt, harness score.py, tests at t4; t6 differs only in the altered check, which still needs a compile that exits 0). Calls: resolve-config rc 0, compile dev/prod rc 1, audit rc 1, summarize rc 2. Result -1/154: no positive check passed; only negative_legacy_tool_delivered (-1) fired. PASS.
- New checks alone: altered_config_outputs_exact reference outputs differ from the standard-config outputs on tier_b (p12/exp6.py, exp7.py: dev keys 3882 vs 4030, prod 2663 vs 2758, held_grants 39 vs 32, unattested 538 vs 676, sod 321 vs 314), so passing the standard run does not pass it. The closed-window tiers: the old oracle (eng0, every window half open) loses conv_2 prod, conv_6 dev/prod, conv_8 dev/prod (s1: 127/152).
- Judge: for an agent that changes nothing, R1-R8 need an action in the trajectory (window-end comparison, HR clock test, approval derivation, nested-group test, first run, altered re-run, outside recompute, reading count), R9 needs a repaired /app/out/tool.zip, R10 needs a closing message naming the conventions. None can be true. PASS.

## Re-score before / after

Scorer: WORK/harness/score.py (BLIND_BRIEF), Docker 4g/2cpu. Before = harden figures (152 positive). After = final tests (t7, 155 positive). Files: WORK/p12/runs/s3_*.txt, s3r_*.txt, s4_*.txt, s5_*.txt, s6_P7w.txt.

| program | before | after | lever loss before | lever loss after | note |
|---|---|---|---|---|---|
| a1_program | 47.4 (72/152) | 48.4 (75/155) | 80 | 80 | gains only new non-lever checks (altered 3, layout 1); conv_6 at 98123 fails (s5) |
| blind 92419ce | 45.4 (69/152) | 46.5 (72/155) | 80 | 80 | s3 + s4 at t6; conv_6 at 98123 not re-run (/tmp/blind cleared), counted lost |
| blind 787e598 | 47.4 (72/152) | 48.4 (75/155) | 80 | 80 | as above |
| blind b6c896c | 47.4 (72/152) | 48.4 (75/155) | 80 | 80 | as above |
| P0s fixed | 47.4 | 45.2 raw / 48.4 lever-only | 80 | 80 | raw also loses 5 harness artifacts (kill cli: no --config anchors, no trailing newline, synthetic repairs) |
| P2n (H wrong) | 47.4 | 45.2 raw / 48.4 lever-only | 80 | 80 | s3 t4 + s5 conv_6 |
| P3b | 47.4 | 45.2 raw / 48.4 lever-only | 80 | 80 | s3r on t7 |
| P4o (S wrong) | 47.4 | 45.2 raw / 48.4 lever-only | 80 | 80 | t4 passed conv_6 (98053 start-insensitive) -> reseeded; t7 conv_6 fails (s5) |
| P7w (W wrong) | 100 on window (lost 0) | loses 30 | 0 | 30 | s6, budget lifted |
| P6o (exact) | 100 | 96.8 raw (150/155) | 0 | 0 | loses only the 5 harness-artifact points |

Percentages move only by the new non-lever checks: +3 altered, +1 layout, +3 total positive (152 -> 155), about +1.0 point per row. No lever loss shrank. Lever share 80/155 = 51.6%. Timeout share 0% (no scored row lost a check to a timeout). Verifier worst measured: P4o 1453 s (t4), P6o 1385 s (t7), oracle engine 1144 s; all under 2430 s. Pred final (0.5 tests + 0.5 judge, a1 judge 7/26 = 26.9): low 36.7, mid 42.7, high 45.4.

## Trap survival

| lever | before loss | after loss | kept | verdict |
|---|---|---|---|---|
| H (HR clock zone) | 80 (P2n) | 80 (P2n) | 100% | PASS |
| S (grant start) | 80 (P4o) | 80 (P4o, after conv_6 reseed) | 100% | PASS |
| W (window boundary) | 0 (never planted) | 30 (P7w) | n/a, grew | PASS |
| fixed readings | 80 (P0s, a1, P3b) | 80 | 100% | PASS |

## Lessons for the master

- A tier planted for one convention can be blind to another: conv_6 at 98053 never separated start readings; only a single-lever kill row (P4o) showed it. Check every tier per convention, not per bundle.
- Kill programs that fall back to the best-agreeing reading can hide a lever; a fixed-window program on closed tiers measured 30, not 0.
- Kit W2 forbids weight 2; directions asking for w2 need a 1/3 split.
- /tmp blind outputs vanish; copy blind deliveries into WORK when they are scored.
- The altered-config check had to drop journal rows: the contract is silent on whether journal accounting follows a passed-in recorded_cutoff.

## Gate results
Final BUNDLE tree bd90fad58ff0. One Harbor block (WORK/p12/runs/gate4.log, 12:34-13:42 IST), copies built by the kit's exe_copy.py from the final BUNDLE, verifier image warmed first, 2 lanes.

| run | reward | wall s | verifier s |
|---|---|---|---|
| oracle-1 | 1.0 | 1476 | 731 |
| oracle-2 | 1.0 | 1465 | 727 |
| oracle-3 | 1.0 | 1421 | 733 |
| owner-only-1 | 1.0 | 1396 | 733 |
| nop-1 | 0.0 | 243 | 229 |
| stub-1 | 0.0 | 256 | 240 |
| forgery-1 (repaired artifacts, shipped tool.zip delivered) | 0.2903 (45/155) | 892 | 232 |

Forgery earns only the artifact checks on the shipped corpus; every check that re-runs the delivered tool pays 0 (before harden 0.303 = 46/152). precheck last line `PRECHECK CLEAN`; xref_check `19 entries, 0 findings`; stacking PASS (OUT/STACKING_CHECK.md, by-hand verdicts).
