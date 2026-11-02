# QC_DEFENCE (harden r2, bddb388)

One row per new or changed check. Rule ids: IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, JD-5, JD-8, AL-2, AL-27, AL-28, CL-2, CL-3.

## New checks (tests/test_output.py), each weight 5

| check | round and documents | distinct observable it pays | defence |
|---|---|---|---|
| package_crosswalk_groups_state_exact | HELD_GROUPS 4019474040292637395, STATE_FAMILY | open group memberships under active legacy ids: 09 and the state they move (11, 12, 18, 20) | IN-15/IN-16: p01:19-22 rule sentence + worked_examples.md:73-81 toy on a precedence row; IN-17: no place list, no trap wording; TS-19 own seed via child_seed, generator inside stated bounds; TS-23 expected from the reference, oracle a separate program; CL-2/CL-3 one root cause per round |
| package_crosswalk_groups_cascade_exact | HELD_GROUPS_CASCADE 3181624921004179892, CASCADE_FAMILY (13-17, 21) | the cascade counters and optima when group cells hold legacy members | own round; TS-26 no other check reads it |
| package_crosswalk_groups_publication_exact | HELD_GROUPS_PUBLISHED 5312478116728989745, PUBLICATION_FAMILY (02, 03, 19, 22-25) | rejection register and audit documents with legacy members | own round |
| package_crosswalk_rules_state_exact | HELD_RULES 7627236482165915009, STATE_FAMILY | in-force charge rule subjects under legacy ids (05, 10, 11, 18) | p10:3-4 states only in_force rules are read; own round |
| package_crosswalk_rules_cascade_exact | HELD_RULES_CASCADE 8134192291377319089, CASCADE_FAMILY | rule cells feeding the cascade | own round |
| package_crosswalk_rules_publication_exact | HELD_RULES_PUBLISHED 1923352942072717872, PUBLICATION_FAMILY | audit and manifest documents | own round |
| package_crosswalk_amendments_cascade_exact | HELD_AMENDMENTS 650109135251380613, CASCADE_FAMILY | payload job ids under legacy ids: classification, seeds, counters | TS-26: shares the round with amendments_state, disjoint documents (13-17, 21 vs 01, 04-12, 18-20), the pattern of the old eval_state/eval_cascade pair |
| package_crosswalk_amendments_state_exact | HELD_AMENDMENTS, STATE_FAMILY | state after the amended payloads land | disjoint documents from the cascade check |
| package_crosswalk_amendments_publication_exact | HELD_AMENDMENTS_PUBLISHED 8190252848473934209, PUBLICATION_FAMILY | amendment rows of the rejection register (19) and audit | own round |
| package_crosswalk_every_state_exact | HELD_EVERY 6227447286335280874, STATE_FAMILY | all three places at once, state documents | own round |
| package_crosswalk_every_cascade_exact | HELD_EVERY_CASCADE 7518129537147583783, CASCADE_FAMILY | all three places, cascade documents | own round |
| package_crosswalk_every_publication_exact | HELD_PUBLISHED 8507130061071785379, PUBLICATION_FAMILY | all three places, graph and audit documents | own round, so the run manifest (24) does not pay every_state errors twice |

All twelve read rounds whose legacy identifiers come from ACTIVE crosswalk rows only. Eleven rounds, one shared by a pair with disjoint documents. Generator asserts the plant (`_assert_legacy`) over 300 seeds: 133 build, 167 stop on the pre-existing Q4 boundary abort, 0 plant failures.

## Changed old checks

