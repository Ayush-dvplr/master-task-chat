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

# Harden round 2 (24 Oct 2026) - current lever set, supersedes L3/L2/L7 above

Lever set N1 + N2 + N3 with L1 as N2's amplifier and L7 kept as graded noise. Scores: oracle with one wrong reading, tests channel, P = 44 (WORK/single_lever.py, WORK/trap/after_h2_single_lever.txt).
COUPLING: every passing row draws in one global seq stream from two counters (region allowance N1, window admit N3); the applied set then feeds the timeout sum whose unit is N2. One wrong counter changes the applied set and moves max_records, retry, timeout and contribution together; hidden-a..d engage all three, so a single misreading fails all three coupling checks.

## N1 region override allowance (H6 group counter keyed wider than the tenant)
- Rule: `quota_limits.cfg:7` "# override_allowance is keyed by region; the region of a tenant is its region in tenant_catalog.xml", values lines 9-23 (r-north = 5); draw: `override_precedence.conf:6`. Shipped: t-aurora (r-north, K301) shares r-north with t-atlas; its shipped rows do not pass (OV-K301-a v040, OV-K301-b superseded), so nothing separates on shipped data.
- Reflex reading: allowance per tenant (probe-1 program filters `row["tenant"] == tenant`), or one counter for every row.
- Hidden: n1-a (t-aurora row uses r-north first, second K042 row refused), n1-b (t-f003 rows in r-03 must not draw r-north), hidden-a, hidden-c, hidden-d, mutation-allowance (r-north 1).
- Alone: per-tenant 21/44 (52.3% lost), global counter 24/44 (45.5%), off 21/44.

## N2 timeout unit by version cutover (H3, L1 amplifier)
- Rule: `units_reference.txt:6-7` cutover 1650000000; whole seconds when the row's version effective_from (policy_version_map.json) is before the cutover, milliseconds otherwise. `rev` neutral (conventions line 5).
- Reflex reading: unit from rev (shipped rev agrees with the cutover, so the shipped control reconciles under both readings), or raw ms.
- Hidden: n2-a (applied v100 rows with rev 1 in ms; superseded v040 rev 2 row in seconds for the control), n2-b (cutover moved to 1750000000: v100 rows are seconds), hidden-a/b/c/d.
- Alone: rev reading 29/44 (34.1%), raw 29/44.

## N3 window admit count (H6 counter keyed by window across tenants)
- Rule: `effective_windows.xml` attribute `admit`; `override_precedence.conf:5` admit, `:6` draw_order ("a row refused by either draws neither").
- Reflex reading: ignore admits, or count only the resolved tenant's rows.
- Hidden: n3-a (t-f003 row takes the single WIN-AUTH admit, K042 row refused, WIN-AUX row applied), n3-b (WIN-AUX admit 1), hidden-b, hidden-c, hidden-d (both draw-order directions), mutation-risk base (hidden-c).
- Alone: off 21/44 (52.3%), resolved-tenant only 21/44; draw_order either direction 29/44 (34.1%).

## L7 (noise) and L1 (amplifier)
- L7 summed rounding 36/44 (curve, mutation_risk); L1 trusted controls 39/44 (trace; hidden-b corrupt t-f003).

## Reflex gate
- Probe-1 program (OUT/agent_program, adapted only for the region key): 0.1591 delivered, 0.1818 rebuilt, 0.1364 unadapted (<= 0.20).

# Harden round 3 (25 Oct 2026) - N4 timeout pool, the only counted lever

Probe 2 (bundle after r2): tests 44/44, judge 14/37, overall 68.92. Fuzz of the probe-2 program on 307 corpora: 0% differing for N1, N2, N3, L7, L1 (OUT harden_r3/DIAGNOSIS.md). Each N rule named its own key, file and separating case, so Opus wrote all three right at its first cli.py (trajectory step 32).

PL note (master decision 25 Oct): this is the last round; N4 is the only counted lever and N1-N3 stay as feeders of the applied set. This knowingly breaks the ">= 3 independent levers" rule of LEVER_RULES section 1; the master accepted it because overall was already < 70 and only tests = 100 failed the gate.

COUPLING: the applied set chosen by N1 (region allowance) and N3 (window admit) in the global seq draw, with N2 setting each row's milliseconds, is the set of rows that share each window's timeout_pool (N4) across tenants and principals; timeout_ms of the resolved key = base + the pooled amounts of its own rows.

