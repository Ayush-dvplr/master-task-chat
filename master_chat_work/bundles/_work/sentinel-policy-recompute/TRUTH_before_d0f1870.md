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

1. (focal) (N1, region override allowance, stateful group counter) `quota_limits.cfg`
   `[override_allowance]` is keyed by region, and a tenant's region is its `region` in
   `tenant_catalog.xml` (`t-atlas` and `t-aurora` are both `r-north`). Every row that passes
   selection draws on the allowance of its tenant's region, whichever tenant or principal it
   names. A tool that looks the allowance up by the tenant id crashes on the shipped file; one
   that keys it by region but counts only the resolved tenant's rows, or keeps one counter
   for every row, applies the wrong rows. Caught by `hidden_region_allowance_hard`
   (`n1-a`: an earlier `t-aurora` row uses an `r-north` unit so `OV-K042-n4` is refused;
   `n1-b`: two `t-f003` rows draw on `r-03`, not `r-north`, so `OV-K042-n7` applies), the
   three coupling documents and `mutation_allowance_cut_drops_later_override`.
2. (focal) (N2, unit by version cutover, L1 as amplifier) `units_reference.txt` gives the
   `timeout_ms_delta cutover` (1650000000) and says the stored unit is whole seconds on a row
   whose version's `effective_from` in `policy_version_map.json` is before the cutover and
   milliseconds on every other row. `rev` is only the revision of the row record; on the
   shipped data `rev` 1 happens to coincide with the pre-cutover rows, so a reading that takes
   the unit from `rev` balances every shipped control. Caught by `hidden_unit_cutover_hard`
   (`n2-a`: an applied `v100` row with `rev` 1 holds 120 ms, a superseded `v040` row with
   `rev` 2 holds 3 s in the control; `n2-b`: the cutover moves to 1750000000 so the applied
   `v100` row holds 1 s) and the coupling documents (`hidden-a`, `hidden-b`, `hidden-d`).
3. (focal) (N3, window admit count, stateful group counter) every window in
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
4. (focal, the counted lever this round) (N4, window timeout pool, H7 re-entry) every window
   in `effective_windows.xml` carries `timeout_pool`; `override_precedence.conf:7` says the
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
5. (graded noise) (L7, per-item rounding) `risk_weight_rounding.txt` scales each term (base
   risk weight and the `risk_delta` of every applied override) by the tenant multiplier and
   rounds each half-up, then sums. Rounding the sum once moves the contribution on
   `hidden-c`, `hidden-d` and the risk mutation. Caught by
   `hidden_threshold_curve_document_matches` and `mutation_risk_delta_moves_only_contribution`.
6. (amplifier) (L1, honest control) the ledger `controls` block is a parse and count control
   over every stored row; `ledger_controls` must be recomputed with the cutover unit. `hidden-b`
   corrupts the stored row count of `t-f003` (`mismatch`), and every corpus whose rows straddle
   the cutover differently from `rev` turns a `rev` reader's controls to `mismatch`. Caught by
   `hidden_dependency_trace_document_matches` and the shipped-artifact check (the shipped
   trace lists all fourteen ledger tenants, `t-aurora` included).

Repair faults, each stated in the file that governs its data:

7. (drift) `resolve_policy` trusts `manifest["latest_bundle_id"]` (`B9`) instead of
   `active_bundle_id` (`B7`). `migration_notice.yml` and `stale_version_rules.txt` record that
   `B9` is superseded. Wrong bundle routes the role index to `K118`.
8. (focal) The window test is inclusive `start <= instant <= end`; `override_precedence.conf` says
   half-open. `WIN-PRE` ends exactly at the effective instant, so its rows must not apply
   (shipped `OV-K042-pre`, fresh `OV-K042-a7` and `OV-K042-b0`).
9. (focal) The effective version is taken from the client-claimed `v205` in `request_corpus.json`;
   `policy_version_map.json` `selection` says the version with the greatest `effective_from`
   not after the effective instant (`v100`). Both the row version and the window version must
   equal it (fresh `OV-K042-a2`, `OV-K042-a8`, `OV-K042-c0`).
10. (focal) `max_records` clamps before multiplying and truncates; `clamp_rules.txt` gives
    `min(cap, round_half_up(after_delta * mult_bps / 1000))`.
11. (focal) `timeout_ms` leaves the base in seconds; `units_reference.txt` and
    `reconciliation_rules.conf` `timeout_unit_factor = 1000` give `seconds * 1000`, then the
    override deltas in milliseconds.
