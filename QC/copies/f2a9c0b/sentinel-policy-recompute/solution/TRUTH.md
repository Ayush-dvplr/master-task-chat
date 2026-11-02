# TRUTH.md - sentinel-policy-recompute

## Defect

The source archive at `/app/data/tool.zip` holds `sentinel-ctl`, a stdlib-plus-pyarrow
policy compiler for a multi-tenant access-control bundle. Its `resolve` command crashes on
Python 3.12, and once that is fixed its compiled security numbers still drift from the
authoritative policy through several independent faulty computations. Every value needed is
present in `/app/data`. The task is to diagnose and correct the faulty computations inside
the tool, reconstruct the authoritative policy by traversing a chained reference corpus,
and drive the repaired tool to emit the deterministic artifacts. The grader does not stop at
the shipped corpus: it reruns the delivered `resolve` on twelve fresh corpora that keep the file
layout and the stated value ranges and rewrite only the override ledger, the region
allowances, the window admit counts and timeout pools (plus one extra `v100` window
`WIN-AUX`) and the unit cutover, plus three one-value mutations, and grades each document
`resolve` writes whole.

Ledger faults (the shipped corpus does not separate these faults; the fresh corpora do):

1. Region override allowance. `quota_limits.cfg`
   `[override_allowance]` is keyed by region, and a tenant's region is its `region` in
   `tenant_catalog.xml` (`t-atlas` and `t-aurora` are both `r-north`). Every row that passes
   selection draws on the allowance of its tenant's region, whichever tenant or principal it
   names. A tool that looks the allowance up by the tenant id crashes on the shipped file; one
   that keys it by region but counts only the resolved tenant's rows, or keeps one counter
   for every row, applies the wrong rows. Caught by `hidden_region_allowance_hard`
   (`n1-a`: an earlier `t-aurora` row uses an `r-north` unit so `OV-K042-n4` is refused;
   `n1-b`: two `t-f003` rows draw on `r-03`, not `r-north`, so `OV-K042-n7` applies), the
   three coupling documents and `mutation_allowance_cut_drops_later_override`.
2. Timeout unit by version cutover. `units_reference.txt` gives the
   `timeout_ms_delta cutover` (1650000000) and says the stored unit is whole seconds on a row
   whose version's `effective_from` in `policy_version_map.json` is before the cutover and
   milliseconds on every other row. `rev` is only the revision of the row record; on the
   shipped data `rev` 1 happens to coincide with the pre-cutover rows, so a reading that takes
   the unit from `rev` balances every shipped control. Caught by `hidden_unit_cutover_hard`
   (`n2-a`: an applied `v100` row with `rev` 1 holds 120 ms, a superseded `v040` row with
   `rev` 2 holds 3 s in the control; `n2-b`: the cutover moves to 1750000000 so the applied
   `v100` row holds 1 s) and the coupling documents (`hidden-a`, `hidden-b`, `hidden-d`).
3. Window admit count. Every window in
   `effective_windows.xml` carries `admit`; `override_precedence.conf` says a window admits
   at most that many applied rows and gives `draw_order`: passing rows draw in ascending `seq`
   across all rows of the ledger, a row is applied only when its region allowance and its
   window both have a unit left, an applied row uses one of each, and a row refused by either
   draws neither. Caught by `hidden_window_admit_hard` (`n3-a`: a `t-f003` row uses the one
   `WIN-AUTH` admit so `OV-K042-w3` is refused and `OV-K042-w4` in `WIN-AUX` applies; `n3-b`:
   `WIN-AUX` admits 1 so `OV-K042-w6` is refused), `mutation_risk_delta_moves_only_contribution`
   and the coupling documents. `hidden-d` grades both draw-order directions: `OV-F003-d2` is
   refused by `r-03` while `WIN-AUTH` still has admits and draws no admit; `OV-K042-d5` is
   refused by `WIN-AUTH` while `r-north` has a unit and draws no `r-north` unit, so
   `OV-K042-d6` applies.
