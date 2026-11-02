# TRUTH.md - 3f39299a-20c7-5792-a6e6-b2a616a3ec30

## Defect

The cooperative's 2025-26 road-salt season exists only as a flat extract. The shipped documents state the rules that decide its figures, with four exceptions: each carrier's weighbridge settings, the periods in which those settings were in force, the whole-unit hand-out procedure and the review trigger. The documents never say where any of these comes from. They say that each calibration batch is dated with the instant it was weighed, that a batch's credited total is the sum of its loads' credited quantities, and that a load is credited with its carrier's settings. They also say that the divisor procedure and the review test are one member of a stated class, applied the same way in every season. The previous season's journal is shipped as a record file. The agent must build `/app/out/derive_report.py`. It is a reusable stdlib program that works out the settings periods from whatever extract it is given, applies the procedure and test that the journal admits, replays the season week by week and writes nine byte-exact reports. The agent then reports eight figures.

1. (focal) Weighbridge settings and their periods. Each extract's calibrated carriers have one of 90 settings each. The dated calibration batches are shuffled, their ids do not follow weighing order, and their stamps use four offsets. The program must find the periods of fixed settings that the dated batches admit, and credit each load with the settings in force at its arrival. On the shipped extract, 16 batches settle exactly one assignment for 11 carriers (one of them idle), and no change is visible: one assignment fits every batch, with no residual and no second fit.
2. (focal, degenerate on the shipped extract) The settings change. Every hidden extract carries a mid-season change with its own instant, its own two busy carriers and its own new settings. That change credits at least 3 post-change loads per changed carrier, and `credited_kg` diverges there. A program that assumes one assignment for the whole season, or that reads the near-duplicate file, passes the shipped extract and fails every hidden one.
3. (focal) Whole-unit procedure. The stated class has four divisor forms: 19,403 descriptions, which are 17,192 distinct procedures up to rescaling. Only `d(0)=1.25, d(n)=2n+0.5` fits the journal. The journal records only the size of each final review list (`reviewed_count`), so the divisor and the review test have to be searched jointly.
4. (focal) Review trigger. Of 14 stated tests, only `B_LT` fits jointly: a customer joins when its grant is strictly below `review_floor` times its fair share before any review bonus. Without `reviewed_count`, `B_LE` would also fit.
5. (focal) Composition across 21 weeks: identity resolution, amendments, void marks, re-keyed loads, the deficit spine, review rounds and lot lapse.
6. (trap) Decoys and data traps, none of them flagged by any document (see Traps).
7. (drift) A least-squares fit rounded to the nearest setting, or one assignment forced onto all the batches, looks like the right tool for the calibration. Neither works: the nearest factors fit no batch exactly, and on a hidden extract no single assignment fits every batch.

The reference language is Python 3 with the standard library only. Two grading channels score the run. Channel A is the `tests/test_output.py` rewardkit grader. Channel B is the judge in `tests/judge.toml`, which covers the eight what-ifs and code quality.

Out of bounds: embedding shipped answers (`negative_hardcoded_sample_answers`), reading grading or solution files (`negative_reads_outside_its_directories`), third-party or network imports (`negative_third_party_or_network_import`), output that depends on location (`negative_location_dependent_output`), reusing the shipped parameters on another extract (`negative_reuses_shipped_parameters`), forged zero residuals (`negative_forged_reconciliation`), and editing the extract or writing outside OUT_DIR (`negative_touches_extract_or_writes_outside`).

## Hint policy

instruction.md and the documents in `environment/data` carry no worked or illustrative examples and no example output. They never say which evidence fixes which unknown, that anything is recoverable or unique, which files are current or decoys, or that settings differ between extracts. They state every rule the computation needs, and the exact report layout in words.

## Degeneracy of the shipped extract

Each of these plausible wrong readings writes reports byte-identical to the oracle's on the shipped extract. Each was run against the 22 hidden extracts as built by the tests, with the oracle patched once per reading.

| Wrong reading | Shipped reports | Hidden extracts it fails |
|---|---|---|
| One settings assignment for the whole season, taken from the earliest batches | same on shipped | differs on 22 of 22 |
| Settings taken from `carrier_calibration_v2.json` | same on shipped | differs on 22 of 22 |
| `credited_kg` column used as the load's credit | same on shipped | differs on 22 of 22 |
| Every load credited under the latest-weighed batches' settings | same on shipped | differs on 22 of 22 |

Readings of documented rules are not degenerate on the shipped extract, so they are not listed as levers. These are: quantities read as floats (differs on shipped, and on 1 hidden extract), a repeated daylight-saving wall time read at its first occurrence (differs on shipped, 19 hidden), an instant on a cutoff put in the week that opens there (differs on shipped, 22 hidden), same-instant identity events in reverse `event_id` order (differs on shipped, 18 hidden), and stamps compared without their offsets (differs on shipped, 22 hidden). The four degenerate readings all concern the undocumented settings change, the one behaviour that only the hidden extracts show.

## Traps

