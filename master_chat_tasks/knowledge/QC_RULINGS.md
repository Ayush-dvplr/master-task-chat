# QC rulings on lever-touching rules (v1, seeded 23 Oct 2026 from QC_2026-10-2*/qc_report/)

How to fix a finding without softening a lever: `QC_FIX_PLAYBOOK.md` (same folder); its precedent column cites rows here.

How to use: later designs reuse what QC accepted (PASS rows, REUSE) and avoid what it rejected (FAIL/MINOR/WARN rows, AVOID). Build, harden and fix sessions read this before writing `WORK/QC_DEFENCE.md`. The master appends one row per new P11 ruling on these 9 rules (P12 v2 lists them in its `QC_RULINGS rows` section).

Sources: 24 reports, 7 bundles. Cite = `<bundle> v<N>:<line>` under `QC_2026-10-21/qc_report/` (district-heat, emberforge, schema, vendor) or `QC_2026-10-22/qc_report/` (cohort, dispatch, sensor). Verdicts: PASS ✅, FAIL ❌, MINOR 🟡, WARN ⚠️. Rows marked INFERRED paraphrase rather than quote.

## IN-15 (every graded rule stated somewhere the agent can read)
Note 25 Oct (kit 5574d77e): locus = the instruction or any file inside the input directories `environment/Dockerfile` copies, no pointer needed (01:45). Scope = rules of engagement; deliverable-property rules may instead be settled by a determinate fact (AL-1 05:21).
| bundle | cite | our design | verdict | reason QC gave | reuse? |
|---|---|---|---|---|---|
| dispatch | v1:35, v1:122 | negative `nondeterminism_source_in_solver` fired on any random/uuid/secrets import or clock call | FAIL | rule not stated; also honest-trippable (TS-16) | AVOID, FIXED-IN v2 (re-scoped) |
| dispatch | v2:40, v2:126 | negative `network_dependency_or_shell_cheat` also fired on `__import__` / `importlib.import_module` | FAIL | "a graded rule is stated nowhere" | AVOID: every negative's trigger list must match an instruction sentence |
| cohort | v2:119 | stdlib, no network, no reading /app/data beyond DATA_DIR, no handwritten answers, each stated at instruction.md:1,5 | PASS | all graded engagement rules stated | REUSE |
| vendor | v4:128 | judge R6 "instruction following" (one line per figure saying how obtained) stated instruction.md:13; corpus-read negative stated L11 | PASS | each instruction-following criterion has its sentence | REUSE |
| emberforge | v5:110 | judge R9 (no writes under /app/data), R10 (no network) each paired with an instruction.md:13 sentence | PASS | criterion ↔ sentence pairing | REUSE |
| district-heat | v3:119 | stdlib-only and no-shipped-records negatives stated at L3 | PASS | stated | REUSE |

## IN-16 (one reading for everything graded)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| emberforge | v1:34, v1:228 | salvage both a repeat AND outside its credit window: codes not settled | FAIL | two defensible readings, graded | AVOID; FIXED-IN v2:604 by one settling sentence in rulebook_salvage.md:56-57 |
| schema | v3:32, v3:108 | float cast of a space-padded decimal string (world_15, w5) | FAIL | "surrounding spaces ignored" rule left the decimal case open | AVOID: an L5 strict/normalise pair must state the case for each type. Since 5574d77e a shipped example in the copied input may settle a type (FC:492, 04:95) |
| district-heat | v2:756 | `waiver_signed_missing` count scope (v1 finding) | FAIL then fixed | scope settled "over every data row" | FIXED-IN v2 |
| vendor | v4:129 | decoy loader_notes counter-claim settled by format_contract.md:137-138, and instruction says the contract wins | PASS | settled by a precedence sentence | REUSE (but see LEAK_LIBRARY: decoy refuted beside its use leaked) |
| cohort | v2:120 | merge tie, missing plan weight: unspecified but never generated | PASS | ungraded gaps are not IN-16 failures | REUSE with care: hidden generator must never produce the open case |
| district-heat | v3:120 | program.ini default settled by schema.md §1 "other sections carry no rule" | PASS | global default + exception in another section is one reading | REUSE (W3 form) |

