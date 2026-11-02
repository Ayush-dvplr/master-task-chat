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
