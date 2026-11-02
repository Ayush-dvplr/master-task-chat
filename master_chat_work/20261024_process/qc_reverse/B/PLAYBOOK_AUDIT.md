# PLAYBOOK_AUDIT: QC_FIX_PLAYBOOK.md rows against what happened next

Board ef7d851. Source: `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md` (v1 ACTIVE, :3 "23 Oct 2026 11:05 IST").
"Playbook era" means rounds whose fix records cite playbook rows: every 20261023 `RECHECK_FIX.md`, plus
20261022 dispatch `p12_r3/RECHECK_FIX.md` (its rows carry `row TS-24` etc). Paths below are under `master_chat_work/`.
When a fix record has no row column (cohort p12_r2/r3, district p12_r2, vendor p12_r3), the row is taken from
the finding id: **UNVERIFIED**. "Came back" uses `next_round_status` in `OUT/fires.json`. "Side effect" uses `OUT/cascades.json`.
Lever evidence comes from the trap-survival tables in the same RECHECK_FIX files.

Verdicts: **WORKS** = the finding cleared, no new finding, levers kept. **LEAKS** = the finding came back, was re-counted, or
drifted again. **BACKFIRES** = the fix produced a new finding (cascade), or a lever lost >10%. **UNTESTED** = no playbook-era use, or no QC after it.

| Row (playbook line, DO quote) | Applied | Came back | Side effect / lever loss (evidence) | Verdict |
|---|---|---|---|---|
| IN-15 (:27 state once in governing file) | 0 | - | the dispatch IN-15 regen chain (6 new fails) is pre-playbook: 20261022 dispatch p12_r3/RECHECK_FIX.md:108 "P12 r2 regenerated that file from stale `WORK/build/mktests.py`, overwriting both fixes" | UNTESTED |
| IN-16 (:28 "one settling clause in the governing file") | 4: cohort p12_r3:19, match p12_r1:18, schema p12_r4:9, sentinel p12_r1:19 | 0 of 4 | sentinel: the clause made a new half nothing triggers. QC/reports/sentinel-policy-recompute/v2.md:415 "override_precedence.conf:4 now names both; the row half is untriggered, see new AL-27 ❌" | BACKFIRES 1/4 |
| AL-2/CL-1 (:29 "grade it through an observable the program writes") | 9: dispatch p12_r3:17,:24; cohort p12_r2:13; emberforge p12_r4:11,:14; match p12_r1:14,:15,:16,:23 | 0 of 9 | emberforge v7 TS-25 ❌ (v7.md:428 "the stdlib check added to fix v6 AL-2 is a positive that pays for an absence"); match redraw led to DS-21 escalated ❌ (v2.md:433 "raised to ❌ F1") | BACKFIRES 2/9 |
| AL-27 (:30 "Add hidden reseeded rows that construct the case") | 11: cohort p12_r2:14, p12_r3:12-18; district p12_r2:15; emberforge p12_r4:13; sensor p12_r2:10 | cohort recurred v3->v4->v5 (different untriggered rules each round); district downgraded | cohort p12_r3:71 "First try failed L1a (11 -> 6, ratio 0.55)", compensated; cohort parked (state.json:132 "AL-27 loop, 3 rounds") | LEAKS |
| AL-28 (:31 one layer per act) | 0 | - | - | UNTESTED |
| TS-26/JD-14 (:32 "narrow the wording of one ... or merge into one at the larger weight") | 2: district p12_r2:12 (fixed); sentinel p12_r2:17 F2 | sentinel TS-26 re-raised and escalated in v3 | sentinel p12_r2/RECHECK_FIX.md:66 "sum rounding (L7) / 0.2903 / 0.2581 / 0.889 / y / FAIL"; v3 TS-14 came from the new assertions | BACKFIRES |
| TS-13 (:33 "Split into two checks ... re-run TS-25 on both halves.") | FIX 3 (schema p12_r4:11, p12_r5:12, p12_r5:13); KEEP 5; PAUSED 1 | schema TS-13 recurred v5->v6->v7; all 5 KEEPs re-counted | schema v6 TS-15 came from the split (p12_r4:11 "archive layout positive +1 and unsafe-member detection negative -1"); schema p12_r5:23 "TS-13 conditional fix reverted by its own condition (reflex gate)"; sentinel p12_r1:33 "reflex 11/38 = 0.2895 (FAIL, gate 0.20)"; sensor p12_r2:26 "live W2 rejected 2-point weights" | BACKFIRES |
| TS-23 (:34 "or KEEP as a warn with the count and the kit line 03:62") | 4 KEEP: district p12_r2:19, match p12_r1:20, schema p12_r4:12, p12_r5:14 | 4 of 4 re-counted (schema v7.md:440 "still 63 checks against the 35 cap") | none; the warn never clears | LEAKS (harmless; KEEP is a standing warn) |
| TS-20 (:35 raise core check) | DO never applied; sentinel PAUSED p12_r1:14 then KEEP p12_r2:19 | KEEP accepted: sentinel v3.md:468 "v3 re-judged it ✅" | - | UNTESTED (DO); KEEP held |
| TS-16 (:36 "Narrow the trigger to the cheat only") | 5: dispatch p12_r3:13,:21,:22,:25; vendor p12_r3:14 | vendor fixed | dispatch: the runtime audit hook gave v4 TS-14, TS-15, AL-28 and the v5 TS-16 escalation (v5.md:380 "stdlib `statistics`/`pprint` import trips negative_writes_outside_output_dir") | BACKFIRES (dispatch) |
| TS-19 (:37 "Add the grader and a generated case") | 7: dispatch p12_r3:15,:20; match p12_r1:22; sentinel p12_r1:16,:25,:26, p12_r2:26 | match moved | sentinel v2 TS-26 ❌ (v2.md:420 "closed by adding hidden-a reference equality to the rerun check; that change is what v2 TS-26 ❌ flags"); sentinel v3 TS-14; dispatch v4 TS-23 (36 checks) | BACKFIRES |
| TS-25 (:38 replace with assertion on earned output) | 1: emberforge p12_r5:10 | no QC after | p12_r5:73 "trap losses stay at ratio 1.00" | UNTESTED |
| JD-7 (:39 "Fix the oracle (and TRUTH.md)") | 5: cohort p12_r2:11; emberforge p12_r4:9,:12, p12_r5:12; match p12_r1:17 (DO not used) | 0 when DO used | match dropped the clause instead: p12_r1:17 "JD-7 (DO fix oracle for good practice) not used: master chose to drop the clauses under JD-5", giving v2 JD-15 ❌ | WORKS (when followed) |
| DS-22 (:40 rewrite TRUTH) | 9: cohort p12_r2:12, p12_r3:11; district p12_r2:16; schema p12_r4:10, p12_r5:11; sensor p12_r2:12, p12_r3:10; sentinel p12_r1:20, p12_r2:27 | cohort recurred, schema re-staled by the later harden (v6.md:386 "TRUTH.md:149 'installing a package (-3)' vs judge.toml R7 `weight = -1`") | TRUTH drifts after every later test/judge edit | LEAKS |
| DS-20 (:41 fix oracle) | 2 FIX (emberforge p12_r4:7, sentinel p12_r1:21) + 1 KEEP (vendor p12_r3:15) | FIX 0 of 2; KEEP re-counted (vendor v6.md:400 "STILL OPEN") | - | WORKS |
| JD-15/JD-16 (:42 re-label / reword a preference at w1/w3) | 12 (dispatch p12_r3:23; district p12_r2:13,:17,:18; emberforge p12_r4:10, p12_r5:11; sensor p12_r2:9; sentinel p12_r1:17, p12_r2:21,:23,:24; vendor p12_r3:13) | sentinel JD-9 recurred | dispatch v4 JD-5 (v4.md:414 "added with the COV-4 fix"); sentinel v3 JD-7 (M4 rewording of R5 the oracle does not meet) | BACKFIRES 2/12 |
| JD-18 (:43 "Add one named-shape criterion (J4) ... confirm the oracle meets it (JD-7)") | 5: district p12_r2:14; emberforge p12_r5:12; sensor p12_r2:14, p12_r3:9; sentinel p12_r2:23 | - | sensor: the JD-5 rewrite of R5 under row JD-18 made IN-8 ❌ (sensor p12_r3:72 "Error-message wording keeps turning into a hidden contract rule (IN-8)") | BACKFIRES 1/5 |
| DS-4 (:44 remove signal) | 1: vendor p12_r3:12 | fixed | - | WORKS |
| DS-6 (:45 fix names/units else KEEP) | 2 KEEP | sensor accepted (v2.md:401); vendor re-counted (v6.md:402) | - | mixed |
| SUGGEST (:46 KEEP) | 6: match p12_r1:19; schema p12_r5:13,:15; sentinel p12_r1:23, p12_r2:22,:28 | 2 escalated (match DS-21, sentinel TS-26), 1 re-counted, 2 accepted | - | LEAKS |
| row NEW (:48) | 4: emberforge p12_r4:8; sentinel p12_r1:24, p12_r2:20,:25 | 0 | sentinel's new R3 text drew v3 JD-11 ⚠️ (v3.md:39 "R3 (-3) penalises changing /app/data, which uid 1000 cannot do") | WORKS mostly |

