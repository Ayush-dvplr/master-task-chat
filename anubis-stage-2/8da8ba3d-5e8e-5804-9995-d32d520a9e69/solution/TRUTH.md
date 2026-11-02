# TRUTH.md - 8da8ba3d-5e8e-5804-9995-d32d520a9e69

## Defect

The archive at `/app/data/tool.zip` ships a stdlib-only Python command named
`nonce-ctl` (`cli.py` plus a short `README.md`). The task is not only "fix
the CLI"; it is "fix the CLI *and drive it* to reconcile 50+ multi-format
security policy files into the full deliverable set under `/app/out/`".

The shipped `cli.py` carries these functional faults. The first three groups
are the fault classes the instruction names (argument routing, key
normalization, derivation arithmetic); the last two sit in artifact emission.

1. Argument routing, `init`. `cmd_init` reads `args.config`, but `init` is
   invoked with `--schema`/`--out` and `--config` is optional, so
   `args.config` is `None` and the read fails before anything is written.
   It also emits a nested `settings` group instead of flat scalars. The fix
   reads `args.schema` and emits six flat keys (`profile`, `producer`,
   `container`, `checksum`, `mode`, `trailer`).
2. Argument routing, subcommand selection. `add_subparsers(dest="command")`
   lacks `required=True`. A bare `python3 cli.py` reaches `args.func` and
   dies with an `AttributeError` traceback (exit code 1). The fix makes the
   subcommand required, so argparse prints usage and exits with code 2.
3. Key normalization, `set`. `cmd_set` writes `data[args.key.upper()] =
   args.value`: the key is uppercased and the value stays a string. The fix
   keeps the key verbatim and coerces the value. The shipped `coerce` also
   tests `s.isdecimal()`, which leaves negative integers as strings; the fix
   strips one leading `-` before the test.
4. Derivation arithmetic, `derive_values`, three places:
   - `pbkdf_iterations` is `base_pbkdf_iters + 2 ** max_tier`; the intended
     rule is `base_pbkdf_iters * 2 ** max_tier` (the `2 ** max_tier` term only
     reads as a scale factor, and `env_overrides.json` scales pbkdf
     multiplicatively);
   - `session_ttl_seconds` adds the MFA step reduction; a reduction is
     subtracted: `base_session_ttl - step_reduction + base ttl offset`;
   - `rate_limit_burst` is `rps * (base_rate_burst_factor + 1)`; the shipped
     `emit-profile` already uses `rps * base_rate_burst_factor`, which is
     the intended rule.
5. Emission, `checksum_manifest`. The shipped kind hashes a hard-coded list
   of 17 names and skips `report.json`, `tool.zip`, `validation_report.json`
   and `summary.json`. The fix hashes every file in `--out-dir` except the
   manifest itself (21 lines).
6. Emission, `policy_matrix`. Role rows and permission columns are not
   sorted. The shipped corpus already lists active roles and permissions in
   ascending order, so the fix (`sorted`) does not change the output.

The shipped file also carries an unused `import os` and an unused
`read_ini` helper; the reference build drops both. `validate`,
`emit-profile` and `export-report` compute correctly as shipped.

How the tests see each fault:
- `init`: `report_records_full_cli_transcript` runs the delivered CLI's
  `init` against the embedded schema and requires a flat result.
- subcommand selection: `repaired_cli_subcommand_is_required` asserts only
  a non-zero exit, which the shipped `AttributeError` path also produces,
  so this fault is not distinguished by the tests.
- `set`: `set_preserves_key_and_coerces_negative` runs `set --key
  Rotation_Days --value -42` against a probe file and requires the key
  verbatim with the integer `-42`.
- derivation: `config_matches_expected_derived_values`, both profile checks,
  `pbkdf_iterations_obeys_power_of_two_multiplier_law`,
  `rate_limit_burst_is_three_times_rps`, and the downstream artifact checks
  that compare against the expected config values.
- `checksum_manifest`: `checksum_manifest_matches_disk_bytes` requires one
  line for each of the 21 other artifacts.
- `policy_matrix` ordering: no test can see it on the shipped corpus.

The oracle (`solution/solve.py`, Python 3.12, stdlib only) extracts the
archive safely, replaces `cli.py` with a repaired build (`FIXED_CLI`), then
drives that CLI as real subprocesses: `init`, `derive`, `validate`, two
`emit-profile` runs, fifteen `emit-artifact` runs, and `export-report`. It
packages the repaired tool as `/app/out/tool.zip` with a sorted file list
and fixed timestamps so two builds are byte-identical, writes
`validation_report.json` and `summary.json` itself, and finally reruns the
`checksum_manifest` kind so the manifest hashes the finished files.

## Load-bearing work

