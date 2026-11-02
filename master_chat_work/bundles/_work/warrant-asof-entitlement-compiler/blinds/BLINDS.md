# Fresh blinds after build 6740572 (scored by master, 30 Oct 06:30-06:57, WORK/harness/score.py, DELIVERED=1, Docker 4g/2cpu)

| name | model | tests % | conv_* failed | other lost | score secs | gateway readings named |
|---|---|---|---|---|---|---|
| 92419ce | claude-opus-5-5 | 45.4 (69/152) | 16/16 (80 pts) | self_check_partition_exact 3 | 262 | own inferred conventions; 7/2199 shipped observations disagree |
| 787e598 | claude-opus-5-5 | 47.4 (72/152) | 16/16 (80 pts) | - | 881 | site-local midnight HR, grant start = quorum decided_at (not before requested), windows [start,end); fits all attestations |
| b6c896c | claude-opus-5-5 | 47.4 (72/152) | 16/16 (80 pts) | - | 290 | windows [start,end), HR site clock, grant start = quorum decided_at; 1 of 18 readings fits all |

Stop rule (any > 70 or two > 65): NOT hit. All three lose the whole convention lever (WRONG, no timeouts). Next: full P11 v3 QC bdd41f8.
