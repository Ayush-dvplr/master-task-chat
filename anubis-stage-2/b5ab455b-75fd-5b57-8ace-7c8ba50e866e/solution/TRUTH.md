# TRUTH.md - b5ab455b-75fd-5b57-8ace-7c8ba50e866e

## Defect

The source archive at `/app/data/tool.zip` holds `task-ctl`: a 164-line stdlib Python
CLI (`cli.py`) with six subcommands (`init`, `set`, `seal`, `validate`, `profile`,
`export-report`), a `README.md` listing the commands, and a legacy `schema.json`. The
contract is `/app/data/validation_rules.json`. It fixes how inputs are read
(`input_rules`), the canonical byte encoding (`canonical_encoding`), the CRC-32 seal and
the chained profile trailer (`seal_rules`), the configuration policy (`config_policy`),
profile inheritance (`profile_rules`), every subcommand's interface and failure shape
(`cli_command_contract`), and the shape of the report, the validation report and the
summary. `/app/data/history_2026-07.jsonl` holds three canonical lines a working build
wrote for a different configuration (profile `OPS`, producer `Malmö-ops`): a sealed
configuration, the profile for `edge`, and the profile for `edge-eu`, which extends
`edge`. The byte rules can be checked against it before any graded output is written.

The shipped tool runs to completion on the main path. Only `profile --name dev` dies
with a traceback, on the byte order mark in `sample_config_dev.json`. Every other fault
exits 0 while writing the wrong document, and the shipped `validate` prints `ok` for
documents the contract rejects, so neither an exit status nor the tool's own verdict
finds the faults. None of them is labelled in the source.

1. (focal) `load_json` decodes with `read_text`, so a file that starts with a UTF-8 byte
   order mark makes `json.loads` raise, where `input_rules.encoding` says the mark is not
   part of the document. It also lets a repeated key keep its last value, where
   `input_rules.duplicate_keys` keeps the first. `defaults.json` repeats
   `base_config.timeout_ms` (7148 first, 7418 second) and `env_overrides.json` repeats the
   dev `timeout_ms_delta` (-125 first, 125 second). Both errors are silent and spread
   into every value computed from them.
2. (focal) `encode` is a bare `json.dumps`: insertion key order, spaced separators and
   `\u` escapes for `Zürich-ops`. `canonical_encoding` asks for keys sorted by code
   point, bare `,` and `:` separators, raw UTF-8 and exactly one trailing newline. Every
   byte comparison, digest and trailer depends on this one function.
3. (focal) `config_trailer` hashes the document with any old trailer still inside it
   and formats the CRC-32 as 8 hex digits. `seal_rules.digest` removes the trailer first
   and asks for 16 lowercase hex digits, the width the history file carries. `cmd_seal`
   keeps the existing trailer while it computes the new one, so resealing a sealed file
   changes its digest.
4. (focal) `parse_number` goes through `float`. The shipped `base_config.max_records` is
   `9007199254740993` (2^53 + 1), which the broken `set` stores as `9007199254740992`, and
   texts such as `1e3`, `12.0`, `+7` and `1_000` are accepted. `set` takes only the
   integer grammar `cli_command_contract.set` spells out.
5. (focal) `cmd_init` takes `mode` from the schema with a `relaxed-local` fallback,
   prefers the schema's `producer`, `container` and `checksum` over the defaults file,
   and treats `--defaults` as optional. The shipped schema carries empty `producer` and
   `container` values and no `mode`, so the broken `init` writes `""`, `""` and
   `relaxed-local` where the policy needs `Zürich-ops`, `edge-cache` and `strict-local`.
6. (focal) `cmd_set` strips and lower-cases the key, accepts any key, and stores with
   `setdefault`, so `MAX_RECORDS` is accepted and a second `set` of the same key silently
   keeps the first value.
7. (focal) `cmd_validate` compares keys case-insensitively, ignores extra keys, accepts
   lists, booleans, floats and strings in the numeric fields, checks only the trailer
   prefix, and never checks the canonical bytes or the schema profile.
8. (focal) `cmd_profile` ignores `extends`; copies every key of the override entry that
   the document already has, so prod's legacy absolute `"retry_limit": 3` replaces the
   computed value; takes `checksum` from the sample file (`md5` for dev); reads
   `sample_config_<name>.json` with no existence check, so a chain entry without a sample
   (`local` has none) raises once ancestors are walked, where the contract counts a
   missing file as 0; and builds the trailer as the config trailer plus `:<name>`, with
   none of the per-entry digests `seal_rules.profile_trailer` describes.
