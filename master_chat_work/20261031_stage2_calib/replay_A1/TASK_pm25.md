# PM2.5 Mechanism Card

Task: `98ed74c1-19ac-5ec8-adaf-392a172d4600`. Relative task references resolve under `/Users/mac/Desktop/Terminal Bench/anubis-stage-2/98ed74c1-19ac-5ec8-adaf-392a172d4600/`. Evidence: `evidence/pm25/` beside this report.

## Actual Causes

The authoritative dictionary says the unit's clock offset holds **for every row on the unit's card** (`environment/data/record_dictionary.md:40-44`). Captured `derive_report.py:236-260` accordingly chooses one offset for each whole card, and line 326 subtracts it from every row.

All 20 hidden profiles introduce one/two/return clock steps (`tests/test_output.py:1385,1398-1432`). Hidden grading supplies `truth_offsets(world)` directly to `reference_reports`, whose lines 313-324 choose an offset segment by row index. The generator creates these steps at 621-675. Shipped data has no steps and no echoes (1373). This is a contract/model mismatch, not evidence that the agent misunderstood half-up rounding or pollutant aggregation.

There is ALSO a genuine, separable error on constant-clock units. `clock_offsets` independently maximizes receipt matches per unit (236-260), allowing one unit to claim another unit's echoed packets. The generator deliberately creates two shared-channel echo pairs (689-719); `_check` rejects worlds unless vote counting is fooled (1151-1162), while requiring at least three single-candidate receipts per segment (1163-1174). These anchoring receipts make the true offset discoverable without assuming that more matches means truth. In profile 01, constant unit AQ814 should be +14 but is inferred +7; AQ766 should be -4 but is inferred -10 (`clock_separation.json`, index 1). These errors are independent of the stepped unit AQ525.

The full counterfactual corrects all row-level offsets and derived received counts, leaving every other business rule intact; all 20 cases become exact. The separation experiment corrects ONLY stepped units, leaving original constant-unit inference unchanged: all 20 cases still fail. Thus LATENT-WRONG constant-unit inference is independently sufficient for every +5 loss. `CAUSES.csv` allocates the 100 raw weight there and records the coexisting UNFAIR clock-step cause as twenty zero-additional-weight rows. This is an explicit allocation policy for overlapping causes, not proof that the nonconforming inputs are harmless. See `scripts/pm25_separation.py` and `clock_separation.json`. Truth injection is an isolation experiment, not a compliant solution.

An additional conforming-clock probe rebuilds profiles 01-03 with `steps=()` and otherwise unchanged generator logic. The unmodified captured program still fails all three, with two fooled echo pairs in each (`conforming_echo_probes.json`; `scripts/pm25_conforming.py`). This is a newly constructed diagnostic corpus, not a substitute for the scored replay. It proves the copyable echo mechanism survives removal of the disputed clock model.

## Hidden Inputs

Twenty deterministic generated extracts: `build_world(EVAL_SEED + index, HIDDEN_PROFILES[index])` at `tests/test_output.py:1650-1656`. Profile constructor 1380-1393 adds shuffled card rows, canonical channel-label variants, two echo patterns, half-decimal factors, exact thresholds, calibration-boundary rows, and ties. There is one +5 exact-all-reports criterion per profile.

| Check | Days / Standard Offset | Steps | Additional Targets |
|---|---|---|---|
| 01 | 18 / -300 | one | 5+3 units/channel groups, reassignment, errata |
| 02 | 22 / -300 | two | DST maintenance, aliases, wide numeric site IDs, two reassignments |
| 03 | 16 / -360 | three one-step units | One shared channel, equal-effective calibration tie, authoritative register filename swap |
| 04 | 56 / -300 | return | Autumn transition, policy filename swap, 50th-rank boundary |
| 05 | 20 / +60 | one and return | Eleven shared-channel units, UTC maintenance, errata, wide IDs |
| 06 | 24 / -480 | two | Autumn DST maintenance, shared groups |
| 07 | 20 / -300 | two one-step units | Wide IDs, errata, register swap |
| 08 | 15 / -420 | return | Nine shared-channel units, aliases, reassignment |
| 09 | 18 / -300 | one | Spring DST maintenance, policy swap |
| 10 | 52 / -360 | two and one | 50th-rank boundary, two reassignments |
| 11 | 25 / -300 | three one-step units | Twelve units, three reassignments, wide IDs, errata, aliases |
| 12 | 14 / +60 | return | Two shared groups, reassignments |
| 13 | 21 / -300 | one | Autumn DST, wide IDs, register swap |
| 14 | 28 / -360 | two | Equal-effective calibration tie |
| 15 | 31 / -300 | one and return | Fourteen units; errata, aliases, wide IDs, tie, both authority-name swaps |
| 16 | 20 / -480 | two one-step units | Errata, reassignments |
| 17 | 20 / -300 | return | 2027 spring DST maintenance, aliases |
| 18 | 17 / -300 | two | Dark site, reassignments |
| 19 | 54 / -420 | two one-step units | Both authority-name swaps, 50th-rank boundary |
| 20 | 19 / +60 | return and two | EU zone rules, wide IDs, errata |

Source: `tests/test_output.py:1397-1433`; actual seeded schedules are recorded in each `case_NN.json` at `$.clock_truth`. Distinctive targets are intentional fixture features, not necessarily causes of failure. Profile 01 is particularly revealing: only three data-quality fields differ; all eight other report files are byte-identical. Yet the whole +5 check fails (`case_01.json`).

