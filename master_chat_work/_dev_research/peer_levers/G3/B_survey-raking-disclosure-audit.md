# B: survey-raking-disclosure-audit (Phase A verdict GENUINE)

Run: overall 36.88, tests 41.41 (53/128), rubric 32.35 (11/34). Root cause PROVEN in `A_survey-raking-disclosure-audit.md`: one branch in the agent's reference-wave band rule. Adding that one branch to a copy of the agent's script reproduces all 22 shipped oracle files byte for byte.

## 1. Inventory
- Domain: household survey weighting (design weights, nonresponse cells, raking, trimming, replicate variance, disclosure suppression).
- Archetype: a stdlib program `/app/out/derive_survey.py DATA_DIR OUT_DIR` plus 22 report files, plus a closing summary that answers 8 what-if questions (instruction.md:3-22).
- Agent sees 47 files, 4.76 MB in total: `HAS-7-standard.md` (508 lines, 4,201 words, the single rule document); a field dictionary (`.psv`); 4 frame registers (csv/tsv/fwf/jsonl); 12 interview files (waves 1-3 × quarters 1-4, mixed formats); contact logs (rfc5424/logfmt), outcomes and reissues; 7 benchmark files; 5 `rules__*` files (toml/ini/conf/csv); disclosure parameters and registry; pilot calibration record `calib__pilot-round.json`; prior band files for waves 1 and 2.
- instruction.md: 608 words, 24 lines.
- Tests: 35 checks: 28 positive worth 128 and 7 negative worth -25 (TRUTH.md:87-153).
  - Gates: 3 × w1.
  - Shipped data: 4 group checks × w5. Each needs the delivered files and the program's own run to equal the oracle bytes.
  - Hidden: 21 × w5 = 7 stage groups × 3 extracts the verifier generates itself.
  - Checks are per stage group: each check compares every file of one pipeline stage (`GROUPS` test_output.py:3194, `_group_on` :3284), so the checks are stage-isolated. Later stages still take earlier stage output as input, inside the agent program.
- Hidden or reseeded inputs: YES. An embedded generator builds a `challenge` extract (420 households), a `second` (560) and a `third` (480). Each has a different margin order, raking rounding point, collapse cap and cascade cap. The program runs as `nobody` with a 120 s limit (TRUTH.md:87-110).
  - About 82% of test weight sits on hidden extracts (105/128, TRUTH.md:82-83). The shipped-data checks hold 20/128.
- Judge: 18 criteria, `mode = "batched"`, 34 positive and -18 negative. R1-R8 compare closing-summary numbers with the oracle's what-if values.
- Reward: 0.5 tests + 0.5 judge (reward.toml 0.00390625 per test point, 0.0147 per judge point).

## 2. Rule map (graded rules, main ones)
| rule | where stated | form | trap explained? | shipped data separates? |
|---|---|---|---|---|
| Margin order and raking rounding point (12 combinations) | instruction.md:9: "never written into the rule files. The published pilot figures ... settle them, as the standard explains"; standard s13 :301-310 | stated as a recovery procedure: infer the setting from an aggregate record | partly: says *that* the settings must be recovered, not *which* they are | YES: the pilot record matches exactly one combination (agent step 13 found it uniquely, 26/26) |
| Band at reference wave (the rule the agent failed) | HAS-7-standard.md:237-243, a single paragraph | default plus a fallback chain whose scope is unclear: "Where hours are absent the band carries forward. For the reference wave it is the band of the unit's wave two interview hours; where that interview is absent ... wave two prior band file ... wave one ... zero hours. A wave two interview that carries hours governs over the wave two prior band file." | NO. The last sentence names a *different* trap (wave-2 interview over the stale prior-band file) and works as a decoy explanation. | NO. The pilot gives unit levels directly (TRUTH; agent step 13), so band derivation is never checked against a published figure. No shipped number separates the two readings. |
| Rounding: halves away from zero at every named division; raking fixes its own point | standard:25-37 | default plus one named exception | yes | n/a (the agent got it right) |
| Raking stop: deviation ≤ tolerance, else last completed iteration stands, not converged | standard:294-299 | plain rule | no | YES in principle: the shipped round should stop at 13 iterations unconverged (TRUTH:73-78), but no shipped number shows it |
| Trimming gated on stratum design effect; median of an even count = lower central value | standard s.trimming :342-352, worked example "on a stratum no report carries" | rule plus a worked example on non-graded data | example present, trap not named | example uses a non-graded stratum |
| Contact corrections: net state at latest instant, reinstatement wins a same-instant tie, out-of-scope void ignored | standard (TRUTH item 2) | stacked conditions | no | yes (the agent passed the dispositions groups) |
| Contact band from attempt counts, not the stale address-register field | standard (TRUTH item 3) | scope by omission: the register field exists but is never named as the source | no | yes (the agent passed) |
| Benchmark ties: winners sort after losers; reissue copy is the PSU source only for a blank psu_code; zero dwelling count never eligible; NFC names | standard (TRUTH items 8, 9, 11, 12) | one sentence each | no | yes (passed) |