## N4 timeout pool (H7 re-entry: the pool is shared again across the rows that held 100 or more)
- Rule: `override_precedence.conf:7` timeout_pool line; pool value is the `timeout_pool` attribute of every window in `effective_windows.xml` (WIN-AUTH 1200, range 600-1500); pointer in `override_deltas.json:10` ("the timeout delta it adds is the amount set by timeout_pool"). Wording follows the caldermoor F2 rewrite: no "by the same rule"; the amount and method are written out ("every millisecond of the pool is shared again, floor(pool * its delta / summed delta of the rows whose added delta was 100 or more), across only those rows").
- Truth (caldermoor reading, master 25 Oct): positive deltas of one window's applied rows; sum <= pool -> own delta; else first share floor(pool*d/sum); rows below 100 add none; survivors split the whole pool floor(pool*d/sum of survivors' deltas); the fits branch is not checked again. Zero or negative deltas add their own delta.
- Reflex reading (measured on the probe-2 program, OUT harden_r3/agent_program): ignores the pool (its cli.py sums raw deltas, L251-255, L325). Constructed one-fact-wrong readings: fits test taken again on the second share; first share kept; only the dropped milliseconds shared again; no drop; pool shared only by the resolved key's rows.
- Hidden: pool-a (WIN-AUTH pool 1000; K003 t-f003 66, K042 231, K042 516, K118 220 -> 2771; agent 2747), pool-b (pool 960; K003 t-cinder 95, K042 562/152/158 -> 2958), hidden-c (pool 1000; c4 520, c5 K118 400, c6 90 -> c6 drops, 2565; agent 2610), hidden-d (cutover seconds, pool 1200 binds -> 1400), mutation-pool (pool-b with pool 900 -> 2899; agent 2872), mutation-risk (hidden-c base -> 2565).
- Checks failed by any wrong reading: hidden_timeout_pool_hard 5, hidden_policy_resolved_document_matches 5, mutation_risk_delta_moves_only_contribution 3, mutation_pool_cut_reshares_timeout 3 = 16/52 (30.8%).
- Differential fuzz (OUT harden_r3/proto/proto_pool_result_v2.json, 300 corpora): probe-2 program differs on 111/300 (37%); mutants fits_recheck 33, no_reentry 111, leftover 89, no_drop 111, mine_only 88. Shipped answer 2250 under every reading (WIN-AUTH pool 1200 holds 250 + K118 delta), so Never 11 holds.
- Judge: R16 +3 own timeout pool ledger; oracle self_check_pool prints `check R16 ok` (solve.py:695).

## Feeders after r3 (P = 52)
- N1 off 29/52, N2 37/52, N3 29/52, draw_order 37/52, L7 44/52, L1 47/52 (OUT harden_r3/local/single_lever.txt).

## Reflex gate
- Probe-2 program 36/52 = 0.6923 (> 0.20). Not strengthened: master target for this last round is one genuine Opus miss with tests 70-90; the 0.20 gate would need N1-N3 rewrites, which the master ruled out.

# Test-hardening round t1 (26 Oct 2026, board b7e15f9) - five quiet rules (S6)

Probe 4 (bundle after the r3 data, judge before d0f1870): tests 52/52, rubric 40, final 70.0. The agent read every rule file before writing cli.py and transliterated each sentence (OUT harden_t1/DIAGNOSIS.md). L1, L2, L3, L7, N1-N4 and the carried-over levers are kept unchanged with their checks and weights; the d0f1870 judge is kept exactly (no new probe: solve.sh prints no toy-corpus witness for Q1-Q5).

Each new rule is one plain sentence plus one toy example on invented values, in the file that owns its family. Shipped data fires none of them and shows none of the new keys or fields (no `param_key_aliases`, no `requires`, no `carry`; the shipped running timeout never falls below 1000). Every hidden corpus built for a rule fires it at least twice; the old corpora fire none (documents byte-equal to the pre-t1 reference).

