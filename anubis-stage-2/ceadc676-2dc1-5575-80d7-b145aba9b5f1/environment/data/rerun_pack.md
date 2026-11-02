# Saved rerun pack for HSI-2611 (published batch v1)

This pack records how the published batch report was produced.
It is kept for traceability. The facility handbook, the governance memo and the reference workbook govern any recomputation.

## Run settings

| setting | value |
|---|---|
| rm_sheet | RM_Certified_DRAFT |
| normalization_table | N-1 |
| reference_set_N | RM-GLU-L,RM-CAF |
| reference_set_C | RM-GLU-H,RM-CAF |
| grubbs_table | G-0 |
| drift_axis | counter_position |
| linearity_partition | session |
| correction_order | blank,linearity,drift,normalization |
| revision_rule | latest_revision |
| autosampler_skips | ignored |
| session_rulings | dashboard |
| arithmetic | binary_float_round_at_end |

## Steps

1. Load every peak row of every shard in the data folder, newest revision first.
2. Subtract the session blank mean from every delta value.
3. Fit a linearity slope from the three ELM-ACT capsules of each session.
4. Fit drift against autosampler counter position.
5. Normalize with Table N-1 sets and RM_Certified_DRAFT values.
6. Screen replicates with Table G-0.
7. Take session status from the QC dashboard.
8. Round the final means to two decimals.

## Session log

