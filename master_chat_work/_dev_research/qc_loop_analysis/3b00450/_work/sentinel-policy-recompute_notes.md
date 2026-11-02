# sentinel-policy-recompute notes (session 3b00450)

## 1. Rounds
| ver | sha | kit | F/M/W | origin counts | preceding edit |
|---|---|---|---|---|---|
| v1 | 8e66159 | 71a653b2 | 5/6/3 | BASELINE 14 | build + harden_r1..r3 |
| v2 | 1d97a1e | 71a653b2 | 2/4/7 | FIX 3, KEPT 2, MISSED 8 | P12_r1 |
| v3 | f06feb3 | 71a653b2 | 1/2/3 | FIX 2, KEPT 2, MISSED 1, REFLAG_FIXED 1 | P12_r2 |
| v4 | 56a292b | 5574d77e | 4/3/0 | HARDEN 6, KEPT 1 | P12 v3 r3 (20261024T1925_fix) + 5 hardens + judge rebuild (20261026T1800_rebuild) |
| v5 | d7661db | 5574d77e | 2/3/1 | MISSED 4, KEPT 2 | 20261027T0717_fix |
| v6 | aaec5ad | 5574d77e | 4/2/7 | MISSED 8, KEPT 4, FIX 1 | 20261027T1030_fix |
| v7 | 24b37c6 | 5574d77e | 1/4/1 | MISSED 3, FIX 2, RULE_CONFLICT 1 | 20261027T1217_fix |
Post-v1 total 51: MISSED 24 (6 of them LATENT_FIX: a QC-fix wrote the line, a later round flagged it), KEPT 11, FIX 8, HARDEN 6, RULE_CONFLICT 1, REFLAG_FIXED 1.

## 2. FIX_CAUSED attribution (8 direct + 6 latent)
Prompt-asked 9: v2 AL-27 (P12_r1.md:33), v2 TS-26 (P12_r1.md:28), v2 JD-9 (P12_r1.md:36), v6 TS-7 (1030_fix.md:16), v7 TS-13 (1217_fix.md:15), v7 JD-15 (1217_fix.md:20), latent v3 JD-11 (P12_r1.md:40), latent v6 IN-13 (0717_fix.md:19), latent v7 CL-2 (0717_fix.md:16 + 1217_fix.md:17).
Session's own 5: v3 JD-7 (R5 reworded, solve.sh not), v3 TS-14 (descriptions not updated), latent v5 AL-2 (R3 retarget dropped the only grader of the stdlib rule), latent v6 TS-19, latent v7 IN-L2 (split residue).
In 8 of 9 prompt-asked cases the prompt line copies the previous QC report's own "Fix:" text (v1 G01-2, G05-2, G04-2, G04-4; v4 M7, F2/F3; v6 F1/M5, W9).
Patterns: rewording a judge criterion (5), adding an assert or check (4), moving weight / renumbering (2), deleting a clause or grader (2), splitting a sentence (1).

## 3. Ping-pong
- Shipped omnibus check: TS-13/TS-20 flagged v1-v6 (6 rounds, severity fail->minor->none->minor->minor->fail on the same weights). P12_r1 split PAUSED: fails our own trap-survival and G3 shipped-only <=5% (p12_r1/RECHECK_FIX.md:5, :35-36). Kept v2-v6. Split in 1217_fix F1 -> v7 TS-23 (39 > 35) and v7 TS-13 (narrower). QC v7 Fix: merge back to 35 (v7.md:44-45).
- Judge R10/R11 handler criterion: v1 positive absence (JD-2 v2) -> negative -1 (v3) -> rebuild R11 two clauses (IN-8 + JD-5 v4) -> clause removed (v5) -> vacuous (CL-2 v7).
- R6 probe: JD-15 v6 -> dropped, weight onto R7-R9 -> JD-15 v7.

