Built `/app/out/derive_report.py` (python3 stdlib only, `python3 derive_report.py DATA_DIR OUT_DIR`) implementing contract.md: manifest MISSING_FILE check, per-round fault checks in manifest order, benefit valuation, crew/permit/exclusion conflicts, and an exact max-benefit portfolio with the sorted-id tie-break (weights embed the tie-break bits so the optimum is unique; exact bucket-elimination DP over a min-fill order, with branch-and-bound only to resolve shared crews having more than 4 proposals). Ran it on the shipped book B3790 into `/app/out`: all 9 documents written in 0.68 s wall (limit 20 s).

Checks: every document has the stated keys; counts and totals add up in summary, region and segment docs; the four region totals sum to the summary total 2685141; no chosen portfolio violates a crew, permit, exclusion or shared-crew-cap constraint; policy_audit has one row per non-empty query line (2400).

Key figures: 192 rounds, 173 planned, 19 rejected, 1165 selected proposals, total benefit 2685141; 3825 conflict pairs (crew 913, permit 1511, exclusion 1955); 589 withdrawn permit rows in planned rounds.

Rejected rounds (19): R12174, R16754, R18756, R19209, R21904, R33642, R40787, R51684, R54358, R54721, R56052, R57174, R62811, R69538, R72683, R83234, R92877, R98987, R99467.