- Stale "authoritative" note (`calibration_notes_2023.md`): it claims that settings never change during a season, that every carrier weighs `metric_tonne`/3/`half_up`, that the moisture deduction comes off the week's total, and that later batches can be skipped. The batches contradict all of this.
- Near-duplicate file (`carrier_calibration_v2.json`, `"status": "final"`): the batches without their dates. On the shipped extract it gives the correct reports. On every hidden extract it holds only the pre-change batches and misses the change.
- `receipts.csv` column `credited_kg`, which is undocumented: on the shipped extract it equals the true credit. On every hidden extract it is the load's quantity times its unit's kg, rounded down, before the moisture deduction.
- Stale totals (`season_totals_expected.json`, `"status": "checked"`): receipts 41,519,002, delivered 36,988,400, closing 6,742,695 and true-up 1,619,500 kg. None of these equals a graded or judged figure (the true values are 41,412,378, 36,903,400, 6,721,071 and 1,868,800). The true-up figure is the season computed with the note's settings and its week-total moisture rule. Its `opening_kg`, 2,212,093, is the plain sum of the depots' opening stock.
- Exponent-form quantities (`1.46745E2` style) on 10 rows of Coldspring Freight and Lakeshore Bulk, which are exact under decimal reading. There is a UTF-8 byte order mark on `receipts.csv` only. Calibration stamps use `Z`, `-05:00`, `-06:00` and `+01:00`.
- Join keys: receipt carriers keyed with spaces or in other case; `VOID-DUP` board lines with spaces around the purchase order number; CRM rows at one instant in two offsets; re-keyed load RC-8064 moving depot and week; order SO-101542 placed exactly at a service-area move.

## Known hard edges

- The settings change is undocumented behaviour that only the hidden extracts show. The shipped extract shows no change at all: one assignment fits all 16 batches. instruction.md and the documents never say that settings may change or must be found over time. They say only that a batch total is the sum of its loads' credits, and that a load is credited with its carrier's settings. Every graded hidden extract carries a change, decidable from that extract's dated batches.
- No document says where the procedures come from. The shipped extract never shows a change. Only the hidden extracts' dated batches show one, and only the journal admits one procedure and one test.
- The journal does not record who was on the review list, only how many.
- Every hidden extract carries its own change, so a program that splits at a hard-coded batch or instant, or that hard-codes the shipped carriers, fails there.

## Load-bearing work

Graded artifacts: `/app/out/derive_report.py` and the nine reports `summary.json`, `policy_audit.json`, `data_quality.json`, `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`, `segment_commercial.json`, `segment_public.json`.