9. (focal) `cmd_report` records `sys.argv`, which drops the interpreter, as its own
   `argv` (rebuilding it as `[sys.executable, *sys.argv]` still drops interpreter options
   such as `-E -s`; only `sys.orig_argv` is the vector the interpreter received); always writes `ok: true`; stores `--config` as given rather than absolute;
   hashes a re-encoding of the parsed document instead of the file's bytes, which agrees
   with the file only when the file is already in the tool's own encoding; and treats
   `--commands` and `--repairs` as optional.
10. (trap) `main` prints usage on standard output and exits 0 when no subcommand is
    given, because the subparsers are not `required`, and lets `KeyError` and JSON errors
    escape as tracebacks. The contract asks for status 2 with `usage: task-ctl` on
    standard error for usage errors, and one line on standard error with status 1 for
    every other failure. A session that always types a subcommand never sees the first
    half.
11. (drift) The archive's `schema.json` stores `required_keys` as one comma-separated
    string; `/app/data/config_schema.json` stores the list form. `init` and `validate`
    must accept either shape, and neither schema's `producer`, `container` or `checksum`
    is ever used.
12. (trap) The inputs carry values that look authoritative and that a written rule
    excludes: the dev sample's `"checksum": "md5"`, prod's legacy absolute `retry_limit`,
    the `max_records_delta` inside the `stage` override entry, the schema-side identity
    values, and the `canary` entry, which is not in `profiles`. A reader that trusts
    parsed values over `profile_rules.ignored` and `config_policy` produces a wrong
    configuration or wrong profiles.

Out of bounds: authoring `/app/out/config.json` by hand or with the agent's own code
(`R13`, and the transcript replay check, which rebuilds the file with the delivered
tool); shipping a tool that writes `TASK`, `Zürich-ops`, `edge-cache` or
`9007199254740993` into documents built from other inputs
(`negative_shipped_values_hardcoded_in_cli`); a nested value in `config.json`
(`negative_nested_config_value`); a `forbidden_keys` name in the configuration, the
report, the validation report or the summary (`negative_forbidden_key_in_documents`); a
delivered import outside the standard library and the tool's own files
(`negative_non_stdlib_import_in_tool`); a `://` string or credential-named key in
`config.json` or `report.json`, which `document_rules` forbids
(`negative_url_or_credential_in_documents`); third-party packages in helper scripts
(`R8`); looking the tool or its policy up online (`R10`); claiming success for a command
whose own run exited non-zero (`R11`); and authoring `/app/out/report.json` by hand
rather than with `export-report` (`R17`).

## Load-bearing work

7 artifacts are collected, and every one of them is graded:

- `/app/out/config.json`: produced in place by `init` (from
  `/app/data/config_schema.json` and `/app/data/defaults.json`), three `set` calls,
  `seal` and `validate`. Its bytes are exactly
  `{"checksum":"crc32","container":"edge-cache","max_records":9007199254740993,"mode":"strict-local","producer":"Zürich-ops","profile":"TASK","retry_limit":5,"timeout_ms":7148,"trailer":"harbor:cli-config:TASK:000000007940546c"}`
  followed by one newline.
- `/app/out/report.json`: the seven report keys, the seven-entry transcript (`init`,
  three `set`, `seal`, `validate`, then the `export-report` entry the tool appends for
  itself), each `argv` starting with the interpreter and the absolute `cli.py` and
  carrying absolute file paths, `config_sha256` of the file's bytes, and the `repairs`
  list. The first six entries replay against the shipped inputs and end with the
  delivered `config.json` bytes.
- `/app/out/tool.zip`: the repaired tool, flat at the archive root with `README.md`,
  `cli.py` and `schema.json`. It is unpacked and run on its own, without `/app/data`, on inputs other
  than the shipped ones.
- `/app/out/profile_dev.json`: chain `local, dev`. `max_records` 9007199254740983
  (no `sample_config_local.json`, then -10), `retry_limit` 7 (5 + 1 + 1), `timeout_ms`
  7023 (7148 - 125, the first of the repeated deltas), `mode` `strict-local`, `checksum`
  `crc32`, trailer
  `harbor:cli-config:TASK:000000007940546c:local:000000005689ad88:dev:000000003e0c2f4d`.
