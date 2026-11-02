# DIAGNOSIS: emberforge-vault-settlement, harden round 2 (22 Oct 2026, IST)

Run read: claude-opus-5 Run 1 (21 Oct 18:47 to 19:34 IST), `baseline_v0/trajectory_job/.../Run 1/agent/trajectory.json` (23 steps), program `artifacts/app/out/settle_vault.py` (1326 lines). Scores are the corrected Docker replay (Variant B of `20261021_v0-rescore/RESCORE_REPORT.md`): tests 146/155 = 0.9419, read per check from `/tmp/v0-rescore-20261021T2055/jobs/ef-B-oracle/ef_B__ZiLvfs2/verifier/reward-details.json`. Rubric 84.21 is taken from the re-score report, not re-measured.

## How the agent worked (step = trajectory step_id)

- Steps 3 to 9 (13:17 to 13:19 UTC): listed `/app/data`, then dumped every document (step 4: `calibration_slice.md`, `convention_register.md`, `finding_codes.md`, `invariants.md`, `record_shapes.md`; step 5: all seven rulebooks) and every table, the ledger last.
- Steps 10 to 14 (13:32 to 13:53): wrote the whole program in two edits. No exploratory runs before writing it.
- Step 15 (13:54): first run. `recover_draw` settled the calibration slice under all 840 draws and kept the ones whose summary equals `calibration_controls.json` and whose returned units for cinderhall equal `example_workshop_report.json`. Exactly one survived (RS-C, half-even, GFS, opening-plus-acquired), and the run printed the final figures (charge 124974, closures L0305 and L0290, seven forges with two findings).
- Steps 16 to 22: internal identities only (charges sum, conservation, key order, Q2 to Q6 constraints). Step 17 caught one real bug with its own Q6 audit (two funded requisitions on CH-01) and fixed it. Step 20 timed its own 48-requisition stress season (6.3 s against the 38 s limit). Step 23 finish, about 47 minutes into a 7200 s budget.

The one self-check that touched the answer was the slice: a unique surviving draw told the agent that its engine reproduced a whole settled season. Everything else it checked was an identity that holds under any reading.

## Lever table (round 1 levers against this run)

| lever | rule and where the agent read it | how it checked itself | checks | points | earned | status | why it did not cost |
|---|---|---|---|---|---|---|---|
| LV-EF-1 cap and floor at one forge | A4 second paragraph, read at step 5: "A forge that the vault floor or a retired reagent also refuses is still judged against the cap, and it still closes its workshop". Program lines 599 to 622 compute the charge and test the cap for every forge that passed the gates, after recording floor and retired findings. | none specific; the slice has no forge that both refuse | `cap_and_floor_*` (10) | 38 | 33 | LEAKED | Round 1 stated the composition in one sentence. The 5 lost points (`cap_and_floor_one_findings`) are the S6 ambiguity (QC IN-16): the program also tests the window on a repeated salvage and adds 5 `UNCREDITED_SALVAGE` pairs on lv1a. Not the lever. |
| LV-EF-2 retired reagent | V9, read at step 5: "It never stands in for the charge cap or the floor, which are judged on the same forge as well." Lines 600 to 605. | none; the slice retires nothing | `retired_reagent_*` (10) | 38 | 38 | LEAKED | Same: the composition is written out in V9. |
| LV-EF-3 consumed reference | register `consumed`, read at step 4, with its scope sentence. Line 598 counts `floor_tested` for every forge past the gates, before any refusal. | none; the slice uses opening-plus-acquired | `consumed_reference_*` (10) | 38 | 38 | LEAKED | The register defines exactly which forges count. |
| LV-EF-4 requisition ladder | Q1 to Q8 (step 5) and the 38 s limit (instruction). Lines 746 to 935: branch and bound over charter groups with a max-flow feasibility bound, then Q8 fixing. | its own 48-requisition stress season, step 20 (6.3 s) | `requisitions_*` (4) | 18 | 18 | LEAKED | Round 1 priced the exhaustive DFS of the round 0 run; this agent never wrote one. A size lever does not bind an agent that picks a bounded search first. |
| LV-EF-L7 every condition is a finding (N3 x A4 x V4) | N3 at step 4; lines 600 to 622 append every finding that holds, CAP at a closed workshop included. | none | inside the six lever `*_findings` checks | 30 | 25 | LEAKED | Same 5 points as LV-EF-1 (S6). |
| isolated rules | | | 6 x w3 | 18 | 15 | | `quiet_rules_findings` lost: the program crashes on a salvage with a missing forge reference (line 580, `src['day']` on None). The shipped season has no such salvage (its own step 12 printed `missing_ref []`), so the path never ran. HELD by an untested branch, not by a lever. |
| structure | | | 5 x w1 | 5 | 4 | | `structure_findings_canonical_form` reads the same cl_quiet season, so the same crash cost it. |

Total: 146 of 155. No negative fired.

## Why round 1 predicted 0.168 and the run scored 0.94

1. The prediction priced the round 0 program, not a fresh reader. S4 was the round 0 run's own program with the reference bundle removed; its readings (floor tested first and stopping, retirement as an early refusal, `consumed` as every forge with an edition, exhaustive plan search) were that one run's mistakes. Round 1 then wrote the correct composition of each lever into the documents (A4 paragraph 2, V9's last sentences, the register's scope sentence). A reader who follows those sentences literally gets all three right, and this one did.
2. The slice still confirmed the engine. Removing the reference bundle left `calibration_controls.json` plus one workshop's returns, which pin the draw uniquely. A wrong reading of anything the slice exercises (E3, S6 first-credit, window, fixed point, rounding) leaves no draw, so the search doubled as an end-to-end test of the engine (study rule 7).
3. Grading isolated one lever per season (`test_output.py:3144-3173`, 40 of 45 positive checks). A program right on the stated levers loses nothing anywhere; the only miss in the run (S6) cost one 5-point check.
4. The final-reply ask told the agent which facts mattered ("four conventions", "the entry that closed each workshop that reached its charge cap", "every forge entry that carries more than one finding"), and the judge read exactly those visible-season values (R1 to R4), which the program printed at step 15.

## Causes against the Phase 2 fixes

| cause | fix that addresses it |
|---|---|
| verifier could not open a 0600 program (reported 1.94) | fix 1 (stage a readable copy, kill by uid) |
| S6 ambiguity cost 5 points on lv1a | fix 2 (IN-16 sentence) |
| slice confirms the whole engine | fix 3, remove the settled slice; publish per-convention evidence only |
| convention count and trap list in the final-reply ask | fix 3, instruction |
| one lever per season, 40+ isolated checks | fix 3, composition re-weight |
| every lever spelled out in one sentence | fix 3, one rule moved to a scope-by-omission sentence, one decoy default |
| judge read visible values the program prints | fix 3, judge per B.12 |
| size lever does not bind | not a separate fix; the ladder seasons are folded into composed seasons so the plan sits downstream of the chain (fix 3 composition) |

No cause falls outside the fixes, so there is no DIAGNOSIS CONFLICT. One caveat: rules stay documented (common rule Never 6), so a literal reader can still get every lever right; what changes is that a single miss now costs whole documents on several seasons, and nothing shipped confirms the chain.
