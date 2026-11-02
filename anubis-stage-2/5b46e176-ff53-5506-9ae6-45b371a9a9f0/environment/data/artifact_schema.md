# Artifact schema

This file fixes the key names, the row shapes and the two CSV headers of
every artifact a cleared epoch owes. It says nothing about the byte form of a
file: the one shipped example report is the authority on that, down to the
byte, and no prose anywhere describes it.

Every money figure is an integer count of micros. Every count is an integer.
Every list of identifiers is in ascending order unless this file says
otherwise. A boolean is a JSON boolean and never the integers 0 or 1.

## summary.json

```
epoch_id                 epoch_opens_at           epoch_closes_at
resolved_parameters      taps_total               taps_admitted
taps_priced              taps_withdrawn           taps_out_of_epoch
epoch_charge_micros      priced_distance_units    admitted_distance_units
suspended_gates          unvalidated_zones        stood_down_operators
operators_in_scope       zones_in_scope           cap_infeasible_zones
```

`resolved_parameters` is an object carrying exactly the seven property names,
which are also listed in the calibration material:

```
adjustment_order     levy_basis           grid_step_micros
midpoint_rule        void_reach           cap_release_order
fault_window_edge
```

`adjustment_order` holds the four adjustment names as a list in the recovered
order. `grid_step_micros` holds an integer. The other five hold one of their
candidate strings. Every value has to be one the calibration material admits.

## reconciliation.json

```
identities               residual_total
```

`identities` is a list of objects, each `identity`, `left`, `right`,
`residual`, where `residual` is `left - right`. `residual_total` is the sum
of every residual. The eleven identities, by name, are:

```
admitted_plus_out_of_epoch_equals_total
priced_plus_withdrawn_equals_admitted
zone_charges_sum_to_epoch_charge
operator_charges_sum_to_epoch_charge
ledger_running_total_closes_on_epoch_charge
priced_plus_withdrawn_distance_equals_admitted_distance
loans_granted_equal_cap_released
net_positions_sum_to_zero
residual_plus_cancelled_equals_gross
assurance_shares_sum_to_retained_distance
retained_margins_sum_to_pool
```

They appear in that order. Every residual is zero in a cleared epoch.

## tap_ledger.json

```
rows                     row_count                charge_micros
```

`rows` is one object per tap in canonical order, carrying:

```
tap_id                   canonical_token          identity_outcome
gate_id                  zone_id                  operator_id
home_operator_id         tapped_at                distance_units
rider_class              completion_class         op
governing_table_id       peak                     cross_operator
gross_before_adjustments_micros                   unit_fare_micros
disposition              withdrawal_reason        exception_id
running_charge_micros
```

`peak` and `cross_operator` are booleans. `withdrawal_reason` and
`exception_id` are the empty string where they do not apply, and
`governing_table_id` is the empty string for a tap no table governed.

## data_quality.json

```
taps_out_of_epoch                taps_without_governing_table
taps_with_retired_identity       taps_with_revoked_identity
identity_cycles_broken           duplicate_tap_ids
zero_distance_taps               decommissioned_gates
faults_open_at_close             exceptions_total
exceptions_upheld                exceptions_rejected
exceptions_on_withdrawn_taps
```

The first nine hold ascending lists of identifiers. The three counts hold
integers. `exceptions_on_withdrawn_taps` holds an ascending list of
exception identifiers.

## identity_register.json

```
outcomes                 resolutions
```

`outcomes` is one object per outcome present, in ascending outcome name,
carrying `outcome`, `tap_ids` and `count`. `resolutions` is one object per
admitted tap, in ascending `tap_id`, carrying `tap_id`, `token_ref`,
`canonical_token`, `outcome` and `chain`. `chain` is the walk in the order it
was walked, so it is not sorted.

## suspension_register.json

```
iterations               gates                    zones
operators
```

`gates` is one object per gate in ascending `gate_id`, carrying `gate_id`,
`zone_id`, `burden_bp`, `allowance_bp`, `suspended` and `reason`, with
`reason` the empty string for a gate that was not suspended. `zones` is one
object per zone in ascending `zone_id`, carrying `zone_id`,
`validated_gate_count`, `validation_floor` and `unvalidated`, where
`validated_gate_count` counts the zone's unsuspended gates. `operators` is
one object per operator in ascending `operator_id`, carrying `operator_id`
and `stood_down`.

## cap_relief.json

```
release_order            zones                    loans
loan_total_micros
```

