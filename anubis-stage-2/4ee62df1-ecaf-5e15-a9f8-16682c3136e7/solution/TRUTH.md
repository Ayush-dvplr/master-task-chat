# TRUTH.md - 4ee62df1-ecaf-5e15-a9f8-16682c3136e7

## Defect

The source archive at `/app/data/tool.zip` holds a standard-library-only security
policy compiler that installs as `sealb-ctl`. It is broken in its four existing
subcommands, and the three subcommands the posture actually needs, `plan`,
`compile` and `aggregate`, are absent and must be built from
`/app/data/config_contract.md`. The task is not only to repair the tool: the
repaired tool must then be driven to compile the posture, and the report artifact
carries the real command transcript that the delivered policy is cross-checked
against. Every graded value is derived from the files under `/app/data`, so
nothing below can be recalled from training.

1. (focal) `cmd_init` emits a nested `settings` object and omits `mode`, which
   violates the flat, ten-key contract in `/app/data/config_schema.json`.
2. (focal) `cmd_set` writes `data[args.key.upper()] = args.value`, so the key is
   mangled and the value stays a string. The contract wants the key verbatim and
   an integer key to carry a JSON integer.
3. (focal) `cmd_report` writes `"commands": "unknown"`, a string where the report
   needs a list of the invocations that ran, each with `argv`, `returncode` and
   `stdout`, plus the tool identity, the config path, the config digest and the
   trailer. Its subparser also lacks the `--digest` and `--commands` options the
   archive README documents.
4. (focal) `plan`, `compile` and `aggregate` do not exist. `plan` prints the
   resolved policy for `base` or one zone by replaying the change journal;
   `compile` reduces the fifty evidence corpora and writes the aggregate, mirror,
   zone-total and corpus-index artifacts; `aggregate` prints one corpus's derived
   integer. All three follow the "CLI-driven derivation" section of the contract.
5. (drift) The tool's own `schema.json` stores `required_keys` as one
   comma-separated string, while the sidecar `/app/data/config_schema.json` stores
   the same list as a JSON array. The tool consumes its own schema; replacing the
   archive schema with the sidecar copy is out of bounds.
6. (trap) `sub.add_subparsers(dest="command")` is declared without
   `required=True`, so a bare invocation reaches `args.func` and raises instead of
   exiting with usage. It never surfaces on the happy path.
7. (trap) `write_json` serialises with a bare `json.dumps(data)`, so the bytes
   differ from the contract's serialisation and the manifest breaks.
8. (focal) Every corpus's effective upper bound is its published `hi` plus the
   three-moduli shift `(R mod 97) + (J mod 31) + (Z mod 53)`, where R is the
   finished-spine `rekey_interval_s`, J is the count of rejected journal
   operations, and Z is the first 16 hex characters of
   sha256(/app/out/tool.zip) parsed as a hex integer. Forty corpora carry an
   otherwise eligible row at every value from `hi + 1` to `hi + 178`, so a shift that is
   wrong by any amount changes those forty aggregates whatever Z the agent's
   archive yields.
9. (trap) The journal is event-sourced: a valid `unset` restores the key to its
   `defaults.json` value, last valid op wins. Zone operations are replayed on top
   of each zone's starting profile and judged against that zone's own state, and
   an invalid zone operation is a rejected journal operation that counts toward
   J. Operations whose `env` is not listed, a `touch` on a key outside the four
   integer spine keys and `mode`, and a `mode` value outside `allowed_modes`
   (exact case) are all rejected.
10. (trap) Corpus rows use look-alikes (full-width and other non-ASCII digits, a
    zero-width, Cyrillic, BOM or no-break-space character in the zone, padding
    spaces inside a field) and values straddling 2**53. The exact
    `str(int(value)) == value` rule on the raw field bytes, byte-exact zone and
    flag comparison, and integer-only parsing reject them. Rows in the reserved
    `svc` zone never count.

The reference is authored in Python (3.12, standard library only). `solve.sh`
runs `solve.py`, which extracts the archive into `/app/tool` (refusing any
member that would land outside it), replaces `cli.py` with the repaired tool it
embeds verbatim, keeps the archive's own `schema.json` and `README.md`, and then
drives the tool as real subprocesses: `init`, `plan --env base`, one `set` per
key that `init` did not already write, `validate`, `compile`, the fifty
`aggregate` calls and `plan` for each zone. It packages `/app/tool` into
`/app/out/tool.zip` before `compile`, writes the roll-up artifacts, calls
`export-report` (which records its own invocation in the transcript), then writes
`validation_report.json` from the delivered files and the manifest last. A
deterministic channel observes the delivered artifacts (Channel A,
`tests/test_output.py`); a judged rubric channel grades the repair-and-drive
trajectory (Channel B, `tests/judge.toml`). Counts and weights are read from
those files below.

