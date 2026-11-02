# TRUTH.md - 9e96e588-55bc-5e39-8eb7-134bec04dd22

## Defect

The source archive at `/app/data/tool.zip` holds a standard-library-only security
policy compiler that installs as `sealb-ctl`. It is broken in its four existing
subcommands, and the two subcommands the posture actually needs, `plan` and
`compile`, are absent and must be built from `/app/data/config_contract.md`. The
task is not only to repair the tool: the repaired tool must then be driven to
compile the posture, and the report artifact carries the real command transcript
that the delivered policy is cross-checked against. Every graded value is derived
from the files under `/app/data`, so nothing below can be recalled from training.

1. (focal) `cmd_init` emits a nested `settings` object containing `checksum` and
   omits `mode` and the four spine keys. The result violates the flat ten-key
   contract in `/app/data/config_schema.json` and later `validate` calls raise.
2. (focal) `cmd_set` writes `data[args.key.upper()] = args.value`, so the key is
   mangled and the value stays a string. The contract wants the key verbatim and
   the value coerced to its natural scalar type.
3. (focal) `cmd_report` writes `"commands": "unknown"`, a string where the report
   needs a list of the invocations that ran, each with `argv`, `returncode` and
   `stdout`, plus the tool identity, the config path, the config digest and the
   trailer.
4. (focal) `plan` and `compile` do not exist. `plan` must print the fully resolved
   policy for one environment by replaying the change journal; `compile` must
   reduce the fifty evidence corpora and write every derived artifact exactly as
   the contract documents.
5. (drift) The tool's own `schema.json` stores `required_keys` as one
   comma-separated string, while the sidecar `/app/data/config_schema.json` stores
   the same list as a JSON array. The experienced instinct is to harmonise them;
   doing so breaks the tool against the schema it ships with and consumes.
6. (trap) `sub.add_subparsers(dest="command")` is declared without
   `required=True`, so a bare invocation reaches `args.func` and raises instead of
   exiting with usage. It never surfaces on the happy path.
7. (trap) `write_json` serialises with a bare `json.dumps(data)`, so two runs that
   set the same keys in a different order produce byte-different files.
8. (focal) Every corpus's effective upper bound is its published `hi` plus
   `(R mod 97) + (J mod 31)`, where `R` is the finished-spine `rekey_interval_s`
   and `J` is the count of rejected journal operations. The spine replay and the
   journal validity classification both feed every corpus; a wrong spine or a
   wrong rejected-ops count shifts bounds and can change any aggregate whose
   eligible rows sit near the shifted bound.
9. (trap) The journal is event-sourced: a valid `unset` retracts a prior `set`,
   restoring the key to its `defaults.json` value, last valid op wins. A solver
   that keeps only the last `set` and ignores `unset` lands wrong spine values
   and wrong zone profiles (the rejected_ops set itself is identical because
   validity classification does not depend on how unset is applied). The error
   never shows on the happy path.
10. (trap) Several corpus rows use look-alikes (full-width digits, a zero-width or
   Cyrillic character in the zone) and values straddling 2**53. The exact
   `str(int(value)) == value` rule and integer-only parsing reject them; a solver
   that normalises Unicode or parses through `float` miscounts them.

The reference is authored in Python (3.12, standard library only). A thin Bash
dispatcher (`solve.sh`) just execs `python3 /solution/solve.py`; the Python
driver (588 lines) extracts `/app/data/tool.zip` to `/app/tool`, overwrites
`cli.py` with the repaired version it carries as the `REPAIRED_CLI` string, then
drives `init`, `plan`, one `set` per planned key, `validate`, `compile` and
`export-report` as real subprocesses, printing each call's argv, stdout and
return code, before packaging the tool deterministically to `/app/out/tool.zip`.
The repaired tool reads each corpus's file name, format and operator from the
table in `config_contract.md`; the bounds, zones, profiles, journal environments,
modes and integer-key bounds from `validation_rules.json`; and the spine from
`defaults.json` and `config_schema.json`. The only fixed lists are the tool name
`sealb-ctl` (from the instruction) and the declared artifact list that
`summary.json` reports, which follows the artifact order in `task.toml` because
`summary_correct` compares that list exactly. A deterministic channel observes the delivered artifacts
(Channel A, `tests/test_output.py`); a judged rubric channel grades the
repair-and-drive trajectory (Channel B, `tests/judge.toml`). Counts and weights
are read from those files below.

