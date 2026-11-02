# RULE_COVERAGE assay-plate-triage (4f33c30, fix r1)

One mutant per rule of the oracle triage.py (WORK/scripts/trap.py), scored on the fixed tests; last column = graded checks that fail under it.

| rule | mutant | failing checks |
|---|---|---|
| L01 chain_blank | L01 chain_blank (bit ignored) | 15 |
| L02 drift_echo | L02 drift_echo (bit ignored) | 16 |
| L03 role_lookback | L03 role_lookback (bit ignored) | 15 |
| L04 band_tier_shift | L04 band_tier_shift (bit ignored) | 16 |
| L05 exposure_floor | L05 exposure_floor (bit ignored) | 15 |
| L06 panel_parity | L06 panel_parity (bit ignored) | 16 |
| L07 baseline_delta | L07 baseline_delta (bit ignored) | 15 |
| L08 exposure_order | L08 exposure_order (bit ignored) | 16 |
| L09 mask_absolves | L09 mask_absolves (bit ignored) | 15 |
| L10 count_bias | L10 count_bias (bit ignored) | 16 |
| L11 matrix_alias | L11 matrix_alias (bit ignored) | 15 |
| L12 quarantine_span | L12 quarantine_span (bit ignored) | 16 |
| L13 trap_blind | L13 trap_blind (mode word ignored) | 27 |
| L14 alias_count | L14 alias_count (operator count fixed at shipped 5) | 15 |
| L15 bias_count | L15 bias_count (tail fixed at shipped 2) | 10 |
| L16 bit_identity | L16 bit map rotated by one (FLAG table shifted) | 18 |
