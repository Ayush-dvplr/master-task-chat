# TRUTH.md - 956d185a-aa75-594b-9031-22809069d1f8

## Defect

The source archive at `/app/data/tool.zip` holds a standard-library-only security
policy compiler named `sealb-ctl` (its argparse program name and README title).
Nothing installs it; it runs as `python3 cli.py` from the extracted archive. Three
of its four existing subcommands (`init`, `set`, `export-report`) are broken, its
dispatcher and JSON writer carry latent defects, and the two subcommands the
posture actually needs, `plan` and `compile`, are absent and must be built from
`/app/data/config_contract.md`. The task is not only to repair the tool: the
repaired tool must then be driven to compile the posture, and the report
artifact carries the real command transcript that the delivered policy is
cross-checked against. Every graded value is derived from the files under
`/app/data`, so nothing below can be recalled from training.

1. (focal) `cmd_init` nests `checksum` under a `settings` object
   (`{"settings": {"checksum": ...}}`), so every configuration it starts breaks
   the flat contract in `/app/data/config_schema.json`. The repaired `init`
   writes the schema's scalar fields (`profile`, `producer`, `container`,
   `checksum`) at the top level, and every key of the planned spine is then
   written through `set`, which brings in `mode`, `trailer` and the four
   replayed integers.
2. (focal) `cmd_set` writes `data[args.key.upper()] = args.value`, so the key is
   mangled and the value stays a string. The contract wants the key verbatim and
   the value coerced to its natural scalar type.
3. (focal) `cmd_report` writes `"commands": "unknown"`, a string where the report
   needs a list of the invocations that ran, each with `argv`, `returncode` and
   `stdout`, plus the tool identity, the config path, the config digest and the
   trailer. Its subparser also accepts only `--config` and `--out`, while the
   archive README's usage line passes `--digest` and `--commands`.
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
   `(R mod 97) + (J mod 31)`, where R is the finished spine's `rekey_interval_s`
   (replayed from the `env` `base` operations only) and J is the rejected-ops
   count, so no corpus can be scored until BOTH the spine has been replayed
   correctly AND the journal validity classification is right. On the shipped
   data R mod 97 is 11 and J is 2168 (J mod 31 is 29), a shift of 40. A wrong R
   or a misclassified operation moves all fifty effective bounds: a spine
   replayed from every `env`, or J one too high, changes 25 of the fifty
   aggregates, while J one too low changes none and is caught only by
   `rejected_ops.json`. The four pipelines are deliberately not independent.
9. (trap) The journal is event-sourced: a valid `unset` retracts a prior `set`,
   restoring the key to its `defaults.json` value, last valid op wins. A solver
   that keeps only the last `set` and ignores `unset` lands a wrong spine, wrong
   values in 25 of the fifty aggregates and three wrong zone profiles out of
   four, and the error never shows on the happy path.
10. (trap) Several corpus rows use look-alikes (full-width digits, a zero-width or
   Cyrillic character in the zone) and values straddling 2**53. The exact
   `str(int(value)) == value` rule and integer-only parsing reject them; a solver
   that normalises Unicode or parses through `float` miscounts them.

The reference is authored in Python (3.12, standard library only). `solve.sh`
only runs `python3 /solution/solve.py`, a 602-line driver that embeds the
repaired `cli.py` verbatim. The driver extracts the archive into `/app/tool`,
writes the repaired `cli.py`, drives `init`, `plan --env base`, one `set` per
planned key, `validate`, `compile` and `export-report` as real subprocesses, and
packages the tool into `/app/out/tool.zip`. It then re-extracts that delivered
`tool.zip`, clears `/app/out`, runs the same pipeline again and stops unless all
22 artifacts come out byte-identical to the first run. A deterministic
channel observes the delivered artifacts (Channel A, `tests/test_output.py`); a
judged rubric channel grades the repair-and-drive trajectory (Channel B,
`tests/judge.toml`). Counts and weights are read from those files below.

