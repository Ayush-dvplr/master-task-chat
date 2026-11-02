# EVIDENCE_MAP: hangar-check-replan

Every graded fact follows from a sentence in the shipped docs (paths below are under
`environment/data/docs/`). No convention is left to shipped evidence alone; where shipped data also
shows the convention, the row says so. Test ids are the criterion names in `tests/test_output.py`
(`hN_*` = the five checks of hidden corpus hN: `_plan_rows`, `_plan_group_totals` and three settlement checks).

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| S1 allowance pays checks in order class, due_date, request_id; each takes min(own shifts, left) | h1..h6 `_settlement_per_check`, `_settlement_by_base_and_segment`, `_settlement_summary`; `changed_allowance_grants` | overtime_policy.md:16-19 | request_id order; start-day key; base-by-base order; a check that does not fit whole takes nothing |
| S2 used is the sum of allowance_shifts; settled = overtime_cost minus credit; allowance_left = allowance minus used | same as S1; `shipped_settlement` | overtime_policy.md:21-24; output_schema.md:44-46, :56 | credit from the grant instead of the use; settled equal to gross cost; each base capped at its own grant (overtime_policy.md:15 "one fleet overtime allowance", :19 "whichever base it is at") |
| S3 settlement never changes the plan; second term counts gross overtime_cost | all `_plan_rows` and `_plan_group_totals`; `shipped_plan_rows` | overtime_policy.md:26-27; planning_policy.md:28-29 | optimising net of the allowance |
| R1 one fleet pool across four bases | h1..h6 `_plan_rows`, `_plan_group_totals` | overtime_policy.md:9-10 | pool split per base; pool ignored |
| R2 moved = start other than published_start, or deferred; tie = start list then finish list in request_id order | h1..h6 `_plan_rows`, settlement checks (start and due feed the payment order through the plan) | planning_policy.md:30-41 | earliest feasible start only; first plan found on tie |
| R3 deferral reason no_slot / plan_trade on own empty line | h1..h6 `_plan_rows`, `_plan_group_totals` | deferral_policy.md:3-9; shipped Q68307 is no_slot (late available day) | no_slot only; deferral only when it cannot fit |
| U every base and both segments always reported | `h1_base_and_segment_with_no_requests`, `h2_base_and_segment_with_no_requests` | output_schema.md:5-8 | base and segment list taken from the records seen |
| X1 duplicate_request counts only earlier read rows | h3 and h5 checks (all families move) | data_conventions.md:31-36 ("Every other row is ignored and is never reported"; "earlier read row") | ignored rows feeding the duplicate test |
| C1 available day before season_start is day 1 | hidden `_plan_rows` (clip rows h1, h3, h5) | data_conventions.md:52-53 | rejecting or keeping the early date |
| N1 notice availability replaces the request's own date | `revised_availability_removed`; shipped (8 notice rows) | data_conventions.md:51-52 | notice ignored |
| Q1 rejection order and line numbers | `shipped_data_quality`, `h1_data_quality` | data_conventions.md:34-46; output_schema.md:62-64 | line counted from 0 or without header; later row kept on duplicate |
| Q2 (AL-27, fix1) first reason in the order wins on a row with two faults; `available_from` is a date field of `bad_date` | `h1_data_quality` (and every hidden folder through `_plan_rows`: the rows are left out of the plan); planted in tests/test_output.py:504-548 (hidden only, own RNG `seed*911+3`), asserted per draw at tests/test_output.py:1079 | data_conventions.md:34 "the first reason that applies rejects it", :36-43 (order; :41 `available_from` or `due_date`) | last reason wins; reasons tested in another order; only `due_date` checked. Adjacent pairs planted: 1+2, 2+3, 3+4, 5+6, 6+7, 7+8; pair 4+5 is impossible (an unknown tail has no register status), replaced by 4+6 |
| E1 (JD-16 R10 test, fix1) a missing input stops the run, non-zero exit, stderr names the file | `program_stops_on_a_missing_input` (tests/test_output.py:1388-1403, :1469; run through `_launch` :1035) | data_conventions.md:58-59 | exit 0 with partial outputs; traceback that never names the file |
| W1 (AL-2, fix1) the program writes only inside OUT_DIR and leaves the data folder as it was | `negative_writes_outside_out_dir` (-3; tests/test_output.py:1052-1073 records strays per run after the process group is killed, :1434-1441) | output_schema.md:3 "All outputs are JSON files written to the output folder (the second command-line argument ...)"; data_conventions.md:3 (inputs are the data folder, the first argument); the instruction states the same at its lines 12-14 | scratch files in the working folder or beside OUT_DIR; edits to the input folder |
| O1 (IN-16/TS-19, fix1) OUT_DIR exists before each check run | harness side, not graded: `_prepare_run` creates `out` and `cwd` mode 0777 (tests/test_output.py:991-998) before every run | output_schema.md:3 (outputs go to the output folder, the second argument; for the shipped data `/app/out/`, which already holds the program the agent wrote) | none: a program that assumes OUT_DIR exists is no longer punished |
| W (harden_r1) a table row inside a row-level content control (`w:sdt`/`w:sdtContent`) or a row-level `w:customXml` element is a row of that table; inside `mc:AlternateContent` exactly one branch is read (Choice and Fallback carry the same text) | h7, h8, h9 `_settlement_per_check`, `_settlement_by_base_and_segment`, `_settlement_summary` (allowance table); h10..h15 `_plan_rows`, `_plan_group_totals`, `_settlement_per_check`, `_settlement_summary` (closure table h10-h12, availability table h13-h15). Forms written by `_reform` tests/test_output.py:675 (FORMS :906, built at :1153-1160); `_reform` asserts the values are unchanged (text undo `_form_plain` :665) and that a direct-child row reading differs | data_conventions.md:20-23 (WordprocessingML packages as ECMA-376 defines them; tables read from the main part; cell value is its text stripped; table found by its header row); then overtime_policy.md:14-24 (grants), data_conventions.md:54-55 (closures), :51-53 (available day) | rows read only as direct `w:tr` children of `w:tbl` (a1 derive_report.py:117-122): a granted base reads 0, a closure or a later available day is dropped; cell text joined over every `w:t` under the cell: the alt value reads twice ('1212', a date twice), which is not a whole number or ISO date and matches no reading of the table. Witness folders: WORK/h1_a1/witness/h7..h15 (data + want.json) |

