# Harden round 2 diagnosis: tariff-engine-audit-repair (board 0dd7a8c)

Probe 2 ran 25 Oct 06:42 IST on bundle d62ffe6, harness attempt 2, trial `tariff-engine-audit-repair__Ys5W4wY`.
Scores: tests 100 (127/127), judge 3.33, overall 51.66. Session rename: opencode `ses_e8f53eb83ffeUY2Klj90QGF61h` is listed; codex has no match.
QC kit HEAD is `976c166611e555e2ba20eb8d81bed279cee1ea30`, the same as round 1. No `baselines.json` exists for this slug.

## 1. Phase A: is the score genuine? GENUINE

- Copy vs BUNDLE: `diff -rq Tasks_INPUT/tariff-engine-audit-repair BUNDLE` shows no differences. The staged copy differs only by the `.kiro-staged-from` marker and by `task.toml` `allowed_hosts` gaining `"host.docker.internal"` at :25 and :32. Both come from harness staging.
- `result.json`: `exception_info: None`. The run took 01:12:57Z to 01:25:11Z (about 12 min), with no timeout. The agent used 3.88M tokens in, 55.6k out, cost $4.08.
- `wrapper.log`: "INTEGRITY: all 1 trial(s) completed cleanly; scores are trustworthy." `test-stdout.txt` ends "reward: 0.5167". It has no `Permission denied`, no `Errno 13`, no missing file and no traceback.
- Judge: gpt-5.6-sol in batched mode read `/logs/agent/trajectory.json` and cited steps. For example, R9: "After the final source edit in step 47, the agent reran its generated checks and visible tests, but did not rerun the bespoke edge probes".
- Correction to the prompt's judge line. Two criteria earned: R8 (+3) and R13 (+3, "two-meter account 150+100 vs 200 tier"). R9 fired (-5), so the net is 1 of 30 = 3.33. R1-R7, R10-R12 earned 0.

## 2. Root cause

| cause | answer | evidence |
|---|---|---|
| 1 run error or wrong copy | NO | Same tree, no exception, clean verifier (section 1). |
| 2 harness or rescoring change | NO | Kit HEAD 976c1666 in both rounds. `reward.toml` weights are unchanged (tests 0.003937 = 0.5/127, judge 0.016667 = 0.5/30). finalize rescaled 0.5167 to 51.67 by the same formula as probe 1. Probe 1 was not an artefact either (round 1 Phase A). |
| 3 our fix rounds made it easier | PARTLY | Round 1 changed `api_contract.md`, the data generator in `tests/test_output.py`, `solve.py`/`solve.sh`, `judge.toml` (R12, R13) and the shipped data limits. Of these, only `api_contract.md` reaches the agent. Its N1 sentence (:125-128) was rewritten at master condition 00:20 to name the amount ("never more than a line's remaining exact value"), the method ("in equal parts ... among the energy lines not yet at zero") and the repetition ("as often as some stays unshared and such a line remains"). That is a separating case written next to its use. N2 (:51) and N3 (:38-40) are definitions the agent reads at step 4. The tests, generator and judge are not visible to the agent. |
| 4 levers weak by design | YES | Each counted lever is one explicit sentence that names its separating quantity. The agent transliterated every one of them in a single write (step 18, 01:17:38Z), 4 min after reading the contract, and never changed the graded logic afterwards. See section 3. |

**PRIMARY CAUSE: 4.** Every lever is stated as an explicit method sentence, and Opus transliterates explicit sentences.
**Contributing: 3.** The 00:20 N1 rewrite removed the only room left for a miss on the H7 branch.

## 3. Lever table (reward-details.json + trajectory)

