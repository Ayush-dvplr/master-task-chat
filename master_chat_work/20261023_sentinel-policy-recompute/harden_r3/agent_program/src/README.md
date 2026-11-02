# sentinel-ctl

`sentinel-ctl` compiles a multi-tenant access-control policy bundle from the
reference material under the data directory and emits a flat scalar
configuration.

Subcommands:

- `init --schema <schema.json> --out <config.json>` writes the flat identity
  fields (profile, producer, container, checksum, mode).
- `resolve --data-dir <dir> --out <out-dir>` reconstructs the authoritative
  policy from the reference material, writing `policy_resolved.json`,
  `dependency_trace.json`, and `threshold_curve.json`, and printing the resolved
  scalars as JSON.
- `profile --data-dir <dir> --env <dev|prod> --out <profile.json>` derives one
  flat environment profile from the resolved policy and the environment sidecar
  deltas of the reference material.
- `set --config <config.json> --key <k> --value <v>` stores one coerced scalar,
  keeping the document flat.
- `validate --schema <schema.json> --config <config.json>` checks the required
  keys are present and every value is scalar; prints `ok`.
- `export-report --config <config.json> --out <report.json> --digest <sha256>
  --commands <json>` writes the run report.

The reconstruction rules, the numeric tables, the effective-time windows, the
tenant multipliers, and the rounding and unit conventions all live in the
reference material; entries that are superseded or belong to a retired bundle
are rejected and reported in `dependency_trace.json`.

Resolution traverses the dependency chain in its documented order:
`boot_manifest.toml` names the active bundle, `bundle_ledger.jsonc` maps that
bundle to its role key and principal index, and the principal index supplies the
param key, tenant and role level. The effective version comes from
`policy_version_map.json` (never from a client claim), override rows are
selected by active status, half-open window containment and version match, then
drawn in ascending seq against the per-region override allowance and the
per-window admit count. `max_records` is scaled half-up by the tenant multiplier
before the cap clamp, timeouts are compiled to milliseconds, and the risk
threshold is reconciled iteratively until the step change is within
`convergence_epsilon`.
