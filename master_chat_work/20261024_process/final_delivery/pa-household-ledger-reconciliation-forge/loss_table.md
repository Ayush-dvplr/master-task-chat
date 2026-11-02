# Loss table: 5e4fd36d-f1ae-5fe6-ba83-c12436dfc083 (claude-opus-5, run_1)

Sources: `run_1/verifier/ctrf.json`, `run_1/verifier/reward-details.json` (not synthesized; per-item detail present), `run_1/verifier/score.json`, weights from `tests/test_output.py:653-677`, `tests/reward.toml:1-7`, `tests/judge.toml`.
Reward formula (`tests/reward.toml`): `test_output` weight 1/108, `judge` weight 1/176 => each channel is 50% (54 positive test points, 88 positive judge points).
Combined = 0.5 x 24/54 + 0.5 x 87/88 = 0.5 x 0.44444 + 0.5 x 0.98864 = **0.71654 -> 71.65** (matches `pass_summary.json` 71.65, `verifier/reward.json` 71.65, `result.json` 0.7165).

Mistake key: M1 = S5 nonresponse denominator counts every resolved engagement, not only resolved AND drawn (agent solve.py:216-217). M2 = S3 q_eff computed in binary float, so three exact half-even ties round the wrong way (agent solve.py:176-188).

## Tests channel (25 tests, 54 positive points, 1 negative)

| # | test (test_output.py) | weight | kept | lost | cause | class |
|---|---|---|---|---|---|---|
| 1 | artifacts_delivered | 1 | 1 | 0 | - | - |
| 2 | metrics_json_has_overall_and_nine_strata | 1 | 1 | 0 | - | - |
| 3 | settlement_lists_nine_strata_and_total | 1 | 1 | 0 | - | - |
| 4 | manifest_declares_core_order | 1 | 1 | 0 | - | - |
| 5 | manifest_digest_covers_delivered_core | 3 | 3 | 0 | self-consistency only | - |
| 6 | population_exact | 3 | 3 | 0 | - | - |
| 7 | label_distribution_exact | 3 | 3 | 0 | - | - |
| 8 | decision_distribution_exact | 3 | 3 | 0 | - | - |
| 9 | frame_counts_exact | 3 | 3 | 0 | - | - |
| 10 | incurred_shares_exact | 3 | 0 | 3 | M1 (cents scale 1.875x etc.) | AMPLIFICATION of M1 (AMBIGUITY) |
| 11 | confidence_intervals_exact | 3 | 3 | 0 | ratio metric, scale-invariant | - |
| 12 | weight_diagnostics_exact | 3 | 0 | 3 | M1 | AMPLIFICATION of M1 |
| 13 | per_stratum_metrics_exact | 3 | 0 | 3 | M1 (tp/fp/fn weighted counts) | AMPLIFICATION of M1 |
| 14 | margins_exact | 5 | 0 | 5 | M1 (all 76 weights) + M2 (3 q_eff ties) | M1 AMBIGUITY + M2 GENUINE |
| 15 | settlement_exact | 5 | 0 | 5 | M1 | AMPLIFICATION of M1 |
| 16 | metrics_json_exact | 5 | 0 | 5 | M1 | AMPLIFICATION of M1 |
| 17 | settlement_breakdown_exact | 1 | 0 | 1 | M1 | AMPLIFICATION of M1 |
| 18 | settlement_ledger_exact | 1 | 0 | 1 | M1 | AMPLIFICATION of M1 |
| 19 | net_benefit_summary_exact | 1 | 0 | 1 | M1 | AMPLIFICATION of M1 |
| 20 | stratum_metrics_stream_exact | 1 | 1 | 0 | ratio metric, scale-invariant | - |
| 21 | overall_metrics_md_exact | 1 | 0 | 1 | M1 | AMPLIFICATION of M1 |
| 22 | reconciliation_report_exact | 1 | 0 | 1 | M1 | AMPLIFICATION of M1 |
| 23 | rollup_xml_exact | 1 | 1 | 0 | ratio metric, scale-invariant | - |
| 24 | audit_summary_exact | 1 | 0 | 1 | M1 | AMPLIFICATION of M1 |
| 25 | negative_artifacts_contradict_each_other | -3 | - | 0 | did NOT fire (returned False; ctrf lists as "failed") | - |
| | **total** | **54** | **24** | **30** | | |