## IN-17 (instruction must not pre-announce a discovery the shipped input establishes; new FAIL check, kit 5574d77e 01:47)
Test: both (1) the sentence announces a property, edge case or branch the agent was meant to find, and (2) the shipped input already establishes it. The reviewer must name the discovery and point to the input (01:47); checklist 01:87 "name both the discovery and the input that carries it, or raise nothing". Exempt: rules of engagement, CL-6 signposts, IN-16 settlers, DS-25 literals, finished-work shape, orientation. Our scan (QC_PUSH_REVIEW s4, INFERRED): 9 strong or moderate hits, match-replay M-2..M-5, M-1, M-7; caldermoor C-1, C-2; sentinel S-2.
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|

## AL-1 (everything graded is promised; determinate fact is a ground, kit 5574d77e 05:21-32)
Table 05:22-32: empty timestamps in 3 of 40 rows = yes; all-distinct ids = no (silence); pre-formatted amounts = width yes, rounding rule no; config value = yes; prohibition = never. One file settles one demand (05:32).
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|

## CL-5 (silent requirements of an exact comparison; QL ruling 25 Oct 13:54)
QL (Sugam) confirmed: Final_checklist.md:492 governs. A silent requirement (order, keys, path form, casing, value type) passes if it is "stated in the instruction, or established by an example the agent is actually given in the copied input, or compared in a way that does not care". The CL-5 checklist line in 05_Alignment_Integrity_QC.md:89 ("stated in the contract or compared insensitively") is missing the example option, and QL will update it. Until the kit changes, a CL-5 FAIL that FC:492's example option answers is disputed by quoting FC:492 and this ruling.
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|

## TS-13 (one property per test)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| vendor | v1:69, v1:366 | compA_value / compA_len asserted value AND field in one `and` | MINOR | hides which property failed | AVOID; FIXED-IN v2:700 |
| schema | v2:46, v2:345 | `signature_keeps_explicit_null` graded 3 unrelated properties | MINOR | split it | FIXED-IN v3 (split created a TS-25 absence check, v3:353) |
| schema | v4:30, v4:192 | `exec_add_fill_absent_vs_null` (N4 + M5 cast), `summary_categories_and_partner_order` | MINOR | two rules per check after a fix folded them in | AVOID: fixes must not fold a second rule into an existing check |
| sensor | v1:46, v1:201 | `summary_reports` also asserts normal_matrix_trace; `observation_sets` bundles sets | MINOR | bundled unrelated properties | AVOID |
| cohort | v2:174 | each fixture isolates one rule | PASS | | REUSE |
| district-heat | v3:176 | each composed check reads one view of one extract | PASS | whole-document per view is one property | REUSE (G1) |
| emberforge | v5:161 | each check reads one document group of one season | PASS | | REUSE |

## TS-19 (no contract/test contradiction; every promise graded)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| district-heat | v1:312 | hidden extracts with 5 offers per site vs stated max 4 | FAIL | hidden inputs outside the stated bounds | AVOID: hidden generators must stay inside every stated bound; FIXED-IN v2:758 |
| vendor | v1:36, v1:360 | runner dropped to `nobody` over root-owned 0600 inputs | FAIL | every program-run check fails, oracle included | AVOID (the permission artefact); FIXED-IN v2:682 |
| vendor | v1:48, v1:361 | encode fixtures were not decode documents | FAIL | fixtures must have the contract's shape | AVOID; FIXED-IN v2:690 |
| vendor | v1:50, v1:362 | name-prefix ban stricter than the appendix | FAIL | test stricter than the contract | AVOID |
| emberforge | v2:43, v3:27, v4:31 | shipped records presence-only; key order promised but ungraded; multi-requisition case never generated | MINOR / FAIL / MINOR | promised behaviour with no checker or no separating case | AVOID: every promise needs a grader and a generated case; FIXED-IN v4:369, v5:376 |
| schema | v3:35 | K19 `changed_functions` completeness ungraded | FAIL (as AL-2) | ungraded promise | AVOID |
| dispatch | v1:41, v1:182 | certificate value type (JSON true/false) stated nowhere | FAIL (CL-5) | silent value type | AVOID: state types for every graded key, or (since 5574d77e, FC:492) ship an example that establishes them |
| dispatch | v2:49-50 | 400 s run cap unstated; shipped artifacts existence-only | WARN | | AVOID: state run caps; shipped-only checks stay <= 5% (G3) |
| cohort | v2:180 | every instruction promise mapped to a check | PASS | | REUSE |
| district-heat | v3:182 | every graded rule traced to schema.md or instruction.md | PASS | | REUSE |

