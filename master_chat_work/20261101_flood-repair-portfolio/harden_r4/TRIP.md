# TRIP flood-repair-portfolio harden r4 (ea94780)

Bundle tree sha before any work: 931f8f817d76 (= Tasks_INPUT = attempt-3 bytes). QC kit HEAD 5574d77e.
a3 program: `20261101_flood-repair-portfolio/a3_score/a3_out/derive_report.py` (697 lines, sha 69670ef2...).

## Reused by reference
- `harden_r3/TRIP.md` (R3 trajectory items: contract.md read whole at openhands_sdk.txt L469; last
  correctness check step 43; 92 min of speed work; no final reply; no shipped-fitted literals) and
  its fuzz table (1,500 generator books + 141 targeted cases: a3 = reference on every stated rule).
- `a3_score/A3_SCORE.md`: tests 108/108, timeout lever 78/78 kept (a3 5.2-8.3 s vs 20 s limit),
  judge low/mid/high 13.33/30/40, predicted final 65.
- Conclusion carried over: no WRONG fact is left in the current docs; only a new documented rule
  can open a separating case.

## Where the a3 program applies each existing rule (derive_report.py line)
| rule (contract.md line) | a3 location | what a new rule would touch |
|---|---|---|
| manifest, MISSING_FILE (:19) | L87-94 | - |
| data rows, row numbers (:21) | table_dicts L40-57 | - |
| registers sites/regions/crews (:25-27) | L106-115 (first wins) | crew mode lookup |
| round grouping, declared order (:33-35) | L123-139, L147 | - |
| proposal checks (:37) | check_proposals L184-199 | a pre-check filter |
| segment/permit/exclusion checks (:38-40) | L201-224 | - |
| first faulty file in declared order (:35) | L226-241 | - |
| benefit formula, NONPOSITIVE_BENEFIT (:44-50, :42) | L244-260 | - |
| crew exclusive conflict (:54) | build_conflicts L266-272 (shared crews: no edge) | crew capacity rule |
| permit held/applied conflict (:56) | L274-281 | - |
| exclusions, site expansion, sources (:58) | L283-298 | - |
| portfolio = independent set, max total (:62) | plan L301-309 -> max_weight_independent_set | where a natural adaptation hooks in |
| sorted-id tie rule (:62) | weight encoding L346 (benefit<<n | 1<<(n-1-i)) | - |
| per-component solve | components L354-368 | a cap across components breaks this split |
| reductions (isolated take, weight dominance, neighbour dominance) | reduce_verts L370-406 | invalid once a non-edge coupling exists |
| exact solvers + time switch | elimination DP L426-480, B&B L511-540, plan_verts L552-557, DP_DEADLINE L19-32 | state would need a count |
| every figure from the chosen portfolio (:64) | build_outputs L570-659 | - |
| region / segment rollups (:76-78) | slice_doc L652-674 | - |

## Consequence for the design
The a3 core is a pure graph MWIS: reduce, split into components, solve each exactly, union.
Every shared-crew relation is dropped at L266-272 (no edge). A rule that limits how many selected
proposals a shared crew may hold couples proposals that are in different components and are not
adjacent; it is invisible to reduce_verts and to the component split. The natural places an agent
would add it are (1) after plan() as a post-step that trims the over-cap crew and (2) before
plan() as a local filter on the crew's members. Both are tested in the kill table (DESIGN.md).