Out of bounds: hand-writing any artifact instead of producing it through the
repaired tool; a transcript whose entries match no process that ran; harmonising
the two schema shapes; embedding derived numeric answers in the tool source;
nested or non-scalar values anywhere in the policy; any host, endpoint or
credential-shaped string; third-party packages; non-deterministic bytes between
runs; and looking the tool up online, since it exists only for this instance
(rubric R6).

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

Channel A declares 29 positive and 5 negative tests, positive weight total
83 and negative weight total -19, so the
theoretical range is -19/83 = -0.229 to +1.000.

Positive tests (29):

- `artifacts_exist` (weight 1)
- `config_is_flat` (weight 3)
- `config_matches_policy` (weight 5)
- `profiles_match` (weight 5)
- `aggregates_match` (weight 5)
- `aggregates_mostly_match` (weight 3)
- `aggregates_csv_matches` (weight 1)
- `aggregates_tsv_matches` (weight 1)
- `aggregates_xml_matches` (weight 1)
- `aggregates_ini_matches` (weight 1)
- `aggregates_env_matches` (weight 1)
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
- `tool_zip_deterministic` (weight 3)
- `cli_repaired` (weight 3)
- `world_readable` (weight 1)
- `trailer_once` (weight 1)
- `corpus_count_fifty` (weight 3)
- `posture_total_consistent` (weight 1)

Negative tests (5) are polarity-inverted: their assertions
hold only when the cheat is present, so an honest run leaves them failing and they
subtract only from a solver that cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_dynamic_fields` (weight -5)
- `negative_fake_transcript` (weight -3)
- `negative_network_or_secret` (weight -3)
- `negative_secret_leaked` (weight -3)

Channel B is 13 criteria (11 positive / 2 negative), positive total 43:

- **R1** (+3, trajectory): The agent inspects the local CLI source, schema file, and failing command behaviour before editing.
- **R2** (+5, trajectory): The agent repairs root causes in argument parsing, flat-key validation, and deterministic serialization rather than only writing final JSON by hand and ships per-artifact unit tests on a synthetic fixture that demonstrate each derivation produces canonical output.
- **R3** (+3, trajectory): The agent uses only local files under /app/data and standard-library Python capabilities while repairing and driving the CLI.
- **R4** (+5, trajectory): The agent runs the repaired CLI subcommands to create and validate the delivered configuration artifact and to compile the derived outputs and performs an independent post-build consistency check by re-extracting the shipped tool.zip and re-running the pipeline from a clean workdir to confirm byte-identical artifacts.
- **R5** (+3, trajectory): The agent records a report whose command outcomes are supported by actual terminal evidence.
- **R6** (-5, trajectory): The agent fetches a task-specific repaired CLI, prior submission, or hidden policy answer from an external source.
- **R7** (-5, trajectory): The agent claims validation or command success while the trajectory contains no matching local command output.
- **R8** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R9** (+3, trajectory): The agent creates the configuration artifact at the exact absolute path the instruction names.
- **R10** (+5, trajectory): The agent demonstrates in its working steps that the effective upper bound of every corpus is hi plus (R mod 97) plus (J mod 31), where R is the finished-spine rekey_interval_s and J is the rejected-ops count, by computing or quoting both shift values before scoring the corpora.
- **R11** (+5, trajectory): The agent writes every delivered JSON artifact with exactly sort_keys=True, indent=2, separators of a plain comma and a colon followed by a single space, ensure_ascii=False, UTF-8 encoding, and a single trailing newline.
- **R12** (+5, trajectory): The agent treats a value as canonical only when str(int(x)) equals the raw field bytes exactly, and rejects every non-canonical form the contract names: leading zeros, -0 / -00 / -000, leading plus, surrounding spaces, underscores, hex, floats, units, words, scientific notation, Devanagari U+0966 range, Arabic-Indic U+0660 range, Gujarati U+0AE6 range, and full-width U+FF10 range.
- **R13** (+3, trajectory): The agent writes the repaired cli.py source as code a reviewer would accept: no bare except, errors handled rather than swallowed, names that say what the thing is, no dead or duplicated blocks, no debug residue, and functions a reader can follow.

Against these criteria the reference repairs the tool, drives every subcommand,
computes both bound shifts before scoring, writes every JSON artifact with the
contract's exact parameters and re-runs the pipeline from the delivered
`tool.zip` into a cleared `/app/out`. It ships no per-artifact unit tests, so it
does not meet the second half of R2.

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
underscores, hex, floats, units and words are all rejected, and 30 to 34 percent
of the parsed rows in every corpus are trap rows that fail at least one clause.
Fields are taken as each format delivers them: the delimited, `::`, JSON and XML
readers keep the field bytes as written, so a padded value or flag is rejected;
`fixed`, `mdtable` and `ssv` cells are cut from their layout and trimmed; the
`ini` reader is `configparser`, which trims the space around each value, and a
`properties` line is trimmed before it is split, so a value or flag padded only
at the line end still counts in those two formats.

**Determinism.** JSON key order and serialisation parameters, zip member order,
timestamps, compression and modes, and any wall-clock or random value must be
pinned, or two runs disagree.

**The pipelines are chained, not parallel.** The corpus bounds are a function of
the compiled spine, so the spine must be correct before any aggregate is right,
and the journal is event-sourced, so a valid `unset` after a `set` must retract
it. A solver that treats the four pipelines as independent, keeps the last
`set`, or ignores the bound shift silently corrupts 24 or 25 of the fifty
aggregates, below the 40-corpus floor of `aggregates_mostly_match`; keeping the
last `set` also breaks the spine and three of the four profiles.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool`, refusing absolute, `..` and
   symlink members.
