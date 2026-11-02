# DIAGNOSIS: sensor-network-lsq-correlated-adjustment, v0 run (claude-opus-5, Run 1)

## Result
- Tests channel: 1.0 (24 of 24 checks recorded in ctrf.json pass, 64 of 64 positive weight; no negative fired).
- Judge: it ran (gpt-5.6-sol, mode individual), 22 of 52 positive weight. Recorded reward 0.7115 = 0.5 x 1.0 + 0.5 x 0.423. The prompt says "no judge key", but reward.json shows a judge score.
- Permission trap: did not fire. Both held-out re-executions ran the agent program as nobody and passed (test-stdout: `verdict=REJECT_HIGH dof=1016 u=4 n=1020 ...` and `verdict=REJECT_HIGH dof=1019 u=3 n=1022 ...`). The grader `chmod 0644`s the program in place and does not open `/app/out` to other users, so it relies on Harbor creating `/app/out` as 0777. Fixed in Phase 2 with a copy into a grader temp dir.

## How the agent solved it
It read schema.md once (step 3), the header blocks (steps 5, 11), wrote one program (steps 20 and 22) and ran it once: step 23 printed `verdict=PASS dof=1019 u=3 n=1022 blunders=18 downweighted=3 sigma0_sq=1.0772532857`. Every later step was a format check. No lever cost it a second attempt.

## Why every lever leaked (detail in `_work/.../LEVERS.md`)
1. Answer key in every file. `trap_block()` appended 12 `TRAP i: <rule>; inverse: <exact fix>` lines to every shipped header, JSON `_traps` arrays, sqlite `traps` tables, the workbook, PDF and DOCX (step 5 and step 11 quote them). The fix for each convention sat next to the data it governs.
2. Full-answer confirmation. `chi_square_bounds_table.csv` states `center = dof * chi_center` and the shipped row brackets the correct vTPv, so a correct pipeline prints PASS and almost any wrong one prints REJECT. Step 23 is that check.
3. Partial confirmation. `observation_weight_manifest.csv` column `apriori_sigma_base` prints every converted sigma (step 17), and the agent compared it with its own conversion (step 32).
4. schema.md labels each rule `(Trap: ...)` and prints the true unit factors, so no rule needs to be combined with another file.

## Score composition (v0)
- Rule-isolating checks (one documented rule or copied value: u, k, crit, origin, provenance, canonical keys, status consistency, artifact set): 8 of 64 positive weight = 12.5%.
- Shipped-data-only checks (graded on `/app/out` from the shipped extract, where the answer is confirmable): 54 of 64 = 84.4%. Only the two held-out re-executions (10 of 64 = 15.6%) grade unseen inputs. This breaks study rule 11 (at most 5%).

## Causes and the Phase 2 fix for each
| cause | fix |
|---|---|
| trap blocks with inverses in every file | 2.3: remove trap blocks and the `TRAP` answer lines; schema keeps the rules without trap labels or worked values |
| PASS band confirms the chain | 2.3: acceptance centres per row from the table (no formula), the shipped band does not bracket the answer |
| manifest sigma column | 2.3: drop `apriori_sigma_base` |
| 84% weight on shipped data | 2.3: re-weight onto whole documents from three reseeded hidden extracts; shipped-only weight at most 5% |
| no lever needs two files or has a rare boundary | 2.3: new levers (station centring split across schema and the station register, angular misclosure reduction with straddle rows, revision-ranked duplicate records across shards) |
| permission reliance on Harbor's /app/out mode | 2.1: `_grant_read()` copy, lock and process-group kill |

No cause found outside Phase 2. No DIAGNOSIS CONFLICT.
