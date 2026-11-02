# HARDEN_REPORT: hangar-check-replan harden r1 (board a79e23e, route 1)

Bundle `master_chat_work/bundles/hangar-check-replan/`, tree before c91e926ac01c, after 0163b9762e5b. Design OUT/DESIGN.md (section 8 = as built), trajectory and fuzz OUT/TRIP.md, leaks OUT/LEAKS.md, stacking OUT/STACKING_CHECK.md. Scores below are tests-only unless marked judge.

## Diagnosis
Paid a1 scored final 75.0 = tests 137/137 + judge 21/42. The a1 program is exact on every plan and settlement branch the generator fires: fuzz of 5904 folders (2100 branch folders, 300 seeds x h1..h6 + shipped, 264 value mutants, 1440 Word and CSV markup mutants) finds DIFFs only on Word markup. a1 reads table rows as direct `w:tr` children and a cell as the join of every `w:t` (a1 derive_report.py:103-127) and tested only the plain markup its own synth.py wrote (trajectory step 27). Family 4b finds no fitted literal; 4c not needed.

## Levers (family 4a, L2 held-out; docs unchanged)
Rule: data_conventions.md:20-23 (WordprocessingML packages as ECMA-376 defines them; tables from the main part; cell value = text stripped; table found by header row). Nine hidden folders, own seed each (FORMS, tests/test_output.py:906), built by `_planted_corpus` then `_reform` (:675) with values unchanged (asserted by `_form_plain` :665 and a changed naive read):
- h7 h8 h9: planning_limits base/allowance_shifts rows in sdt / customXml / mc:AlternateContent (overtime_policy.md:14-24); settlement_per_check, settlement_by_base_and_segment, settlement_summary, w5.
- h10 h11 h12: disruption_notice closures (data_conventions.md:54-55); h13 h14 h15: tail available_from (data_conventions.md:51-53); plan_rows, plan_group_totals, settlement_per_check, settlement_summary, w5.
- Oracle branch: solution/solve.py:35-65 (`_branch`, `_content`, `_text`) used at :197-198. Paid/careful branch: a1 derive_report.py:117-122. Saved witness inputs: WORK/h1_a1/witness/h7..h15/{data,want.json}.

## Arithmetic
Old checks keep code and seeds (digest: 178 top-level segments byte-identical; 4 changed = leak fix `_run_program`, `_build_case`, `_check_stops_on_missing_input`, and the writes-outside loop extended to FORMS). Old weights: hN plan_rows stay 3, the three hN settlement checks 5 -> 1 (weight 2 is refused by tests_qc W2). Old positive 65, lever 165 (33 checks), total 230, lever share 71.7 %. Tests 77 (> 44), criteria 17. reward.toml test_output 1/460, judge 1/78.

## Judge changes
Dropped restatements R6 reruns_from_another_place, R8 runs_with_a_missing_input_file, R9 runs_with_a_base_that_has_no_requests. Added P-d probes reruns_with_a_closure_added (R12, solve.sh:196-205) and reruns_with_a_revised_availability (R13, solve.sh:207-224); ids renumbered R1..R17 (judge_qc J2). Probes R1-R6, R12, R13 = 24/39 = 61.5 %. Negatives -16 (R14 -5, R15 -3 unrun pass, R16 -5, R17 -3). a1 trajectory: low 9/39 = 23.1, mid 12/39 = 30.8 (wins R2, R8, R9, R10, R11; R15 fires), high 18/39 = 46.2 (adds R3, R6).

## Kill table (Docker, built tests, positive 230; full table WORK/COST_TABLE.md harden_r1 section)
| program | tests | lever kept /165 |
|---|---|---|
| a1 as delivered (paid) | 65 = 28.3 % | 0 |
| a1 first write | 65 = 28.3 % | 0 |
| design blind e8e9c82 / r2 | 108 = 47.0 % | 55 (alt only) |
| design blind r1 | 56 = 24.3 % | 20 |
| all-but-one (16 one-slip programs) | 6 to 65 (2.6 to 28.3 %) | 0 each |
| solve_no_cxml (one fact wrong) | 175 = 76.1 % | 110 |
| careful_reader (lever-aware, recorded) | 230 = 100 % | 165 |
| oracle solve.py | 230 = 100 % | 165 |
Loss kind WRONG everywhere (rc 0, documents written). Reference derive per hidden folder h1..h15 measured 4.7 to 9.9 s (max h10 9.85 s; 1/4 of RUN_LIMIT 60 = 15), `_runs/.../harden1-20261102T1341/witness.jsonl`; program runs at most 22.5 s. Witness folders WORK/h1_a1/witness/h7..h15: oracle EXACT on all nine, a1 first diff e.g. h7 summary.json.bases[0].allowance_granted got 0 want 10, h9 got 66 want 6, h10 allowance_used got 12 want 2.

