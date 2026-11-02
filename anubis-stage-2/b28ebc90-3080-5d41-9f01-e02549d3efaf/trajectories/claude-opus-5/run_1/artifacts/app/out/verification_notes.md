# Verification notes - cycle HB-2034-231

Checks made against the papers in /app/data and the documents this run published.

last_window_start_ms 82320000
set_aside CAPACITY_DISPLACED 99
set_aside COOLDOWN 14
set_aside DISPLACED_FINAL 9
set_aside FALLBACK_DISPLACED 23
set_aside GATE_CLOSED 4
set_aside IMPLAUSIBLE_DEMAND 8
set_aside NO_FALLBACK_FITS 58
set_aside OCCURRENCE_CAP_ZERO 2
set_aside OUT_OF_DAY 1
set_aside PREREQ_MISSING 51
set_aside PREREQ_WITHDRAWN 3
set_aside READMITTED 3
set_aside RETIRED_ROUTINE 35
set_aside SUPPRESSED 86
set_aside UNKNOWN_CEILING 4
set_aside UNRESOLVED_ACTION 3

- The live workbook grid is the sheet `grid_beta`, matched on its key cell B1 reading `HB-2034-231` byte for byte; `grid_draft` differs in case, `grid_alpha` carries a suffix and `grid_current` carries a trailing space.
- The window grid read under RR1 against `window_frozen_revisions` and under RR6 from `origin_ms` 1140000 tiles the cycle: every window start equals the previous window's start plus its recorded difference, and the last window, W12, runs from 82320000 to 89820000, which is `day_end_ms`.
- The twelve windows carry ordinals 1 to 12 and W02 and W03 overlap, so the lower ordinal takes a trigger that two windows admit.
- Both digests were taken over bytes already written: core 14d6b40aa3d8f4ff4f59b9989e14efac489736b65e1700e032c2d6e6f92d9fea and publication b7ce7941261a0d8c1a114f72a0399c4c8e2b5d23b967edf9c970c77c23227317, and run_manifest.txt reproduces every one of the twenty six document digests.
- The control totals this cycle yields are actions_read 248, aliases_bound 428, instances_expanded 397, instances_eligible 297, edges_kept 278, cycles_settled 62, demand_rows 238, initial_allocations 135, displaced 103, fallback_proposals 45, overturned 9, final_instances 145, readmitted 3, terminal 97 and total_demand_mwh 248520.
- Two runs over /app/data produced identical bytes, and the same cycle under /tmp/datacopy produced them again; the paper directory compared byte for byte unchanged after every run.
- No window and device group draws more than the pool r10 offered it, mandatory overruns excepted and flagged: W05/DV-05 and W06/DV-02 carry overrun `yes` because their mandatory draw exceeds the ceiling.
- Five one shot overrides are spent by the second state pass: OV-006 3 to 2, OV-007 2 to 1, OV-008 3 to 0, OV-025 2 to 0 and OV-901 1 to 0.
- The shipped suite runs 13 tests with 0 failures and 0 errors on the repaired package, and the tests directory is carried through byte for byte.
- Every reason code published is a member of the closed vocabulary in glossary_and_reason_codes.md.