## Findings about the playbook itself

1. **No row predicts its own side effect.** 30 fix-induced chains are in cascades.json. Only 3 were anticipated by any row, and those rows were written later (`OUT/FIX_SIDE_EFFECTS.md`): JD-18 :43 "confirm the oracle meets it (JD-7)" (x2) and TS-13 :33 "re-run TS-25 on both halves" (x1). No playbook-era fix had its cascade predicted by the row it used.
2. **Missing rows for the ids we actually produced.** There is no JD-5 row, yet JD-5 is the most dangerous fix (8 fixed, 5 produced a new finding: match JD-15, schema JD-2, sentinel JD-9, sentinel JD-7, sensor IN-8). See match p12_r1:107 "a JD-5 row for dropping extra clauses would help". There are also no rows for IN-8, DS-27, DS-18, TS-14, TS-15, TS-17, TS-24, JD-9 or JD-11, which together account for 14 produced findings.
3. **Rows that add assertions or checks backfire through Gate 03.** TS-19, TS-16 and TS-13 add assertions or checks. Their new checks then fire TS-14 (descriptions stale), TS-15 (no inversion comment), TS-23 (count), TS-25 (pays for absence) and TS-26 (double pay). Each such row should end with "re-run TS-14/TS-15/TS-23/TS-25/TS-26 on the new check".
4. **Rows that edit judge text backfire through JD-7 and IN-8.** JD-5 and JD-15/16 rewording changes what the oracle must meet (sentinel v3 JD-7, sensor IN-8). Row :43's "confirm the oracle meets it" belongs on every judge-text row.
5. **KEEP rows never clear a count.** TS-23 (4/4) and TS-13 (5/5) KEEPs were re-counted every round (`OUT/DEFENCES.md`). A KEEP saves the levers but does not shorten the loop.
6. **Lever gate vs QC fix conflict.** TS-13 splits were blocked by the reflex gate 3 times: schema p12_r5:23, sentinel p12_r1:33, sensor p12_r2:26. The sentinel TS-26 fix lost L7 (0.889). The playbook gives no fallback beyond "max 2 tries, then PAUSED" (:58-63).

Loop accounting per task: see `OUT/LOOPS.md`.
