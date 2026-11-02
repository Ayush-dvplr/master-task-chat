# Settlement report schema

This document fixes the names and the value types of every field the settlement
reports carry. It fixes no value: every number and every identifier below is yours
to derive from the corpus you are given. Where a field's meaning depends on a rule,
the rule lives in the policy document named beside it.

Every monetary field is a whole number of micro units. Every count is a whole
number. Region rollups and service segment rollups share one shape, given by the
worked probe rollup that ships with the corpus.

## summary.json

One object with exactly these twelve fields.

- order_rows: the count of genuine work order records in the field population, once
  filler has been discarded (packet_encoding.md, count bias).
- decoded_rows: the count of records decoded from the field population before filler
  is discarded.
- orders_scored: the count of field orders that reach admission, meaning those
  neither rejected nor deferred by the identity and revision policies.
- orders_placed: the count of field orders that end up resting on a lane.
- orders_deferred: the count of field orders that settle nowhere but are not
  rejected. This is one figure covering both deferral routes together: work whose
  governing client is not yet active (identity_policy.md) and work held back by a
  client admission ceiling (capacity_policy.md).
- orders_rejected: the count of field orders rejected outright, meaning work on or
  after its governing client's retirement day (identity_policy.md) and work whose
  submission day no revision governs (revision_policy.md).
- billable_slots_total: the sum of billable slots over the placed orders.
- charge_micros_total: the sum of charges over the placed orders (cost_policy.md).
- rebate_micros_total: the sum of rebates over the placed orders.
- capped_micros_total: the sum of capped value over the placed orders.
- net_micros_total: the sum of net value over the placed orders.
- lanes_used: the count of distinct lanes carrying at least one placed order.

## data_quality.json

One object with exactly these ten fields.

- order_rows: as in summary.json.
- decoded_rows: as in summary.json.
- rejected_orders: an array of the rejected order identifiers, ascending.
- deferred_orders: an array of the deferred order identifiers, ascending, covering
  both deferral routes exactly as orders_deferred does.
- region_net_micros: an object keyed by the four region names as they appear in your
  region rollup file names, each holding that region's net value.
- segment_net_micros: an object keyed by the two service class names as they appear
  in your segment rollup file names, each holding that segment's net value.
- conservation_residual_micros: the net value of the schedule less the sum of the
  four region net values (global_invariants.md, conservation).
- segment_residual_micros: the net value of the schedule less the sum of the two
  segment net values.
- calibration_net_micros: the net value of the calibration population, settled under
  the same rules as the field population. It appears in no rollup.
- invariants: an object holding exactly these four booleans, one verdict per
  invariant named in global_invariants.md: region_partition_closed,
  segment_partition_closed, order_identity_unique, capacity_respected.

## Region and segment rollups

Each rollup carries order_count, orders, totals, and one discriminator field naming
what the rollup covers. A region rollup's discriminator field is called region. A
segment rollup's discriminator field is called service_class, and its value is the
service class as the client directory spells it. Everything else matches the worked
probe rollup: the per-order fields and the totals fields are the same in both kinds.
The orders array runs in ascending order of order identifier.

## policy_audit.json

One object with exactly these six fields. This file records the derivation, not the
settlement.

- candidate_space: an array with one entry per withheld constant, in the order the
  constants resolve. Each entry carries parameter (the constant's name as listed
  under resolved_parameters), control (the published control figure that resolves
  it, spelled as calibration_slice.md spells it), domain_size (the count of
  candidate values in that constant's declared range), resolved (the value you
  settled on), rejected (the count of candidate values you ruled out) and verdicts
  (an array holding one entry per candidate value in that constant's declared
  range, each carrying value, the candidate you tried, and verdict, the string
  "accepted" or "rejected"). The control that resolves a constant is the control
  that eliminated every candidate the entry rejects, so the entry names it once.
- resolved_parameters: an object holding your settled value for each of the twelve
  withheld constants, keyed exactly: rotate_step, shadow_bias, count_bias,
  island_offset, permute_rounds, stream_label, chain_seed, delta_span,
  drift_modulus, alias_rotor, window_span, quant_mode. The stream label and the
  quantisation mode are strings; the other ten are whole numbers.
- calibration_comparison: an array with one entry per published control figure, each
  carrying control (its name), published (the figure as published) and reproduced
  (the figure your settled constants reproduce).
- fixpoint: an object carrying passes (the count of admission passes, counted as
  capacity_policy.md counts them), congestion_index and congestion_tier, each an
  object keyed by the four site names as the site directory spells them.
- assignment_search: an object carrying sites_searched, feasible_leaves (a count
  describing the extent of your own search), displaced_orders (the count of admitted
  orders that end up on relief capacity) and site_cost_micros, an object keyed by
  site name holding each site's settled lane cost.
- candidates_examined and candidates_rejected: the totals across all twelve
  constants of the candidate values you examined and of those you ruled out.
