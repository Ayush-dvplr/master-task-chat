# HARDEN_REPORT: district-heat-flex-procurement, harden lp1 r2 (board eb6f232)

23 Oct 2026, 13:03-13:58 IST. Live QC kit HEAD 71a653b23fc2. Tree after the harden: c3c5b97731b5 (sha256 over sorted relative path + NUL + content, 27 files). Session renamed eb6f232; `opencode session list` shows it. Input result: a5 combined 81.25 (tests 100, rubric 62.5). Genuine check: GENUINE (see DIAGNOSIS.md section 1).

## 1. Levers before and after

| Lever | r1 rule text | a5 leak class | r2 change | r2 rule text | Single wrong reading loses (of 98) |
|---|---|---|---|---|---|
| L1 receipt green control | export_manifest.tsv:1-5 | (e) punished a reading nobody takes: the receipt sums "as written" agreed with the correct multiplied reading too | Kept as a truthful parse/count control, now beside the allowance file: the receipt agrees with `allowance_ticks` as written, so a reader who treats the allowance as a static per-event limit sees the control green | export_manifest.tsv:1-5; site_allowances.tsv:1-7 | LEDstatic 85 |
| L2 register multiplier | schema.md:54-57 | (a) one plain sentence, applied at step 14 | RETIRED as a lever (plain data rule kept, still graded in composed docs; MULT0 loses 79) and replaced by L3 | schema.md:54-57 | n/a |
| L3 season allowance ledger (NEW) | none | n/a | New `site_allowances.tsv`; events draw the allowance in `dispatch_start` instant order, equal instants by the 2.4 convention (descending id); a drawn allowance removes later candidates | site_allowances.tsv:1-7; schema.md:36-38 (dispatch_start), 95-98, 130-136 (2.4), 152-158 (section 3), 334-335 (allowance_blocked_offer_count) | LEDnone 85, LEDid 82, LEDstr 82, LEDtie 47 |
| L4 rate composition | rate_cards.xml:4-5, schema.md:36-37, program.ini:21-25, schema.md section 6 checklist 193-201 | (a) + (d): section 6 listed every piece as a checklist | Section 6 checklist removed; each piece stated once in the file it governs | rate_cards.xml:4-7; schema.md:37-38; program.ini:21-25; schema.md:138-141 (2.5 caps); schema.md:198-205 | OVR0 70, OVRrate 67, UPL0 67, H3 67, ADD0 57, CAPpre 48 |
| L7 per-interval half-even credit | rate_cards.xml:6-9 with gloss | (a) then (c): gloss explained the trap; step 28 counted 933 exact halves on shipped data | Gloss removed; "rounded half to even" defined once in 2.2; shipped relief nudged (3720 steps of 10 Wh) so no interval amount is an exact half and half-up equals half-even on shipped data | rate_cards.xml:8-11; schema.md:118-120 | R7offer 70, R7offer_even 70, H5c 70, R7up 29 |

