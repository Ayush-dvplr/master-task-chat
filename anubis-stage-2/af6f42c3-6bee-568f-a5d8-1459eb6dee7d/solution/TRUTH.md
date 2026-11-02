# TRUTH.md - af6f42c3-6bee-568f-a5d8-1459eb6dee7d

## Defect

The source archive at `/app/data/tool.zip` holds a standard-library-only security
policy compiler that installs as `sealb-ctl`. It is broken in its four existing
subcommands, and the two subcommands the posture actually needs, `plan` and
`compile`, are absent and must be built from `/app/data/config_contract.md`. The
task is not only to repair the tool: the repaired tool must then be driven to
compile the posture, and the report artifact carries the real command transcript
that the delivered policy is cross-checked against. Every graded value is derived
from the files under `/app/data`, so nothing below can be recalled from training.

1. (focal) `cmd_init` reads `args.config`, but the `init` subparser declares only
   `--schema` and `--out`, so every `init` dies with `AttributeError` before it
   reads a byte. It also emits a nested `settings` object and omits `mode`, which
   violates the flat, ten-key contract in `/app/data/config_schema.json`.
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
8. (focal) Every corpus's effective upper bound is its published `hi` plus the
   compiled base `rekey_interval_s` modulo 97 plus the rejected-operation count
   modulo 31, so no corpus can be scored until both the spine has been replayed
   correctly and the journal has been classified correctly; a single spine error
   or a single misclassified journal op silently shifts all fifty bounds. The
   four pipelines are deliberately not independent.
9. (trap) The journal is event-sourced: a valid `unset` retracts a prior `set`,
   restoring the key to its `defaults.json` value, last valid op wins. A solver
   that keeps only the last `set` and ignores `unset` lands a wrong `rejected_ops`
   set and wrong zone profiles, and the error never shows on the happy path.
10. (trap) Several corpus rows use look-alikes (full-width digits, a zero-width or
   Cyrillic character in the zone) and values straddling 2**53. The exact
   `str(int(value)) == value` rule and integer-only parsing reject them; a solver
   that normalises Unicode or parses through `float` miscounts them.

The reference is authored in Python (3.12, standard library only, a
standard-library driver that embeds the repaired tool verbatim) with a
Bash dispatcher (`solve.sh`) that extracts the archive, writes the repaired
`cli.py`, then drives `init`, one `set` per policy key, `validate`, `compile` and
`export-report` as real subprocesses before packaging the tool. A deterministic
channel observes the delivered artifacts (Channel A, `tests/test_output.py`); a
judged rubric channel grades the repair-and-drive trajectory (Channel B,
`tests/judge.toml`). Counts and weights are read from those files below.

Out of bounds: hand-writing any artifact instead of producing it through the
repaired tool; a transcript whose entries match no process that ran; harmonising
the two schema shapes; embedding derived numeric answers in the tool source;
nested or non-scalar values anywhere in the policy; any host, endpoint or
credential-shaped string; third-party packages; non-deterministic bytes between
runs; and looking the tool up online, since it exists only for this instance.

## Load-bearing work

22 artifacts are collected, and every one of them is graded:

- `/app/out/config.json`
- `/app/out/report.json`
- `/app/out/tool.zip`
- `/app/out/aggregates.json`
- `/app/out/aggregates.csv`
- `/app/out/aggregates.tsv`
- `/app/out/aggregates.xml`
- `/app/out/aggregates.ini`
- `/app/out/aggregates.env`
- `/app/out/aggregates.md`
- `/app/out/aggregates.txt`
- `/app/out/validation_report.json`
- `/app/out/summary.json`
- `/app/out/profile_core.json`
- `/app/out/profile_edge.json`
- `/app/out/profile_dmz.json`
- `/app/out/profile_mgmt.json`
- `/app/out/rejected_ops.json`
- `/app/out/zone_totals.json`
- `/app/out/corpus_index.json`
- `/app/out/posture.json`
- `/app/out/manifest.sha256`

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

Channel A declares 30 positive and 5 negative tests, positive weight total
96 and negative weight total -19, so the
theoretical range is -19/96 = -0.198 to +1.000.

Positive tests (30):

- `artifacts_exist` (weight 1)
- `config_scalar_types` (weight 3)
- `config_matches_policy` (weight 5)
- `profiles_match` (weight 5)
- `aggregates_plain_delimited_match` (weight 5)
- `aggregates_symbol_delimited_match` (weight 5)
- `aggregates_structured_match` (weight 5)
- `aggregates_csv_matches` (weight 3)
- `aggregates_tsv_matches` (weight 1)
- `aggregates_xml_matches` (weight 3)
- `aggregates_ini_matches` (weight 1)
- `aggregates_env_matches` (weight 3)
- `aggregates_md_matches` (weight 1)
- `aggregates_txt_matches` (weight 1)
- `zone_totals_match` (weight 3)
- `corpus_index_match` (weight 5)
- `posture_match` (weight 3)
- `rejected_ops_match` (weight 5)
- `validation_report_correct` (weight 5)
- `summary_correct` (weight 3)
- `report_transcript_real` (weight 5)
- `report_digest_truthful` (weight 3)
- `manifest_correct` (weight 5)
- `tool_round_trips` (weight 5)
- `json_bytes_canonical` (weight 3)
- `artifacts_are_regular_files` (weight 1)
- `tool_zip_deterministic` (weight 3)
- `trailer_once` (weight 1)
- `tool_compile_reproduces_rollups` (weight 3)
- `tool_compile_deterministic` (weight 1)

