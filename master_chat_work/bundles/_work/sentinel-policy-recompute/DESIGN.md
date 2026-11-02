# DESIGN sentinel-policy-recompute

## Harden P9 v2 r1 (23 Oct 2026)

Baseline claude-opus-5 0.7778 = 0.5 x tests 1.000 + 0.5 x judge 15/27. Tests-only was 1.000: every trap was spelled out in instruction.md line 5 and restated as key=value lines in reconciliation_rules.conf, clamp_rules.txt and ledger comments.

Changes:
- override_deltas.json is an ordered ledger: `conventions` (9 plain sentences), rows with `seq`, `rev`, `tenant`, and a per-tenant `controls` block. quota_limits.cfg gains `[override_allowance]`.
- Levers L3 (tenant allowance consumed in seq order across principals), L2 (rev 1 rows store seconds), L7 (risk terms rounded one by one), L1 (honest parse and count control). See LEVERS.md.
- Leak sentences retired: instruction trap list, reconciliation_rules.conf rule keys and notes, clamp warning, worked rounding example, `ignore` line, decoy labels and comments. Each rule is stated once in the file governing its data. Tier key written into convergence_spec.txt line 6 and the tier parquet metadata (IN-13 condition).
- output_field_spec.txt: dependency_trace gains `applied_overrides` and `ledger_controls`; header says resolve writes the three documents.
- Shipped tool.zip: same bugs plus a raw-reading ledger control (`ledger_controls`) and `applied_overrides` in its trace.
- Tests: 17 checks (P12 v3 r3), P = 33, negatives -11 (weights from the kit set 5/3/1/-3/-5). Whole-doc on hidden corpora 15 (45.5%), init/set rebuild on hidden corpora 3, mutation + validate 9, canonical rerun 1, five per-artifact shipped checks 5 (15.2%). Hidden corpora are built inside the test from the embedded corpus by rewriting only override_deltas.json and quota_limits.cfg.
- Verifier: `_grant_read` staging, nobody-uid kill after killpg, serialised runs, `[check]` messages; K8 litellm pin.
- Judge: batched, 15 criteria, P = 37; J2 x4 (R12-R15), J3 (R9), J4 (R10, +3 maintainable cli.py, P12 v3 r3).
- Shipped answers unchanged: 285 / 3 / 2250 / 51 (contribution now 63).

## Harden round 2 (24 Oct 2026, 0074a64)

Probe 1 (b0332e7aa626): tests 33/33, judge 16/37, overall 71.62. Opus read every rule file at step 9 and implemented L3/L2/L7/L1 at the first write; primary cause 4 (levers weak by design). See OUT harden_r2/DIAGNOSIS.md.

Changes:
- N1 replaces L3: override_allowance keyed by region (quota_limits.cfg), tenant_catalog.xml gains t-borealis/t-cinder/t-aurora; t-aurora (K301, r-north) added to principal_role_index.yaml and tenant_multiplier_table.xlsx.
- N2 replaces L2: timeout_ms_delta unit by version cutover in units_reference.txt; rev neutral; shipped rev regenerated to agree with the cutover.
- N3 replaces L7 as a counted lever: admit attribute on every window; admit and draw_order lines in override_precedence.conf. L7 kept as graded noise, L1 as N2 amplifier.
- override_deltas.json conventions: rev meaning, timeout pointer to units_reference.txt, single value ranges, draw pointer; allowance and rev-seconds sentences removed.
- Tests: 12 positive checks, P = 44: three `_hard` w5 families (n1-a/b, n2-a/b, n3-a/b), coupling policy/curve/trace w5 on hidden-a..d, rebuild 3, mutations 3+3, validate 3, rerun 1, one merged shipped check 1 (2.3%). Corpora rewrite override_deltas.json, quota_limits.cfg, effective_windows.xml and units_reference.txt only.
- Judge: R11 observable (profiles by running repaired sentinel-ctl), R12 N2, R13 N1, R14 N3 conduct; solve.py self_check_ledger prints check R12-R15 ok.
- Shipped answers unchanged: 285 / 3 / 2250 / 51 (contribution 63).

## Harden round 3 (25 Oct 2026)