4. Window timeout pool. Every window
   in `effective_windows.xml` carries `timeout_pool`; `override_precedence.conf:8` says the
   applied rows of one window whose millisecond timeout delta is above zero share that pool
   (any tenant or principal): at or below the pool each adds its own delta, otherwise each
   adds `floor(pool * delta / summed delta)`; a row then below 100 adds none and every
   millisecond of the pool is shared again across only the rows that held 100 or more, in
   proportion to their deltas. The second share does not test the fits branch again. A row
   whose delta is zero or below adds its own delta. Caught by `hidden_timeout_pool_hard`
   (`pool-a`: pool 1000, `OV-F003-p1` 66 / `OV-K042-p2` 231 / `OV-K042-p3` 516 /
   `OV-K118-p4` 220, `p1` drops and the other three share 1000 again, 2771; `pool-b`: pool
   960, `OV-C003-q1` 95 drops and the three `K042` rows share 960 again, 2958), the policy
   document on `hidden-c` (pool 1000, `OV-K042-c6` 90 drops, `c4` and `OV-K118-c5` share 1000
   again, 2565) and `hidden-d` (pool 1200 binds without a drop, 1400),
   `mutation_pool_cut_reshares_timeout` (`pool-b` with pool 900, 2899) and
   `mutation_risk_delta_moves_only_contribution` (on `hidden-c`). Reading the second share as
   a fresh pass that tests the fits branch again gives 2747 on `pool-a`; keeping the first
   share gives 2722; ignoring the pool gives 2610 on `hidden-c`.
4a. Running timeout floor. `units_reference.txt:8-9`: the timeout starts at
   the base in milliseconds and takes each applied override's added amount in ascending `seq`;
   whenever the running value falls below 1000 it is raised to 1000 before the next amount.
   Summing first, or one clamp after the sum, is wrong once a dip is followed by a rise.
   Caught by `hidden_running_timeout_floor_hard` (`q1-a`, `q1-b`) and the rare-pair check.
4b. Reissued override. `override_deltas.json` conventions: rows sharing an
   `override_id` are one override, the highest-`seq` row; earlier rows pass no selection and
   draw no unit; `controls` still count every stored row (the stored controls of `q2-a`,
   `q2-b`, `combo-a` and `combo-b` reconcile only that way). Caught by
   `hidden_reissued_override_hard` and the rare-pair check.
4c. Principal alias span. Optional top-level `param_key_aliases`
   (`alias`, `principal`, `start`, `end`): a row naming the alias is an override of the
   principal while the effective instant lies in the half-open span, of no principal outside;
   it draws either way. Caught by `hidden_principal_alias_span_hard` and the rare-pair check.
4d. Requires order. `override_precedence.conf:7`: a row with `requires` is
   applied only when the named override was applied earlier in the same draw; otherwise it is
   refused and draws neither unit. An order-free check (named row applied anywhere) is wrong.
   Caught by `hidden_requires_order_hard` and the rare-pair check.
4e. Carried clause. A superseded row with `carry` (`max_records_delta` or
   `risk_delta`) whose window contains the instant, row and window at the effective version,
   adds that one delta to its principal's `after_delta` or risk terms; it is not applied,
   draws nothing and is not listed. Caught by `hidden_superseded_carry_hard` and the
   rare-pair check. Shipped data has no alias, no reissued id, no `requires`, no `carry` and a
   running timeout that never falls below 1000, so 4a-4e leave every shipped value unchanged.
5. Per-term risk rounding. `risk_weight_rounding.txt` scales each term (base
   risk weight and the `risk_delta` of every applied override) by the tenant multiplier and
   rounds each half-up, then sums. Rounding the sum once moves the contribution on
   `hidden-c`, `hidden-d` and the risk mutation. Caught by
   `hidden_threshold_curve_document_matches` and `mutation_risk_delta_moves_only_contribution`.
6. Ledger controls. The ledger `controls` block is a parse and count control
   over every stored row; `ledger_controls` must be recomputed with the cutover unit. `hidden-b`
   corrupts the stored row count of `t-f003` (`mismatch`), and every corpus whose rows straddle
   the cutover differently from `rev` turns a `rev` reader's controls to `mismatch`. Caught by
   `hidden_dependency_trace_document_matches` and the shipped-artifact check (the shipped
   trace lists all fourteen ledger tenants, `t-aurora` included).

Repair faults, each stated in the file that governs its data:

7. `resolve_policy` trusts `manifest["latest_bundle_id"]` (`B9`) instead of
   `active_bundle_id` (`B7`). `migration_notice.yml` and `stale_version_rules.txt` record that
   `B9` is superseded. Wrong bundle routes the role index to `K118`.
8. The window test is inclusive `start <= instant <= end`; `override_precedence.conf` says
   half-open. `WIN-PRE` ends exactly at the effective instant, so its rows must not apply
   (shipped `OV-K042-pre`, fresh `OV-K042-a7` and `OV-K042-b0`).
