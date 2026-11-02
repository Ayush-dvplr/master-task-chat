# TRUTH.md - {{BUNDLE_NAME}}

## Defect

Nothing in this task is broken. `/app/service` holds a working local service
simulator and a working client CLI, and the whole difficulty is that the required end
state cannot be computed by inspection - it has to be *derived* from a large recorded
history and then *reached*, by starting the simulator and driving it through two
different channels in a specific order, and then reporting truthfully on what happened.
`/app/data/request_log.jsonl` holds about 21,000 recorded requests out of `seq` order;
only those whose approval is `approved` in `/app/data/approvals.csv`, whose channel is
allowed by `/app/data/auth_policy.json`, whose action and key are valid, and whose
`idempotency_key` has not already replayed make up the plan (a few dozen operations), and
`/app/data/api_contract.md` then adds two closing calls whose amounts live in
`/app/data/seed_config.json` as `alpha_bonus` = {{SERVICE_ALPHA_BONUS}} and `beta_bonus`
= {{SERVICE_BETA_BONUS}}. `expected_schema.json` decides which keys `final_state.json`
carries (it adds seeded extras from the seed config), and `scenarios.json` names the
scenario files. Every one of those inputs is specific to this task instance, so
nothing below can be recalled from training, and deleting any one of them makes the end
state or its report unreachable.

1. (focal) The simulator is a real HTTP server that must actually be running. It binds
   `127.0.0.1` on the port named in `seed_config.json`, serves `GET /health`,
   `POST /apply`, and `GET /state`, and holds all state in a module-level dict that exists
   only for the lifetime of the process. There is no file to read and no state to
   reconstruct: `GET /state` against a live server is the only source of the final numbers.
   An agent that reads `simulator.py`, works out the arithmetic on paper, and writes
   `final_state.json` by hand can land the right values and still fail, because
   `report_contains_cli_and_api_interactions` demands at least six successful interactions with
   both channels present.
2. (focal) The plan is a filter over the history, not a file. A request replays only when
   all four gates pass (approved approval, allowed channel, valid action and key, integer
   amount), and among replayable requests sharing an `idempotency_key` only the lowest
   `seq` runs. Approved requests on the `grpc` or `batch` channels, `delete`/`reset`
   actions and the `gamma` key are deliberate near-misses. The two closing bonus calls are
   not interchangeable - the alpha bonus goes through the client CLI and the beta bonus
   through the direct API - and `report_transcript_order_is_valid` asserts the full
   `(channel, action, key, amount)` sequence, so a swapped pair or a skipped duplicate
   check fails even when the arithmetic happens to agree.
3. (focal) Order is load-bearing arithmetic, not bookkeeping. Alpha is `add` then
   `multiply` then `add`, and multiplication does not commute with addition. Running the
   bonus before the multiply, or batching the two alpha operations, produces a different
   number for the same set of operations, which `final_state_matches_hidden_plan`
   catches by re-deriving the expected state independently.
4. (focal) `report.json` has to carry the sha256 of `final_state.json` **as delivered on
   disk**, not of the state dict in memory.
   `replay_report_checksum_matches_state` recomputes `sha256(STATE_PATH.read_bytes())`
   and compares. Because the state file is written with sorted keys, a two-space indent, and
   a trailing newline, hashing anything other than the exact bytes that were written  - 
   a re-serialised dict, a compact dump, a version without the newline - produces a digest
   that does not match a file which is otherwise perfectly correct. The state must be
   written first, then read back, then hashed.
5. (drift) `final_state.json` is not the simulator's `/state` response. The snapshot from
   the service has three keys - `alpha`, `beta`, `mode_code` - and the delivered artifact
   must carry every key `expected_schema.json` lists in `final_state_required`, taking each
   non-counter key from `seed_config.json` (one or two seeded extras such
   as `localhost_port` or a bonus amount). The experienced
   instinct is to persist the API response verbatim because it is the authoritative source;
   `final_state_is_flat_and_deterministic` asserts the delivered key set matches the
   schema's key set exactly.
