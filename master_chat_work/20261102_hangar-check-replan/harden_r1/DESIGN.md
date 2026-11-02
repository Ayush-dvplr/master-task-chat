# DESIGN: hangar-check-replan harden r1 (board a79e23e, route 1)

Bundle tree c91e926ac01c (= Tasks_INPUT = a1 bytes). Paid a1: final 75.0 = tests 100.0 (137/137) + judge 50.0 (21/42).
Evidence: OUT/TRIP.md (trajectory + fuzz), kill logs `_runs/20261102/hangar-check-replan/harden1-20261102T0200/`
(kill1/kill2/kill3 .jsonl + kill1_sum.txt, kill3_sum.txt), prototypes WORK/h1_a1/proto/.

## 1. Diagnosis

a1 read every doc and both Word files, built an exact DP that matches the reference, and checked it against
full enumeration on small folders. Every settlement and plan branch the generator can fire is EXACT for the a1
program (fuzz, 5904 folders: 2100 generator-branch folders, 300 seeds x 7, and 264 value mutants all MATCH; the only
DIFFs are Word-markup mutants, TRIP.md section 5). Family 4b finds nothing: the a1 source holds
only documented constants (TRIP.md section 3).

The one place a1 stopped checking is the Word reader. data_conventions.md:20-23 says the two .docx inputs are
"WordprocessingML packages as ECMA-376 defines them", tables are read from the main document part, a cell's
value is its text with spaces removed, and each table is found by its header row. a1 reads rows with
`tbl.findall(w:tr)` (direct children only) and a cell as the join of every `w:t` below it (a1 L103-127), and it
tested only the markup its own synth.py wrote (step 27). Three markup forms that ECMA-376 defines for table
rows and runs, each holding the same values, make the a1 program write a valid but WRONG report:

| form | ECMA-376 | what a1 does |
|---|---|---|
| sdt: data rows inside a row-level content control (`w:tbl/w:sdt/w:sdtContent/w:tr`, Word repeating section) | Part 1, CT_Tbl content: `w:tr`, `w:customXml`, `w:sdt` (EG_ContentRowContent) | rows skipped |
| cxml: each data row inside a row-level `w:customXml` element | Part 1, same content group | rows skipped |
| alt: each value-cell run inside `mc:AlternateContent` with `mc:Choice` and `mc:Fallback` carrying the same run | Part 3 (Markup Compatibility): a consumer processes exactly one branch | text doubled, e.g. `12` read as `1212`, a date read as `2027-03-042027-03-04` (a1 then drops the row) |

Header rows stay plain markup, so every reader finds the table; only data rows change. Every value is the same
under every valid reading of the package; the doubled or missing rows contradict every valid reading, so each
graded fact is determinate (LEVER_RULES 0b). Forms that only crash a1 (strict namespace, `./word/...` target,
cell-level sdt, item/class table rows) are excluded: no stated limit, Law-1 v3.5 does not count them.

## 2. Levers (family 4a, L2 held-out; docs unchanged; 4b none; 4c not needed)

Nine new hidden folders, each its own seed and RNG (G8), built by the existing `_planted_corpus` (all old planting
asserts hold), with expected values derived from the plain folder BEFORE the markup change (values are unchanged, so
the reference `_docx_tables` and `derive` stay byte-identical). Each folder runs in its own call.

| folder | table changed (rule) | form | checks (weight) |
|---|---|---|---|
| h7 | planning_limits base/allowance_shifts (overtime_policy.md:14-19, data_conventions.md:14) | sdt | settlement_per_check 5, settlement_by_base_and_segment 5, settlement_summary 5 |
| h8 | same | cxml | same three, 5 each |
| h9 | same | alt | same three, 5 each |
| h10 | disruption_notice base/from/days closures (data_conventions.md:54-55) | sdt | plan_rows 5, plan_group_totals 5, settlement_per_check 5, settlement_summary 5 |
| h11 | same | cxml | same four, 5 each |
| h12 | same | alt | same four, 5 each |
| h13 | disruption_notice tail/available_from (data_conventions.md:51-53) | sdt | same four, 5 each |
| h14 | same | cxml | same four, 5 each |
| h15 | same | alt | same four, 5 each |