Out of bounds: hand-writing any artifact instead of producing it through the
repaired tool; a transcript whose entries match no process that ran; harmonising
the two schema shapes; embedding derived numeric answers in the tool source;
nested or non-scalar values anywhere in the policy; any host, endpoint or
credential-shaped string; third-party packages; non-deterministic bytes between
runs; and looking the tool up online, since it exists only for this instance.

## Load-bearing work

22 artifacts are collected, and every one of them is graded:

- `/app/out/aggregates.csv`
- `/app/out/aggregates.env`
- `/app/out/aggregates.ini`
- `/app/out/aggregates.json`
- `/app/out/aggregates.md`
- `/app/out/aggregates.tsv`
- `/app/out/aggregates.txt`
- `/app/out/aggregates.xml`
- `/app/out/config.json`
- `/app/out/corpus_index.json`
- `/app/out/manifest.sha256`
- `/app/out/posture.json`
- `/app/out/profile_core.json`
- `/app/out/profile_dmz.json`
- `/app/out/profile_edge.json`
- `/app/out/profile_mgmt.json`
- `/app/out/rejected_ops.json`
- `/app/out/report.json`
- `/app/out/summary.json`
- `/app/out/tool.zip`
- `/app/out/validation_report.json`
- `/app/out/zone_totals.json`

- `/app/out/config.json` is the flat ten-key spine policy, produced by running the
  repaired tool and matching the journal-replayed baseline.
- `/app/out/profile_core.json`, `profile_edge.json`, `profile_dmz.json` and
  `profile_mgmt.json` are the four zone profiles, each the spine plus the zone
  overrides plus that zone's valid journal operations.
- `/app/out/aggregates.json` plus its `.csv`, `.tsv`, `.xml`, `.ini`, `.env`,
  `.md` and `.txt` views carry one derived integer per corpus under the contract
  eligibility and aggregation rules.
- `/app/out/zone_totals.json`, `corpus_index.json`, `posture.json` and
  `rejected_ops.json` are the roll-ups over the corpora and the journal.
- `/app/out/validation_report.json`, `summary.json`, `report.json` and
  `manifest.sha256` are the coverage, inventory, transcript and digest artifacts.
- `/app/out/tool.zip` is the repaired tool itself, rebuilt deterministically.

## Verification

Grader entrypoint: `tests/test.sh`. It clears stale reward files, locks
`/logs/verifier` to root, restricts `/tests`, then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
rewardkit scores Channel A from the `@criterion` checks in `tests/test_output.py`,
each weighted by its `criteria.<name>(weight=W)` registration, and Channel B from
`tests/judge.toml`. `tests/reward.toml` divides each channel's weighted sum by its
positive total and gives each half of `reward`, so the combined reward runs from
-1.000 to +1.000. The oracle and nop calibration runs score Channel A alone.

Channel A declares 44 deterministic checks (40 positive, 4 negative), positive weight total
96 and negative weight total 16, so the
theoretical range is -1.000 to +1.000.

Positive tests (40):

- `artifacts_exist` (weight +1)
- `config_is_flat` (weight +3)
- `config_matches_policy` (weight +5)
- `profiles_match` (weight +5)
- `aggregate_group_c01_c05` through `aggregate_group_c46_c50`, ten checks of five
  corpora each against the independent re-derivation (weight +1 each)
- `aggregates_csv_matches`, `aggregates_tsv_matches`, `aggregates_xml_matches`,
  `aggregates_ini_matches`, `aggregates_env_matches`, `aggregates_md_matches` and
  `aggregates_txt_matches`, each parsing the view back and comparing it with the
  delivered `aggregates.json` (weight +1 each)
- `zone_totals_match` (weight +3)
- `corpus_index_match` (weight +5)
- `posture_match` (weight +3)
- `rejected_ops_match` (weight +5)
- `validation_report_correct` (weight +5)
- `summary_correct` (weight +3)
- `report_transcript_real` (weight +5)
- `report_digest_truthful` (weight +3)
- `manifest_correct` (weight +5)
- `tool_round_trips` (weight +5)
- `cli_repaired` (weight +3)
- `cli_subcommands_execute` (weight +5)
- `tool_zip_deterministic` (weight +3)
- `json_bytes_strict` (weight +3)
- `world_readable` (weight +1)
- `no_secrets` (weight +3)
- `trailer_once` (weight +1)
- `corpus_count_fifty` (weight +3)
- `posture_total_consistent` (weight +1)

