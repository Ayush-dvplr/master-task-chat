# SDA output format reference

The exact shape of every artifact the replay writes. Column order, delimiter,
header rule and row order are all part of the contract. A file with the right
numbers in the wrong order is wrong.

Every file is UTF-8 without a byte order mark, line feed terminated, and ends
with exactly one trailing line feed.

## Header rule

Delimited artifacts, meaning the comma, tab, pipe and space separated ones,
carry a header line naming their columns in order. JSON Lines artifacts carry
no header line, and neither do the two whole document JSON artifacts.

## Empty column rule

A column defined below is always present on every row. Where the condition it
reports does not apply, the column carries the empty string. A row is never
shortened and a column is never dropped.

## Number rule

Ratios carry exactly four digits after the decimal point, rounded half to even
at emission. Counts and ticks are whole numbers with no decimal point.
Booleans are the bare lower case words `true` and `false`.

The window sequence column is a fixed width code of four characters with
leading zeros, matching the sequence inside the window identifier. It is not an
integer and its leading zeros are never stripped.

---

## `/app/out/stream_registry.csv`

Comma separated with a header. One row per recorded stream, ordered by
`stream_id` ascending.

    stream_id,tenant_id,priority_class,priority_rank,k_seed,admit_open,admit_close,status

`tenant_id` is the authoritative tenant. `k_seed` is the seed K as the corpus
recorded it, before any recalibration.

## `/app/out/token_classes.json`

One JSON object, no header. Keys are token identifiers and values are class
identifiers. The keys appear in ascending token ordinal order, which is the
order the token index records, and are never sorted as text.

## `/app/out/window_index.tsv`

Tab separated with a header. One row per recorded window, ordered by
`window_id` ascending.

    window_id	stream_id	seq	k_requested	drafted_recorded	slot	grant_tick	expiry_tick	repair_codes	terminal_band

`k_requested` is the repaired value. `drafted_recorded` is the length of the
repaired draft vector. `expiry_tick` is the recorded expiry, before any
revocation or cancellation is applied. `repair_codes` holds the codes that
applied, ascending, joined with a semicolon, and the empty string when none
applied. `terminal_band` is the band of the window's stream.

## `/app/out/lease_grants.psv`

Pipe separated with a header. One row per recorded window, ordered by `slot`
ascending, then `grant_tick` ascending, then `window_id` ascending. This order
differs from every other artifact and is deliberate.

    window_id|slot|grant_tick|recorded_expiry|effective_expiry|preempted_by|span

`effective_expiry` is the expiry after any revocation that took effect.
`preempted_by` is the canonical identifier of the stream whose revocation took
effect and moved the expiry, and the empty string when no revocation took
effect. `span` is the effective expiry minus the grant tick, floored at 0.

## `/app/out/cancel_timeline.jsonl`

JSON Lines, no header. One object per cancelled stream, ordered by `stream_id`
ascending. Keys appear in this order.

    stream_id, cancel_tick, origin, windows_after, windows_straddling

`windows_after` counts the stream's windows whose grant tick is at or after the
cancellation tick. `windows_straddling` counts those whose grant tick is before
the cancellation tick and whose effective expiry is after it.

## `/app/out/k_schedule.tsv`

Tab separated with a header. One row per stream, ordered by `stream_id`
ascending.

    stream_id	seed_k_recorded	seed_k_final	passes	converged	schedule

`schedule` is the policy K of each window of that stream in ascending sequence
order, rendered as decimal integers joined with a comma and no spaces.

## `/app/out/acceptance_ledger.csv`

Comma separated with a header. One row per window, ordered by `window_id`
ascending.

    window_id,k_policy,drafted,agreed_prefix,accepted,rejected,expired,reclaimed,voided

## `/app/out/lease_conflicts.tsv`

Tab separated with a header. One row per recorded revocation, ordered by
`window_id` ascending, then `challenger` ascending, then `revoke_tick`
ascending.

    window_id	slot	holder	holder_rank	challenger	challenger_rank	revoke_tick	disposition

`disposition` is `preempted` when the revocation took effect and `inverted`
when it did not.

## `/app/out/reclaim_ledger.csv`

Comma separated with a header. One row per cancelled stream, ordered by
`stream_id` ascending.

    stream_id,cancel_tick,windows_reclaimed,tokens_reclaimed,slots_released

`slots_released` counts the distinct slots held by the reclaimed windows of
that stream.

## `/app/out/malformed_repairs.jsonl`

