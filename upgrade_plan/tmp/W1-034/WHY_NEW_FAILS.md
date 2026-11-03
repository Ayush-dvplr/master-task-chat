WHY NEW DESIGNS FAIL OR STALL (W1-034, 3 Nov 2026)

Scope: every task Ayush started as a new design (registry pipeline kind "new", plus the three first builds of 19 to 21 Oct that predate the kind field), the two lever pilots of 1 Nov, and the idea supply events. Converted and intake tasks are used only where a record speaks about design (match-replay). Read only; nothing here was rerun.

Path keys used in the file:line column:
D = master_chat_tasks/decisions.jsonl
L = master_chat_tasks/lessons.jsonl
T = master_chat_tasks/registry/tasks.json
I = master_chat_tasks/registry/ideas.jsonl
FP = master_chat_work/20261102_test_design_study/FIX_PLAN.md

Kinds of failure used in the table: NO IDEA (no candidate, or only candidates of a shape already known to fail), WEAK LEVER (the lever chosen at idea or design time was already known to leak), NO CORE (the design blind or the careful program kept the primary lever), LEAK (built task, then a probe, blind or paid run scored tests 95 to 100), QC FAIL (first QC of the first build failed), SOLVABILITY (the lever needed an unstated fact, a withheld format or a timeout exception), TIME (session, agent or calendar time ran out or was the reason to stop).

1. EVIDENCE TABLE