Probe 2 (bundle after r2): tests 44/44, judge 14/37 (R9 fired), overall 68.92. Fuzz on the probe-2 program, 307 corpora: 0% differing on every lever; primary cause 4 (each rule named its separating case). See OUT harden_r3/DIAGNOSIS.md.

Changes:
- N4 timeout pool (H7 re-entry): every window in effective_windows.xml gains `timeout_pool` (WIN-AUTH 1200); override_precedence.conf line 7 states the pool share, the drop below 100 and the second share of the whole pool across the rows that held; override_deltas.json conventions line 10 points to it. Truth = caldermoor reading (fits branch not checked again).
- N4 is the only counted lever (master decision; PL note in LEVERS.md). N1-N3 feeders, L7 noise, L1 amplifier, unchanged.
- Tests: 14 positive checks, P = 52: new hidden_timeout_pool_hard w5 (pool-a, pool-b) and mutation_pool_cut_reshares_timeout w3; hidden-c reworked so the pool drops a row (policy test); mutation-risk now a one-value mutation of the pooled hidden-c. Corpora also rewrite timeout_pool attributes and an aux window pool.
- Judge: R16 +3 own timeout pool ledger; 16 criteria, P = 40; solve.py self_check_pool prints check R16 ok.
- reward.toml weights 0.5/52 and 0.5/40.
- Shipped answers unchanged: 285 / 3 / 2250 / 51 (contribution 63).

## Test-hardening round t1 (26 Oct 2026, board b7e15f9)

Probe 4 (bundle after r3; judge before the d0f1870 rebuild): tests 52/52, rubric 40, final 70.0. The agent read every rule file first and transliterated each sentence (OUT harden_t1/DIAGNOSIS.md). Master QL 26 Oct: tests 100 is never deliverable.

Changes:
- Five quiet rules (S6), one sentence plus one toy example each: Q1 running timeout floor (units_reference.txt:8-9), Q2 reissued override_id (override_deltas.json:6), Q3 param_key_aliases span (override_deltas.json:4), Q4 requires order (override_precedence.conf:7, field named at override_deltas.json:11; replaces the retry cap), Q5 superseded carry (override_deltas.json:13). Shipped data fires none and shows no new key or field.
- Tests: six new checks, P = 80: five owned w5 (q1-a/b .. q5-a/b, generated per seed with own RNG, whole documents exact) and the rare-pair check w3 (combo-a/b). Old corpora rebuilt unchanged (documents byte-equal, quiet rules fire 0). reward.toml test_output 0.5/80.
- Oracle CORRECT_CLI implements Q1-Q5; self-checks unchanged. Judge d0f1870 kept exactly (no new probe).
- Measured: each rule wrong alone 90.0 (span/window readings 93.75), all-but-one 90.0, first write 65.0, probe-4 program 65.0.
- Shipped answers unchanged: 285 / 3 / 2250 / 51 (contribution 63).

## Test-hardening round t2 (27 Oct 2026, board 4a82a12)

Blind round-1 read of the t1 bundle (ecb5b69): tests 80/80 after a 5-minute first write. Every Q rule was a row filter or counter and was transliterated (OUT harden_t2/DIAGNOSIS.md).

Changes:
- U (S3 unique fit): optional top-level `reports` in override_deltas.json; convergence_spec.txt:7 fixes iteration_divisor by the standing curve reports, recomputed per role through the full draw; no single fit -> unresolved (iterations [seed], converged and risk_threshold null; output_field_spec.txt:14-15). Range 6..14 at reconciliation_rules.conf:3.
- D1 (derived state, order): a reset withdraws every curve report at a lower seq (override_deltas.json line 15; seq unique across rows and reports, line 5).
- D2 (derived state, revision chain): statuses withdrawn and reinstated (line 14; override_precedence.conf:2); a reinstated row adds the deltas of the last active row of its id at a lower seq.
- Oracle CORRECT_CLI: reinstated_from/deltas_of, carried_of per principal, report_fits over the conf range, null verdict. Self-checks and judge unchanged.
- Tests: four new checks (w5, w5, w5, w3) on generated corpora utie-a/b, udecoy-a/b, d1-a/b, d2-a/b, combo2-a/b (own RNG). P = 98; reward test_output 0.5/98. The 28 old corpora give identical documents.
- Measured: new lever alone 91.84, Q alone 88.78, first write 58.16, blind round-1 program 86.73 (COST_TABLE.md).
- Shipped answers unchanged: 285 / 3 / 2250 / 51.

