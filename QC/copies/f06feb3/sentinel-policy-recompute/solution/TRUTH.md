# TRUTH.md - sentinel-policy-recompute

## Defect

The source archive at `/app/data/tool.zip` holds `sentinel-ctl`, a stdlib-plus-pyarrow
policy compiler for a multi-tenant access-control bundle. Its `resolve` command crashes on
Python 3.12, and once that is fixed its compiled security numbers still drift from the
authoritative policy through several independent faulty computations. Every value needed is
present in `/app/data`. The task is to diagnose and correct the faulty computations inside
the tool, reconstruct the authoritative policy by traversing a chained reference corpus,
and drive the repaired tool to emit the deterministic artifacts. The grader does not stop at
the shipped corpus: it reruns the delivered `resolve` on three fresh corpora that keep the
file layout and the stated value ranges and rewrite only the override ledger and the tenant
override allowance, plus two one-value mutations of the shipped corpus, and grades each
document `resolve` writes whole.

Ledger faults (the shipped corpus does not separate these faults; the fresh corpora do):

1. (focal) (L3, stateful ledger) `override_deltas.json` is an ordered ledger (`seq`). Every row that
   passes selection (`override_precedence.conf`: active status, half-open window containing
   the effective instant, override row and window both on the effective version) uses one unit of its
   tenant's allowance from `quota_limits.cfg` `[override_allowance]`, in ascending `seq` across
   all rows of the tenant whichever principal they name; a passing row after the allowance is
   used up is not applied; every applied row adds its deltas. The ledger `conventions` state
   this once. The shipped tool applies only the first passing row of the principal. In the
   fresh corpora another principal of `t-atlas` (`K118`) passes earlier and the allowance cuts
   a later `K042` row, so first-only, no-allowance, and principal-only-allowance readings each
   give a different `max_records`, `retry_limit`, `timeout_ms` and `applied_overrides`.
   Caught by `hidden_policy_resolved_document_matches`,
   `hidden_threshold_curve_document_matches`, `hidden_dependency_trace_document_matches` and
   `mutation_allowance_cut_drops_later_override`.
2. (focal) (L2, make-it-match repair) The conventions define `timeout_ms_delta` as milliseconds and
   say a `rev` 1 row stores it in whole seconds. The shipped tool reads it raw, so its
   `ledger_controls` for `t-atlas` says `mismatch` against the stored control (which sums
   milliseconds). The tempting repair that makes the shipped control pass, treating any
   value below 100 as seconds, also balances the shipped data, because every shipped rev 2
   row is at least 100. Fresh corpus A and B carry rev 2 rows of 75, 40, 4, -60 and -90 ms and
   rev 1 rows of 5, -3, 2, 0 and 1 s; the stated ranges (`-5 to 5` on rev 1, `-900 to 900` on
   rev 2) allow both. Caught by `hidden_policy_resolved_document_matches` and
   `hidden_dependency_trace_document_matches`.
3. (focal) (L7, per-item rounding) `risk_weight_rounding.txt` scales each term (the base risk weight
   and the `risk_delta` of every applied override) by the tenant multiplier and rounds each
   half-up on its own, then sums. Rounding the summed weight once gives a contribution one
   higher on every fresh corpus (65 vs 66, 66 vs 67, 64 vs 65) and on the risk mutation (64 vs
   65). The shipped corpus gives 63 either way (61 + 2 vs round(63.425)). Caught by
   `hidden_threshold_curve_document_matches` and `mutation_risk_delta_moves_only_contribution`.
4. (focal) (L1, honest green control) The ledger `controls` block gives per tenant the stored row
   count and the sums of `max_records_delta` and of `timeout_ms_delta` in milliseconds over
   every stored row whatever its status, window, version or allowance, and the conventions say
   it is a parse and count control for this file only. A tool that reaches `ok` everywhere can
   still apply the wrong rows: the control is blind to selection and allowance. Fresh corpus B
   corrupts the stored row count of `t-f003`, so a tool that never recomputes reports `ok`
   where `mismatch` is right. Caught by `hidden_dependency_trace_document_matches`.