- `derive_report.py DATA_DIR OUT_DIR` runs in at most 240 s, is deterministic across paths and working directories, and leaves other files in OUT_DIR alone. It works out the settings periods from that extract's calibration and credits every load with the settings in force at its arrival. The divisor procedure and review test are the joint choice the journal admits; every hidden extract carries the shipped journal.
- `policy_audit.json` reports, per calibrated carrier, its settings at the close of the season (the settings in force at the last closing cutoff).
- The final message states the eight figures of `instruction.md`.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app`. Channel A registers 35 checks: 28 positives with a total weight of 116, and 7 negatives with a total of -25.

- Shipped and behaviour checks (weight 1 each, 6 in all, 5.2% of the positive weight): the four program-behaviour checks, `shipped_carrier_settings` and `shipped_all_reports` (every shipped report except the carrier settings, which `shipped_carrier_settings` alone grades). A program that gets every shipped figure right but no hidden extract scores 6/116 = 0.052.
- Hidden extracts (weight 5 each, 22 in all, 110 of 116, 94.8%): one all-or-nothing check per extract. All nine reports must match byte for byte. Each extract is built at grade time from the embedded shipped data and has its own carriers, calibration, settings and mid-season change (`_reweigh`, then `_finish`). Its periods are certified unique at build time. The four freshly drawn extracts carry every documented `contracts.csv` column, `weight_class` included, drawn from a generator of its own so that no other value changes.

Channel B (`tests/judge.toml`) has 22 criteria, with a positive total of 58 and a negative total of -24:

- R1 to R8 are the what-ifs, weight 5 each:
  - R1: public delivered 16,600,500 kg with JR-0068 recorded `highest_weight` (the journal then admits `d(0)=1.24, d(n)=2n+0.4` with `B_LT`).
  - R2, R5 and R8 state a weighbridge change that the shipped extract never shows: from 2026-01-27T00:49:00Z on, Coldspring Freight weighs `long_ton`/9/`down` and Lakeshore Bulk `metric_tonne`/5/`down`. No load arrives within two hours of that instant.
  - R2: closing stock 6,694,704 kg under that change (the shipped closing stock is 6,721,071).
  - R3: the 18 customers whose true-up changes under `oldest_open_lot`.
  - R4: 915 reviewed entries at round limit 3.
  - R5: true-up 1,873,800 kg under that change (the shipped true-up is 1,868,800).
  - R6: lapsed 8,417,700 kg with Redfern loads 168 h later.
  - R7: true-up 1,905,800 kg with IE-015 moved and thresholds +0.05.
  - R8: 31 in-season loads credited with different settings under that change.
- R9 (weight 3) is code quality: the delivered program handles errors explicitly, with no bare except, no dead or duplicated blocks and no debug residue (the oracle has no except clause and prints only its usage line to standard error).
- R10 to R17 are negatives. R16 counts only writes the agent makes with its own commands, so a program that edits its DATA_DIR is priced once, by the test negative.
- R18 to R22 are conduct criteria, weight 3 each, none of them reading a fact a test reads:
  - R18: before finishing, the agent runs the program on an extract whose contents differ from the shipped one (a byte copy at another path does not count).
  - R19: the agent checks, by any means such as tracing a run or reading every path the source opens, that the files the program opens lie under DATA_DIR, OUT_DIR or the program's directory.
  - R20: the program relies on a fitted set of batches only when exactly one weighbridge assignment reproduces it (the oracle's `recover_weighbridge` collects every fit, raises when the whole season admits two or more, and raises unless the batches before and after the split each admit exactly one). The recorded run's search returns its first answer.
  - R21: the program settles the divisor procedure and the review test uniquely, either by applying one fixed procedure and test from the class the documents state (the oracle hard-codes the one pair the previous-season journal settles) or by a journal fit that keeps a candidate only when it is the only one. The recorded run returns the first surviving combination.
  - R22: the program has an explicit path for an empty fit that stops or widens to every stated setting (the oracle keeps every stated factor open for a carrier when no run of batches gives a regular system to bound it). The recorded run substitutes a preset 950 estimate.

`tests/reward.toml` weights the channels 0.5/116 and 0.5/58, so the tests and the judge each carry half of the reward.

## Root cause

**Uniqueness of the settings periods.** On the shipped extract, an exhaustive search over the 16 batches finds exactly 1 assignment. On each of the 22 hidden extracts, built and certified when the tests build them, the search over the 32 batches in weighing order finds the following:

- 0 assignments fit all 32 batches.
- Exactly 1 assignment fits the first 16.
- Exactly 1 assignment fits the last 16.
- The old settings miss every later batch, and the new settings miss every earlier batch.

A prefix longer than 16 is therefore inconsistent, and so is a suffix longer than 16, so the split is unique. No load arrives within two hours of the change. The oracle first tries one assignment for every batch, then finds the longest reproducible prefix by bisection and certifies the split there.

**Unique recovery of the procedure.** Every one of the 17,192 classes x 14 tests = 240,688 pairs is replayed in full against all 150 entries. Exactly one pair fits: `d(0)=1.25, d(n)=2n+0.5` with `B_LT`.

## Solution shape

The reference program is `solution/solve.py`, which `solve.sh` copies to `/app/out/derive_report.py` and runs on `/app/data`.

1. Read the extract with BOM-tolerant CSV and exact decimals. Trim and case-fold references and receipt carriers.
2. Sort the calibration batches by `weighed_at`. Take one assignment when exactly one fits every batch; otherwise split them after the longest prefix some assignment reproduces, found by bisection, where one assignment settles each side and the certificates hold. Factors are bounded by exact rational solves of runs of consecutive batches, settled carriers are fixed before any branching, and roundings are matched by meeting in the middle. Whole units go out from a priority heap after an exact head start of every unit priced above a level. Credit each load with the settings in force at its arrival, and report the settings in force at the last closing cutoff.
3. Apply the journal-admitted procedure as fixed constants: `d(0)=1.25`, `d(n)=2n+0.5` and `B_LT`.
4. Screen orders, build lots, replay the 21 weeks, and write the nine reports canonically.

## Ordered plan

1. Read every document and record layout.
2. Solve the calibration, and handle the case where no single assignment fits by ordering the batches by instant and finding the split. Rerun with the stated weighbridge change (R2, R5, R8).
3. Recover the procedures jointly from the journal. Rerun with JR-0068 changed (R1).
4. Implement the season and the reports in clean code with errors raised explicitly, then verify the conservation identities, test the program on an edited copy of the extract and check the files it opens (R9, R18, R19).
5. Rerun for the tie-break, round-limit, Redfern and IE-015 changes (R3, R4, R6, R7).

## Pitfalls

- Trusting `calibration_notes_2023.md`, `carrier_calibration_v2.json`, the `credited_kg` column or `season_totals_expected.json`. All four look harmless or right on the shipped extract.
- Assuming one assignment for the whole season, splitting in file or batch-id order, or comparing `weighed_at` stamps as text.
- Filtering divisor classes against a guessed review list (`B_LE` survives without `reviewed_count`).
- Reading quantities as floats, or reading `receipts.csv` without stripping its byte order mark.

## Provenance

```yaml
uuid: 3f39299a-20c7-5792-a6e6-b2a616a3ec30
instance_id: 3f39299a-20c7-5792-a6e6-b2a616a3ec30
task_name: terminal-bench/3f39299a-20c7-5792-a6e6-b2a616a3ec30
fix_patch_sha256: 14ce21714759a2e7d6fcfe705a88934383523ab2d23051e5d9dec0f1d60468b5
solve_py_sha256: 84c3723b3969c37f08895206badb507852fa166e7ea31eeae16348a010961f42
language: python
```