2. Read `/app/data/config_contract.md`, the schema, the defaults, the rules, the
   overrides and the journal, and decide what each contributes.
3. Rewrite `cli.py`: make the subparser required; fix `init` to write the
   schema's four scalar fields flat instead of nesting `checksum` under
   `settings`; fix `set` to keep the key and coerce the value; keep `validate`
   splitting the archive schema's comma-separated keys and asserting flatness;
   give `export-report` its `--digest` and `--commands` options and the
   structured report; write every JSON file with the contract's exact
   `json.dumps` parameters and one trailing newline.
4. Implement `plan`, which replays the journal for one environment honouring the
   set/unset retraction rule and prints the resolved policy, and `compile`, which
   first computes the spine, then reduces the fifty corpora under the eligibility
   rule with the spine-dependent effective upper bound, and writes every artifact.
5. Drive the repaired tool: `init`, `plan --env base`, one `set` per planned key,
   `validate`, `compile`, then `export-report` with the accumulated transcript
   and the config digest.
6. Package `/app/tool` into `/app/out/tool.zip` from a sorted file list, stored
   uncompressed, with 1980-01-01 member timestamps and 0644 modes.
7. Re-extract the delivered `tool.zip`, clear `/app/out`, repeat steps 5 and 6,
   and compare every artifact byte for byte with the first run.

## Ordered plan

1. Extract and read before editing; run each existing command once and record how
   it fails. Rubric R1 credits this inspection.
2. Separate the contract from the code: write down the ten keys, the validity
   rules, the canonical-integer rule (rubric R12), the eligibility rule and the
   aggregation operators first.
3. Repair `init` and `set`, verifying each by reading the file on disk. Rubric R2
   credits repairing parsing, validation and serialization at the root, and R13
   judges the repaired `cli.py` as code a reviewer would accept.
4. Keep `validate` on the archive's own comma-separated schema and confirm it
   accepts the flat configuration and rejects an empty one.
5. Implement `plan` and `compile`, computing `R mod 97` and `J mod 31` before any
   corpus is scored (rubric R10) and writing every JSON artifact with the
   contract's exact parameters (rubric R11), then drive the full sequence as
   subprocesses. Rubric R4 grades running the repaired subcommands to create,
   validate and compile; R3 grades staying on local files and the standard
   library; R9 credits writing the configuration at `/app/out/config.json`.
6. Repair `export-report` last, once a real transcript exists; rubric R5 credits
   a report whose command outcomes match the terminal output, and R7 penalises a
   success claim with no matching command output.
7. Package the tool and write the roll-up artifacts from what the run observed.
8. Re-extract the delivered `tool.zip`, run the pipeline again from a cleared
   `/app/out` and compare every artifact byte for byte, which is the second half
   of rubric R4; then summarise where each artifact was written, which rubric R8
   credits.

