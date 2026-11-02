# TRIP bddb388: slipway-overhaul-replan-repair, paid attempt 3

Source: gate_run_a3 (claude-opus-5, Run 1): final 77.52 = tests 49/68 (72.06) + judge 78/94 (82.98). 98 steps, $10.59.
Program: WORK/a3_program (1949 lines; 544 diff lines vs the shipped engine). Step index: WORK/h2_a3/a3_steps.txt.

## R3.1 Files opened, in order
- 3-8: 00_open_this_first.txt, replan_programme_contract, data_lineage, readings_not_in_force, every stage paper p01-p14, work_ledger contract, output_schema_reference, serialisation contract, policy toml/yaml, round_header, known_traps_and_footguns.md (step 8: the trap list was read and used), worked_examples, glossary, engine_defaults.ini.
- 9-15: workbook (zipfile/ET: Schedule R, R40-PEN, pool weights), memo PDF streams, directive docx.
- 16-24: project.zip unpacked, every module and test_visible.py read.
- 25-46: registers frozen vs current, edge journal, duplicate pairs, groups, withdrawn plan/counter heads (33), rules, amendments, supplement, capacity, cycle edges.
- Never opened as a check: withdrawn_counter_publication.csv stage by stage (only the head at 33).

## R3.2 Literals fitted to shipped data
None. grep of the program for shipped ids (JOB-, PCT-, GRP-, CCR-, AMD-, CMT-, RND-), sheet names and shipped figures finds only a `PCT-` prefix test in the ini parser (normalise.py:121). The program is general where the shipped round exercises it.
Where it is not general (quiet branches the shipped round and every generator seed never fire):
- crosswalk applied to register and journal only; group memberships, conditional charge rules and amendment payloads read legacy ids raw (p01:19-21 says both ends of every identifier go through the crosswalk before anything reads them).
- reversal of a group_member_revision that changed nothing (add of a standing member, remove of a non-member) changes the group; reversal of an edge_withdrawn of a non-active row makes the row active (p13: a reversal applies the exact inverse of what the named amendment did).

## R3.3 Where checking stopped
- Done: shipped engine run first (36, P-f); relocated rerun /tmp/papers_other PORTABLE and diff -r IDENTICAL (75, 96, P-e); independent brute-force baseline recompute (78-80, P-c); unittest after the last edit (89, 95).
- Not done: any run on altered input (P-d), edge-input run (P-a), empty or malformed input (P-h), one-instance witness of a tie settled by weights (P-b; R10), uniqueness witness (P-g), naming the jobs the drafting copy adds (R12), stage-by-stage compare against withdrawn_counter_publication.csv (R26), contrast of an inert and a revalidated amendment in the final message (R23).
- Final message (98) claims "all 16 tests still pass" and an independent recompute; both are backed by runs after the last edit (89, 95, 78-80), so J3a would not fire on a3. Recorded honestly; J3a is kept for the next run.

## R3.4 Lost points by kind
| check | w | kind | who was right |
|---|---|---|---|
| shipped_graph_layer_exact | 3 | WRONG | docs (Q1): p02:20-23 lodgements naming a JOB-CYCLE job are rejected EDG-UNKNOWNJOB; reference drops them |
| shipped_audit_documents_exact | 3 | WRONG | docs (Q1), same rows in 19 |
| package_probe_publication_exact | 3 | WRONG | docs (Q1) |
| package_eval_state_exact | 5 | WRONG | docs (Q2) |
| package_challenge_state_exact | 5 | WRONG | docs (Q2) |
No TIMEOUT, no CRASH. Every non-disputed check passed, including all cascade families on held-out seeds.

## Q1 / Q2 verdicts (both go to a3's reading; the docs are explicit)
- Q1: spec_stage_p02_precedence_graph.md:3-6 (rows tested in order, rejected row appears once in the rejection register) and :20-23 ("the lodgements that named it are then rejected under EDG-UNKNOWNJOB by the test above"). One reading fits; the reference drops these rows (tests/test_output.py ~2812-2832). Fix: reference rejects them under EDG-UNKNOWNJOB and lists them in 02 and 19.
- Q2: spec_stage_p10_objective.md:24-26 ("held as an exact rational and published to twelve decimal places"), spec_stage_p11_search.md:15 ("the round is their sum"), rounding_and_arithmetic_policy.yaml (mode exact_rational; weighted_resource placed at stage_p14 publication), instruction.md ("rounding where the stage paper places it and nowhere else"). No shipped fact supports summing rounded strings; the shipped round makes both readings coincide. Fix: reference sums exact rationals per precinct, rounds once at publication (`_selection_body` ~3035-3060).
- Consequence: on the current tests a3 would score 68/68. All test loss must come from new held-out instances.

## Judge criteria on a3
| id | w | earned | why |
|---|---|---|---|
| R1 repaired in place | 5 | 1 | real: str_replace on /app/work engine, zip at 94 |
| R2 package expectations | 3 | 1 | real: test_visible read 24, run 81 |
| R3 quiet branch | 3 | 1 | cheap: code for reversal shapes, never run on one |
| R4 determinism | 3 | 1 | real: diff -r IDENTICAL 75, 89 |
| R5 path independence | 3 | 1 | real: relocated papers 75 |
| R6-R19 fault restatements | 56 | 1 each except R10, R12 | cheap: credited from edits, tests already grade every one (JD-8) |
| R10 live pool weights + tie witness | 5 | 0 | no witness of two equal-charge sets |
| R12 register in force + drafting adds | 5 | 0 | never named the jobs the drafting copy adds |
| R20 stdlib binaries | 3 | 1 | real: zipfile/zlib 9-15 |
| R21 set aside by reason | 3 | 1 | final message list |
| R22 sheet and key cell | 3 | 1 | final message |
| R23 inert amendments | 3 | 0 | no AMD-101 vs AMD-104 contrast |
| R24 pool to last unit | 3 | 1 | final message PCT-ELS 995/995 |
| R25 faults beside stage | 3 | 1 | final message |
| R26 compare withdrawn counters | 3 | 0 | head only, no stage compare |
| R27, R28 negatives | -3 each | 0 | not fired |
Judge rebuild target: drop R6-R19 (tests grade them), add probes on the acts a3 skipped (P-a, P-b, P-d, P-g, P-h, plus R10/R12/R26 shapes), J3a, J4.

## Lessons for the master
- both disputes resolved to the paid agent's reading because the stage papers state them outright | no change: ruling per dispute, not a template gap
- a reference that only implements planted shapes hides latent wrong answers on quiet branches | no change: covered by G9/G12
