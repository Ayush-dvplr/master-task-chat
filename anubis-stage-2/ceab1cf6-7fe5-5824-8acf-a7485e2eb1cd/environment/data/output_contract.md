# Output contract for /app/out

This file documents the exact field names, object structure, and text layout that
every artifact written under /app/out must use. It describes shape only. Every
value is derived from the rule files under /app/data following the task brief;
nothing here supplies a derived answer. Produce each artifact exactly as specified
so a mechanical reader can locate every field.

General rules for every artifact:

- All JSON artifacts are UTF-8 text. Every scalar is an integer or a string;
  there are no floats, timestamps, uuids, or random fields anywhere.
- When an artifact records a digest of another file, compute it over the exact
  bytes you wrote for that file.
- The active band is the integer computed as (max_records // 13) % 7 from the
  base record count in defaults.json. It is referred to below as target_tier.
- The input inventory is every file present in /app/data, tool.zip included.
  Wherever an artifact below lists or counts the inputs consumed, it covers that
  whole inventory.

## Repaired tool interface

The repaired cli.py reads its rule files from /app/data, or from the directory
named by the TASK_CTL_DATA environment variable when that variable is set. Such
a directory holds the same file names in the same layouts, with its own values,
its own base_config in defaults.json and its rows in any order. Every value the
tool derives must come from the directory it reads.

- derive --schema <schema.json> --out <path> writes a JSON object whose config
  member is the flat 31-key configuration for that directory's active band.
- profile --schema <schema.json> --name <dev or prod> --out <path> writes the
  flat profile object described under profile_dev.json and profile_prod.json.
- validate --schema <schema.json> --config <path> prints ok and exits 0 for a
  valid flat config, and exits non-zero with a message saying the configuration
  must be flat when any value is nested.
- Run with no subcommand, the tool prints a usage error and exits non-zero; it
  never ends in a Python traceback.

## config.json

A single flat JSON object whose key set is exactly the 31 scalar keys listed in
field_registry.ndjson3 (the rows with in_config true and status CANONICAL) and
mirrored by config_schema.json. All keys are lowercase with no surrounding
whitespace. No value is a nested object or an array.

## report.json

A flat JSON object emitted by the repaired tool's export-report command:

- ok: boolean true
- tool: the string task-ctl
- config_path: the filesystem path to the config.json that was validated
- config_sha256: the SHA-256 hex digest of the bytes of config.json
- commands: a list of at least six command records. Each record is an object
  with argv (a list of strings), returncode (an integer, 0 on success), and
  stdout (a string). The transcript includes the init, set, validate, and
  export-report subcommands, and every returncode is 0.
- trailer: the trailer string that config.json carries

## summary.json

A flat JSON object:

- artifact_count: the integer number of artifacts written under /app/out, which
  equals the number of entries in required_artifacts in validation_rules.json
- artifacts: the list of artifact file names, in the exact order of
  required_artifacts in validation_rules.json
- profiles: the list containing dev and prod, in that order
- format_tag: the profile tag from config_schema.json
- trailer: the trailer string from config.json
- target_tier: the active band integer
- input_count: the integer number of files in the input inventory
- inputs: the sorted list of every file name in the input inventory
- tool: the string task-ctl

## validation_report.json

A JSON object:

- ok: boolean, true only when every check below holds
- checks: an object with
  - all_artifacts_present: boolean
  - config_matches_policy: boolean
  - config_scalar_flat: boolean
  - command_failures: a list, empty when no command failed
  - required_artifacts: the required_artifacts list from validation_rules.json
  - profiles: an object keyed by dev and prod. Each entry is an object with
    scalar_flat (boolean) and trailer (string). The dev trailer is the config
    trailer followed by :dev and the prod trailer is the config trailer followed
    by :prod.

## profile_dev.json and profile_prod.json

Flat JSON objects with the scalar keys profile, avg_bitrate_kbps,
max_bitrate_kbps, vbv_buffer_kbits, gop_size_frames, qp, and trailer. The profile
value is TASK-dev or TASK-prod. The trailer is the config trailer followed by
:dev or :prod.

## profile_delta_report.json

A JSON object with keys dev and prod. Each is an object giving the signed
difference (the profile value minus the main config value) for avg_bitrate_kbps,
max_bitrate_kbps, vbv_buffer_kbits, gop_size_frames, and qp.

## selection_trace.kv

KEY=VALUE lines with the keys max_records, retry_limit, timeout_ms, target_tier,
height, and rule. The rule line records the selection expression
active_band = (max_records // 13) % 7.

## gop_plan.ini

An INI file with a [gop] section carrying gop_size_frames, min_keyint_frames,
keyint_seconds, and min_keyint_seconds.

## vbv_plan.properties

KEY=VALUE lines with the keys vbv_buffer_kbits, max_bitrate_kbps, and
vbv_seconds_milli.

## qp_curve.psv

A pipe-separated file whose header line is qp|band_offset|avg_bitrate_kbps,
followed by one data row.

## color_config.env

KEY=VALUE lines with the keys color_primaries, color_transfer, and color_matrix.

## framerate_plan.kv

KEY=VALUE lines with the keys fps_num, fps_den, and lookahead_frames.

## tiling_plan.toml

KEY = VALUE lines with the keys tile_columns, tile_rows, tiles, and threads.

## rounding_audit.yaml

A YAML mapping with the keys policy (the string round_half_even),
granularity_kbps, maxrate_ratio_permille, and eff_permille.

## convergence_report.txt

Lines of the form key: value with the keys config_sha256, reproduced, and
iterations. iterations is the number of derive runs whose outputs were compared
(at least two), and reproduced is true only when those outputs were byte for byte
identical.

## reproducibility_manifest.json

A JSON object with base (an object carrying max_records, retry_limit, and
timeout_ms), config_sha256, and spine_keys (the sorted list of config keys).

## derivation_provenance.xml

A derivation_provenance element containing a field_sources element whose source
children name the data file each field was read from, and a registry_keys
element listing the canonical config keys.

## input_manifest.ndjson

One JSON object per file in the input inventory, each with the keys name,
format, bytes (the file size), and rows.

## ladder_ordering.tsv

A tab-separated file whose header line is the columns profile, avg_bitrate_kbps,
max_bitrate_kbps, and rank. The main, dev, and prod rows follow, ordered by
ascending avg_bitrate_kbps.

## bitrate_ladder.csv

A comma-separated file whose header line is the columns profile,
avg_bitrate_kbps, max_bitrate_kbps, and vbv_buffer_kbits, with one row each for
main, dev, and prod.

## ladder_solution.yaml

A YAML document with tier, a config mapping holding the flat config, and a
profiles mapping holding the dev and prod objects.

## tool.zip

The repaired tool, packaged deterministically, containing the repaired cli.py
and its schema.json at the archive root. Members are stored in sorted name
order and every member carries the fixed timestamp 1980-01-01 00:00:00.
