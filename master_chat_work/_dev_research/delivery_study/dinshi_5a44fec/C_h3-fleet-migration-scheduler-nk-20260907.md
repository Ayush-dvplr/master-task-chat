# C card: h3-fleet-migration-scheduler-nk-20260907

Base `T=.../Perfect_for_Delivery/Dinshi_Jain/h3-fleet-migration-scheduler-nk-20260907`. No QC report exists for this task.

## 1 Scores and verdict
- Recorded overall 64.77, tests 70.71, rubric 58.82 (score.json; final = mean of the two).
- Verdict **GENUINE** (A file). Genuine test points lost 29/99: 3 shipped x3 + 4 hidden x5. The 4 hidden losses are INFERRED to have the same cause (each hidden check compares one scalar or block, and only `ok` is recorded). No negative fired.

## 2 Inventory
- Domain: HTTP/3 reverse-proxy fleet scheduling (apportionment, selection, placement, preemption cascade, token buckets, damped fixed point). Archetype: **constant recovery** (four withheld settlements fitted from sealed corpora) + reusable program (`reusable_scheduler.py <data> <out>`) + 11 canonical JSON artifacts with an integrity manifest.
- Files: 26 in `environment/data`: README-input-schema.md (spec, with section 6 listing candidate values), 6 `case-*.json` + 6 `seal-*.json`, worked_micro_example.json, fixed_point_constants.json, csv (fleet_nodes, stream_manifest, tenants, token_buckets, mtu/latency matrices, epoch_windows, packet_rate_profiles), json (qos_classes, preemption_ladder, migration_penalty_table).
- Instruction: 587 words, 17 lines. 21600 s.
- Tests (stacking_check): 35 checks, positive 99, negatives -26 (6 negatives). Judge 20 criteria, positive 51, batched.
- Shares (stacking_check): hidden_rows 59.6%, isolated 20.2%, shipped_only 20.2%, whole_doc 0%.

## 3 Test architecture
- Expected values: **embedded golden results keyed by an input fingerprint** (`_GOLDEN_RESULTS_B64` test_output.py:417, decoded by `_golden_results` 482; `_reference_solve` raises "fixture has no independently reviewed golden result" when the fingerprint is unknown). Input data is also embedded (`_EMBEDDED_DATA_B64`). So expected outputs are precomputed (18 fixtures) and no reference code runs at grade time.
- Fresh discriminating fixtures, one per withheld settlement and per mechanic (619 SLO strict, 632 LR tie, 648 floor before cap, 662 refill floor, 677 migration previous epoch, 694 one-hop cascade, 747 hard cap mid-loop, 775 tenant priority before stream id, 816 utilization end pre-refill): each is a tiny hand-made input with one asserted property.
- Hidden seeded regimes `_seeded_scenario` 791 (oversubscribed, tight_slo, burst_arrival, migration_dominant): each changes one input file of the shipped set and **compares one scalar** (840-864).
- Shipped checks compare whole blocks (trace 725, tenant report 736, final_state 866). Sealed witness checks (884-913) compare schedule_matrix + one other file per seal.
- Program run `_run_agent` with a privilege drop (310, 374). The fresh fixtures passed, so it ran (no H6 artefact).
- Negatives: hardcoded -5, filename -5, nondeterministic -5, float leak -3, scratch files -3, hollow program -5. stacking_check flags AL-28 "UNMATCHED" 20 (float/scratch/hollow plus judge R3/R4/R16 at -3 each), to be confirmed by hand. No wrong-reading negatives.

## 4 Lever table (failed checks)
Rule graded by all 7 failures: `admitted` count per tenant/epoch = streams **placed** after phase 6b (oracle solve.py:516-518, 578-582 counts `assignments`).