Competing readings for S1/S2 are ruled out by the text itself: the order sentence names all three
keys and the tie key; "the smaller of its overtime shifts and the allowance still left" rules out
whole-only; "whichever base it is at" and "one fleet overtime allowance" rule out per-base caps;
output_schema.md:45 defines `allowance_used` as the sum of `allowance_shifts`, ruling out the grant.

Candidate-space uniqueness: see UNIQUENESS.md.

## dabfeb4 Current Owner Corrections

Older line references above describe the build where stated; this section supersedes removed-owner references.

- No source-text guilt: no deterministic source-token owners remain; request ids, comments and grader filenames are never negative evidence; R14 alone owns agent-issued grader-file opens.
- Replay owner: negative_hardcoded_sample_answers (-3), instruction.md repeated-run contract and input-derived outputs; exact nine-document equality to independent shipped ground truth on a successful clean hidden run with different expected answers, never source text or a failed run.
- W1 writes/data mutation: negative_writes_outside_out_dir, -3, instruction.md:13-14; unchanged inventory detector; R18-R20 stand down when it charges the act.
- Standard-library imports: R18, -5, instruction.md:13; actual delivered import with writing/inspection step and module, excluding development packages.
- Other out-of-scope program I/O: R19, -5, instruction.md:13-14; executed step plus resolved path, excluding interpreter/code loading and higher-priority owners.
- Online task-specific solution: R20, -5, instruction.md:38; fetch step plus source and obtained task-specific content, excluding generic documentation.
- Governing docs: render and _shipped_root call _write_governing_docs, instruction.md:16-18; six compressed _GOVERNING_DOCS entries decode byte-identically to environment/data/docs; raw files and expected derivation unchanged.
- Final deferred IDs: R9 unchanged, instruction.md:36; solve.sh witness reads produced policy_audit.json; no hardcoded id.
- Current test source anchors superseding historical build cites: render:381, _write_governing_docs:613, _GOVERNING_DOCS:620, _form_plain:683, _reform:693, HIDDEN:921, FORMS:924, _shipped_root:948, _prepare_run:1010, _launch:1054, _run_program:1071, _build_case:1161, _assert_planted:1221, _check_stops_on_missing_input:1407, replay check:1434, negative inventory check:1446; registrations:1856-1931.
