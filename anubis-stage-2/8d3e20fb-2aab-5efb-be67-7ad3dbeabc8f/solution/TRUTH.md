# TRUTH.md - 8d3e20fb-2aab-5efb-be67-7ad3dbeabc8f

## Defect

The source archive at `/app/data/tool.zip` holds a standard-library-only security
policy compiler that installs as `sealb-ctl`. All four of its existing
subcommands are broken, and the two subcommands the posture actually needs,
`plan` and `compile`, are absent and must be built from
`/app/data/config_contract.md`. The
task is not only to repair the tool: the repaired tool must then be driven to
compile the posture, and the report artifact carries the real command transcript
that the delivered policy is cross-checked against. Every graded value is derived
from the files under `/app/data`, so nothing below can be recalled from training.

1. (focal) `cmd_init` writes a seed that nests `checksum` under a `settings`
   object and omits the four integer spine keys, `mode` and `trailer`, so the
   emitted configuration is neither flat nor complete and violates the flat,
   ten-key contract in `/app/data/config_schema.json`.
1b. (focal) `cmd_validate` iterates `schema["required_keys"]` directly instead
   of splitting the comma-separated string, so against the archive's own schema
   it walks the characters of the string and reports every key as missing. The
   repair is `schema["required_keys"].split(",")`.
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
   the same list as a JSON array. The experienced instinct is to make `validate`
   expect an array; doing so without also changing the archive schema breaks the
   tool against the schema it ships with, which `tool_round_trips` runs.
6. (trap) `sub.add_subparsers(dest="command")` is declared without
   `required=True`, so a bare invocation reaches `args.func` and raises instead of
   exiting with usage. It never surfaces on the happy path.
7. (trap) `write_json` serialises with a bare `json.dumps(data)`, so two runs that
   set the same keys in a different order produce byte-different files.
8. (focal) Every corpus's effective upper bound is
   `hi + (R mod 97) + (J mod 31) + (E_i mod 7)` solved as a per-corpus fixpoint,
   where R is the finished-spine `rekey_interval_s`, J is the rejected-ops count,
   and E_i is the eligible-row count of that corpus under the same bound; no
   corpus can be scored until the spine has been replayed correctly, the journal
   has been classified byte-exactly, and the fixpoint has converged. A single
   spine error, a single misclassified journal operation, or applying the
   published `hi` without resolving the fixpoint shifts every one of the fifty
   bounds. The four pipelines are deliberately not independent.
9. (trap) The journal is event-sourced: a valid `unset` retracts a prior `set`,
   restoring the key to its `defaults.json` value, last valid op wins. A solver
   that keeps only the last `set` and ignores `unset` lands a wrong `rejected_ops`
   set and wrong zone profiles, and the error never shows on the happy path.
10. (trap) Several corpus rows use look-alikes (full-width digits, a zero-width or
   Cyrillic character in the zone), fields padded with a space beside the
   separator, and values straddling 2**53. The exact `str(int(value)) == value`
   rule on the raw field bytes and integer-only parsing reject them; a solver
   that strips fields, normalises Unicode or parses through `float` miscounts
   them.
11. (trap) `c43_ban_minutes` and `c49_apparmor_hits` share the maximum derived
   value, so `posture.json` must break the tie by the earlier name, and
   `c47_cgroup_limit` has no eligible row at all, so its `last` reduces to `0`.

The reference is authored in Python (3.12, standard library only, a 600-line
driver, `solve.py`, that embeds the repaired tool verbatim); `solve.sh` only runs
it. The driver extracts the archive, writes the repaired `cli.py`, then drives
`init`, `plan`, one `set` per policy key, `validate`, `compile` and
`export-report` as real subprocesses before packaging the tool. A deterministic
channel observes the delivered artifacts (Channel A, `tests/test_output.py`); a
judged rubric channel grades the repair-and-drive trajectory (Channel B,
`tests/judge.toml`). Counts and weights are read from those files below.

Out of bounds: hand-writing any artifact instead of producing it through the
repaired tool; a transcript whose entries match no process that ran; a `validate`
that no longer accepts the archive's own schema; embedding derived numeric
answers in the tool source;
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
-(16/97)/2 - (10/43)/2 = -0.199 to +1.000. The oracle and nop calibration runs
score Channel A alone.

Channel A declares 29 positive and 4 negative tests, positive weight total
97 and negative weight total -16, so the
theoretical range is -16/97 = -0.165 to +1.000.

Positive tests (29):