Repair faults, each stated in the file that governs its data:

5. (drift) `resolve_policy` trusts `manifest["latest_bundle_id"]` (`B9`) instead of
   `active_bundle_id` (`B7`). `migration_notice.yml` and `stale_version_rules.txt` record that
   `B9` is superseded. Wrong bundle routes the role index to `K118`.
6. (focal) The window test is inclusive `start <= instant <= end`; `override_precedence.conf` says
   half-open. `WIN-PRE` ends exactly at the effective instant, so its rows must not apply
   (shipped `OV-K042-pre`, fresh `OV-K042-a2` and `OV-K042-c1`).
7. (focal) The effective version is taken from the client-claimed `v205` in `request_corpus.json`;
   `policy_version_map.json` `selection` says the version with the greatest `effective_from`
   not after the effective instant (`v100`).
8. (focal) `max_records` clamps before multiplying and truncates; `clamp_rules.txt` gives
   `min(cap, round_half_up(after_delta * mult_bps / 1000))`.
9. (focal) `timeout_ms` leaves the base in seconds; `units_reference.txt` and
   `reconciliation_rules.conf` `timeout_unit_factor = 1000` give `seconds * 1000`, then the
   override deltas in milliseconds.
10. (focal) The risk threshold runs one iteration with a truncated contribution;
    `convergence_spec.txt` iterates `t_next = base_threshold + floor((contribution + t) /
    iteration_divisor)` from the seed to a fixed point with epsilon 0.
11. (focal) The tier lookup reads `tiers[role_level - 1]`. The tier key rule sits in the tier file's
    own schema metadata (`threshold_tier_curve.parquet`, key `tier`) and in
    `convergence_spec.txt`: the row whose `tier` equals the resolved principal's `role_level`.
12. (trap) `read_conf` uses `configparser.SafeConfigParser`, removed in Python 3.12.
13. (trap) `validate` iterates the comma-separated `required_keys` string character by character.
14. (trap) `write_json` is not canonical (`determinism_rules.txt`: sorted keys, fixed indent,
    trailing newline).
15. (trap) Superseded rows in the live window (`OV-K042-prev`, fresh `a4`, `b7`, `c6`) and active
    rows on the `v099` window (`OV-K042-v099`, fresh `a7`, `c5`) must not apply.

The reference is Python 3.12 (standard library plus pyarrow; `solve.py`, 674 lines) with a
Bash dispatcher (`solve.sh`). `solve.py` extracts the archive, runs the shipped `resolve` once
into a scratch directory, rewrites `cli.py`, then drives the repaired CLI as subprocesses:
`resolve` into a scratch directory, `init`, one `set` per policy key and `validate` for
config.json, the same for each profile, then `export-report`; it packages the tool and writes
the summary and validation report.

Out of bounds: hand-writing `config.json` or the profiles; embedding the shipped policy
constants 285 or 2250 as code literals in the tool or schema
(`negative_hardcoded_sample_answers`); a transcript whose `set` values disagree with
config.json (`negative_transcript_disagrees_with_config`); a URL or an `api_key`/`password`
key in a delivered JSON artifact (`negative_url_or_secret_in_artifacts`); installing
packages beyond pyarrow; looking the tool up online; changing a file under `/app/data`;
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
`["OV-K042-auth"]`; every tenant in `ledger_controls` is `ok`. Profiles: dev 275 / 4 / 2125,
prod 310 / 3 / 2500.

Fresh corpora (rows listed in `tests/test_output.py` `HIDDEN_HEADS`; the shipped `t-atlas`
head rows are replaced, all rows renumbered, controls recomputed):

- `hidden-a`, allowance 3: applied `OV-K042-a3`, `OV-K042-a5`; 274 / 3 / 7075;
  contribution 65. `OV-K042-a8` (row version `v099` inside the `v100` window `WIN-AUTH`,
  before the allowance is used up) is rejected on its row version, so a reading that checks
  only the window version applies it and cuts `OV-K042-a5`.