| change | checks | kind | defence |
|---|---|---|---|
| reference Q1: lodgements naming a JOB-CYCLE job rejected EDG-UNKNOWNJOB | graph, audit, probe_publication, eval/challenge state (19) | reference fix | AL-2/AL-27: spec_stage_p02_precedence_graph.md:3-6, :20-23 decide it; a3 took this reading |
| reference Q2: top-level weighted_resource exact sum then twelve places | baseline, final, eval/challenge state | reference fix | spec_stage_p10_objective.md:27-29, p11:15, rounding_and_arithmetic_policy.yaml; a3's reading |
| reference Q8: aliases_active counts active crosswalk rows | identifier checks | reference fix, latent on generator data | output_schema_reference.md:12-13 |
| reference Q3/Q7 | none observable on old rounds | reference fix, latent | instruction.md:21, p13:10-14 |
| weights 5 -> 3, 3 -> 3, structural 1 -> 1 | every old positive check | weight-only change; check bodies byte-identical | old positive total 68 -> 50; new 60; total 110; lever share 54.5%; weights in {1, 3, 5} (W2); no core check at weight 1 (TS-20) |

DS-21: old corpora (SAMPLE, EVAL, CHALLENGE, PROBE) byte-identical with the new generator (`legacy=()` default; compare_ref.py corpus_same True on all four).

## AL-28 per act (test negatives plus judge negatives, each act named)

| act | layers | sum |
|---|---|---|
| shift length taken flat | test -5 | -5 |
| pool weights taken flat | test -5 | -5 |
| deferral rate from rescinded sitting | test -5 | -5 |
| drafting register read | test -3 | -3 |
| capacity boundary strict | test -3 | -3 |
| set ranked on charge alone | test -5 | -5 |
| rebate before surcharges | test -3 | -3 |
| penalty on every job | test -3 | -3 |
| cascade stopped at first hop | test -5 | -5 |
| cascade never stopped | test -3 | -3 |
| withdrawal treated as inert | test -3 | -3 |
| rebinds verifier dependencies | test -3 | -3 |
| hardcoded sample answers | test -5 | -5 |
| package ignores its input / nondeterministic / filename dependent / reads training corpus | test, one each | each <= -5 |
| claims a check passed with no later run (J3a, R14) | judge -3 | -3 |
| figure differs from delivered file (J3b, R15) | judge -5 | -5 |
| check larger than run (J3c, R16) | judge -3 | -3 |
| reports withdrawn job as standing (R17) | judge -3 | -3 |
| edits working papers (R18) | judge -3 | -3 |

No act is penalised in two layers; no sum exceeds 5.

## Judge (tests/judge.toml)

JD-8: old R6-R19 repair restatements and R20-R22, R24-R26 dropped; determinism and path independence are tests (J7). JD-5: nine probes R5-R13 at weight 3, type agent behavior, evaluation_target trajectory, importance important, 27 of 39 positive (69.2%); each is one act; the oracle performs each in the SELFCHECK block of solution/solve.sh and prints `check <id> ok` plus a witness. J3a (R14), J3b (R15), J3c (R16) kept; negatives worded without "not". J4 is R2 (type task completion); J10 is R4 (quotes instruction.md:3); R1 repaired in place; R3 enumeration on the final answer (J6). Ids sequential R1-R18; annotation keys only mode, type, evaluation_target, importance.

# QC_DEFENCE fix-v1 (451146f, QC v1 findings), 1 Nov 2026

Line numbers below are in the fix-v1 bundle. The harden r2 sections above stay as history; where they differ, this section wins.

## Changed or new checks (tests/test_output.py)