task | date | what happened at design | file:line
district-heat-flex-procurement | 19 to 21 Oct | WEAK LEVER: every "rule written far from use" lever leaked (only_H1 0.92, all_lazy 0.59); QC FAIL 11 on first PL QC; TIME: agent used the full 7200 s twice and got no score | L:8, L:42, T:73
vendor-archive-roundtrip-recovery | 21 to 24 Oct | QC FAIL 26 on v0; LEAK: corrected tests 88.97 then 100 after harden (one explicit sentence per rule); killed by the kill rule | T:350, L:52, D:111
schema-migration-plan-repair | 21 Oct | WEAK LEVER: one lever gated 79 of 156 points, compositions held 23 to 32 percent; 14 points paid by the unrepaired shipped code; QC FAIL 8 on v0 (later pushed at 32.12 after many rounds) | L:20, L:28, L:30, T:467
ChatGPT idea batch 20261021 (5 ideas) | 21 Oct | NO IDEA: all 5 ideas had the same leaking shape (one documented rule plus a reflex reading); idea 1 rejected as too close to an own task (emberforge) | L:9, I:1
data-product-config-compiler | 24 to 25 Oct | WEAK LEVER: the idea was HOLD with "likely leaks" at idea gate, still built; DESIGN READY passed on paper; probe 1 tests 100, harden r2 ROUND LIMIT no credible lever; parked | I:3, D:141, D:156, D:202, T:701
metered-usage-rating-pipeline | 24 Oct | LEAK: habit levers H1 to H4 in one contract, probe tests 199/199; three harden rounds ended ROUND LIMIT; TIME: 8 session time box | D:146, D:201, D:348, L:87
tariff-engine-audit-repair | 24 to 25 Oct | LEAK: probe 1 tests 100; diagnosis found the contract itself named N1 to N3 (transliterated at step 18) | D:156, D:198
habit lever bank (5 fresh builds) | 24 Oct | WEAK LEVER: "Stated habit levers in an explicit contract do not trip Opus"; fourth and fifth builds on the same bank both tests 100 | L:87
cleanroom-window-schedule | 25 Oct | LEAK: 3 of 3 blinds at 100; stated width, span and interval structure handed over the exact method; parked | D:222, D:224, T:734
cold-chain-backbone-quote | 25 Oct | LEAK: probe tests 100, parked by kill rule (one blind had a core DP bug only); later hardened and pushed at 29.06 | D:222, D:228, T:713
counter-page-crash-recovery | 25 to 26 Oct | LEAK: 3 blinds 95/95 in about 3 min; "fully stated replay/recovery contracts are transliterated exactly" | D:237, T:743
batch-lease-scheduler-replay | 25 to 26 Oct | LEAK: 3 blinds 139/139, same pattern as crash recovery; parked | D:238, T:773
flood-repair-portfolio | 26 Oct to 2 Nov | LEAK: 2 of 3 blinds found the elimination DP (parked once); paid a1 tests 108/108; TIME: a3 agent timeout 7200 s; NO CORE: careful blinds exact on the capped books after r4 | D:239, D:628, D:715, FP:21
fuel-card-settlement-consolidation | 26 to 27 Oct | NO CORE: design blind exact 13/13 (42 rules plus 15 quiet ones transliterated in 4 min); redesign R2 unique fit exact again; parked | D:275, D:289, T:821
pilotage-dues-reconstruction | 26 to 31 Oct | NO CORE four times: v1 blind exact 25/25 rules, v2 redesign, try 3 blind kept 12/12, try 4 blind kept 20/20 ("tried every per visit anchor in about 2 s"); parked | D:272, D:623, D:638, T:830
outage-window-replan | 30 Oct | NO CORE at design (blind exact on shipped and 3 hidden seeds); rescued by a stated runtime lever, but SOLVABILITY: blinds lost 100 percent by timeout, above the 70 percent exception, needed Ayush; pushed at 34.78 | D:523, D:525, D:532, T:871
backdated-entitlement-replay | 31 Oct | NO CORE: design blind exact 309/309, lever 300/300 in 0.4 s; stage 2 patterns not proven; parked | D:645, T:906
hangar-check-replan | 31 Oct to 2 Nov | TIME: design session ran out of output (32,000 reasoning tokens, 0 output, WORK empty); NO CORE three times (design, redesign 1, redesign 2); parked then reopened under route 1; QC FAIL 5 on first QC | D:666, D:678, D:688, D:693, D:714, T:916
depot-charge-plan | 31 Oct to 2 Nov | NO CORE v1 (blind exact); redesign lever was a latent meter family the docs never stated: SOLVABILITY, QC DS-21 REAL, the fair fix removed the lever; later paid a1 tests 100 and a2 0 of 2,312 folders differ | D:696, D:701, D:703, T:937
lever pilots L03 and L02 | 1 Nov | NO CORE: L03 three blinds at 100 percent; L02 naive readers lost only 30 percent; "Study phase ends with no new PROVEN lever" | D:683, D:687
new task supply | 31 Oct to 1 Nov | NO IDEA: "new idea only if all fail"; "No replacement (no PROVEN lever)" after hangar and depot parked; "Night: 0 new tasks"; multicorner not picked (no hidden instance lever) | D:604, D:693, D:703, D:707
lever source | 23 Oct | NO IDEA: "Lever design came from our own notes and our own harden sessions only; peer tasks ... sat unread" | L:55
match-replay-desync-audit (converted, design note) | 24 Oct | SOLVABILITY: a withheld format gating 100 of 158 points was escalated by QC from warn to fail | L:77

2. THE 5 MAIN CAUSES, WITH COUNTS

Counting rule: one count per task or event row above where the cause is named in the record; a row can count under more than one cause. NO CORE is also counted per blind or kill table event because each one cost a full design round.

1. NO CORE at design: the careful exact program (design blind) kept the primary lever. 8 designs, 13 design rounds lost (fuel card 2, pilotage 3 recorded plus v2, outage 1, backdated 1, hangar 3, depot 1, pilots L03 and L02 2). Every one of these designs had its lever stated in full in the docs; the blind wrote the program in 2 to 4 minutes (D:275, D:623, D:645). Root: the lever families tried (stated rules, unique fit over a stated domain, exact optimum) are the ones the careful program handles; carrier variation (D2) was tried only as a late redesign and a pilot, and carried state (D8) never as a primary.