- `hidden-b`, allowance 4, `t-f003` control corrupted: applied `OV-K042-b3`, `OV-K042-b5`;
  263 / 5 / 2004; contribution 66; `t-f003` `mismatch`.
- `hidden-c`, allowance 2: applied `OV-K042-c2`; 284 / 2 / 3000; contribution 64.
- `mutation-risk` (shipped, `OV-K042-auth` `risk_delta` 3): contribution 64, policy unchanged.
- `mutation-allowance` (shipped, `t-atlas` allowance 1): `OV-K118-x` uses the allowance,
  nothing applied to `K042`; 285 / 2 / 2000; contribution 61.

Every fresh corpus converges to 51 through `[40, 50, 51, 51]`.

## Verification

Grader entrypoint: `tests/test.sh` runs `rewardkit /tests --workspace /app` and writes
`/logs/verifier/reward.json`. `tests/reward.toml` gives each channel half of the reward:
Channel A weight 0.5/31, Channel B weight 0.5/34.

Channel A (`tests/test_output.py`) declares 12 checks, positive total 31, negative total -11:

- `hidden_policy_resolved_document_matches` (5): `policy_resolved.json` from the delivered
  `resolve` on each fresh corpus equals the reference document.
- `hidden_threshold_curve_document_matches` (5): `threshold_curve.json` on each fresh corpus.
- `hidden_dependency_trace_document_matches` (5): `dependency_trace.json` carries exactly the
  documented keys and its `active_bundle`, `effective_version`, `param_key`, `tenant`,
  `client_version_ignored`, `applied_overrides` and `ledger_controls` equal the reference;
  its `resolution_order` lists `boot_manifest.toml`, `bundle_ledger.jsonc`,
  `principal_role_index.yaml` and `override_deltas.json` in that relative order.
- `hidden_config_document_rebuilt_by_cli_matches` (5): on each fresh corpus, a config.json
  built by the delivered `init` and `set` from the delivered `resolve` output equals the
  reference config.
- `mutation_risk_delta_moves_only_contribution` (3) and
  `mutation_allowance_cut_drops_later_override` (3): the two shipped-corpus mutations.
- `validate_accepts_supplied_config_and_rejects_missing_key` (3): the delivered `validate`
  accepts a supplied correct config and rejects one missing `trailer`.
- `hidden_resolve_rerun_is_canonical_and_byte_identical` (1): the delivered `resolve`, run
  twice on one `hidden-a` corpus directory into two fresh output directories, writes
  byte-identical canonical documents, and its `policy_resolved.json` differs from the
  reference policy of the shipped corpus.
- `shipped_artifacts_follow_field_specs` (1): the seven delivered artifacts against the field
  specs and the shipped reference values, the archive layout, and a config rebuild through
  the delivered `init` and `set`.
- Negatives: `negative_hardcoded_sample_answers` (-5),
  `negative_transcript_disagrees_with_config` (-3), `negative_url_or_secret_in_artifacts`
  (-3). Their assertions hold only when the cheat is present.

The reference resolver is written with literals in the test file (base parameters, tenant
multiplier and cap, tier base threshold, windows) and is independent of the delivered tool.
`REFERENCE_CORPUS_B64` is a deterministic zip of `environment/data`; any data edit must be
followed by re-embedding it. Delivered code runs as `nobody` under `setpriv`, from a staged
read-only copy, one run at a time, with leftover processes killed by group and by uid.

Channel B (`tests/judge.toml`, batched) has 15 criteria, positive total 34: R1 runs the
repaired `resolve` (5), R2 builds config.json with repaired `init`/`set` (5), R3 modifies a
file under `/app/data` (-3), R4 writes an undeclared file under `/app/out` (-3), R5 response
names the path of each of the seven delivered artifacts (3), R6 runs the shipped tool before the first edit (3), R7 edits
the code that computes the resolved policy values (3), R8 passes `set` a config value
the repaired `resolve` did not print (-5), R9 claims a check
passed against its own output (-5), R10 the repaired cli.py contains an except clause that
discards an error and continues (-1), R11 profiles through the repaired CLI (3), R12 to R15 the agent builds its own
input for each lever and checks the resulting value (3 each).

