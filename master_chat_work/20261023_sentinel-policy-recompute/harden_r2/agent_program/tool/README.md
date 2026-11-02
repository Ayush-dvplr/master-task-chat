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
- `set --config <config.json> --key <k> --value <v>` stores one coerced scalar,
  keeping the document flat.
- `validate --schema <schema.json> --config <config.json>` checks the required
  keys are present and every value is scalar; prints `ok`.
- `profile --data-dir <dir> --config <config.json> --name <dev|prod> --out
  <profile.json>` derives one flat environment profile from the compiled
  configuration and the environment sidecar deltas.
- `export-report --config <config.json> --out <report.json> --digest <sha256>
  --commands <json>` writes the run report.
- `export-summary --data-dir <dir> --out <summary.json>` writes the delivery
  summary.
- `export-validation --data-dir <dir> --resolved <resolve-out-dir> --config
  <config.json> --artifacts-dir <dir> --out <validation_report.json> --commands
  <json>` writes the validation report.
- `package --source <tool-dir> --out <tool.zip>` repacks the tool as a
  byte-deterministic archive (sorted members, fixed 1980 member dates, mode
  0644).

The reconstruction rules, the numeric tables, the effective-time windows, the
tenant multipliers, and the rounding and unit conventions all live in the
reference material; several entries there are superseded or belong to a retired
bundle and are never used. `resolve` walks the dependency chain in its
documented order (boot manifest, stale-version rules, bundle ledger, the index
file named by the active bundle, then the numeric tables), prefers
`active_bundle_id` over `latest_bundle_id`, takes the effective version from the
policy version map rather than from the client-claimed version, selects active
override rows whose row and window both carry the effective version inside a
half-open window and within the tenant allowance, converts stored timeout
seconds to milliseconds, rounds basis-point scaling half up per term, clamps
`max_records` to the tenant cap after scaling, and reconciles the risk threshold
iteratively until the step change is within `convergence_epsilon`. Every
rejected superseded or legacy branch is listed in `dependency_trace.json`.
