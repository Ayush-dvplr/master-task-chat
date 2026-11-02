# A: yard-rehandle-ledger-recompute

**Verdict: PARTLY**. The recorded tests score of 16.42 is mostly a verifier permission artefact (H6). Only 21 of 68 points are a genuine loss, and the QC re-grade puts them all in the vessel family.

## Recorded run
- report.json: 5 tests passed, 28 failed. Recorded 11/67 = 16.42. exception_info is null, no negative fired, and ctrf messages are empty (the s1.py scan).
- Failed positives: shipped_vessel_family_exact (3), shipped_manifest_exact (3), program_minted_spines_exact (5), and program_{strained,wide,sparse}_{state,yard,vessel}_exact (9 x 5 = 45).
- Agent run: 11:20:55-11:44:56 UTC (24 min). It ended normally with a final message at trajectory step 79. No timeout.

## The artefact (program tier, 50 points recorded)
- QC report `Kunwar_Singh_yard-rehandle-ledger-recompute_QC_Report.md:9`: before the fix, the owner-only run scored 0.2537.
- `:34` F1: all ten `program_*` checks returned False on a correct submission. Cause: the program was run as an unprivileged user without first being made readable. The fix is `_grant_read` (current tests/test_output.py:5852), which adds mode|0o055 on the parent.
- `:74`: "re-graded ... read **47 of 68 (0.6912)**, against the recorded 11 of 67 (0.1642). The H6 bug had suppressed all ten `program_*` checks on a submission that in fact generalised correctly; the remaining 21 weight of loss is a genuine error confined to the vessel family and the manifest that digests it".
- Gate named: every `_run_program` call (tests/test_output.py:5915) failed with a permission error, so it returned a failure for every seed. This was not stated in the instruction because it is a grader bug, not a task rule.

## Genuine loss (21 of 68 after the fix)
- shipped_vessel_family_exact (3), shipped_manifest_exact (3), and program_{strained,wide,sparse}_vessel_exact (3 x 5). All are **wrong VALUE**. The manifest digests every document, so one wrong vessel document also fails the manifest.
- The QC report at `:107` gives the shape of one wrong value: "one wrong value scores 0.912 (62 of 68, losing shipped_vessel_family_exact 3 and shipped_manifest_exact 3)". On hidden seeds the same error recurs in each vessel family, so it costs 15 more.
- The agent's spine family passed, so ration shares, load eligibility and terminal reconciliation are right. That rules out the QC M1 "Reading B" ambiguity (`:57-63`): Reading B also loses the spine.
- **The exact vessel document and field that differ were NOT determined.** I could not run the reference. Static candidates (INFERRED): which boxes appear in the manifest or cutoff counts, assessed_cents of the deferred box, or berth-report/audit fields.
- Self-consistency check I ran: for all 6 vessels, the agent's departure order equals its own manifest rows sorted by (class_rank, stow_sequence, bay_no, box_id).

## Notes
- Wrong-reading negatives (ration_run_to_convergence, ration_rounds_once_at_end, redistribution_across_the_pairing, alphabetical_ladder_order, free_capacity_before_reserved, confirmation_overturns_the_ladder, absent_mass_read_as_zero, slot_boundary_opens_the_slot): none fired. The spec spells out each of these traps, for example spec_stage_y13_quay_ration.md:60-61 and :72-74.
- Genuine test points lost: 21/68 by the QC re-grade. Of the 50 program-tier points, 35 were lost only to the permission bug; the 15 on the three vessel families are genuine (the same error as the shipped vessel family).