9. The effective version is taken from the client-claimed `v205` in `request_corpus.json`;
   `policy_version_map.json` `selection` says the version with the greatest `effective_from`
   not after the effective instant (`v100`). Both the row version and the window version must
   equal it (fresh `OV-K042-a2`, `OV-K042-a8`, `OV-K042-c0`).
10. `max_records` clamps before multiplying and truncates; `clamp_rules.txt` gives
    `min(cap, round_half_up(after_delta * mult_bps / 1000))`.
11. `timeout_ms` leaves the base in seconds; `units_reference.txt` and
    `reconciliation_rules.conf` `timeout_unit_factor = 1000` give `seconds * 1000`, then the
    override deltas in milliseconds.
12. The risk threshold runs one iteration with a truncated contribution;
    `convergence_spec.txt` iterates `t_next = base_threshold + floor((contribution + t) /
    iteration_divisor)` from the seed to a fixed point with epsilon 0.
13. The tier lookup reads `tiers[role_level - 1]`. The tier key rule sits in the tier file's
    own schema metadata (`threshold_tier_curve.parquet`, key `tier`) and in
    `convergence_spec.txt`: the row whose `tier` equals the resolved principal's `role_level`.
14. `read_conf` uses `configparser.SafeConfigParser`, removed in Python 3.12.
15. `validate` iterates the comma-separated `required_keys` string character by character.
16. `write_json` is not canonical (`determinism_rules.txt`: sorted keys, fixed indent,
    trailing newline).
17. Superseded rows in the live window (`OV-K042-prev`, `OV-K301-b`, fresh `a4`, `b6`,
    `cs`) must not apply or draw.

The reference is Python 3.12 (standard library plus pyarrow; `solve.py`, 1214 lines) with a
Bash dispatcher (`solve.sh`). `solve.py` extracts the archive, runs the shipped `resolve` once
into a scratch directory (printing `check shipped run ok` with its failure), runs a scratch copy of the
shipped `cli.py` with only the `ConfigParser` call changed and prints each value it gets wrong
next to the authoritative one, names the defects (`check defects named ok`), rewrites `cli.py` (every
declared input read through one guard that stops the run with a message naming a missing or
malformed file), checks it on its own ledger (`self_check_ledger`, printing `ledger-check ok`)
and on an own pooled window (`self_check_pool`, printing `pool-check ok`), then drives the
repaired CLI as subprocesses: `resolve` into a scratch directory, `init`, one `set` per policy
key and `validate` for config.json, the same for each profile, then `export-report`; it
packages the tool and writes the summary and validation report. A second stage
(`solve.py --self-check`) runs the delivered tool on scratch copies of the corpus (window end
at the effective instant, a risk term on a half, a changed tenant multiplier, a changed
role_level, a removed input, a malformed input), recomputes three delivered values outside
the tool, prints one `check ... ok` line per probe, recomputed value and handler check, and leaves `/app/out`
unchanged.

Out of bounds: hand-writing `config.json`; embedding the shipped policy
constants 285 or 2250 as code literals in the tool or schema
(`negative_hardcoded_sample_answers`); a transcript whose `set` values disagree with
config.json (`negative_transcript_disagrees_with_config`); a URL or an `api_key`/`password`
key in a delivered JSON artifact (`negative_url_or_secret_in_artifacts`); a tool Python
file importing a module outside the standard library, pyarrow and the tool itself
(`negative_third_party_import_in_tool`); installing
packages beyond pyarrow; looking the tool up online; changing a file under `/app/data`;
building the deliverables from a `resolve` run on an edited copy of the corpus;
passing `set` a config value the repaired `resolve` did not
print.

## Load-bearing work

Seven artifacts are collected:

- `/app/out/config.json`
- `/app/out/report.json`
- `/app/out/tool.zip`
- `/app/out/profile_dev.json`
- `/app/out/profile_prod.json`
- `/app/out/validation_report.json`
- `/app/out/summary.json`

Shipped corpus values: `max_records` 285, `retry_limit` 3, `timeout_ms` 2250, `trailer`
`sentinel:policy:TASK:2c016d65`, `risk_threshold` 51, `param_key` `K042`, `tenant`
`t-atlas`, `effective_version` `v100`; threshold curve tier 4, base threshold 40,
contribution 63, iterations `[40, 50, 51, 51]`, converged 51; `applied_overrides`
`["OV-K042-auth"]` (`OV-K118-x` also applies, to `K118`; `WIN-AUTH` admits 3, `r-north`
allows 5 and the `WIN-AUTH` timeout pool of 1200 holds both deltas, so none binds); in `ledger_controls` thirteen tenants are `ok` and `t-atlas`
is `mismatch` (stored controls 6 rows, 22, 2250 ms against 8, -23, 550 ms recomputed), and
`ledger_repair.json` is `{"t-atlas": [3, 6]}` (its only spare rows, superseded `OV-K042-prev`
and pre-cutover `OV-K042-old`, -2 s = -2000 ms). Profiles:
dev 275 / 4 / 2125, prod 310 / 3 / 2500.

