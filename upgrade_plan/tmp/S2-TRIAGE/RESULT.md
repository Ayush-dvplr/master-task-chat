OPTION (b) RESULT: FREE TRIAGE SCRIPT (3 Nov 10:00, triage.py, TRIAGE.csv, no AI tokens)

Signals per task: (1) share of dict keys written by solution/solve.py that appear in no shipped text; (2) TRUTH.md sentences that admit a rule is undocumented or hidden only.
Checked against the 28 verified cards (11 DEFECT, 17 DESIGN):
1. Flag rule "missing share 0.3 or more, or any TRUTH admission" catches 6 of 11 DEFECT tasks (6d12f970, 3f39299a, 98ed74c1, 91f5740c, 8956ff8b, 9f5486ac) and wrongly flags 3 of 17 DESIGN tasks (8eae0f87, 275f885b, 7c2e77a1).
2. It misses DEFECTS about ids or values rather than key names (75407a55, b625f36e, 058cbab3, cf9b2067).
VERDICT: not reliable enough to skip cards. Useful only to rank tasks and to warn. Kept as a tool for later (the same check can run on Ayush's OWN bundles before QC: graded names that appear in no shipped doc).
