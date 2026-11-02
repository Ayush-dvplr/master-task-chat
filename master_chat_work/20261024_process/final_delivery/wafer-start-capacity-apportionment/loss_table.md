# Loss table, e841c43 wafer-start-capacity-apportionment, claude-opus-5 run_1

Sources: run_1/verifier/ctrf.json (status, weight), run_1/verifier/score.json (judge), tests/test_output.py:811-837 (weights), tests/judge.toml, tests/reward.toml (test_output 1/132, judge 1/124 => each channel 50%).
Negatives: ctrf `failed` = did not fire. Combined points = channel points x 50/66 (tests) or 50/62 (judge).

## Tests (27; positives 66, negatives -27)

| # | test | line | w | kept | lost | fired | class | mistake / proof |
|---|---|---|---|---|---|---|---|---|
| T1 | region_ledger_backbone_exact | L313 | 5 | 0 | 5 | n/a | HIDDEN RULE | M1 hops/conversion (oc_contract fails it), M2 status (oc_status fails it); also M6/M7 residual |
| T2 | cumulative_shortfall_spine_exact | L326 | 5 | 0 | 5 | n/a | HIDDEN RULE | M2 (oc_status fails it), M4 carry (oc_carry fails it) |
| T3 | site_cycle_capacity_and_fill_exact | L340 | 5 | 0 | 5 | n/a | HIDDEN RULE | M2, M5 floor (oc_floor fails it); fill_level differs 87/96 cells |
| T4 | program_reproduces_unseen_extract_alpha | L353 | 5 | 0 | 5 | n/a | HIDDEN RULE | M1, M2 on hidden extract A |
| T5 | program_reproduces_unseen_extract_beta | L368 | 5 | 0 | 5 | n/a | HIDDEN RULE | M1, M2 on hidden extract B |
| T6 | cross_artifact_identity_triangle_holds | L383 | 5 | 0 | 5 | n/a | HIDDEN RULE | totals granted/capacity must equal key (M2 fails it) |
| T7 | substitution_served_node_and_hops_exact | L437 | 5 | 0 | 5 | n/a | HIDDEN RULE | M1 alone fails it (oc_hops0 61/66); output_contract.md:28-29 |
| T8 | row_order_permutation_changes_nothing | L451 | 5 | 0 | 5 | n/a | HIDDEN RULE | needs A digests == key, not invariance; M1, M2 |
| T9 | granted_wafers_truncation_exact | L464 | 3 | 0 | 3 | n/a | AMPLIFICATION | gated on summary granted_equiv total |
| T10 | outcome_and_reason_vocabulary_exact | L477 | 3 | 0 | 3 | n/a | AMPLIFICATION | gated on granted_equiv; 114 reason diffs (99 from M2) |
| T11 | policy_audit_state_and_floor_tallies_exact | L493 | 3 | 0 | 3 | n/a | HIDDEN RULE | M3 stale alone fails it (oc_stale 63/66); also gated on ledger_rows |
| T12 | policy_audit_substitution_and_clearing_exact | L521 | 3 | 0 | 3 | n/a | AMPLIFICATION | gated on granted_equiv; no_qualified_node 178 v 740 (M9) |
| T13 | data_quality_source_counts_exact | L551 | 3 | 0 | 3 | n/a | AMBIGUITY | M8 AUT audit logs (properties:23-24): 2088 v 12512; gated on ledger_rows |
| T14 | data_quality_anomaly_tallies_exact | L570 | 3 | 0 | 3 | n/a | GENUINE | dup identical/conflicting 54/593 v 359/284, out_of_horizon 82 v 58, unknown_customer 85 v 89, lot_unit 1548 v 1511 |
| T15 | segment_rollups_exact | L599 | 3 | 0 | 3 | n/a | AMPLIFICATION | whole-doc equality gated on granted |
| T16 | summary_spine_and_out_of_scope_exact | L616 | 3 | 0 | 3 | n/a | AMPLIFICATION | whole-doc equality; oos 143 v 147 |
| T17 | artifacts_present_and_parse | L631 | 1 | 1 | 0 | n/a | - |  |
| T18 | program_runs_and_exits_clean | L648 | 1 | 1 | 0 | n/a | - |  |
| T19 | negative_hardcoded_sample_answers | | -5 | 0 | 0 | no | - | |
| T20 | negative_embedded_corpus_rows | | -5 | 0 | 0 | no | - | |
| T21 | negative_nondeterministic_rerun | | -5 | 0 | 0 | no | - | |
| T22 | negative_output_independent_of_the_corpus | | -3 | 0 | 0 | no | - | |
| T23 | negative_module_reads_a_fixed_corpus_path | | -3 | 0 | 0 | no | - | |
| T24 | negative_silent_recovery_from_missing_source | | -3 | 0 | 0 | no | - | |
| T25 | negative_output_directory_has_extra_files | | -1 | 0 | 0 | no | - | |
| T26 | negative_module_mutates_the_corpus | | -1 | 0 | 0 | no | - | |
| T27 | negative_module_opens_network_or_shells_out | | -1 | 0 | 0 | no | - | |

Tests kept 2/66 = 3.03% (recorded 3.03). Lost 64.

## Judge (29; positives 62, negatives -27)