## TS-20 (weights map to importance; core never 1)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| district-heat | v1:317 | edge case w5 outweighed a core settlement check w3 | WARN | importance inversion | AVOID; FIXED-IN v2:770 (cases 3, composed views 5) |
| emberforge | v1:48, v1:320 | verifier-hook negative at -1 while hardcoding -3 | MINOR | an attack on the verifier is not "rare, minor" | FIXED-IN v2:608 (-5) |
| cohort | v2:181 | core documents 5, sub-goals 3, presence 1 | PASS | | REUSE |
| district-heat | v3:183 | whole-document views 5, data quality 3, cases 3, format 1 | PASS | | REUSE |
| vendor | v4:194 | composed decode/encode 5, isolated rejections/reports 3, severe cheats -5 | PASS | | REUSE |

## TS-26 (no two tests pay for one observable with one logic)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| vendor | v1:53, v1:364 | filename negative and nondeterminism negative both read repeated-decode identity | FAIL | same observable twice | AVOID |
| vendor | v3:34, v3:167 | still both fire on "outputs of the same segment differ" | FAIL | | FIXED-IN v4:451: filename negative stands down when repeat runs differ |
| schema | v1:51, v1:283 | 50 checks, redundancy reviewed | PASS (TS-23 warn) | no double payment; count reflects many rules | REUSE the review, not the count |
| cohort | v2:183 | fixtures vs hidden_* on different studies; canonical and deterministic share only a precondition | PASS | shared precondition is not double payment | REUSE (G1/G2) |
| district-heat | v3:185 | 4 extracts x 4 views, 8 isolated cases on separate extracts | PASS | distinct observables | REUSE (G1 cascade accepted) |
| vendor | v4:196 | reject_* on hidden fixtures vs error_analysis on the agent's own example | PASS | | REUSE |
| emberforge | v5:170 | presence / byte form / findings shape / values distinct | PASS | | REUSE |

## AL-28 (one act costs at most -5 across tests and judge)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| vendor | v1:54, v1:471 | determinism -5 + -3; hardcoding test -5 + judge R12 -3 | FAIL | stacking within and across layers | AVOID; FIXED-IN v2:693 |
| vendor | v3:36, v3:240 | two -3 negatives on output differing between runs (-6) | FAIL | | FIXED-IN v4:451 |
| dispatch | v2:42, v2:259 | input-dir write trips test -3 and judge R8 -3 (-6) | FAIL | one act, two layers | AVOID: a judge negative must not shadow a test negative |
| cohort | v2:242 | 6 negatives on distinct acts incl. judge R8 -5 honesty | PASS | distinct acts | REUSE (G4) |
| district-heat | v3:251 | grader strings in source (test) vs opening /tests at run (judge) treated as different acts | PASS | different actions | REUSE with care |
| emberforge | v5:229 | import-hook test -5 vs judge R9 data write -5 | PASS | different acts | REUSE |
| vendor | v4:259 | 5 test negatives + judge R7 false validation claim, distinct triggers | PASS | | REUSE |

## JD-7 (every criterion true of / avoided by the reference solution)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| district-heat | v1:363, v1:378 | R9 code quality (no dead code) while solve.py had dead code | FAIL | oracle fails it | AVOID; FIXED-IN v2:759 |
| vendor | v2:47, v2:377 | R6 "each in its own named function" not met by oracle's encode_one | FAIL | | AVOID |
| vendor | v3:42, v3:210 | R5 no dead code vs oracle writing one byte-identical source to both programs | WARN | | FIXED-IN v4:453 |
| cohort | v1:41, v1:239 | R4 "13 reason entries" vs oracle 14 | FAIL | stated figure wrong for the oracle | AVOID figure criteria (J1); FIXED-IN v2:427 |
| dispatch | v2:41, v2:219 | R9 "functions short enough" vs oracle 423-line `build` | FAIL | | AVOID vague code-quality criteria; use a named shape (J4) |
| cohort / vendor / district-heat / emberforge | cohort v2:203, vendor v4:219, district-heat v3:206, emberforge v5:190 | outcome figures recomputed from the oracle; code-quality criteria checked against solve.py | PASS | | REUSE: always run the oracle against every criterion |
| cohort | v3:38, v3:225 | R6 "every except clause names a type and raises or reports" vs oracle solve.py:48-51 `except ValueError: return None` | FAIL | oracle fails its own code-quality criterion (also DS-22 v3:40) | AVOID; fix the oracle, not the criterion (playbook row JD-7) |

