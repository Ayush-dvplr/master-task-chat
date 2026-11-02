# Judge baseline from saved run_1 reward-details (27 Oct)

| id | w saved | w now | earned saved | text changed | judge reasoning |
|---|---|---|---|---|---|
| R1 | 3.0 | 3 | 0.0 | same | The response states 3015547, not the required 2999382. |
| R2 | 3.0 | 3 | 0.0 | same | The response states 0 changed rows, not 21. |
| R3 | 3.0 | 3 | 0.0 | same | The response states 8 settled claims, not 115. |
| R4 | 3.0 | 3 | 0.0 | same | The response states 2404196, not 1294476. |
| R5 | 3.0 | 3 | 0.0 | same | The response states 0 affected treaty settlements, not 32. |
| R6 | 3.0 | 3 | 0.0 | same | The response states 184, not 1847061. |
| R7 | 3.0 | 3 | 0.0 | same | The response states 217, not 3020677. |
| R8 | 3.0 | 3 | 0.0 | same | The response states 80 changed grants, not 7. |
| R9 | 3.0 | 3 | 0.0 | same | The response states 0 remainder dollars, not 5135. |
| R10 | 3.0 | 3 | 0.0 | same | The response states 0 affected LOB cycles, not 2. |
| R11 | 3.0 | 3 | 0.0 | same | The response states 0 claims, not 5. |
| R12 | 3.0 | 3 | 0.0 | same | The response states 0 dollars, not 1104789. |
| R13 | 3.0 | 3 | 0.0 | same | The response states 16 claims, not 15. |
| R14 | 3.0 | 3 | 0.0 | same | The response states 0 LOB cycles, not 14. |
| R15 | 1.0 | 1 | 0.0 | same | The trajectory displays treaty totals and validates artifact structure, but it never executes a per-LOB ledger sum compared to the corresponding treaty_working.json field. |
| R16 | 3.0 | 3 | 1.0 | CHANGED | At least three claim_adjustment_log.log lines are quoted in Step 12. The executed module's settle_alae logic tests both literal candidates pro_rata and excess_only over every parsed observation before selecting pro_rata. |
| R17 | 3.0 | 3 | 1.0 | CHANGED | At least three treasury_curve_observations.log lines are quoted in Step 12. The executed settle_curve logic tests both literal candidates flat_10y and duration_matched over every parsed observation before selecting duration_matched. |
| R18 | 3.0 | 3 | 1.0 | same | The response identifies errata_2032-04.md as the authority and describes the governing attachment as per-event clash attachment; methodology_audit.json also records the exact rule clash_cover_per_event. |
| R19 | 3.0 | 3 | 0.0 | CHANGED | The module uses positional column 4, but the trajectory does not show the CLM-00011 transaction row and its governing value together with the positional reading mechanism as required. |
| R20 | 3.0 | 3 | 0.0 | same | The response names several exact data-quality fields, but it does not cite the specific source filename producing each named tally. |
| R21 | 1.0 | 1 | 0.0 | same | The artifacts show RE-0412#1 and RE-0412#2, but the trajectory lacks the required worked example quoting both the alias row and epoch boundary. |
| R22 | 1.0 | 1 | 1.0 | same | The trajectory reads layer_capacity_declarations.csv, and reserving.py derives capacities through _lob_cycle_map at runtime rather than containing a literal per-cycle capacity table. |
| R23 | 1.0 | 1 | 0.0 | same | The response does not explain all three allocation steps, identify a binding-capacity cell, and quote a matching ledger grant. It instead claims no capacity binds. |
| R24 | 1.0 | 1 | 1.0 | same | The trajectory repeatedly executes reserving.py over /app/data and /app/out, including the final artifact-producing runs. |
| R25 | 1.0 | 1 | 1.0 | same | The delivered implementation is one Python file using standard-library imports, and no package-manager installation command appears. |
| R26 | 1.0 | 1 | 1.0 | CHANGED | The response names pro_rata and duration_matched, matching methodology_audit.json. |
| R27 | 1.0 | 1 | 0.0 | same | The response overclaims that every settled observation contradicts excess_only, while its own executed check only establishes 18 positive-ALAE retention observations. Thus not every methodology derivation claim is supported by the shown evidence. |
| R28 | -5.0 | -5 | 0.0 | same | There is no access to a file under /tests/ or /logs/verifier/. |
| R29 | -5.0 | -5 | 0.0 | same | The selected pro_rata convention is not shown to be contradicted by a claim-adjustment observation; the executed check reports no pro-rata misfits. |
| R30 | -5.0 | -5 | 0.0 | same | The selected duration_matched curve is not shown to be contradicted by a treasury observation. |
| R31 | -3.0 | -3 | 0.0 | same | The fourteen counterfactual answers are presented as plain integers, not fractions, ranges, confidence intervals, or tilde-hedged values. |
| R32 | -3.0 | -3 | 0.0 | same | No external search, HTTP request, external implementation retrieval, or package installation appears. |
| R33 | -3.0 | -5 | 0.0 | CHANGED | The response uses the errata's per-event clash-cover rule rather than the withdrawn handbook's individual-risk rule. |
| R34 | -1.0 | -3 | 0.0 | CHANGED | None of the fourteen counterfactual integers uses comma, K, or M formatting. |
| R35 | -1.0 | 1 | 0.0 | CHANGED | The response does not cite a reused reinsurer identifier without its required epoch suffix. |

Saved judge earned 13 of 65 positive (R16 3, R17 3, R18 3, R22 1, R24 1, R25 1, R26 1) = 20.0%; no negatives fired.
Current judge.toml: 35 criteria, positives 66. Text CHANGED since 27 Oct: R16, R17, R19, R26, R33, R34, R35 (others same).
Closing message R1-R14 numbers: 3015547, 0, 8, 2404196, 0, 184, 217, 80, 0, 0, 0, 0, 16, 0.
Old judge values: 2999382 21 115 1294476 32 1847061 3020677 7 5135 2 5 1104789 15 14.
Oracle (QC report) values: 2972752 20 114 1294465 32 1830654 2994037 7 5135 2 5 1104789 15 14.
No closing number equals either set -> R1-R14 lost BEFORE and AFTER.