22 artifacts land under `/app/out/`, and every one is graded. The
deterministic channel (`tests/test_output.py`) declares 30 positive
rewardkit checks summing to +112 and 6 negative checks summing to -24,
each weight living on its `criteria.<name>(weight=W)` registration. The
judged channel (`tests/judge.toml`) carries 10 criteria, 8 positive summing
to +26 and 2 negative summing to -8. `tests/reward.toml` gives each channel
half of the final reward (`test_output` at 0.5/112, `judge` at 0.5/26).

Deliverables at their exact absolute paths:

`/app/out/config.json` (flat scalar JSON, 25 keys, `sort_keys=True` with
two-space indent and a trailing newline) is the reconciled main
configuration, written by `derive`. The six string values (`checksum`,
`container`, `mode`, `producer`, `profile`, `trailer`) come from
`/app/data/config_schema.json` and `/app/data/defaults.json`. The nineteen
integer scalars are computed by `derive_values` inside `FIXED_CLI`, which
reads its inputs through small selector helpers (`active_threat_actors`,
`throttled_endpoints`, `active_rbac`, and so on) that `emit-artifact` reuses,
so every artifact filters the corpus the same way the counts do.

`/app/out/profile_dev.json` and `/app/out/profile_prod.json` are the two
environment profiles, written by `emit-profile`. Each starts from the
reconciled config, then adds the deltas from `/app/data/env_overrides.json`
and the session offsets of the matching row in
`/app/data/hardening_profiles.yaml`; `rate_limit_burst` is recomputed with
`base_rate_burst_factor` from `defaults.json`. `pbkdf_iterations` halves for
dev and doubles for prod through `pbkdf_scale_num`/`pbkdf_scale_den`. The
`trailer` ends with `:dev` or `:prod`.

`/app/out/report.json` is written by `export-report`. `commands` holds one
entry per recorded subprocess: the twenty runs the driver made before
`export-report`, each with the argv it executed, its return code and its
trimmed stdout, followed by the entry `export-report` writes for itself
(`sys.orig_argv`, return code 0 because the process exits 0 right after
writing the report, and its stdout `reported`). The driver checks that this
last entry matches the run it observed from outside. `ok` is `true`, `tool`
is `"nonce-ctl"`, `config_sha256` is the sha256 of the delivered
`config.json` bytes, and `trailer` is the config's trailer. The final
`checksum_manifest` rerun is not in `commands`: it has to hash the finished
`report.json`, so it can only run after that file is written.

`/app/out/tool.zip` is the repaired CLI (`cli.py` and `README.md`), packaged
by the driver with `zipfile` so `python3 cli.py validate --schema ...
--config ... --rules ...` succeeds against the delivered config after
unzipping. The caller supplies the schema and rules files.

`/app/out/validation_report.json` and `/app/out/summary.json` are written by
the driver from what the run observed (the shipped CLI has no subcommand for
them). The validation report's `checks` hold artifact presence, flatness of
the config and both profiles, `command_failures` (empty for a clean run) and
`required_artifacts`, plus a few informational fields. The summary carries
`artifact_count`, `artifacts`, `inputs` (file names under `/app/data`),
`profiles`, `tool`, `format_tag` and `trailer`.

The multi-format artifacts are written by `emit-artifact`:
`policy_matrix.csv` (active roles as rows, active permissions as columns,
ascending, binding cells 1/0),
`rate_limits.tsv` (non-deprecated internal/admin endpoints sorted by
endpoint, `effective_rps = base_rps + concurrency_delta`),
`rotation_schedule.yaml` (classes with `required: true`, ascending),
`mfa_quorum.toml` (quorum threshold first, then enabled non-deprecated strong
factors sorted by id; the weight sum equals `mfa_quorum_threshold`),
`audit_sampling.ini` (`[audit]` with enabled channels and their deltas,
ascending),
`threat_scores.jsonl` (active, non-quarantined actors, ascending),
`cipher_priority.txt` (non-deprecated ciphers; line count equals
`active_cipher_count`),
`egress_allowlist.conf` (allow minus denylist; count equals
`egress_rules_count`),
`session_policy.xml` (four scalar fields from the config),
`trust_anchor_manifest.pem` (active, rotation-ok anchors; score sum equals
`trust_anchor_score`),
`compliance_map.md` (mapped frameworks; weight sum equals
`compliance_score`),
`attestation_ledger.log` (active signers; `attestation_quorum = N // 2 + 1`),
`derived_metrics.env` (nineteen `IRONVAULT_<KEY>=<value>` lines in the order
`DERIVED_METRIC_KEYS` documents),
`canary_thresholds.properties` (four thresholds from the config),
`checksum_manifest.txt` (one `<sha256>  <artifact>` line per other artifact,
matching the bytes on disk).