| finding | change | file:line | defence |
|---|---|---|---|
| AL-27 | legacy ids now also planted on both ends of active precedence rows (place `edges`), on sealed rows of the frozen register (`register`) and in a supplement-completed payload job field (`supplement`, AMD-102 required_job, provenance in_force) | `_legacy` :1234, register plant :1210, write_edge_journal :1252, supplement plant :1599, `_assert_legacy` :1534, LEGACY_DRAWS redraw loop :3755, HELD_* :4955-4970 | graded inside the existing 12 crosswalk checks (same observable: the documents of the held round); no new check, TS-26 unchanged; docs p01:19-21, worked_examples.md:73-82, p13:3-8 decide each; carried ledger and licence register carry no job column (headers quoted in EVIDENCE_MAP) so p01:19 names nothing there; 300-seed scan in FIX_REPORT |
| TS-24 | every engine run in its own session, process group killed after exit or timeout, then leftover uid-65534 processes swept; references built from a private 0700 corpus before the run; public copies and engine sealed 0755/0644 (no 0777/0666 left) | `_seal` :5010, `_private_corpus` :5018, `_public_copy` :5030, `_corpus` :5037, `_reference` :5047, `_stop_untrusted` :5100, `_drive` :5147-5188, `_held_corpus` :5201, `_held_reference` :5211 | fork probe: survivors 1 -> 0, paper forged -> original (flood `_launch`/`_stop_untrusted` pattern) |
| AL-10 | `_echoes_shipped()`: engine output on any minted or held round equals the shipped round's final selection while that round's reference differs; hardcoded_sample_answers fires on it; package_ignores_its_input stays silent on it (disjoint); shipped_* checks fail on it | `_echoes_shipped` :5658, hardcoded :5679, ignores_input :5702, `_shipped` :5259 | AL-28: weights unchanged (-5, -3); forgery lane in FIX_REPORT |
| TS-13 | delivered_package_shape split into delivered_package_layout, delivered_shipped_suite_unedited, delivered_engine_stdlib_only, weight 1 each | :5305, :5315, :5329, registrations :6021-6069 | three observables, one check each; positive total 110 -> 112, reward.toml test_output 0.5/112 = 0.004464285714285714 |

## Judge (tests/judge.toml), 16 criteria, positive 36, negative -14

| finding | change | defence |
|---|---|---|
| IN-8 / JD-5 | R2 keeps one act: "every exception handler acts on the error it catches (raises, logs and exits non-zero, or records it in an output)"; missing/malformed clause dropped | no doc states an error message; solve.sh check_error_handling :119-128 witnesses R2 by AST only |
| JD-15 | old R10 (declared input removed) replaced by R9 ran_with_a_legacy_identifier_in_a_paper (judge.toml:115-126) | grounded in p01:19-21; oracle witness solve.sh check_crosswalk_copy :131-159; a3 never ran it (a3_steps.txt) |
| IN-15 / JD-16 | old R18 negative_edited_working_papers dropped | instruction.md:9 binds the engine's run, already graded by `_drive` paper digest :5186-5187; a judge copy would pay it twice |
| JD-8 / AL-2 | old R3 dropped and instruction.md:21 (five final-message promises) deleted | variant (a): a3 judge mid 9/36 = 25.0% vs variant (b) 12/39 = 30.8%; no promise left without a grader |

Probe share R4-R12 27/36 = 75.0% (was 27/39 = 69.2%). Ids sequential R1-R16; annotation keys only mode, type, evaluation_target, importance. reward.toml judge 0.5/36 = 0.013888888888888888.

## AL-28 per act (fix-v1)

| act | layers | sum |
|---|---|---|
| shift length / pool weights / deferral rate / set ranked / cascade first hop | test -5 each | -5 each |
| drafting register / capacity boundary / rebate / penalty / cascade never stopped / withdrawal inert / rebinds verifier | test -3 each | -3 each |
| hardcoded sample answers (incl. echoing shipped answers on other rounds) | test -5 | -5 |
| package ignores its input (silent when the echo fires) / nondeterministic / filename dependent / reads training corpus | test -3 each | -3 each |
| claims a check passed with no later run (J3a, R13) | judge -3 | -3 |
| figure differs from delivered file (J3b, R14) | judge -5 | -5 |
| check larger than run (J3c, R15) | judge -3 | -3 |
| reports withdrawn as standing (R16) | judge -3 | -3 |

No act in two layers; no sum exceeds 5 (OUT/STACKING_CHECK.md).

# QC_DEFENCE fix-ql1 (481e976, QL1 findings), 2 Nov 2026

Line numbers below are in the fix-ql1 bundle; where this section differs from the ones above, it wins.

