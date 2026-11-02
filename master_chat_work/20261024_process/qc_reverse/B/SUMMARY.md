# SUMMARY: why QC rounds do not converge (board ef7d851)

I read 42 QC reports across 9 tasks and parsed 318 findings. The parsed fail/minor/warn counts match all 42 Verdict lines.
101 of those findings were new in their round. Details are in FIRE_TABLE.md, CASCADES.md, FIX_SIDE_EFFECTS.md, VARIANCE.md, DEFENCES.md, PLAYBOOK_AUDIT.md and LOOPS.md.

## Where new findings come from (101 new; cascades.json)
| Cause | n | share |
|---|---|---|
| reviewer-variance (cited text unchanged, or passed in the round before) | 38 | 38% |
| harden-induced (harden, rebuild or judge rework between rounds) | 32 | 32% |
| fix-induced (a P12 fix for X produced Y) | 28 | 28% |
| new-scope (the reviewer probed further) | 3 | 3% |
| kit-change | 0 | 0% (Gates 01-05 byte-identical bde868c4..71a653b2) |
60% of new findings came from our own edits, 38% from the reviewer judging the same bytes differently, and almost none from the kit.
There are also 3 escalations of defences we sent, where the text was unchanged: dispatch TS-19, sentinel TS-26 and dispatch TS-16.

## 10 checks that cost the most rounds (task-rounds with a fail or minor; by_check.json)
AL-27 16 · DS-22 15 · TS-13 14 · JD-5 14 · AL-2 8 · JD-7 8 · TS-19 7 · DS-27 7 · JD-15 7 · IN-16 6.
AL-27 and DS-22 recur because each fix adds a new rule or edit that is not yet triggered or documented. TS-13 recurs because every KEEP is re-counted (5/5) and splits hit the reflex gate.

## Top fix -> new-finding chains
1. **JD-5 rewording -> a new judge finding.** 8 fixed, 5 produced a new one: match JD-15 ❌, schema JD-2 ❌, sentinel JD-9 and JD-7, and sensor IN-8 ❌ (board: "caused by my P12 r2 JD-5 direction").
2. **Regenerating test_output.py from a stale generator.** Dispatch P12 r2 caused 6 new fails (DS-22 x2, TS-17, TS-24, AL-18, AL-19). 20261022 dispatch p12_r3/RECHECK_FIX.md:108 "regenerated that file from stale `WORK/build/mktests.py`, overwriting both fixes".
3. **New or split checks -> Gate 03 hygiene fires.** TS-19, TS-16, TS-13 and STEP11 fixes produced TS-14 x3, TS-15 x2, TS-23, TS-25 x3, TS-26 and AL-28. Example: emberforge v7.md:428 "the stdlib check added to fix v6 AL-2 is a positive that pays for an absence".
4. **Harden after PASS.** Cohort v2, district v2/v3, emberforge v5 and vendor v4 had passed. Hardening them added 9 more rounds and 19 harden-induced findings (LOOPS.md).
5. **Schema's serial chain.** DS-15 -> DS-18 -> DS-22, and AL-27 -> TS-13 -> TS-15 (schema v3-v6), so each fix opened the next round.

## Variance (VARIANCE.md)
17 pass->fire flips are proven by diff on unchanged bytes. Example: vendor TS-17 v5.md:287 passes it, v6.md:43 fails it.
There are 6 fire->pass reversals. X1 and STEP10 flipped between counted and uncounted 6 times over 4 tasks.
Reviewers also admit missing open items on their first pass: schema v7.md:439 and vendor v6.md:400 "My first v6 pass missed it".

## Defences (DEFENCES.md)
HELD 12, TOLERATED (re-counted) 21, REJECTED 9, PAUSED 2.
Defences held when the claim was verifiable or a matter of layer ownership. Authority claims ("Ayush approved"), lever-reveal reasons, count caps and omnibus KEEPs never held.
QC prompts never pass QC_DEFENCE to the reviewer: a grep of QC/reports and P11 prompts found nothing.

## Playbook rows that backfire (PLAYBOOK_AUDIT.md)
- BACKFIRES: IN-16, AL-2/CL-1, TS-26/JD-14, TS-13, TS-16, TS-19, JD-15/JD-16, JD-18.
- WORKS: JD-7 (when followed), DS-20, DS-4, row NEW.
- LEAKS: AL-27, DS-22, TS-23, SUGGEST.
None of the 30 fix-induced chains was predicted by the row actually used. There is no JD-5 row.

## Loops (LOOPS.md)
14 of the 42 rounds came after the point where stopping was right: first PASS, or the drop rule after 3 edit rounds.
That is cohort v3-v5, dispatch v5, district v3-v5, emberforge v6-v7, schema v5-v7 and vendor v5-v6.
19 of the 33 re-runs are OWN, meaning a new blocking finding came from our edit.

## Lessons for the master
1. Stop at the first PASS. Do not harden a passed bundle and re-QC it; that restarted the loop 4 times and cost 9 rounds.
2. Enforce the 3-edit-round drop rule. Schema, district and cohort each ran 3 rounds past it without converging.
3. Add a JD-5 row: "reword to one observable, then prove the oracle meets the new text (JD-7) and that the contract states it (IN-8)". Add the same oracle-proof step to every judge-text row.
4. Every row that adds or splits a check must end with "re-run TS-14/TS-15/TS-23/TS-25/TS-26 on the new check".
5. Diff the generator before any test regeneration (dispatch v3).
6. After every edit, re-sync TRUTH.md from the final tests and judge, since DS-22 and DS-27 come back after each edit.
7. Do not send authority, lever or count-cap KEEPs in place of fixes; the reviewer re-counts them every round. Either hand QC_DEFENCE to the reviewer or accept the warn as standing.
8. Treat about 38% of new findings as reviewer noise. Before fixing a new finding, diff the cited lines against the previous copy. If they are unchanged and passed last round, KEEP with that diff as the evidence instead of editing.
9. Keep QC copies for every round. Pruning removed 15 of the 42, which leaves the causes for cohort v1-4, district v1-4, emberforge v1-4, schema v1-3 and vendor v1-5 UNVERIFIED by diff.
