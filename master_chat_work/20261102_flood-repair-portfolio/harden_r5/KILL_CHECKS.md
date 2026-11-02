# Per-Check Kill Table
Scope: H1-H3 only, seven existing checks/book, weights3/5/5/3/3/3/3=25, total75 positive points.
Columns in each sequence: feasible, optimal, summary, policy_audit, data_quality, regions, segments.
E=EXACT for that check; W=WRONG; T=TIMEOUT for the whole process so every check is unearned. No CRASH occurred.
Rows are based on actual verifier check replay, not only exit codes. No claim of a full108-point rescore.

| Program | H1 checks | H2 checks | H3 checks | Points H1/H2/H3 | Kept/75 |
|---|---|---|---|---|---:|
| paid_a4 | EEEEEEE | EEEEEEE | EEEEEEE | 25/25/25 | 75 |
| blind4_b1 | EEEEEEE | EEEEEEE | EEEEEEE | 25/25/25 | 75 |
| blind4_b2 | EWWWEWW | EWWWEWW | EWWWEWW | 6/6/6 | 18 |
| a3_natural | EWWWEWW | WWWWEWW | EWWWEWW | 6/3/6 | 15 |
| a3_correct | EEEEEEE | EEEEEEE | EEEEEEE | 25/25/25 | 75 |
| a3_prefilter | EWWWEWW | WWWWEWW | EWWWEWW | 6/3/6 | 15 |
| a3_unchanged | WWWWEWW | WWWWEWW | WWWWEWW | 3/3/3 | 9 |
| dae9563 | TTTTTTT | TTTTTTT | TTTTTTT | 0/0/0 | 0 |
| elim | WWWWEWW | WWWWEWW | WWWWEWW | 3/3/3 | 9 |
| vebest | WWWWEWW | WWWWEWW | WWWWEWW | 3/3/3 | 9 |
| a1 | TTTTTTT | TTTTTTT | TTTTTTT | 0/0/0 | 0 |
| first_write | TTTTTTT | TTTTTTT | TTTTTTT | 0/0/0 | 0 |
| all_but_one | TTTTTTT | TTTTTTT | TTTTTTT | 0/0/0 | 0 |
| lever_aware | EEEEEEE | EEEEEEE | EEEEEEE | 25/25/25 | 75 |
| reference | EEEEEEE | EEEEEEE | EEEEEEE | 25/25/25 | 75 |
| reference_busy | EEEEEEE | EEEEEEE | EEEEEEE | 25/25/25 | 75 |

Seconds are in DESIGN.md; machine rows in WORK/r0_lever/results.json, replay_results.json and extra_results.json.
Replay uses BUNDLE/tests/test_output.py:1480-1526 unchanged; document comparator :1293-1317.
Historical programs/roles: WORK/h1_a1/KILL_TEST.md:3 and h4_rule/proto/drive4.sh, drive4_blind.sh.
Paid key row loses0/75 measured and0/108 toward the >=44 required; wrong older rows do not rescue the lever.
NO_WITNESS.md records why no smallest paid-program differing input is supplied.

## Lessons for the master
An old blind failing while the current paid program passes is not a successful hardening | no change: R0 key-row rule applies.
