# Output contract

Every deliverable, its exact path, its exact shape and its exact order.

The paths below are written against `/app/out` because that is where the shipped
run publishes. They are the contract for whichever output directory the program
is handed, so a run over any extract into any output directory leaves that
directory holding these twenty-nine entries and nothing else. The first of them
is the program, which means the program writes a copy of itself into the output
directory on every run, and a directory holding twenty-eight is short one
deliverable.

## 1. Bytes

Every file is UTF-8, uses LF line endings, and ends with one newline.

A JSONL file carries one JSON object per line, serialized with sorted keys and
with no space after the separators. A JSON file is serialized with sorted keys
and an indent of two spaces. In a JSON or JSONL file every character outside
ASCII is written as a `\u` escape with four lowercase hexadecimal digits. A
delimited file carries a header line naming its fields in the order given
below, then one line per row, with no quoting and no padding. Every integer is
written in its plainest form with no sign, no thousands separator and no
decimal point.

Every order this contract gives is ascending unless it says descending. A text
field, an identifier, a name or a code is compared character by character by
code point, so a list ordered by reason code runs `AMBIGUOUS_IDENTITY` before
`FEED_RETIRED` and `EDGE_DANGLING` before `EDGE_SELF`, whatever order the
protocol or the glossary lists those codes in. An integer field such as
`row_index` or `period_index` is compared by its value.

## 2. The deliverables

```
/app/out/reconcile.py                 the program itself
/app/out/normalized_assertions.jsonl  every accepted commitment assertion
/app/out/rejects.csv                  every rejected row
/app/out/alias_resolution.jsonl       what each obligor surface resolved to
/app/out/actor_roster.csv             one line per principal
/app/out/project_lineage.csv          one line per resolved project code
/app/out/assertion_contests.csv       one line per commitment key
/app/out/commitment_ledger.jsonl      one object per admitted commitment
/app/out/state_resolution.csv         one line per admitted commitment
/app/out/live_edges.csv               every live edge
/app/out/dropped_edges.csv            every accepted edge that is not live
/app/out/blocking_closure.jsonl       one object per reachable pair
/app/out/blocked_commitments.csv      one line per blocked commitment
/app/out/actionable_queue.tsv         the ACTIONABLE commitments
/app/out/deferred_queue.psv           the DEFERRED commitments
/app/out/withdrawn_register.csv       the WITHDRAWN commitments
/app/out/unresolvable.jsonl           the UNRESOLVABLE commitments
/app/out/cadence_debt.csv             one line per cadence
/app/out/waiver_trace.jsonl           one object per waiver that had an effect
/app/out/attention_allocation.csv     one line per open commitment with effort
/app/out/month_load_index.csv         one line per principal and month carrying
                                       at least one open commitment with effort
/app/out/escalation_queue.csv         one line per escalated commitment
/app/out/actor_rollup.json            keyed by principal identifier
/app/out/project_rollup.json          keyed by project root
/app/out/provenance_index.jsonl       one object per admitted commitment
/app/out/audit_totals.csv             one line per named figure
/app/out/reconciliation.txt           the closing figures as plain lines
/app/out/validation_report.json       the five identities and their residuals
/app/out/run_manifest.json            the decisions this run took
```

## 3. Fields and order

`normalized_assertions.jsonl` carries `assertion_id`, `commitment_key`,
`obligor_actor`, `obligee_actor`, `obligee_status`, `project_code`,
`project_root`, `due_at`, `commitment_day`, `effort_minutes`, `effort_origin`,
`cadence_ref`, `observed_at` and `source_class`, ordered by `assertion_id`.
`obligee_status` is `RESOLVED`, `AMBIGUOUS` or `UNKNOWN`. `effort_origin` is
`STATED`, `DEFAULTED` or `DECLARED_ZERO`. `obligee_actor` is the empty string
when `obligee_status` is not `RESOLVED`, and `commitment_ledger.jsonl` carries
the `obligee_actor` of its winning assertion.

`rejects.csv` carries `feed_file`, `row_index`, `record_kind`, `record_id`,
`commitment_key` and `reason_code`, ordered by reason code, then feed file, then
row index, then record identifier. `row_index` counts records inside that file
from zero. `record_kind` is `commitment`, `state` or `edge`. For an edge row
`commitment_key` is its `dependent_key`.