| lever | rule (file:line) | checks it moves | pts | earned | read / coded / self-tested (step) | given away by | verdict |
|---|---|---|---|---|---|---|---|
| N1 allowance re-share (H7) | Energy share :46-48; Amounts :125-128 | fresh/rescaled/relocated/rotated lines (energy), subtotals, credits | 60 | 60 | read 4; coded 18 `share_allowance` (`while left>0 and takers: part=left/len(takers); take=min(part,room)`), used 20; tested 32 (allowance above a line), 39-40 | Amount, method and repetition all named in :125-128 (the 00:20 wording). The agent's loop is that sentence word for word. | LEAKED |
| N2 calendar month (H3) | Month :51; Active days :43; Standing :115-119 | fresh/rescaled/api standing, subtotals, credits | 45 | 45 | read 4; coded 18 `month_spans` (calendar.monthrange); tested 29-31, probe 2026-01-20..2026-03-02 (judge R4) | Standing :115-119 spells the per-month sum. "Month" is defined in the glossary as a calendar month and is not confusable with any per-line field. | LEAKED |
| N3 account tier position (H6) | Account position :38-40; Energy :107-113 | relocated/rotated/api lines, subtotals, credits | 45 | 45 | read 4; coded 18 `rate_tiers(quantity,tiers,offset)`, offset carried in report.py step 20 (docstring "so the split follows account positions rather than meter positions"); tested two-meter 150+100 vs 200 (judge R13) | The definition names the order and the carry-over ("the period quantity of each meter following those of the meters before it"). | LEAKED |
| LV-TR-4 strict quantity (gate) | field rule :63, :85-86 | every exceptions/lines check | gate | held by agent | 13: value-type counter on meter_reads (int 10372, str 143, float 79, bool 55, None 37); 16: `_quantity` rejects bool, non-int and negative values | Field rule, plus the agent's own census of the data | gate kept, LEAKED as a lever (uncounted) |
| LV-TR-2 half even (gate) | :49-50, :128-130 | all money checks | gate | held | 18 `round_money = Fraction(round(v*100),100)` (half even); 39-40 tie probes | Named rule | gate kept (uncounted) |
| LV-TR-1 amplifier (H5) | :3-5 | T2/T3 w3, negative -3 | 6 | 6 | 25-26 edited 2 visible tests; did not delete any | Contract is the stated arbiter | held as design, not a lever |
| negatives | - | hardcoded -5, visible_test_removed -3 | -8 | 0 fired | - | - | correct, no cheating |

Judge: R1 0, R2 0, R3 0 (no independent recompute; actuals came from `build_invoices`), R4 0 (wrong probe shape), R5 0 (arithmetic search, no energy-line tie run), R6 0 (no altered copy), R7 0 (unreachable branches in `share_allowance`), R8 +3, R9 -5, R10 0, R11 0, R12 0 (no third share), R13 +3.

## 4. Trajectory autopsy (49 steps, about 11 min)

- **Read (01:13:14-01:15:01, 2 min).** Step 3 `find /app`, then 4 `cat api_contract.md` (the whole contract), 5-8 the package source, 9-12 ci files, failing log and visible tests. In 13-14 it measured the data with Python (quantity value types, negatives, regression-case stats: 2000 cases, 675 two-meter, 980 with allowance).
- **Write (01:17:08-01:18:31, 1.5 min).** Step 16 wrote parser.py (strict quantity, exception order). Step 18 wrote core.py, with exact Fractions and N1, N2, N3 and half even all in one write. Step 20 wrote report.py (account offset, share, then rounding) and step 21 `__main__.py`. Steps 19 and 47 were cosmetic edits to core.py (the CENT constant and a blank line). **The graded logic never changed after step 20.**
- **Self-tests (01:18:31-01:20:11).** Steps 22-24 ran the regression and shipped analysis. Steps 25-27 edited the 2 visible tests and ran unittest. Steps 29-32 ran recompute probes on its own Fractions: determinism, all 2000 regression cases against `customer_claim` (mixed claims, with no separation on any lever), and a search for allowance above a line (3 found, all covered).
  - Levers its tests covered: N1 to the second share only (no third), N2 (Jan-Mar span), N3 (two meters across tier 1) and half even.
- **Deliverables (01:20:11-01:24:05).** Steps 33-48: missing-file checks, `make_deliverables.py`, zip build, re-extract and re-probe, py_compile. Final response at step 49.

## 5. Differential fuzz on the probe-2 program (OUT/fuzz_r2/)

- Driver `fuzz_r2.py` is a copy of round 1 `fuzz_r1.py`. It runs the agent at `OUT/agent_program/repo/src` against the test oracle `_Ledger`, with seed 0x0DD7A8C and sizes 12/24/30/45. The comparison covers the whole document, exceptions included.
- 320 jobs, 306 valid (generator rejections: N1 11, N2 2, N3 1). The log ends `ALL_DONE`.

| family | corpora differing |
|---|---|
| lever-free | 0/80 (0%) |
| N1 | 0/69 (0%) |
| N2 | 0/78 (0%) |
| N3 | 0/79 (0%) |

**All three counted levers are REVEALING (0% differing) on the probe-2 program, and so are both gates.** Under the master rule, none of N1, N2 or N3 counts any more as a lever against fresh Opus.

## 6. Per lever: did the contract name it, or did the agent read it on its own?

- **N1: named by the contract.** The 00:20 sentence names the amount ("never more than a line's remaining exact value"), the method ("equal parts ... among the energy lines not yet at zero") and the repetition ("as often as some stays unshared and such a line remains").
  - The agent's `share_allowance` docstring paraphrases :125-128, and its loop is the sentence. Nothing was left to its own reading.
  - This matches caldermoor (da61544): naming the amount and method removed the only measured miss.
- **N2: named.** Standing :115-119 states the per-month sum at its use. "Month" (:51) is a glossary term with no competing per-line field, so the H3 trip condition is not met (LEVER_RULES 1b H3).
- **N3: named.** :38-40 states the carry-over across meters. The agent's docstring restates it.
- **Gates: named, plus the agent's own care.** Step 13's value-type census shows the agent looks at the data before trusting the field rule.

