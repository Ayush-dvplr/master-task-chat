# QC loop analysis (session 3b00450, 27 Oct 2026)

Scope: 8 tasks, 54 QC reports, 381 findings (`FINDINGS.csv`). Sentinel was classified by hand (`_work/sentinel-policy-recompute_notes.md`). The other 7 were classified by script (`_work/classify.py`, `_work/attrib.py`): it parses each report's Findings list and diffs the cited file:line between consecutive `QC/copies/<sha>/<slug>`. Parsed fail/minor/warn counts match the report Verdict lines in 51 of 54 reports. Two of the three misses are off by one; the third is dispatch v5, whose verdict line the regex could not read, though its parsed findings (3/4/3) are correct.

Caveats:
- 58 post-v1 rows carry `UNVERIFIED` in cause_evidence. The QC copy for the earlier round was pruned (cohort v1-v3, district v1-v3, emberforge v1-v4, schema v1-v2, vendor v1-v4), so the origin there rests only on the preceding edit type.
- REFLAG matching is rule + file name, which is coarse.
- MISSED_EARLIER means the cited line is byte-unchanged and an earlier QC passed it. It does not mean the finding is false: sentinel v7 CL-2 is a real defect in this group.

## 1. Origin of findings (post-v1, n = 255; v1 = 126 BASELINE)

| origin | n | share | fails |
|---|---|---|---|
| FIX_CAUSED | 67 | 26.3% | 33 |
| MISSED_EARLIER (line unchanged, flagged late) | 67 | 26.3% | 23 |
| REFLAG_KEPT (kept with a reason, re-counted) | 50 | 19.6% | 15 |
| HARDEN_CAUSED | 37 | 14.5% | 20 |
| REFLAG_FIXED (fix did not hold) | 25 | 9.8% | 9 |
| NEW_RULE (kit text changed) | 6 | 2.4% | 0 |
| RULE_CONFLICT (split vs A3 cap) | 3 | 1.2% | 0 |

Reviewer-side findings (MISSED_EARLIER + REFLAG_*) total 142/255 = 55.7%. Our own edits (FIX + HARDEN + CONFLICT) total 107/255 = 42.0%. The kit accounts for 2.4%.

Sentinel by hand: post-v1 51 = MISSED 24 (6 of them latent fix effects: a QC fix wrote the line, and a later round flagged it), KEPT 11, FIX 8, HARDEN 6, CONFLICT 1, REFLAG_FIXED 1.

### Totals by version index (all tasks)

"More errors after each round" is not true on average. Findings fall as rounds go on: v1 126, v2 48, v3 53, v4 44, v5 38, v6 44, v7 20, v8 7, v9 1. The rises come from specific events:

| spike | cause | evidence |
|---|---|---|
| dispatch v3: 15 fails | P12 r2 regenerated test_output.py from a stale generator (8023 + 18445 changed lines, `_work/difficulty_deltas.tsv`) | 8 FIX_CAUSED |
| emberforge v6: 8 fails | harden after the v5 PASS | `P9_harden_lp1_r1` |
| cohort v3: 4 fails | harden after the v2 PASS | `P9_harden_r2` |
| district v4: 4 fails | harden after the v3 pass | `P9_harden_lp1_r1` |
| sentinel v4 | 5 hardens plus the judge rebuild | `20261026T1800_rebuild.md` |
| sentinel v6: 13 findings | 8 MISSED_EARLIER on lines unchanged since the rebuild | sentinel notes |

### Per task per round

Columns: BASE, FIX, HARD, MISS, KEPT, RFIX (REFLAG_FIXED), CONF (RULE_CONFLICT), NEWR (NEW_RULE).