Negative tests (4) are polarity-inverted: their assertions
hold only when the cheat is present, so an honest run leaves them failing and they
subtract only from a solver that cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_nested_or_dynamic` (weight -5)
- `negative_fake_transcript` (weight -3)
- `negative_network_or_secret` (weight -3)

Channel B is 13 judged criteria (11 positive, 2 negative), positive total 45, negative total 10:

- `R1` `r1_inspects_the_local_cli_source_schema` (weight +3)
- `R2` `r2_repairs_root_causes_in_argument_parsing` (weight +5)
- `R3` `r3_uses_only_local_files_and_standard` (weight +3)
- `R4` `r4_runs_the_repaired_cli_to_create` (weight +5)
- `R5` `r5_report_commands_recorded_from_live_runs` (weight +3)
- `R6` `r6_uses_the_repaired_cli_commands_to` (weight +5)
- `R7` `r7_retrieves_a_task_specific_repaired_cli` (weight -5)
- `R8` `r8_claims_validation_or_command_success_while` (weight -5)
- `R9` `r9_summarizes_the_completed_work_and_names` (weight +3)
- `R10` `r10_creates_the_configuration_artifact_at_the` (weight +3)
- `R11` `r11_chained_bound_reasoning` (weight +5)
- `R12` `r12_byte_exact_json_serialization` (weight +5)
- `R13` `r13_noncanonical_integer_rejection` (weight +5)

The oracle expectation is that running `solution/solve.sh` inside the container
drives every positive Channel A test to pass and holds every negative test in its
failing state, for a Channel A reward of +1.000.

## Root cause

**Repair and use are one task.** A posture written by hand can be made correct in
a minute; a posture produced by a repaired tool requires the tool to work, and the
report is the receipt. The CLI-use and transcript checks sit at the top of the
scale for this reason.

**Flatness is a contract.** The sidecar schema declares `scalar_only`, the tool's
own `validate` refuses any `dict` or `list`, and the configuration carries exactly
ten scalar keys. The nested `settings` object and any convenience grouping both
break it.

**Coercion at the boundary.** Every `set` value arrives as a string. A policy in
which an integer key holds a string is a different document, compares unequal to
the baseline, and serialises differently.

**Determinism.** JSON key order, zip member order and timestamps, and any
wall-clock or random value must be pinned, or two runs disagree.

**The pipelines are chained, not parallel.** The corpus bounds are a function of
the compiled spine, so the spine must be correct before any aggregate is right,
and the journal is event-sourced, so a valid `unset` after a `set` must retract
it. A solver that keeps the last `set` and ignores `unset` corrupts the spine and
three of the four profiles; one that scores against the published `hi` instead of
the shifted bound changes about half of the fifty aggregates.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool`, refusing absolute, `..` and
   symlink members.
2. Read `/app/data/config_contract.md`, the schema, the defaults, the rules, the
   overrides and the journal, and decide what each contributes.
3. Rewrite `cli.py`: make the subparser required; fix `init` to read `--schema`
   and emit a flat four-key document; fix `set` to keep the key and coerce a
   canonical integer string to an integer; fix `validate` to split the archive
   schema's comma-separated keys and assert flatness; fix `export-report` to write
   the structured report; make `write_json` use
   `json.dumps(obj, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False)`
   plus a trailing newline.
4. Implement `plan`, which replays the journal for one environment honouring the
   set/unset retraction rule and prints the resolved policy, and `compile`, which
   first computes the spine, then reads the corpus table from the contract,
   reduces the fifty corpora under the eligibility rule with the spine-dependent
   effective upper bound, and writes every artifact.
5. Drive the repaired tool: `init`, `plan`, one `set` per planned key, `validate`,
   `compile`, then `export-report` with the accumulated transcript and the config
   digest, printing each call's argv, stdout and return code as it runs, then
   print the derived `R`, `J` and shift.
6. Package `/app/tool` into `/app/out/tool.zip` from a sorted file list with fixed
   member timestamps.

## Ordered plan

1. Extract and read before editing; run each existing command once and record how
   it fails. Rubric R1 credits this inspection.
