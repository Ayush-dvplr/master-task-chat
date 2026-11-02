# A2_SCORE - depot-charge-plan, paid attempt 2 (claude-opus-5 run_1), offline score (board af2d811)
Bundle tree 205cb85281c7 (= Tasks_INPUT). Program: OUT/a2_out/derive_report.py (sha256 in a2_out_sha256.txt). Reference: BUNDLE/solution/solve.py.
Local python3 runs; scratch and logs: `_runs/20261102/depot-charge-plan/a2score-20261102T0028/{scratch,logs}`.

## Result
**No documented case found where a2 is WRONG: 0 determinate DIFFs in 2312 folders** (plus 28 smoke folders).
The only DIFFs (20/20 on the blank-line probe) are a **reference bug**: a2 is right there. Nothing can be planted as a lever.

| block | generator | folders | MATCH | DIFF | max ref s / a2 s |
|---|---|---|---|---|---|
| 1c | shipped data | 1 | 9/9 docs | 0 | - |
| 3a | shipped-like (gen_core shipped) | 300 | 300 | 0 | 8.3 / 3.5 |
| 3a | hidden | 300 | 300 | 0 | 10.2 / 6.8 |
| 3a | hidden_reorder (rows shuffled, public weight 6) | 300 | 300 | 0 | 9.1 / 4.5 |
| 3a | uplift (gen_core.uplift = shipped test generator, rule 11) | 300 | 300 | 0 | - |
| 3a | large | 300 | 300 | 0 | 78.2 / 34.0 (6 jobs in parallel) |
| 3b | 13 targeted mutators x 60 (below) | 780 | 780 | 0 | 57.8 / - |
| 3b | blank_lines (reference-bug probe) | 20 | 0 | 20 | 9.0 / - |
| 3b | offgrid_first (first_slot 12:01-12:14) | 12 | 12 | 0 | 4.6 / 2.2 |

Each targeted mutator covers a branch a2's own fuzz never varied (A2_RULES.md), and every one stays inside what charging_rules.md (CR) allows: roster_depot (CR:14), offgrid arrive/depart and published slot (CR:14, :28), bad_window_edges (CR:13), overlapping / off-grid / over-count outages (CR:22), multiple derates incl. above base (CR:23), extras on/off plan and on other dates (CR:16), duplicate and above-rate published rows (CR:28-29), tariff version ending on the plan date (CR:27), flat and 0 prices with other weights, i.e. heavy ties (CR:33), blank and unknown contracts (CR:17), soc above need and 1-3 slot windows (CR:16, :40), fewer slots and a later first_slot (CR:7), and combo (9 mutators stacked, every 5th on large). Logs: logs/fuzz_<branch>.jsonl, logs/targeted_*.jsonl.

## DIFF list
| # | case | doc line | who is right | lever? |
|---|---|---|---|---|
| D1 | blank lines inside roster.csv / published_plan.csv: data_quality `line` from the reference is n lower than the physical line after n blank lines (e.g. ref 2504 vs a2 2505; physical line 2505 is the bad_window row). Reproducer: scratch/keep/blank_lines_1 (data/, ref/, a2/) | CR:44 (line numbers counted with the header as line 1) | **a2** (physical line). The reference `rows()` uses csv.DictReader, which skips blank lines, together with enumerate(start=2) (solve.py:51-60) | No. This is a reference bug. The docs never say a CSV may hold blank lines, and shipped data and tests have none, so it is latent. Fix it only if a later harden ever plants blank lines. |

Checked and not a lever (both sides agree, or the docs fix nothing):
- first_slot off the quarter-hour: the reference's day_index floors relative to first_slot (solve.py:108-111), which rotates the bands by one slot, but the fitted k absorbs that rotation. 12/12 MATCH, and no report shows k.
- slot_minutes other than 15: the docs rule it out. "k from 0 to 95 ... fit exactly one k" (CR:27) is unique only with 96 slots per day.
- Docs that leave the answer open (not determinate, so no lever under R2): notice lines off the stated format (a2's regex is lenient, the reference's strict), overlapping tariff versions (a2 takes the first, the reference errors), a settlement span that is not a whole number of slots, negative prices.

## Why a2 is right everywhere
a2 is a lexicographic min-cost flow with the same weight scheme and the same (slot, bus_id) lock-and-push tie-break as the reference. Every branch in the A2_RULES.md trace (CR rules 1-22 and the notice format) uses the same reading as solve.py. The only behaviour its own tiny fuzz never compared (data_quality, unmet_reason, changed, region/segment, feeder_peak) also matches on all 2292 non-blank folders.

## Candidate levers
None. No L2 instance exists, because a2 mishandles no documented branch. No LC1 family exists either: a2 has no shipped-fitted literals (TIMELINE.md), k is fitted per depot, and every count is read from the data.

## Prediction
- a2 tests on any held-out set drawn from the current docs: **100** (557/557 now; 2312/2312 offline).
- Judge (unchanged rubric, 44 positive): low 6/44 = 13.6, mid 10/44 = 22.7 (observed), high 16/44 = 36.4 (if it also scores R3/R4 or avoids the R12/R14 over-claim).
- Predicted final = 0.5 x 100 + 0.5 x 22.7 = **61.4** (range 56.8-68.2). It cannot go under 50 while tests are 100, and the R5(a) bar is <= 35, so no route-1 harden can reach the bar.

## Recommendation: **off_route1** (one new documented rule), with park as the fallback on Ayush's word
| option | cost (one line) |
|---|---|
| route1_harden | Not possible. There is no WRONG case to plant: 0 of 2312 folders, every documented branch exercised. |
| off_route1 (one new documented rule) | A docs and reference change, then regenerated tests, full QC and one paid run (~$6 plus about a day). It works only if a careful brute-force agent misreads the rule the way a1 misread "replaced by". a2 read every rule correctly, so the odds are modest. |
| park | Zero cost. R1 says only Ayush parks, so this is his call. |

## Lessons for the master
- a winning paid program can be scored offline in about 70 min of local fuzz; once 0 determinate DIFFs show up across all generators plus targeted mutators, stop route 1 | template_change: add "0 DIFF in >=2000 folders incl. targeted branches -> off_route1/park decision" exit to the a2-score prompt
- the reference has a latent blank-line line-number bug (DictReader) | template_change: QC kit check that the reference's data_quality line equals the physical line on a blank-line probe
- the judge loses come from process probes (R1-R8, R18, R19), not from the program | template_change: none (the judge already measures it)
