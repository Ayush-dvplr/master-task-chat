# Artifact contract

Every artifact is a JSON object encoded UTF-8, written under `/app/out`. Object
keys may stand in any order. A list that is empty is written as an empty list.

## `/app/out/report.json`

```
{
  "cycle_id": string,
  "decision_instant": string,
  "audit_count": integer,
  "decisions": [
    {"request_id": string, "unit_key": string, "revision": string,
     "target_channel": string, "site": string, "risk_tier": string,
     "decision": string, "reason_code": string}
  ],
  "reason_code_counts": {code: integer},
  "escalations": [{"unit_key": string, "original_reason_code": string}],
  "unresolved": [{"unit_key": string, "revision": string, "reason_code": string}],
  "admission_order": [string]
}
```

`decisions` holds one entry per adjudicated request, ordered by `request_id`
ascending. `reason_code_counts` holds only codes that occurred, ordered by the
registry order. `escalations` is ordered by unit key ascending. `unresolved` holds
the requests reported under the pending embargo code, ordered by unit key then
revision. `admission_order` holds the admitted requests in
admission order as `unit_key|revision|target_channel`.

## `/app/out/summary.json`

```
{
  "cycle_id": string,
  "inputs_seen": integer,
  "audit_count": integer,
  "admitted_total": integer,
  "deferred_total": integer,
  "rejected_total": integer,
  "withdrawn_excluded": integer,
  "escalated_total": integer,
  "admission_rate": number,
  "admitted_by_channel": {channel: integer},
  "coverage_share_pct": {channel: number},
  "repeat_deferral_count": integer,
  "closure_passes": integer,
  "rollback_holds": integer,
  "dependency_digest": string
}
```

`admitted_by_channel` and `coverage_share_pct` are keyed in ladder order.

## `/app/out/final_state.json`

The body of `GET /state` once the cycle has been driven, written unchanged.

## `/app/out/transcript_summary.json`

```
{
  "actor": string,
  "endpoint": string,
  "batch_limit": integer,
  "calls": integer,
  "replayed_calls": integer,
  "ops_submitted": integer,
  "ops_accepted": integer,
  "ops_rejected": integer,
  "seal_ops": integer,
  "aborted_calls": integer,
  "final_op_seq": integer,
  "idempotency_keys": [string]
}
```

`calls` counts the calls whose idempotency key was new. `replayed_calls` counts the
calls whose key had been seen. `ops_submitted` and `ops_accepted` count ops in the
new key calls only, and `ops_rejected` is the difference. `aborted_calls` counts
the new key calls the service refused whole. `endpoint` is the apply address the
cycle was driven through, written in full, and it is the one field in any artifact
that names a host. `idempotency_keys` lists the new keys in the order they were
used.

## `/app/out/scenario_alpha.json` and `/app/out/scenario_beta.json`

```
{
  "scenario": string,
  "decision_instant": string,
  "audit_count": integer,
  "admitted_total": integer,
  "deferred_total": integer,
  "rejected_total": integer,
  "reason_code_counts": {code: integer},
  "admitted_digest": string
}
```

`scenario` is `alpha` or `beta`.

## `/app/out/scenario_mode.json`

```
{
  "cycle_id": string,
  "modes": {
    "strict": {"admitted_total": integer, "deferred_total": integer,
               "attestation_failed": integer},
    "delegated": {"admitted_total": integer, "deferred_total": integer,
                  "attestation_failed": integer}
  },
  "delta": {"admitted_total": integer, "deferred_total": integer,
            "attestation_failed": integer}
}
```

`attestation_failed` counts requests reported under that code. `delta` is strict
less delegated, field by field.

## Normative parameters

```
json_indent: 2
```
