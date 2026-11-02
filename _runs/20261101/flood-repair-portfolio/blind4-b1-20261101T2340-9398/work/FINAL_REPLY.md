# Final reply

I built `/app/out/derive_report.py DATA_DIR OUT_DIR`, using only the Python 3 standard library. It reads the manifest and checks each round's files in the order the manifest declares. It computes each proposal's benefit and builds the crew, permit and exclusion conflicts. It then picks the portfolio with the highest total benefit for each round, keeping shared crews at 4 or fewer. When two portfolios tie, it takes the one whose sorted id list comes first. The solver is an exact tree-decomposition DP; the largest bag width on this book is 18. From the results it writes summary.json, policy_audit.json, data_quality.json, region_{North,South,West,East}.json and segment_{commercial,public}.json.

Checks on the shipped book B3790 (0.56 s wall time against a 20 s limit):
- Totals reconcile: 192 rounds = 173 planned + 19 rejected. The summary shows 1165 selected proposals and total benefit 2685141, and the four region files add up to the same figures.
- Segment totals: commercial 420 proposals / 1040381; public 468 proposals / 1330852.
- Conflicts: 3825 pairs (crew 913, permit 1511, exclusion 1955); 589 withdrawn permit rows were ignored.
- policy_audit has 2400 rows, one for each non-blank query line.
- 171 of the rounds were checked against brute force with no mismatches. The two large rounds (R57468 with 160 proposals, R79260 with 150) were checked for feasibility only.

Rejected rounds (19), by round id:
R12174 UNKNOWN_PROPOSAL (permits.csv row 619)
R16754 INVALID_INPUT (exclusions.json 193)
R18756 INVALID_INPUT (proposals.csv 1957)
R19209 UNKNOWN_PROPOSAL (exclusions.json 164)
R21904 DUPLICATE_PROPOSAL (proposals.csv 1741)
R33642 UNKNOWN_PROPOSAL (segment_codes.tsv 2003)
R40787 UNKNOWN_PROPOSAL (segment_codes.tsv 503)
R51684 INVALID_INPUT (proposals.csv 119)
R54358 UNKNOWN_PROPOSAL (exclusions.json 78)
R54721 INVALID_INPUT (segment_codes.tsv 1807)
R56052 INVALID_INPUT (segment_codes.tsv 2245)
R57174 UNKNOWN_PROPOSAL (permits.csv 2781)
R62811 INVALID_INPUT (proposals.csv 2568)
R69538 INVALID_INPUT (proposals.csv 1795)
R72683 INVALID_INPUT (permits.csv 867)
R83234 NONPOSITIVE_BENEFIT (proposals.csv 2091)
R92877 UNKNOWN_PROPOSAL (exclusions.json 1455)
R98987 DUPLICATE_PROPOSAL (proposals.csv 1705)
R99467 UNKNOWN_PROPOSAL (exclusions.json 694)
