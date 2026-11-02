# DIAGNOSIS — tariff-engine-audit-repair, harden round 1 (board d62ffe6)

Probe 1 (claude-opus-5, openhands-sdk, build a5f8657): tests 121/121 = 100, judge 15/24 = 62.5, overall 81.25.
PRIMARY cause: **Cause 4, levers weak by design.** The contract names the separating case of every lever, so the agent wrote correct graded logic in about 45 s right after reading it. Gaps: WORK/XREF.md does not exist (ls error), there is no baselines.json for this task in master_chat_work, and BUNDLE is not a git repo (`git rev-parse` fails), so I could not re-check tree d09c7bd1fda2 through git.

## Phase A — was the probe genuine? **GENUINE**

| Check | Evidence |
|---|---|
| Copy vs BUNDLE | `diff -rq .kiro-staged-tasks/tariff-engine-audit-repair BUNDLE` shows only the extra `.kiro-staged-from` file, plus `task.toml`, where the staged copy adds `"host.docker.internal"` to allowed_hosts (lines 25, 32). That is harness staging. |
| result.json | `exception_info: null`, `reward: 0.8125`, trial tariff-engine-audit-repair__nTk8qUP |
| Timings | env 15:36:40-15:36:50Z, agent 15:37:02-15:44:14Z (7 m 12 s, well under limit), verifier 15:44:22-15:45:28Z. No timeout. |
| Verifier errors | verifier/test-stdout.txt is 15 bytes: `reward: 0.8125`. Grep for `Permission denied`, `Errno 13`, `Traceback`, `timeout` and `error` in test-stdout and trial.log: no hits. trial.log has only the benign `Skipping image OS validation`. |
| Crashes | None. Every one of the 31 checks returned a value. No negative check fired. |
| Judge read the response | judge_response.txt cites trajectory steps 25, 26 and 28 (Fraction recompute and edge probes) and gives a reason for each 0 (R4, R5, R6). |
| pass_summary | `jobs/.../trajectory/claude-opus-5/pass_summary.json`: average_combined_score 81.25, test_weights_percentage 100.0, rubric 62.5 |

## The four causes

| # | Cause | Verdict | Evidence |
|---|---|---|---|
| 1 | Run error or wrong copy | NO | See Phase A: same files, no exception, no timeout, no Errno 13 |
| 2 | Harness or rescoring change | NO | reward-details.json weights: test_output 0.004132 = 0.5/121, judge 0.020833 = 0.5/24. These match task design and reward.toml 0.5/0.5. |
| 3 | QC or fix rounds made the task easier | NO | This is the first probe after build a5f8657. No earlier hard baseline exists (no baselines.json), so there are no "changed since baseline" files to list. The only build-round changes are P4, logged in WORK/TODO_build_a5f8657.md. |
| 4 | Levers weak by design | **YES, PRIMARY** | Each separating case is spelled out in `environment/ci/api_contract.md`: L56 plus the enumeration at L77-79; L43-44 Month = billing period; L42 plus L117-119 half-even per line; L121-125 credit base. Trajectory step 4 reads the contract (`cat`); steps 13-17 write all graded logic between 15:39:22 and 15:40:04; the data census comes only afterwards (step 22). |

## Lever table (reward-details.json plus trajectory)

