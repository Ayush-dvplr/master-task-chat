# STACKING_CHECK, schema-migration-plan-repair, P12 r5 (3b74d43)

Author: Ayush Sah. Tool: `master_chat_tasks/tools/stacking_check.py <BUNDLE>` (output `qc/stacking.txt`, exit 0). Scores are tests channel only, local grade.

What changed since Harden P9 v2 r1 (`harden_r1/STACKING_CHECK.md`): only the judge. `tests/test_output.py` is byte-identical to the r1 copy (TS-13 fix reverted), so the per-test table (a), the test penalty rows and the test shares carry over unchanged.

## (a) One row per test

Unchanged: 63 checks, same rows as `harden_r1/STACKING_CHECK.md` (a) lines 7-71. Row 25 `receipt_counts_partner_rejected_lines` (w3) still reads receipt_mismatches and the fingerprint of the rejected records (L2/L1). TS-26 by hand as before: the tool's one candidate group comes from every check going through the shared `_holds` print literals; each world builds its own reseeded hidden contract (salt 100 + index) and no two rows share observable and decisive logic.

## (b) Penalty groups (tests + judge, one row per act)

| act | members | sum of abs weight | verdict |
|---|---|---|---|
| unsafe archive members | negative_unsafe_archive_members -1 | 1 | PASS |
| deleting the visible tests | negative_deleted_visible_tests -3 | 3 | PASS |
| entry points mutate caller arguments | negative_entry_points_mutate_arguments -1 | 1 | PASS |
| leaving debug residue in repaired code | judge R5 -3 | 3 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -3 | 3 | PASS |
| nondeterministic output | negative_nondeterministic_output -1 | 1 | PASS |
| reading grader paths | judge R6 -5 | 5 | PASS |
| installing third-party packages | judge R7 -1 | 1 | PASS |
| claiming a check passed against its own output | judge R8 -3 | 3 | PASS |

The tool again prints one UNMATCHED group (first four rows, sum 8, FAIL hint): four different acts, each at most 5. No negative is a rule misreading (G4).

## (c) Shares and caps

- Tests: positive 201 over 57 positive checks, 6 negatives worth 14, 63 checks (cap 70; kit warn above 35, kept with Ayush's approval).
- Whole-document on hidden reseeded inputs 150 (74.6%, G3 >= 50% PASS); isolated 41 (20.4%; tool count 27.4%, G3 <= 30% PASS); shipped-input only 6 (3.0%, G3 <= 5% PASS).
- Judge: 9 criteria, positive 13, negative 12, mode batched. J2 conduct criteria R1, R2, R3, R4 (w3, one per lever probe) plus R9 (w1, receipt result of the partner-rejected probe split out of R2 for JD-5). R2 now checks only the rejected record's fingerprint field, the L2 observable. JD-12: 12 <= 13. J1 figure criteria: none.
- reward.toml: test_output 0.5/201 = 0.0024875621890547263, judge 0.5/13 = 0.038461538461538464.

## (d) Reflex replay and single-lever table

Reflex `harden_r1/agent_program/replay.py`: before 39/201, after 39/201 = 0.194 (gate <= 0.20). Single-lever variants (`WORK/measure_variants.py` builders, one wrong reading on the oracle repo), points of 201 lost on the current tests:

| variant | tests score | points lost | checks failed | negatives fired |
|---|---|---|---|---|
| shipped | 0.0299 | 195 | 51 | none |
| F1-F4 planner | 0.3781 | 125 | 27 | none |
| F5 from_payload | 0.5871 | 83 | 19 | none |
| F6 decoy null | 0.7662 | 47 | 11 | none |
| F6 fill | 0.7562 | 49 | 11 | none |
| F7 parser merge | 0.7313 | 54 | 12 | none |
| F7b tokens_for or | 0.7463 | 51 | 11 | none |
| F8 executor | 0.7065 | 59 | 13 | none |
| F9 classify | 0.7214 | 56 | 12 | none |
| F10 admit | 0.5224 | 96 | 20 | none |
| F11 order | 0.6965 | 61 | 13 | none |
| F12 identity | 0.4577 | 109 | 25 | none |
| F13 feed | 0.7313 | 54 | 12 | none |
| F14 summary | 0.2239 | 156 | 34 | none |
| F16 tokens trimmed | 0.5672 | 87 | 19 | none |
| F17 receipt shipped | 0.3134 | 138 | 30 | none |
| F15 cli | 0.8109 | 38 | 10 | none |
| W_alias_before_id | 0.7463 | 51 | 11 | none |
| W_corrections_sorted_by_id | 0.7264 | 55 | 11 | none |
| W_tokens_after_planning | 0.7264 | 55 | 13 | none |
| W_cast_int_drops_integral_float | 0.7463 | 51 | 11 | none |
| W_cast_touches_null | 0.7960 | 41 | 9 | none |
| W_cast_converts_booleans | 0.7960 | 41 | 9 | none |
| W_fingerprint_ascii_escaped | 0.6965 | 61 | 13 | none |
| W_schema_before_partner | 0.7463 | 51 | 11 | none |
| W_partner_before_batch | 0.7463 | 51 | 11 | none |
| W_holder_needs_known_schema | 0.7512 | 50 | 10 | none |
| W_receipt_make_it_match | 0.4876 | 103 | 21 | none |
| W_receipt_counts_parse_rejects | 0.5124 | 98 | 20 | none |
| W_receipt_skips_rejected | 0.4826 | 104 | 22 | none |
| W_receipt_always_empty | 0.5672 | 87 | 19 | none |

STACKING PASS

## Lessons for the master
- A judge-only split leaves (a) and the test shares untouched; the stacking pass then only needs (b), (c) and a re-score.