## 3. Lever table (failed checks and criteria)
All failures come from ONE rule: the reference-wave band. Every failure flows downstream from raking membership.

| id | weight | rule graded | agent's reading | correct reading | mechanism | self-test on shipped data catches it? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| shipped_weighting_reports | 5 | raking, final weights | band at ref wave = wave-2 interview hours, then the fallback chain (derive_survey.py:1242-1251, written at step 28) | wave-3 hours first (general "band follows from its hours"); the chain applies only when hours are absent (solve.py:463-476) | pronoun/scope ambiguity in a 4-sentence paragraph; the closing sentence explains a neighbouring trap, so the reader feels the paragraph is "handled" | N: the agent's round converged in 4 iterations at dev 867,448 and looks healthy. Truth: 13 iterations, unconverged, dev 5,393,296. No shipped figure is published for the round. | AMBIGUOUS. The literal text supports the agent ("For the reference wave it is the band of the unit's wave two interview hours"). IN-16 risk, see s8. | B dependent chain + NEW "scope-ambiguous fallback" |
| shipped_replication_and_estimates | 5 | replicates, estimates | same root | same | cascade: replicates replay the whole chain | N | same | B |
| shipped_disclosure_reports | 5 | CV screening, suppression | same root | same | cascade | N | same | B |
| {challenge,second,third}_adjustment | 3×5 | adjustment group (includes raking_trace.json) | same root (INFERRED for hidden extracts; shipped proven) | same | cascade on new data | N | same | B |
| {challenge,second,third}_trimming / _estimates / _disclosure | 9×5 | downstream stages | same root (INFERRED) | same | cascade | N | same | B |
| Judge R1, R4, R5, R6, R7, R8 | 3+5+5+3+3+3 = 22 | closing-summary what-if numbers (e.g. R5 finished weight total 331499999995; the agent gave 331500000002) | the agent re-ran its own program with altered settings | the oracle re-run | same root: every what-if re-runs a wrong base | N | stated (what-if questions in instruction.md:13-22) | B (a judge-channel copy of the same error) |
| Judge R10 | 1 | code quality | the agent left dead state `eligible_set` | — | ordinary quality slip | n/a | yes | — |

Totals: 75 test points and 22 judge points are lost to one rule; 1 judge point is lost to code quality.

## 4. Contrast (what the agent passed)
- It passed every stage upstream of raking on shipped data and all three hidden extracts: frame, benchmarks, dispositions (10 × w5 = 50), plus 3 gates (3).
  - Those rules are one plain sentence each, but they still carry stacked conditions: correction ties, reinstatement, void scope, the stale register field, reissue PSU.
  - What made them easy: each fires visibly on shipped rows, and the agent inspected the rows (steps 5-20). This matches our DIAGNOSIS: where the data shows the rule firing, the agent codes it on first write.
- It passed the withheld-settings recovery as well. The puzzle was hard, but the shipped pilot record is a perfect oracle. The agent brute-forced 12 combinations and found the unique match (step 13).
  - Lesson: a "hidden setting recoverable from published aggregates" lever leaks completely when the aggregate check is cheap. It is our leaked "decoy refuted on the same page" in another form.

