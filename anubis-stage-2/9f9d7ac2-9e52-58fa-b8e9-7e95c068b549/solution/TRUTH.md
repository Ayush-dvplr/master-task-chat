# TRUTH.md - 9f9d7ac2-9e52-58fa-b8e9-7e95c068b549

## Defect

The source archive at `/app/data/tool.zip` holds a standard-library-only security
policy compiler whose argparse program name is `sealb-ctl`. Its four existing
subcommands are broken, and the two subcommands the posture needs, `plan` and
`compile`, are absent and must be built from `/app/data/config_contract.md`. The
task is not only to repair the tool: the repaired tool must then be driven to
compile the posture, and the report artifact carries the command transcript of
that run. Every graded value is derived from the files under `/app/data`, so
nothing below can be recalled from training.

1. (focal) `cmd_init` writes a nested `settings` object (holding `checksum`)
   instead of flat top-level scalars, which breaks the flat ten-key contract in
   `/app/data/config_schema.json`. The repaired `init` writes a flat document of
   the identity scalars the schema carries (`profile`, `producer`, `container`,
   `checksum`); every remaining key arrives through `set`.
2. (focal) `cmd_set` writes `data[args.key.upper()] = args.value`, so the key is
   mangled and the value stays a string. The contract wants the key verbatim and
   the value coerced to its natural scalar type.
3. (focal) `cmd_report` writes `"commands": "unknown"`, a string where the report
   needs a list of the invocations that ran, each with `argv`, `returncode` and
   `stdout`, plus the tool identity, the config path, the config digest and the
   trailer. Its parser also lacks the `--digest` and `--commands` options the
   archive README documents.
4. (focal) `plan` and `compile` do not exist. `plan` prints the resolved policy
   for `base` or one zone by replaying the change journal; `compile` reduces the
   fifty evidence corpora and writes the derived artifacts the contract
   documents.
5. (drift) The tool's own `schema.json` stores `required_keys` as one
   comma-separated string, while `/app/data/config_schema.json` stores the same
   list as a JSON array. Harmonising them breaks the tool against the schema it
   ships with; the repaired `validate` accepts both shapes.
6. (trap) `sub.add_subparsers(dest="command")` is declared without
   `required=True`, so a bare invocation reaches `args.func` and raises instead of
   exiting with usage. It never surfaces on the happy path.
7. (trap) `write_json` serialises with a bare `json.dumps(data)`, so two runs that
   set the same keys in a different order produce byte-different files.
8. (focal) Every corpus's effective upper bound is its published `hi` plus
   `(rekey_interval_s mod 97) + (rejected_ops_count mod 31)`, taken from the
   finished spine and the journal classification, so no corpus can be scored
   until both are right. On the shipped data the shift is 34 (13 + 21).
9. (trap) The journal is event-sourced: a valid `unset` restores the key to its
   `defaults.json` value, last valid operation wins, in ascending `seq` (the file
   is not stored in `seq` order). A solver that keeps only the last `set` and
   ignores `unset` still gets the spine and `rejected_ops` right but builds wrong
   `edge` and `dmz` profiles.
10. (trap) Several corpus rows use look-alikes (Devanagari, Arabic-Indic,
    Gujarati or full-width digits, a zero-width or Cyrillic character in the
    zone) and values straddling 2**53. The exact `str(int(value)) == value` rule
    and integer-only parsing reject them; a solver that normalises Unicode or
    parses through `float` miscounts them.

The reference is `solution/solve.py` (Python 3.12, standard library only),
started by `solution/solve.sh`. It embeds the repaired `cli.py`, a README for it
and a `test_cli.py` unit-test module. It extracts the archive into `/app/tool`,
writes those three files, runs the unit tests (they build a small synthetic
fixture and exercise parsing, eligibility, journal replay, the effective bound,
the config commands, serialization, packaging, compile and seal), then drives
the repaired tool as real subprocesses: `init`, `plan --env base`, one `set` per
planned key, `validate`, `compile`, `package`, `export-report`, `seal`, and a
final `export-report` so the transcript covers every earlier call.

The repaired tool reads every zone, corpus format, operator and bound from
`/app/data` at run time (formats and operators from the contract table, bounds
from `validation_rules.json`, which must agree). `seal` reads the delivered
artifacts back, computes every check in `validation_report.json` from them and
from the data, sets `ok` only when every boolean check holds, `command_failures`
is 0, the integer checks agree across artifacts and nothing extra sits in
`/app/out`, then writes the manifest. A tampered artifact makes `seal` exit
non-zero with `ok: false`.

Out of bounds: hand-writing any artifact instead of producing it through the
repaired tool; a transcript whose entries match no process that ran; harmonising
the two schema shapes; embedding derived numeric answers in the tool source;
nested or non-scalar values anywhere in the policy; credential-shaped strings in
the outputs; third-party packages; non-deterministic bytes between runs; and
looking the tool up online, since it exists only for this instance.

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

- `config.json` is the flat ten-key spine policy, built through `init` and `set`
  and equal to the journal-replayed baseline (`max_sessions` 1840,
  `retry_budget` 2, `handshake_timeout_ms` 2123, `rekey_interval_s` 32508,
  `mode` `strict-seal`).