## Verification

Grader entrypoint: `tests/test.sh`. It clears any stale reward files,
locks `/logs/verifier` to root, restricts `/tests`, then hands over with
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
rewardkit scores `test_output.py` as the `test_output` input and
`judge.toml` as the `judge` input, `tests/reward.toml` combines the two
into the single `reward`, and rewardkit writes `reward.json` plus
`reward-details.json`. `test.sh` writes no reward bytes itself.

Contract fixtures. `config_schema.json` and `validation_rules.json` are
embedded as string constants near the top of `test_output.py`
(`SCHEMA_JSON_TEXT`, `RULES_JSON_TEXT`) rather than read from
`/app/data/`, because the separate verifier container has no `/app/data`.

Checks that execute the delivered CLI extract `/app/out/tool.zip` into a
private temporary directory, make it readable, and run `cli.py` as `nobody`
through `setpriv`. Before the `validate` run the verifier grants read access
on `/app/out/config.json` and its parent directories, so an agent file left
at mode 0600 still validates.

Positive checks (30, summing to +112) cover artifact presence, the flat
scalar config key set and values, deterministic serialization, the two
profiles, the profile trailer suffixes, the power-of-two pbkdf law, the
burst-equals-three-times-rps law, the report transcript (at least nine
entries covering every subcommand kind) backed by a live `init`, the config
digest, each multi-format artifact's shape and the counts tied to the main
config, the validation report and summary, a live `validate` of the
delivered tool.zip, a non-zero bare invocation, and a live `set` that keeps
the key verbatim and coerces a negative integer.

Positive weight total: +112.

Negative checks (6), polarity-inverted so the check returns True only
when the cheat is present; an honest run leaves them all False:
`negative_network_imports_present` (-3),
`negative_forbidden_secret_or_url_material_in_outputs` (-3),
`negative_hardcoded_sample_answers` (-5),
`negative_nested_or_dynamic_config` (-5),
`negative_delivered_cli_py_is_unrepaired` (-5, the packaged `cli.py` is a
byte-identical copy of the shipped broken file),
`negative_hard_coded_derivation_constants` (-3).

Negative weight total: -24.

Theoretical test-channel reward range: -24/112 to +1.000, before
`tests/reward.toml` halves it. No judged-channel score exists for the
oracle, because the oracle produces no agent trajectory.

The judged channel (`tests/judge.toml`) has ten criteria:
`r1_safe_extract_to_app_tool` (+3, instruction following),
`r2_deliverables_via_repaired_cli` (+5, instruction following),
`r3_reads_contract_before_editing` (+3), `r4_verifies_by_running` (+3),
`r5_cross_references_inputs` (+3), `r6_truthful_transcript` (+3),
`r7_honest_summary` (+3), `r8_repaired_cli_quality` (+3),
`negative_external_answer_source` (-5, instruction following) and
`negative_unbacked_success_claim` (-3). Three clauses in those criteria ask
for things the instruction does not request and the reference solution does
not produce: r1's hash check of the extracted contents against a manifest
(the archive carries no manifest), r2's per-key provenance comments (the
config and profiles are plain JSON with no comment syntax), and r8's
companion `.pyi` type stub (the oracle packages only `cli.py` and
`README.md`).

## Root cause

**Why "repair" and "use" are one task.** A configuration produced by hand
is quick. A configuration produced by a repaired CLI requires the CLI to
work, and `report.json` is the receipt. The tests can confirm the
repaired `init` and `set` directly and the derivation through the delivered
values; `validate` is unchanged from the shipped build, so the live
`validate` check confirms the packaged tool runs rather than that it was
repaired.

**Flatness is a contract.** `config_schema.json` declares the required
keys as a comma-separated string that `validate` splits and checks;
`validation_rules.json` bounds six of the integer scalars; `validate`
refuses any nested value. Any convenience `settings` grouping violates it.

**Type coercion at the CLI boundary.** Every argument arrives as a string.
A value of `"3200000"` instead of `3200000` looks right and fails every
numeric equality.

**How the profiles are derived.** Each profile is the reconciled config
plus the `env_overrides.json` delta plus the `hardening_profiles.yaml`
offsets for the matching row; `pbkdf_iterations` scales by
`pbkdf_scale_num / pbkdf_scale_den`; the trailer gains `:dev` or `:prod`.

**Determinism.** JSON key order (`sort_keys=True`), zip member order and
timestamps (sorted file list, `date_time=(1980, 1, 1, 0, 0, 0)`), and no
wall-clock or random values anywhere.

