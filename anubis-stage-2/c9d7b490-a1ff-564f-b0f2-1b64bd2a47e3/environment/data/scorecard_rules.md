# Scorecard rules

## Versions

`scorecard_registry.json` lists the scorecard versions. Only versions with
`status` `released` are ever used. The version of a snapshot is the released
version with the latest `effective_from` on or before the snapshot date.

## Points

A version file gives `base_points` and `cutoff` per observation segment and a
list of `characteristics`. Every characteristic has a `name`, a `special` map
of special bins to points, and either `bins` (each with `label`, `lo`, `hi`
and `points`) or, for `sector_class`, `categories` (risk class to points). A
value falls in the bin with `lo` at or below it and `hi` above it; a `hi` of
`null` has no upper bound. A characteristic that takes a special bin
(`missing`, `zero_limit`, `no_hit`, `thin` or `quarantined`) is labelled with
that name. A `sector_class` value is labelled with its risk class.

The score of an observation is the base points of its observation segment
plus the points of the bin of every characteristic the version lists. A
characteristic the version does not list is neither computed into the score
nor reported. An observation is approved when its score is at or above the
cutoff of its observation segment.

## Exclusions

`exclusion_policy.yaml` lists the exclusion reasons in the order they are
checked; an observation carries the first that holds, or none. An observation
is excluded with reason `prior_charge_off` when another lease with the same
obligor at the snapshot (counted as in `active_leases`, whatever its state)
is `charged_off` on the as of date as known at the knowledge instant. It is
excluded with reason `holiday_active` when the as of date falls in the
lease's deferral span as known at the instant (`schedule_rules.md`). These
are the only two reasons. An excluded observation is still scored, labelled
and listed; it is left out of every metric population (`metrics_rules.md`).