2. Separate the contract from the code: write down the ten keys, the validity
   rules, the eligibility rule and the aggregation operators first. Rubrics R11
   and R13 credit stating the chained bound and the canonical-integer rule.
3. Repair `init` and `set`, verifying each by reading the file on disk. Rubric R2
   credits repairing parsing, validation and serialization at the root, and R12
   credits the pinned JSON serialization parameters.
4. Repair `validate` and confirm it round-trips against the archive's own schema.
5. Implement `plan` and `compile`, then drive the full sequence as subprocesses
   using only local files and the standard library. Rubrics R4 and R6 grade
   running the repaired tool to create, set and validate the policy; R3 grades
   staying local and standard-library only, and R7 penalises fetching a repaired
   tool or answers from outside.
6. Repair `export-report` last, once a real transcript exists; rubrics R5 and R8
   compare the report's command entries with the invocations the trajectory shows.
7. Package the tool and write the roll-up artifacts from what the run observed.
8. Run the pipeline a second time into a clean directory and diff every artifact
   byte for byte, then summarise where each artifact was written. Rubric R9
   credits the closing summary; R10 credits writing the configuration at
   `/app/out/config.json`.

## Pitfalls

- **Hand-writing an artifact.** It is faster and it is the most expensive choice
  here; `report_transcript_real`, `tool_round_trips`, `cli_subcommands_execute`
  and rubrics R4 and R6 read the evidence that the tool produced the files.
- **Counting a trap row.** A row whose zone, flag, or integer form is off by one
  clause does not count; one mis-counted row fails the `aggregate_group_*` check
  for its corpus, `zone_totals_match`, `corpus_index_match`, and the three checks
  that carry `aggregate_total` (`posture_match`, `validation_report_correct` and
  `summary_correct`).
- **Applying a journal operation out of order, without validating it, or ignoring
  an `unset`.** `config_matches_policy`, `profiles_match` and `rejected_ops_match`
  read the event-sourced replay; a valid `unset` retracts the prior `set`.
- **Scoring a corpus with the published bound instead of the spine-shifted one.**
  The effective upper bound is `hi + (compiled rekey_interval_s mod 97) + (rejected_ops_count mod 31)`;
  the `aggregate_group_*` checks, `corpus_index_match` and `posture_match` fail on
  the shift.
- **Harmonising the two schema shapes.** `tool_round_trips` and
  `cli_subcommands_execute` unpack the delivered `tool.zip` and run its validator
  and subcommands against the `schema.json` inside it, so the tool and its own
  schema must agree.
- **Leaving `settings` nested or a value as a string.** `config_is_flat` and
  `config_matches_policy` read the delivered policy; `negative_nested_or_dynamic`
  fires on a `timestamp`, `generated_at`, `uuid` or `random_seed` key.
- **A non-deterministic `tool.zip` or unpinned JSON.** `tool_zip_deterministic`
  requires sorted `ZIP_STORED` members dated 1980-01-01 00:00:00,
  `json_bytes_strict` re-serialises every JSON artifact with the pinned
  parameters and compares bytes, and `manifest_correct` and
  `report_digest_truthful` hash the delivered bytes.
- **Embedding derived numbers in the tool source.** `negative_hardcoded_sample_answers`
  fires when the source carries the answers instead of computing them.
- **Normalising Unicode or parsing through `float`.** Look-alike digits and values
  past 2**53 must be judged by exact `str(int(value)) == value`, or the
  `aggregate_group_*` checks miscount.
- **Naming a host, URL, token or key.** `no_secrets` and
  `negative_network_or_secret` scan the delivered files and the tool source.

## Provenance

- Reference entrypoint: `solution/solve.sh`, which runs `solution/solve.py`
  (588 lines, repaired `cli.py` embedded as `REPAIRED_CLI`).
- Inputs: 57 files under `environment/data/`.
- `environment/data/tool.zip` sha256 `897ec460064611e9853dadeb8e0bed1a8877b17238277d342bb72c8cee9a48fc`.
- `environment/data/config_contract.md` sha256 `b9bcfe4eb5ceff7cf0f19d7fe60460d0daab8ce25151747c9c5d2689d14f26f9`.
- `environment/data/validation_rules.json` sha256 `a69212984d1e9f175b232dc18fc6046feeaeb35dc06660dbcf9354451df521f1`.
