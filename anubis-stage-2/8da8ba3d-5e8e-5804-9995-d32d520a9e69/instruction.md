You are the on-call operator for the Ironvault Bastion Control Plane at NONCE.
The security team shipped `nonce-ctl` (stdlib-only Python) with faults in
argument routing, key normalization, and derivation arithmetic. Repair the CLI
and use it to reconcile the Bastion policy end-to-end, then publish the full
artifact set to `/app/out/`.

The broken CLI archive is `/app/data/tool.zip`. The full input corpus (schema,
validation rules, environment overrides, sample profile hints, plus 50+ policy
files across CSV, TSV, JSON, JSONL, YAML, TOML, INI, .properties, .conf, .txt,
and PEM-style formats) lives under `/app/data/`. The load-bearing files feed
the derived scalar policy values: rotation cadences, MFA factor weights,
threat-actor tiers, cipher deprecations, trust-anchor scores, RBAC bindings,
firewall actions, hash-algorithm weights, attestation-signer status, egress
allow/deny lists, compliance framework weights, session lifetimes, and
audit-channel sampling deltas. Other files in the corpus provide security
domain context and are not required to be consumed by the derivation. The contract lives in
`/app/data/config_schema.json`, `/app/data/validation_rules.json`,
`/app/data/env_overrides.json`, and `/app/data/hardening_profiles.yaml`. The
`sample_config_*.json` files are hints only and must not be copied.

Start by extracting `/app/data/tool.zip` safely into `/app/tool`, rejecting any
archive member that uses an absolute path, a path-traversal segment, or a
symlink. Then bring the CLI up so `nonce-ctl` runs its full pipeline end to end
(`init`, `derive`, `set`, `validate`, `emit-profile`, `emit-artifact`,
`export-report`) and so a bare invocation without a subcommand exits non-zero
rather than silently defaulting. The `init` subcommand reads the schema at
`--schema` and emits a flat scalar configuration document with no nested
groupings. The `set` subcommand preserves keys exactly as passed and coerces
integer values including negatives. The `derive` subcommand computes every
derived security scalar from the corpus according to the interaction rules each
file declares through its own field values; no scalar may come from a sample
or a hard-coded constant. The `emit-profile` subcommand applies both the
`env_overrides.json` deltas and the matching offsets from
`hardening_profiles.yaml`. The `validate` subcommand enforces the numeric
bounds in `validation_rules.json` and the required keys in
`config_schema.json`, and rejects any nested value.

The main configuration at `/app/out/config.json` must be produced by running
the repaired CLI, not hand-written. It is a single flat JSON object of scalar
values, emitted with `sort_keys=True`, a two-space indent, and a trailing
newline. `/app/out/profile_dev.json` and `/app/out/profile_prod.json` come from
the same CLI via `emit-profile`; each carries every key of the main
configuration with its overrides applied, and its `trailer` value ends with
`:dev` or `:prod`.

`/app/out/report.json` records the CLI transcript. Its `commands` list holds at
minimum one `init`, one `derive`, one `validate`, two `emit-profile`, several
`emit-artifact`, and one `export-report`, each entry carrying `argv`,
`returncode`, and trimmed `stdout`. The `config_sha256` field equals the
sha256 of the delivered `/app/out/config.json` bytes and the `trailer` field
equals the config's `trailer`. The repaired CLI is repackaged as
`/app/out/tool.zip` so that unzipping it and running
`python3 cli.py validate --schema ... --config ... --rules ...` against the
delivered configuration succeeds.

The remaining artifacts follow directly from the reconciled corpus.
`/app/out/policy_matrix.csv` is the RBAC role x permission binary membership
matrix restricted to active roles as rows and active permissions as columns,
in ascending id order. `/app/out/rate_limits.tsv` has one row per non-deprecated
`internal` or `admin` endpoint, sorted by endpoint, with columns `endpoint`,
`zone`, `effective_rps`, `concurrency_delta`. `/app/out/rotation_schedule.yaml`
covers every secret class marked `required: true`, ordered by `class_id`.
`/app/out/mfa_quorum.toml` opens with the quorum threshold and lists one
`[[factor]]` block per enabled, non-deprecated, strong factor, sorted by
`factor_id`; the declared `quorum_threshold` equals both the factor-weight sum
and the main config's `mfa_quorum_threshold`. `/app/out/audit_sampling.ini` has
an `[audit]` section listing only channels for which
`sampling.<channel>.enabled=true`, with the channel's numeric `delta` as the
value.

Emit `/app/out/threat_scores.jsonl`, `/app/out/cipher_priority.txt`,
`/app/out/egress_allowlist.conf`, `/app/out/trust_anchor_manifest.pem`,
`/app/out/compliance_map.md`, and `/app/out/attestation_ledger.log` too. Each
contains only the active, allowed, or non-deprecated entries, ordered by id,
and stays consistent with the count-style scalars in the main config; for
example, the line count of `cipher_priority.txt` equals `active_cipher_count`.

`/app/out/session_policy.xml` is well-formed XML rooted at `<sessionPolicy>`
exposing `ttlSeconds`, `idleTimeoutSeconds`, `mfaQuorum`, and
`tokenEntropyBits` from the main config. `/app/out/derived_metrics.env` carries
one `IRONVAULT_<KEY>=<value>` line per derived numeric scalar, in the order
documented by `emit-artifact --kind derived_metrics`.
`/app/out/canary_thresholds.properties` is derived from the main config,
covering error percentage, latency budget, minimum signers, and maximum deny
rate. `/app/out/checksum_manifest.txt` carries one `<sha256>  <artifact>` line
per emitted artifact, matching the actual bytes on disk.

`/app/out/validation_report.json` is a JSON object with a top-level `ok`
boolean and a `checks` object. `checks` carries `all_artifacts_present` (true
when every declared artifact is present), `config_scalar_flat` (true when the
main config is flat and scalar only), `profiles_scalar_flat` (true when both
profiles are flat and scalar only), `command_failures` (the list of CLI
commands that exited non-zero, empty on a clean run), and `required_artifacts`
(the list of all 22 artifact file names). `ok` is true only when every boolean
check passed and `command_failures` is empty.

`/app/out/summary.json` is a JSON object with `artifact_count` (the number of
artifacts, 22), `artifacts` (the list of all 22 artifact file names), `inputs`
(the list of input file names under `/app/data`), `profiles` (exactly
`["dev", "prod"]`), `tool` (`"nonce-ctl"`), `format_tag` (`"NONCE"`), and
`trailer` (the main config's trailer).

The delivered artifacts must not contain any `http://` or `https://` URL, any
bearer token, or any `secret=`, `password=`, or `api_key=` fragment, and the
repaired CLI must not import `requests`, `urllib`, or `socket`. Use only the
Python standard library and the local files under `/app/data/`.

You have 7200 seconds. Do not cheat by using online solutions or hints
specific to this task.