- `artifacts_exist` (weight 1)
- `config_has_required_keys` (weight 3)
- `config_matches_policy` (weight 5)
- `profiles_match` (weight 5)
- `aggregates_match` (weight 5)
- `aggregates_csv_matches` (weight 3)
- `aggregates_tsv_matches` (weight 1)
- `aggregates_xml_matches` (weight 3)
- `aggregates_ini_matches` (weight 1)
- `aggregates_env_matches` (weight 3)
- `aggregates_md_matches` (weight 1)
- `aggregates_txt_matches` (weight 1)
- `zone_totals_match` (weight 5)
- `corpus_index_match` (weight 5)
- `posture_match` (weight 5)
- `rejected_ops_match` (weight 5)
- `validation_report_correct` (weight 5)
- `summary_correct` (weight 5)
- `report_transcript_real` (weight 5)
- `report_digest_truthful` (weight 3)
- `manifest_correct` (weight 5)
- `tool_round_trips` (weight 3)
- `cli_repaired` (weight 5)
- `tool_zip_deterministic` (weight 3)
- `compile_reproducible` (weight 3)
- `json_canonical` (weight 3)
- `trailer_once` (weight 1)
- `corpus_count_fifty` (weight 3)
- `posture_total_consistent` (weight 1)

Negative tests (4) are polarity-inverted: their assertions
hold only when the cheat is present, so an honest run leaves them failing and they
subtract only from a solver that cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_nested_or_dynamic` (weight -5)
- `negative_fake_report` (weight -3)
- `negative_network_or_secret` (weight -3)

Channel B is 13 criteria (11 positive / 2 negative), positive total 43 and
negative total -10:

- **R1** (+3, trajectory): The agent inspects the local CLI source, schema file, and failing command behaviour before editing.
- **R2** (+5, trajectory): The agent repairs root causes in argument parsing, flat-key validation, and deterministic serialization rather than only writing final JSON by hand.
- **R3** (+3, trajectory): The agent uses only local files and standard-library Python capabilities while configuring the CLI.
- **R4** (+5, trajectory): The agent runs the repaired CLI to create and validate the delivered configuration artifact.
- **R5** (+3, trajectory): The agent records a report whose command outcomes are supported by actual terminal evidence.
- **R6** (+5, trajectory): The agent uses the repaired CLI commands to set each required flat scalar configuration value during the working session.
- **R7** (-5, trajectory): The agent retrieves a task-specific repaired CLI, prior submission, or hidden policy from an external source.
- **R8** (-5, user_facing_message): The response claims a validation or command success that is absent from or contradicted by the local command output in the trajectory.
- **R9** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R10** (+5, trajectory): The agent explains that the effective upper bound of every corpus is hi plus (R mod 97) plus (J mod 31) plus (E_i mod 7) solved as a per-corpus fixpoint, where R is the finished-spine rekey_interval_s, J is the rejected-ops count, and E_i is the eligible-row count of that corpus under the same bound.
- **R11** (+5, trajectory): The agent treats a value as canonical only when str(int(x)) equals the raw field bytes exactly, and rejects every non-canonical form the contract names: leading zeros, -0 / -00 / -000, leading plus, surrounding spaces, underscores, hex, floats, units, words, scientific notation, Devanagari U+0966 range, Arabic-Indic U+0660 range, Gujarati U+0AE6 range, and full-width U+FF10 range.
- **R12** (+3, trajectory): The agent names at least one concrete journal operation whose misclassification would change the effective upper bound of every one of the fifty corpora.
- **R13** (+3, state_change): The agent writes the repaired cli.py as ordinary production Python: errors propagated or handled rather than swallowed with bare except, informative names, no dead or duplicated blocks, and no debug or scratch residue.

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
underscores, hex, floats, units and words are all rejected, and about a third of
the parsed rows (4159 of 11991) are trap rows that fail one clause.

**Determinism.** JSON key order, zip member order and timestamps, and any
wall-clock or random value must be pinned, or two runs disagree.

**The pipelines are chained, not parallel.** The corpus bounds are a function of
the compiled spine, so the spine must be correct before any aggregate is right,
and the journal is event-sourced, so a valid `unset` after a `set` must retract
it. A solver that decomposes the task into four independent passes, keeps the
last `set`, or ignores the spine shift silently corrupts the aggregates, the
rejected-op set or the zone profiles.

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
6. Package `/app/tool` into `/app/out/tool.zip` from a sorted file list with fixed
   member timestamps.

## Ordered plan

1. Extract and read before editing; run each existing command once and record how
   it fails. Rubric R1 credits this inspection.
2. Separate the contract from the code: write down the ten keys, the validity
   rules, the eligibility rule and the aggregation operators first.
3. Repair `init` and `set`, verifying each by reading the file on disk. Rubric R2
   credits repairing parsing, validation and serialization at the root.
4. Repair `validate` and confirm it round-trips against the archive's own schema.
5. Implement `plan` and `compile`, then drive the full sequence as subprocesses.
   Rubrics R4 and R6 grade running the tool to build, set and validate the policy.
6. Repair `export-report` last, once a real transcript exists; rubric R5 grades a
   report whose outcomes match local output, and R8 penalises a closing claim of
   success that the output does not show.
7. Package the tool and write the roll-up artifacts from what the run observed.
8. Run the pipeline a second time into a clean directory and diff every artifact
   byte for byte, then summarise where each artifact was written; rubric R9
   credits the closing summary, and `compile_reproducible` and
   `tool_zip_deterministic` check the rebuild.

## Pitfalls

- **Hand-writing an artifact.** It is faster and it is the most expensive choice
  here; `report_transcript_real`, `negative_fake_report`, `cli_repaired` and
  rubric R4 read the evidence that the tool produced the files.
- **Counting a trap row.** A row whose zone, flag, or integer form is off by one
  clause does not count, and a field padded with a space beside its separator is
  off by one clause; `aggregates_match`, `corpus_index_match` and
  `posture_match` fail on a single mis-counted corpus.
- **Breaking the posture tie by the later name, or failing on an empty corpus.**
  `posture_match` expects `c43_ban_minutes` as `max_corpus`, and
  `aggregates_match`, its seven views and `corpus_index_match` expect
  `c47_cgroup_limit` to reduce to `0`.
- **Applying a journal operation out of order, without validating it, or ignoring
  an `unset`.** `config_matches_policy`, `profiles_match` and `rejected_ops_match`
  read the event-sourced replay; a valid `unset` retracts the prior `set`.
- **Scoring a corpus with the published bound instead of the spine-shifted one.**
  The effective upper bound is `hi + (R mod 97) + (J mod 31) + (E_i mod 7)` solved
  as a per-corpus fixpoint; `aggregates_match`, `corpus_index_match` and
  `posture_match` fail on the shift.
- **Breaking `validate` against the archive schema.** `tool_round_trips` unpacks
  the delivered `tool.zip` and runs its `validate` with its own `schema.json`
  against the delivered config.
- **Leaving `settings` nested or a value as a string.** `config_has_required_keys`,
  `config_matches_policy` and `negative_nested_or_dynamic` read the delivered
  policy.
- **A non-deterministic `tool.zip` or unsorted JSON.** `tool_zip_deterministic`,
  `json_canonical`, `compile_reproducible` and `manifest_correct` compare exact
  bytes.
- **Embedding derived numbers in the tool source.** `negative_hardcoded_sample_answers`
  fires when the source carries the answers instead of computing them.
- **Normalising Unicode or parsing through `float`.** Look-alike digits and values
  past 2**53 must be judged by exact `str(int(value)) == value`, or
  `aggregates_match` miscounts.
- **Naming a host, URL, token or key.** `negative_network_or_secret` scans the
  tool source for network call sites and embedded credentials, and every
  delivered text artifact for URLs and credential words.

## Provenance

```yaml
uuid: 8d3e20fb-2aab-5efb-be67-7ad3dbeabc8f
instance_id: 8d3e20fb-2aab-5efb-be67-7ad3dbeabc8f
task_name: terminal-bench/8d3e20fb-2aab-5efb-be67-7ad3dbeabc8f
fix_patch_sha256: 839b9069b91c6a7bab3f586dc318b7bb64550f87eb93d1261717678524ac3ee5  # sha256 of solution/solve.sh
solve_py_sha256: 17f4b56991b8e8b627c2ef91d245357c3b3477c1f682c625a78387fbd3e19327  # informational; solve.py is 600 lines
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
  The test channel carries 29 positive checks worth 97 weight and 4 negative
  checks worth -16 weight, so on its own it ranges -16/97 = -0.165 to
  +1.000. The judged channel carries 13 criteria (11 positive + 2 negative)
  worth 43 positive and -10 negative points, so on its own it ranges
  -10/43 = -0.233 to +1.000. tests/reward.toml divides each channel's
  weighted sum by its positive total and gives each half of the reward,
  so the combined reward runs from -0.199 to +1.000 with no clamp.
```
