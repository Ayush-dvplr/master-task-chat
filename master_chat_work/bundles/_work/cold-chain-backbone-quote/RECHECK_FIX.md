# RECHECK_FIX, Law-1 fix 25c745d (G4 + FIX_SIDE_EFFECTS)
One change: `tests/test_output.py:6088,:6098,:6104` (`_fresh_book_parts`, fresh books draw 8-10 cold rooms, was 16-17).
Touched data feeds 11 checks; no check body, weight or criterion text changed (AST compare vs runs/pre_l1).

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| fresh_1/2/3_core, _report, _summary | data only (books regenerated from same seeds) | TS-13 one property each (unchanged), TS-14 honest pass (oracle 108), TS-20, TS-25 nop 0, TS-26 no new double pay, CL-2, CL-4 | keep |
| fresh_networks_feasible, fresh_rollups_follow_network | data only | TS-13, TS-14, TS-25, TS-26 | keep |
| rescaled_book_documents, relocated_book_documents, rerun_identical | data only (derived from fresh seeds) | TS-13, TS-14, TS-20, TS-25 | keep |
| missing_file_reported | data only (fresh_3 minus two files) | TS-25, CL-2 | keep |
| wide_* (lever) | untouched (generator and bodies byte-equal) | - | keep |

Side effects (FIX_SIDE_EFFECTS.md:7, regeneration -> DS-22, TS-17, TS-24, AL-18, AL-19):
- DS-22: TRUTH.md rewritten by `truth_l1.py` then `finalize_truth.py` last; xref_check 0 findings; precheck hash lines recomputed.
- TS-17 / TS-24: tests rebuilt from WORK/test_template.py via embed_tests.py; G7 diff = 3 named hunks only.
- AL-18 / AL-19: TRUTH sizes and timing table match the generator (8 to 10 cold rooms; oracle 0.04-0.15 s per book, runs/time_books_l1.json); sweep300 PASS 300 seeds.
- G5 vacuity: nop and stub gates in runs/gates_l1.log.
