# Configuration contract

Every value below comes from the files in `/app/data`; none is fixed by the tool.

## Main configuration (`config.json`)

1. Start from `defaults.json`: the four `base_config` values (`max_records`,
   `retry_limit`, `timeout_ms`, `trailer`) plus its `checksum` and `mode`. `profile`,
   `producer` and `container` come from `config_schema.json`. The nine keys are the
   schema's `required_keys`.
2. Replay `change_journal.jsonl`. Each line is one recorded `set` operation with
   `seq`, `env`, `key`, `value`, `actor` and `ticket`. Lines are not in `seq` order:
   apply operations in ascending `seq`. An operation is valid when all of these hold:
   - its `env` is listed in `journal_envs` of `validation_rules.json`;
   - its `key` is `max_records`, `retry_limit`, `timeout_ms` or `mode` (exact case);
   - for the three integer keys, `value` is a JSON integer (not a string) inside the
     inclusive `[min, max]` pair of `bounds` in `validation_rules.json`;
   - for `mode`, `value` is one of `allowed_modes` (exact text).
   Valid `base` operations set the key in the main configuration; a later valid
   operation on the same key wins.

## Profiles (`profile_dev.json`, `profile_prod.json`)

For each profile `P` in `validation_rules.json` `profiles`, start from the finished
main configuration and then:

1. add `max_records_delta` of the profile's sample file (`sample_config_dev.json` or
   `sample_config_prod.json`) to `max_records` and take its `checksum`;
2. add `retry_limit_delta` and `timeout_ms_delta` of `env_overrides.json` `P` to
   `retry_limit` and `timeout_ms`, and take its `mode`;
3. set `profile` to `<main profile>-P` and `trailer` to `<main trailer>:P`;
4. apply the valid journal operations whose `env` is `P`, in ascending `seq`.

## Validation report

`validation_report.json` carries `ok` and `checks`. `checks` holds
`all_artifacts_present`, `config_matches_policy`, `config_scalar_flat` (booleans),
`command_failures` (the CLI commands that exited non-zero, normally `[]`),
`required_artifacts` (from `validation_rules.json`), `profiles` (per profile name an
object with `scalar_flat` and `trailer`) and `rejected_ops` (the ascending `seq`
numbers of every journal operation that was not valid).

## Run report and summary

`report.json` is written by the repaired CLI's `export-report` and carries `ok`
(true), `tool` (`{{PACKAGE_NAME}}-ctl`), `config_path`, `config_sha256` (the SHA-256
hex digest of the delivered `config.json` bytes), `trailer` (the main configuration's
trailer) and `commands`: one object per CLI command you ran, in order, each with
`argv` (the command's argument list), `returncode` and `stdout`. No timestamps.

`summary.json` carries `tool`, `format_tag` (the main configuration's `profile`),
`trailer`, `profiles` (from `validation_rules.json`), `artifacts` and `artifact_count`
(the `required_artifacts` list and its length), and `inputs` and `input_count` (the
sorted names of every file in `/app/data` and how many there are).