| task | ver | F/M/W | BASE | FIX | HARD | MISS | KEPT | RFIX | CONF | NEWR |
|---|---|---|---|---|---|---|---|---|---|---|
| sentinel | v1-v7 | 5/6/3, 2/4/7, 1/2/3, 4/3/0, 2/3/1, 4/2/7, 1/4/1 | 14 | 0,3,2,0,0,1,2 | 0,0,0,6,0,0,0 | 0,8,1,0,4,8,3 | 0,2,2,1,2,4,0 | 0,0,1,0,0,0,0 | v7:1 | 0 |
| emberforge | v1-v9 | 3/3/3, 1/2/4, 2/0/1, 2/1/1, 0/0/1, 8/0/1, 2/0/2, 4/0/1, 0/1/0 | 9 | 0,0,1,3,0,0,1,3,1 | 0,5,0,0,0,4,0,0,0 | v6:2, v7:2 | 0,1,2,1,1,1,1,0,0 | v6:2, v8:2 | 0 | v2:1 |
| dispatch | v1-v8 | 4/3/2, 3/1/3, 15/0/2, 0/3/4, 3/4/3, 4/1/3, 1/1/2, 0/1/1 | 9 | 0,3,8,2,5,1,1,0 | 0 | 0,3,8,3,2,4,2,1 | 0,1,1,0,2,2,0,0 | 0,0,0,1,1,1,1,1 | v4:1 | 0 |
| schema | v1-v7 | 8/2/5, 1/2/2, 5/1/3, 1/2/2, 1/2/2, 1/2/2, 0/1/3 | 15 | v3:7, v4:2 | v6:1 | v4:1, v5:2 | 0,2,2,1,2,2,2 | v4-v7: 1,1,2,2 | 0 | v2:3 |
| match | v1-v7 | 4/0/6, 2/0/3, 4/1/1, 1/3/2, 1/0/1, 3/0/1, 0/0/2 | 10 | 0,5,1,3,1,1,1 | 0 | v3:3, v4:2, v6:2 | v4:1, v6:1, v7:1 | v3:1, v5:1 | v3:1 | 0 |
| vendor | v1-v6 | 26/10/4, 7/0/1, 3/0/2, 0/0/2, 0/3/3, 0/2/3 | 40 | v3:4, v4:1 | v2:7, v5:3 | v3:1, v5:1, v6:2 | v4:1, v5:2, v6:2 | v6:1 | 0 | v2:1 |
| district | v1-v5 | 11/5/4, 0/0/3, 0/0/1, 4/3/1, 0/2/2 | 20 | v3:1, v5:1 | v2:2, v4:5 | v5:2 | v5:1 | v4:3 | 0 | v2:1 |
| cohort | v1-v5 | 6/3/0, 0/0/0, 4/2/0, 2/3/0, 1/2/1 | 9 | v4:2 | v3:4 | 0 | v4:3, v5:3 | v3:2, v5:1 | 0 | 0 |

The full per-row table is printed by `_work/stats.py`.

## 2. FIX_CAUSED attribution (67)

- **Prompt told the session to do it: at least 22.** In sentinel, 6 of the 8 direct cases were prompt-asked. In 8 of 9 sentinel prompt-asked cases (direct plus latent), the prompt line copies the previous QC report's own `Fix:` text. Examples:
  - `20261027T1217_fix.md:15` "Move the `rebuild_config(\"shipped\")...` assert ... into the config criterion" led to v7 TS-13.
  - `20261027T1217_fix.md:20` "drop R6 and move its 3 points to R7-R9" led to R7-R9 going from 3 to 5 each and to v7 JD-15. The weight rule W2 {1,3,5} forced +2 per criterion, so the judge total went from 40 to 41 although the prompt said "Judge positive total unchanged".
  - `P12_r1.md:28` (rerun check "FIRST require ... reference") led to v2 TS-26.
  - `P12_r1.md:33` (state the row version) led to v2 AL-27.
  - `20261027T1030_fix.md:16` ("under /app/tool and inside /app/out/tool.zip") led to v6 TS-7.
