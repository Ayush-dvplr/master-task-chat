# DEFENCES: did our KEEP / REBUT / FALSE_POSITIVE / PAUSED hold at the next QC?

Board ef7d851. Sources: every KEEP/REBUT/PAUSED decision row in `master_chat_work/<date>_<slug>/p12_r*/RECHECK_FIX.md` (extracted to scratch `pbrows.json`), the matching fix directions in `master_chat_tasks/prompts/issued/<slug>/P12_r*.md`, PL_NOTE.md, and `master_chat_work/bundles/_work/<slug>/QC_DEFENCE.md`. The outcome is read from the next report's "Compared with" section. Paths below: `RF` = `master_chat_work/<date>_<slug>/<round>/RECHECK_FIX.md`; reports = `QC/reports/<slug>/vN.md`.

Outcome labels:
- **HELD**: the next QC dropped it, or carried it with no count (= `kept-accepted` in fires.json).
- **TOLERATED**: the next QC counted it again at the same severity, no argument with our reason (= `kept-rejected` in fires.json; the defence did not remove the count).
- **REJECTED**: the next QC raised it, or said our label was wrong.
- **PAUSED**: fixer stopped on the trap gate; finding left.

## Totals

| Outcome | Count | Share |
|---|---|---|
| HELD | 12 | 30% |
| TOLERATED (re-counted) | 21 | 52% |
| REJECTED (raised / label called wrong) | 6 (+3 emberforge JD-16 KEEPs later escalated by a harden) | 15% |
| PAUSED | 2 | 5% |

Roughly 40 defence decisions; only 3 in 10 removed the finding from the count. No defence of a check-count warn (TS-23) or an omnibus check (TS-13) was ever accepted.

## Defences that HELD

| Task | Round | Id | Our wording (source) | Next QC reply | Why it held |
|---|---|---|---|---|---|
| dispatch | v1->v2 | X1 | W9 X1 FALSE_POSITIVE keep (RF 20261022 dispatch p12_r1:17) | v2.md:393 "informational (not counted in v2)" | reviewer could verify: binaries skipped, no dash in text files |
| dispatch | v3->v4 | EXEC-5 / Step 10 | P12_r3.md:34 "`EXEC-5 warn \| KEEP \| row none \| Ayush rule: oracle x3 per round, the kit's x5 runs once before sign-off`" | v4.md:409 "this round again ran x3 per Ayush; carried as ⏸️ in the sign-off, not counted as a finding" | process rule, reviewer chose not to count (same rule counted in v3, see REJECTED) |
| dispatch | v4->v5 | X1 | P12_r3.md:33 "scanner limitation; QC extracted the five binaries by hand and found no prohibited dash" | v5.md:372 "not counted as a bundle finding in v5" | verifiable claim |
| emberforge | v2->v3 | W-01-1 IN-L3 | REBUT (RF 20261022 emberforge p12_r1:14) | v3.md:400 "text unchanged; v3 gate 01 did not raise it (IN-L3 read as acceptable labelling)" | labelling argument |
| emberforge | v2->v3 | TS-19 (visible-season records) | KEEP (RF 20261022 emberforge p12_r1:12) | v3.md:401 "unchanged; not re-raised in v3, since the hidden seasons grade the settlement and the visible figures go through judge R1-R5, R12" | reason named the layer that already grades it |
| emberforge | v2->v3 | JD-16 (R10 network) | KEEP (p12_r1:17) | v3.md:402 "unchanged; not re-raised, since a test cannot observe an attempted connection without grading source tokens (TS-27)" | held one round only: v4.md:35 re-raised JD-16 on the same R10 text (tests/judge.toml:131) |
| emberforge | v3->v4 | JD-16 (R9 /app/data writes) | KEEP (RF 20261022 emberforge p12_r2:11) | v4.md:373 "the bundle is unchanged on this point ... v4 did not re-raise it because /app/data is not a declared artifact" | reviewer re-derived it |
| sensor | v1->v2 | DS-6 | PL_NOTE (20261023 sensor p12_r2/PL_NOTE.md:5) "DS-6 minor kept: changing the table's header or centres would signal the acceptance-row lever." | v2.md:401 "This round I judged it a declared data convention ... so DS-6 ✅" | reviewer re-judged; note it accepted "data convention", not "lever reveal" |
| sentinel | v1->v2 | JD-16 | KEEP SUGGEST (RF 20261023 sentinel p12_r1:23) | v2.md:421 "closed on re-judgement, the verifier receives only the seven declared artifacts so the judged layer owns R4 (JD-16.4)" | layer-ownership argument |
| sentinel | v2->v3 | M2 TS-20 | KEEP (RF sentinel p12_r2:19; QC_DEFENCE.md:93-101 "RULED (Ayush, 23 Oct 19:45, option a)") | v3.md:468 "bundle weights unchanged (test_output.py:779-790); v3 re-judged it ✅ because hidden config values are paid at 5" | reviewer recomputed weights |
| sentinel | v2->v3 | W13 X1 | KEEP (p12_r2:28; QC_DEFENCE.md:181-182 "Binary-skip warning on tool.zip / parquet; KEEP, no text file carries a dash.") | v3.md:467 "records no finding" | verifiable claim |
| vendor | v5->v6 | X1 | KEEP (RF 20261023 vendor p12_r3:17) | v6.md:405 "verified false positive with no count" | verifiable claim |