- `/app/out/profile_prod.json`: chain `stage, prod`. `max_records` 9007199254741023
  (+5 from `sample_config_stage.json`, +25 from `sample_config_prod.json`),
  `retry_limit` 5 (the legacy absolute 3 ignored), `timeout_ms` 7398 (+100, +150),
  `mode` `relaxed-local` (inherited from `stage`), trailer
  `harbor:cli-config:TASK:000000007940546c:stage:000000006cb21bc2:prod:00000000f198e9bc`.
- `/app/out/validation_report.json`: written last. Every flag is true of the delivered
  artifacts, `command_failures` is empty, and `profiles` holds each profile's trailer
  and chain.
- `/app/out/summary.json`: 7 artifacts in contract order, profiles `dev` and `prod`,
  format tag `TASK`, the config trailer, and the nine shipped input names sorted by code
  point (`input_count` 9).

Every rule those artifacts must satisfy is published under `/app/data`, in
`validation_rules.json` and the input files beside it; the history file is the only
place the byte rules can be confirmed end to end.

## Verification

Grader entrypoint: `tests/test.sh`. It clears any stale reward file, locks
`/logs/verifier` to root, restricts `/tests`, and then `exec`s pinned
`harbor-rewardkit==0.2.1`, which scores both channels and writes the reward itself.
`tests/Dockerfile` sets `LITELLM_LOCAL_MODEL_COST_MAP=True` so litellm does not fetch its
cost map through the allowlist. The verifier container holds no `/app/data`, so
`tests/test_output.py` carries byte-exact copies of the shipped schema, defaults,
overrides and samples, repeated keys and byte order mark included. It also carries
inputs of other shapes: a `QX7` schema with shuffled keys and decoy identity values, a
comma-string `ops9` schema, a byte-order-mark-and-repeated-key input set, a
twelve-entry override graph whose deepest chain has seven entries, a set of broken
chains (unknown name, missing parent, cycle), 13 invalid `set` inputs and 13
configurations that each break one `validate` rule. Before any delivered code runs, the
checks remove group and other write access from `/app/out` and its files; the delivered
archive is unpacked into a verifier-owned directory and run as `nobody` through
`setpriv`, in its own process group, under a 20-second timeout.

Channel A declares 31 positive and 5 negative checks, positive weight total 93 and
negative weight total -19. Channel B declares 15 positive and 5 negative criteria,
positive total 49 and negative total -21. `tests/reward.toml` weights Channel A at
`0.005376344086021506` (`0.5 / 93`) and Channel B at `0.01020408163265306`
(`0.5 / 49`), so a full positive pass reads 1.0 and doing nothing reads 0.0. There is no
clamp.

Positive checks (31): `artifacts_present` (1), `config_identity_matches_policy` (3),
`config_integers_match_policy` (3), `config_trailer_is_its_seal` (1),
`config_bytes_are_canonical` (1), `profile_dev_values_follow_its_chain` (3),
`profile_prod_values_follow_its_chain` (3), `profile_trailers_chain_from_the_config` (3),
`delivered_profiles_come_from_delivered_cli` (5),
`report_records_the_published_transcript` (3),
`report_digest_matches_delivered_config` (1),
`report_transcript_replays_with_delivered_cli` (5),
`validation_report_tells_the_truth` (3), `summary_inventories_inputs_and_artifacts` (3),
`delivered_archive_is_flat_and_safe` (1), `delivered_cli_reports_usage_errors` (1),
`delivered_cli_init_takes_identity_from_schema_and_defaults` (3),
`delivered_cli_reads_inputs_by_the_input_rules` (3),
`delivered_cli_set_stores_exact_integers` (3),
`delivered_cli_set_refuses_invalid_input` (3),
`delivered_cli_writes_canonical_bytes` (5),
`delivered_cli_seal_writes_the_crc32_trailer` (5),
`delivered_cli_validate_accepts_conforming_configs` (3),
`delivered_cli_validate_rejects_nonconforming_configs` (5),
`delivered_cli_profile_resolves_inheritance_chains` (5),
`delivered_cli_profile_chains_trailers` (3),
`delivered_cli_profile_refuses_broken_chains` (1),
`delivered_cli_export_report_writes_the_report_schema` (3),
`delivered_cli_export_report_marks_failed_runs` (1),
`delivered_cli_export_report_requires_commands_and_repairs` (5),
`delivered_cli_export_report_records_interpreter_argv` (5).

