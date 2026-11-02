# Fresh P13 blinds scored on final tests (07:23-07:35 IST 30 Oct)
Command: WORK/BLIND_BRIEF.md (Docker 4g/2 cpu, one container at a time). Scores: WORK/blinds/score_<sha>.txt. Read only result json and program.

| blind | dir | tests % | lever points lost (of 68) | TIMEOUT share of lost lever pts | WRONG share | h2 s | h3 s | blind judge estimate |
|---|---|---|---|---|---|---|---|---|
| 9aaa86f | -8352 | 18/92 = 19.6% | 68 | 100% | 0% | 90.1 (timeout at 90 s test cap) | 90.1 (timeout) | 11-11 |
| 59480e5 | -273c | 18/92 = 19.6% | 68 | 100% | 0% | 90.1 (timeout) | 90.1 (timeout) | 11-17 |
| 25a31cb | -2fd8 | 18/92 = 19.6% | 68 | 100% | 0% | 90.1 (timeout) | 90.1 (timeout) | 11-14 |

Kept by all three: shipped_policy_audit, shipped_summary, shipped_data_quality, altered_copy_policy_audit, relocated_copy_summary, missing_customers_named (18). Lost: all 20 hidden checks (74 points, 68 lever), every one by TIMEOUT; no CRASH, no negative fired. Mutation runs 0.1-0.2 s.

Verdict: no blind keeps > 50% of lever points (0% kept). Timeout share is 100%, above the 70% option (c) cap: the loss is time-out only, not WRONG output.
