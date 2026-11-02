# LEVERS sentinel-policy-recompute (Harden P9 v2 r1)

Lever set L1 + L2 + L3 + L7 (three from L1-L3). Not a repeat of any used set (cohort L1+L2+L3+L4/L5, vendor L2+L3+L5+L6, district-heat L1+L2+L4+L7, emberforge L3+L6+L7, schema L1+L2+L5+L6).
Single-lever scores below are the oracle with exactly one wrong reading, tests channel only, local scorer (WORK/single_lever.py).

## L3 stateful stream: tenant override allowance

- Rule text: `environment/data/override_deltas.json` line 9 (conventions): "Each tenant has an override allowance in quota_limits.cfg. The rows that pass selection use that allowance one unit each, in ascending seq order across all rows of the tenant whichever principal they name, and a row that passes selection after its tenant's allowance is used up is not applied." Line 10: "Every applied row adds its deltas to the base parameters of its principal." Allowance values: `quota_limits.cfg` lines 6-8 (bare property, range 1 to 6 stated line 6). Selection: line 8 points to `override_precedence.conf` lines 2-4.
- Reflex reading: take the first passing override of the resolved principal (the shipped tool and the claude-opus-5 program both do this), or apply every passing override with no allowance, or count the allowance per principal.
- Hidden cases: hidden-a (allowance 3, a K118 row passes at the first seq, third K042 passing row is cut), hidden-b (allowance 4, two K118 rows first, third K042 row cut), hidden-c (allowance 2, one K042 applied then K118 consumes, K042 cut); mutation-allowance (shipped corpus, t-atlas 5 -> 1, OV-K118-x consumes the unit, OV-K042-auth not applied).
- Checks failed: first-only 0.3548 (4 hidden docs); no allowance 0.2581; allowance per principal 0.2581 (4 hidden docs + mutation_allowance).
- Shipped data: allowance 5 is not binding, K042 has one passing row; nothing separates (W5).
- Interactions: the applied set feeds L2 (timeout sum), L7 (risk terms) and L1 (max_records sum).

## L2 make-it-match repair: rev 1 rows carry seconds

- Rule text: `environment/data/override_deltas.json` line 6: "timeout_ms_delta is a delta in milliseconds; a rev 1 row stores it in whole seconds." Ranges line 7: "timeout_ms_delta -5 to 5 on rev 1 rows and -900 to 900 on rev 2 rows."
- Reflex reading: read the field as milliseconds (its name). The shipped control then reports mismatch for t-atlas (raw 1455 vs stored 6450). The plausible repair that makes the control match is "small values are seconds" (|v| < 100), which matches every shipped row because shipped rev 2 values are all >= 100.
- Hidden cases: rev 2 rows under 100 ms (hidden-a 75 applied, 40 on K118; hidden-b 4 applied, -60 on K118; hidden-c 90 on K118 and 50 cut) and rev 1 rows at awkward values (5, -3, 0, 1, -4, -1). All inside the stated ranges.
- Checks failed: raw ms reading 0.5161 (hidden policy + trace + config); |v|<100 heuristic 0.5161 (hidden policy + trace + config, the trace through ledger_controls on hidden-c).
- Shipped data: never contradicts the rule (all rev 1 rows are -5..5, all rev 2 rows >= 100).

## L7 rounding per item: risk contribution

- Rule text: `environment/data/risk_weight_rounding.txt` lines 2-3: "terms = risk_weight_base of the principal and the risk_delta of every applied override" / "contribution = sum of round_half_up(term * mult_bps / 1000) over the terms". The old worked example was removed (W6).
- Reflex reading: add the deltas first and round the scaled sum once (the old file and the solver program both do this).
- Hidden cases: hidden-a 61+2+2=65 (sum 66), hidden-b 61+4+1=66 (sum 67), hidden-c 61+3=64 (sum 65); mutation-risk (OV-K042-auth risk_delta 2 -> 3, per-term 64, sum 65).
- Checks failed: sum rounding 0.7419 (hidden curve + mutation_risk).
- Shipped data: 61.275 -> 61 and 2.15 -> 2 sum to 63, same as 63.425 -> 63, so shipped does not separate.
- Interaction: risk_threshold converges to 51 on every corpus, so the lever shows only in threshold_curve.contribution; the policy document is not double paid.