| id | w | locations (quotes) | form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|
| shipped_fixed_point_trace_converges_within_tolerance | 3 | README:58 "Sort admitted streams globally by:" (phase 6, before placement); :79 "When an unplaced admitted stream `s`"; :90 "`fairness_deviation[e] = sum over t of \|admitted_count[t, e] - target[t, e]\|`"; :110-111 "`admissions_new` via phases 4-6"; :135 trace field `admitted_total` | **implied by a definition / split across sections**: the word is used for pre-placement selection (:58, :79), while the count definition (:111 "via phases 4-6") implies post-placement | step 10 think: "\"admitted\" = phase-5 selected (phase 6 says \"sort admitted streams\"), so fairness uses selected counts" | its own audit (step 20 audit.py) asserted `admitted == placed + preempted`, which encodes its own reading; seals have preempted_count 0 and worked_micro_example `phase_6b_cascade: none` | **NO, HIDDEN RULE** (the term carries two meanings; :111 is the only hint) | never-used list "'it' two antecedents"-like; NEW: overloaded term |
| shipped_tenant_report_has_every_epoch | 3 | same + :130 report field `admitted` | same | same | same | same | same |
| shipped_final_state_matches_reviewed_result | 3 | total_cost depends on the fairness deviation | cascade | same | same | same | cascade |
| hidden_tight_slo_fairness_matches_reference | 5 | same | same | INFERRED same | same | same | same |
| hidden_burst_arrival_fixed_point_matches_reference | 5 | trace admitted_total | same | INFERRED | same | same | same |
| hidden_migration_dominant_objective_matches_reference | 5 | objective total | same | INFERRED | same | same | same |
| hidden_oversubscribed_objective_matches_reference | 5 | objective fairness_deviation | same | INFERRED | same | same | same |

Evidence of value: shipped objective_breakdown want fairness_deviation 26 / total 1431, got 12 / 1403; trace admitted_total want 18,18,18,18,13,13,12,12, got 18,18,19,... (my decode of the golden blob against artifacts/app/out, A file).

## 5 How tests handle QC (no QC report; read from code)
- TS-13: hidden regime checks compare one scalar each; shipped checks compare whole blocks. 3 fixtures assert 3 times (stacking §2).
- TS-16: negatives are cheat acts only.
- TS-19: every one of the four withheld rules has its own fresh fixture (all passed). The undefined `admitted` is not a stated promise, so it is graded without a rule. Risky under our IN-16 ("nothing graded has two defensible readings").
- TS-20: 1/3/5 used; core hidden = 5.
- TS-26: stacking flags migration_dominant = oversubscribed (same observable, different input), so no double pay on one input.
- IN-15/IN-16: no report. Our ruling: IN-16 should FAIL on `admitted`. The task reached delivery anyway.
- AL-28: stacking marks 20 unmatched; acts look distinct (float, scratch, hollow), so INFERRED PASS by hand.
- CL-4: one wrong concept cost 29 pts across 7 checks; the cascade is natural (fairness feeds total cost).
- JD-7: unknown (no report).

## 6 Leak avoidance
- W1/W6: the withheld rules are named with candidate lists (README §6, :180-197), and each case states its `purpose`; this is safe because the seals pin every candidate (the agent's sweep at step 17 found exactly one fitting combination of 24). Leak-free by construction: the agent must fit, not read.
- The trap that actually scored (admitted) was never discussed anywhere. The seals and the worked micro example have zero preemption, so shipped data does not separate the two readings (W5/W6: no shipped separating case).
- Golden results hidden in a compressed blob in the test, so they are invisible to the agent.
- LEAK_LIBRARY: the constant-recovery part resembles the vendor "calibration" rows but avoids "shipped boundary rows let agent watch rules fire" because only the 4 named settlements fire in the seals.

## 7 Agent behaviour
- Read the README (steps 4-6, first 15 s), csv/json (7), worked example (8), cases and seals (9). Step 10 think (12:19:03, minute 4) did a hand analysis of the seals and settled `admitted`.
- First full program step 11/13 (12:20:17-12:21:30, minute 5-6). verify_cases (14-15), sweep of 24 combinations (16-17), audit (20-21), fuzz with a hand-built cascade corpus (22-23).
- Graded logic did not change after step 13 (INFERRED; later steps verify and deliver).
- Final claim (step 32): settlements recovered and "All six seals pass". True, but silent on the admitted meaning.

## 8 Passed checks
- All four withheld-settlement fixtures + 5 mechanic fixtures: one-property inputs that match the README sentences.
- Seal witness checks: no preemption in seals, so the admitted reading did not matter.
- Schema/canonical/integrity/SLA independence: format checks.

## 9 Take-aways
- SAFE adopt: precomputed golden results keyed by input fingerprint, embedded compressed in the test (no reference logic at grade time, and an unknown fixture fails loudly).
- SAFE adopt: candidate-list constant recovery where every candidate is pinned by a single-feature sealed case.
- RISKY (no QC, would fail IN-16 under our rulings): a term used with two meanings, with the graded meaning implied only by the "computed via phases 4-6" clause.
- Avoid: shipped seals that exclude the branch where the readings differ, paired with a self-audit-friendly identity.