- The four `profile_<zone>.json` files are the spine plus the zone overrides plus
  that zone's valid journal operations.
- `aggregates.json` and its seven mirrors carry one derived integer per corpus
  under the contract eligibility and aggregation rules (total
  9007199255328396; the maximum is `c49_apparmor_hits` at 9007199254740993).
- `zone_totals.json`, `corpus_index.json`, `posture.json` and
  `rejected_ops.json` (2160 rejected operations) are the roll-ups.
- `validation_report.json`, `summary.json`, `report.json` and
  `manifest.sha256` are the coverage, inventory, transcript and digest artifacts.
- `tool.zip` is the repaired tool rebuilt from `/app/tool` by `package`
  (ZIP_STORED, 1980-01-01 timestamps, mode 0100644, sorted members).

## Verification

Grader entrypoint: `tests/test.sh`. It clears stale reward files, locks
`/logs/verifier` to root, restricts `/tests`, then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
rewardkit scores Channel A from the `@criterion` checks in `tests/test_output.py`,
each weighted by its `criteria.<name>(weight=W)` registration, and Channel B from
`tests/judge.toml`. `tests/reward.toml` divides each channel's weighted sum by its
positive total and gives each half of `reward`.

Channel A has 78 checks: 76 positive (total 134) and 2 negative (total -8):

- Presence and inventory: `artifacts_exist` (1), `no_extra_artifacts` (3),
  `world_readable` (1).
- Policy: `config_is_flat` (3), `config_matches_policy` (5), `trailer_once` (1),
  `profiles_match` (5).
- Aggregates: fifty `aggregates_<corpus>_matches` checks (1 each) compare each
  value in `aggregates.json` with the derived truth; `mirror_consistency` (5)
  parses the seven mirrors and compares them with `aggregates.json`.
- Roll-ups: `zone_totals_match` (3), `corpus_index_match` (5), `posture_match`
  (3), `rejected_ops_match` (5), `corpus_count_fifty` (3),
  `posture_total_consistent` (1).
- Reports: `validation_report_correct` (5), `summary_correct` (3),
  `report_transcript_real` (5), `report_digest_truthful` (3),
  `report_keys_exact` (3), `manifest_correct` (5), `json_bytes_exact` (5).
- Tool: `tool_round_trips` (5) unpacks `tool.zip`, validates the delivered config
  against the archive's own schema, and re-runs `compile` on the shipped data to
  reproduce `aggregates.json` byte for byte; `cli_subcommands_present` (1),
  `cli_rejects_nested` (1), `cli_deterministic_init` (1), `zip_deterministic` (3).
- Negatives: `negative_hardcoded_sample_answers` (-5) fires when the aggregate
  total appears in `cli.py` or `schema.json`; `negative_secret_present` (-3) fires
  when a credential-like token appears in a delivered artifact.

Channel A alone ranges from -8/134 (about -0.060) to +1.000.

Channel B (`tests/judge.toml`) has 8 criteria, positive total 27, negative total -5:

- R1 (+3): inspects the CLI source, schema and failing behaviour before editing.
- R2 (+5): repairs parsing, flat-key validation and serialization at the root
  rather than hand-writing JSON, and ships per-component unit tests on a
  synthetic fixture.
- R3 (+3): uses only local files and standard-library Python.
- R4 (+3): writes the configuration at the exact named path, with no auxiliary
  copies.
- R5 (+5): names the effective-upper-bound formula with intermediate values.
- R6 (+5): applies the canonical-integer rule and rejects every listed form.
- R7 (+3): recognises that a valid `unset` retracts a prior `set`.
- R8 (-5): claims success with no matching local command output.

Channel B alone ranges from -5/27 (about -0.185) to +1.000. The combined reward
ranges from -(0.5 * 8/134 + 0.5 * 5/27), about -0.122, to +1.000, with no clamp.

The oracle expectation is that running `solution/solve.sh` inside the container
passes every positive Channel A check and trips no negative one, for a Channel A
reward of 1.000. The judged channel grades a trajectory and has no oracle score.

## Root cause

**Repair and use are one task.** A posture written by hand can be made to look
right quickly; a posture produced by a repaired tool requires the tool to work,
and the report is the record of the run.

**Flatness is a contract.** The sidecar schema declares `scalar_only`, the
repaired `validate` refuses any `dict` or `list`, and the configuration carries
exactly ten scalar keys.

**Coercion at the boundary.** Every `set` value arrives as a string. A policy in
which an integer key holds a string compares unequal to the baseline.

**The eligibility rule is narrow.** A row counts only when its zone is one of the
four active zones, its flag is exactly `active`, and its value is a canonical
base-10 integer inside the corpus bound. In the delimited, `::`, properties,
JSON and XML formats the grader keeps the field bytes as stored, so a row with a
space inside a field (` 12`, `active `) does not count. The `ini` corpora are
read with `configparser`, the `mdtable` corpora by trimmed table cells and the
`fixed` corpora by trimmed columns, so padding there is part of the format and
does not disqualify a row.