## Test-hardening round t3 (27 Oct 2026, board 3022cae)

Blind round-2 read of the t2 bundle (16ab9fc): tests 98/98 after a 5-minute first write; every rule was a filter, counter or a 9-candidate loop (OUT harden_t3/DIAGNOSIS.md). Master: no more stated filter rules; add a computational core.

Changes:
- R (computational core): resolve also writes `ledger_repair.json` (output_field_spec.txt:4 and :17). override_deltas.json conventions[14] (line 17) defines spare rows (withdrawn; superseded without carry; any row with a later row of the same override_id; never the source of a reinstated row in force), a repair (spare rows whose removal makes stored rows, max_records sum and ms timeout sum equal controls; empty set counts), the objective (smallest total absolute timeout in ms, cutover unit), the tie-break (ascending seq lists compared one by one) and the null verdict, with one toy example. Objective and constraints only, no method. instruction.md:5 states the 60 s limit per resolve run (existing test timeout).
- Shipped instance: t-atlas controls now 6 rows / 22 / 2250 ms (override_deltas.json:3214) -> repair [3, 6] (8 spare-or-not rows, 2 spare). Other 13 tenants ok.
- Hidden: rbig, rtie, runit, rspare, rall (a/b, own RNG `sentinel-<family>-<seed>`); each corpus has two repaired filler tenants with 58-72 spare rows and k = 8 cheap planted rows, plus one null tenant. Spare rule depends on Q2 (reissue), Q5 (carry), D2 (reinstated) readings; cost depends on N2 cutover.
- Tests: five R checks w5 (reconciles = feasibility on rbig and runit; cheapest, tie, unit, spare = whole document), hidden_rare_repair_pairs_hard w3 (rall: tie, unit and spare together) and hidden_fresh_state_corpora_hard w5 (seed-3 corpora of the nine quiet families) so all-but-one stays <= 92. Weights kept in the QC set {1,3,5}. P = 131; reward test_output 0.5/131. Existing check code byte-unchanged (diff of test_body.py adds lines only); corpora that keep the shipped controls now show t-atlas mismatch in the trace, reference and oracle agree.
- Oracle CORRECT_CLI: spare(), cheapest_repair() (visits k-sets in order of total cost), writes ledger_repair.json; solve.py checks the shipped {"t-atlas": [3, 6]}.
- Measured: blind r2 78.63 (six R checks only), greedy/naive/full table/(count,sum) table/halves 78.63, all-but-one 90.08, first write 64.89; Docker reference <= 0.26 s per corpus, exact table, halves and every k-subset time out at 60 s on all 10 R corpora (COST_TABLE.md t3).
- Shipped answers unchanged: 285 / 3 / 2250 / 51.

## Gate v3.6 harden (27 Oct 2026, board 217875e)
Run a7 (07363dd): tests 80.69, rubric 19.51, final 50.1; lost only the 6 ledger_repair checks by hidden-scale TIMEOUT; judge paid R2 and the vacuous handler criterion. Smallest-change route (master note 4): test lever and check bodies unchanged, judge rebuilt. OUT harden_g36_217875e/DESIGN.md.

Changes:
- QC v7 fixes F1 (drop handler criterion), F2 (R6-R8 w3), F3 (shipped config w3 + shipped profiles w3; rebuild bytes assert deleted), F5 (instruction.md:7 wording), F6 (TRUTH.md:52 cite). F4 not applied (TS-23 warn, 40 checks).
- Judge: new probes R10 version-map rerun and R11 unit-cutover rerun (w3), R12 code quality w1 (maintainable cli.py naming an unreadable reference file; false on the shipped file), R13 artifact paths, R14-R16 honesty negatives. 16 criteria, positive 37, negative 11. reward.toml 0.5/146, 0.5/37.
- Oracle self-check: two new rerun blocks, unreadable-input block kept, plain prints.
- Predicted a7: tests 118/146 = 80.82, rubric 4/37 = 10.81 (R12 counted passed), final 45.82 (COST_TABLE.md).