| id | rule | file:line | reflex reading (habit of a quick program) | wrong document it yields |
|---|---|---|---|---|
| Q1 | running timeout floor 1000 ms, applied override by override in ascending seq | units_reference.txt:8-9 | base + sum of added amounts (probe-4 cli.py:406), or one clamp after the sum | timeout_ms below 1000 or too low after a dip and recovery |
| Q2 | reissued override_id: only the highest-seq row is that override; earlier rows pass no selection, draw no unit | override_deltas.json:6 | every row independent | extra applied row, extra unit drawn (later rows starve) |
| Q3 | `param_key_aliases` entries map alias to principal while effective_instant lies in half-open [start, end); outside, the row belongs to no principal; it draws either way | override_deltas.json:4 | param_key == resolved key only; or alias mapped without the span | missing or extra applied rows |
| Q4 | `requires`: row applied only when the named override was applied earlier in the same draw (lower seq); else refused, draws neither unit (replaces the retry cap, per master go note 2) | override_precedence.conf:7, override_deltas.json:11 | field ignored; or order-free check (named row applied anywhere) | extra applied row; extra units drawn |
| Q5 | superseded row with `carry` (max_records_delta or risk_delta) adds that one delta for its principal when its window contains effective_instant and row and window carry the effective version; not applied, draws nothing, not listed | override_deltas.json:13 | superseded rows skipped; or carry taken whatever the window | max_records or contribution off; or carry from a closed window |

## Grading (P = 80)
- Owned tests w5 (tests_qc W2 allows 5/3/1 only): hidden_running_timeout_floor_hard (q1-a, q1-b), hidden_reissued_override_hard (q2-a, q2-b), hidden_principal_alias_span_hard (q3-a, q3-b), hidden_requires_order_hard (q4-a, q4-b), hidden_superseded_carry_hard (q5-a, q5-b): whole policy_resolved, threshold_curve and graded dependency_trace (incl. ledger_controls) exact. Each owned corpus fires only its own rule (G1a per-row ownership: generator `accepted()` rejects a corpus where another rule fires).
- Combo test w3: hidden_rare_rule_pairs_hard (combo-a, combo-b) plants seven pairs of two quiet rules on one record (T4): P1 Q3+Q4, P2 Q2+Q3, P3 Q1+Q3, P4 Q3+Q5, P5 Q2+Q4, P6 Q1+Q2, P7 Q5+Q2; own RNG `random.Random("sentinel-combo-<seed>")`.
- Each rule wrong alone (primary reading): 8/80 = 10%; all-but-one 72/80 = 90.0; first write (all five skipped) 52/80 = 65.0. See COST_TABLE.md.
- Weights of the old checks unchanged; reward.toml test_output 0.5/80 = 0.00625.

# Test-hardening round t2 (27 Oct 2026, board 4a82a12) - unique fit and derived state

Blind round-1 read (ecb5b69) scored 80/80: every Q rule was a filter or counter on the current row, transliterated in one pass (OUT harden_t2/DIAGNOSIS.md). Round 2 adds two shapes a careful single-pass reader does not finish: a quantity fixed only by evidence across several records (S3 unique fit) and state built from earlier records (derived state). All earlier levers, checks and weights are kept; P 80 -> 98.

| id | rule | file:line | habit reading (careful first-pass program) | wrong document |
|---|---|---|---|---|
| U | iteration_divisor fixed by the standing curve reports: the divisor under which every standing report, recomputed for its role by the same draw and rules, converges to its reported value; none fixed -> unresolved (nulls) | convergence_spec.txt:7, range reconciliation_rules.conf:3, nulls output_field_spec.txt:14-15, report form override_deltas.json conventions line 15 | divisor 10 from the conf (blind r1); first fitting divisor (H8); fit to the first report only | wrong iterations, contribution unchanged, risk_threshold numeric where null is due |
| D1 | a reset withdraws every curve report at a lower seq | override_deltas.json line 15 (order: line 5) | every curve report counts; only the first reset counts | no fit (unresolved) or a different divisor |
| D2 | reinstated row selects like active and adds the deltas of the last active row of its override_id at a lower seq; withdrawn never selects | override_deltas.json line 14, override_precedence.conf:2 | reinstated not drawn (blind r1: status != active); own deltas; first active row | wrong applied_overrides, max_records, retry, timeout, contribution |

- Master go 1: U states no search (no "try each", no count words); the range sits where iteration_divisor is defined. No toy example for U; D1 and D2 have one each on invented ids (OV-Z1, seq 3..12).
- Master go 2: witnesses are recomputed through the full draw (allowance, admit, aliases, reissue, requires, carry, reinstated), so in combo2 at least 2 of the Q2-Q5 wrong readings move the fitted divisor (generator check). Q1 changes timeout only and cannot move a risk fit.
- Master go 3: D2 chains of length >= 3 (active -> withdrawn -> reinstated, active -> active -> withdrawn -> reinstated, and in combo2 active -> withdrawn -> reinstated -> superseded/withdrawn); D1 corpora hold two resets each withdrawing a report that alone would change the fit. Planted in their own corpora and combo2 (not every hidden corpus) so each lever owns 8.2% (G1a).
- Grading: hidden_unique_divisor_fit_hard w5 (utie-a/b tie -> unresolved, udecoy-a/b decoy -> 14), hidden_curve_reset_hard w5 (d1-a/b), hidden_reinstated_chain_hard w5 (d2-a/b), hidden_rare_state_pairs_hard w3 (combo2-a resolves 12, combo2-b tie). Own RNG `sentinel-<family>-<seed>`.
- Measured: each new lever alone 91.84; Q alone 88.78; first write 58.16; blind r1 86.73 (COST_TABLE.md t2).