## 5. Agent behaviour
- 62 steps, about 23 min, $7.43.
- Read the whole standard at step 3 (`cat`) and the field dictionary at step 4. Inspected files at steps 5-20.
- Recovered the pilot combination at step 13. Wrote the program at step 21, edited it at 22-43, ran it at step 29 (rake 4 iterations, converged).
- Self-tests:
  - row-shuffle invariance (step 44);
  - determinism re-run (steps 52-54);
  - output checks (steps 55-58).
- None of the self-tests could expose the band misread: they test invariances, not values, and the only value oracle (the pilot) bypasses band derivation.
- The agent never noticed. The final message at step 61 says "The work is complete". The what-if answers were confidently wrong because they re-ran the same base.

## 6. Test design
- Expected values come from the embedded generator plus an oracle run at test time, on the shipped extract and on 3 reseeded extracts.
- Partial credit is per stage group: the group passes only if all of its files are byte-equal.
- Negatives:
  - hardcoded -5;
  - reuses_shipped_margin_order -5 (catches an agent that pins the pilot combination instead of recovering it per extract);
  - nondeterministic -3, filename -3, row_order -3, writes_outside -3, third_party -3.
  - None of them fired.
- Shipped-data-only weight: 20/128 (16%).
- Stage chaining means one upstream error fails every later stage on every extract (TRUTH:157-161, "byte compare so slip shows in every downstream report").
  - TRUTH mutation table (:133): one wrong band rule costs 0.258-0.688 of the channel.

## 7. Judge design
- Failed criteria: the 6 what-if numerics (R1, R4-R8) and code quality (R10). R2, R3 and R9 passed.
- Reusable pattern: what-if counterfactual questions answered in the closing summary ("if the min count were +2, how many cells change"). They force a real re-run.
  - JD-8 risk: they read the closing summary, not the files, so the observable differs. Still, one rule error is charged in both channels (tests 75 and judge 22). INFERRED: this stays legal only while each criterion names a distinct observable.
- JD-7: the oracle answers R1-R8 (TRUTH lists the oracle values), so the criteria are meetable.
- JD-18: R10 code quality is present.

## 8. QC safety
| lever | IN-15 | IN-16 | TS-16 | TS-19 | TS-20 | AL-28 | verdict |
|---|---|---|---|---|---|---|---|
| Reference-wave band fallback | stated | FAIL-RISK: "No significant ambiguity in anything that is graded" (01_Instruction_QC.md:46); two readings, both defensible, and no shipped figure picks between them | n/a | stated but ambiguous | ok | n/a | NOT ALLOWED as written (ambiguity). Allowed variant: state the chain unambiguously ("only where the reference-wave interview carries no hours") and keep the cascade. |
| Stage chaining across reseeded extracts | ok | ok | ok | ok | ok (5 per stage) | not a penalty | SAFE |
| Hidden settings recovered from published aggregate | stated (instruction.md:9) | ok | negative `reuses_shipped_margin_order` fires only on a replay, so it is honest-safe (TS-16 ok) | ok | ok | ok | SAFE but weak: it leaked here |
| What-if judge numerics | — | — | — | — | — | JD-8: different observable | RISKY (double-charges one error) |

## 9. Writing style
- "The standard is the contract: it defines every rule ... and it decides which files, and which rows inside them, are in scope." (instruction.md:1). Technique: put all rule authority in one long document and promise completeness, without listing the rules in the instruction.
- "Two settings of the round ... were never written into the rule files. The published pilot figures shipped with the data settle them" (instruction.md:9). Technique: state that a parameter must be *derived*, and name the evidence source without the value.
- "its sections are grouped by subsystem and do not follow the order the rules are applied in" (TRUTH.md:12, a design note mirrored in the standard's layout). Technique: rules sit far from the step where they apply, so the agent must assemble the pipeline itself.
- "Where hours are absent the band carries forward. For the reference wave it is ..." (standard:237-238). Technique (do NOT copy as is): a general default followed by a specific-case sentence whose scope reads as unconditional. It works through ambiguity, which IN-16 forbids.
- Worked trimming example "on a stratum no report carries" (TRUTH; standard s.trimming). Technique: a worked example that shows the method but cannot be used as a value check on graded rows.
