# Operations runbook

The relay service under `/app/service` owns the seating. Nothing else may write
it. Start it with the python interpreter on the host, on the base address in
`horizon_config.json`. It serves `GET /health`, `GET /state`, `GET /transcript`
and `POST /apply`.

A `POST /apply` body carries `ops`, `actor` and `idempotency_key`. The actor is
the one named in `relay_policy_baseline.json`. The batch limit is the advisory cap
recorded in the defaults section of `channel_budgets.ini` divided by the number of
channels on the ladder. The service refuses a call whose op count is above that
limit and applies nothing from it. A call whose `idempotency_key` has been seen
before returns the result the key first produced and advances no state.

Two op shapes exist. A promote op carries `op` set to `promote`, a `unit_key`, a
`revision`, a `target_channel` and `requires`, which is the list of this
revision's binding requirements as pairs of unit key and minimum revision. A seal
op carries `op` set to `seal` and a `channel`.

## Driving a cycle

Submit the admitted requests as promote ops in admission order. Fill each call to
the batch limit before opening another. When every promote op has been applied,
close the cycle with one further call that carries only seal ops, one per channel,
in ladder order. No promote op may share a call with a seal op.

The service reads the ops of a call in the order given. One refused op aborts the
whole call: the service reports the refusal with the index of the op that caused
it, applies nothing from that call, and advances no state. An aborted call is
still a call and is still counted. A cycle driven from a correct adjudication
aborts no call, so the aborted call count of a closed cycle is zero. Probing the
service with speculative ops therefore costs the whole call and shows up in that
count.

## Transcript

`GET /transcript` returns the calls the service has accepted. A call whose
idempotency key had been seen before is marked as a replay. After the seal call,
repeat the first promote call once, unchanged, so the transcript carries exactly
one replay and the state does not move.

## Normative parameters

```
replay_count: 1
seal_sequence: ladder
```
