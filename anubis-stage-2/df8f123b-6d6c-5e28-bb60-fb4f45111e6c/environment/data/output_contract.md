# Output contract

Every artifact is JSON written with two space indentation, keys sorted as text and
one closing newline. Every instant is written in ISO 8601 form with a +00:00
offset and whole seconds. Every minute figure is a whole number. Lists of pledge
identifiers are sorted as text.

## /app/out/report.json

| key | value |
| --- | --- |
| window_id | the window identifier |
| governing_mode | strict or tempered |
| settlement_cutoff | the cutoff instant |
| pledges | one entry per docket pledge, sorted by pledge_id |
| counts | the state tally of the docket |

A pledge entry carries exactly these keys: pledge_id, counterparty_key,
pledge_class, governing_due_instant, due_authority, due_record_key,
effective_discharge_instant, lateness_minutes, granted_minutes, residual_minutes,
final_state, reason_codes. effective_discharge_instant is null when the pledge has
no effective instant. final_state is one of cleared, tempered_clear, breached,
waived, blocked, held, lapsed.

Lateness is charged only against discharge evidence. A waived pledge carries the
waiver grant instant as its effective instant and no lateness. A pledge whose
final state is anything other than breached carries residual minutes of zero.

A pledge filed directly in the register reports its register record key. A series
instance has no register row of its own, so its due record key is built from the
letters SRX, the series identifier and the period label, joined by single hyphens,
giving a key of the shape SRX-SR-0000-YYYY-MM for a monthly period and
SRX-SR-0000-YYYY-Qn for a quarterly one.

counts carries exactly these keys: audit_total, breach_rate_denominator, breached,
cleared, tempered_clear, waived, blocked, held, lapsed. audit_total is the number
of docket pledges. breach_rate_denominator counts docket pledges whose class facts
in force carry an in breach rate flag of yes and whose final state is one of
cleared, tempered_clear, breached, waived.

## /app/out/final_state.json

Exactly these keys, read from the interface state after the closure confirmation
has been issued, so the refusal tally includes that confirmation: sealed, window_id,
registered, accepted_transitions, rejected_calls, state_counts, grace_granted_total,
total_lateness_minutes, settlement_fingerprint. state_counts carries one key per
final state with the same names the report uses.

## /app/out/transcript_summary.json

Exactly these keys: total_calls, accepted_calls, rejected_calls, calls_by_channel,
rejections_by_reason, first_sequence, last_sequence, seal_sequence.
calls_by_channel carries the keys api and cli. rejections_by_reason carries one key
per reason that occurred, with its count.

## /app/out/scenario_alpha.json

Exactly these keys: scenario_id with the value alpha, basis with the value
grace_withdrawn, breached, tempered_clear, reverted_pledges, total_residual_minutes.
The scenario repeats the settlement with no grace round at all and reports the
pledges that lose their tempered clear state. total_residual_minutes sums the
residual minutes of every pledge breached in that grace withdrawn settlement,
not only the pledges listed in reverted_pledges.

## /app/out/scenario_beta.json

Exactly these keys: scenario_id with the value beta, basis with the value
presence_zone_resolution, docket_size, breached, membership_changes,
lateness_delta_minutes. The scenario resolves every due expression in the zone the
principal occupied at the origin instant of the pledge, taken from
travel_itinerary.csv with half open legs and the home zone outside every leg, and
leaves every other rule unchanged. membership_changes lists the pledges that join
or leave the docket under that resolution. lateness_delta_minutes is the total
lateness of the scenario docket less the total lateness of the filed docket.

## /app/out/scenario_mode.json

Exactly these keys: scenario_id with the value mode, governing_mode,
countersignature_authority, tallies, grace_pool_minutes, grace_unused_minutes.
tallies carries the keys strict and tempered, each with the keys breached, cleared,
tempered_clear and waived. grace_unused_minutes is the pool less the granted total.

## /app/out/summary.json

Exactly these keys: window_id, governing_mode, audit_total, breach_rate_denominator,
breached_in_rate, breach_rate_per_mille, granted_minutes_total, unresolved_pledges,
settlement_fingerprint, counterparty_count, top_breach_counterparty.
breached_in_rate counts breached docket pledges that also sit in the
breach rate denominator. unresolved_pledges lists docket pledges whose final state
is blocked or held. counterparty_count is the number of distinct holders on the
docket. top_breach_counterparty is the holder key with the most breached pledges,
and a tie goes to the lower holder key as text.