- **Session's own choice or side effect: 45.** 21 of these are consistency findings: the cited TRUTH, description or timeout text was unchanged, but tests/ or solution/ changed under it (DS-22, AL-18, AL-19, TS-24, TS-14). 13 have no copy to diff.
- **45 of the 67 have a rule id that a "re-check every touched rule" pass would test.** The set used was TS-13/14/16/19/20/23/25/26, JD-2/5/6/7/9/15, DS-22/27, AL-18/19/27/28, CL-2/4.

Edit patterns behind FIX_CAUSED in the diffed rounds:

| pattern | n |
|---|---|
| docs left stale after code edits | 21 |
| doc/spec sentence edited | 11 |
| weight change | 9 |
| added or split check | 5 |
| removed or merged check | 4 |
| criterion reworded | 4 |
| other code/data edit | 4 |
| assert added or moved | 3 |
| renumbered | 3 |

The worst single pattern is regenerating tests from a generator: dispatch v3, 8 findings including 6 fails.

Correction to the master's example: sentinel v7 CL-2 (R10 vacuous) was not caused by "the v5 fix relabelling R10". Two edits caused it:
1. `20261027T0717_fix.md:16` F2 (the fix after QC v4) deleted R11's missing-input clause, the only non-vacuous half.
2. `20261027T1217_fix.md:17` F2 added `/app/tool/cli.py` to the artifacts, so the judge started paying the vacuous criterion.

The v5 fix relabel touched only the `type` field.

## 3. Recurring rules and conflicts

**Top 10 rules by task-rounds:**

| rule | task-rounds |
|---|---|
| DS-22 | 20 |
| AL-27 | 18 |
| TS-13 | 17 |
| JD-5 | 15 |
| TS-23 | 14 |
| TS-16 | 12 |
| IN-16 | 11 |
| DS-27 | 10 |
| TS-19 | 10 |
| JD-15 | 10 |

DS-20 and JD-7 tie JD-15 at 10.

**Rules that recur 3 or more times in one task:**

| task | rule | rounds |
|---|---|---|
| sentinel | TS-13 | 7 |
| emberforge | JD-16 | 7 |
| dispatch | TS-16 | 6 |
| dispatch | STEP11 | 6 |
| district | AL-27 | 6 |
| sentinel | JD-15 | 5 |
| emberforge | AL-27 | 5 |
| schema | TS-13 | 5 |
| schema | TS-23 | 5 |
| match | A3 | 5 |
| vendor | TS-16 | 5 |

**Conflicting pairs:**
- **TS-13/TS-20/CL-4 (split) vs A3/TS-23 (cap 35).** 27 post-v1 findings sit on the split side and 22 TS-23/A3 findings on the cap side. Only 3 cap findings were RULE_CONFLICT (sentinel v7, dispatch v4, match v3) and 3 FIX_CAUSED (dispatch v5, match v2, v4).
  - The sentinel shipped check was flagged TS-13/TS-20 in v1-v6. Severity on unchanged weights went fail, minor, pass (v3), minor, minor, fail.
  - It was kept because the split failed our own trap-survival and G3 rules (`p12_r1/RECHECK_FIX.md:5,:35-36`). It was then split in `1217_fix` F1, which took the count from 35 to 39 and drew v7 TS-23. The QC v7 Fix says "merge ... so the count is 35", which contradicts `QC_FIX_PLAYBOOK_v2.md:41` and feedback.jsonl 2026-10-24 12:52 "There is NO cap".
- **JD-5 (split a compound criterion) vs JD-7/JD-9/JD-15/IN-8.** In sentinel the handler criterion went JD-2 (v2), then negative -1 (v3), then IN-8 + JD-5 (v4), then a clause was dropped (v5), then CL-2 vacuous (v7).
- **CL-2 (rerun pays constant output) vs TS-26 (double payment).** Sentinel v1 CL-2 fix led to v2 TS-26, whose fix led to v3 TS-14.

## 4. Reviewer variance