`alias_resolution.jsonl` carries `surface_folded`, `distinct_actors`,
`assertion_count` and `max_hops`, one object per distinct folded obligor surface
appearing on an accepted commitment assertion, ordered by `surface_folded`.
`distinct_actors` is the ascending list of every principal that surface resolved
to across the accepted assertions.

`actor_roster.csv` carries `actor_id`, `canonical_handle`, `commitment_count`,
`open_effort_minutes`, `waivers_granted` and `waivers_lapsed`, ordered by
`actor_id`. `waivers_granted` and `waivers_lapsed` count the waivers of that
principal's cadences that were granted and lapsed under its allowance.

`project_lineage.csv` carries `project_code`, `project_root`, `assertion_count`
and `allocated_minutes`, ordered by `project_code`. `allocated_minutes` sums the
`allocated_minutes` of the ledger commitments carrying that project code.

`assertion_contests.csv` carries `commitment_key`, `winning_assertion`,
`winning_class`, `contender_count` and `distinct_classes`, ordered by
`commitment_key`.

`commitment_ledger.jsonl` carries `commitment_key`, `obligor_actor`,
`obligee_actor`, `project_code`, `project_root`, `commitment_day`, `due_at`,
`effort_minutes`, `effort_origin`, `resolved_state`, `commitment_class`,
`cadence_ref`, `source_class`, `winning_assertion` and `allocated_minutes`, in
the canonical order of protocol section 11.

`state_resolution.csv` carries `commitment_key`, `resolved_state`,
`assertions_seen`, `assertions_applied` and `governing_class`, ordered by
`commitment_key`. `assertions_seen` counts the accepted state rows naming that
commitment and `assertions_applied` counts those the walk applied.

`live_edges.csv` carries `edge_id`, `dependent_key`, `blocker_key`,
`asserted_at`, `dependent_actor`, `blocker_actor` and `dependent_blocked`,
ordered by dependent key, then blocker key, then edge identifier.
`dependent_blocked` is `yes` when the dependent has a line in
`blocked_commitments.csv` and `no` otherwise.

`dropped_edges.csv` carries `edge_id`, `dependent_key`, `blocker_key`,
`asserted_at` and `drop_reason`, ordered by drop reason then edge identifier.

`blocking_closure.jsonl` holds one object for each blocked commitment and each
commitment in its closure, and carries `dependent_key`, `blocker_key`,
`hop_distance`, `blocker_state` and `terminal`, ordered by dependent key then
blocker key. `terminal` is the string `yes` or the string `no`.

`blocked_commitments.csv` carries `commitment_key`, `reachable_blockers`,
`frontier_count`, `chain_depth`, `frontier_head` and `allocated_minutes`,
ordered by `commitment_key`.

`actionable_queue.tsv` and `deferred_queue.psv` both carry `commitment_key`,
`obligor_actor`, `commitment_day`, `effort_minutes`, `project_root` and
`allocated_minutes`, in the canonical order of protocol section 11.
Wherever a deliverable carries `allocated_minutes` for one commitment, it is
that commitment's share of its envelope, and zero when the envelope gave it
none.

`withdrawn_register.csv` carries `commitment_key`, `obligor_actor`,
`commitment_day`, `effort_minutes` and `source_class`, in the canonical order.

`unresolvable.jsonl` carries `commitment_key`, `reason_code`, `obligor_actor`
and `commitment_day`, ordered by reason code then commitment key.

`cadence_debt.csv` carries `cadence_id`, `period_days`, `periods_elapsed`,
`periods_discharged`, `periods_waived`, `debt` and `max_streak`, ordered by
`cadence_id`.

`waiver_trace.jsonl` carries `cadence_id`, `period_index`, `effect` and
`period_start`, ordered by cadence then period index.

`attention_allocation.csv` carries `year_month`, `obligor_actor`,
`commitment_key`, `demand_minutes` and `allocated_minutes`, ordered by month,
then principal, then commitment key.

`month_load_index.csv` carries `year_month`, `obligor_actor`, `budget_source`,
`budget_minutes`, `reserve_minutes`, `demand_minutes`, `allocated_minutes` and
`open_count`,
one line for each principal and settlement month carrying at least one open
commitment with effort greater than zero, ordered by month then principal.
`budget_source` is `OVERRIDE`, `REGISTERED` or `ABSENT`, `budget_minutes` is
the envelope, `reserve_minutes` the reserve of protocol section 9, and
`open_count` is
the number of open commitments the envelope was distributed across, counted
before any share was reduced to zero.

