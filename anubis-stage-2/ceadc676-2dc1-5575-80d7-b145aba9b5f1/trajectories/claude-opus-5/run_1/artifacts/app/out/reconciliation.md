# Reconciliation of batch HSI-2611

## Summary

| element | recomputed_reported | published_reported | compared | diff_count | mean_shift |
|---|---|---|---|---|---|
| N | 203 | 213 | 195 | 192 | -0.189 |
| C | 199 | 210 | 190 | 156 | 0.018 |

## Session decisions

| session | element | computed | ruling | decision | reasons |
|---|---|---|---|---|---|
| SQ-2611-02 | C | REJECT |  | REJECT | SLOPE |
| SQ-2611-05 | C | REJECT | RL-0475 | ACCEPT | QC:QC-SED |
| SQ-2611-11 | N | REJECT |  | REJECT | QC:QC-MUS |
| SQ-2611-11 | C | REJECT |  | REJECT | QC:QC-MUS |
| SQ-2611-13 | N | ACCEPT | RL-0478 | REJECT |  |
| SQ-2611-15 | C | REJECT |  | REJECT | QC:QC-SED;QC:QC-MUS |
| SQ-2611-16 | N | REJECT | RL-0484 | ACCEPT | QC:QC-SED |
| SQ-2611-16 | C | ACCEPT | RL-0484 | ACCEPT |  |
| SQ-2611-21 | N | REJECT |  | REJECT | LEAK |
| SQ-2611-21 | C | REJECT |  | REJECT | LEAK |

## Run settings

| setting | published_run | in_force |
|---|---|---|
| rm_sheet | RM_Certified_DRAFT | RM_Certified_2026 |
| normalization_table | N-1 | N-2 |
| reference_set_N | RM-GLU-L,RM-CAF | RM-GLU-L,RM-GLU-H |
| reference_set_C | RM-GLU-H,RM-CAF | RM-GLU-L,RM-GLU-H,RM-CAF |
| grubbs_table | G-0 | G-1 |
| drift_axis | counter_position | run_minutes |
| linearity_partition | session | instrument_local_day |
| correction_order | blank,linearity,drift,normalization | linearity,drift,blank,normalization |
| revision_rule | latest_revision | audit_admitted |
| autosampler_skips | ignored | applied |
| session_rulings | dashboard | R-1_in_force |
| arithmetic | binary_float_round_at_end | exact_decimal_stage_rounding |

## Superseded notices

| notice | material | lot | element | notice_value | in_force_value |
|---|---|---|---|---|---|
| NB-2026 | RM-CAF | CF-25C | C | -27.74 | -27.73 |
| NB-2039 | RM-GLU-H | GH-23C | C | 36.63 | 36.55 |
| NB-2052 | RM-GLU-H | GH-25A | N | 47.65 | 47.62 |
| NB-2094 | RM-GLU-L | GL-25B | N | -4.42 | -4.49 |
| NB-2104 | RM-CAF | CF-22A | C | -27.84 | -27.77 |
| NB-2126 | RM-CAF | CF-25C | N | 0.99 | 0.96 |
| NB-2162 | RM-GLU-H | GH-25A | N | 47.69 | 47.62 |
| NB-2173 | RM-GLU-L | GL-24A | N | -4.60 | -4.52 |
| NB-2191 | RM-GLU-L | GL-25B | N | -4.48 | -4.49 |