## 7. Lever plan for Phase 2 (for master review)

Measured in `OUT/proto/proto_b.py`, with output in `proto_b.out`. No BUNDLE edits yet.

### Option A (needs Ayush): N1 as a bare recursive H7 term in the glossary only

- **Where it goes.** Replace Energy share :46-48 with one recursive definition, and cut the re-share sentence from Amounts :125-128.
- **Proposed text.**
  - Glossary: "Energy share: of an amount among some energy lines, each of the lines takes an equal part of the amount, but never more than what is left of its exact value; a line's energy share is what it takes, plus its energy share of the amount the lines could not take, among those of them not yet at zero."
  - Amounts: "each line amount is its exact value, less, for an energy line, its energy share of the allowance among the account's energy lines, rounded half to even to 0.01."
- **Semantics do not change.** The oracle, tests and shipped data stay byte-identical. The probe-2 program scores 1.0 by construction (it implements the same semantics), so this option relies on a fresh agent misreading the recursion.
- **Habit and reflex.** It is H7 re-entry stated through a recursive term (the shapes measured as caldermoor CM-B and caldermoor N2 'wait'). The reflex readings are one pass, or one pass plus one re-share. Both cost 60/127 = **47.2% alone** (round 1 COST_TABLE N1_one_pass / N1_two_passes = 0.5276). That is over the 45% cliff bound.
  - Trim: N1's footprint falls under 45% if Option B's new rows join the denominator (60/157 = 38.2%).
- **QC risk.** QC has called a bare "by the same rule" ambiguous (IN-16). The recursion answers that, because it states the base case ("not yet at zero"; nothing left means nothing to take) and makes the repetition determinate.
  - QC_DEFENCE fallback: IN-16 DO, adding back one general clause: "the sharing repeats until nothing is left or every line is at zero".
- **Evidence it can work.** Caldermoor's bare H7 is the only habit Opus missed in 1889 fuzz corpora, at 12.9% on its survivor. The probe result for caldermoor's recursive-term shape is still pending.

### Option B (keeps explicit wording): N4 monthly tier positions (H6 + H3 shape, glossary only)

- **Where it goes.** Change only Account position :38-40: "...counted from 1 afresh in each month over its meters in ascending `meter` order, the month quantity of each meter following those of the meters before it."
  - Add the term "Month quantity: the sum of `quantity` over the accepted reads of a meter whose `day` is in that month."
  - Energy :111-112 adds "units are summed over the months of the period" (one general clause).
  - Period quantity :52 stays, and stays in use (repair report and module notes).
- **Habit and reflex.** The probe-2 program, like every program written to the current text, counts positions once over the period via Period quantity (the existing quantity and the obvious carrier). It is H6, because the position state is keyed on (account, month) while the habit key is the account.
- **Measured incidence of the reflex vs B on the probe-2 semantics.**

| sample | B differs from the period reading |
|---|---|
| shipped data | 0/2000 accounts |
| regression cases | 0/2000 cases |
| current hidden corpora | fresh 0/30, rescaled 0/30, relocated 0/24, rotated 0/24, api 38/45 |
| fuzz families none, N1, N2, N3 | 0 corpora |
| fuzz family N2+N3 | 80/80 corpora, 1899/2082 accounts |

  - The shipped control reconciles under both readings (shipped periods sit inside one month).
  - **It differs only where a period crosses a month and the account's units pass tier 1. The probe-2 program differs on it, so it is not REVEALING (> 0%).**
- **Owned rows (G1, PL rule).** N4 separates even with one meter (sum of the per-month min vs the min of the sum), so it does not need N3.
  - Add one hidden family `monthly` with single-meter crossing-month accounts and units above tier 1 in two months. Its checks would be `monthly_energy_lines_exact` 5, `monthly_subtotals_exact` 5, `monthly_credits_and_totals_exact` 5, plus a mutated rerun `monthly_rescaled_*` 15.
  - Planned cost alone: monthly 30 + api 15 = 45/157 = **28.7%**. The other levers become N1 60/157 = 38.2%, N2 45/157 = 28.7% and N3 45/157 = 28.7%. All four sit in 25-45%.
  - One-fact-wrong (CL-4): an agent that has only N4 wrong loses exactly those 45 points. The standing rows are untouched (N2 owns them), and the shipped rows are untouched.
- **Judge.** Add R14 w3: "probed an account whose units pass tier 1 in two months of one period and compared month-restart positions", shown by solve.sh `check R14 ok`.
- **Risk, stated honestly.** This is still an explicit definition. Tonight's sentinel, sensor and district redesigns with explicit H6/H3 wording all scored tests 100. Its only advantage over N3 is that the glossary carries it, not the use site, and that the obvious carrier (Period quantity) already exists.