- **Lines unchanged and flagged late (MISSED_EARLIER): 67.** 56 of them are in round 3 or later (22 fails). Sentinel examples:
  - v6 DS-27 on TRUTH "re-embedding", present since v1 (8e66159 TRUTH.md:167).
  - v6 JD-6 and AL-28 on judge lines unchanged since the v4 rebuild.
  - v7 DS-22 on TRUTH.md:52, unchanged since v4.
  - v7 IN-L2 on a sentence created in v3.
- **Kept items re-flagged (REFLAG_KEPT): 50, of which 15 are fails.** Sentinel's TS-13 KEEP was re-counted every round: in v2-v3 with the Ayush "option a" defence (`p12_r2/RECHECK_FIX.md:18`), and in v5-v6 with `0717_fix.md:20` and `1030_fix.md:19`. Severity rose from minor to fail on unchanged bytes (v6 TS-20).
- **QC_RULINGS and playbook rows QC ignored:**
  - TS-23 "no cap" (`QC_FIX_PLAYBOOK_v2.md:41`, `QC_RULINGS.md:137`): QC v7 sentinel told us to merge.
  - TS-13 KEEP defences (`QC_RULINGS.md:45-54`).
  - The NOISE row (`QC_FIX_PLAYBOOK_v2.md:58`).
  - No P11 prompt passes the kept list or QC_DEFENCE to the reviewer. This was already noted in `master_chat_work/20261024_process/qc_reverse/B/SUMMARY.md`, and the issued `*_qc.md` prompts still do not do it.
- **Internal contradiction in our playbook:** `QC_FIX_PLAYBOOK_v2.md:57` (NEW-CHECK) still lists "TS-23 count <= 35" while :41 says there is no cap.

## 5. Difficulty impact ("is QC making it easy?")

Scores are final / tests / judge, from `MASTER_RUN_LEDGER.md` and reward-details.json.

| task | attempts around QC fix rounds | changes by fix round | verdict |
|---|---|---|---|
| sentinel | A2-4 after P12 r1-r3: 71.62/100/43.24, 68.92/100/37.84, 70.0/100/40.0. A5-6 after hardens: 65.59/96.18/35.0, 45.56/78.63/12.5. A7 after the v4-v6 fixes: 50.1/80.69/19.51 | P12 r1-r2: HARDER (row-version fixture, resolution_order assert), except removing the rerun loop was EASIER (trap L7 ratio 0.889). 0717: judge EASIER (R11 left vacuous). 1217: tests EASIER (shipped split 1 to 15 of 145 points), judge EASIER (R10 pays an idle agent 5/41) | **Partly.** A7 failed exactly A6's 6 checks (28 points). On the pre-fix weights A7 scores 42.97, so the QC fixes added +7.1 pp final for the same behaviour (+1.03 from tests, +6.1 from judge R10). The difficulty itself comes from the hardens |
| emberforge | A7 (after v7) 27.31/29.63/25.0, A8 (after v9) 59.91/94.83/25.0 | v7 to v9 fixes restored the I3 tiebreak sentence that harden_lp1 had deleted (`20261024T1142_fix.md` directions 1-2). P14 measured that ambiguity at 18/54 of A7's test loss (`p14_a7/A_*.md:7`). v8: a judge criterion moved into tests at w1 (`program_names_missing_input`), slightly EASIER. v9: added the `quiet_rules` AL-27 check, HARDER | **Yes for tests, by design:** +65 pp tests, of which about 33 pp is the restored sentence. The rest is the A8 agent's own run (not attributable). Check set and weights otherwise unchanged (`_work/difficulty_deltas.tsv`) |
| dispatch | A2 (after v4) 76.52/67.33/85.71, A4 (after v8) 14.7/35.64/-6.25 | v5-v8: judge positive weight 21 to 16, test positive 101 unchanged, tests regenerated in v6 to v7 | **No:** harder, -32 pp tests, -62 pp final |
| schema | A3 (about v1) 84.44/99.3/69.57, A4 (after v7) 46.16/100/-7.69 | v5 to v6 harden: 46 to 63 checks, positive 137 to 201. Judge 10 to 8 criteria | **No:** tests at ceiling throughout, judge harsher |
| match | probe after v2 46.88 tests / 17.65 judge / 32.27 final; A3 after v7 43.42/69.19/17.65 | `1341_fix.md:30` DS-21 writes the fragment grammar into calibration.md: EASIER. `1732_fix.md:37` CL-4 keeps trap corpora under the allowance: EASIER for partial solvers. `2231_fix.md:35` CL-4 cliff: EASIER. IN-16 settling sentences (`2059_fix.md:37`, `1621_fix.md:25`): EASIER. IN-17 deletions (`1621_fix.md:29-34`): HARDER. Test positive 158 to 172 | **Yes:** +22.3 pp tests, +11.2 pp final. Mostly from the CL-4 partition and the DS-21 grammar sentence |
| vendor | A2 (after v4) 100/100/100, A3 (after v6) 71.88/100/43.75 | v6: 58 test lines changed, no weight change | **No measurable change.** A1 4.83 tests predates the QC-triggered P4 rebuild (no copy, UNVERIFIED) |
| district | A4 (after v3) 100/100/100, A5 (after v5) 81.25/100/62.5 | v5: judge +1 criterion | **No:** tests at 100 either way |
| cohort | A2 (after v2) 100/100/100; no run after v3-v5 | not measurable | **Unknown** |