2. LEAK after build: the task was built, then tests 95 to 100 on the first probe, blind or paid run. 10 tasks (district heat, vendor, metered, tariff, config, cleanroom, cold chain, counter page, batch lease, flood). Before 26 Oct there was no design blind, so the leak was found only after the full build and QC spend (L:54: "Many QC/fix rounds ... were spent polishing tasks whose difficulty had never been proven").

3. WEAK LEVER chosen knowingly, and NO IDEA supply: 9 events (L:9, I:1, I:3, L:20, L:55, L:87, D:604, D:693, D:703). Ideas came from two ChatGPT batches and from the master's own lever notes; the idea gate already said "likely leaks" (I:3) and the build went ahead; when designs failed there was no queue of other ideas, so the night produced 0 new tasks. Nothing rotated domain or family: 7 of the 14 new builds were optimization or scheduling and 6 used stated rule levers (section 3).

4. QC FAIL on the first build or a SOLVABILITY defect in the lever: 7 events (district heat 11 fails, vendor 26, schema 8, hangar 5, depot DS-21, outage timeout share 100 percent, match-replay withheld format). Two of them (depot, match-replay) are the same pattern: the lever worked only because a fact was not written, and the fair fix removed it (D:701, L:77).

5. TIME and cost: 6 events (hangar session out of output D:666, district heat agent timeouts L:42, flood a3 agent timeout D:715, metered 8 session box D:348, the 5 to 6 hour study before builds D:661, the auto night that ended with 0 new tasks D:703). Each NO CORE round costs a design session plus a blind session plus scoring, so cause 1 multiplies cause 5.

3. FAMILY AND DOMAIN OF AYUSH'S NEW BUILDS (master labels, INFERRED from the records above)

task | domain | primary lever family as built
metered-usage-rating-pipeline | billing | D3 stated habit rules
tariff-engine-audit-repair | billing repo patch | D3 stated rules
data-product-config-compiler | config tooling | D3 stated rules
fuel-card-settlement-consolidation | settlement | D3 breadth plus unique fit
pilotage-dues-reconstruction | port dues | unique fit over a stated domain (D7 risk)
backdated-entitlement-replay | entitlements | unique fit over a stated domain
counter-page-crash-recovery | storage recovery | fully stated replay (attempted D1)
batch-lease-scheduler-replay | scheduling | fully stated replay (attempted D1)
cleanroom-window-schedule | scheduling optimization | exact optimum (D4)
cold-chain-backbone-quote | network optimization | exact optimum (D4)
flood-repair-portfolio | portfolio optimization | exact optimum then runtime (D4)
outage-window-replan | scheduling optimization | exact optimum then runtime (D4)
hangar-check-replan | scheduling optimization | exact optimum, then D2 carrier as redesign
depot-charge-plan | scheduling optimization | exact optimum, then a latent convention

Count: D3 or stated rule unique fit 6, D4 exact optimum or runtime 6, stated replay 2. D1 as designed by teammates (branch fired only by hidden data, many hidden inputs), D2 as a primary from the first card, D8 carried state, D5 and D6 never appear as the first family. Domain: 7 of 14 are optimization or scheduling, 4 billing or settlement. The teammate families that cost Opus the most points (PATTERNS.md D2: 330 of 352, 553 of 644; D1: 100 of 107) are the ones Ayush's designs did not start from.

4. WHAT THE RECORDS SAY WORKED FOR NEW DESIGNS
1. outage-window-replan pushed at 34.78 and cold-chain-backbone-quote at 29.06, both through a runtime or exact optimum lever with a timeout exception (T:871, T:713). Both needed Ayush exceptions on the timeout share.
2. The fix route (build, full QC, one paid run, harden from what the paid program got wrong; D:706) works on converted tasks (schema, warrant) but on new tasks it hits cause 1 again when the paid program is exact (depot a2 0 of 2,312, T:937).