Patch proof (host venv, rewardkit 0.2.1, `OUT/regrade.txt`): agent outputs 24/54; patch M1 only -> 49/54 (+25, only margins_exact still failing); patch M1+M2 -> 54/54, 28/28 files byte-identical to reference.

## Judge channel (27 criteria, 88 positive points, 1 negative; judge gpt-5.6-sol, mode batched)

| id | target | weight | kept | lost | criterion (short) | class |
|---|---|---|---|---|---|---|
| R1 | trajectory | 3 | 3 | 0 | reads overview + 8 spec files before computing | - |
| R2 | trajectory | 1 | 1 | 0 | applies stages in ordering_dependencies.yaml order | - |
| R3 | trajectory | 3 | 3 | 0 | solver uses stdlib only | - |
| R4 | final_answer | 3 | 3 | 0 | states reading for each of S1-S8 | - |
| R5 | final_answer | 1 | 0 | 1 | names the settling file per stage | CONDUCT (report wording) |
| R6 | trajectory | 5 | 5 | 0 | engagement key from four s1 fields | - |
| R7 | trajectory | 5 | 5 | 0 | anchor min submission_no; canonical highest approved | - |
| R8 | trajectory | 5 | 5 | 0 | reviews ordered by review_seq | - |
| R9 | trajectory | 5 | 5 | 0 | S3 running baseline per frozen stratum ascending key | - |
| R10 | trajectory | 3 | 3 | 0 | currency exponents from file | - |
| R11 | trajectory | 5 | 5 | 0 | gain from xlsx sheet whose B1 = calibration_version | - |
| R12 | trajectory | 3 | 3 | 0 | audit unit cost from PDF | - |
| R13 | trajectory | 3 | 3 | 0 | beta from PDF | - |
| R14 | trajectory | 3 | 3 | 0 | z from PDF | - |
| R15 | trajectory | 3 | 3 | 0 | per-diem gap handling from s4 / fx_fallback_policy.yml | - |
| R16 | trajectory | 5 | 5 | 0 | base rate keyed on stratum_frozen | - |
| R17 | trajectory | 5 | 5 | 0 | nonresponse factor on pay-band partition | JUDGE blind spot: passed although M1 is in exactly this factor (see ANALYSIS Phase 4) |
| R18 | trajectory | 3 | 3 | 0 | residue to largest weight, ties smallest key | - |
| R19 | trajectory | 5 | 5 | 0 | log-odds calibration | - |
| R20 | trajectory | 3 | 3 | 0 | inclusive p_cal >= tau_s | - |
| R21 | trajectory | 5 | 5 | 0 | overall F-beta from overall P/R | - |
| R22 | trajectory | 3 | 3 | 0 | macro weight-share means | - |
| R23 | trajectory | 5 | 5 | 0 | Kish ESS over actual / predicted positives | - |
| R24 | trajectory | 1 | 1 | 0 | names verdict_crosswalk.json or s2 as source | - |
| R25 | trajectory | 1 | 1 | 0 | recomputes SHA-256 manifest check | - |
| R26 | trajectory | 1 | 1 | 0 | no bare except | - |
| R27 | final_answer | -3 | - | 0 | claims checked while last solver run errored: did NOT fire | - |
| | **total** | **88** | **87** | **1** | | |

## Loss by class (in combined-score points, each channel = 50)

| class | test points lost | judge points lost | combined points lost |
|---|---|---|---|
| AMBIGUITY (M1, root) + its AMPLIFICATION | 25 sole + shared margins | 0 | 25/54 x 50 = 23.15 |
| GENUINE (M2) + M1 jointly on margins_exact | 5 | 0 | 5/54 x 50 = 4.63 |
| CONDUCT (R5) | 0 | 1 | 1/88 x 50 = 0.57 |
| JUDGE ERROR / ARTEFACT / HIDDEN RULE | 0 | 0 | 0 |
| **total** | 30 | 1 | **28.35** (100 - 71.65) |

Split of the margins 5 points: both mistakes are needed to recover it (patch M1 alone leaves it failing; M2 alone cannot be tested in isolation because M1 already breaks every weight). For class totals it is booked as 2.5 AMBIGUITY + 2.5 GENUINE where a single number is needed (result.json): AMBIGUITY+AMPLIFICATION 25.46, GENUINE 2.31, CONDUCT 0.57.