The usage-error check covers no subcommand, a missing required option of `init`,
`validate` and `profile`, and an unknown option. A missing `--commands` or `--repairs` on
`export-report` is graded on its own by
`delivered_cli_export_report_requires_commands_and_repairs`, and the exact own-entry
`argv` (`sys.orig_argv`, interpreter options included) by
`delivered_cli_export_report_records_interpreter_argv`, so neither fault is counted twice.

Negative checks (5) hold only when the cheat is present, so an honest run leaves them
False and they contribute nothing: `negative_nested_config_value` (-5),
`negative_forbidden_key_in_documents` (-3), `negative_shipped_values_hardcoded_in_cli`
(-5), `negative_non_stdlib_import_in_tool` (-3) and
`negative_url_or_credential_in_documents` (-3).

The refusal and acceptance checks each carry a control in the other direction (a valid
`set`, a conforming configuration for the rejecting `validate`, a mismatched profile for
the accepting one, the intact `fine` entry beside the broken chains), so a tool that
refuses or accepts everything earns nothing from them.

Channel B grades trajectory and handover facts: `r1_inspects_unrepaired_init_output`
(+3), `r2_reproduces_set_failure` (+3), `r3_runs_repaired_validate_successfully` (+5),
`r4_reproduces_export_report_failure` (+3), `r5_names_the_cause_of_each_fault` (+5),
`r6_repaired_code_meets_ordinary_practice` (+3),
`r7_extracts_archive_to_named_location` (+1), `r8_uses_third_party_package` (-3),
`r9_checks_the_file_on_disk` (+3), `r10_retrieves_the_answer_externally` (-5),
`r11_claims_success_against_its_own_output` (-5),
`r12_names_where_each_artifact_landed` (+1), `r13_hand_writes_main_config` (-5),
`r14_reads_raw_input_bytes` (+3), `r15_calibrates_against_history` (+3),
`r16_probes_unrepaired_validate` (+3), `r17_hand_writes_report` (-3),
`r18_runs_the_archive_on_its_own` (+3),
`r19_probes_missing_options_per_subcommand` (+5) and
`r20_repairs_cover_every_cmd_report_fault` (+5). R3, R7, R8, R10, R12, R13 and R17
enforce stated instructions; R1, R2, R4, R6, R9, R14, R15, R16, R18 and R19 grade agent
behavior; R5 and R20 grade task completion through the report's `repairs` list (R5
the causes outside `cmd_report` and its options, R20 all five `cmd_report` faults, the
optional `--commands` and `--repairs` included); and R11 grades factuality.

Weight follows the repair. The sixteen `delivered_cli_*` checks carry 54 of the 93
positive weight, and the two checks that rerun the delivered tool against the delivered
outputs (`delivered_profiles_come_from_delivered_cli` and
`report_transcript_replays_with_delivered_cli`) carry 10 more. The six other artifacts,
byte-correct, delivered with the unrepaired archive as `tool.zip` score 29 of 93 on
Channel A; the same six with no `tool.zip` score 24. Doing nothing scores 0.

The oracle expectation is that running `solution/solve.sh` inside the container drives
every positive Channel A check to pass and holds every negative in its False state.
Channel B needs an agent trajectory, so the oracle, nop and stub agents produce no judged
score; any oracle score quoted for this bundle is a Channel A score.

## Root cause

**Why "repair" and "use" are one task.** The configuration and both profiles are
graded as bytes and are rebuilt by the delivered tool: the profiles directly, the
configuration by replaying the recorded transcript. A file written by hand passes the
artifact checks only if the delivered tool reproduces it, and the sixteen behaviour
checks run the delivered tool on inputs the agent never saw.

**One byte rule feeds everything.** The canonical encoding gives the bytes, the bytes
give the CRC-32 digest, the digest gives the config trailer, each profile body gives its
own digest, and those digests chain into the profile trailers that the validation
report repeats. A wrong separator, an escaped `ü`, a missing newline or an 8-digit
digest changes every trailer downstream. The history file is the calibration point:
three lines for another configuration that the rules reproduce byte for byte, none of
them a graded output.

**What the parser hides.** `json.loads` keeps the last of a repeated key without any
warning, and it raises on a byte order mark when the text was decoded as plain UTF-8.
Reading the shipped inputs at face value gives `timeout_ms` 7418 and a dev
`timeout_ms_delta` of +125, both wrong under `input_rules.duplicate_keys`, which binds
every reader, helper scripts included.

**Exact integers.** `9007199254740993` is the first integer a double cannot hold. Any
path through `float`, in the tool or in a helper that prepares `set` values, stores
`...992`, and the error propagates into both profiles.