| Check / criterion | Pts | Earned | Lever(s) | Status |
|---|---|---|---|---|
| shipped_exceptions_exact | 5 | 5 | LV-TR-4 | LEAKED (enumeration L77-79) |
| shipped_standing_lines_exact | 5 | 5 | LV-TR-3 | LEAKED (no separation: shipped periods are calendar months) |
| shipped_energy_and_settlement_exact | 5 | 5 | LV-TR-2, COUPLING | LEAKED |
| fresh_exceptions_exact | 5 | 5 | LV-TR-4 | LEAKED |
| fresh_energy_lines_exact | 5 | 5 | LV-TR-2 | LEAKED (L42, L117-119) |
| fresh_standing_lines_exact | 5 | 5 | LV-TR-3 | LEAKED (L43-44) |
| fresh_subtotals_exact | 5 | 5 | LV-TR-2/3 | LEAKED |
| fresh_credits_and_totals_exact | 5 | 5 | COUPLING | LEAKED (L121-125) |
| rescaled_{lines,subtotals,credits_and_totals}_exact | 15 | 15 | TR-2/3, COUPLING | LEAKED |
| relocated_{lines,subtotals,credits_and_totals}_exact | 15 | 15 | TR-2/3, COUPLING, LV-TR-1 | LEAKED |
| rotated_{lines,subtotals,credits_and_totals}_exact | 15 | 15 | TR-2/3/4, COUPLING | LEAKED |
| api_{lines,subtotals,credits_and_totals}_exact | 15 | 15 | TR-2/3, COUPLING, LV-TR-1 | LEAKED |
| archive/visible/corrected/regression (3 each) | 12 | 12 | P-defects, visible asserts A/B | gate, not a lever |
| module_notes / summary / repair_report (1 each) | 3 | 3 | — | gate |
| missing_source_is_named, two_runs_are_identical | 6 | 6 | LV-TR-1 amplifier | LEAKED |
| negative_hardcoded_sample_answers / negative_visible_test_removed | -5 / -3 | 0 / 0 | — | not fired |
| R1-R3 recompute shipped / exceptions / regression | 9 | 9 | — | earned (steps 25-26) |
| R4 own month-crossing input | 3 | 0 | LV-TR-3 | HELD (judge: probes were 1-day 03-05 and 62-day 03-01, none crossed into the next month) |
| R5 own half-cent tie input | 3 | 0 | LV-TR-2 | HELD |
| R6 altered-copy rerun | 3 | 0 | — | HELD |
| R7 code quality, R8 changed functions | 6 | 6 | — | earned |
| R9 / R10 / R11 penalties | -5/-3/-5 | 0 | — | not fired |

## Trajectory autopsy (agent/trajectory.json, 33 steps; no reasoning_content stored)

- **Read order.** Step 3 `find /app`. Step 4 `cat api_contract.md` at 15:37:12. Steps 5-6 all package source. Step 7 test_visible.py. Steps 8-10 manifest, build_config, lint and failing log. Step 11 heads of the data files. Step 12 grep of failing tests at 15:39:03, after a ~90 s thinking gap.
- **When the program was written.** core.py at step 13 and again at step 15, parser.py at step 14, report.py at step 17 (15:40:04). Step 17 is the **last edit to graded logic**: no step after it writes src/tariff.
- **Graded logic changes after writing.** None.
- **Self-tests.**
  - Step 18: visible tests.
  - Steps 19-20: two corrected tests.
  - Step 21: the CLI with a missing input.
  - Step 22: a census of quantity types, run after the rule was already coded. It found int 10502, digit string 142, float 72, bool 56, None 43.
  - Step 24: regression diff.
  - Step 25: independent Fraction recompute of 2000 regression cases, 0 mismatches.
  - Step 26: Fraction recompute of the full corpus.
  - Step 28: edge probes (1-day period, 62-day period, a meter never active, tier boundaries 199/200/201/600/601, credit exactly at commitment).
- **Time per phase.** Reading about 2 m (15:37:08-15:39:03), writing graded logic about 45 s (15:39:22-15:40:04), tests and fixes about 15 s, deliverables and self-verification about 3 m 20 s (15:40:34-15:43:51), finish 15:44:11.

## Cause 4 per lever (rule text, where it was read, how it leaked, fuzz)

Fuzz: 352 new corpora (seed 0x62FFE6), of which 341 are valid and 14 hit the reference crash, so those 14 were compared against the oracle. Log: OUT/fuzz/fuzz_run.log ends ALL_DONE; numbers in OUT/fuzz/summary.json. **Agent program differs on 0/341** (P1 0/159, P2 0/110, P3 0/72). The single-slip variants do differ, which shows the corpora exercise every lever.