Out of bounds: hand-writing any artifact instead of producing it through the
repaired tool; a transcript whose entries match no process that ran; replacing
the archive schema with the sidecar schema; embedding derived numeric answers in
the tool source; nested or non-scalar values anywhere in the policy; any host,
endpoint or credential-shaped string; third-party packages; non-deterministic
bytes between runs; and looking the tool up online, since it exists only for
this instance.

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
  repaired tool's `init` and `set` and matching the journal-replayed baseline.
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

Reference values on the shipped data: R = 3600, J = 8592 (1059 of them rejected
`touch` operations), and the spine is `handshake_timeout_ms` 467, `max_sessions`
180, `rekey_interval_s` 3600, `retry_budget` 4, `mode` `strict-seal`. Z depends on
the bytes of the agent's own `tool.zip`, so the shift is `11 + 5 + (Z mod 53)`.

## Verification

Grader entrypoint: `tests/test.sh`. It clears stale reward files, locks
`/logs/verifier` to root, restricts `/tests`, then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
rewardkit scores Channel A from the `@criterion` checks in `tests/test_output.py`,
each weighted by its `criteria.<name>(weight=W)` registration, and Channel B from
`tests/judge.toml`. `tests/reward.toml` divides each channel's weighted sum by its
positive total and gives each half of `reward`, so the combined reward runs from
-1.000 to +1.000. The oracle and nop calibration runs score Channel A alone.

Channel A declares 29 positive and 6 negative tests, positive weight total 97 and
negative weight total -26, so the theoretical range is -26/97 = -0.268 to +1.000.

Positive tests:

- `artifacts_exist` (weight 1)
- `config_is_flat` (weight 3)
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
- `cli_reproduces_derived_outputs` (weight 5)
- `json_artifacts_canonical` (weight 3)
- `commands_through_cli_count_matches` (weight 3)
- `zip_shift_present_and_coherent` (weight 3)
- `profile_trailer_embeds_config_sha_prefix` (weight 3)
- `config_sha_in_posture_matches_file` (weight 3)
- `touch_rejected_counter_nonzero` (weight 3)

`aggregates_match` and `zone_totals_match` compare against the grader's own
reduction. The mirror views, `corpus_index_match`, `posture_match` and the
`aggregate_total` fields of `validation_report.json` and `summary.json` compare
against the agent's own `aggregates.json`, and only after that file agrees with
the grader's reduction at the true shift on at least 45 of the 50 corpora, so one
mis-derived corpus costs `aggregates_match` alone while a wrong shift or a
hand-written table loses the whole family. `report_transcript_real`,
`report_digest_truthful` and `tool_round_trips` run the agent's rebuilt CLI from
`tool.zip`: `validate` must accept the delivered policy and refuse a nested or
incomplete copy, `set` must write a JSON integer, and the recorded `init` and
`set` calls, replayed in a scratch directory, must rebuild `config.json` byte for
byte. `cli_reproduces_derived_outputs` runs the rebuilt `compile`, `aggregate`
and `plan` against the shipped inputs and requires the delivered files back, and
runs `aggregate` on a private copy of one corpus to confirm the tool reduces what
it reads.