**Red lines.** No hand-written config; no fabricated transcript entries;
no nested values; no URLs, tokens, or credential-shaped strings in outputs;
no third-party packages; no `requests`, `urllib`, or `socket` imports in
the repaired CLI.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool`, refusing absolute paths,
   `..` members, symlinks, and any member that resolves outside the target.
2. Read the contract files in `/app/data`: `config_schema.json` (25
   required keys and the string values), `validation_rules.json` (bounds and
   required artifacts), `defaults.json` (base numbers and `mode`),
   `env_overrides.json` (per-environment deltas) and
   `hardening_profiles.yaml` (session offsets).
3. Repair `cli.py`: required subcommand; `init` reads `--schema` and writes
   six flat keys; `set` keeps keys verbatim and coerces values including
   negatives; `derive` uses the corrected pbkdf, session TTL and burst
   arithmetic; `checksum_manifest` hashes every other file in `--out-dir`.
4. Drive the repaired CLI as real subprocesses: `init`, `derive`,
   `validate`, two `emit-profile`, fifteen `emit-artifact`, then
   `export-report` with the recorded entries passed through `--commands`.
5. Package `/app/out/tool.zip` from a sorted file list with fixed member
   timestamps.
6. Write `validation_report.json` and `summary.json` from the observed run,
   then rerun the `checksum_manifest` kind so it hashes the final files.

## Ordered plan

1. Extract, then run each subcommand once to see how it fails. `init`
   fails first; until it works nothing downstream has input.
2. Read the contract before touching code: the 25 required keys, the
   scalar-only rule, the numeric bounds, and the per-file fields each
   derivation reads.
3. Repair `init` and `set`; verify each by running it and reading the file
   on disk.
4. Repair the three `derive_values` expressions; rerun `derive` and check
   the result against the `validation_rules.json` bounds with `validate`.
5. Generate both profiles with `emit-profile` and check one by hand
   against `env_overrides.json` and `hardening_profiles.yaml`.
6. Emit every artifact kind; repair `checksum_manifest` so it covers every
   file in the output directory.
7. Drive the full pipeline end to end, write the report, package
   `tool.zip`, write the validation report and summary, and refresh the
   checksum manifest last.
8. Run the pipeline a second time and diff every artifact byte for byte.

## Pitfalls

- **Hand-writing `config.json`.** The values themselves can be computed by
  hand, but the instruction requires the repaired CLI to produce them, and
  `report.json` must hold the real runs.
- **Copying values from `sample_config_*.json`.** The samples carry only
  `notes` and `profile_hint`; delivering either string as a config value
  fires `negative_hardcoded_sample_answers`.
- **Emitting nested groups.** The shipped `init`'s `settings` object fails
  `config_key_set_and_types` and fires `negative_nested_or_dynamic_config`.
- **Uppercasing keys or leaving values as strings.** Either half of the
  `set` fault fails `set_preserves_key_and_coerces_negative`.
- **Applying `env_overrides.json` without the hardening offsets, or the
  reverse.** The profile loses `profile_dev_matches_expected` and
  `profile_prod_matches_expected`.
- **Applying the base hardening idle offset in `derive`.** The base row's
  `idle_timeout_offset` (-60) is not part of the main config's idle value;
  applying it would push the dev profile's idle timeout below zero.
- **Packaging the shipped `cli.py` unchanged.** Fires
  `negative_delivered_cli_py_is_unrepaired` and fails the live `init` and
  `set` checks.
- **Running the checksum manifest only once, before the report, archive,
  validation report and summary exist.** The manifest then misses or
  mis-hashes those four files.
- **Non-deterministic serialization.** `json.dumps` without `sort_keys`
  follows insertion order; unsorted or wall-clock zip members change bytes
  between runs.
- **Mentioning a URL, token, or credential-shaped fragment in any
  artifact.** `negative_forbidden_secret_or_url_material_in_outputs` scans
  every non-zip artifact for `http://`, `https://`, `secret=`, `password=`,
  `api_key=`, and `bearer `.

## Provenance

This task asks an on-call operator to repair a stdlib-only Python CLI
(`nonce-ctl`) shipped inside `/app/data/tool.zip`, and then to drive the
repaired CLI to produce a full set of policy artifacts under `/app/out/`.
The shipped CLI's faults fall in subcommand argument routing, key
normalization, derivation arithmetic, and the checksum manifest's file
list. The contract files (`config_schema.json`, `validation_rules.json`,
`env_overrides.json`, `hardening_profiles.yaml`) and the input corpus in
`environment/data/` supply every value the agent needs; the
`sample_config_*.json` files are hints that must not be copied.

Every graded numeric scalar is derivable from the local corpus, so the
task is solvable offline from `instruction.md` plus `environment/data/`.
Nothing in this file is visible to the agent, and the instruction never
names it. This section describes the task and its intended solution shape
only; it records no authoring tools, generators, models, or individual
bylines.