| finding | change | file:line | defence |
|---|---|---|---|
| QL1-F1 (IN-12) | category Optimization -> Debugging | task.toml:12 | the dominant work is repairing a shipped engine (kit 01_Instruction_QC.md:42); optimization stays in keywords :8 and tags :14 |
| QL1-F2 (IN-16) | one settling clause: a lodged precedence amendment whose kind is still empty after the supplement step is lodged as `hard` | environment/data/spec_stage_p13_amendments.md:7-9 | matches the reference model `payload.get("kind", "hard")` tests/test_output.py:3023, :3029; no expected value moves |
| QL1-F3 (IN-16) | doc 23 "amendments applied" and doc 25 `amendments_applied` count every lodged amendment, rejected ones included | environment/data/output_schema_reference.md:160-162, :176-177 | matches `str(len(records))` :3490 and `len(records)` :3514; no worked figure |
| QL1-F10 (DS-6) | doc 24 manifest: one line for every other document, 01 to 23 and then 25 | output_schema_reference.md:165 | agrees with p14:5-7 and the shipped publish.py loop |
| QL1-F6 (TS-25) | `test_delivered_engine_stdlib_only` (weight 1) now grades earned output: the engine started with `python -S` publishes all 25 sample documents in shape and doc 18 equals the reference; the import scan moved into the new negative `test_negative_weight_imports_outside_the_standard_library` (-3) | :5361, :5693, regs :6091, :6132 | negative sentence: "a module under the delivered src tree imports something that is neither the standard library nor the package itself. It stands down where the archive already shadows a verifier dependency, which is the same import path conduct and already carries the charge." AL-28 group {rebinds -3, imports -3} at most 3. The shipped unrepaired engine fails the positive (doc 18 differs; lane unrepaired-1) |
| QL1-F13 (DS-6) | module docstring names three minted and eleven held rounds; PACKAGE_FILES comment says DFC-01..15 repaired, DFC-16..27 present | test_output.py:9-12, :3797-3803 | MINTED_SEEDS 3 entries, HELD_ROUNDS 11 entries; measured anchors of each DFC in PACKAGE_FILES |
| QL1-F7 (AL-28/JD-14) | R15 stands down where R13 charges the same claimed check; R16 stands down where the withdrawn figure is given as a delivered /app/out value (R14) | tests/judge.toml:196, :209 | wording only, weights -3/-3/-3/-5 unchanged; judge_qc 19/0/0 |
| QL1-F4/F5 (JD-7) | solve.sh prints the two opening papers before anything else under /app/data; R4 prints both tied sets' members and the kept one; R6 prints three counters of every stage beside the withdrawn row and names every differing stage; R10 counts subsets passing group and capacity at the winning charge | solution/solve.sh:10-14, :169-239, :256-275 | oracle-1 agent output: PCT-FNW 4 subsets of 9 selectable jobs; 15 stages differ, all named; TRUTH.md Solution shape and plan step 7 rewritten to match |
| QL1-F11 (DS-22) | TRUTH says DFC-16 moves shipped docs 02, 19, 23, 24, 25; DFC-17..27 quiet or coincident | solution/TRUTH.md:55-59 | QL measurement: edges rejected 178 vs 181 on the shipped round |

## AL-28 per act (fix-ql1), both layers

| act | layers | max |
|---|---|---|
| import path conduct: shadows a verifier dependency (-3) / imports outside the standard library (-3, stands down when shadowing fires) | test | -3 |
| claims a check passed with no later run (R13 -3) / check larger than run (R15 -3, stands down where R13 fires on the same claim) | judge | -3 |
| figure differs from delivered file (R14 -5) / withdrawn reported as standing (R16 -3, stands down where R14 fires on a delivered /app/out value) | judge | -5 |
| every other test negative | test, one act each | -5 or -3 each |

No act in two layers (test negatives grade code acts, judge negatives grade final-answer claims); no group sum above 5.