Negative tests (6) are polarity-inverted: their assertions hold only when the
cheat is present, so an honest run leaves them failing and they subtract only
from a solver that cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_nested_or_dynamic` (weight -5)
- `negative_fake_transcript` (weight -3)
- `negative_network_or_secret` (weight -3)
- `negative_no_homoglyph_counts_leaked` (weight -5)
- `negative_no_svc_in_zone_totals` (weight -5)

Channel B is 16 criteria (15 positive / 1 negative), positive total 53, negative total -5:

- **R1** (+3, trajectory): The agent inspects the local CLI source, schema file, and failing command behaviour before editing.
- **R2** (+5, trajectory): The agent repairs root causes in argument parsing, flat-key validation, and deterministic serialization rather than only writing final JSON by hand.
- **R3** (+3, trajectory): The agent uses only local files and standard-library Python capabilities while configuring the CLI.
- **R4** (+5, trajectory): The agent runs the repaired CLI to create and validate the delivered configuration artifact.
- **R5** (+3, trajectory): The agent records a report whose command outcomes are supported by actual terminal evidence.
- **R6** (+5, trajectory): The agent uses the repaired CLI's set subcommand to apply the flat scalar configuration values that the delivered config.json carries, rather than hand-writing those values into the file.
- **R7** (-5, trajectory): The agent retrieves a task-specific repaired CLI, prior submission, or hidden policy from an external source.
- **R8** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R9** (+3, trajectory): The agent extracts /app/data/tool.zip into /app/tool with a method that keeps every member path inside /app/tool.
- **R10** (+3, trajectory): The agent recomputes the sha256 of every manifest-listed artifact after its final write and compares each digest with the matching manifest.sha256 line.
- **R11** (+5, trajectory): The agent treats a value as canonical only when str(int(x)) equals the raw field bytes exactly, and rejects every non-canonical form the contract names: leading zeros, -0 / -00 / -000, leading plus, surrounding spaces, underscores, hex, floats, units, words, scientific notation, Devanagari U+0966 range, Arabic-Indic U+0660 range, Gujarati U+0AE6 range, and full-width U+FF10 range.
- **R12** (+3, trajectory): The agent demonstrates that the journal replay evaluates max_sessions validity against the spine state at that seq by relying on the current rekey_interval_s and handshake_timeout_ms at that moment.
- **R13** (+3, trajectory): The agent derives the Z shift from the sha256 of the rebuilt /app/out/tool.zip and applies Z mod 53 to every corpus upper bound.
- **R14** (+3, trajectory): The agent demonstrates byte-exact zone matching that rejects U+0441, U+200B, U+00A0, and U+FEFF by name, and shows the per-byte comparison used.
- **R15** (+3, trajectory): The agent re-runs the CLI command that exposed each source defect after editing the code for it and checks the new output.
- **R16** (+3, trajectory): The agent re-runs the pipeline from a scratch copy of the delivered /app/out/tool.zip into a scratch output directory and compares the sha256 of the regenerated tool.zip and every regenerated manifest-listed artifact with the delivered /app/out copies.

The oracle expectation is that running `solution/solve.sh` inside the container
drives every positive Channel A test to pass and holds every negative test in its
failing state, for a Channel A reward of +1.000.

## Root cause

**Repair and use are one task.** A posture written by hand can be made correct in
a minute; a posture produced by a repaired tool requires the tool to work, and the
report is the receipt. The checks that run the rebuilt tool sit at the top of the
scale for this reason.

**Flatness is a contract.** The sidecar schema declares `scalar_only`, the tool's
own `validate` refuses any `dict` or `list`, and the configuration carries exactly
ten scalar keys. The nested `settings` object and any convenience grouping both
break it.

**Coercion at the boundary.** Every `set` value arrives as a string. A policy in
which an integer key holds a string is a different document, compares unequal to
the baseline, and serialises differently.

**The eligibility rule is narrow.** A corpus row counts only when its zone is
byte-exactly one of the four active zones, its flag is byte-exactly `active`, and
its value is a canonical base-10 integer inside the shifted corpus bound. A large
share of every corpus is trap rows that fail one clause.

**Determinism.** JSON key order, zip member order and timestamps, and any
wall-clock or random value must be pinned, or two runs disagree.

**The pipelines are chained, not parallel.** The corpus bounds are a function of
the compiled spine, the journal classification across the base and zone replays,
and the packaged tool, so all three must be right before any non-`min` aggregate
is right.

## Solution shape

1. Extract `/app/data/tool.zip` into `/app/tool`, refusing members that resolve
   outside it.
2. Read `/app/data/config_contract.md`, the schema, the defaults, the rules, the
   overrides and the journal, and decide what each contributes.
3. Rewrite `cli.py`: make the subparser required; fix `init` to emit a flat
   document; fix `set` to keep the key and write integers as integers; fix
   `validate` to read the archive schema's comma-separated keys and refuse nested
   or missing keys; fix `export-report` to write the structured report; serialise
   every JSON file with the contract's parameters.
4. Implement `plan` (stateful base and zone replay), `compile` (byte-exact corpus
   reduction under the shifted bound, writing the aggregate, mirror, zone-total
   and corpus-index files) and `aggregate`.
5. Drive the repaired tool: `init`, one `set` per planned key, `validate`, then
   package `/app/tool` into `/app/out/tool.zip` from a sorted member list with
   fixed timestamps and attributes, then `compile`, the fifty `aggregate` calls
   and the zone `plan` calls.
6. Write the remaining roll-ups, run `export-report` with the accumulated
   transcript, then `validation_report.json` and the manifest.

## Ordered plan

1. Extract and read before editing; run each existing command once and record how
   it fails. Rubric R1 credits this inspection.
2. Separate the contract from the code: write down the ten keys, the validity
   rules, the eligibility rule and the aggregation operators first.
3. Repair `init`, `set` and `validate`, re-running each failing command after its
   edit. Rubrics R2 and R15 credit repairing at the root and confirming each fix.
4. Implement `plan`, `compile` and `aggregate`, then drive the full sequence as
   subprocesses. Rubrics R4 and R6 grade building the policy through the tool,
   and rubrics R11 to R14 grade the replay, bound and eligibility reasoning.
5. Repair `export-report` last, once a real transcript exists; rubric R5 grades
   the report outcomes against the terminal output.
6. Package the tool and write the roll-up artifacts from what the run observed,
   then recompute the manifest digests after the last write (rubric R10).
7. Re-run the pipeline from a scratch copy of the delivered archive and compare
   every digest (rubric R16), then summarise where each artifact was written
   (rubric R8). Rubric R9 credits safe extraction and R3 the local-only toolset.

## Pitfalls

- **Hand-writing an artifact.** It is faster and it is the most expensive choice
  here; `report_transcript_real`, `cli_reproduces_derived_outputs` and rubric R4
  read the evidence that the tool produced the files.
- **Counting a trap row.** A row whose zone, flag, or integer form is off by one
  clause does not count; `aggregates_match` fails on a single mis-counted corpus.
- **Trimming field bytes.** Padding spaces inside a delimited field, an XML
  element's text or a property value are field bytes; trimming them counts rows
  the contract rejects.
- **Applying a journal operation out of order, without validating it, against the
  wrong state, or ignoring an `unset`.** `config_matches_policy`, `profiles_match`
  and `rejected_ops_match` read the event-sourced replay.
- **Scoring a corpus with the published bound instead of the shifted one.** The
  effective upper bound is `hi + (R mod 97) + (J mod 31) + (Z mod 53)`; the
  aggregate family fails on any shift error.
- **Replacing the archive schema.** `tool_round_trips` runs the rebuilt tool's
  `validate` against the `schema.json` inside the delivered `tool.zip`.
- **Leaving `settings` nested or a value as a string.** `config_is_flat` and
  `negative_nested_or_dynamic` both read the delivered policy.
- **A non-deterministic `tool.zip` or unsorted JSON.** `zip_shift_present_and_coherent`,
  `json_artifacts_canonical` and `manifest_correct` compare exact bytes and layout.
- **Embedding derived numbers in the tool source.** `negative_hardcoded_sample_answers`
  fires when the source carries the answers instead of computing them.
- **Normalising Unicode or parsing through `float`.** Look-alike digits and values
  past 2**53 must be judged by exact `str(int(value)) == value`.
- **Naming a host, URL, token or key.** `negative_network_or_secret` scans the
  delivered policy, the report and the tool source.

## Provenance

```yaml
instance_id: 4ee62df1-ecaf-5e15-a9f8-16682c3136e7
task_name: terminal-bench/4ee62df1-ecaf-5e15-a9f8-16682c3136e7
language: python
```

## Hardening defects and verification

### Hardening defects

- **H1 (focal)** The journal replay is stateful and single-pass. A `set` on
  `max_sessions` whose value exceeds `floor(current(rekey_interval_s) /
  current(handshake_timeout_ms))` at that moment is invalid, in the base replay
  and in every zone replay against that zone's state.
- **H2 (focal)** The ZIP's sha256 (first 16 hex chars, mod 53) is a third
  additive shift on every corpus upper bound.
- **H3 (focal)** Zone profile trailers embed the first 8 hex chars of
  `sha256(/app/out/config.json)`, so the config must be byte-frozen before any
  profile is written.
- **H4 (drift)** The obvious "classify then apply" two-pass pipeline is wrong.
- **H5 (drift)** Zone tokens carrying a Cyrillic `с`, a zero-width space or a BOM
  never equal an ASCII zone name; tokens padded with a no-break space become equal
  to one under `str.strip()`, which is why only a byte-exact comparison is right.
- **H6 (trap)** `touch` ops with a value mismatch, a non-integer value on a spine
  key, or a key outside the spine keys and `mode` are rejected and counted toward
  J, but never mutate state.
- **H7 (trap)** The `c49` maximum depends on honest 2**53+N integer handling.

### Hardening verification

- The aggregate shift is `(R mod 97) + (J mod 31) + (Z mod 53)` with Z from
  the rebuilt tool.zip's sha256. All three moduli are pairwise coprime.
- `validation_report.json.checks.commands_through_cli` equals the number of
  entries in `report.json`'s `commands` list and is at least 53.
- `posture.json.zip_sha256` and `posture.json.config_sha256` are checked against
  the delivered bytes, and `posture.json.touch_rejected` against the grader's own
  replay (1059 on the shipped journal).

### Negative test channel coverage

- `negative_no_homoglyph_counts_leaked` (weight -5): penalises a non-ASCII zone key in zone_totals.
- `negative_no_svc_in_zone_totals` (weight -5): penalises a nonzero total for the reserved `svc` zone.
