# A_daaca581 (Aditya Patel, Data Processing) — Step 1 genuineness

Recorded: final 50.23 / tests 17.12 / rubric 83.33. Second version of the 3def42a3 task (see C_daaca581_DIFF.md).

## Verdict: GENUINE

## Version-skew check (done first)
- ctrf has 36 tests; every name is present in `tests/test_output.py` of the folder (python check, no MISSING printed). The 36th test `feeder_balance_shape` (weight 1) exists only in this version, so the run used this tree, not 3def42a3's.
- Positive weight 146; passed t04 5 + feeder_balance_shape 1 + t10 5 + dc01 3 + dc02 5 + dc06 3 + dc07 3 = 25 → 25/146 = 17.12 ✓ (matches recorded tests score). No negative fired (hardcoded −5, filename −5, io_outside −5, nondeterministic −3 all `failed` = not fired; inverted polarity, test_output.py negatives comment "True means the cheat happened").

## Crash / gate / path checks
- `result.json:121` `"exception_info": null`.
- `verifier/test-stdout.txt`: grep for `Permission denied|Traceback|Error` returned nothing; stdout ends `reward: 0.5023`.
- ctrf failed tests carry no messages (no assertion text to read).
- Agent wrote all nine deliverables + `transform.py` (2539 lines) to `/app/out` (artifacts listing). Ran on hidden tier: tests t04, t10, dc01, dc02, dc06, dc07 pass and `_hard()` requires the hidden run r1 to match as well (test_output.py `_hard`), so the transform ran on the hidden corpus inside the 1500 s cap. No gate zeroed the channel.
- Program staging: verifier copies transform.py to a root-owned 0644 dir before running as nobody (same `_stage_program` as 3def42a3) → no permission artefact possible.

## Failed tests: value, not gate
Evidence that failures are wrong VALUES on the shipped tier itself: the two runs (3def42a3 run and this run) worked on byte-identical `/app/data` (cmp of all 100 files: no difference). Their `/app/out` artefacts differ:
- `read_resolution.csv`: 8 diff hunks, e.g. `KV0213982,2025-11-01,CORRECTION,566841.239` (3def run) vs `KV0213982,2025-11-02,INVALIDATED,566852.132` (this run); 7 extra MISSING rows in this run.
- `control_report.json`: `data_rows` 5194 vs 5195, 5191 vs 5193, 5192 vs 5194, 5193 vs 5194 on four files. t09 owns the whole control report as its residual share (TRUTH.md:381); the 3def run passed t09, so this run's counts are wrong on the visible tier → t09 failure is genuine.
- `feeder_balance.json` 8 differing lines; `meter_summary.csv` 14 rows; `settlement_summary.json` billed_import_wh 55173529026 vs 55173389475, ufe_wh 939923667 vs 940063218.
- `daytype_calendar.csv`, `interval_injection.csv`, `lighting_deemed.csv` identical between runs (t10, dc02, t04 pass in both).
Per-row expected values cannot be computed without running the generator (forbidden), so which run is right on each differing row is INFERRED from pass/fail only.

Hidden-only fixtures added in this version (`_tiebreak_fixtures`, `_ufe_tie_fixture`) plant traps in families T7 (corrections, tariff errata → t07), T12 (accuracy test, UFE tie → t12) (test_output.py:1147, 1530, 1621, FAMILY_TEST :3265-3271). t07 and t12 failed in both runs, so the fixtures cannot account for the 31-point gap; they are all stated tie-breaks (contract s4, s8; manual s3, s6 per TRUTH.md:381) → genuine if they cost anything.

## Judge
- 11 criteria, identical `tests/judge.toml` to 3def42a3. Only R5 failed (relocated/altered-copy comparison, process step, important, 3 pts) → 15/18 = 83.33 ✓.
- Real miss: every transform run in the trajectory used `/app/data` as DATA_DIR (steps 125, 130, 133, 137, 140, 200, 212, 222, 227, 239, 246, 252); different output dirs only. Not a judge artefact.

## Genuine points lost
- Tests: 121/146 positive (all value failures; no gate). 
- Judge: 3/18 (R5).