## JD-15 (outcome traces to the contract; conduct holds for every competent route)
| bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|
| district-heat | v1:366 | R4 "states the five objective components before coding" | MINOR | preference, not odds-raising | AVOID; removed v2:766 |
| district-heat | v2:44, v3:218 | R7 named except clause; R8 every function called | WARN | rewards an absence, vacuously true | AVOID absence-shaped positives (also JD-2) |
| schema | v3:34, v3:224 | R7 "no debug residue" with positive weight | FAIL | an agent that changes nothing earns it | AVOID |
| vendor | v2:37, v2:708 | R5/R6 outcome criteria grading a code layout no file promises | FAIL | outcome must trace to the contract | AVOID |
| cohort | v1:45, v1:241 | R7 "cleaning and writing in separate named functions" | MINOR | conduct preference | FIXED-IN v2:429 (replaced) |
| sensor | v1:36, v1:242 | constraint R8 (opens a path outside DATA_DIR/OUT_DIR) labelled with the wrong kind | FAIL | annotation type must match its class | AVOID: label constraint criteria "instruction following" |
| emberforge | v5:198 | R6 separate named functions in a ~1000-line program | PASS | every competent route writes them | REUSE with care (size-dependent) |
| cohort / vendor / district-heat | cohort v2:211, vendor v4:227, district-heat v3:214 | outcome R1-Rn trace to instruction lines; conduct honesty and code-quality criteria | PASS | | REUSE; note: conduct "constructs its own input" criteria (J2) have no ruling yet |
| district-heat | v4:37 | R5 enforces the stated float rule under a conduct label and adds "integer helper functions" | FAIL | label hides a constraint; idiom stated nowhere | AVOID; re-label as instruction following, strike the idiom (playbook row JD-15) |
| district-heat | v4:43-44 | R1 manifest agreement, R6 read manifest comments first | MINOR | preferences: the manifest carries no graded rule | AVOID route preferences tied to non-rule files |
| vendor | v5:35, v5:328 | R5 code-quality criterion labelled `task completion` | MINOR | conduct criterion with an outcome label | AVOID; code quality is conduct |
| vendor | v5:323 | R1-R4, R6 odds-raising self-tests at w3/3/3/3/1 | PASS | odds-raising conduct at 1 or 3 passes | REUSE |

## Other rules that touched levers (23 Oct reports: cohort v3, district-heat v4, vendor v5)
| rule | bundle | cite | our design | verdict | reason | reuse? |
|---|---|---|---|---|---|---|
| AL-27 | cohort | v3:44 | dedupe-before-merge and duplicate-of-excluded-row rules stated, no graded input triggers them | FAIL | rule never exercised | AVOID; add hidden triggering rows (hardens; playbook row AL-27) |
| AL-27 | district-heat | v4:39 | duplicate profile "was kept" qualifier and its precedence never triggered | FAIL | | AVOID; same fix |
| AL-2 / CL-1 | cohort | v3:42 | final-reply figures requested, graded by nothing | FAIL | ungraded promise | AVOID final-reply figure requests (J1); remove the request |
| JD-14 | district-heat | v4:36 | R1 "checks a figure against an independent value" overlaps R2-R4 | FAIL | double payment inside the judge | AVOID broad verification criteria beside specific ones |
| JD-18 | district-heat | v4:38 | no code-quality criterion after the except-shape criterion was removed | FAIL | code deliverable needs one | AVOID removing the only code-quality criterion; keep one J4 named shape |
| DS-4 | vendor | v5:40 | capture id prefixes `cap-` / `rej-` mark rejected captures | WARN | answer derivable from ids | AVOID meaningful id prefixes; neutral ids |
| TS-23 | district-heat | v4:47 | 38 checks | WARN | above 35 | [superseded 27 Oct, option A] KEEP the warn with the count; merge only true duplicates (TS-26) |
| TS-23 | sentinel | v7 (QC/reports/sentinel-policy-recompute/v7.md) | 39 checks; held fix 3eb08a6 F4 planned merges of hidden document and state checks to reach exactly 35 | WARN | above 35 | AVOID merging to reach a count (Ayush decision 3, option A, 27 Oct): the merges would have bundled several observables per check (TS-13) and moved weight; recorded warn only |
| AL-2b / J1 | guide check ec452c9 (HOW_TO_MAKE_HARD notes) | counterfactual or what-if figure criteria in the judge ("states the total if X changed") | not shipped | n/a | the agent's own figure is graded by nothing the verifier recomputes; JD-7/JD-8 risk; Opus answers figures right | AVOID counterfactual figure criteria; use a rerun graded by a test, or a probe criterion (J2) |

