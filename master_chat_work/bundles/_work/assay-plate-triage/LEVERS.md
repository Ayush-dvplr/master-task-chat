# LEVERS assay-plate-triage (written 26 Oct by fix round 4f33c30 from TRUTH.md, tests and the Opus run_1 trajectory; no DESIGN.md existed)

Loss = points of 90 lost on channel A by the single wrong-reading variant of the reference (WORK/scripts/trap.py, rows in WORK/trap_rows.json and WORK/trap_perm_rows.json).

| Lever | What must be found | Wrong reading it punishes | Checks that grade it | Loss |
|---|---|---|---|---|
| L01 chain_blank (0x001) | a plate's blank starts at the ending blank of the previous plate on the same instrument | blank resets per plate (bit ignored) | mode_bit_chain_blank, 5 every_bit_except (not chain_blank), 8 full, grown | 71 |
| L02 drift_echo (0x002) | a measure charge lands on the plate's next read | charge applied at once | mode_bit_drift_echo, 6 except, 8 full, grown | 76 |
| L03 role_lookback (0x004) | tolerance from the previous read's operator | own operator's tolerance | mode_bit_role_lookback, 5 except, 8 full, grown | 71 |
| L04 band_tier_shift (0x008) | band edges lift by 15 x tier | fixed edges | mode_bit_band_tier_shift, 6 except, 8 full, grown | 76 |
| L05 exposure_floor (0x010) | normalise by the plate's smallest exposure | the read's own exposure | mode_bit_exposure_floor, 5 except, 8 full, grown | 71 |
| L06 panel_parity (0x020) | odd replicates use the plain adjustment | family adjustment always | mode_bit_panel_parity, 6 except, 8 full, grown | 76 |
| L07 baseline_delta (0x040) | last sorting instrument's baseline is a delta from the smallest other | baseline literal | mode_bit_baseline_delta, 5 except, 8 full, grown | 71 |
| L08 exposure_order (0x080) | resolve by (exposure, seq) | seq order | mode_bit_exposure_order, 6 except, 8 full, grown | 76 |
| L09 mask_absolves (0x100) | a masked well removes one strike (rollup only) | strikes untouched; readings-only digest check calls it free | mode_bit_mask_absolves, 5 except, 8 full, grown | 71 |
| L10 count_bias (0x200) | the last 1 + plate_count % 4 reads by seq are dropped | trust declared_reads | mode_bit_count_bias, 6 except, 8 full, grown | 76 |
| L11 matrix_alias (0x400) | written matrix aliases tier + operator_count places on | matrix literal | mode_bit_matrix_alias, 5 except, 8 full, grown | 71 |
| L12 quarantine_span (0x800) | quarantine adds the previous plate's strikes on the instrument (rollup only) | own strikes only | mode_bit_quarantine_span, 6 except, 8 full, grown | 76 |
| L13 trap_blind | the mode word must be honoured at all | plain chain only, mode ignored (Opus run_1: 3/90) | every bit, except and full check | 87 |
| L14 alias_count | alias offset reads the operator count of the run | offset fixed at the shipped count (5) | mode_bit_matrix_alias, 5 except, 8 full, grown (11 operators) | 71 |
| L15 bias_count | tail length reads the plate count of the run | tail fixed at the shipped 2 | 4 except, 5 full, grown (corpora whose plate count % 4 differs from the shipped run's) | 50 |
| L16 bit_identity | which bit owns which alteration | alterations wired to the wrong bits (rotation or swap) | the 12 mode_bit checks and the 6 except checks | rotate 42, swap 7 |

Plain chain constants (gain, matrix and panel adjustments, bands, tolerances, charge, ceiling, thresholds, ties) are graded by the base tier (untrapped_run_alpha/beta) and inside every other check; settled by the two worked mode zero runs.