New checks 33, lever weight 3x15 + 6x20 = 165. Allowance folders grade settlement only (the plan is not changed by
grants, overtime_policy.md:26-27); closure/availability folders grade plan and settlement views (different
observables per check, TS-26 as hN). BRANCH_FIRE: a verify-time assert in each folder that an independent extended
reader returns the plain tables and the direct-child reader does not; offline G12 over 300 seeds per variant that
the naive reading changes the graded views (kill1: fire 'differs' on every seed; avail_alt naive date parse crashes).

Old weights (weights only, check code and seeds byte-identical): h1..h6 plan_rows 3->2, the three h1..h6 settlement
checks 5->2. Old positive 137 -> 77. New positive 242. Tests 44 + 33 = 77 (> 44, stated here). Lever share
165/242 = 68.2%.

## 3. Kill table (Docker, hangar-tests, --memory 4g --cpus 2; 3 seeds per variant; letters = plan_rows,
plan_groups, settle_checks, settle_groups, settle_summary; E EXACT, W WRONG, C CRASH)

| program | allow sdt/cxml/alt | close sdt/cxml/alt | avail sdt/cxml/alt | lever pts kept /165 | max s |
|---|---|---|---|---|---|
| a1 (paid, unchanged) | EEWWW / EEWWW / EEWWW | WWWWW x3 | WWWWW x3 | 0 | 2.0 |
| a1 first write (steps 19+20) | EEWWW / EEWWW / EEWWW | WWWWW x3 | WWWWW x3 | 0 | 18.1 |
| blind e8e9c82 | EEWWW / EEWWW / EEEEE | WWWWW / WWWWW / EEEEE | WWWWW / WWWWW / EEEEE | 55 | 1.2 |
| blind r2 | EEWWW / EEWWW / EEEEE | WWWWW / WWWWW / EEEEE | WWWWW / WWWWW / EEEEE | 55 | 1.0 |
| blind r1 | EEWWW / EEWWW / EEWWW | WWWWW / WWWWW / EEWWW | WWWWW / WWWWW / EEWWW | 0 | 24.2 |
| all-but-one (16 w_* programs) | EEWWW or WWWWW | WWWWW | WWWWW, avail_alt CCCCC | 0 | 23.6 |
| solve_current (bundle oracle today) | EEWWW / EEWWW / EEWWW | WWWWW x3 | WWWWW / WWWWW / CCCCC | 0 | 23.4 |
| careful enumerator (reader walks sdt/customXml, one MCE branch) | EEEEE | EEEEE | EEEEE | 165 | 1.5 |
| solve_ext (Phase 2 oracle reader) | EEEEE | EEEEE | EEEEE | 165 | 19.2 |

Stale blind `proto/blind` (older data layout) crashes on everything and is excluded. Every generic solver and blind
loses >= 15% of lever points by WRONG (v3.7 e). The careful enumerator keeps every point (recorded, not a blocker).
Reference seconds max 10.2 per folder (<= 15 s = 1/4 of RUN_LIMIT 60).

## 4. Judge (tests/judge.toml; 18 -> 17 criteria)

Drop R6 reruns_from_another_place (the shipped run test already runs from another folder), R8
runs_with_a_missing_input_file (restates program_stops_on_a_missing_input), R9 runs_with_a_base_that_has_no_requests
(restates h1/h2 no-request checks) - JD-8. Keep probes R1, R2, R3, R4, R5, R7, R11 (P-h, no test grades malformed
input), J4 R10, J6 R12, process R13, R14, negatives R15-R18 (R16 J3a kept). Add two P-d probes (w3, important,
process, trajectory): N1 reruns_with_a_closure_added (copy of disruption_notice.docx with one closure row added,
shows a changed plan field) and N2 reruns_with_a_revised_availability (copy with one tail row added or changed,
shows a changed start_date). No probe names Word markup (J2b, no re-charging a trap the tests grade). solve.sh
gains `check N1 ok` / `check N2 ok` with witness lines (JUDGE_MAP oracle-shows rows). Positive 13 x 3 = 39; probes
R1-R5, R7, R11, N1, N2 = 27/39 = 69.2%.

