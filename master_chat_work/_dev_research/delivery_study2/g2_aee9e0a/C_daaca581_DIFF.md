# C_daaca581_DIFF — daaca581 (Aditya Patel) vs 3def42a3 (Harshank Kanungo)

Scores: daaca581 50.23 / 17.12 / 83.33 vs 3def42a3 60.63 / 37.93 / 83.33. Verdict both GENUINE (A_daaca581.md, A_3def42a3.md).

## What is identical
- `instruction.md`, `tests/judge.toml`, `tests/test.sh`, `tests/Dockerfile`: `diff` empty.
- `environment/data`: same 100 names, every file byte-identical (cmp loop, no DIFF).
- `task.toml`: only name and author differ. `environment/Dockerfile`: only PyYAML 6.0.3 (3def) vs 6.0.2 (daaca).
- Judge: same 11 criteria; both runs fail only R5 (run on a relocated or altered copy) → 83.33 each.

## What differs
| area | 3def42a3 | daaca581 |
|---|---|---|
| tests/test_output.py | 352 KB, 35 tests, positive 145 | 360.7 KB, 36 tests, positive 146 (diff 187 lines) |
| hidden tier | regenerated from EVAL_SEED, same trap set as visible | same, plus `_tiebreak_fixtures` and `_ufe_tie_fixture` behind a `hidden=True` flag (visible tier never calls them; TRUTH.md:381) |
| planted hidden fixtures | none | (1) second November FAIL accuracy test → latest date wins; same-date test → higher test id wins (contract s4, family T12 → t12, test_output.py:1530); (2) second VALIDATED correction revision → higher revision wins (manual s3, T7 → t07, :1147); (3) two APPROVED tariff errata same key same issue date → higher erratum number wins (manual s6, T7 → t07, :1621); (4) one SCADA erratum shifted 1..20000 Wh so the UFE largest-remainder cutoff falls between two equal-weight accounts → lower account id wins (contract s8 → t12) |
| extra test | — | `feeder_balance_shape` weight 1, canonical JSON shape of feeder_balance.json on both tiers |
| reward.toml | test_output 1/290 | 1/292 (positive 146 ×2) |
| solution/solve.py | 2259 lines | 1796 lines, rewritten (1993 diff lines) |
| TRUTH.md | — | adds the fixture paragraph and the shape test; claims a misread record now costs four checks (meter-row test, account-row test, feeder-object test t03/t05/dc11, t12) |

Pattern: the second author kept the corpus and instruction and added **hidden-only tie-break fixtures** for stated tie-breaks the shipped data never exercises (the shipped corpus never reaches those branches). This is the 05:21-32 / W5 shape ("separating cases hidden-only") applied to tie-breaks; legal because each tie-break is a stated sentence.

## Why tests 17.12 vs 37.93
Points the 3def run earned that the daaca run did not: t03 5, t09 5, t14 5, t16 5, dc08 3, dc10 5, dc11 3 = 31 raw weight; daaca earned 1 back on the new shape test, so earned weight 55/145 vs 25/146 (gap 30 raw = 20.8 test-score points).
1. **Run variance on the same shipped data (main cause, evidenced).** The two runs' `/app/out` artefacts differ on byte-identical input: `control_report.json` data_rows on four files (e.g. 5194 vs 5195), 8 hunks in `read_resolution.csv` (CORRECTION on 11-01 vs INVALIDATED on 11-02 for several meters, extra MISSING rows), 8 lines of `feeder_balance.json`, 14 `meter_summary.csv` rows, `billed_import_wh` 55173529026 vs 55173389475. t09 owns the entire control report (TRUTH.md:381) and the 3def run passed it, so daaca's t09 loss is a visible-tier misread by this session, not a fixture. Feeder objects are owned by t03/t05/dc11 (TRUTH daaca :381); the differing feeder lines explain t03/dc11 INFERRED.
2. **Hidden-only fixtures: little or no part of the gap.** They land in t07 and t12, which both runs failed anyway (FAMILY_TEST test_output.py:3265-3271). Possible secondary effect of the shifted SCADA erratum on a feeder object (t03/t05/dc11) — INFERRED, untraced.
3. **Denominator** 146 vs 145: negligible (0.1 pt).
4. Agent differences: daaca session created transform.py at step 116 06:19 (~20 min in) vs ~30 min in 3def; 79 vs 75 min; $45.29 vs $48.56. Both self-tested only on `/app/data`.

Take-away: on a 30+-test all-or-nothing-family grid, single-run test scores of the same task swing ~20 points between Opus sessions; one recorded run is a noisy estimate (relevant to our §6 kill rule, which parks on one probe). Hidden-only tie-break fixtures are a cheap, QC-safe hardening step but did not, by themselves, move this score.