Negative tests (5) are polarity-inverted: their assertions
hold only when the cheat is present, so an honest run leaves them failing and they
subtract only from a solver that cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_nested_or_dynamic` (weight -5)
- `negative_fake_transcript` (weight -3): fires only when report.json records a successful validate run that the delivered CLI cannot reproduce
- `negative_network_or_secret` (weight -3): scoped to the repaired CLI source, so it does not overlap with `negative_credentials_leaked`
- `negative_credentials_leaked` (weight -3): reads every delivered artifact (except tool.zip) for an endpoint URL or a credential-style key assignment

Channel B is 14 criteria (12 positive / 2 negative), positive total 44:

- **R1** (+3, trajectory): The agent inspects the local CLI source, schema file, and failing command behaviour before editing.
- **R2** (+5, trajectory): The agent repairs root causes in argument parsing, flat-key validation, and deterministic serialization rather than only writing final JSON by hand.
- **R3** (+3, trajectory): The agent uses only local files and standard-library Python capabilities while configuring the CLI.
- **R4** (+5, trajectory): The agent runs the repaired CLI to create and validate the delivered configuration artifact.
- **R5** (+3, trajectory): The agent runs the full pipeline a second time into a clean output directory and compares the artifact bytes against the first run to confirm deterministic output.
- **R6** (+5, trajectory): The agent uses the repaired CLI commands to set each required flat scalar configuration value during the working session.
- **R7** (-5, trajectory): The agent retrieves a task-specific repaired CLI, prior submission, or hidden policy from an external source.
- **R8** (-3, trajectory): The agent states in its narration that a command or validation succeeded when the trajectory contains no local command output with that result.
- **R9** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R10** (+3, trajectory): The agent creates the configuration artifact at the exact path the instruction names and refrains from writing auxiliary or renamed copies.
- **R11** (+3, trajectory): The agent derives R (the finished-spine rekey_interval_s) and J (the rejected-ops count) from its own journal replay and validity classification, states the resulting shift (R mod 97) plus (J mod 31) with those concrete numbers, and checks for at least one corpus which planted rows above the published hi that effective bound admits.
- **R12** (+3, trajectory): The agent runs a check before finishing that re-serialises its delivered JSON artifacts with the contract's json.dumps parameters and compares the result byte for byte with the delivered files.
- **R13** (+5, trajectory): The agent treats a value as canonical only when str(int(x)) equals the raw field bytes exactly, and rejects every non-canonical form the contract names: leading zeros, -0 / -00 / -000, leading plus, surrounding spaces, underscores, hex, floats, units, words, scientific notation, Devanagari U+0966 range, Arabic-Indic U+0660 range, Gujarati U+0AE6 range, and full-width U+FF10 range.
- **R14** (+3, trajectory): The agent writes a repaired cli.py that reads as ordinary idiomatic Python a reviewer would accept: no bare except clauses swallowing errors, no debug prints left behind, no dead or duplicated branches, functions and variables named for what they do, and types used consistently with the surrounding file.

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

**The eligibility rule is narrow.** A corpus row counts only when its zone is one
of the four active zones, its flag is exactly `active`, and its value is a
canonical base-10 integer inside the corpus bound. Leading zeros, signs, spaces,
underscores, hex, floats, units and words are all rejected, and roughly half of
every corpus is trap rows that fail one clause.

**Determinism.** JSON key order, zip member order and timestamps, and any
wall-clock or random value must be pinned, or two runs disagree.

**The pipelines are chained, not parallel.** The corpus bounds are a function of
the compiled spine, so the spine must be correct before any aggregate is right,
and the journal is event-sourced, so a valid `unset` after a `set` must retract
it. A solver that decomposes the task into four independent passes, keeps the
last `set`, or ignores the spine shift silently corrupts half the aggregates, the
rejected-op set and three of the four profiles with no partial-credit foothold.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool`, refusing absolute, `..` and
   symlink members.
2. Read `/app/data/config_contract.md`, the schema, the defaults, the rules, the
   overrides and the journal, and decide what each contributes.