Fresh corpora (rows in `tests/test_output.py` `HIDDEN_HEADS`, settings in `VARIANTS`; the
shipped head rows with `seq` up to 8 are replaced, all rows renumbered, controls recomputed);
values are `max_records` / `retry_limit` / `timeout_ms`, contribution, applied overrides:

- `n1-a` (`r-north` 2): 280 / 3 / 2200, 63, `OV-K042-n2`.
- `n1-b` (`r-north` 2): 280 / 3 / 2120, 63, `OV-K042-n7`.
- `n2-a`: 274 / 3 / 2180, 63, `OV-K042-u1`, `OV-K042-u2`.
- `n2-b` (cutover 1750000000): 280 / 3 / 3000, 63, `OV-K042-u4`.
- `n3-a` (`WIN-AUTH` admit 1): 284 / 3 / 2150, 63, `OV-K042-w4`.
- `n3-b` (`WIN-AUX` admit 1): 280 / 3 / 2250, 62, `OV-K042-w5`, `OV-K042-w7`.
- `hidden-a` (`r-north` 2): 280 / 3 / 2080, 63, `OV-K042-a3`.
- `hidden-b` (`r-north` 4, `WIN-AUTH` admit 2, `t-f003` control corrupted): 274 / 3 / 2090,
  62, `OV-K042-b5`; `t-f003` `mismatch`.
- `hidden-c` (`WIN-AUTH` pool 1000): 274 / 3 / 2565, 66, `OV-K042-c4`, `OV-K042-c6`.
- `hidden-d` (`r-03` 1, `r-north` 3, `WIN-AUTH` admit 2, cutover 1750000000):
  274 / 3 / 1400, 66, `OV-K042-d3`, `OV-K042-d6`.
- `pool-a` (`WIN-AUTH` admit 6, pool 1000, `r-north` 6): 285 / 7 / 2771, 84, `OV-K042-p2`,
  `OV-K042-p3`; converges to 53.
- `pool-b` (`WIN-AUTH` admit 6, pool 960, `r-north` 6): 285 / 3 / 2958, 100, `OV-K042-q2`,
  `OV-K042-q3`, `OV-K042-q4`; converges to 55.
- `mutation-risk` (`hidden-c`, `OV-K042-c6` `risk_delta` 4): contribution 67, policy unchanged.
- `mutation-allowance` (`hidden-a`, `r-north` 1): `OV-K301-a1` uses the only unit, nothing
  applied to `K042`; 285 / 2 / 2000; contribution 61.
- `mutation-pool` (`pool-b`, pool 900): 285 / 3 / 2899, contribution 100.

Every other corpus converges to 51.

Generated corpora for rules 4a to 4e (`generate_spec(family, seed)` in `tests/test_output.py`,
own RNG `sentinel-<family>-<seed>`, accepted only when the owned rule fires at least twice and
no other rule of 4a to 4e fires); `max_records` / `retry_limit` / `timeout_ms`, contribution, converged:

- `q1-a` 285 / 6 / 1146, 78, 53 (3 floor raises); `q1-b` 285 / 6 / 1579, 74, 52 (2).
- `q2-a` 285 / 4 / 2517, 63, 51 (2 reissued rows); `q2-b` 285 / 2 / 2636, 73, 52 (3).
- `q3-a` 285 / 3 / 2859, 73, 52 (4 alias rows); `q3-b` 285 / 3 / 2792, 70, 52 (3).
- `q4-a` 285 / 3 / 2451, 66, 51 (2 refusals); `q4-b` 285 / 3 / 2644, 68, 51 (2).
- `q5-a` 275 / 2 / 2277, 75, 52 (2 carried rows); `q5-b` 274 / 2 / 2144, 81, 53 (2).
- `combo-a` 285 / 4 / 1162, 97, 55; `combo-b` 282 / 6 / 1228, 76, 52: seven pairs of two rules of
  4a to 4e on one record (alias row requiring a later row, reissued id reissued as an alias row,
  alias negative raised by the floor, superseded alias carry, requires naming a reissued id,
  reissued id raised by the floor, reissued id carried).

