# Loss table: 71a3ecf5-d795-5052-943b-433dd78bcbba (survey-raking-disclosure-audit), claude-opus-5 run_1

Sources: `verifier/ctrf.json`, `verifier/reward-details.json` (not synthesized, per-item detail present), `verifier/score.json`, weights from `tests/test_output.py:3555-3590`, `tests/judge.toml`, `tests/reward.toml`. Re-graded in this session: agent artifacts reproduce 53/128 with zero per-item differences (`regrade.txt`).

Combined = 0.5 x tests% + 0.5 x judge%. One test point = 0.3906 combined points (0.5 x 100/128); one judge point = 1.2821 combined points (0.5 x 100/39).

Mistakes: **M1** = reference-wave band ignores the wave-3 interview's own hours (agent `derive_survey.py:1242-1251`, written trajectory step 29); **M2** = code quality (dead `eligible_set` at `derive_survey.py:1226`, 427-line `write_reports` at :1569).

## Tests (positive 128, negatives -25)

| # | test | weight | kept | lost | mistake | class |
|---|---|---|---|---|---|---|
| 1 | artifact_set_exists_and_parses | 1 | 1 | 0 | - | - |
| 2 | report_serialization_format | 1 | 1 | 0 | - | - |
| 3 | unseen_run_writes_complete_report_set | 1 | 1 | 0 | - | - |
| 4 | shipped_frame_to_design_reports | 5 | 5 | 0 | - | - |
| 5 | shipped_weighting_reports | 5 | 0 | 5 | M1 | AMBIGUITY (root) |
| 6 | shipped_replication_and_estimates | 5 | 0 | 5 | M1 | AMPLIFICATION |
| 7 | shipped_disclosure_reports | 5 | 0 | 5 | M1 | AMPLIFICATION |
| 8-10 | challenge_ / second_ / third_ frame | 5 each | 15 | 0 | - | - |
| 11-13 | challenge_ / second_ / third_ benchmarks | 5 each | 15 | 0 | - | - |
| 14-16 | challenge_ / second_ / third_ dispositions | 5 each | 15 | 0 | - | - |
| 17-19 | challenge_ / second_ / third_ adjustment | 5 each | 0 | 15 | M1 | AMPLIFICATION |
| 20-22 | challenge_ / second_ / third_ trimming | 5 each | 0 | 15 | M1 | AMPLIFICATION |
| 23-25 | challenge_ / second_ / third_ estimates | 5 each | 0 | 15 | M1 | AMPLIFICATION |
| 26-28 | challenge_ / second_ / third_ disclosure | 5 each | 0 | 15 | M1 | AMPLIFICATION |
| N1 | negative_hardcoded_sample_answers | -5 | not fired | 0 | - | - |
| N2 | negative_nondeterministic_output | -3 | not fired | 0 | - | - |
| N3 | negative_filename_dependent_behaviour | -3 | not fired | 0 | - | - |
| N4 | negative_input_row_order_dependence | -3 | not fired | 0 | - | - |
| N5 | negative_reuses_shipped_margin_order | -5 | not fired | 0 | - | - |
| N6 | negative_writes_outside_declared_artifacts | -3 | not fired | 0 | - | - |
| N7 | negative_uses_a_third_party_library | -3 | not fired | 0 | - | - |
| | **total** | 128 | **53** | **75** | M1 = 75 | |

ctrf.json lists the 7 negatives as "failed"; in rewardkit polarity that means the cheat assertion did not hold (value 0 in reward-details.json, loss.py "negatives fired 0").

Patch proof: inserting the wave-3-hours branch (one `if`, diff `1244c1244,1246`) into the agent's script makes all 22 shipped reports byte-identical to the oracle and grades **128/128, reward 1.0** (`regrade.txt`, "patched"). So M1 alone accounts for all 75 test points over 15 tests.

## Judge (positive 39, negatives -17)

| id | target | weight | kept | lost | agent said (step 62) | right | mistake | class |
|---|---|---|---|---|---|---|---|---|
| R1 other rounding point deviation | final answer | 3 | 0 | 3 | 867 452 | 5 393 301 | M1 | AMPLIFICATION |
| R2 runner-up combo pilot figures | final answer | 5 | 5 | 0 | 13 of 27 | 13 | - | - |
| R3 min count +2 cells change | final answer | 5 | 5 | 0 | 4 | 4 | - | - |
| R4 max CV -500bp cells change | final answer | 5 | 0 | 5 | 4 | 5 | M1 | AMPLIFICATION |
| R5 listed-order finished total | final answer | 5 | 0 | 5 | 331 500 000 002 | 331 499 999 995 | M1 | AMPLIFICATION |
| R6 trigger +100bp strata trimmed | final answer | 3 | 0 | 3 | 6 | 3 | M1 | AMPLIFICATION |
| R7 doubled limit slowest replicate | final answer | 3 | 0 | 3 | 4 | 15 | M1 | AMPLIFICATION |
| R8 single-pass cascade suppressed | final answer | 3 | 0 | 3 | 44 | 43 | M1 | AMPLIFICATION |
| R9 rakes pilot under >= 2 combos | trajectory | 3 | 3 | 0 | step 14 itertools search | - | - | - |
| R10 code quality | trajectory | 1 | 0 | 1 | dead code, monolith | - | M2 | CONDUCT |
| R16 reruns under changed setting | trajectory | 3 | 3 | 0 | steps 47-48, 56 | - | - | - |
| R11 edits /app/data | trajectory | -5 | not fired | 0 | | | | |
| R12 stray file in /app/out | state | -1 | not fired | 0 | `__pycache__` removed step 54 | | | |
| R13 unchecked pilot claim | final answer | -3 | not fired | 0 | | | | |
| R14 false pass claim | final answer | -3 | not fired | 0 | | | | |
| R15 answer differs from own output | final answer | -3 | not fired | 0 | | | | |
| R17 repeats failing command | trajectory | -1 | not fired | 0 | | | | |
| R18 cites unread source | final answer | -1 | not fired | 0 | | | | |
| | **total** | 39 | **16** | **23** | | | M1 = 22, M2 = 1 | |

Patch proof (judge side): the agent's own what-if commands (steps 47, 48, 56, 58, 59) re-run on host Python against the band-patched script print 5 393 301, 5, 331 499 999 995, 3, 15 and 43, and still 4 for R3 (`regrade.txt`, what-if section). The agent's method was right; only the base it ran on was wrong.

## Summary by class (combined points of 100)

| class | items | raw points | combined points |
|---|---|---|---|
| AMBIGUITY (M1 root, first billing) | 1 test | 5 test | 1.95 |
| AMPLIFICATION (M1 repeats) | 14 tests + 6 criteria | 70 test + 22 judge | 27.34 + 28.21 = 55.55 |
| CONDUCT (M2) | R10 | 1 judge | 1.28 |
| GENUINE / HIDDEN RULE / JUDGE ERROR / ARTEFACT | none | 0 | 0 |
| **total lost** | | 75 test + 23 judge | **58.78** (100 - 41.22) |