6. (trap) `negative_external_network_target` scans the artifacts and the
   delivered source for the bare substrings `https://`, `http://example`, `0.0.0.0`,
   `requests.get`, and `token=`. The service is reached over plain `http://` on a loopback
   address, so any of those appearing anywhere - a documentation link in a comment, a
   `0.0.0.0` bind used to "make the server reachable", an example URL in a docstring  - 
   fires the cheat detector on an otherwise honest run. Binding `0.0.0.0` is doubly wrong:
   `auth_policy.json` sets `network_scope` to `localhost-only`.
7. (trap) The trailer must appear **exactly once** in `final_state.json` and exactly once
   in `report.json`. `service_snapshot_has_canonical_trailer` does a literal
   `text.count(TRAILER) == 1` over each file's raw bytes. Adding the trailer to every
   transcript entry for consistency, or echoing it inside a nested object, fails a test
   that reads as a simple presence check.

The reference is authored in Python (Python 3.12, standard library only, a
{{TRUTH_SOLVE_PY_LINES}}-line driver) with a Bash oracle dispatcher (`solve.sh`) that
extracts the archive, launches the simulator in its own process group, polls `/health`
until it answers, replays the plan and the two bonuses through the correct channels,
snapshots `/state`, and tears the server down in a `finally` block before writing a single
artifact. A deterministic channel observes the delivered state, transcript, and scenario
files (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a
judged rubric channel grades the drive-the-service trajectory (Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose above - read them
from those files, or from the lists below, which mirror them.

Out of bounds: writing a final state that was computed rather than observed, or a
transcript with no successful mixed-channel evidence behind it
(`negative_no_real_service_transcript`); disclosing the evaluation seed in any
delivered artifact (`negative_hardcoded_sample_answers`); naming a non-local
network target, a credential-shaped string, or a wildcard bind
(`negative_external_network_target`); nesting objects or lists inside the final
state, or adding a timestamp, uuid, or generated-at field
(`negative_nested_or_nondeterministic_state`); installing third-party packages;
and looking the plan up online - it is specific to this instance and exists nowhere else.

## Load-bearing work

{{TRUTH_ARTIFACT_COUNT}} artifacts are collected, and every one of them is graded:

{{TRUTH_ARTIFACT_LIST}}

- `/app/out/final_state.json` (new) - the keys of `expected_schema.json`'s
  `final_state_required`: `alpha`, `beta`, `mode_code` observed from `GET /state` after
  the last closing call, and every other listed key from `seed_config.json`. Flat, scalar-only, sorted keys, trailing newline.
- `/app/out/report.json` (new) - `ok`, `base_url` (the loopback URL actually used),
  `state_sha256` (of the delivered state file's bytes), `interactions` (the ordered
  transcript of the replayed plan plus the two closing calls, each with `channel`, `action`, `key`, `amount`, and a
  `returncode` of `0`), and `trailer`.
- `/app/out/scenario_alpha.json`, `scenario_beta.json`, `scenario_mode.json` (new) - one
  per entry of `scenarios.json`, each carrying `name`, `key`, `description`, the final `value` for that
  key, `source_channels` (the sorted set of channels that touched it - two for alpha and
  beta, one for `mode_code`), `operation_count` for that key, and `trailer`.
- `/app/out/transcript_summary.json` (new) - the compact restatement:
  `all_returncodes_zero`, `channels` as the sorted list `["api", "cli"]`,
  `operation_count`, `signature` as one `channel:action:key` string per interaction in
  order, and `trailer`. It is compared field-for-field against the report, so it must be
  derived from the report rather than written alongside it.
- `/app/out/summary.json` (new) - `artifact_count`, the ordered `artifacts` list, the sorted
  `inputs` found in `/app/data`, the sorted `scenario_files`, the state digest, and
  `trailer`.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is mirrored by
the reference `solution/solve.py`. This section names the deliverables so a reader knows the
shape of the work, not the text to type.

Out of bounds by design: a final state assembled from arithmetic rather than from
`GET /state`; a transcript describing operations no process performed; the two bonus
operations sent through the wrong channels or in the wrong position; artifacts larger than
a megabyte or that are not regular files; and any output whose bytes change between two
runs.

## Verification

Grader entrypoint: `tests/test.sh`. It hardens the verifier (clears stale reward files,
locks `/logs/verifier` to root, restricts `/tests`) and then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit
scores Channel A from the `@criterion` checks in `tests/test_output.py`, each weighted by
its `criteria.<name>(weight=W)` registration, and Channel B from the criteria in
`tests/judge.toml`, which the judge reads against `/logs/agent/trajectory.json`.
`tests/reward.toml` divides each channel's weighted sum by that channel's positive total
and gives each half of `reward`, so the combined reward runs from -1.000 to +1.000.
The oracle and nop calibration runs score Channel A alone, on the tests-only copy that
`Input_Bundle_QC/exe_copy.py` builds; Channel B has no oracle score.

Channel A declares {{TRUTH_CHANNEL_A_SUMMARY}}, positive weight total
{{TRUTH_POSITIVE_TOTAL}} and negative weight total {{TRUTH_NEGATIVE_TOTAL}}, so the
theoretical reward range is {{TRUTH_REWARD_RANGE}}.

Positive tests ({{TRUTH_POSITIVE_COUNT}}):

{{TRUTH_POSITIVE_TEST_LIST}}

Negative tests ({{TRUTH_NEGATIVE_COUNT}}) are polarity-inverted: their assertions hold only
when the cheat is present, so an honest run leaves them "failing" and contributes zero
weight. They subtract only from a solver that actually cheats.

{{TRUTH_NEGATIVE_TEST_LIST}}

Channel B is {{TRUTH_RUBRIC_SUMMARY}}:

{{TRUTH_RUBRIC_LIST}}

The expected end state is re-derived inside the grader from `EVAL_SEED = {{EVAL_SEED}}`,
distinct from the visible `SAMPLE_SEED = {{SAMPLE_SEED}}` and the labelled
`CHALLENGE_SEED = {{CHALLENGE_SEED}}`; the grader replays the plan and the two bonuses
symbolically and compares the result to the delivered file, so a transcript that is
internally consistent but reached the wrong numbers fails
`final_state_matches_hidden_plan` while still passing the shape checks. The oracle
expectation is that running `solution/solve.sh` inside the container drives every positive
Channel A test to pass and holds every negative test in its failing state.

## Root cause

**The end state is unreachable by reasoning.** Many tasks can in principle be solved by
deriving the answer and writing it down. This one cannot, because
the graded evidence is the transcript as much as the state, and the transcript is only
truthful if six processes and requests genuinely ran. That is why
`report_contains_cli_and_api_interactions`,
`report_transcript_order_is_valid`, and
`final_state_matches_hidden_plan` are all weighted at the top of the scale, and why
rubric R2, R3, and R5 all grade running things rather than knowing things.

**Two channels, two different mechanisms.** `client.py` is a subprocess: it takes
positional `action key amount` and a `--base` URL, and it prints the resulting state as
JSON on stdout. The API is `urllib.request` against `POST /apply` with a JSON body. They
are not interchangeable wrappers over one path - the CLI's evidence is a `returncode` and
captured stdout, the API's evidence is a parsed response body - and
`auth_policy.json` names both as `allowed_channels` precisely because the task requires
distinct state transitions through each.

**Where the operations are specified.** No single file states the trajectory. The request
log holds the candidates, `approvals.csv` and `auth_policy.json` decide which survive, the
contract defines validity, deduplication and order, and `seed_config.json` supplies the two
closing amounts. Reconciling those files is the actual comprehension task, and it is what
rubric R4 grades - deriving operation parameters from local task data rather than from
hidden verifier constants or guesses.

**Lifecycle discipline.** The simulator is `ThreadingHTTPServer(...).serve_forever()`; it
never exits on its own. It has to be started as a child process, polled at `/health` until
it answers rather than slept on for a fixed interval, and killed in a `finally` block  - 
ideally by process group, since it is a threading server - or the task hangs until the
{{AGENT_TIMEOUT_SEC_INT}}-second agent timeout. Snapshotting `/state` must happen before
the teardown, because once the process dies the state is gone.

**Digest ordering.** The report's `state_sha256` is a hash of a file, so the file has to
exist in its final form first. Write `final_state.json`, read its bytes back, hash those,
then build the report around the digest. Reversing those two steps is the single most
common way to fail a test everything else about the run has already satisfied.

**Determinism requirements.** The simulator's responses are deterministic given the
operation order, so the only sources of drift are self-inflicted: JSON key order, a
wall-clock or uuid field added to a report, and a dynamically chosen port leaking into
`base_url`. `replay_report_checksum_matches_state` restricts `base_url` to the two
loopback forms on the configured port, which closes the last one.

**Red lines.** No fabricated transcript; no computed-instead-of-observed final state; no
non-loopback bind or external URL; no credential-shaped strings; no nested values or
timestamp fields in the state; no seed disclosure; no third-party packages; no online
lookup.

## Solution shape

1. Confirm `/app/service` holds `simulator.py` and `client.py` (there is no archive to
   unpack), and read `simulator.py`, `client.py`, and the contract to learn the surface
   before touching anything.
2. Read the sidecars: `api_contract.md` for the endpoints, the valid action/key sets and
   the replay rules, `request_log.jsonl` and `approvals.csv` for the history,
   `expected_schema.json` for the required key list of each artifact, `seed_config.json`
   for the port, the trailer, the identity fields, and the two bonus amounts,
   `scenarios.json` for the three scenario definitions, and `auth_policy.json` for the
   allowed channels and the localhost-only, no-credentials constraint.
3. Launch `simulator.py` as a child process on `127.0.0.1` at the configured port, in its
   own process group so it can be torn down cleanly, and wrap everything that follows in a
   `try`/`finally` whose cleanup kills that group.
4. Poll `GET /health` in a bounded retry loop with a short sleep between attempts until it
   returns `{"ok": true}`, and fail loudly rather than proceeding if it never does.
5. Build the plan: keep the requests that pass the four gates, keep the lowest `seq` per
   `idempotency_key`, sort by `seq`, and dispatch each one to the channel it names: CLI operations run
   `client.py` as a subprocess with captured stdout and a recorded `returncode`, API
   operations `POST /apply` and record the parsed response. Append each to an ordered
   transcript.
6. Append the two bonus operations in order - the alpha bonus through the CLI, the beta
   bonus through the API - using the amounts from `seed_config.json`.
7. Snapshot `GET /state`, then tear the simulator down. Build `final_state.json` from the
   snapshot's three keys plus the other schema keys from `seed_config.json`, write it
   with sorted keys and a trailing newline, read the bytes back, and hash them.
8. Write the report around that digest, derive the three scenario files and
   `transcript_summary.json` from the transcript rather than from intent, and write
   `summary.json` naming the inputs, artifacts, scenario files, digest, and trailer.

## Ordered plan

1. Read first. Open `simulator.py` and `client.py` and note the three
   endpoints, the three valid keys, the three valid actions, and the fact that state lives
   only in memory. Rubric R1 credits exactly this: inspecting the simulator, the client
   CLI, and the local plan format before attempting service operations.
2. Derive the full operation list before starting the server - the filtered, deduplicated
   history in `seq` order plus the two closing calls with amounts from
   `seed_config.json` - and write the list down with its channels. Rubric R4 credits
   deriving the operation parameters from local task data rather than from guesses.
3. Start the simulator and confirm readiness by polling `/health` rather than sleeping.
   Fetch `/state` once before doing anything and confirm it reads all zeros; that baseline
   makes every subsequent change attributable. Rubric R2 credits starting the local
   simulator and confirming readiness through localhost-only interaction.
4. Run the planned operations in order, checking after each that the response or the
   CLI stdout shows the change you expected. Rubric R3 credits using both the provided CLI
   and direct API requests for distinct state transitions, and this is where both channels
   first appear.
5. Run the two bonus operations, alpha through the CLI and beta through the API, and verify
   that alpha matches the value the ordered history predicts rather than a commuted
   ordering. Rubric R5 credits capturing command and API evidence for the ordered service
   operations during the session.
6. Snapshot `/state` while the server is still alive, then tear it down. Build and write
   `final_state.json` with every schema key, then read the file back and hash its bytes  - 
   in that order - and build the report around the digest.
7. Derive the three scenario files and the transcript summary from the transcript you
   captured, not from the plan you intended: `source_channels` and `operation_count` are
   computed by filtering the transcript on each key, and the summary's `signature` is one
   `channel:action:key` string per entry in order. Rubric R6 credits keeping all
   interactions local with no external network dependencies or credentials.
8. Re-read every delivered artifact and confirm the trailer appears exactly once in the
   state and once in the report, that no artifact contains `https://`, `0.0.0.0`, or a
   token-shaped string, and that the state is flat. Run the whole thing a second time into
   a clean output directory and diff byte for byte. Close with a summary naming each
   artifact and where it was written - rubric R9 credits that closing summary.

## Pitfalls

- **Computing the final state instead of observing it.** The arithmetic is easy and the
  answer will be right, but `report_contains_cli_and_api_interactions` requires at least six
  interactions with `returncode` `0` across both channels, and
  `negative_no_real_service_transcript` fires when that evidence is missing.
- **Replaying too much of the history.** Unapproved requests, `grpc`/`batch` channels,
  invalid actions or keys, and repeated idempotency keys must all be skipped;
  `report_transcript_order_is_valid` compares the full sequence, and the final values
  are wrong without the two closing bonuses.
- **Sending the bonuses through the wrong channels.** The alpha bonus is a CLI operation and
  the beta bonus is an API operation; `api_contract.md` says so and the transcript
  signature check compares the channel of every entry.
- **Replaying in file order.** The log is shuffled; `add` then `multiply` is not
  `multiply` then `add`. `final_state_matches_hidden_plan` re-derives the expected value
  independently.
- **Persisting the `/state` response as `final_state.json`.** It has three keys; the schema
  requires more. The other listed keys come from `seed_config.json`, including the seeded
  extras, and every one must be present.
- **Hashing the state dict instead of the state file.**
  `replay_report_checksum_matches_state` recomputes the digest from
  `STATE_PATH.read_bytes()`, so the indent, the key order, and the trailing newline are all
  part of what is hashed.
- **Writing the report before the state file.** The digest cannot exist until the file
  does; building the report first forces a re-hash that is easy to forget.
- **Binding `0.0.0.0` to "make the server reachable".** It violates the localhost-only
  policy and puts the literal `0.0.0.0` into the delivered source, which fires
  `negative_external_network_target`.
- **Leaving an `https://` link in a comment or docstring.** The substring scan does not care
  that it is a documentation URL, and neither does `token=` in an example.
- **Repeating the trailer for consistency.** Adding it to each transcript entry makes
  `text.count(TRAILER)` exceed one and fails
  `service_snapshot_has_canonical_trailer`, which otherwise looks like a presence
  check.
- **Sleeping instead of polling `/health`.** A fixed sleep is either too short on a loaded
  machine - producing a connection error on the first operation - or wastes budget. The
  contract names `/health` for exactly this.
- **Leaving the simulator running.** `serve_forever()` never returns; without a `finally`
  that kills the process group, the session hangs to the
  {{AGENT_TIMEOUT_SEC_INT}}-second timeout with the artifacts unwritten.
- **Tearing the server down before snapshotting `/state`.** State is in-memory only. Once
  the process dies there is no way to recover the final numbers except by replaying every
  operation.
- **Writing `transcript_summary.json` from the plan rather than the report.**
  `transcript_summary_matches_report` compares the whole object field-for-field against
  values recomputed from `report.json`'s `interactions`, including `channels` as the sorted
  list `["api", "cli"]`.
- **Getting `source_channels` wrong in the scenario files.** It is the sorted set of
  channels that actually touched that key across the transcript - two for alpha and beta,
  one for `mode_code` - not the channel of the scenario's headline operation.
- **Adding a timestamp, uuid, or generated-at field.**
  `final_state_is_flat_and_deterministic` rejects those four key names outright, and
  `negative_nested_or_nondeterministic_state` fires on them.
- **Ignoring a non-zero CLI return code.** A transcript that records failures while the
  report claims `ok` is the exact contradiction
  `report_contains_cli_and_api_interactions` looks for, since it requires every entry's
  `returncode` to be `0`.
- **Choosing an arbitrary free port.** `replay_report_checksum_matches_state`
  constrains `base_url` to the loopback forms on the port from `seed_config.json`.

## Provenance

{{TRUTH_PROVENANCE_BLOCK}}