**Determinism.** JSON key order and separators, zip member order, timestamps and
modes, and any wall-clock or random value are pinned, so two runs agree byte for
byte.

**The pipelines are chained.** The corpus bounds depend on the finished spine and
the rejected-op count, so the journal must be replayed and classified correctly
before any aggregate is right. Measured on the shipped data: scoring with the
published `hi` changes 24 of the 50 aggregates; dropping the `J mod 31` term also
changes 24; accepting non-ASCII digits changes 17. Every shift from 17 to 40
yields the same aggregates, so an error confined to the `R mod 97` term changes
nothing graded, and an off-by-one in `J` shows only in the rejected-op count.
Keeping the last `set` and ignoring `unset` changes no aggregate and only the
`edge` and `dmz` profiles.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool`, refusing absolute, `..` and
   symlink members.
2. Read the contract, the schema, the defaults, the rules, the overrides and the
   journal.
3. Rewrite `cli.py`: make the subparser required; make `init` read `--schema` and
   write a flat document; make `set` keep the key and coerce the value; make
   `validate` reject nesting first and accept both `required_keys` shapes; give
   `export-report` its documented options; serialise every JSON file with
   `sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False` and one
   trailing newline.
4. Implement `plan`, `compile`, `package` and `seal` as described above, and
   unit-test each piece on a synthetic fixture.
5. Drive the repaired tool end to end and record every call in the report.

## Ordered plan

1. Extract and read before editing; run each existing command once and record how
   it fails (R1).
2. Write down the ten keys, the journal validity rules, the eligibility rule, the
   effective bound and the aggregation operators from the contract.
3. Repair `init`, `set`, `validate` and `export-report` at the root, with a unit
   test per component (R2).
4. Implement `plan` with the set/unset retraction rule in ascending `seq` (R7),
   then `compile` with the canonical-integer rule (R6) and the effective upper
   bound, showing its intermediate values (R5).
5. Drive the full sequence as subprocesses using only local files and the
   standard library (R3), writing the configuration only at
   `/app/out/config.json` (R4).
6. Package the tool, export the report, seal, and report only what the commands
   printed (R8).
7. Run the pipeline a second time into a clean directory and compare every
   artifact byte for byte.

## Pitfalls

- **Hand-writing an artifact.** `tool_round_trips` re-runs the delivered tool's
  `compile` and expects the delivered `aggregates.json` back byte for byte.
- **Counting a trap row.** Each mis-counted corpus fails its own
  `aggregates_<corpus>_matches` check and the roll-ups that include it
  (`zone_totals_match`, `corpus_index_match`, `posture_match`,
  `validation_report_correct`, `summary_correct`).
- **Applying a journal operation out of order, without validating it, or ignoring
  an `unset`.** `config_matches_policy`, `profiles_match` and `rejected_ops_match`
  read the event-sourced replay.
- **Scoring a corpus with the published bound.** The effective upper bound is
  `hi + (rekey_interval_s mod 97) + (rejected_count mod 31)`.
- **Harmonising the two schema shapes.** `tool_round_trips` validates with the
  archive's own comma-separated schema.
- **Leaving `settings` nested or a value as a string.** `config_is_flat` and
  `config_matches_policy` read the delivered policy.
- **A non-deterministic `tool.zip` or loosely serialised JSON.**
  `zip_deterministic` reads the archive entries; `json_bytes_exact` re-serialises
  every JSON artifact and compares bytes.
- **Writing `validation_report.json` by hand.** `validation_report_correct`
  compares every check with values derived from the data and the other artifacts.
- **Embedding derived numbers in the tool source.**
  `negative_hardcoded_sample_answers` fires when the source carries the total.
- **Normalising Unicode or parsing through `float`.** Look-alike digits and values
  past 2**53 must be judged by exact `str(int(value)) == value`.
- **Writing a credential-like token into an output.** `negative_secret_present`
  scans every delivered artifact except `tool.zip`.

## Provenance

```yaml
uuid: 9f9d7ac2-9e52-58fa-b8e9-7e95c068b549
instance_id: 9f9d7ac2-9e52-58fa-b8e9-7e95c068b549
task_name: terminal-bench/9f9d7ac2-9e52-58fa-b8e9-7e95c068b549
fix_patch_sha256: af785c967d02e14d046f3ad6552a91d552eb81fc3949f5850fa37e5073023a39  # sha256 of solution/solve.sh
solve_py_sha256: e01674b5ffb10d9b9bced51710d091440417ca1715dfc23b6e46ceb40febd2d8  # sha256 of solution/solve.py
language: python
golden_score_measured: 1.00000  # Channel A (tests/test_output.py) reward of the oracle
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null  # judged channel grades a trajectory; no oracle score exists
caveat: >
  Channel A carries 76 positive checks worth 134 and 2 negative checks worth
  -8; Channel B carries 7 positive criteria worth 27 and 1 negative worth -5.
  tests/reward.toml gives each channel half of the reward after dividing by its
  positive total, so the combined reward runs from about -0.122 to +1.000.
```