## 6. Rounds to pass, and self-caused findings

"Self-caused" counts findings with origin FIX_CAUSED, HARDEN_CAUSED or RULE_CONFLICT introduced by the edit just before that round.

| task | QC rounds | first 0-fail round | end state | self-caused per round (v2..vN) |
|---|---|---|---|---|
| sentinel | 7 | none | FAIL 1/4/1 | 3,2,6,0,1,3 (+6 latent) |
| emberforge | 9 | v5 | MINOR v9 | 5,1,3,0,4,1,3,1 |
| dispatch | 8 | v4 | MINOR v8 | 3,8,3,5,1,1,0 |
| schema | 7 | v7 | MINOR v7 | 0,7,2,0,1,0 |
| match | 7 | v7 | WARN v7 | 5,2,3,1,1,1 |
| vendor | 6 | v4 | MINOR v6 | 7,4,1,3,0 |
| district | 5 | v2 | MINOR v5 | 2,1,5,1 |
| cohort | 5 | v2 | FAIL v5 | 0,4,2,0 |

82 findings (33 fails) came in rounds after a task's first 0-fail round: dispatch 24, emberforge 19, cohort 15, district 13, vendor 11.

## Verdicts

- **H1 (master fix prompts cause new findings): CONFIRMED, not dominant.** FIX_CAUSED is 67/255 = 26.3% of post-v1 findings and 33 of 100 post-v1 fails, the largest single source of fails. At least 22 were directed by the prompt, and those prompts usually copy QC's own Fix text. Sentinel v7 TS-13 and JD-15 are confirmed. v7 CL-2 is confirmed but traces to the v4 fix (0717 F2) plus the v6 fix (1217 F2), not the v5 relabel.
- **H2 (split vs cap conflict): PARTLY.** The conflict is real: 27 split-side and 22 cap-side findings. But only 3 findings are a direct RULE_CONFLICT. The live ping-pong is QC's TS-23 Fix text against our no-cap ruling.
- **H3 (fresh reviewer re-flags old lines and kept items): CONFIRMED.** 142/255 = 55.7% of post-v1 findings are unchanged-line or re-flag findings (125 of 207 in round 3 or later). That includes 50 kept items re-counted (15 fails), and severity changes on identical bytes.
- **H4 (tests not easier, judge slightly easier): CONFIRMED for sentinel, PARTLY overall.** Sentinel tests +2.06 pp from the shipped split and judge +12.2 pp (5 of 8 A7 judge points from vacuous R10), +7.1 pp final in total. Elsewhere, fixes made tests easier on match (+22 pp) and emberforge (+33 pp from the restored sentence, intended), and harder on dispatch (-32 pp).