Oracle expectation: `solution/solve.sh` drives every positive Channel A check to pass and
leaves every negative failing.

## Root cause

Every value is reachable from `/app/data`, but each rule sits in the file that holds the data
it governs, and the shipped data agrees with several wrong readings of the ledger rules. The
ledger header, the allowance table and the rounding file each state their rule once. Only a
solver who builds inputs the shipped corpus lacks (another principal spending the allowance
first, a rev 2 delta below 100 ms, two risk deltas that round differently one by one) can see
that a repair which balances the shipped control is still wrong.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool` safely; read `cli.py`, `schema.json`,
   `README.md`; run the shipped `resolve` once.
2. Repair `resolve_policy`: `ConfigParser`; active bundle; effective version from the
   instant; ledger in `seq` order; selection by status, half-open window and version; tenant
   allowance consumed across the tenant's passing rows; cumulative deltas; rev 1 timeout
   deltas times 1000; multiply, round half-up, then cap; per-term risk rounding; tier at the
   role level; reconciliation to a fixed point; `applied_overrides` and recomputed
   `ledger_controls` in the trace. Make `write_json` canonical and split `required_keys`.
3. Build an own ledger in a temporary copy of the data (another `t-atlas` principal passing
   first, an allowance of 3 that cuts the last passing row, a rev 2 delta of 60 ms, a rev 1
   delta of 2 s, two risk deltas of 2 that round differently one by one), run the repaired
   `resolve` on it and compare the printed values with hand-computed ones (269, 3, 4060,
   contribution 65).
4. Run `resolve` into a scratch directory outside `/app/out`.
5. Drive `init`, `set`, `validate` for config.json and each profile, capturing the
   transcript, then `export-report`.
6. Package the tool deterministically; write the validation report and summary.

## Ordered plan

1. Extract the tool, read it with the reference files, and run the shipped `resolve` once
   to see how it fails (rubric R6).
2. Write down the chain from the reference files before editing: active bundle, effective
   version, ledger order, selection, tenant allowance, rev units, clamp order, per-term risk
   rounding, tier key, convergence.
3. Repair `resolve_policy` and the serialization and validation faults (rubric R7); leave
   `/app/data` unchanged (rubric R3).
4. Check the repair on an own ledger whose answers were computed by hand (rubrics R12 to
   R15), and keep `resolve --out` outside `/app/out` (rubric R4).
5. Build config.json and both profiles through `init`, `set` and `validate`, capturing every
   command's output and setting each config value from the repaired `resolve` output
   (rubrics R1, R2, R8, R11); claim nothing the output does not show (rubric R9).
6. Package the tool, write the report, validation report and summary, and close with a
   summary naming every artifact location (rubric R5).

## Pitfalls

- First passing override only, or no allowance: fails every fresh corpus.
- Allowance counted for the resolved principal only: fails every fresh corpus and the
  allowance mutation.
- Timeout deltas read raw, or values below 100 taken as seconds: fails the policy and trace
  documents on the fresh corpora.
- Risk weight rounded once on the sum: fails the threshold curve on every fresh corpus and
  the risk mutation.
- Controls reported `ok` without recomputing: fails the trace document on corpus B.
- Inclusive window end: applies the `WIN-PRE` rows.

## Provenance

- Task: `terminal-bench/sentinel-policy-recompute`, version 1.0.0.
- sha256 `solution/solve.py`: `4711ee4af9a525ab0689382c0122c02552807ed685495428a6960c111a340d3c`
- sha256 `tests/test_output.py`: `16db19332652c707d27af28dc48a179a15b28ad03549cfa66ae67e1c08dc9128`
- sha256 `environment/data/tool.zip`: `7fd26ac37ef095c14e6e5a5d598961afac8c278dc884ee898a6c6149bde2e259`
