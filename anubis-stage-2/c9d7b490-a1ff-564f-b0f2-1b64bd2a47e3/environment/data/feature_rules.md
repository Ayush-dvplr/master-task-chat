# Feature rules

Every characteristic of an observation is computed for its as of date from
the records known at its knowledge instant. "The obligor" is the obligor of
the lease at the snapshot (`identity_rules.md`).

## Characteristics

`dpd_now` is the days past due of the lease on the as of date.
`max_dpd_12m` is the largest days past due on any of the 365 days ending on
the as of date, and `recent_worst` the largest on any of the 90 days ending on
it. All three use the lease's schedule and payments as known at the instant
(`schedule_rules.md`, `cash_rules.md`).

`months_on_book` is the number of whole months from `start_date` to the as of
date: the difference in months, less one when the day of the month of the as
of date is earlier than that of `start_date`.

`active_leases` counts the leases, this one included, that are `active` on the
as of date as known at the instant and whose obligor reference names an
obligor known at the instant with the same surviving obligor on the as of
date.

`utilisation` is the exposure of the obligor in thousandths of its credit
limit, rounded down. The exposure is the sum, over the leases counted by
`active_leases`, of the instalment amount times the number of that lease's
instalments due after the as of date on its schedule as known at the instant.
The credit limit is the `credit_limits.csv` row of the obligor known at the
instant with the latest `effective_from` on or before the as of date (ties to
the later `recorded_at`, then the larger `limit_id`), ignoring rows whose
`limit_k` is blank, which record a limit under review and say nothing. With
no such row the characteristic takes its `missing` bin; with a limit of 0 it
takes its `zero_limit` bin.

`bureau` is a score on the KR scale. Its candidates are the pulls of either
vendor for the obligor's tax id with a pull date on or before the as of date
and at most `max_age_days` days before it, known at the instant, and not
disputed by a `bureau_disputes.json` entry known at the instant. The pull with
the latest pull date wins; a tie goes to the vendor listed first for the
observation segment in `[precedence]`, then to the later recorded time, then
to the larger pull id. A KR pull gives its `score` when `status` is `OK`, the
`no_hit` bin when `NOHIT` and the `thin` bin when `THIN`. An ND pull gives the
`no_hit` bin when `result` is `NOHIT`, the `thin` bin when `result` is `HIT`
with a blank `score`, and otherwise the KR equivalent of its score: with the
ND score written as `t` tenths, `300 + t * to_kr_numerator // to_kr_denominator`.
A written ND score of `0.0` is a real score. With no candidate the
characteristic takes its `missing` bin.

`sector_class` is the risk class `sector_reference.json` gives the obligor's
sector code on the as of date, or the `missing` bin when it has none.

## Lineage and quarantine

`feature_lineage.yaml` lists, for every node and characteristic, the nodes it
is computed from. A confirmed incident of `data_incidents.json` quarantines
its `source` for every observation whose region is in its `regions` and whose
knowledge instant is at or after `from_utc` and before `to_utc`, whenever the
incident was declared. Incidents with any other status change nothing. A
characteristic computed, directly or through other nodes, from a quarantined
source takes its `quarantined` bin whatever its value.