Generated corpora for the curve reports and reinstated rows (same generator, own RNG per
family; accepted only when the owned rule fires at least twice, no rule of 4a to 4e fires, and every reading of the other families leaves the
documents unchanged); `max_records` / `retry_limit` / `timeout_ms`, contribution, converged:

- `utie-a` 285 / 3 / 2161, 67, null; `utie-b` 285 / 3 / 2219, 64, null: two standing curve
  reports that divisors 13 and 14 both reproduce, so the threshold is unresolved
  (`iterations` `[40]`, `converged` and `risk_threshold` null).
- `udecoy-a` 285 / 2 / 2679, 66, 48; `udecoy-b` 285 / 2 / 2419, 62, 47: three standing reports
  fix divisor 14 alone; the first report alone also fits 13.
- `d1-a` 285 / 3 / 2447, 62, 51; `d1-b` 285 / 4 / 2682, 67, 51: two curve reports withdrawn by
  later resets; the standing reports fix 10; counting the withdrawn ones fits no divisor.
- `d2-a` 285 / 4 / 2921, 67, 51; `d2-b` 285 / 3 / 2435, 69, 52: three reinstated rows each add
  the deltas of the last active row of their override_id below them.
- `combo2-a` 285 / 3 / 1000, 85, 51 (divisor 12); `combo2-b` 285 / 4 / 1000, 100, null (tie):
  reports, resets and reinstated rows on alias, reissued, requires, carry and floor records.

Of the candidate divisors 6 to 14, the standing curve reports fit only 14 on `udecoy-a/b`, only
10 on `d1-a/b` and only 12 on `combo2-a`; both 13 and 14 fit on `utie-a`, `utie-b` and `combo2-b`.

Generated corpora for the ledger repair (own RNG per family; rows added only on filler tenants
at versions other than `v100`, so the three resolve documents follow the shipped chain; each corpus has two
repaired tenants with 60 to 71 spare rows and 8 rows to remove, and one tenant with no repair);
`ledger_repair.json` per tenant, rows and total absolute timeout:

- `rbig-a` `t-f007` 8, 275 ms; `t-f008` 8, 194 ms; `t-f005` null. `rbig-b` `t-f007` 8, 254 ms;
  `t-f008` 8, 244 ms; `t-f009` null.
- `rtie-a` `t-f003` 8, 239 ms; `t-f008` 8, 230 ms; `t-f009` null. `rtie-b` `t-f007` 8, 153 ms;
  `t-f008` 8, 177 ms; `t-f009` null (two cheapest sets per repaired tenant; spare twins).
- `runit-a` `t-f004` 8, 251 ms; `t-f006` 8, 322 ms; `t-f009` null. `runit-b` `t-f003` 8,
  361 ms; `t-f006` 8, 228 ms; `t-f000` null (pre-cutover rows of 1 s cost 1000 ms).
- `rspare-a` `t-f000` 8, 280 ms; `t-f006` 8, 255 ms; `t-f008` null. `rspare-b` `t-f000` 8,
  204 ms; `t-f008` 8, 253 ms; `t-f007` null (cheap twins that are not spare: carry rows,
  in-force reissued rows, protected reinstated sources).

## Verification

Grader entrypoint: `tests/test.sh` runs `rewardkit /tests --workspace /app` and writes
`/logs/verifier/reward.json`. `tests/reward.toml` gives each channel half of the reward:
Channel A weight 0.5/146, Channel B weight 0.5/37.

Channel A (`tests/test_output.py`) declares 40 checks, positive total 146, negative total -14:

- `hidden_region_allowance_hard` (5), `hidden_unit_cutover_hard` (5),
  `hidden_window_admit_hard` (5): on each rule's own two corpora (rules 1 to 3), `policy_resolved.json` and
  the graded trace fields other than `ledger_controls` equal the reference. Each corpus
  separates only its own rule.
- `hidden_timeout_pool_hard` (5): the same on `pool-a` and `pool-b`, whose `WIN-AUTH` timeout
  pool is exceeded and leaves one row below 100 ms.
- `hidden_running_timeout_floor_hard` (5), `hidden_reissued_override_hard` (5),
  `hidden_principal_alias_span_hard` (5), `hidden_requires_order_hard` (5),
  `hidden_superseded_carry_hard` (5): on the two generated corpora of each of rules 4a to 4e, every
  document (policy, curve, graded trace with `ledger_controls`) equals the reference.
