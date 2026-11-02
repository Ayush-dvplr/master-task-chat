# Artifact schema

This file fixes the shape of a settled window. It names every key each artifact
carries and says what each key holds. It carries no settled value, and it says
nothing about how any value is derived. The rulebooks, the invariant statement
and the calibration slice own that side; this document owns names and nesting
only.

Counts are integers. Every key whose name ends in `_micros` holds an integer
number of micros. Every key whose name ends in `_bp` holds an integer number of
basis points. No settled figure is ever a fractional number and no settled figure
is ever written as text.

## Serialization

`example_domain_report.json` in this working set is a complete artifact the
platform produced for the calibration window. It is the authority on the byte
level form every artifact takes: how objects are laid out, how keys are arranged,
how lists are arranged, and how the file ends. Match it exactly. Nothing about
that form is described in prose anywhere in this reference set, on purpose, and
where prose here and the example ever disagree the example is right.

## Reason vocabulary

Withdrawal reason counts are objects keyed by these tokens.

| token | meaning |
| --- | --- |
| `withdrawn_provisional_domain` | the record landed on a feed of a provisional domain |
| `withdrawn_retired_producer` | the canonical producer was retired as at the record emission instant |
| `withdrawn_unknown_producer` | the reference did not resolve to a recognised producer |
| `withdrawn_cyclic_identity` | the reference sat in a chain of identity events that never settles |
| `withdrawn_no_governing_card` | no rate card was live at the record emission instant |
| `withdrawn_by_tombstone` | a tombstone in this window reached the canonical producer |
| `withdrawn_by_reserve_designation` | the record sat on a feed the window designated as a reserve slot |
| `withdrawn_by_quarantine_cascade` | the canonical producer was tainted in this domain by a quarantined feed |
| `withdrawn_by_curtailment` | the record was dropped to bring the domain inside its curated cap |

One further token, `quarantined_defect_rate`, marks a ledger row on a
quarantined feed. It is a disposition of its own and never appears in a
withdrawal reason count.

Which records earn which token is decided by the rulebooks, not here. A token
that applies to no record in a given window does not appear in the count object
at all.

## Dispositions

Every ledger row carries exactly one of `curated`, `withdrawn` or `quarantined`.

## `summary.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `window_open` | the instant the window opened |
| `window_close` | the instant the window closed |
| `landing_record_count` | how many landing records the register carried |
| `in_window_record_count` | how many records took part in the settlement |
| `curated_record_count` | how many records finished curated |
| `withdrawn_record_count` | how many records finished withdrawn |
| `quarantined_record_count` | how many records finished quarantined |
| `curated_payload_units` | the payload units of the curated records |
| `settled_charge_micros` | the charge the window settled |
| `withdrawal_reason_counts` | an object from reason token to count |
| `designated_reserve_feed_ids` | the designated feeds of the whole window |
| `quarantined_feed_ids` | the quarantined feeds of the whole window |
| `admitted_domain_count` | how many domains are settled |
| `admitted_channel_count` | how many channels are settled |
| `resolved_parameters` | an object carrying `adjustment_precedence`, `backpressure_coefficient_micros`, `quantisation_step_micros`, `rounding_mode` and `tombstone_reading` |

## `reconciliation.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `identity` | an object with `in_window_record_count`, `curated_record_count`, `withdrawn_record_count`, `quarantined_record_count` and `residual_record_count` |
| `charge` | an object with `window_settled_charge_micros`, `domain_charge_total_micros`, `channel_charge_total_micros` and `residual_micros` |
| `units` | an object with `curated_payload_units`, `domain_curated_units_total` and `residual_units` |
| `per_domain` | an array, one row per settled domain |

A `per_domain` row carries `domain_id`, `curated_record_count`,
`withdrawn_record_count`, `quarantined_record_count`, `settled_charge_micros`
and `residual_micros`.

## `ingest_audit.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `ledger` | an array, one row per record that took part in the settlement |
| `identity_resolutions` | an array, one row for each way a producer reference seen in the window resolved |
| `tombstone_entity_ids` | the canonical entities a tombstone reached in this window |
| `override_record_ids` | the curated records that carried an upheld agreed rate |

A ledger row carries `record_id`, `sequence`, `emitted_at`, `feed_id`,
`domain_id`, `canonical_producer_id`, `governing_card_id`, `payload_units`,
`disposition`, `reason`, `unit_charge_micros`, `record_charge_micros` and
`cumulative_charge_micros`. A row with nothing to say for `reason` or
`governing_card_id` carries an empty text value rather than omitting the key.

An identity resolution row carries `producer_ref`, `canonical_producer_id`,
`status` and `record_count`. The status is one of `resolved`, `retired`,
`unknown` or `cyclic`. A reference that resolved the same way for every record
that carried it has a single row. A reference that resolved to different
canonical producers or to different outcomes at different instants, which the
identity rulebook allows, has one row for each distinct outcome it took, and
`record_count` on each row counts the records that carried the reference under
that outcome. A reference that did not resolve, meaning an unknown or a cyclic
outcome, carries an empty canonical identifier; a resolved or retired outcome
carries the canonical producer it reached.

