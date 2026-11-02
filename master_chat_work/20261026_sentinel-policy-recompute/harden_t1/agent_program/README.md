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
  --commands <json>` writes the run report. `--commands` takes the transcript
  either inline or as the path of a JSON file holding it.
- `profile --data-dir <dir> --policy <policy_resolved.json> --name <dev|prod>
  --out <profile.json>` writes one flat scalar environment profile.
- `summarize --data-dir <dir> --out <summary.json>` writes the delivery summary.
- `verify --data-dir <dir> --config <config.json> --policy
  <policy_resolved.json> --trace <dependency_trace.json> --curve
  <threshold_curve.json> --out-dir <dir> --commands <json> --out
  <validation_report.json>` writes the validation report.
- `package --tool-dir <dir> --out <tool.zip>` writes a byte-deterministic
  archive of the tool (sorted members, 1980 timestamps, mode 0644).
- `digest --path <file>` prints the sha256 of a file.

Every document is written with sorted keys, a fixed indent and a trailing
newline, so repeated runs are byte-identical.

The reconstruction rules, the numeric tables, the effective-time windows, the
tenant multipliers, and the rounding and unit conventions all live in the
reference material; several entries there are superseded or belong to a retired
bundle and are rejected by `resolve`, which records each rejection in
`dependency_trace.json`.