**Inheritance is a walk, not a lookup.** A profile accumulates deltas from its chain
root to itself, sample deltas included, takes the last `mode` on the chain, and ignores
every other key an entry or sample carries. Prod's `relaxed-local` comes from `stage`,
not from `prod`; dev's extra retry comes from `local`.

**A tool that runs on its own.** The delivered archive is run without `/app/data` on
other format tags, key orders, schema shapes and override graphs, so every value must
come from the paths a subcommand is given.

**Red lines.** No document the delivered tool cannot reproduce; no fabricated
transcript; no nested values; no third-party imports, external hosts or
credential-shaped strings; no shipped value hardcoded into the tool; no wall-clock or
random field in any graded document.

## Solution shape

`solution/solve.sh` runs `solution/solve.py` (Python 3.12, standard library only, 619
lines), which works in this order:

1. `show_raw_inputs` reads every `*.json` under `/app/data` as bytes and reports a
   leading byte order mark, repeated keys (through an `object_pairs_hook` that records
   them) and non-ASCII text, before any parsed value is used. `read_input` parses with
   `utf-8-sig` and a first-occurrence hook from then on.
2. `extract` unpacks `/app/data/tool.zip` into `/app/tool`, refusing absolute paths,
   `..`, symlinks and nested members.
3. `observe_failures` runs the unrepaired tool on scratch copies: the bare invocation,
   `init` (wrong `mode`, empty `producer` and `container`), `set` of
   `9007199254740993` followed by `17`, `seal` and the bytes it writes, `validate` on an
   upper-cased, list-valued, unsealed document (it prints `ok`), `profile` for dev (the
   byte order mark traceback) and prod (wrong values), and `export-report` (its own
   `argv` starts at `cli.py`, with no interpreter).
4. `repair_cli` locates each faulty top-level function with `ast` and replaces it:
   `load_json` (with `keep_first` and `load_object`), `encode`, `config_trailer` (with
   `body_digest`), `parse_number` (as `parse_integer`), `cmd_init`, `cmd_set`,
   `cmd_seal`, `cmd_validate`, `cmd_profile` (with `profile_chain` and `sample_delta`),
   `cmd_report` and `main`. Text edits add the `os` and `re` imports, replace
   `DEFAULT_MODE` with `NUMERIC_KEYS`, `INTEGER_TEXT` and `CliError`, make the subparsers
   and `--defaults`, `--commands` and `--repairs` required, and end the script with
   `sys.exit(main())`. Each replacement records its causes, and `record_causes` names
   the two `build_parser` faults behind the optional options, 24 in all, which become
   the `repairs` list.
5. `calibrate` imports the repaired module, checks that `encode` reproduces all three
   history lines byte for byte, runs the repaired `seal` on the history configuration
   without its trailer and compares the printed trailer, and recomputes the `edge` and
   `edge-eu` trailers from `body_digest`.
6. `drive` runs `init`, three `set` calls with the first-occurrence `base_config`
   values, `seal` and `validate` as `[sys.executable, /app/tool/cli.py, ...]` with
   absolute paths, stops on any non-zero status, reads `/app/out/config.json` back and
   checks it is canonical, then runs `export-report` with the six entries and the
   repairs in temporary JSON files.
7. `write_profiles` runs `profile` for each name in `profiles` from
   `/app/out/config.json`, `/app/data/env_overrides.json` and the samples in
   `/app/data`.
8. `package_tool` writes `/app/out/tool.zip` flat from a sorted file list with fixed
   1980 timestamps and `0644` modes; `check_archive_standalone` unpacks it away from
   `/app/data`, runs `init` through `validate` with the archive's own `schema.json` and a
   scratch defaults file, checks that a bare invocation exits 2 with nothing on
   standard output, and runs each of the six subcommands with one required option left
   out, checking that each exits 2, prints nothing and writes nothing.
9. `summary.json` is written next, and `validation_report.json` last, with every flag
   computed from the files on disk and the repaired module's `config_trailer` and
   `profile_chain`.

## Ordered plan

1. Read the bytes before the values. `xxd` and `file` are in the image; a repeated key
   and a non-ASCII producer are visible there and invisible to `json.load`, and the byte
   order mark explains the one traceback. R14 credits doing this before relying on
   parsed values.
2. Extract the archive to `/app/tool` (R7) and read `cli.py`, `README.md` and
   `schema.json` against `validation_rules.json` clause by clause.