| Lever | Rule text and location | Read at step | Written at step | Giveaway | Agent differs | Habit variant differs |
|---|---|---|---|---|---|---|
| LV-TR-4 (H1) | api_contract.md:56 "`quantity`: a JSON integer, 0 or more." and :77-79, which lists every malformed form | 4 | 14 (parser.py:18-30, the docstring copies the list) | Enumeration of the separating values (fails the LV-ENUM precheck at :76-78) | 0% | VA_qty_coerce 97.7% |
| LV-TR-3 (H3) | :43-44 "Month: the account's billing period ... from `start` to `end`" plus :108-110 | 4 | 17 (report.py:70 `month_days=(end-start).days+1`) | The glossary defines the term as the per-line field, so the habit IS the rule | 0% | VA_month_calendar 97.1%, VA_month_30 97.1% |
| LV-TR-2 (H2) | :42 and :117-119 "rounded half to even to 0.01" per line | 4 | 13/15 (core.py:7-9, 37) | The rounding step is stated at its own stage, so no stage is displaced | 0% | VA_half_up 97.1% |
| COUPLING (credit) | :121-125 "computed on the sum ... before rounding of the total ... total is subtotal x (1-credit_rate) rounded" | 4 | 15 (core.py:49-62) | The formula is given verbatim | 0% | VA_credit_rounded 85.6% |
| LV-TR-1 (H5 amplifier) | :3-5 and :132-134 (python -I, cwd, api) | 4 | 17 | Stdlib-only package; relocation is harmless | 0% | — |

## Phase 2 proposals (per lever)

Line numbers below refer to BUNDLE `environment/ci/api_contract.md` unless stated otherwise. Each new rule is stated once, never lists its separating values, and has no worked separating example.

### N1 — H7 allowance re-share. REPLACES the COUPLING credit partial; it becomes the new coupling into subtotal and credit.

**Rule text**
- New column in billing_periods.csv (:62-64): "`allowance`: a decimal with two digits, 0 or more; the money the account may take off its energy lines."
- Definitions (after :42): "Energy share: each energy line of the account takes an equal part of the allowance, but never more than the line's exact value; a part a line cannot take stays unshared."
- A separate sentence placed in Amounts (:117-119): "Allowance that stays unshared is shared again by the same rule among the lines not yet at zero. Each energy line amount is its exact value less its share, rounded half to even to 0.01."
- The text names no pass count and says neither "loop" nor "until".

**Cases**
- Hidden: owned accounts with cascade depth 1, 2 and 3+ (lines smaller than the equal part, as in the prototype), and an allowance larger than all energy.
- Shipped data and regression rows: allowance 0, or no line below the equal part, so one pass is exact.

**Planting and cost**
- Families: fresh energy, subtotals and credits (15), rescaled (15) and api (15) = **45 pts, 37.2% alone**.
- One-fact-wrong (one cascade account) fails the families it sits in. Keep one N1 account per family, so the cost is 15 pts each (12.4%).

**Why the agent program differs.** Prototype case `N1_allowance_reshare` gives agent subtotal 162.00 vs 127.20. The habit (two passes) matches on the 2-pass case but differs on `N1_allowance_three_passes`: 153.00 vs 148.60. This is the caldermoor CM-B shape, the only genuine slip seen (2/314).

### N2 — H3 calendar month. REPLACES LV-TR-3.

**Rule text**
- Rewrite :43-44: "Month: a calendar month, from its first to its last day."
- Rewrite :40: "Active days: the days of a month that lie in the billing period and on which the meter is active."
- Rewrite :108-110: "A meter's standing line amount is the sum, over each month with active days, of `standing_charge` x active days / days in the month, rounded once; its units are all its active days."
- The text does not mention periods that cross a month end.

**Cases**
- Hidden periods cross a month end: 01-20..02-18, 02-15..03-14, 12-10..01-09 (a year change), and spans of 27-62 days touching 2-3 months.
- Shipped periods stay calendar months.

**Planting and cost**
- Families: relocated (15), rotated (15), and fresh standing, subtotals and credits (15) = **45 pts, 37.2% alone**.
- Judge R4 (own month-crossing input) is kept as the conduct criterion for this family.

**Why the agent program differs.** Prototype `N2_period_crosses_month`: agent standing 31.00 (the period length used as the month), new rule 31.93, habit (days of the start month) 30.00. All three disagree.

### N3 — H6 account tier position. REPLACES LV-TR-4 as the counted lever.

**Rule text**
- Add to Definitions beside :45: "Account position: the count of accepted units of the account before a unit, taken meter by meter in `accounts.csv` order and each meter's reads in file order."
- Rewrite :100-106: "A unit is rated at the tier its account position reaches. Each meter's energy lines group its units by tier."
- Period quantity (:45) stays the per-meter field, so the per-line field and the wider counter are both present.

**Cases**
- Hidden: accounts with 2-4 meters whose combined units cross a tier boundary exactly at a meter boundary, and in the middle of a meter.
- Shipped and regression data: the total per account stays at or under the first `up_to` (or one meter per account), so the shipped data cannot reveal the rule.