## L1 green control, wrong answer: ledger controls

- Rule text: `environment/data/override_deltas.json` line 11: "controls gives, per tenant, the number of stored rows and the sums of max_records_delta and of timeout_ms_delta in milliseconds over every stored row of that tenant, whatever its status, window, version or allowance; it is a parse and count control for this file only." Field shape: `output_field_spec.txt` line 16 (`ledger_controls`).
- Reflex reading: once the control turns green (after the L2 heuristic) take the resolved numbers as right. The control is honest (W7): it checks parsing and counting only, and a ledger reader that balances it can still select and apply the wrong rows.
- Hidden cases: hidden-b corrupts the stored t-f003 row count (expected "mismatch"); every hidden corpus has balanced t-atlas controls while the applied set differs from the first-only/no-allowance readings.
- Checks failed: controls trusted, never recomputed 0.8387 (hidden trace).

## Carried-over levers (unchanged values, leak sentences retired)

Half-open window (WIN-PRE ends at the instant; inclusive end 0.1290), version gate (OV-K042-v099 / WIN-AUTH-V099), B9 vs B7, client version v205, seconds base timeout, tier index, convergence. Each is now stated once in the file that holds its data (override_precedence.conf, policy_version_map.json `selection`, stale_version_rules.txt, units_reference.txt, convergence_spec.txt line 6 + parquet metadata `tier`).

## Reflex replay

OUT/agent_program, minimally adapted to the new layout (WORK/adapt_reflex.py: ledger sorted by seq, make-it-match control, first passing row): 0.1613 (5/31). Original artifacts 0.0968 (3/31); original program crashes on the new data.

## P12 r2 (QC v2 fixes, board 47d0997)

- Version gate, row half (match_version): new separating case hidden-a OV-K042-a8 (active K042, WIN-AUTH v100 window, row version v099, placed after OV-K118-a1 while allowance remains). Reference and oracle skip it; a window-version-only solver applies it, uses up the allowance and loses OV-K042-a5. Variant "window-version only" 1.0000 before, 0.3548 after (loss 20/31). Effect: harder.
- Trace resolution order (W11): hidden_dependency_trace now also needs boot_manifest.toml, bundle_ledger.jsonc, principal_role_index.yaml, override_deltas.json in that relative order. Effect: harder.
- Rerun check (F2): reference equality dropped (byte identity, canonical form, policy differs from shipped). Every variant that failed it loses 1/31 less; L7 sum rounding 0.2903 -> 0.2581 (ratio 0.889, trap FAIL on L7, see p12_r2 RECHECK_FIX).
- All other r2 fixes (instruction wording, judge R5/R7/R10, TRUTH heading): none on every lever.

## P12 v3 r3 (QC v3 fixes, board f06feb3)

- F1 (TS-26): the init/set rebuild check feeds authoritative values (w3). Every lever that lost the old w5 config check loses 5 less; after share / F1-adjusted before share = 0.939 on every lever. Effect: none on the lever readings (the payment moved, the separating hidden cases stay).
- M1 (TS-13): five w1 per-artifact shipped checks; P 31 -> 33; shipped-only presentation, no lever reads it. Effect: none (ratio 31/33 = 0.939).
- P3 (AL-27): hidden-c row OV-K042-c0 (row v100 on the v099 window WIN-AUTH-V099) makes the window half of the version gate decide; window-version-dropped mutant m14 0 -> 15/33. Effect: harder (carried-over version gate).
- P2: decoy_alias_table.jsonc renamed principal_alias_table.jsonc. Effect: none.
- Judge (R3, R7, R10), solve.sh paths, descriptions: none on every lever.
- Lever losses after (P = 33): L3 allowance 18 (0.545), L2 rev 1 seconds 10 (0.303), L7 per-term 8 (0.242), L1 controls 5 (0.152). v0 agent program 12/33 = 0.364 (was 5/31 = 0.161: +3 rebuild check, +4 split).