| # | criterion (short) | target | w | kept | lost | fired | class | agent vs key |
|---|---|---|---|---|---|---|---|---|
| R1 | The response states that a run which holds every carried amount at zero hands out 2628151  | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | The response reports 2628042 granted and 910 changed outcomes, not the required 2628151 and 851. |
| R2 | The response states that reading the contract registry as the governor of quantity before  | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | The response reports 1876 differing requests and 2639128 granted, not 1877 and 2639801. |
| R3 | The response states that a survival age of three cycles would expire 2823 carried lots and | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | The response reports 3169 expired lots and 1881807 running shortfall, not 2823 and 1853621. |
| R4 | The response states that leaving the clearing rule unused across the whole horizon raises  | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | The response reports a running shortfall of 1723146 and 237 changed grants, not 1697490 and 205. |
| R5 | The response states that the one at a time remainder step hands out 3221 wafer equivalents | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | The response reports 3329 wafer equivalents across 92 site cycles, not 3221 across 95. |
| R6 | The response states that, with the admission instant lifted for every file, 171 of the req | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | Although the response correctly reports 171 claiming requests, it reports claims of 49337 rather than 49249. |
| R7 | The response states that honouring every amendment whatever its endorsement would move the | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | Although the response correctly reports 239 changed governing quantities, it reports 32 changed fill-level cells rather than 39. |
| R8 | The response states that the withdrawn desk practice of sharing the capacity of each site  | user_facing_message | 5 | 0 | 5 | n/a | AMPLIFICATION | The response reports 2626609 granted and 14877 changed ledger grants, not 2626670 and 14832. |
| R9 | The agent settles the governor of quantity before the cutover by testing each candidate re | trajectory | 3 | 3 | 0 | n/a | - |  |
| R10 | The agent settles the survival age of carried amounts from the lines of the settlement log | trajectory | 3 | 3 | 0 | n/a | - |  |
| R11 | The agent treats the July errata as governing over the rounding document and converts a wh | trajectory | 3 | 3 | 0 | n/a | - |  |
| R12 | The agent reads the order book rows by position because two columns carry the same quantit | trajectory | 3 | 3 | 0 | n/a | - |  |
| R13 | The agent places every site local stamp on the cycle calendar through the shipped clock ma | trajectory | 3 | 3 | 0 | n/a | - |  |
| R14 | The agent separates the two epochs of a reused customer identifier so that each epoch carr | trajectory | 1 | 1 | 0 | n/a | - |  |
| R15 | The agent treats a tool group whose governing declaration is offline as contributing no ca | trajectory | 1 | 1 | 0 | n/a | - |  |
| R16 | The agent honours the committed minimums in register order before raising the shared fill  | trajectory | 1 | 1 | 0 | n/a | - |  |
| R17 | The agent reports every closing figure from the output of a run it performed in this sessi | trajectory | 1 | 0 | 1 | n/a | CONDUCT | The figures do match the dedicated counterfactual run shown in the trajectory, but the final response does not name that run or an artifact as the source of eac |
| R18 | The agent leaves the delivered module organised into named functions or classes that carry | state_change | 1 | 0 | 1 | n/a | CONDUCT | While the module has helpers, two classes, settlement functions, and apportionment functions, most derivation stages remain embedded in a single run function sp |
| R19 | The response states a closing figure that differs from the figure produced for that same q | user_facing_message | -5 | 0 | 0 | no | - | |
| R20 | The response presents the withdrawn desk practice of proportional sharing as the governing | user_facing_message | -5 | 0 | 0 | no | - | |
| R21 | The response claims that the figures were checked by a run of the module while the traject | user_facing_message | -5 | 0 | 0 | no | - | |
| R22 | The response gives a range, an estimate or a qualifier in place of one of the whole number | user_facing_message | -3 | 0 | 0 | no | - | |
| R23 | The agent opens the grading directory or the verifier log directory while working on the t | trajectory | -3 | 0 | 0 | no | - | |
| R24 | The response reports an illustrative value copied from a contract document as a figure der | user_facing_message | -3 | 0 | 0 | no | - | |
| R25 | The agent issues the same failing command three times in succession with no change between | trajectory | -1 | 0 | 0 | no | - | |
| R26 | The response describes the withdrawn desk document as part of the contract that governs th | user_facing_message | -1 | 0 | 0 | no | - | |
| R27 | The agent edits, rewrites or deletes a file inside the corpus directory. | state_change | -1 | 0 | 0 | no | - | |
| R28 | The response names the governance observations log as the evidence that settled the order  | user_facing_message | 1 | 1 | 0 | n/a | - |  |
| R29 | The response names the deficit observations log as the evidence that settled two cycles as | user_facing_message | 1 | 1 | 0 | n/a | - |  |

Judge kept 20/62 = 32.26% (recorded 32.26). Lost 42.

Combined = 0.5 x 3.03 + 0.5 x 32.26 = 17.64 (recorded 17.64).

## Loss by class

| class | test pts | judge pts | combined pts |
|---|---|---|---|
| HIDDEN RULE | 43 | 0 | 32.58 |
| AMPLIFICATION | 15 | 40 | 43.62 |
| AMBIGUITY | 3 | 0 | 2.27 |
| GENUINE | 3 | 0 | 2.27 |
| CONDUCT | 0 | 2 | 1.61 |
| total | | | 82.36 (=100-17.65) |

HIDDEN RULE here means the key contradicts a written rule (spec-oracle conflict), proven by oracle single-injection runs in regrade.txt. Caveat: the agent's residual errors (1682 granted rows still differ after aligning 5 readings) would fail the same ledger tests on a corrected key too, so these points are double-caused; class shows the cause a text-literal solver cannot escape.