## Pitfalls

- **Hand-writing an artifact.** It is faster and it is the most expensive choice
  here: `cli_repaired` runs the delivered tool's `plan --env base` and compares
  it with the spine, `tool_round_trips` runs its `validate` on the delivered
  config, `report_transcript_real` reads the command list in `report.json`, and
  rubrics R4 and R5 judge from the trajectory whether the tool really produced
  the files.
- **Counting a trap row.** A row whose zone, flag, or integer form is off by one
  clause does not count; `aggregates_match` and `corpus_index_match` fail on a
  single mis-counted corpus, and `aggregates_mostly_match` stops paying below 40
  correct corpora.
- **Applying a journal operation out of order, without validating it, or ignoring
  an `unset`.** `config_matches_policy`, `profiles_match` and `rejected_ops_match`
  read the event-sourced replay; a valid `unset` retracts the prior `set`.
- **Scoring a corpus with the published bound instead of the chained-shifted one.**
  The effective upper bound is `hi + (compiled rekey_interval_s mod 97) + (rejected-ops count mod 31)`;
  `aggregates_match`, `corpus_index_match` and `posture_match` fail on either shift.
- **Harmonising the two schema shapes.** `tool_round_trips` and `cli_repaired`
  unpack the delivered `tool.zip` and run its `validate` against the archive's
  own `schema.json`.
- **Leaving `settings` nested or a value as a string.** `config_is_flat` and
  `config_matches_policy` read the delivered policy; `negative_dynamic_fields`
  fires when `config.json` carries a run-dependent key (`timestamp`,
  `generated_at`, `uuid`, `random_seed`, `run_id`, `created_at` or `now`).
- **A report that does not match the delivered config.** `report_digest_truthful`
  and `negative_fake_transcript` both compare the report's `config_sha256` with
  the sha256 of `config.json`.
- **A non-deterministic `tool.zip` or drifting JSON.** `tool_zip_deterministic`
  checks the archive's sorted member order, 1980-01-01 timestamps, stored
  compression and 0644 modes; `manifest_correct` and `report_digest_truthful`
  hash the delivered files. No test re-runs the pipeline or re-serialises the
  JSON, so run-to-run drift and serialisation-parameter drift are judged through
  rubrics R4 and R11.
- **Embedding derived numbers in the tool source.** `negative_hardcoded_sample_answers`
  fires when the delivered tool's `cli.py` or `schema.json` carries the
  evaluation seed or the aggregate total instead of computing it.
- **Normalising Unicode or parsing through `float`.** Look-alike digits and values
  past 2**53 must be judged by exact `str(int(value)) == value`, or
  `aggregates_match` miscounts.
- **Naming a host, URL, token or key.** `negative_secret_leaked` scans every
  delivered artifact except `tool.zip` for `secret`, `password`, `api_key`,
  `apikey`, `token` and `credential`; `negative_network_or_secret` scans the
  delivered tool's `cli.py` and `schema.json` plus `config.json` and
  `report.json` for `requests.`, `urllib.`, `socket.`, `http://` and `https://`.

## Provenance

```yaml
uuid: 956d185a-aa75-594b-9031-22809069d1f8
instance_id: 956d185a-aa75-594b-9031-22809069d1f8
task_name: terminal-bench/956d185a-aa75-594b-9031-22809069d1f8
fix_patch_sha256: b03450a11666808a82a46fb8ad8e1c1e3ce7772509828a6f37d539f629ed3316  # sha256 of solution/solve.sh
solve_py_sha256: f60ef60119b7d7f80bac0a87ac8365a7016d5aab79748a96de286150a5342266  # informational; recompute after each solve.py edit
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
  The test channel carries 29 positive checks worth 83 weight and 5 negative
  checks worth -19 weight, so on its own it ranges -19/83 = -0.229 to
  +1.000. The judged channel carries 13 criteria worth 43 positive points
  and -10 negative points. tests/reward.toml divides each channel's weighted
  sum by its positive total and gives each half of the reward, so the
  combined reward runs from -1.000 to +1.000 with no clamp.
```