## Rule Density And Burial

The dictionary spans 142 lines and the monitoring standard 118. At least 17 operational families interact: clock recovery, channel normalization/shared-channel attribution, calibration revision authority, amendment/withdrawal activation, inclusive effective times, asset aliases, deployments, civil maintenance conversion, local-standard hour boundaries, outside-window precedence, multiple exclusion reasons, decimal half-up, hourly/day completeness, partial-day exception validity, ranked daily design values, site status/tie order, and scoped rollups. This is an explicit analyst grouping, not 17 independently weighted tests.

Examples of deep but fair details: readings on an exact hour close the preceding hour (`record_dictionary.md:45-47`); set/amend/withdraw and effective-time rules (109-123); standard time differs from civil maintenance time (139-142); partial days exceeding the standard can qualify (`monitoring_standard.md:17-23`); the rank is ceil(n/50) (32); district scope uses any non-incomplete site while rollups use valid sites (38-42). These branches are legitimate only with conforming input and settled semantics.

## Checks And Lost Weight

Ten shipped-report/stdout checks earn +1 each; 20 hidden-extract checks earn +5 each: 100/110 positive weight. Seven negative tests do not fire. Recorded tests are 10/110 = 9.090909%, exported as 9.09%.

`_hidden_passes` at `tests/test_output.py:1659-1664` requires runtime success and exact bytes for all nine reports. `_cached` at 1613-1620 catches every factory exception and substitutes None, hiding generator/reference failures as failed checks. `_execute` at 1558-1610 suppresses stderr, enforces 60 seconds, and audits the unprivileged staged program. Field diagnostics preserve these comparators while exposing the swallowed information. All original diagnostic cases complete successfully; no exception or timeout explains the recorded losses.

Judge earns 14/58, loses 44 raw weight: seven wrong figures R2-R4 and R6-R9 cost 35; R13 undetermined-offset error and R14 unexplained-journal error cost 6; R17 fires -3 for overstated distinct check sizes. Exact values and reasoning are in `RECORDED_CHECKS.csv`; all ten lost/fired criteria are in `JUDGE_LOSS.csv`. The final claims 55 distinct factor variants and 66 extracts, but step_id 43 prints 19 cached factors and later overlapping scans cannot be added as distinct (`trajectory_readable.txt:2454`, original `steps[42]`; final `steps[48]`).

The changed-journal what-ifs also create partial clock regimes, so clock-model conflict is a plausible explanation for their figure mismatches, but it is **INFERRED** here: each what-if has not received the field-level truth-injection experiment used for hidden tests. Figure differences are not silently treated as seven separately proven calibration bugs.

## Careful Engineer Versus Trap

Following the whole-card rule is the careful engineer's defensible choice; maximizing independent votes instead of enforcing journal attribution is not guaranteed by that rule. Opus ran a separate 34-card synthetic check, compared all nine reports, audited actual opens, and checked paths/determinism (final step_id 49), but did not catch the adversarial echo construction. The fallback on ambiguous/impossible input also explains R13-R14, distinct from the hidden generator violating clock scope. Confusing run counts with distinct input counts is a genuine reporting defect. Printing many nearby factor results is not evidence of that many distinct fixtures.

## QC Fit

Kit root: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

| Gate | Fit | Evidence And Reason |
|---|---|---|
| IN-8 | LIKELY FAIL | `01_Instruction_QC.md:38`: hidden per-row clock schedules contradict dictionary 40-44. Correct outputs are not grounded in the agent-facing temporal contract. |
| IN-17 | PASS | `01_Instruction_QC.md:47`: source-document orientation is allowed. A temporal-granularity requirement would settle an otherwise ungrounded behavior, not reveal a discovery established by the shipped no-step data. |
| AL-1 | LIKELY FAIL | `05_Alignment_Integrity_QC.md:21`: silence in shipped data about clock steps establishes nothing; the actual dictionary affirmatively excludes them. |
| AL-27 | PASS for inspected targets | `05_Alignment_Integrity_QC.md:38`: `_plant` (955), span/maintenance generators, half-factor and fifty-rank plants, and profiles 1397-1433 create threshold, effective-time, revision-authority, and reassignment situations that alter reports. This is trigger evidence, not a full rule-by-rule mutation certification. |
| CL-4 | PASS by explicit-exact-match exception | `Final_checklist.md:491`: instruction line 3 explicitly requires byte-for-byte equality for every report. Thus profile 01's three wrong fields can legitimately zero its +5 under this exception, without making the underlying clock mismatch fair. |

One independently wrong field in one exact hidden extract costs +5/110 = 4.545455 percentage points. A wrong model applied across all extracts costs +100/110 = 90.909091 points. Report copies and aggregate fields multiply visible deltas without multiplying independent root facts.

## Copy Into Another Domain

For telemetry compliance, use 16-20 seeded extracts and roughly 15-17 documented operational families. Keep 10-12 units, shared channels, source revision authority, time-zone conversions, and threshold/rank boundaries. The directly copyable mechanism is two low-receipt/high-receipt echo pairs whose frame lockstep fools per-unit voting while three single-candidate anchor receipts force each true offset. Keep every clock constant if that is the contract. State any allowed temporal changes explicitly. Grade attribution, exclusion decisions, corrected measurements, completeness, and aggregate status in separate slices. Use one independently calculated partial-period probe, one simultaneous exclusion-precedence case, and one provenance/immutability audit. Keep an executed-fixture registry so reported counts are deduplicated, not sums of overlapping searches.