## Leaks
All rows closed (OUT/LEAKS.md). TS-24: `_launch` own session, killpg and nobody sweep, read-back after kill, one run lock, case roots 0700 except during own run. Attacks: lift 60 net (26.1 %, -5 fired, lift_found 0), overwrite 65 (= a1), stub 1, forgery 1, hardcoded 6 net; all lever 0/165. Fork probe: built survivors 0, pre-build control 1.

## Predicted score (a1 program on new tests 28.3)
Final low (28.3+23.1)/2 = 25.7, mid 29.5, high 37.2; gate tests < 85 and rubric < 85 hold for every row except the lever-aware careful reader.

## Gates
Tests-only lanes from live kit exe_copy.py copies, `_runs/20261102/hangar-check-replan/hardengate-20261102T1412/` (chain.log ALL_DONE, every lane rc 0):
| lane | trial | reward | verifier s |
|---|---|---|---|
| oracle 1/2/3 | 5wbWr4Y / dcpoAvE / wUhTyGr | 1.0 / 1.0 / 1.0 | 473 / 476 / 496 |
| owner-only | KGAxpbL | 1.0 | 493 |
| nop | 6Qx3SSX | 0.0 | 333 |
| stub | dJXd9de | 0.0 | 416 |
| forgery | g6vCGaV | 0.0043 (1/230) | 423 |
| a1 as delivered x2 | 3xXsBwo / 57a7MVF | 0.2826 / 0.2826 | 306 / 361 |
Verifier max 496 s = 18 % of 2700. Oracle prints `check P10 ok` and `check P11 ok` with witnesses (closure West 2027-03-02 moves Q14683 to 2027-03-03; VT-AXK available_from 2027-03-03 moves Q14683 to 2027-03-03).
PRECHECK last line: `PRECHECK CLEAN` (tests 77, judge 17; warns X1 binary docx, A3 77 checks only). Validator domain-calculation: 39 passed, 0 failed, GATE PASS. xref_check: 12 entries, 0 findings. stacking_check: OUT/STACKING_CHECK.md (hand rulings PASS).
Tasks_INPUT: 7 changed files copied with cp -Rp; `diff -rq` empty; tree sha both 0163b9762e5b.
G12: 30 seeds per form (300 stopped at ~3 h, Ayush): h7 30/0, h8 30/0, h9 30/0, h10 30/0, h11 30/0, h12 30/0, h13 30/0, h14 30/0, h15 30/0 (ok/fail; 270 folders, 2103 s, _runs/20261102/hangar-check-replan/harden1-20261102T1341/gen30.jsonl).

## Docs changed
None of docs/*.md or the two docx. instruction.md:1 gains route1 R0.7 sentence "Leave enough of that time to finish and write your final reply." instruction.md:32-34 keeps "compared field by field ... only an exact match of a field counts" rather than R0.3's "graded whole" sentence, because the tests grade per field-group view with partial credit; master to rule.

## Not run / notes
- WORK/build_tests.py and WORK/build_judge.py are now stale (the build was a patch script, WORK/h1_a1/build_h1.py, from WORK/h1_a1/pre_build/); do not rerun them.
- customXml rows are ECMA-376 Part 1 Transitional; Word 2010+ drops customXml tags on save but keeps the rows, so the values are the same (QC_DEFENCE W fallback).
- Shipped closure table has a header only; P10 adds its row by copying the header row's markup.

## Lessons for the master
- lesson | template_change: fuzz Word inputs with ECMA-376 row containers (sdt, customXml) and mc:AlternateContent early; paid programs read direct w:tr children.
- lesson | template_change: tests_qc W2 refuses weight 2; plan down-weights in {1,3,5}.
- lesson | template_change: judge ids must be renumbered sequentially after drops (judge_qc J2).
- lesson | template_change: attack harness must deliver forking programs' outputs instead of running them as root (pipe held by daemon).
