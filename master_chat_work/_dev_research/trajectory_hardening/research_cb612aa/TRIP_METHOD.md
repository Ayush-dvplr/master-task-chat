# Trip-point method (cb612aa)

Script: `trip_points.py` in this folder, read-only. Run it with `perl -e 'alarm 300; exec @ARGV' python3 trip_points.py "$OUT"`. Outputs: `TRIP_POINTS.csv` (298 rows; columns slug, run, cls, layer, item, weight, evidence, note) and `_trip_summary.json`.

## 1. Inputs per run
`report.json` (names and weights), `verifier/reward-details.json` (true pass/fail values), `verifier/test-stdout.txt` (assertion lines), `agent/trajectory.json` (steps and the final message). For kvec, which has no reward-details, the script falls back to `report.json` `passed`.

## 2. Classes and how the script assigns them
| Class | Rule | Precision when checked by hand |
|---|---|---|
| WRONG_AND_GRADED | a positive test with value < 1 (evidence `test-stdout.txt:<line>`), a judge positive on `final_answer`/`state_change` that failed, or any negative with value > 0 | exact, because it comes from the grader itself |
| SKIPPED_BEHAVIOUR | a judge positive with `evaluation_target=trajectory` that failed | exact, as far as the judge is right |
| RIGHT_EASY | a positive test that passed with weight <= 1 or a format/existence name (`shipped/sample/exists/cli/schema/format/parse/keys/json/zip/layout`) | name-based heuristic |
| STATED_WRONG_FACT | the final message (`finish` tool `arguments.message`) claims success (`byte-identical`, `all checks pass`, `reproduce ... exactly`) while failed positive tests > 0 | 8 hits. 7 are genuinely false claims. The match-replay one is overstated coverage (J3c) rather than a false fact |
| WRONG_NOT_GRADED | keyword candidates: a caveat in the final message (`assum/heuristic/ignored/skipped/could not`), or the last self-check output containing `Traceback/FAIL/mismatch/WARN` | **about 0%**. All 12 candidates I reviewed were false positives or unconfirmed (§3) |

## 3. WRONG_NOT_GRADED: what the trajectory gives you, and what you need instead
I checked these candidates by hand (top 5 per task does not apply, because no task has more than 1 candidate):
- vendor step 48 ("'true' string ignored"): this is the stated rule (`environment/data/decoder_appendix.md:106-107`) and it is already graded (`tests/test_output.py:390-415`, fixture l.782). Not a gap.
- district-heat step 56 ("[export] deliberately ignored"): matches `schema.md:30` ("carries no rule"), graded at `test_output.py:716`. Not a gap.
- 7ef8d80a step 50 (tokens_per_step "ignoring packing"): describes the defect the agent found, not its own error. Not a gap.
- cold-chain step 60 ("old core.best_network was a heuristic"): describes the old code. Not a gap.
- dispatch step 76 ('mismatch'): the word appears in printed source code, not in an output. Not a gap.
- numeric step 20 ("could not run the module as a different user; verified from permission bits"): an unverified claim. UNKNOWN. Settling check: run the agent's artifact as uid 1001 in a scratch copy.
- kvec step 254 ("2025-11-01 corrections ignored in favour of the October close ... export attribution by a day"): an admitted deviation. UNKNOWN. Settling check: diff kvec `artifacts/` settlement rows against `solution/solve.py` output for that meter.
- cohort-retention, data-product, schema, sentinel, tariff: the caveat text is a restatement of rules ("was the first file row covering D", "fell back to 'absent'", "pre-cutover deltas stored in seconds"). Each is UNKNOWN until diffed against the oracle.

**A working WRONG_NOT_GRADED detector** (proposal):
1. Re-run the oracle `solution/solve.py` on the same inputs and diff every artifact field-by-field against `artifacts/app/out/*`.
2. Take each differing field and look up the tests that read it, using a rule-to-test map: grep `tests/test_output.py` for the key name.
3. A field that differs but has no test reading it is WRONG_NOT_GRADED.
4. Step 1 needs Docker or a python run of solve.py, which this read-only round did not allow. **Not run.**

## 4. Per-task counts (latest run; W&G / WNG-candidate / EASY / SKIP / SWF)
| task | tests (failed+) | judge n | final | W&G | WNG? | EASY | SKIP | SWF |
|---|---|---|---|---|---|---|---|---|
| 7ef8d80a | 47 (1) | 11 | 99.1 | 1 | 1 | 6 | 0 | 1 |
| caldermoor | 57 (3) | 14 | 51.45 | 6 | 0 | 5 | 7 | 1 |
| cohort-retention | 25 (0) | 8 | 100 | 0 | 1 | 5 | 0 | 0 |
| cohort-uplift | 30 (0) | 9 | 100 | 0 | 0 | 11 | 0 | 0 |
| cold-chain | 26 (0) | 10 | 85.0 | 0 | 1 | 7 | 2 | 0 |
| data-product | 35 (0) | 15 | 100 | 0 | 1 | 7 | 0 | 0 |
| dispatch | 35 (17) | 11 | 14.7 | 19 | 1 | 4 | 3 | 1 |
| district-heat | 50 (0) | 12 | 68.52 | 1 | 1 | 4 | 4 | 0 |
| emberforge | 24 (1) | 8 | 59.91 | 1 | 0 | 5 | 3 | 1 |
| match-replay | 46 (11) | 11 | 43.42 | 12 | 0 | 7 | 5 | 1 |
| metered-usage | 64 (0) | 16 | 82.35 | 3 | 0 | 1 | 1 | 0 |
| numeric-reduction | 31 (1) | 21 | 87.41 | 2 | 1 | 12 | 3 | 1 |
| pcggc | 22 (0) | 11 | 100 | 0 | 0 | 3 | 0 | 0 |
| schema-migration | 63 (0) | 9 | 46.16 | 2 | 1 | 24 | 2 | 0 |
| season-ladder | 37 (11) | 16 | 82.09 | 11 | 0 | 5 | 0 | 0 |
| sensor-network | 30 (0) | 11 | 87.5 | 0 | 0 | 5 | 2 | 0 |
| sentinel | 39 (6) | 14 | 50.1 | 7 | 1 | 7 | 8 | 1 |
| specdec | 37 (0) | 12 | 100 | 0 | 0 | 5 | 0 | 0 |
| tariff | 39 (0) | 14 | 59.09 | 0 | 1 | 6 | 9 | 0 |
| vendor-archive | 32 (0) | 8 | 71.88 | 0 | 1 | 1 | 3 | 0 |
| kvec (Output_RFP only) | 36 (25) | 11 | 50.23 | 29 | 0 | 1 | 1 | 1 |

What the counts show:
- 10 of 21 latest runs fail **zero** positive tests. For those, the trajectory has no test trip to mine. Only SKIPPED_BEHAVIOUR (judge) rows and RIGHT_EASY rows exist. This is the tests-100 problem (QC_RULINGS.md:145 Q5).
- On tasks where judge points are lost, SKIPPED_BEHAVIOUR keeps showing the same acts: never ran the shipped tool before the first edit, never recomputed independently, never re-ran on a changed copy. These are exactly the P-5 probe acts in LEVER_RULES_v3.md:151 J2. They are already graded, so no new criterion is needed for them.
- STATED_WRONG_FACT appears in 8 of 21 runs, and in none of them did a negative fire. This is the largest **ungraded** behaviour the trajectories show (J3a/J3c, LEVER_RULES_v3.md:171-173).