- `hidden_rare_rule_pairs_hard` (3): the same on `combo-a` and `combo-b`.
- `hidden_unique_divisor_fit_hard` (5): every document on `utie-a`, `utie-b`, `udecoy-a` and
  `udecoy-b` (divisor fixed by the standing curve reports, or unresolved).
- `hidden_curve_reset_hard` (5): every document on `d1-a` and `d1-b` (resets withdraw earlier
  reports).
- `hidden_reinstated_chain_hard` (5): every document on `d2-a` and `d2-b` (reinstated rows).
- `hidden_rare_state_pairs_hard` (3): every document on `combo2-a` and `combo2-b`.
- `hidden_fresh_state_corpora_hard` (5): every document on `fresh-q1` to `fresh-q5`,
  `fresh-utie`, `fresh-udecoy`, `fresh-d1` and `fresh-d2` (seed 3 of each family above).
- `hidden_ledger_repair_reconciles_hard` (5): on `rbig-a/b` and `runit-a/b`,
  `ledger_repair.json` is keyed by the mismatched tenants, null exactly where no repair
  exists, and every list holds distinct spare-row seqs of its tenant whose removal makes the
  row count and both sums equal the stored controls (feasibility only).
- `hidden_ledger_repair_cheapest_hard` (5), `hidden_ledger_repair_tie_hard` (5),
  `hidden_ledger_repair_unit_hard` (5), `hidden_ledger_repair_spare_hard` (5): the whole
  `ledger_repair.json` equals the reference on `rbig`, `rtie`, `runit` and `rspare` (a and b).
  `resolve` runs under the stated 60-second limit.
- `hidden_rare_repair_pairs_hard` (3): the whole `ledger_repair.json` on `rall-a` and `rall-b`,
  where ties, pre-cutover rows and the spare reading meet on the same tenants.
- `hidden_policy_resolved_document_matches` (5), `hidden_threshold_curve_document_matches`
  (5), `hidden_dependency_trace_document_matches` (5): the coupling family, every document on
  `hidden-a` to `hidden-d`, which engage the ledger rules together (`hidden-c` and `hidden-d` also
  bind the `WIN-AUTH` timeout pool). The trace carries exactly
  the documented keys, its `active_bundle`, `effective_version`, `param_key`, `tenant`,
  `client_version_ignored`, `applied_overrides` and `ledger_controls` equal the reference, and
  its `resolution_order` lists `boot_manifest.toml`, `bundle_ledger.jsonc`,
  `principal_role_index.yaml` and `override_deltas.json` in that relative order.
- `cli_init_and_set_rebuild_config_from_authoritative_values` (3): for each coupling corpus,
  the delivered `init` and `set` fed the reference policy values write a canonical config
  equal to the reference config.
- `mutation_risk_delta_moves_only_contribution` (3),
  `mutation_allowance_cut_drops_later_override` (3) and `mutation_pool_cut_reshares_timeout`
  (3): the three one-value mutations.
- `validate_accepts_supplied_config_and_rejects_missing_key` (3): the delivered `validate`
  accepts a supplied correct config and rejects one missing `trailer`.
- `hidden_resolve_rerun_is_canonical_and_byte_identical` (1): the delivered `resolve`, run
  twice on one `hidden-a` corpus directory into two fresh output directories, writes
  byte-identical canonical documents, and its `policy_resolved.json` differs from the
  reference policy of the shipped corpus.
- `shipped_config_carries_policy_values` (3): config.json is canonical and equals the
  authoritative shipped config.
- `shipped_profiles_carry_policy_deltas` (3): profile_dev.json and profile_prod.json are
  canonical and each equals the shipped policy shifted by its profile deltas.
- `shipped_validation_report_grades_policy_and_branches` (3): validation_report.json carries
  the shipped policy, curve and graded trace and rejects `B9`, `legacy_override_table.ini` and
  `superseded_windows.xml`.
- `shipped_report_records_tool_runs_and_digest` (3): report.json records `resolve`, `init`,
  `set` and `validate` runs that returned 0, the config.json sha256 and the trailer.
- `shipped_summary_lists_artifacts_and_inputs` (3): summary.json lists the seven artifacts,
  both profiles and the sorted corpus file names as inputs.
- `shipped_tool_archive_is_pinned_and_repaired` (1): tool.zip holds README.md, cli.py and
  schema.json with the 1980 timestamp and mode 0644 and a repaired cli.py.
- Negatives: `negative_hardcoded_sample_answers` (-5),
  `negative_transcript_disagrees_with_config` (-3), `negative_url_or_secret_in_artifacts`
  (-3), `negative_third_party_import_in_tool` (-3). Their assertions hold only when the
  cheat is present.

