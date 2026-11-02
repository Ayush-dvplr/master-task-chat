# COST_TABLE (G10)

Real tests (tests/test_output.py, positive 139) on a patched copy of the fixed package; overall = 0.5 x tests% + 0.5 x 90 (judge assumed 90). One-fact-wrong score = tests% kept when only that reading is wrong. Every lever alone >= 25% and every all-but-one row < 70.

| row | lever | wrong reading | points lost | lost % | one-fact-wrong tests % | predicted overall |
|---|---|---|---|---|---|---|
| LV-BS-1 alone (all but this lever right) | LV-BS-1 | LAZY+FW2: internal events handled at the next external instant, external first | 105 | 75.5 | 24.5 | 57.2 |
| LV-BS-2 alone (all but this lever right) | LV-BS-2 | PREFAIL+STALE: preemption ends the attempt, stale token applied | 102 | 73.4 | 26.6 | 58.3 |
| LV-BS-3 alone (all but this lever right) | LV-BS-3 | ANYTERM+REDUP: release on any terminal parent with no cascade, redelivery applied twice | 102 | 73.4 | 26.6 | 58.3 |
| LAZY | LV-BS-1 | internal events processed only at external instants | 100 | 71.9 | 28.1 | 59.0 |
| FW2 | LV-BS-1 | external events before completion/expiry at a shared instant | 102 | 73.4 | 26.6 | 58.3 |
| PEREVENT | LV-BS-1 | dispatch after every external event | 102 | 73.4 | 26.6 | 58.3 |
| EXPFIRST | LV-BS-1 | expiry before completion at the same instant | 72 | 51.8 | 48.2 | 69.1 |
| FW1 | LV-BS-1 | completion guarded by attempt token only (stale completion after preempt+resume) | 102 | 73.4 | 26.6 | 58.3 |
| PREFAIL | LV-BS-2 | preemption counted as an attempt end | 102 | 73.4 | 26.6 | 58.3 |
| STALE | LV-BS-2 | stale attempt token applied | 102 | 73.4 | 26.6 | 58.3 |
| FW4 | LV-BS-2 | heartbeat/fail on a preempted job with the current token applied | 102 | 73.4 | 26.6 | 58.3 |
| FW3 | LV-BS-2 | lost units = ticks of the current run only | 51 | 36.7 | 63.3 | 76.7 |
| FW3b | LV-BS-2 | cancel of a running job uses remaining at run start | 79 | 56.8 | 43.2 | 66.6 |
| EVICTFAIL | LV-BS-2 | eviction counted as an attempt end | 102 | 73.4 | 26.6 | 58.3 |
| ANYTERM | LV-BS-3 | dependents released on any terminal parent, no cascade | 102 | 73.4 | 26.6 | 58.3 |
| REDUP | LV-BS-3 | identical redelivery applied a second time | 97 | 69.8 | 30.2 | 60.1 |
| FW5 | LV-BS-3 | cascade skips unsubmitted dependents | 102 | 73.4 | 26.6 | 58.3 |
| PRECSWAP | slip | audit precedence not_running before stale_attempt | 51 | 36.7 | 63.3 | 76.7 |
| FW2R | slip | checkpoint remaining read from run start (no interpolation) | 28 | 20.1 | 79.9 | 84.9 |
| SUBORDER | slip | dispatch tie by submission order | 102 | 73.4 | 26.6 | 58.3 |
| FIRSTWRITE | all | PREMORTEM first-write program (FW3b+FW4+FW5) | 102 | 73.4 | 26.6 | 58.3 |
| SHIPPED | all | shipped engine defects together | 105 | 75.5 | 24.5 | 57.2 |
| clean | none | reference package | 0 | 0.0 | 100.0 | 95.0 |

Slip rows FW2R, FW3 and PRECSWAP stay above 70 overall alone; they are slips inside a lever, not levers. No row triggers a negative.
