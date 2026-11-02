# Metrics definitions

`audit_count` counts the requests this cycle adjudicated, which is every request
inside the horizon after the duplicate rule, whatever decision each reached.

`admitted_total`, `deferred_total` and `rejected_total` count requests by the
decision their reason code carries.

`withdrawn_excluded` counts the requests whose reported code is the withdrawal
code.

`admission_rate` is `admitted_total` divided by `audit_count` less
`withdrawn_excluded`. Compute it once from the unrounded integers and round half
up to four decimal places. The rate is `0.0` when the divisor is zero.

`admitted_by_channel` counts admitted requests per channel and names all four
channels, including those with none.

`coverage_share_pct` gives each channel its share of `admitted_total` as a
percentage to two decimal places. Shares are apportioned by largest remainder so
that the four values sum to exactly `100.0`. When `admitted_total` is zero every
share is `0.0`.

`escalated_total` counts requests reported under the escalated reason code.

`repeat_deferral_count` counts distinct unit keys whose decision this cycle is
`deferred` and which also hold a row in `prior_cycle_decisions.csv` for the
immediately preceding cycle, the same target channel and decision `deferred`.
Rows from earlier cycles do not count.

`dependency_digest` is the first sixteen lower case hexadecimal characters of the
SHA-256 of the admitted requests in admission order, where each request
contributes `unit_key|revision|target_channel|pool|draw_index` and the
contributions are joined with single newlines and nothing is appended after the
last one. `pool` is the name of the pool the request drew its slot from, written
`tier1`, `tier2` or `general`. `draw_index` is the position of that draw inside
that pool for that channel, counted from one in the order capacity was offered,
and a draw that was later lost to closure still consumed its index.

`closure_passes` counts the passes of the closure test that evicted at least one
holder. The pass that closes the matter by evicting nobody is not one of them, and
the figure is zero when the first pass evicts nobody.

`rollback_holds` counts the tier two slots held for rollback cover across all four
channels, so a pair in a channel whose hold is larger than one contributes that
larger figure.

`inputs_seen` counts the files in the evidence directory.

An `admitted_digest` is built the same way as `dependency_digest` for the admitted
set of whichever scenario reports it.

## Normative parameters

```
rate_places: 4
share_places: 2
digest_chars: 16
digest_joiner: newline
digest_fields: unit_key,revision,target_channel,pool,draw_index
pool_names: tier1,tier2,general
```