- SQ-2611-01 C: slope 0.993344 intercept -0.537419 points 11 dashboard PASS
- SQ-2611-01 N: slope 0.991187 intercept 1.004300 points 4 dashboard PASS
- SQ-2611-02 C: slope 1.070062 intercept -1.003085 points 10 dashboard FAIL
- SQ-2611-02 N: slope 1.015325 intercept 2.224662 points 5 dashboard PASS
- SQ-2611-03 C: slope 0.992589 intercept 0.745239 points 10 dashboard PASS
- SQ-2611-03 N: slope 1.001730 intercept 1.409968 points 5 dashboard PASS
- SQ-2611-04 C: slope 0.976041 intercept -0.287262 points 10 dashboard PASS
- SQ-2611-04 N: slope 1.001265 intercept -0.797289 points 7 dashboard FAIL
- SQ-2611-05 C: slope 1.013640 intercept -0.627067 points 10 dashboard PASS
- SQ-2611-05 N: slope 1.014643 intercept -0.609430 points 5 dashboard PASS
- SQ-2611-06 C: slope 0.986722 intercept -0.223396 points 10 dashboard PASS
- SQ-2611-06 N: slope 0.988125 intercept -1.030291 points 8 dashboard PASS
- SQ-2611-07 C: slope 0.990265 intercept -0.370144 points 8 dashboard FAIL
- SQ-2611-07 N: slope 0.994527 intercept 0.256077 points 8 dashboard PASS
- SQ-2611-08 C: slope 0.992412 intercept -0.830487 points 7 dashboard PASS
- SQ-2611-08 N: slope 1.007486 intercept -1.090904 points 4 dashboard PASS
- SQ-2611-09 C: slope 0.983827 intercept -1.348606 points 8 dashboard FAIL
- SQ-2611-09 N: slope 1.019013 intercept -1.297352 points 8 dashboard PASS
- SQ-2611-10 C: slope 1.001636 intercept 0.818769 points 8 dashboard PASS
- SQ-2611-10 N: slope 1.009599 intercept -0.861206 points 5 dashboard PASS
- SQ-2611-11 C: slope 0.978872 intercept -0.737766 points 10 dashboard PASS
- SQ-2611-11 N: slope 1.000034 intercept 1.774261 points 4 dashboard FAIL
- SQ-2611-12 C: slope 1.003142 intercept -0.675215 points 9 dashboard PASS
- SQ-2611-12 N: slope 0.989555 intercept -2.352325 points 5 dashboard PASS
- SQ-2611-13 C: slope 1.008031 intercept 1.464802 points 7 dashboard PASS
- SQ-2611-13 N: slope 0.989997 intercept 1.346340 points 7 dashboard PASS
- SQ-2611-14 C: slope 1.007353 intercept -0.073723 points 9 dashboard PASS
- SQ-2611-14 N: slope 0.974674 intercept 1.213282 points 7 dashboard PASS
- SQ-2611-15 C: slope 1.006139 intercept 1.494818 points 8 dashboard PASS
- SQ-2611-15 N: slope 1.010795 intercept -0.832236 points 8 dashboard PASS
- SQ-2611-16 C: slope 1.006426 intercept 1.157088 points 9 dashboard PASS
- SQ-2611-16 N: slope 0.997320 intercept -2.371029 points 7 dashboard FAIL
- SQ-2611-17 C: slope 1.013542 intercept 0.354589 points 10 dashboard PASS
- SQ-2611-17 N: slope 1.019079 intercept 0.652737 points 7 dashboard FAIL
- SQ-2611-18 C: slope 1.020826 intercept -0.821224 points 8 dashboard PASS
- SQ-2611-18 N: slope 0.991730 intercept 1.409039 points 7 dashboard PASS
- SQ-2611-19 C: slope 1.010586 intercept 0.342410 points 10 dashboard PASS
- SQ-2611-19 N: slope 1.002072 intercept -1.460612 points 6 dashboard PASS
- SQ-2611-20 C: slope 1.009523 intercept 1.331045 points 10 dashboard FAIL
- SQ-2611-20 N: slope 1.008045 intercept 0.184882 points 4 dashboard PASS
- SQ-2611-21 C: slope 0.997501 intercept -0.579241 points 9 dashboard PASS
- SQ-2611-21 N: slope 0.995222 intercept -2.188957 points 8 dashboard FAIL
- SQ-2611-22 C: slope 0.986127 intercept -1.270546 points 9 dashboard PASS
- SQ-2611-22 N: slope 1.016559 intercept -1.969536 points 7 dashboard FAIL
- LN-2611-01 loaded from shard export, instrument K1
- LN-2611-02 loaded from shard export, instrument K2
- LN-2611-03 loaded from shard export, instrument K2
- LN-2611-04 loaded from shard export, instrument K1
- LN-2611-05 loaded from shard export, instrument K2
- LN-2611-06 loaded from shard export, instrument K1
- LN-2611-07 loaded from shard export, instrument K2
- LN-2611-08 loaded from shard export, instrument K1
- LN-2611-09 loaded from shard export, instrument K2
- LN-2611-10 loaded from shard export, instrument K2
- LN-2611-11 loaded from shard export, instrument K1
- LN-2611-12 loaded from shard export, instrument K1
- LN-2611-13 loaded from shard export, instrument K2
- LN-2611-14 loaded from shard export, instrument K2
- LN-2611-15 loaded from shard export, instrument K2
- LN-2611-16 loaded from shard export, instrument K1
- SQ-2611-01 loaded from shard export, instrument K1
- SQ-2611-02 loaded from shard export, instrument K2
- SQ-2611-03 loaded from shard export, instrument K2
- SQ-2611-04 loaded from shard export, instrument K1
- SQ-2611-05 loaded from shard export, instrument K1
- SQ-2611-06 loaded from shard export, instrument K2
- SQ-2611-07 loaded from shard export, instrument K1
- SQ-2611-08 loaded from shard export, instrument K2
- SQ-2611-09 loaded from shard export, instrument K1
- SQ-2611-10 loaded from shard export, instrument K2
- SQ-2611-11 loaded from shard export, instrument K1
- SQ-2611-12 loaded from shard export, instrument K2
- SQ-2611-13 loaded from shard export, instrument K1
- SQ-2611-14 loaded from shard export, instrument K2
- SQ-2611-15 loaded from shard export, instrument K1
- SQ-2611-16 loaded from shard export, instrument K2
- SQ-2611-17 loaded from shard export, instrument K1
- SQ-2611-18 loaded from shard export, instrument K2
- SQ-2611-19 loaded from shard export, instrument K2
- SQ-2611-20 loaded from shard export, instrument K1
- SQ-2611-21 loaded from shard export, instrument K2
- SQ-2611-22 loaded from shard export, instrument K1
- SQ-2611-01 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-01 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-01 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-01 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-02 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-02 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-02 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-02 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-03 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-03 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-03 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-03 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-04 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-04 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-04 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-04 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-05 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-05 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-05 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-05 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-06 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-06 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-06 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-06 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-07 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-07 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-07 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-07 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-08 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-08 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-08 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-08 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-09 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-09 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-09 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-09 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-10 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-10 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-10 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-10 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-11 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-11 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-11 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-11 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-12 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-12 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-12 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-12 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-13 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-13 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-13 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-13 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-14 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-14 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-14 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-14 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-15 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-15 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-15 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-15 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-16 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-16 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-16 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-16 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-17 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-17 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-17 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-17 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-18 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-18 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-18 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-18 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-19 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-19 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-19 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-19 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-20 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-20 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-20 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-20 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-21 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-21 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-21 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-21 N: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-22 C: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-22 C: replicate screen G-0 one-sided, rounding at the end
- SQ-2611-22 N: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first
- SQ-2611-22 N: replicate screen G-0 one-sided, rounding at the end

## Session notes

- SQ-2611-01: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-02: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-03: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-04: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-05: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-06: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-07: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-08: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-09: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-10: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-11: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-12: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-13: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-14: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-15: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-16: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-17: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-18: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-19: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-20: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-21: autosampler log not consulted; status copied from the dashboard export
- SQ-2611-22: autosampler log not consulted; status copied from the dashboard export