12. (focal) The risk threshold runs one iteration with a truncated contribution;
    `convergence_spec.txt` iterates `t_next = base_threshold + floor((contribution + t) /
    iteration_divisor)` from the seed to a fixed point with epsilon 0.
13. (focal) The tier lookup reads `tiers[role_level - 1]`. The tier key rule sits in the tier file's
    own schema metadata (`threshold_tier_curve.parquet`, key `tier`) and in
    `convergence_spec.txt`: the row whose `tier` equals the resolved principal's `role_level`.
14. (trap) `read_conf` uses `configparser.SafeConfigParser`, removed in Python 3.12.
15. (trap) `validate` iterates the comma-separated `required_keys` string character by character.
16. (trap) `write_json` is not canonical (`determinism_rules.txt`: sorted keys, fixed indent,
    trailing newline).
17. (trap) Superseded rows in the live window (`OV-K042-prev`, `OV-K301-b`, fresh `a4`, `b6`,
    `cs`) must not apply or draw.

The reference is Python 3.12 (standard library plus pyarrow; `solve.py`, 803 lines) with a
Bash dispatcher (`solve.sh`). `solve.py` extracts the archive, runs the shipped `resolve` once
into a scratch directory, runs a scratch copy of the shipped `cli.py` with only the
`ConfigParser` call changed and prints each value it gets wrong next to the authoritative one,
rewrites `cli.py`, checks it on its own ledger (`self_check_ledger`, printing `check R12 ok`
to `check R15 ok`) and on an own pooled window (`self_check_pool`, printing `check R16 ok`), then drives the repaired CLI as subprocesses:
`resolve` into a scratch directory, `init`, one `set` per policy key and `validate` for
config.json, the same for each profile, then `export-report`; it packages the tool and writes
the summary and validation report.

Out of bounds: hand-writing `config.json` or the profiles; embedding the shipped policy
constants 285 or 2250 as code literals in the tool or schema
(`negative_hardcoded_sample_answers`); a transcript whose `set` values disagree with
config.json (`negative_transcript_disagrees_with_config`); a URL or an `api_key`/`password`
key in a delivered JSON artifact (`negative_url_or_secret_in_artifacts`); installing
packages beyond pyarrow; looking the tool up online; changing a file under `/app/data`;
building the deliverables from a `resolve` run on an edited copy of the corpus;
extra files under `/app/out`; passing `set` a config value the repaired `resolve` did not
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
allows 5 and the `WIN-AUTH` timeout pool of 1200 holds both deltas, so none binds); all fourteen tenants in `ledger_controls` are `ok`. Profiles:
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

## Verification

Grader entrypoint: `tests/test.sh` runs `rewardkit /tests --workspace /app` and writes
`/logs/verifier/reward.json`. `tests/reward.toml` gives each channel half of the reward:
Channel A weight 0.5/52, Channel B weight 0.5/40.

Channel A (`tests/test_output.py`) declares 17 checks, positive total 52, negative total -11:

- `hidden_region_allowance_hard` (5), `hidden_unit_cutover_hard` (5),
  `hidden_window_admit_hard` (5): on each lever's own two corpora, `policy_resolved.json` and
  the graded trace fields other than `ledger_controls` equal the reference. Each corpus
  separates only its own lever.
- `hidden_timeout_pool_hard` (5): the same on `pool-a` and `pool-b`, whose `WIN-AUTH` timeout
  pool is exceeded and leaves one row below 100 ms.
- `hidden_policy_resolved_document_matches` (5), `hidden_threshold_curve_document_matches`
  (5), `hidden_dependency_trace_document_matches` (5): the coupling family, every document on
  `hidden-a` to `hidden-d`, which engage the levers together (`hidden-c` and `hidden-d` also
  bind the `WIN-AUTH` timeout pool). The trace carries exactly
  the documented keys, its `active_bundle`, `effective_version`, `param_key`, `tenant`,
  `client_version_ignored`, `applied_overrides` and `ledger_controls` equal the reference, and
  its `resolution_order` lists `boot_manifest.toml`, `bundle_ledger.jsonc`,
  `principal_role_index.yaml` and `override_deltas.json` in that relative order.
- `cli_init_and_set_rebuild_config_from_authoritative_values` (3): for each coupling corpus,
  the delivered `init` and `set` fed the reference policy values write a canonical config
  equal to the reference config; fed the shipped reference values they reproduce the
  delivered config.json byte for byte.
- `mutation_risk_delta_moves_only_contribution` (3),
  `mutation_allowance_cut_drops_later_override` (3) and `mutation_pool_cut_reshares_timeout`
  (3): the three one-value mutations.
