# Lifecycle rules

## Lease events

`lease_events.jsonl` carries `ACTIVATE`, `BUYOUT`, `PAYOFF`, `CHARGE_OFF` and
`VOID` records. Lines that are byte for byte identical are one record and
count once in `duplicates`. An event is identified by `event_id`; a later
`version` of the same `event_id` replaces the earlier one. The governing
version of an event at an instant is the highest version known at the
instant (ties go to the later `recorded_at`). When the governing version is a
`VOID`, the event is withdrawn and has no effect. An event whose `lease_ref`
names no lease is rejected with reason `unknown_lease`.

The state of a lease on a date, as known at an instant, comes from replaying
the governing versions known at the instant whose `effective_date` is on or
before the date, in order of `effective_date` and then `event_id`. A lease
starts `pending`. `ACTIVATE` moves `pending` to `active`. `BUYOUT` and
`PAYOFF` move `active` to `closed` on their effective date, and `CHARGE_OFF`
moves `active` to `charged_off` on its effective date. Any other event is an
invalid transition: it is ignored and the replay continues. The events found
invalid when every event known at the watermark is replayed are rejected with
reason `invalid_transition`.

## Payment holidays

`relief_approvals.csv` holds the status rows of payment holiday requests. The
rows of one request, known at an instant, are taken in order of `status_at`
and then `status_id`. The only valid moves are a first `REQUESTED`,
`REQUESTED` to `APPROVED` or `DECLINED`, and `APPROVED` to `WITHDRAWN`. A row
making any other move is ignored; the rows ignored when every row known at the
watermark is replayed are rejected with reason `invalid_transition`, keyed by
`status_id`. A row whose `lease_ref` names no lease is rejected with reason
`unknown_lease`.

A request is in force at an instant when its last valid status known at that
instant is `APPROVED`. A lease may have at most `max_holidays_per_lease`
holidays in force. When more are in force, the requests with the earliest
`APPROVED` row (by `status_at`, then `request_id`) govern and every other
request in force is rejected, as known at the watermark, with reason
`holiday_limit`, keyed by `request_id`. A governing request defers the lease's
instalments from `first_deferred_instalment` onward by `months` months
(`schedule_rules.md`).
