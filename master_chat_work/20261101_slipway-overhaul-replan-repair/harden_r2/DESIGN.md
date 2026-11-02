# DESIGN - slipway-overhaul-replan-repair (board bddb388, harden round 2)

Paid run a3: final 77.52 = tests 49/68 (72.06) + judge 78/94 (82.98).
Target next paid run: tests < 85, rubric < 85, final < 40. Design target final <= 35.

## 1. Arithmetic (a3 program, measured in Docker, new tests)
| item | value |
|---|---|
| a3 tests on new checks | 43/93 = 46.24 (lever 0/50; old checks all pass) |
| a3 judge (new rubric, graded from trajectory) | low 6/39 = 15.4, mid 9/39 = 23.1, high 12/39 = 30.8 |
| predicted final mid | (46.24 + 23.08) / 2 = 34.66 (<= 35) |
| predicted final high | (46.24 + 30.77) / 2 = 38.50 (< 40) |
| lever share of positive test weight | 50/93 = 53.8% (bar >= 40%) |
| judge probe share | 27/39 = 69.2% (band 55-70%) |

## 2. Q1 / Q2 disputes (decided first; both go to a3's reading)
- Q1 lodgements naming a JOB-CYCLE job. spec_stage_p02_precedence_graph.md:3-6 (first failing test
  is the reason, a rejected row appears once in the rejection register) and :20-23 ("the lodgements
  that named it are then rejected under EDG-UNKNOWNJOB by the test above") are explicit. The old
  reference dropped those rows silently. Reading a3 took is the only one the paper allows; reference
  now re-tests the journal after the cycle jobs leave, so the rows are EDG-UNKNOWNJOB in 02 and 19.
- Q2 top-level weighted_resource of 11/18. spec_stage_p10_objective.md:24-26 (exact rational,
  published to twelve places), spec_stage_p11_search.md:15 (the round is the sum of the precincts),
  rounding_and_arithmetic_policy.yaml (mode exact_rational, rounding applied at publication),
  instruction.md:13 ("rounding where the stage paper places it and nowhere else"). No shipped fact
  supports summing rounded precinct strings (the readings coincide on the shipped round). Reference
  now sums the exact precinct values and rounds once. This is a3's reading; honest verdict: the docs
  warrant it, so no lever comes from Q1/Q2.
- Docs changed for Q1/Q2: no. Changed old checks: reference only (docs 02, 11, 18, 19, 23, 24, 25 on
  the old seeds; corpora byte-identical, compare.log).
- Q3 (class rate on a class with no job: inert per instruction.md:21), Q7 (reversal applies the exact
  inverse, p13:13-14; amendment lodgement tests EDG-SELF before EDG-UNKNOWNJOB, p02:11-12) and Q8
  (aliases_active = count of active crosswalk rows, output_schema_reference.md:12-13) fixed in the
  reference and in the oracle. Q3 and Q8 are latent on every generated round.

## 3. Lever (tests only): crosswalk applied to every job identifier
Rule: spec_stage_p01_identifier_and_revision.md:19-21 puts identifiers through
identifier_crosswalk.tsv before anything else reads them; a non-active row maps nothing. The shipped
round and every old seed carry legacy identifiers only in the crosswalk itself, so this branch never
fires on what the agent sees. a3 (and the shipped engine) map only the register and the edge journal.
Held-out rounds plant ACTIVE-row legacy ids (OLD-<n>) in:
- G: open memberships of exclusive_slot_groups.csv (a3 drops the member: 09, 11, 12, 14-21, 23-25 differ)
- R: first_job / second_job / anchor_job of in-force conditional_charge_rules.jsonl (rule never fires)
- A: amendment payload job fields (a3 rejects AMD-NOTARGET / EDG-UNKNOWNJOB) plus AMD-120, a reversal
  of the lodgement AMD-102 (exact inverse withdraws that edge; p13:13-14, worked_examples.md:73-79)
Doc change: p01:19-21 rewritten as a rule sentence (no place list, no trap wording): "Every job
identifier, in whichever paper it stands, is put through identifier_crosswalk.tsv before anything
else reads it; for a precedence row that means both of its ends. A crosswalk row whose status is not
active maps nothing." plus one W6 toy example on invented ids in worked_examples.md. Papers are not
digested into any output document, so old references stay identical.
Dropped candidates (ambiguous by 0b): group add/remove no-op reversals (action `add` undocumented),
reversal of a withdrawal of a non-active row, EDG-SELF lodged by amendment (EDG-CYCLE not ordered in
p02), restatement of non-rule kinds, negative amounts, double-booking by amendment.

## 4. Test changes (every changed check listed)
Old checks: assertion code byte-identical; only the reference (Q1, Q2, Q3, Q7, Q8 fixes) and weights
change. Weights: old 5 -> 3, old 3 -> 2, structural 1 -> 1 (old total 43). New checks (own seeds via
`write_corpus(dest, seed, legacy)`; default `legacy=()` keeps old corpora byte-identical):
| new check | seed : places | family | weight |
|---|---|---|---|
| package_crosswalk_groups_state_exact | 4019474040292637395 : groups | STATE | 9 |
| package_crosswalk_rules_state_exact | 7627236482165915009 : rules | STATE | 9 |
| package_crosswalk_amendments_cascade_exact | 650109135251380613 : amendments | CASCADE | 8 |
| package_crosswalk_amendments_state_exact | 650109135251380613 : amendments | STATE | 8 |
| package_crosswalk_every_state_exact | 6227447286335280874 : all three | STATE+CASCADE | 8 |
| package_crosswalk_every_publication_exact | 6227447286335280874 : all three | PUBLICATION | 8 |
Positive total 93; lever 50 (53.8%). G12: generator asserts every requested place carries a legacy id
(`_assert_legacy`); scan over 300 seeds: 133 build, 167 abort with the Q4 message, 0 plant failures, 0 errors (scan300b.log). Negatives unchanged.
Q5: known_traps_and_footguns.md removed (generator, lineage row, environment file); every rule it
announced is stated in a stage paper or the directive (p01, p02:8, p05, p08, p09, p10, p12, p13:10-14,
directive sections 2 and 5).

## 5. Judge rebuild (39 positive)
Dropped R2-R22, R24-R26 (repair restatements JD-8, determinism now a test J7, figures J1).
Kept R1 (repaired in place, w3), R23 text as J6 enumeration (w3), added J4 code quality (w3) and one
J10 order criterion quoting instruction.md:3 (w3). Probe band, nine probes at w3 (process, trajectory,
important), on acts a3 skipped: tie the weights settle (old R10 pattern), jobs the drafting copy adds
(R12), counters stage by stage beside withdrawn_counter_publication.csv (R26), altered-copy rerun
(P-d), reversal naming another kind (P-a), declared input missing (P-h), count of sets sharing the
winning charge (P-g), reordered-rows rerun, empty amendment journal (P-h). Negatives: J3a -3, J3b -5,
J3c -3, withdrawn reported as standing -3, edited working papers -3 (no "not" in any negative).
a3 graded: R1, J10 earned; J4 uncertain (no handlers, traceback names the file); R23 and all nine
probes missed (trajectory index WORK/h2_a3/a3_steps.txt); J3a not counted (unittest and rerun diff
after the last edit, steps 89 and 95). Oracle solve.sh will run each probe and print `check <id> ok`
plus a witness line (Phase 2), and gains one error-handling repair for J4.

## 6. Kill table (Docker, 8 rounds each: 4 old seeds + 4 held specs)
| program | tests /93 | lever kept /50 | lost |
|---|---|---|---|
| a3_program (paid run, first) | 43 = 46.24% | 0 | all six crosswalk checks |
| oracle_fixed (oracle + DFC-16..26) | 93 = 100% | 50 | none |
| oracle_program (old oracle; catalogued faults only, first-write) | 31 = 33.33% | 0 | Q1/Q2 old checks + all six |
| engine_orig (shipped, blind) | 2 = 2.15% | 0 | all but two structural |
| a3_groups (a3 + crosswalk in groups) | 52 = 55.91% | 9 | rules, amendments x2, every x2 |
| a3_rules | 52 = 55.91% | 9 | groups, amendments x2, every x2 |
| a3_amendments | 59 = 63.44% | 16 | groups, rules, every x2 |
| oracle_less_groups (all-but-one) | 68 = 73.12% | 25 | groups, every x2 |
| oracle_less_rules (all-but-one) | 68 = 73.12% | 25 | rules, every x2 |
| oracle_less_amendments (all-but-one) | 61 = 65.59% | 18 | amendments x2, every x2 |
| a3_careful (careful enumerator) | 93 = 100% | 50 | none (recorded) |
Logs: _runs/20261101/slipway-overhaul-replan-repair/harden2-114714/kill3_*.log, score3.log.

Loss kind WRONG on every row (bytes differ); no crash or timeout. Careful enumerator (a3 plus the
crosswalk in groups, rules and amendments) keeps the lever: recorded, not a blocker (R5 d).
Timing: corpus 0.9-6.8 s, reference 0.05-0.11 s, program 0.23-0.53 s per round; verifier limit 5400 s.

## 7. EVIDENCE_MAP (full file WORK/EVIDENCE_MAP.md in Phase 2)
| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Q1 cycle lodgements EDG-UNKNOWNJOB | shipped_graph, shipped_audit, probe_publication, eval/challenge_state | spec_stage_p02_precedence_graph.md:3-6, :12, :20-23 | silent drop; JOB-CYCLE row |
| Q2 exact sum, round once | shipped_baseline, shipped_final, eval/challenge_state | spec_stage_p10_objective.md:24-26; spec_stage_p11_search.md:15; rounding_and_arithmetic_policy.yaml | sum of rounded strings |
| Q8 active crosswalk rows | identifier family | output_schema_reference.md:12-13 | alias-map size |
| crosswalk in groups | crosswalk_groups, every_* | p01:19-21; p08 | raw id dropped |
| crosswalk in rules | crosswalk_rules, every_* | p01:19-21; p10 | rule never fires |
| crosswalk in amendments | crosswalk_amendments_*, every_* | p01:19-21; p13:10-16 | AMD-NOTARGET, EDG-UNKNOWNJOB |
| reversal of a lodgement | crosswalk_amendments_*, every_* | p13:13-14; directive section 1; worked_examples.md:73-79 | crash, re-withdraw |

## 8. QC_DEFENCE (per new or changed check)
| check | rule ids answered |
|---|---|
| six crosswalk checks | IN-15/IN-16 rule stated in p01 sentence plus toy example; IN-17 no trap or place list in docs; TS-19 hidden seeds own RNG, within stated bounds; TS-23 expected from reference, oracle independent (solve.py repairs); TS-26 each check reads its own seed and family, no two read one observable; CL-2/CL-3 one root cause per seed (groups, rules, amendments separate) |
| old checks (reference fix only) | AL-2/AL-27 docs decide Q1/Q2, a3 reading taken; DS-21 corpora byte-identical |
| judge | JD-5 probes on acts the tests cannot see; JD-8 restatements removed; J3a kept; no annotation keys beyond mode, type, evaluation_target, importance |

## 9. Residual risks
- Q4: about 56% of fresh seeds abort in write_corpus (no level charge to seat); held seeds are chosen
  from buildable ones and the scan records the rate.
- One root cause carries the whole lever (crosswalk scope). An agent that reads p01 literally and
  maps every identifier passes all six. The p01 rewrite makes the rule plain without naming places.
- Judge high band 30.8 if P2 is credited for a3's register comparison (steps 25-35): final 38.5.
- Eviction choice is undocumented (store LRU shared by all engines); untouched.

R5 check: (a) 34.66 <= 35; (b) 53.8% >= 40%; (c) sections 7-8; (d) section 6; (e) reference
0.05-0.11 s per round against a 5400 s verifier limit; oracle 93/93 in the kill run, nop and
oracle lanes are Phase 3 gates.

DESIGN READY: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_slipway-overhaul-replan-repair/harden_r2/DESIGN.md