## Defences TOLERATED (re-counted at the same severity)

| Task | Rounds | Id | Our wording (source) | Next QC reply |
|---|---|---|---|---|
| schema | v2..v7 (5 KEEPs) | TS-23 | P12_r4.md:27 "46 checks (49 after TS-13) is above the 35 warn and under the 70 cap (kit 03:62); merging checks would undo TS-13"; P12_r5.md:27 "Ayush approved (23 Oct 18:20 ...)"; KEEP rows RF p12_r1:15, r2:16, r3:13, r4:12, r5:14 | v7.md:440 "A3 / TS-23 ⚠️: still 63 checks against the 35 cap." |
| district | v4->v5 | TS-23 | KEEP (RF 20261023 district p12_r2:19); lesson p12_r2:48 "Count WARNs above 35 checks are KEEP when the fold would break TS-13." | v5.md:415 "TS-23 / tests_qc A3 (38 checks, cap 35): STILL OPEN" |
| match | v1->v2 | TS-23 | P12_r1.md:35 "Ayush approves the count over 35; no folding (folding would make omnibus checks, TS-13)" (RF p12_r1:20) | v2.md:433 "still open as W1 (41 then, 42 now)." |
| schema | v6->v7 | TS-13 | KEEP after revert (RF p12_r5:12, :23 "TS-13 conditional fix reverted by its own condition (reflex gate)"; QC_DEFENCE.md:156) | v7.md:439 "still asserts receipt mismatches and null fingerprints together. (My first v7 pass missed it ...)" |
| schema | v6->v7 | TS-15 | P12_r5.md:28 "polarity is correct; Ayush accepted it as-is (23 Oct 18:20). Do not edit"; PL_NOTE p12_r5:10 | v7.md:441 "still has no inline inversion comment. (My first v7 pass missed it; corrected in Gate 03.)" |
| cohort | v3->v4, v4->v5 | TS-13 | KEEP (RF 20261023 cohort p12_r2:15 "fixing it would pay 6/71 format and rerun credit to programs that get no cohort right"; p12_r3:21) | v4.md:448 "TS-13 ... STILL OPEN"; v4.md:459 "TS-29 and TS-13 have now been open for two rounds; fix them or record that they are accepted as minors." |
| cohort | v4->v5 | TS-29 | KEEP (p12_r3:20) | carried as minor in v5 |
| sensor | v1->v2 | TS-13 | KEEP (RF 20261023 sensor p12_r2:13; :26 "TS-13 attempted split ... live W2 rejected 2-point weights") | v2.md:399 "`_check_reports` still asserts normal_matrix_trace.json ... so one trace slip costs 9/62." |
| sensor | v1->v2 | X1 | KEEP (p12_r2:15) | counted as warn again in v2 |
| sentinel | v2->v3 | M1 TS-13 | KEEP (p12_r2:18; QC_DEFENCE.md ruling 23 Oct 19:45) | v3.md:464 "TS-13 🟡 omnibus `shipped_artifacts_follow_field_specs` (test_output.py:624-671), unchanged." |
| vendor | v3->v4 | TS-16 | KEEP (RF 20261022 vendor p12_r2:9) | v4.md:452 "still present, carried as ⚠️ TS-16." |
| vendor | v5->v6 | DS-20-1 | KEEP (RF vendor p12_r3:15) | v6.md:400 "STILL OPEN ... My first v6 pass missed it; re-opened and counted in v6." |
| vendor | v5->v6 | DS-6-1 | KEEP cosmetic (p12_r3:16) | v6.md:402 "STILL OPEN ... My first v6 pass missed it" |
| emberforge | v4->v5 | JD-16 (R10 network) | KEEP (RF 20261022 emberforge p12_r3:12) | v5.md:377 "⚠️ carried. I passed it in my first gate 04 pass and revised it to warn after re-reading 04_Judge_QC.md:97" |
| dispatch | v3->v4 | X1 | KEEP (RF dispatch p12_r3:26) | v4 counted (status kept-rejected), then v5 uncounted |

(fires.json carries the full 21 `kept-rejected` rows.)

## Defences REJECTED