Shipped data never separates the trap readings of L1, L3 order and L7 (LEDstatic, LEDid, LEDstr, LEDtie, R7up give the oracle's shipped documents): 54 sites blocked under every reading, 1226 generous, `dispatch_start` text order equals instant order, 262 adjacent id inversions in start order. Hidden composed extracts reuse site ids across events, mix UTC offsets, write equal instants with different offsets and set allowances at 20-80 percent of demand.

Removed giveaways: section 6 checklist (L4); rate_cards.xml exact-half gloss and shipped exact halves (L7); the r1 multiplier lever and its isolated check (L2). No instruction text names a trap; instruction.md unchanged and states "Each output document is graded whole on fresh inputs".

## 2. Tests channel (tests/test_output.py, 33 checks, +98 / -13)

| Group | Checks | Points | Share of 98 |
|---|---|---|---|
| Format on shipped /app/out | 4 x 1 | 4 | 4.1% (shipped-only, <= 5%) |
| Whole documents on 4 hidden reseeded extracts (region 5, segment 5, summary 3, policy_audit 3, data_quality 3) | 20 | 76 | 77.6% (>= 50%) |
| Isolated rule cases: rate_composition_case, interval_credit_rounding_case, allowance_order_case, allowance_consumption_case | 4 x 3 | 12 | 12.2% |
| Mutations: segment_rate_adder_mutation, allowance_ticks_mutation | 2 x 3 | 6 | 6.1% |
| Isolated total | 6 | 18 | 18.4% (<= 30%) |
| Negatives (cheating only): hardcoded -5, grader path -5, external import -3 | 3 | -13 | n/a |

Dropped checks: waiver_labels_case, tie_break_greatest_tuple_case, residual_ties_descending_id_case, tick_feasibility_case, objective_component_order_case, rejected_profile_rows_case, register_multiplier_case, wh_per_tick_mutation (their rules stay planted in the composed extracts). Failure messages print as `[check]` JSON lines (rewardkit 0.2.1 Score carries no message). Reward: tests 0.5/98, judge 0.5/17.

## 3. Judge channel (tests/judge.toml, mode batched, 8 criteria, +17 / -5)
R1 own extract with a drawn allowance, checks later candidate_offer_count (w3, L1/L3); R2 own extract where the first-starting event has the greater id and later-sorting text (w3, L3); R3 own composed rate above cap, checks credit_cents and cap_binding_count (w3, L4); R4 own half-cent interval amount (w3, L7); R5 ledger in one named function (w3, code shape); R6 exact arithmetic (w1); R7 final run after last edit (w1); R8 claims a check its output contradicts (w-5, honesty). No criterion states a figure or endorses a reading the tests penalise.

## 4. Gates
- Agent programs (tests only, local): a5 11/98 = 0.1122; reflex (a5 + ledger in event_id order) 16/98 = 0.1633; r1 program 2/98 = 0.0204; oracle 98/98. STACKING_CHECK.md: PASS (0 duplicate observable+logic pairs, penalty groups <= 5).
- xref_check: 43 entries, 0 findings.
- QC (kit 71a653b2): structure 17/0, instruction 5/0, tests 37/0, judge 19/0, validate_bundle 41 passed 0 failed 0 warnings. First run failed J10, J5, R3, 15.4; all fixed. Playground static: not in the kit at HEAD (removed in a72c20a4), not run.
- QL rule, `git diff 2690e960 HEAD -- Input_Bundle_QC/`: a74bda85 K8 litellm pin PASS; c9e3454a H6/TS-30 modes and exe_copy --owner-only PASS; d9f94333 G2 judge batched PASS; f3765e67 H6 interpreter switches PASS; 3fb1650b T14 author PASS; 71a653b2 S3/S5 trajectories dir PASS (none shipped). FIXED this round: J10, J5, R3, 15.4.
- Docker (tests only, copies from live exe_copy.py, log `/tmp/opencode-logs/dh-lp2-docker-20261023T134700-20fa/`), 13:47-13:54, warm verifier image built first, one nohup chain ending ALL_DONE, lock released: oracle x3 = 1.0, 1.0, 1.0; owner-only oracle 1.0; nop 0.0; stub 0.0102 (tests-only scores; earns artifact_set only, every rerun check reports "program run failed: wrote no OUT_DIR"); forgery -0.0102 (program embedding the 9 shipped oracle documents: earns the 4 format points, fails all 26 rerun checks, negative_hardcoded_sample_answers fires -5). With the judge absent the tests channel is scaled to the whole reward (1/98 per point).

## 5. Not run
- No agent trajectory on the r2 bundle; the a5 and reflex program scores measure the new rules, not a fresh agent. a5 still passes the L4 and L7 isolated cases and the adder mutation because its program already held the correct readings; whether a fresh agent now misses them is open until the next trajectory.
- Judge channel not run locally; playground static absent from the kit.