a1 trajectory on the new judge: wins R2 (step 44 cross-sum of terms), R11 (step 47 exit code), R12, R13, R14;
loses R1, R3, R4, R5, R7, R10, N1, N2 (no closure or availability rerun; step 46 changed only the season); R16
fires. Low 9/39 = 23.1 (R2 lost); mid 12/39 = 30.8; high 18/39 = 46.2 (R3, R7 flip).

## 5. Prediction (tests-only labels)

a1 program on new tests: 77/242 = 31.8 (all old checks still pass, every lever check WRONG).
Final = (tests + judge)/2: low 27.4, mid 31.3, high 39.0. Gate: tests 31.8 < 85, rubric <= 46.2 < 85,
final < 40 at every grade. First-write and all-but-one <= 31.8 (<= 60); blinds e8e9c82/r2 about
(old part + 55)/242, estimated <= 50 (<= 65; measured in Phase 3 COST_TABLE).

## 6. Changes in Phase 2 (after go)

- tests/test_output.py: append markup helpers (sdt/cxml/alt restructure, independent extended reader), nine
  `_build_case`-style folders with own seeds, 33 registrations, weights above; old functions byte-identical
  (digest before/after, G7). tests/reward.toml top weights rewritten by script: test_output 1/(2x242) =
  0.002066115702479339 (was 1/274), judge 1/(2x39) = 0.01282051282051282 (was 1/84).
- solution/solve.py: Word reader L140-167 replaced by the solve_ext reader (walks `w:sdt`/`w:sdtContent`/
  `w:customXml` row wrappers, one `mc:AlternateContent` branch). solve.sh probes N1, N2. TRUTH.md sha by script last.
- tests/judge.toml: drop R6, R8, R9; add N1, N2; renumber.
- Docs, instruction.md, environment/data: unchanged (no lever announced, IN-17; shipped docx stay plain).
- WORK: LEVERS, COST_TABLE, QC_DEFENCE (rows IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, JD-5, JD-8, AL-2, AL-27,
  CL-2, CL-3 for h7-h15 and N1/N2), EVIDENCE_MAP (row W: data_conventions.md:20-23 + ECMA-376 Part 1/Part 3),
  JUDGE_MAP, BRANCH_FIRE, RULE_COVERAGE, XREF via xref_check.py.

## 7. Leaks (OUT/LEAKS.md)

Phase 1 forbids BUNDLE edits, so LEAKS.md is a draft with a plan; the fixes land in Phase 2 before the gates.
Open: W-03a TS-24 (`_run_program` without own session, process-group kill or nobody sweep; case roots 0755 and
run dirs 0777 kept all session). Fix: flood cb8dada `_launch`/`_stop_untrusted` (start_new_session, killpg,
/proc sweep of the run user), read-back of out only after the kill, private 0700 run dirs removed in finally,
case data 0700 after its run; fork probe must show 0 survivors; attack programs (lift, overwrite, stub, forgery,
hardcoded shipped answers) run in Docker and must score 0 lever points. All other LEAK_LIBRARY rows closed.

## 8. As built (Phase 2 deltas from this draft)

- Weight 2 is refused by tests_qc W2 (set -5,-3,-1,1,3,5): h1..h6 plan_rows stay 3, the three h1..h6 settlement
  checks go 5 -> 1. Old positive 65, lever 165, total 230; lever share 71.7%; reward.toml test_output 1/460 =
  0.002173913043478261, judge 1/78.
- judge_qc J2 asks for sequential ids: N1, N2 became R12 reruns_with_a_closure_added and R13
  reruns_with_a_revised_availability; old R7, R10..R18 renumbered R6, R7..R11, R14..R17. Probes R1-R6, R12, R13 =
  24/39 = 61.5% (the 27/39 above wrongly counted the malformed-input criterion, which is a code property).
- Measured (score0): oracle 230/230; a1 program 65/230 = 28.3; final low 25.7, mid 29.5, high 37.2.

## Lessons for the master
- a paid run that matches the reference on every generator branch still trusts its own input markup | template_change: route-1 fuzz always includes format-level equivalence mutators for every input format the docs name by standard