| Task | Round | Id | Our wording (source) | Next QC reply |
|---|---|---|---|---|
| dispatch | v2->v3 | TS-19 (F7) | FALSE_POSITIVE: shipped artifacts existence-only is enough (RF 20261022 dispatch p12_r2:18; QC_DEFENCE.md:31 "## Only one shipped-run check") | v3.md:895 "The v2 existence-only warning remains and is now a strict coverage fail, COV-5 / AL-2"; our own next fixer: p12_r3:24 "so p12 r2 F7's FALSE_POSITIVE label was wrong" |
| dispatch | v2->v3 | X1 | KEEP (p12_r2:21) | v3.md:894 "\| Still open \| X1 \| ... automated coverage still warns. \|" (counted; v2 had not counted it) |
| dispatch | v2->v3 | Step 10 x5 | KEEP (p12_r2:19) | v3.md:896 "Both rounds ran oracle x3 by Ayush's authorization; the kit still requires an x5 round" (EXEC-5 counted) |
| sentinel | v2->v3 | W7 TS-26 | KEEP SUGGEST (RF sentinel p12_r2:22 "isolating init/set would hand 5 points to a solver with a wrong resolve") | v3.md:465 "unchanged in the bundle ... v3 grades it ❌ because the measured mutants m2/m3 lose the same resolved values twice (5 + 5)" |
| match | v1->v2 | W-02 DS-21/IN-9 | "No change. Question in PL_NOTE" (RF 20261023 match p12_r1:19); direction P12_r1.md:34 "KEEP and write the defence" | v2.md:433 "still open and raised to ❌ F1, because with per-seed quantity redraws ... the grammar now gates 100 of 158 positive points" (our own F-04/CL-3 redraw raised the stakes) |
| emberforge | v2..v5 | JD-16 | three KEEPs (p12_r1:17, p12_r2:11, p12_r3:12) | after harden_lp1_r1, v6 counted JD-16 as ❌ (cascades.json harden-induced row); the KEEP reason did not travel into the new tree |

## Defences PAUSED

| Task | Round | Id | Source | Next QC |
|---|---|---|---|---|
| sentinel | v1->v2 | G03-1 TS-20 | RF 20261023 sentinel p12_r1:14 PAUSED; :33 "reflex 11/38 = 0.2895 (FAIL, gate 0.20)"; :90 "(isolated + shipped) / P <= 0.20 caps total shipped weight at about 3.75" | downgraded ❌ -> 🟡 in v2, then HELD in v3 (v3.md:468) |
| sentinel | v1->v2 | G03-3 TS-13 | p12_r1:15 PAUSED | re-counted 🟡 v2 and v3 |

## Which wording held and which did not

Held:
1. **Claims the reviewer can check in one step**: "binary files skipped, checked by hand, no dash" (X1). This held 4 of 7 times. When it failed, the cause was the reviewer's counting habit, not the claim: X1 went counted/uncounted 6 times over 4 tasks (VARIANCE.md section C).
2. **"Another layer already grades this"**: emberforge v3.md:401 (hidden seasons + judge), sentinel v2.md:421 (judged layer owns R4), emberforge v4.md:373 (not a declared artifact). In each case the reviewer repeated the layer argument in its own words.
3. **Weight arithmetic the reviewer can redo**: sentinel TS-20 (v3.md:468 "hidden config values are paid at 5").

Did not hold:
1. **Authority**: "Ayush approved", "Ayush accepted it as-is", "Ayush rule: oracle x3". The reviewer never accepted a count because Ayush allowed it (schema TS-23 x5, schema TS-15, match TS-23, dispatch EXEC-5 in v3). The x3/x5 dispute closed only when the reviewer ran x5 itself (emberforge v7.md:423 "oracle x5 all 1.000").
2. **"Fixing it would reveal lever L"** (suggestion test, cohort P12_r2.md:38). The reviewer has no lever map, so it re-counts the item (cohort TS-13 x2, sensor TS-13, sentinel TS-13). sensor DS-6 is the one apparent exception, and there the reviewer accepted a different reason ("declared data convention", v2.md:401).
3. **FALSE_POSITIVE on a coverage gap**: dispatch F7 ("existence only") was escalated to a fail and later called wrong by our own fixer.
4. **KEEP on a warn whose stakes our next fix raised**: match DS-21 (our redraw) and sentinel TS-26 (the reviewer measured mutants). The KEEP reason was written before the fix and was not checked again after it.
5. **KEEPs do not survive a harden**: emberforge JD-16 held for 3 rounds, then the LP1 tree brought it back as a fail. Nothing in QC_DEFENCE.md carries a KEEP across a rebuild.

Process note: QC_DEFENCE.md files are mostly design defences (lever lists, design choices). They hold few per-finding KEEP lines (match :30/:36, schema :106/:156/:158/:159, sentinel :47/:93-101/:181-182). The reviewer is never shown them, so a KEEP reaches QC only through the bundle text itself or the next report's own re-judgement. Checked: `grep -l QC_DEFENCE QC/reports/*/v*.md` returns nothing, and `grep -n "QC_DEFENCE\|defence\|DEFENCE" master_chat_tasks/prompts/issued/*/P11_qc_r*.md` returns nothing. The QC prompts never hand the defences to the reviewer.