The reference resolver is written with literals in the test file (base parameters, tenant
multiplier and cap, tier base threshold) and reads regions, allowances, windows, admits,
timeout pools, version dates, the cutover, aliases and the `requires` and `carry` fields from each corpus; it is independent of the delivered tool.
`REFERENCE_CORPUS_B64` is a deterministic zip of `environment/data`. Delivered code runs as `nobody` under `setpriv`, from a staged
read-only copy, one run at a time, with leftover processes killed by group and by uid.

Channel B (`tests/judge.toml`, batched) has 16 criteria, positive total 37, negative 11. The
probe band (R1 to R11, 33 of 37, 3 each) grades acts in the trajectory: R1 runs the shipped
tool before the first edit to `/app/tool/cli.py` and shows its failure; R2 resolves a corpus
it built whose effective instant equals a window end; R3 resolves a corpus it built with a
risk term on a half; R4 reruns on a copy with a changed tenant `mult_bps`; R5 reruns on a copy
with a changed `role_level`; R6, R7, R8 recompute `timeout_ms`
of config.json, the converged risk threshold of validation_report.json and `max_records` of
profile_prod.json outside the tool and compare; R9 names a defect of the shipped `cli.py`
before the first edit; R10 reruns on a copy with a changed `effective_from` of the effective
version in `policy_version_map.json` and shows the effective version change; R11 reruns on a
copy with a changed `timeout_ms_delta` cutover in `units_reference.txt` and shows `timeout_ms`
change. R12 the delivered `cli.py` is maintainable and stops on an unreadable or unparsable
reference file with a message naming it (1); R13 the response lists every delivered artifact
by path (3); R14 claims a check passed with no run after the last edit (-3); R15 states a
figure differing from the delivered file (-5); R16 overstates the size of a check it ran
after the last edit (-3).

Oracle expectation: `solution/solve.sh` drives every positive Channel A check to pass and
leaves every negative failing.

## Root cause

