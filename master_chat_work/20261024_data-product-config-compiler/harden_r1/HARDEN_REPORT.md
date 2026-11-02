# Harden round 1: data-product-config-compiler (e317de1)

Phase A was GENUINE: probe 1 scored tests 125/125, judge 25/28, overall 94.65. The primary cause was Cause 4: the levers were weak by design. Fuzz on the probe program found 0% of corpora differing for every build lever (DIAGNOSIS.md).
The new tree sha is bf73461da54c. The bundle has 35 tests (P = 120, one negative -5) and 15 judge criteria (positive 37).

## Levers before and after
| lever | before (build 13a9939) | after (harden r1) | alone loss | one-fact-wrong | fuzz r3 differs |
|---|---|---|---|---|---|
| LV-CC-1 active owner + owner RETIRE | counted, 54.4% | background rule (no carve-out wording) | 65.0% | n/a | 0% in r1 |
| LV-CC-2 strict JSON type | counted, 68.0% | background; reason-3 enumeration removed (:109) | 83.3% | n/a | 0% in r1 |
| LV-CC-4 canonical log ids | counted, 58.4% | background | 69.2% | n/a | 0% in r1 |
| NL-1 H3 "Assignment of an owner on D" = latest active_from | none | counted; contract :38-42, owners.csv :63-65 | 31.7% (38/120) | 4.2% (latest covering row) | 88.0% |
| NL-3 H7 `quota_cap`; units given back are re-shared among the uncapped, and holders keep their units | none | counted; :140-145, schema quota_cap | 31.7% (38/120) | 27.5% (two rounds) | 81.8% |
| NL-4 H1 text integer as digits 0-9, boolean true/false; other text is passed over | none | counted; :87-93 | 59.2% (71/120) | 20.8% (isdigit) | 100% |
| COUPLING largest remainder over active weights | amplifier | amplifier (feeds NL-1/NL-4 into quota rows) | 0 alone | n/a | n/a |

- With all three levers wrong, tests score 20.0% (overall 55.0 at judge 90). G10 "all but this one right, overall < 70" holds only for NL-4 (65.4); NL-1 and NL-3 reach 79.2. The master asked for each lever at 25-40% alone, and both meet that. Full table: WORK/COST_TABLE.md.
- In fuzz r3 (326 cases, 320 valid), the probe agent program differs on 96.6% of corpora and the oracle on 0%. Outputs: OUT/fuzz/cf_out_r3.jsonl.

## Counts and shares
- Tests: 10 families x (visible w3 + `_hard` w5) = 80; date_shift, quota_rescale, shuffled 5 each; three capped rows 5 each; readonly 3; six generic rows w1; layout w1. Total P = 120.
- Hidden or mutated share is 88/120 = 73.3%, shipped-only 31/120 = 25.8%, whole-document 19/120 = 15.8%, isolated 1/120 = 0.8%.
- Judge changes:
  - R1-R6 must now hold on the shipped data and on an altered copy (J2).
  - R8 now uses the J4 maintainability wording.
  - New w3 criteria: R13 (an owner's later row ended before D, so the owner is orphaned), R14 (a non-digit text value keeps the earlier value) and R15 (a cap that binds only after a re-share).
  - R11 is honesty (-3) and R12 is grader reads (-5).
  - solve.sh prints `check <id> ok` for R1-R7, R10 and R13-R15.

## Gates
- Reflex gate: the probe agent program scores 21/120 = 0.175 against the new tests (limit 0.20). Grades are in OUT/grades/.
- STACKING_CHECK: PASS (OUT/STACKING_CHECK.md).
- Rule coverage: 55 rows, 0 uncovered.
- xref_check: 22 entries, 0 findings.
- precheck.sh with kit 976c1666: PRECHECK CLEAN, 0 FAIL.
- validate_bundle (cli-config): 41 passed, 0 failed.
- No __pycache__ in the bundle.
- Docker r2 was run from exe_copy copies of the final tests (`/tmp/dk-e317de1-20261025T014719-4d75`, 0 exceptions):

| run | score |
|---|---|
| oracle x3 | 1.0, 1.0, 1.0 |
| owner-only | 1.0 |
| nop | 0.0 |
| stub | 0.0 |
| forgery | 0.0167 |

- Docker r1 had scored forgery at 0.2667, because copied documents passed the visible rows. The fix is in `_load`: each /app/out document must be byte-equal to what the delivered tool writes for the shipped release.

## Not run
- Live judge: no judge run here, so the judge score is not measured.
- Playground static check: removed upstream, so not run.
- Live Opus probe: next step.

## Lessons for the master
Keep-rewrite levers with unchanged semantics cannot show >0% fuzz on the probe program; only new-semantics levers can count | template_change: harden prompt "Phase 2 lever rule" should say keep-rewrite levers are background only
Forgery from copied shipped answers passed every visible row (0.27) until visible rows required byte-equality with the delivered tool's rerun | template_change: LEVER_RULES G1 add "visible rows re-derive from the delivered program"
Equal-weight team plants keep an H3 team lever off the quota cliff, so one-fact-wrong stays near one fact | no change: CL-4 already covers it
