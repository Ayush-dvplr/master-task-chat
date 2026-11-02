# Paid Source Confirmation c0f4820
P = Output_RFP/flood-repair-portfolio/trajectories/claude-opus-5/run_1/artifacts/app/out/derive_report.py (harness-relative).
- P:57-70 reads nonempty physical-line CSV/TSV rows, dropping the header and numbering from one.
- P:77-90 checks every manifest-declared file in declared order before loading.
- P:95-157 loads sites, regions, crew modes, case-sensitive INI values, proposals, segments, permits, exclusions and audit queries.
- P:301-303 sets STATE_CAP=1000000, LEAF_CAP=120000, COMBO_CAP=256.
- P:361-377 enumerates surplus-member removal masks; eleven shared members give C(11,7)=330 and return None.
- Important correction to the screening premise: P:353-354 then calls branch_and_bound, NOT greedy.
- P:699-702 initializes cap-four branch-and-bound; P:599-620 memoizes capacity-aware connected components.
- P:622-624 initializes a greedy incumbent; P:630-691 searches include/exclude branches with bounds and DP leaves.
- P:693-697 returns the best incumbent after catching an internal Timeout. No unconditional greedy return follows the 256 cutoff.
- P:23-25 sets shared limit four and internal book/round budgets 13/4 seconds; P:345-356 also catches an escaping Timeout.
- P:705-715 includes only shared crews with more than four proposals in the capped groups.
- Reference solution/solve.py:215-257 carries per-crew counts in frontier states; :261-293 selects the exact optimum across components.
- Independent tests/test_output.py:1260-1277 enumerates keep-four choices using its separate :1179-1257 portfolio oracle.
- Public basis: environment/data/contract.md:11-15 permits <=160 proposals and <=900 conflict records, with 20-second output deadline; :62 requires cap four and exact best benefit/tie selection.
No source or BUNDLE file changed. The cutoff itself is a branch change, not evidence of wrong output; measurement decides.

## Lessons for the master
Read the caller after a cutoff before predicting a heuristic fallback | no change: measurement requirement already applies.