`release_order` is the zone identifiers in the release order the capping
rulebook settled, so it is not sorted. `zones` is one object per zone in
ascending `zone_id`, carrying:

```
zone_id                  revenue_cap_micros       effective_cap_micros
priced_total_before_micros                        priced_total_after_micros
lent_micros              borrowed_micros          curtailed_tap_ids
residual_micros          cap_infeasible
```

`loans` is one object per loan in the order the loans were made, carrying
`from_zone`, `to_zone`, `operator_id` and `amount_micros`.

## operator_<operator_id>.json

```
partition_kind           partition_id             epoch_id
taps_priced              taps_withdrawn           charge_micros
priced_distance_units    zones_in_scope           gates_suspended
net_position_micros
```

`partition_kind` reads `operator`.

## zone_<zone_id>.json

```
partition_kind           partition_id             epoch_id
operator_id              taps_priced              taps_withdrawn
charge_micros            priced_distance_units    revenue_cap_micros
effective_cap_micros     gates_in_scope           cap_infeasible
```

`partition_kind` reads `zone`.

## netting_summary.json

```
epoch_id                 interchange_share_bp     obligation_total_micros
residual_total_micros    cancelled_cycle_count    cancelled_total_micros
net_position_total_micros                         netting_digest
funded_edge_count        deferred_edge_count      funded_total_micros
deferred_total_micros
```

`cancelled_total_micros` is the total amount removed from the graph, so a
cancellation of amount `a` over a cycle of `n` operators removes `a * n`.

## netting_obligations.json

```
edges                    total_micros
```

`edges` is one object per gross edge, sorted by `payer` then `payee`,
carrying `payer`, `payee`, `amount_micros` and `tap_count`.

## netting_residual.json

```
edges                    cycles                   total_micros
```

`edges` is one object per residual edge, sorted by `payer` then `payee`,
carrying `payer`, `payee` and `amount_micros`. `cycles` is one object per
cancellation in the order the cancellations happened, carrying `sequence`
and `amount_micros`, with `sequence` the operators of the cycle written from
its smallest operator.

## netting_positions.json

```
positions                net_total_micros
```

`positions` is one object per operator in the register, in ascending
`operator_id`, carrying `operator_id`, `gross_out_micros`, `gross_in_micros`,
`residual_out_micros`, `residual_in_micros` and `net_position_micros`.

## netting_schedule.json

```
rows                     funding_ceilings
```

`rows` is one object per residual edge in funding order, carrying `payer`,
`payee`, `amount_micros`, `state` and `payer_funded_running_micros`, with
`state` reading `funded` or `deferred`. `funding_ceilings` is one object per
operator in ascending `operator_id`, carrying `operator_id`,
`funding_ceiling_micros` and `funded_micros`.

## netting_cycles.csv

One row per cancellation in the order the cancellations happened. The header
is exactly:

```
cycle_index,sequence,amount_micros
```

`cycle_index` counts from one. `sequence` is the operators of the cycle
joined by a single greater than sign and nothing else, for example
`alderop>brambleop>cinderop`. A file with no cancellations carries the header
and no rows.

## assurance_summary.json

```
epoch_id                 assurance_sigma          assurance_modulus
min_sample               sample_size              median_margin
mad                      threshold                retained_count
held_back_count          pool_micros              assurance_digest
priced_distance_units    zero_distance_taps
```

## assurance_margins.json

```
rows                     row_count
```

`rows` is one object per tap in the sample, in ascending `tap_id`, carrying
`tap_id`, `rider_class`, `unit_fare_micros`, `floor_fare_micros`,
`distance_units`, `margin`, `deviation` and `held_back`.

## assurance_holdbacks.json

```
rows                     row_count
```

`rows` is one object per held back tap, in ascending `tap_id`, carrying
`tap_id`, `margin`, `median_margin`, `deviation` and `threshold`.

## assurance_order.json

```
tap_ids                  margins                  digest
```

`tap_ids` and `margins` are the retained taps in the digest order of the
assurance rulebook, so neither is sorted, and the two lists line up
position by position.

## assurance_apportionment.json

```
retained_distance_units  shares                   share_total_units
```

`shares` is one object per rider class present among the retained taps, in
ascending rider class, carrying `rider_class`, `retained_margin_micros` and
`share_units`.

## assurance_ladder.csv

One row per rider class present in the sample, in ascending rider class. The
header is exactly:

```
rider_class,retained_count,held_back_count,margin_total,share_units
```

A file with an empty sample carries the header and no rows.