## `data_quality.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `out_of_window_record_count` | records outside the window boundary |
| `suspended_feed_record_count` | records on suspended feeds |
| `provisional_domain_record_count` | records on feeds of provisional domains |
| `retired_producer_record_count` | records whose canonical producer was retired |
| `unknown_producer_record_count` | records whose reference did not resolve |
| `cyclic_identity_record_count` | records sitting in a chain that never settles |
| `records_without_governing_card` | records no rate card was live for |
| `feeds_over_nominal_throughput` | the feeds whose curated load exceeded their nominal throughput |
| `domains_at_quarantine_floor` | the settled domains at or below their quarantine floor |
| `upheld_exception_count` | how many filed exceptions were upheld |
| `dismissed_exception_count` | how many filed exceptions were dismissed |

## `slot_designation.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `window_nominal_throughput` | the nominal throughput of the window |
| `designated_nominal_throughput` | the nominal throughput the window designated |
| `designated_band_low_bp` | the lowest designated share the policy register accepts |
| `designated_band_high_bp` | the highest designated share the policy register accepts |
| `channels` | an array, one row per channel that took part |

A channel row carries `channel_id`, `slot_ceiling`, `candidate_feed_count`,
`designated_feed_ids` and `designated_nominal_throughput`.

## Domain reports

One per settled domain. The keys are `domain_id`, `channel_id`, `curated_cap`,
`quarantine_floor`, `curated_record_count`, `curated_payload_units`,
`settled_charge_micros`, `curated_record_ids`, `curtailed_record_ids`,
`feed_ids`, `producer_ids`, `quarantined_feed_ids` and
`withdrawal_reason_counts`. `curtailed_record_ids` names only the records
dropped at the cap, not everything the domain withdrew. `producer_ids` names the
canonical producers of the curated records. `example_domain_report.json` is a
worked instance of exactly this artifact and settles any question this table
leaves open.

## Channel reports

One per settled channel. A channel report is **not** the same shape as a domain
report and must not be built from the example. Its keys are `channel_id`,
`slot_ceiling`, `curated_record_count`, `curated_payload_units`,
`settled_charge_micros`, `designated_reserve_feed_ids`, `member_domain_ids`,
`admitted_domain_ids` and `domain_charge_micros`.

`member_domain_ids` is the full membership of the channel from the domain
register and is not narrowed by anything the settlement did.
`admitted_domain_ids` is narrowed, and `domain_charge_micros` is an object keyed
by the settled member domains only. Reporting the same list for both is the most
common way this artifact goes wrong.

## Egress artifacts

Six artifacts carry the egress layer. This section fixes their names on the same
terms as every section above: `rulebook_egress.md` owns how each figure is
derived, and this table owns what it is called once it is written out. An egress
account carrying the right figures under other names does not satisfy the
schema. Every number named here is an integer.

### `egress_summary.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `egress_pool_micros` | the retained egress pool in micros |
| `egress_digest` | the digest taken over the egress order |
| `retained_record_count` | how many curated records the burst rule retained |
| `burst_record_count` | how many curated records the burst rule held out |
| `payload_unit_octets` | the octets per payload unit the policy register publishes |

### `egress_rates.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `rates` | an array, one row per curated record, ordered by `record_id` ascending |

A rate row carries `record_id`, `feed_id`, `domain_id`, `payload_units`,
`record_charge_micros` and `egress_rate`. The first five are carried forward
from the settled window unchanged; `egress_rate` is the only derived figure.

### `egress_bursts.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `bursts` | an array, one row per curated record the burst rule held out, ordered by `record_id` ascending |

A burst row carries `record_id`, `feed_id`, `domain_id`, `egress_rate`,
`group_median`, `group_mad` and `threshold`. The last three are the figures the
burst rule decided that record against, recorded so the decision can be
rechecked without recomputing the group.

### `egress_order.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `order` | an array in egress order, one row per retained record |

An order row carries `position`, `record_id` and `egress_rate`. `position` is
one based and counts upward with no gap. Records the burst rule held out appear
nowhere in this array.

### `egress_apportionment.json`

| key | holds |
| --- | --- |
| `window_id` | the identifier of the settled window |
| `curated_payload_units` | the payload units the shares sum to |
| `shares` | an object keyed by group key, each value that group's whole number of payload units |

A group key is the feed scoped by its domain, written `DOMAIN:FEED`, exactly as
`egress_ladder.csv` writes it.

### `egress_ladder.csv`

A CSV carrying this header line exactly, then one row per group key that
retained at least one record, in ascending group key order, ending in a single
line feed with no trailing blank line:

    group_key,retained_count,group_rate_total,payload_share

`retained_count` is how many records that group retained, `group_rate_total` is
the sum of their egress rates, and `payload_share` is the share the group took
in `egress_apportionment.json`.