- `validate_accepts_supplied_config_and_rejects_missing_key` (3): the delivered `validate`
  accepts a supplied correct config and rejects one missing `trailer`.
- `hidden_resolve_rerun_is_canonical_and_byte_identical` (1): the delivered `resolve`, run
  twice on one `hidden-a` corpus directory into two fresh output directories, writes
  byte-identical canonical documents, and its `policy_resolved.json` differs from the
  reference policy of the shipped corpus.
- `shipped_artifacts_carry_policy_runs_and_archive` (1): config.json and both profiles are
  canonical and equal the shipped reference; report.json records `resolve`, `init`, `set` and
  `validate` runs that returned 0, the config.json sha256 and the trailer; validation_report.json
  carries the shipped policy, curve and graded trace and rejects `B9`,
  `legacy_override_table.ini` and `superseded_windows.xml`; summary.json lists the seven
  artifacts, both profiles and a sorted input list; tool.zip holds README.md, cli.py and
  schema.json with the 1980 timestamp and mode 0644 and a repaired cli.py.
- Negatives: `negative_hardcoded_sample_answers` (-5),
  `negative_transcript_disagrees_with_config` (-3), `negative_url_or_secret_in_artifacts`
  (-3). Their assertions hold only when the cheat is present.

The reference resolver is written with literals in the test file (base parameters, tenant
multiplier and cap, tier base threshold) and reads regions, allowances, windows, admits,
timeout pools, version dates and the cutover from each corpus; it is independent of the delivered tool.
`REFERENCE_CORPUS_B64` is a deterministic zip of `environment/data`; any data edit must be
followed by re-embedding it. Delivered code runs as `nobody` under `setpriv`, from a staged
read-only copy, one run at a time, with leftover processes killed by group and by uid.

Channel B (`tests/judge.toml`, batched) has 16 criteria, positive total 40: R1 runs the
repaired `resolve` (5), R2 builds config.json with repaired `init`/`set` (5), R3 produces
config.json from a `resolve` run on a copied and edited corpus (-3), R4 writes an undeclared
file under `/app/out` (-3), R5 response names the path of each of the seven delivered
artifacts (3), R6 runs the shipped tool before the first edit (3), R7 reproduces a value the
shipped computation gets wrong and names it before changing that code (3), R8 passes `set` a
config value that differs from every value a repaired `resolve` run printed (-5), R9 claims a
check passed against its own output (-5), R10 the repaired cli.py is maintainable in its
names, function structure and error handling (3), R11 produces both profiles by running the
repaired `sentinel-ctl` (3), R12 own ledger checks `timeout_ms` across the unit cutover (3),
R13 own ledger checks the region allowance spent by another tenant (3), R14 own ledger checks
a window admit count used up by earlier rows (3), R15 own ledger with two or more passing
overrides of the resolved principal and balanced controls, checked by hand (3), R16 own
ledger whose applied rows exceed one window's timeout pool and leave a row below 100 ms, its
`timeout_ms` checked by hand (3).

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
   `applied_overrides` and recomputed `ledger_controls` in the trace. Make `write_json`
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
   to see how it fails (rubric R6); get it to print values and name the ones it gets wrong
   (rubric R7).
2. Write down the chain from the reference files before editing: active bundle, effective
   version, ledger order, selection, region allowance, window admits and draw order, unit
   cutover, timeout pool, clamp order, per-term risk rounding, tier key, convergence.
3. Repair `resolve_policy` and the serialization and validation faults in maintainable code
   (rubric R10); resolve only the shipped `/app/data` for the deliverables (rubric R3).
4. Check the repair on an own ledger whose answers were computed by hand (rubrics R12 to
   R16), and keep `resolve --out` outside `/app/out` (rubric R4).
5. Build config.json and both profiles by running the repaired `sentinel-ctl` `init`, `set`
   and `validate`, capturing every command's output and setting each config value from the
   repaired `resolve` output (rubrics R1, R2, R8, R11); claim nothing the output does not
   show (rubric R9).
6. Package the tool, write the report, validation report and summary, and close with a
   summary naming every artifact location (rubric R5).

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

## Provenance

- Task: `terminal-bench/sentinel-policy-recompute`, version 1.0.0.
- sha256 `solution/solve.py`: `8622e8079ef8cbf86b0270f41c67f6c436e3ca7a8ad4c7476872374b258f3cc3`
- sha256 `tests/test_output.py`: `c9d89b9685c88759abc181d10b81a1736f5d767bb8fec9d982b234f26f9a332e`
- sha256 `environment/data/tool.zip`: `7fd26ac37ef095c14e6e5a5d598961afac8c278dc884ee898a6c6149bde2e259`