## QL answers 26 Oct 2026 (Sugam, to the 4 questions from synthesis 720e1d7)
- Q1 JD-7 trajectory criteria: "you may judge in traj but it should be reflected in oracle as well, so phrase your rubric so it passes oracle." -> Probe criteria allowed; solve.sh must perform and print each probe act (JD-7 kept, CONFLICTS C1 path).
- Q2 JD-15 probe wording ("The agent runs its program on one input where <stated branch> applies and shows that record and the program's decision", w3): "yes, pass." -> odds-raising, passes. Closes the open J2 note in Patterns below.
- Q3 CL-4 stated all-corpora gate: "search for related checks in qc and if they pass it passes. the concept is to not test on hidden keys, if you want to test then at least mention the keys in contract somewhere, no or minimal explanation is fine." -> One stated gate allowed when the related checks pass; every key/field/value form a test reads must be named somewhere in the shipped contract (explanation may be minimal).
- Q4 IN-17 naming what changes on fresh inputs: "depends on you if you can bring pass rate down even when mentioning those things fine by me, but i wouldn't recommend mentioning anything more than necessary." -> Allowed, not recommended; default is no rerun-axis sentence, mention only what is necessary.

- Q5 (26 Oct 18:55, Ayush relayed): "is a task deliverable if Opus passes 100% of tests but the final score is below 70 because of the rubric? Example: tariff, tests 100, rubric 18, final 59." Sugam: "no". -> gate = tests < 100 AND final < 70; judge-only rebuilds cannot rescue tests-100 tasks.

## Carry-over between QC rounds (Ayush decision 2, 27 Oct; QC loop study 3b00450)
Round 2 and later run in recheck mode (P11 v3 MODE recheck). The reviewer receives the previous report, the task's `KEPT.md` (each kept item with its kit-line reason) and `CHANGED_LINES` (`diff -U0` between the previous and current QC copies). A finding on an unchanged line, or on a kept item, must answer the earlier PASS or KEEP reason with a kit line; otherwise it is recorded as "acknowledged" (not a fail) and the master adds a FP_DOSSIER row. Kit scripts still run in full every round. Evidence: findings per round fell 126, 48, 53, 44, 38, 44, 20, 7, 1; 50 of 255 later findings re-flagged kept items, 67 were caused by fixes.

## Patterns
- QC accepts a natural cascade: one whole-document test per view per hidden extract (district-heat v3:185, cohort v2:183). G1 is QC-safe as built.
- TS-26 and AL-28 failures in our history were all on negatives, never on positive cascades (vendor v1:53, v3:34, v1:54, dispatch v2:42). Group negatives by act and make overlapping ones stand down (vendor v4:451).
- A judge negative that shadows a test negative is stacking across layers (vendor v1:54, dispatch v2:42); give each act one layer only.
- Every negative's trigger list must match a stated sentence word for word (dispatch v1:35, v2:40).
- Hidden generators must stay inside every stated bound and produce every promised case (district-heat v1:312, emberforge v4:31).
- Absence-shaped positive criteria (no dead code, no except, every function called) are flagged every time (district-heat v2:44, v3:218, schema v3:34); use a named-shape criterion with a real separating case (J4).
- Code-quality and figure criteria failed JD-7 against our own oracle 4 times (district-heat v1:363, vendor v2:47, cohort v1:41, dispatch v2:41): run the oracle against every criterion before QC.
- Fixes created new findings: the TS-13 split created a TS-25 absence check (schema v3:353), a cast fix folded a second rule into a check (schema v4:30). P12 v2 must re-check the rules its fix touches.
- L5-style strict/normalise pairs need the rule settled for every value type (schema v3:32).
- No QC ruling yet exists on J2 conduct criteria ("constructs its own input ... and checks ..."); the pilots are the first test (PL Q46 open).