### Recommendation

- **A + B together** (needs Ayush for A). With 157 test points and the judge at 3.33, the outcomes would be:
  - A missed alone: tests 61.8, overall about 33.
  - B missed alone: tests 71.3, overall about 37.
  - Neither missed: tests 100.
- **If Ayush keeps explicit H7 wording: B alone**, with N1 left as is. Expect tests 71.3 if B is missed, and 100 if not.
- No other shape found survives the shipped-visibility test:
  - account-level standing dedupe: 1034 shipped accounts have overlapping meters, so it is visible and a cliff;
  - redefining `up_to` as block width: contradicts the field name;
  - cumulative register reads: large shipped change;
  - duplicate key without meter: transliterated at once.

### Reflex gate note

The probe-2 program implements N1-N3, so on the new tests it scores 1.0 under Option A alone. Under B it loses the 45 N4 points (about 0.71). It cannot reach <= 0.20 without a union cost over 80%, which breaks the master's 25-45% no-cliff bound. Following the master note, I will gate each new lever on its single-lever mutant (25-45%) and report the agent-program score without strengthening on it.

## 8. LEAK_LIBRARY rows

| lever | how it was written | leaked at | planned fix |
|---|---|---|---|
| N1 allowance re-share (H7) | Amounts :125-128 names amount, method and repetition ("as often as some stays unshared and such a line remains") | step 18, `share_allowance` loop = sentence | Option A: one recursive glossary term, with the re-share sentence cut from Amounts (needs Ayush); else keep and add N4 |
| N2 calendar month (H3) | Month :51 glossary = calendar month; Standing :115-119 spells the per-month sum at use | step 18, `month_spans` calendar.monthrange | keep as counted row; no per-line field competes with "month", so H3 cannot trip |
| N3 account tier position (H6) | Account position :38-40 names the order and the carry-over across meters | steps 18-20, `rate_tiers(offset)` | keep; extend the same state by month (N4) so the carrier is keyed wider than the habit |

## 9. Addendum 07:20 (caldermoor probe 5)

**What changed.** Caldermoor probe 5 (after harden r3, da61544) scored tests 98.45. Both of its N2 'wait' tests passed. That lever is a glossary-only recursive term against `chain_depth`, the same shape as my Option A. So the recursive-term shape leaked to fresh Opus, just as explicit wording did. Tonight's tally is sentinel 100, sensor 100, district 100, tariff 100, caldermoor 98.45, metered 100.

**Option A.** The evidence for my recursive wording is now against it (n=1, measured leak).
- The only shape with a measured Opus miss is still the bare H7 "shared again by the same rule" form, which caldermoor used before 5f2e150.
- A could become that bare sentence in Amounts :125-128 (cutting "as often as ..."). That still needs Ayush, and it carries the QC IN-16 ambiguity risk that QC already called out. Its fallback (IN-16 DO, one general repeat clause) gives back exactly the wording that leaked.
- Expected value: low, and it should not be counted.

**Option B.** The evidence is unchanged: B is explicit wording, and explicit wording leaked 5 of 5 tonight.
- B is the only candidate that differs on the probe-2 program (fuzz N2+N3 80/80; api 38/45). So it is the only one that meets the master's "> 0% differing" condition.
- Expect fresh Opus to read it. Its honest prior for a miss is low.

**Recommendation.**
- B as the counted lever. It is measurable, owned rows, 28.7% alone.
- Bare-H7 N1 only if Ayush accepts the QC risk. I no longer recommend the recursive form.
- Say plainly to Ayush that wording shapes look exhausted against Opus 5. If the round 2 probe is still tests >= 95, I recommend parking at round 3 rather than another wording round.

**Second look at the section 7 rejected list.** None of the four improves:
- **Account standing dedupe.** It lives in 1034 shipped accounts. It would need shipped and regression data rewritten (a Never 11 risk to the digest) and is a cliff (> 45%).
- **`up_to` as a block width.** Still contradicts the field name, so QC would call it misleading.
- **Cumulative register reads.** Still a large shipped change, and the rule would be explicit anyway.
- **Duplicate key without meter.** Transliterated at once.

**The one new shape the evidence points to.** The only positive Opus missed tonight was behavioural, not semantic: caldermoor `failed_run_leaves_no_partial_file`.
- A tariff analogue: a stated contract rule that a run which fails (malformed input file, missing file) writes no partial `invoices` output and exits non-zero. `missing_source_is_named` today checks only the message.
- It would be an owned row with a hidden failing corpus.
- The evidence is one data point. It needs its own design check: under G10 a single act check worth >= 25% is a cliff, so it should go in as an extra row beside B, not as the main lever.
- It needs the master's and Ayush's view before Phase 2.
