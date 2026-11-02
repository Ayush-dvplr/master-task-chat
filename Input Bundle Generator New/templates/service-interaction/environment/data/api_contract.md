# Local Service API Contract

The {{FORMAT_TAG}} simulator (`/app/service/simulator.py`, started with
`--host 127.0.0.1 --port <localhost_port from seed_config.json>`) binds to localhost only. Use `GET /health` to wait
for readiness, `POST /apply` with JSON fields `action`, `key`, and `amount` for
state transitions, and `GET /state` for the final snapshot.

Valid actions are `add`, `multiply`, and `set`. Valid keys are `alpha`, `beta`,
and `mode_code`. The simulator starts with all three at `0`. The client CLI
(`/app/service/client.py <action> <key> <amount>`) sends the same `POST /apply` call.

## Operation plan

The end state is the replay of the approved history, followed by two closing calls.

1. `request_log.jsonl` holds one recorded request per line: `seq`, `request_id`,
   `channel`, `action`, `key`, `amount`, `idempotency_key` and `approval` (an
   approval id or `null`). Lines are not in `seq` order.
2. A request is replayable when its `approval` is a row of `approvals.csv` whose
   `status` is `approved`, its `channel` is in `allowed_channels` of
   `auth_policy.json`, its `action` and `key` are valid as above, and its `amount` is
   an integer.
3. Replayable requests that share an `idempotency_key` replay once: the one with the
   lowest `seq`.
4. Replay the remaining requests in ascending `seq`, each through its own channel:
   `cli` through the client CLI, `api` through `POST /apply`.
5. Then make the two closing calls: through the CLI, `add alpha <alpha_bonus>`; then
   through the API, `add beta <beta_bonus>`, with both bonuses from `seed_config.json`.

`final_state.json` carries exactly the keys listed in `final_state_required` of
`expected_schema.json`: `alpha`, `beta` and `mode_code` from the final `GET /state`
snapshot, and every other listed key with its value from `seed_config.json`.

## Report artifacts

Each file under `/app/out` is one JSON object; key order and whitespace are free.
`trailer` is always the trailer string the service state carries.

- `report.json`: `ok`, `base_url`, `state_sha256` (sha256 hex of the bytes of
  `final_state.json`), `trailer` and `interactions`, one object per state-changing
  call in the order you made it, each with `channel` (`cli` or `api`), `action`, `key`,
  `amount` and `returncode` (the CLI exit status; `0` for an API call).
- `scenario_<name>.json`, one per entry of `scenarios.json`: `name`, `key` and
  `description` from that entry, `value` (the key's final value), `operation_count` (how many `interactions`
  touch the key), `source_channels` (the sorted distinct channels of those
  interactions) and `trailer`.
- `transcript_summary.json`: `all_returncodes_zero` (every interaction's `returncode`
  is `0`), `channels` (sorted distinct channels used), `operation_count` (the number of
  interactions), `signature` (one `"channel:action:key"` string per interaction, in
  order) and `trailer`.
- `summary.json`: `artifact_count`, `artifacts` (the seven deliverable paths in the
  order the task lists them), `inputs` (the sorted names of the files directly under
  `/app/data`),
  `scenario_files` (the sorted scenario file names), `state_sha256` and `trailer`.