**Planting and cost**
- Families: rotated (15), api (15), and fresh energy, subtotals and credits (15) = **45 pts, 37.2% alone**.

**Why the agent program differs.** Prototype `N3_account_tier_position`: M2 is rated 80 units at tier 1 (20.00) by the agent, against 20 units at tier 1 plus 60 at tier 2 (5.00 + 12.00) under the new rule. The per-meter habit equals the agent program.

**Peer overlap.** The metered task uses a billing-group tier counter. This counter is keyed by account, so the mechanism is the same but the entity differs. I flag this for the master.

### LV-TR-4 — keep as a gate, rewrite. Not counted.

- Replace :77-79 with "`malformed_quantity`: its `quantity` is not what the `quantity` field rule allows." The single rule stays at :56. This removes the enumeration, so LV-ENUM is clean.
- Its checks stay, but no points are counted for it: the agent program differs 0% either way.

### LV-TR-2 half-even — keep the rule. Not counted.

- The rounding must be stated. Half-cent ties stay in the hidden data as the hook for judge R5.

### LV-TR-1 amplifier — keep. Not counted.

### Totals and prediction

- **Coverage.** All three counted levers together touch fresh E/S/Sub/Cr (20) and rescaled, relocated, rotated and api (60) = 80 pts (66.1%).
- **Prediction.** If Opus slips on one lever: tests about 63-75. If it slips on none: 100.
- **Honest risk.** Opus transliterates sentence by sentence. N3 sits in a definition and N2 in the glossary, so both may be read correctly. N1's re-entry is the habit with the best evidence of slipping, but it is still low (2/314). I expect tests of about 70-90 if exactly one of N1/N3 slips.

### Other changes

- **Judge.** Keep R1-R11. Add R12 "own input where unshared allowance needs a third share" (w3, for N1) and R13 "own account whose meters together cross a tier boundary" (w3, for N3). solve.sh gets `check r12 ok` and `check r13 ok`. Use J4 code-quality wording for R7. Keep J3 (R9).
- **Reference crash.** tests/test_output.py:5526 crashes when `standing_charge` is an integer (14/341 fuzz corpora). Fix in Phase 2 by converting through `str()`/Decimal there, then prove the outputs are byte-identical on the shipped tier and on the seeded hidden tiers.
- **Docker plan for Phase 3.** oracle x3, owner-only, nop, stub, forgery (at most 2 Docker-heavy blocks). Then a fuzz re-run with N1/N2/N3 habit variants, where each must differ by more than 0% on the agent program and at least 25% alone.

## LEAK_LIBRARY rows

| Lever | How it was written | Step leaked | Planned fix |
|---|---|---|---|
| LV-TR-4 H1 quantity type | Field rule plus a full list of malformed forms (:77-79) | 4 (read), 14 (docstring copies the list) | Drop the list; one field rule; demote to gate |
| LV-TR-3 H3 month | Glossary made "Month" = the billing period, the per-line field itself | 4, 17 (report.py:70) | Month = calendar month, period crosses month end (N2) |
| LV-TR-2 H2 half-even | Rounding stated at its own stage, so no displacement | 4, 13 | Keep as stated rule; not counted |
| COUPLING credit base | Formula spelled out with "before rounding of the total" | 4, 15 | Replace with N1 H7 re-share |

## Lessons for the master
- Glossary defined the H3 term as the per-line field itself, so the habit was the rule | template_change: LEVER_RULES_v1.md H3 row — add "the defined term must NOT equal any input column"
- Enumerated malformed list leaked H1 in 45 s; the precheck caught it only after the probe | template_change: LEVER_RULES_v1.md:38 (H1 row) — make LV-ENUM FIND a build-blocking gate before probe 1
- Fuzz with single-slip variants proved the corpora exercised every lever (85-98%) while the agent sat at 0%; this separates "corpus too thin" from "contract gives it away" | template_change: LEVER_RULES_v1.md G10 — require habit-variant zips in the differential fuzz
- Reference crash on integer standing_charge went unseen until fuzz (14/341) | no change: G12 already asks for generator bounds asserts; it was not applied to rate_card types
- No baselines.json and no XREF.md existed for a probed task | no change: round notes E already require XREF; enforce it in the build round
