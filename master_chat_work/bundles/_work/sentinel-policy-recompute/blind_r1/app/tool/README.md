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
- `export-report --config <config.json> --out <report.json> --digest <sha256>
  --commands <json>` writes the run report.

The compiled numbers have been reported to drift from the authoritative policy
model. The reconstruction rules, the numeric tables, the effective-time windows,
the tenant multipliers, and the rounding and unit conventions all live in the
reference material; several entries there are superseded or belong to a retired
bundle and must not be used.