JSON Lines, no header. Exactly six objects, one for each repair code, in code
order `R01` through `R06`. A code with no instances is still emitted and
carries zero in both counts. Keys appear in this order.

    repair_code, windows, tokens_affected

`windows` counts the windows the code applied to. `tokens_affected` sums, over
those same windows, the number of tokens each drafted under its policy K.

## `/app/out/window_disposition.csv`

Comma separated with a header. One row per window, ordered by `window_id`
ascending.

    window_id,stream_id,seq,terminal_band,k_policy,drafted,accepted,rejected,expired,reclaimed,voided,disposition

`disposition` names the terminal class holding the most of that window's
drafted tokens. Ties are broken in the order `accepted`, `rejected`, `expired`,
`reclaimed`, `voided`, so the earliest of the tied classes in that order wins.

## `/app/out/token_accounting.tsv`

Tab separated with a header. One row per stream, ordered by `stream_id`
ascending.

    stream_id	drafted	accepted	rejected	expired	reclaimed	voided	residual

`residual` is that stream's drafted count minus the sum of its five terminal
classes.

## `/app/out/stream_metrics.json`

One JSON object, no header. Keys are canonical stream identifiers in ascending
order. Each value is an object whose keys appear in this order.

    pooled_ratio, band, alpha_final, windows, passes, converged

`pooled_ratio` and `alpha_final` are ratios rendered as strings with four
decimal places. `alpha_final` is the moving average after the last window of
the settled pass. `windows` counts the stream's windows. `converged` is a JSON
boolean.

## `/app/out/tenant_cost.csv`

Comma separated with a header. One row for every tenant in the registry, in
registry order, including a tenant that owns no stream.

    tenant_id,gross_units,capped_units,cap,over_cap

## `/app/out/inversion_report.tsv`

Tab separated with a header. One row per recorded priority inversion, ordered
by `window_id` ascending, then `challenger` ascending, then `revoke_tick`
ascending.

    window_id	slot	holder	challenger	revoke_tick	tokens_preserved

`tokens_preserved` is the number of tokens the holding window ended with in the
accepted class, which is what the ignored revocation left in place.

## `/app/out/nonconvergence_report.jsonl`

JSON Lines, no header. One object per stream that did not converge, ordered by
`stream_id` ascending. Keys appear in this order.

    stream_id, passes, final_schedule, pooled_ratio

`final_schedule` is a JSON array of integers. `pooled_ratio` is a string with
four decimal places.

## `/app/out/slot_occupancy.tsv`

Tab separated with a header. One row for every slot in the registry, in
registry order, including a slot no window ever held.

    slot	windows	granted_ticks	effective_ticks	peak_concurrent

`granted_ticks` sums the recorded span of every window on that slot, each
floored at 0. `effective_ticks` sums the effective span. `peak_concurrent` is
the largest number of that slot's effective lease ranges covering any single
tick, counting a range as covering the ticks from its grant tick up to but not
including its effective expiry, and counting only ranges whose span is above 0.

## `/app/out/conservation_ledger.json`

One JSON object, no header. Keys appear in this order.

    drafted, accepted, rejected, expired, reclaimed, voided, residual

Every value is a whole number over the entire run.

## `/app/out/reconciliation.tsv`

Tab separated with a header. Exactly six rows, in this order: `drafted`, then
the five terminal classes in the order `accepted`, `rejected`, `expired`,
`reclaimed`, `voided`.

    class	from_windows	from_streams	delta

`from_windows` aggregates the per window ledger. `from_streams` aggregates the
per stream accounting. The two are derived independently and neither is copied
from the other. `delta` is `from_windows` minus `from_streams`.

## `/app/out/arbiter_driver.py`

The replay program itself, as a single Python source file that runs on the
standard library alone. Invoked as

    python3 /app/out/arbiter_driver.py --data <corpus directory> --out <output directory>

it reads the corpus from the given directory and writes every other artifact
listed here into the given output directory, and it exits with status 0. It
carries no answer values of its own: run against a different corpus directory
holding the same families of files, it produces that corpus's figures.

## `/app/out/run_manifest.json`

One JSON object, no header, with a single key `artifacts` whose value is an
array. The array holds one object per declared artifact except this manifest
itself, in the declared artifact order given at the top of the instruction, and
each object's keys appear in this order.

    path, sha256, bytes

`path` is the absolute artifact path. `sha256` is the lower case hexadecimal
SHA-256 digest of that file's bytes. `bytes` is its length in bytes.
