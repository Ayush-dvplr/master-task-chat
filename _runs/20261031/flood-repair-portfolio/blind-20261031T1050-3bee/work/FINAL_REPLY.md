# Final reply (frozen 11:08 IST)

Built `/app/out/derive_report.py DATA_DIR OUT_DIR` (Python 3 stdlib only). It checks the manifest (missing file -> `ERROR MISSING_FILE <name>`, exit 1), validates every round in declared file order, builds each round's conflict graph from crews, active permits and exclusions, and picks the exact maximum-weight conflict-free portfolio (memoised branch-and-reduce; ties broken by the smallest sorted id list). It writes summary.json, policy_audit.json, data_quality.json, region_{North,South,West,East}.json and segment_{commercial,public}.json.

Checked on the shipped book B3790: one run, real 7.64 s (38% of the 20 s limit), exit 0, all 9 documents written. 192 rounds, 173 planned, 19 rejected; 1165 proposals selected, total benefit 2685141; 3825 conflict pairs (crew 913, permit 1511, exclusion 1955); 589 withdrawn permit rows; 2400 audit rows for 2400 non-empty query lines; no selected pair conflicts; the 4 regions add up to the summary. The first solver version was too slow (>120 s) and was replaced once.

Rejected rounds (19): R12174, R16754, R18756, R19209, R21904, R33642, R40787, R51684, R54358, R54721, R56052, R57174, R62811, R69538, R72683, R83234, R92877, R98987, R99467.