`escalation_queue.csv` carries `commitment_key`, `obligor_actor`,
`commitment_class`, `effort_minutes`, `allocated_minutes`,
`shortfall_minutes`, `principal_debt`, `chain_depth` and `trigger`, ordered by
descending shortfall and then by ascending commitment key. A commitment that is
blocked and reaches no closure entry carries a chain depth of zero.

`actor_rollup.json` is one object keyed by principal identifier. Each value
carries the six class names as counts, `commitment_count`,
`open_effort_minutes` and `allocated_minutes`. `project_rollup.json` is the same
shape keyed by project root.

`provenance_index.jsonl` carries `commitment_key`, `winning_assertion`,
`contributing_assertions`, `source_files` and `state_assertions`, ordered by
commitment key, with each list in ascending order. `contributing_assertions`
holds every accepted assertion naming that commitment. `source_files` holds the
feed files carrying those contributing assertions and no other file.
`state_assertions` holds every state row naming that commitment that passed
`MALFORMED_ROW`, `FEED_RETIRED`, `OUT_OF_WINDOW` and `UNKNOWN_COMMITMENT`,
whether the walk applied it or refused it as `ILLEGAL_TRANSITION`.

`audit_totals.csv` carries `metric` and `value`, in the order the figures are
listed in section 4.

`reconciliation.txt` carries one figure per line as a name, a space, and the
value, beginning with the line `CALDERMOOR COMMITMENT CLOSURE`, then the same
figures in the same order as `audit_totals.csv` restricted to the ones section 4
marks with an asterisk, then one line per identity as `identity_` followed by
the identity name, a space, and its residual.

`validation_report.json` carries `identities`, an object mapping each identity
name to its residual, `identities_checked`, the ascending list of those names,
and `all_residuals_zero`, a boolean.

`run_manifest.json` carries `day_boundary_offset_minutes`,
`effort_floor_minutes`, `effort_ceiling_minutes`, `allocation_floor_minutes`,
`window_start`, `window_end`, `reason_codes`, `commitment_classes`,
`retired_feeds`, `split_surfaces`, `multi_hop_assertions`,
`order_tiebreaks_applied`, `edges_dropped_out_of_scope`, `waivers_suppressing`,
`waivers_inert`, `waivers_lapsed`, `allocations_starved` and
`illegal_transitions`.
`split_surfaces` is the number of folded obligor surfaces that resolved to more
than one principal. `multi_hop_assertions` is the number of accepted assertions
whose obligor resolved through two or more alias assertions.
`order_tiebreaks_applied` is the number of adjacent pairs in the ledger sharing
a commitment day and a principal whose order the effort comparison decided.
`reason_codes` is the ascending list of the nine reason codes of protocol
section 6, `commitment_classes` the ascending list of the six class names, and
`retired_feeds` the ascending list of the feed files whose highest revision in
`feed_manifest.csv` carries a non-empty `retired_at`.
`allocations_starved` is the number of commitments whose share in the first
distribution of an attention envelope fell below fifteen minutes, so that the
envelope rule gave them zero. `edges_dropped_out_of_scope` is the number of
dropped edges carrying `EDGE_OUT_OF_SCOPE`, `waivers_suppressing`,
`waivers_inert` and `waivers_lapsed` the number of `waiver_trace.jsonl` objects
carrying `SUPPRESSED`, `INERT` and `LAPSED`, and `illegal_transitions` the
number of rejected rows carrying `ILLEGAL_TRANSITION`.

## 4. The audit figures

```
* rows_ingested
* rows_rejected
  rows_accepted
* commitments_admitted
* class_actionable, class_blocked, class_deferred, class_settled,
  class_unresolvable, class_withdrawn
  reject_ambiguous_identity, reject_feed_retired, reject_illegal_transition,
  reject_malformed_row, reject_nonpositive_effort, reject_out_of_window,
  reject_unknown_commitment, reject_unknown_principal, reject_unknown_project
* live_edges
* dropped_edges
* closure_pairs
* blocked_commitments
* open_effort_minutes
* allocated_minutes
* escalated_commitments
* cadence_debt_total
```

`rows_ingested` counts every record read from a commitment, state or edge feed.
`closure_pairs` counts the objects in `blocking_closure.jsonl` and
`blocked_commitments` counts the lines in `blocked_commitments.csv`.

## 5. Negative space

The output directory holds the twenty-nine deliverables and nothing else, and
that holds for `/app/out` and for every other output directory the program is
given. Every file under the extract directory is left byte identical to the way
it was found. A run that cannot finish leaves no partial file behind.