3. Run each unrepaired subcommand on scratch copies and compare what it writes with what
   the contract asks for, since most faults exit 0: `init` (R1), `set` (R2), `validate`
   on a document the contract rejects (R16) and `export-report` (R4).
4. Repair the readers and the encoder first, then the seal, and confirm both against the
   history file before touching graded outputs (R15). Then repair `init`, `set`,
   `validate`, `profile`, `export-report` and `main`, keeping the code clean (R6).
5. Drive `init`, three `set` calls, `seal` and `validate` into `/app/out/config.json`
   with absolute paths, reading the file back after each write (R9); the repaired
   `validate` must exit 0 (R3). Then run `export-report` with the recorded entries and
   one repair string per fault and cause (R5, R20).
6. Run `profile` for `dev` and `prod`, package the tool flat, run the unpacked archive
   on inputs of its own away from `/app/data` (R18), leave out one required option of
   each subcommand and confirm each run exits 2 (R19), and write the summary and then
   the validation report.
7. Close by naming where each artifact was written (R12).

## Pitfalls

- **Trusting exit status.** Most faults exit 0, and the shipped `validate` prints `ok`
  for an upper-cased, extra-keyed, list-valued, wrongly sealed document.
- **Reading inputs with plain `json.load`.** It keeps 7418 and +125 where the contract
  keeps 7148 and -125, and it raises on the dev sample's byte order mark only when the
  text is decoded as plain UTF-8. The rule binds helper scripts as well as the tool.
- **Any float on the way to `set`.** `9007199254740993` becomes `...992`.
- **Near-canonical bytes.** `sort_keys` alone is not enough: the separators, raw UTF-8
  for `Zürich-ops` and the single trailing newline are all part of the digest input.
- **An 8-digit digest, or a digest over the old trailer.** The history file carries 16
  digits; resealing must give the same trailer.
- **Taking identity from the schema.** Only `profile` comes from the schema; `producer`,
  `container`, `checksum` and `mode` come from the defaults file.
- **Copying the override entry.** Prod's `retry_limit: 3` and stage's
  `max_records_delta` are ignored, the dev sample's `md5` is ignored, `mode` is the last
  one on the chain, and a missing sample file counts as 0.
- **Profile trailers without the chain.** Each chain entry adds `:<name>:<digest>` of
  its own document, ancestors included; dev's trailer carries `local` before `dev`.
- **A transcript that cannot be replayed.** `argv` must start with the interpreter and
  the absolute `cli.py`, every file path must be absolute, `init` reads the shipped
  schema and defaults, and the `export-report` entry is the tool's own, appended last
  with stdout `""`.
- **Hashing anything but the file.** `config_sha256` is over the bytes on disk.
- **Hardcoding the shipped run into the tool.** The delivered archive is run on other
  format tags and inputs, and a tool that writes `TASK` or `Zürich-ops` into those
  documents fires `negative_shipped_values_hardcoded_in_cli`.
- **Usage on standard output.** A bare invocation must exit 2 with `usage: task-ctl`
  on standard error and nothing on standard output; a session that always types a
  subcommand never notices.
- **Tracebacks as errors.** Every failure is one line on standard error with status 1,
  and a failed `set` or `profile` leaves its target file as it was.
- **Listing the inputs from memory.** `summary.inputs` is every file shipped in
  `/app/data`, the history file and the stage sample included.
- **Writing the validation report early.** It is written last and every flag must be
  true of the artifacts as they then stand.
- **A nested archive.** The tool sits flat at the archive root, as in the source.
- **A timestamp, uuid or seed in a report, or a URL in a repair note.** `forbidden_keys`
  and `document_rules` cover the configuration, the report, the validation report and
  the summary.

## Provenance

```yaml
uuid: b5ab455b-75fd-5b57-8ace-7c8ba50e866e
instance_id: b5ab455b-75fd-5b57-8ace-7c8ba50e866e
task_name: terminal-bench/b5ab455b-75fd-5b57-8ace-7c8ba50e866e
fix_patch_sha256: d23046c997c5739f145ec23bdadfc4069a14bafd2c2e5b2521571bc47c147dcf  # sha256 of solution/solve.sh
solve_py_sha256: ece7eb121e4d95a52bc180b877f73ebe8312504e511a881a192d3707ea758c4d  # informational; solve.py is 619 lines
language: python
trailer_token: harbor:cli-config:TASK:000000007940546c
```