## 4. Reviewer variance
- TS-20 on unchanged weights: fail v1, minor v2, pass v3 (v3.md "re-judged it ✅"), minor v5, fail v6.
- Passed then fired on identical bytes: v2 TS-26, JD-2, IN-2, STEP11 (VARIANCE.md rows); v3 JD-11; v5 JD-15 R10 (v5.md "v4 read R10 as a constraint"); v6 JD-6, AL-28, DS-17, DS-27 :334 (since v1).
- QC_RULINGS/playbook ignored: QC v7 TS-23 Fix "merge ... so the count is 35" vs QC_FIX_PLAYBOOK_v2.md:41 (TS-23 KEEP, no cap) and feedback.jsonl 2026-10-24 12:52. TS-13 KEEP defended by QC_RULINGS row (p12_r2/RECHECK_FIX.md:18) re-counted every round. No QC prompt carries the kept list (qc_reverse/B/SUMMARY.md "QC prompts never pass QC_DEFENCE").

## 5. Difficulty impact
| fix round | tests bodies | weights | data | instruction | judge | verdict |
|---|---|---|---|---|---|---|
| P12_r1 (->v2) | rerun check +reference equality | none | conf:4 states row+window | :1 split | R3/R8 retarget, R7 reword | NEUTRAL/HARDER (double pay) |
| P12_r2 (->v3) | +row-version fixture, +resolution_order assert, -rerun reference loop | none | none | :5 reword, :7 split | R5 5->3, R10 +1 -> -1 | HARDER tests (mutant 11/31), rerun loop EASIER (trap L7 ratio 0.889, scores.jsonl P12 r2), judge HARDER |
| harden/rebuild (->v4) | P 31->131, 15 judge criteria | | many | | rebuilt | HARDER (tests 100 -> 96.18/78.63) |
| 0717 fix (->v5) | none | timeout 2700->4200 | none | 2 requirements deleted | R11 missing-input clause deleted | judge EASIER (R11 now vacuous) |
| 1030 fix (->v6) | +negative -3, summary inputs exact | none | none | none | labels | HARDER (small) |
| 1217 fix (->v7) | shipped 1 check -> 5 | shipped 1 -> 15 of 145 | +ledger_ref/overrides_ref pointers | :3 names cli.py, :7 scope | R6 dropped, R7-R9 3->5, R12 5->3, +cli.py artifact | tests EASIER (+2.06 pp same failures), judge EASIER (R10 vacuous +12.2 pp) |

Harness (MASTER_RUN_LEDGER.md:152-208, reward-details.json):
| attempt | when | after | final | tests | judge |
|---|---|---|---|---|---|
| 1 | 10-20 | pre-QC | 77.78 | 100 | 55.56 |
| 2-4 | 10-24/25 | P12 r1-r3 | 71.62 / 68.92 / 70.0 | 100 | 43.24 / 37.84 / 40.0 |
| 5 | 10-27 05:53 | hardens + rebuild | 65.59 | 96.18 | 35.0 |
| 6 | 10-27 06:18 | same bundle | 45.56 | 78.63 (103/131) | 12.5 (R12 only) |
| 7 | 10-27 14:34 | QC fixes v4-v6 (07363dd) | 50.1 | 80.69 (117/145) | 19.51 (R2 3 + R10 5) |
Attempt 7 failed exactly attempt 6's six checks (28 pts). Re-scored on the pre-fix weights: tests 78.63, judge 3/41 = 7.32, final 42.97. The QC fixes added +7.1 pp final for identical behaviour: +1.03 from the shipped split, +6.1 from vacuous R10.
Verdict: partly. QC fix rounds 1-2 made it harder; fix rounds v4 and v6 made it easier by ~7 pp final (tests +2.1 pp, judge +12.2 pp); difficulty itself came from the hardens.

## 6. Rounds
7 QC rounds, still FAIL (v7 1/4/1); one more fix (20261027T1328_fix.md) issued, not yet QC'd. Self-caused per round (direct FIX + RULE_CONFLICT, latent in brackets): v2 3, v3 2 [+1], v4 0 (harden 6), v5 0 [+1], v6 1 [+2], v7 3 [+2].