Every value is reachable from `/app/data`, but each rule sits in the file that holds the data
it governs, and the shipped data agrees with several wrong readings of the ledger rules: no
other `r-north` tenant passes selection, no window's admit count or timeout pool binds, and
every shipped row's `rev` matches its side of the unit cutover. Only a solver who builds inputs the shipped corpus
lacks (another tenant of the same region passing first, a window filled by other rows, a row
whose `rev` disagrees with its version date, a window whose timeout pool is exceeded) can see that a repair which balances the shipped
controls is still wrong.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool` safely; read `cli.py`, `schema.json`,
   `README.md`; run the shipped `resolve` once.
2. Repair `resolve_policy`: `ConfigParser`; active bundle; effective version from the
   instant; ledger in `seq` order across every tenant; selection by status, half-open window,
   window version and row version; region allowance by the tenant's catalog region and window
   admit count, drawn together, a refused row drawing neither; cumulative deltas; timeout
   delta unit from the cutover in `units_reference.txt`; timeout deltas shared through each
   window's `timeout_pool`, with the drop below 100 and the whole pool shared again; multiply, round half-up, then cap;
   per-term risk rounding; tier at the role level; reconciliation to a fixed point;
   `applied_overrides` and recomputed `ledger_controls` in the trace; reinstated rows draw
   with the deltas of the last earlier active row of their override_id; the divisor in force
   is the one the standing curve reports fix (each recomputed for its role from the same
   draw), `iteration_divisor` when none stands, and an unresolved threshold (seed-only
   iterations, null `converged` and `risk_threshold`) when they fix no single one; for each
   mismatched tenant, the cheapest repair over its spare rows in `ledger_repair.json` (the
   reference visits sets of the needed size in order of total cost, so the first cost level
   holding a repair ends the walk). Make `write_json`
   canonical and split `required_keys`.
3. Build an own ledger in a temporary copy of the data (an earlier `t-aurora` row spending an
   `r-north` unit, a `t-f003` row spending a `WIN-AUTH` admit, a `v100` row with `rev` 1, a
   pre-cutover row with `rev` 2, a row refused by its window that must not spend `r-north`),
   run the repaired `resolve` on it and compare with hand-computed values (applied `OV-SC-3`
   and `OV-SC-5`; 269, 3, 2062, contribution 65), and a second own ledger whose `WIN-AUTH`
   pool of 780 is exceeded and drops a `t-f003` row (applied `OV-PC-2`, `OV-PC-3`; 2780).
4. Run `resolve` into a scratch directory outside `/app/out`.
5. Drive `init`, `set`, `validate` for config.json and each profile, capturing the
   transcript, then `export-report`.
6. Package the tool deterministically; write the validation report and summary.

## Ordered plan

1. Extract the tool, read it with the reference files, and run the shipped `resolve` once
   to see how it fails (rubric R1); get it to print values and name the defects before
   editing (rubric R9).
2. Write down the chain from the reference files before editing: active bundle, effective
   version, ledger order, selection, region allowance, window admits and draw order, unit
   cutover, timeout pool, clamp order, per-term risk rounding, tier key, convergence.
3. Repair `resolve_policy` and the serialization and validation faults, with every exception
   unreadable or unparsable reference file stopping the run with a message naming it
   (rubric R12); resolve
   only the shipped `/app/data` for the deliverables.
4. Check the repair on an own ledger whose answers were computed by hand, and keep
   `resolve --out` outside `/app/out`.
5. Build config.json and both profiles by running the repaired `sentinel-ctl` `init`, `set`
   and `validate`, capturing every command's output and setting each config value from the
   repaired `resolve` output.
6. Package the tool, write the report, validation report and summary.
7. Probe the delivered tool on scratch corpora (rubrics R2 to R5, R10, R11) and recompute
   delivered values outside it (rubrics R6 to R8); claim nothing the output does not show
   (rubrics R14 to R16), and close with a summary naming every artifact location (rubric R13).

## Pitfalls

- Allowance looked up by tenant id: `resolve` fails on every corpus.
- Region allowance counted for the resolved tenant only, or one counter for every row: fails
  `hidden_region_allowance_hard` and the coupling documents.
- Timeout unit taken from `rev`, or deltas read raw: fails `hidden_unit_cutover_hard` and the
  policy and trace documents.
- Window admits ignored or counted for the resolved tenant only: fails
  `hidden_window_admit_hard`, the coupling documents and the risk mutation.
- A row refused by one counter still drawing the other: fails the coupling documents.
- Risk weight rounded once on the sum: fails the threshold curve and the risk mutation.
- Controls reported `ok` without recomputing: fails the trace document on `hidden-b`.
- Inclusive window end: applies the `WIN-PRE` rows.
- Timeout pool ignored: fails `hidden_timeout_pool_hard`, the policy document on `hidden-c` and
  `hidden-d` and both pooled mutations.
- Second share of the pool read as a fresh pass that tests the fits branch again, or the first
  share kept after the drop: fails `hidden_timeout_pool_hard` and the pooled mutations.
- Timeout floor applied once after the sum, or not at all; reissued rows drawn as separate
  rows; aliases or their span ignored; `requires` ignored or checked without order; superseded
  `carry` ignored or taken outside its window: each fails its own check and the rare-pair
  check, the rare state-pair check and the fresh state-corpora check (130/146).
- Divisor read from `iteration_divisor` while curve reports stand, the first divisor that fits
  taken without checking that it is the only one, or the fit tested on the first report
  only: fails `hidden_unique_divisor_fit_hard`, the rare state-pair and fresh checks (133/146).
- Curve reports withdrawn by a later reset still counted, or only the first reset honoured:
  fails `hidden_curve_reset_hard`, the rare state-pair and fresh checks (133/146).
- Reinstated rows skipped, drawn with their own deltas, or given the deltas of the first active
  row: fails `hidden_reinstated_chain_hard`, the rare state-pair and fresh checks (133/146).
- Ledger repair taken as the cheapest rows first, or as a table over row count and
  `max_records` sum then checked on timeout: wrong sets on every repair corpus (118/146). An
  exact table over count and both sums, or every set of the needed size: past 60 seconds on
  60 or more spare rows; a split into two halves likewise (118/146 each). Ties to the last set, raw
  pre-cutover cost, or a spare reading off by one of carry, reissue or reinstated source:
  two whole-document checks and the rare repair-pair check (133/146).

## Provenance

- Task: `terminal-bench/sentinel-policy-recompute`, version 1.0.0.
- sha256 `solution/solve.py`: `15ea5deaf73e2a885138a1bd25d4eaf9b41c34a7825c2c9ea040fdc7f82fd34b`
- sha256 `tests/test_output.py`: `f1d9d572707987256d0d2e8a21d6dd7be412437fa765f937a00c07325769c6d5`
- sha256 `environment/data/tool.zip`: `7fd26ac37ef095c14e6e5a5d598961afac8c278dc884ee898a6c6149bde2e259`