3. Rewrite `cli.py`: make the subparser required; fix `init` to read `--schema`
   and emit a flat five-key document; fix `set` to keep the key and coerce the
   value; fix `validate` to split the archive schema's comma-separated keys and
   assert flatness; fix `export-report` to write the structured report; make
   `write_json` sort keys and indent.
4. Implement `plan`, which replays the journal for one environment honouring the
   set/unset retraction rule and prints the resolved policy, and `compile`, which
   first computes the spine, then reduces the fifty corpora under the eligibility
   rule with the spine-dependent effective upper bound, and writes every artifact.
5. Drive the repaired tool: `init`, one `set` per planned key, `validate`,
   `compile`, then `export-report` with the accumulated transcript and the config
   digest.
6. Package `/app/tool` into `/app/out/tool.zip` from a sorted file list, stored
   uncompressed, with every member carrying the epoch and `external_attr` of the
   shipped `/app/data/tool.zip` members.

## Ordered plan

1. Extract and read before editing; run each existing command once and record how
   it fails. Rubric R1 credits this inspection.
2. Separate the contract from the code: write down the ten keys, the validity
   rules, the eligibility rule and the aggregation operators first.
3. Repair `init` and `set`, verifying each by reading the file on disk. Rubric R2
   credits repairing parsing, validation and serialization at the root.
4. Repair `validate` and confirm it round-trips against the archive's own schema.
5. Implement `plan` and `compile`, then drive the full sequence as subprocesses.
   Rubrics R4 and R6 grade running the repaired tool to create, set and validate
   the policy, and rubric R10 grades writing it only at the named path.
6. Repair `export-report` last, once a real transcript exists; rubric R8 subtracts
   when the narration claims a command or validation succeeded that no local
   command output in the trajectory shows.
7. Package the tool and write the roll-up artifacts from what the run observed.
8. Run the pipeline a second time into a clean directory and diff every artifact
   byte for byte, then summarise where each artifact was written; rubric R5
   credits the second run and byte comparison, and rubric R9 the closing summary.

## Pitfalls

- **Hand-writing an artifact.** It is faster and it is the most expensive choice
  here; `report_transcript_real`, `tool_round_trips` and rubric R4 read the
  evidence that the tool produced the files.
- **Counting a trap row.** A row whose zone, flag, or integer form is off by one
  clause does not count; the `aggregates_*_match` check for that corpus's wire
  family and `corpus_index_match` (through `eligible_rows`) fail on a single
  mis-counted corpus.
- **Applying a journal operation out of order, without validating it, or ignoring
  an `unset`.** `config_matches_policy`, `profiles_match` and `rejected_ops_match`
  read the event-sourced replay; a valid `unset` retracts the prior `set`.
- **Scoring a corpus with the published bound instead of the spine-shifted one.**
  The effective upper bound is `hi + (compiled rekey_interval_s mod 97) + (rejected_ops count mod 31)`;
  the `aggregates_*_match` family checks, `corpus_index_match` and `posture_match`
  fail on the shift, and the rows planted just above the published bounds make
  a shift that is off by one in either term visible.
- **Harmonising the two schema shapes.** `tool_round_trips` unpacks the delivered
  `tool.zip` and runs the shipped validator against the archive schema.
- **Leaving `settings` nested or a value as a string.** `config_scalar_types` and
  `negative_nested_or_dynamic` both read the delivered policy.
- **A non-deterministic `tool.zip` or unsorted JSON.** `tool_zip_deterministic`
  requires every member to carry the shipped archive's epoch and `external_attr`;
  `json_bytes_canonical` enforces the exact JSON serialization bytes.
- **Embedding derived numbers in the tool source.** `negative_hardcoded_sample_answers`
  fires when the source carries the answers instead of computing them.
- **Normalising Unicode or parsing through `float`.** Look-alike digits and values
  past 2**53 must be judged by exact `str(int(value)) == value`, or the
  `aggregates_*_match` check for that corpus's wire family fails.
- **Writing an endpoint URL or a credential-style key assignment.**
  `negative_credentials_leaked` scans the delivered files and
  `negative_network_or_secret` scans the tool source.

## Provenance

```yaml
uuid: af6f42c3-6bee-568f-a5d8-1459eb6dee7d
instance_id: af6f42c3-6bee-568f-a5d8-1459eb6dee7d
task_name: terminal-bench/af6f42c3-6bee-568f-a5d8-1459eb6dee7d
fix_patch_sha256: 6b9905faae6c9f00a5cbab7058fe0d90a673a527f01fa16218a291eaca05228a  # sha256 of solution/solve.sh
solve_py_sha256: 3e9921061bd7f14df141d4d79f7cfb264f80104d8105b42527553e4a983d3214  # informational
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. The expected figures are exactly 1.000 on each of five
  oracle runs and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 30 positive checks worth 96 weight and 5 negative
  checks worth -19 weight, so on its own it ranges -19/96 = -0.198 to
  +1.000. The judged channel carries 14 criteria worth 44 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
