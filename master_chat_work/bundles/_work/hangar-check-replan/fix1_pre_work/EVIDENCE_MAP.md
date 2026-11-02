# EVIDENCE_MAP: hangar-check-replan

Every graded fact follows from a sentence in the shipped docs (paths below are under
`environment/data/docs/`). No convention is left to shipped evidence alone; where shipped data also
shows the convention, the row says so. Test ids are the criterion names in `tests/test_output.py`
(`hN_*` = the four checks of hidden corpus hN).

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| S1 allowance pays checks in order class, due_date, request_id; each takes min(own shifts, left) | h1..h6 `_settlement_per_check`, `_settlement_by_base_and_segment`, `_settlement_summary`; `changed_allowance_grants` | overtime_policy.md:16-19 | request_id order; start-day key; base-by-base order; a check that does not fit whole takes nothing |
| S2 used is the sum of allowance_shifts; settled = overtime_cost minus credit; allowance_left = allowance minus used | same as S1; `shipped_settlement` | overtime_policy.md:21-24; output_schema.md:44-46, :56 | credit from the grant instead of the use; settled equal to gross cost; each base capped at its own grant (overtime_policy.md:15 "one fleet overtime allowance", :19 "whichever base it is at") |
| S3 settlement never changes the plan; second term counts gross overtime_cost | all `_plan_fields`; `shipped_plan_rows_and_rejections` | overtime_policy.md:26-27; planning_policy.md:28-29 | optimising net of the allowance |
| R1 one fleet pool across four bases | h1..h6 `_plan_fields` | overtime_policy.md:9-10 | pool split per base; pool ignored |
| R2 moved = start other than published_start, or deferred; tie = start list then finish list in request_id order | h1..h6 `_plan_fields`, settlement checks (start and due feed the payment order through the plan) | planning_policy.md:30-41 | earliest feasible start only; first plan found on tie |
| R3 deferral reason no_slot / plan_trade on own empty line | h1..h6 `_plan_fields` | deferral_policy.md:3-9; shipped Q68307 is no_slot (late available day) | no_slot only; deferral only when it cannot fit |
| U every base and both segments always reported | `h1_base_and_segment_with_no_requests`, `h2_base_and_segment_with_no_requests` | output_schema.md:5-8 | base and segment list taken from the records seen |
| X1 duplicate_request counts only earlier read rows | h3 and h5 checks (all families move) | data_conventions.md:31-36 ("Every other row is ignored and is never reported"; "earlier read row") | ignored rows feeding the duplicate test |
| C1 available day before season_start is day 1 | hidden `_plan_fields` (clip rows h1, h3, h5) | data_conventions.md:52-53 | rejecting or keeping the early date |
| N1 notice availability replaces the request's own date | `revised_availability_removed`; shipped (8 notice rows) | data_conventions.md:51-52 | notice ignored |
| Q1 rejection order and line numbers | `shipped_plan_rows_and_rejections`, `h1_data_quality` | data_conventions.md:34-46; output_schema.md:62-64 | line counted from 0 or without header; later row kept on duplicate |

Competing readings for S1/S2 are ruled out by the text itself: the order sentence names all three
keys and the tie key; "the smaller of its overtime shifts and the allowance still left" rules out
whole-only; "whichever base it is at" and "one fleet overtime allowance" rule out per-base caps;
output_schema.md:45 defines `allowance_used` as the sum of `allowance_shifts`, ruling out the grant.

Candidate-space uniqueness: see UNIQUENESS.md.
