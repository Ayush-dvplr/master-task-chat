# STACKING_CHECK: schema-migration-plan-repair (P12 v12, board 08741c4)

Tool: `master_chat_tasks/tools/stacking_check.py` on BUNDLE (raw output: stacking_raw.txt). Tests unchanged (141 checks, 591 positive, negatives -14); judge 21 criteria, 43 positive (was 23 / 49). The only differences from the QC copy a97202e run are the judge counts.

## AL-28 penalty groups (unmatched bucket named by hand)

| act | tests | judge | sum abs w | verdict |
|---|---|---|---|---|
| archive holds an unsafe member path | negative_unsafe_archive_members -1 | - | 1 | PASS |
| deletes a visible repo test | negative_deleted_visible_tests -3 | - | 3 | PASS |
| entry point mutates its argument | negative_entry_points_mutate_arguments -1 | - | 1 | PASS |
| leaves debug residue in src | - | R13 -3 | 3 | PASS |
| states a figure that differs from the run summary | - | R17 -5 | 5 | PASS |
| overstates the size of a check it ran | - | R18 -3 | 3 | PASS |
| hardcodes the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -3 | - | 3 | PASS |
| nondeterministic output | negative_nondeterministic_output -1 | - | 1 | PASS |
| names or reads grader files | - | R14 -5 | 5 | PASS |
| third-party or network install | - | R15 -1 | 1 | PASS |
| claims a check passed that its output contradicts | - | R16 -3 | 3 | PASS |

The tool's FAIL row is its static "UNMATCHED act" bucket lumping six distinct acts; each is a different action and no action fires more than 5. Same on the QC copy; QC v12 AL-28 PASS.

## Other hints

- TS-26: 1 candidate group (the shared `[check]` wrapper text of the world and case checks; each runs a different case). Unchanged since v12, where TS-26 passed.
- TS-13 multi-assert hints: none.
- G3 hidden or mutated reruns 91.5% (>= 30%): PASS.
- J1 figure hints: none.

Verdict: PASS.