# Test-hardening round t3 (27 Oct 2026, board 3022cae) - computational core R

Blind round-2 read (16ab9fc) scored 98/98: U, D1, D2 and Q1-Q5 were each a filter, counter or 9-candidate loop (OUT harden_t3/DIAGNOSIS.md). Round 3 adds one figure that the docs define by objective and constraints only: the cheapest ledger repair. Earlier levers, checks and weights are kept byte-unchanged; P 98 -> 133.

| id | rule | file:line | habit reading | wrong document |
|---|---|---|---|---|
| R | ledger_repair.json: for each tenant whose ledger_controls is mismatch, the set of its spare rows whose removal makes row count, max_records_delta sum and timeout_ms_delta sum (ms) equal its controls entry, with the smallest total absolute timeout in ms; equal totals -> seq list first compared one by one; none -> null | override_deltas.json:17 (conventions[14], toy example on invented seqs 2..9), output_field_spec.txt:4 and :17, instruction.md:5 (60 s per resolve run) | greedy (k cheapest), (count, records) knapsack then check timeout, exact (count, records, timeout) table, halves by seq, all k-subsets | wrong set, null where a repair exists, or no document within 60 s |
| R.tie | equal totals -> earlier seq list | override_deltas.json:17 | last set found / larger list | other optimal set |
| R.unit | cost in ms, pre-cutover rows x1000 (units_reference.txt:6-7) | override_deltas.json:17 "in milliseconds" | raw field value as cost | set with a pre-cutover row |
| R.spare | spare excludes carry rows (Q5), the in-force row of a reissued id (Q2) and the protected source of a reinstated chain (D2) | override_deltas.json:17 | every superseded row spare; reissued earlier rows not spare; reinstated source spare | set holding a non-spare twin |

- Shipped instance: t-atlas stored controls edited to {rows 6, max_records_delta_sum 22, timeout_ms_delta_sum_ms 2250}; repair [3, 6] (C(8,2)); solve.py checks it.
- Hidden: 10 corpora (rbig, rtie, runit, rspare, rall x seed 1, 2; own RNG `sentinel-<family>-<seed>`), each with 2 repaired filler tenants of 58-72 spare rows (k = 8 planted cheap rows) and 1 null tenant (stored max_records sum skewed by 1). No stated size or count bound.
- Grading (w5 each, plus hidden_rare_repair_pairs_hard w3 on rall where tie, unit and spare meet; hidden_fresh_state_corpora_hard w5 on seed-3 corpora of the nine quiet families): hidden_ledger_repair_reconciles_hard (feasibility only: keys, null verdicts, spare rows, all three figures reconcile; rbig + runit), hidden_ledger_repair_cheapest_hard (rbig whole doc), _tie_hard (rtie), _unit_hard (runit), _spare_hard (rspare). reward.toml test_output 0.5/131 (P = 131).
- Measured: COST_TABLE.md t3.

## Gate v3.6 harden (217875e)
- Test lever R (ledger_repair, P-1) unchanged: 28/146 = 19.18% after the F3 split; hidden corpora, weights, 60 s limit byte-unchanged.
- Judge probe band (P-5): two new probes for acts the a7 run skipped, R10 version-map rerun (policy_version_map.json effective_from of the resolved version) and R11 unit-cutover rerun (units_reference.txt timeout_ms_delta cutover), w3 each; R6-R8 back to w3 (F2); R10 handler criterion dropped (F1, vacuous on shipped cli.py); R12 code quality w1 (JD-18), false on the shipped cli.py. Predicted a7 rubric 10.81, final 45.82 (COST_TABLE).

## P12 fix QC v8 (3157183)
- No lever touched. Restored tool-use check `shipped_config_produced_by_repaired_tool` w1 (shipped config bytes); P 146 -> 147; lever R 28/147 = 19.05% (ratio 0.993 of 19.18%). R12 reworded only (weight 1 unchanged). Lever effects: R none, Q1-Q5 none, U/D1/D2 none, N1-N4 none, judge band none.
