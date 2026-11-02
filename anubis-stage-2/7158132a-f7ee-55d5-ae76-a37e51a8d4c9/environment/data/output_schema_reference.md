# output schema reference

Column order is binding. Every column is an integer unless the
description says otherwise.

## canonical_contact_ledger.csv

columns: contact_id, period_id, station_id, antenna_uid, mission_id, contract_id, eligible_seconds, raw_capacity_kib, usable_capacity_kib, effective_class, protected, late_cancel, allocation_state, demand_kib, allocated_kib, accepted_kib

One row per admitted pass per period, ordered by contact_id then period_id. allocation_state is won or displaced. A displaced row carries zero in demand_kib, allocated_kib and accepted_kib and an empty contract_id.

## admitted_contact_ledger.csv

columns: contact_id, period_id, station_id, antenna_uid, mission_id, presentation_id, scheduled_start_s, scheduled_end_s, commit_boundary_s, event_status, operator_code, protected, late_cancel, eligible_seconds

Same rows as the canonical ledger, ordered the same way, carrying the admission evidence instead of the settlement figures.

## rejected_contact_ledger.psv

columns: contact_id, station_id, aperture_label, presentation_id, scheduled_start_s, scheduled_end_s, predicate_index, reject_code, reject_reason

One row per rejected pass, ordered by contact_id. Not per period.

## normalized_contact_intervals.tsv

columns: contact_id, period_id, antenna_uid, segment_start_s, segment_end_s, segment_seconds

One row per eligible piece, ordered by contact_id then period_id then segment_start_s.

## antenna_capacity_ledger.csv

columns: contact_id, period_id, antenna_uid, eligible_seconds, rate_piece_count, raw_capacity_kib, capacity_cap_kib, usable_capacity_kib

One row per canonical row, ordered by contact_id then period_id.

## capacity_cap_exceptions.psv

columns: contact_id, period_id, antenna_uid, raw_capacity_kib, capacity_cap_kib, clipped_kib

Only rows where raw capacity strictly exceeded the cap.

## contention_groups.jsonl

columns: antenna_uid, period_id, group_seq, member_count, member_ids, eligible_seconds_total

member_ids is the contact identifiers of the component sorted ascending and joined by commas. Ordered by antenna_uid then period_id then group_seq.

## winning_resource_assignments.csv

columns: contact_id, period_id, antenna_uid, mission_id, effective_class, effective_rank, protected, commit_boundary_s, remaining_obligation_kib, eligible_seconds, usable_capacity_kib

The accepted rows only, ordered by contact_id then period_id.

## displaced_contact_ledger.psv

columns: contact_id, period_id, antenna_uid, mission_id, displaced_by, displaced_seconds, usable_capacity_kib

The displaced rows only, ordered by contact_id then period_id.

## mission_entitlement_state.csv

columns: contract_id, period_id, carry_source_kib, carry_cap_kib, carry_in_kib, carry_forfeit_kib, entitlement_kib, available_allowance_kib, consumed_kib, unconsumed_kib, contract_expired

One row per contract per period with settled terms, ordered by contract_id then period_id.

## carry_forward_ledger.csv

columns: contract_id, period_id, carry_in_kib, carry_forfeit_kib, carry_out_kib, carry_forward_enabled

The same rows, carrying the state that crosses into the next period.

## rationing_pass_trace.jsonl

columns: antenna_uid, period_id, pass_seq, active_count, share_kib, allocated_kib, budget_kib, demand_total_kib

One row per pass of the ration, for the aperture periods that ran it, ordered by antenna_uid then period_id then pass_seq.

## delivered_volume_ledger.csv

columns: contact_id, period_id, mission_id, contract_id, antenna_uid, demand_kib, allocated_kib, accepted_kib, from_carry_kib, from_new_kib

The accepted rows only, ordered by contact_id then period_id.

## deferred_volume_ledger.csv

columns: contact_id, period_id, mission_id, demand_kib, accepted_kib, deferred_kib, late_cancel

The accepted rows only, ordered by contact_id then period_id.

## unused_capacity_ledger.tsv

columns: contact_id, period_id, antenna_uid, usable_capacity_kib, accepted_kib, unused_capacity_kib

The accepted rows only, ordered by contact_id then period_id.

## station_utilisation_ledger.csv

columns: station_id, period_id, occupied_seconds, available_seconds, utilisation_bp, denominator_state

One row per station per period, ordered by station_id then period_id. denominator_state is the word empty or the word populated, never a blank field.

## antenna_utilisation_ledger.tsv

columns: antenna_uid, period_id, occupied_seconds, available_seconds, utilisation_bp, denominator_state

One row per aperture per period, ordered by antenna_uid then period_id. denominator_state is the word empty or the word populated, never a blank field.

## mission_settlement_statements.csv

columns: mission_id, period_id, won_pass_count, eligible_seconds, usable_capacity_kib, accepted_kib, deferred_kib, unused_capacity_kib, net_mcr

One row per mission per period, every pair present, ordered by mission_id then period_id.

## station_settlement_statements.csv

columns: station_id, period_id, won_pass_count, eligible_seconds, accepted_kib, unused_capacity_kib, utilisation_bp

One row per station per period, every pair present, ordered by station_id then period_id.

## contract_compliance_ledger.csv

columns: contract_id, period_id, mission_id, obligation_kib, delivered_kib, reserved_kib, shortfall_kib, compliance_state

One row per contract period with settled terms. compliance_state is met, exempt or short.

## credit_debit_ledger.csv

columns: contract_id, period_id, shortfall_kib, shortfall_debit_mcr, unused_reserved_kib, unused_credit_mcr, outage_credit_mcr, carry_restore_kib, net_mcr

One row per contract period with settled terms.

## outage_adjustment_ledger.psv

columns: contract_id, period_id, mission_id, claim_overlap_seconds, qualifying_floor_seconds, outage_qualified, exempt_kib, carry_restore_kib

One row per contract period with settled terms, qualified or not.

## exception_classification_report.jsonl

columns: exception_class, subject_id, code, detail_value

exception_class is the report_class attribute that exception_code_dictionary.xml gives the code, and the reject_reason column of the rejected ledger is that code reason_slug attribute. Ordered by exception_class then subject_id then code, then the period the exception arose in, P1 before P2 before P3. That period is a sort key only and is not a column of this report. exception_class is admission, capacity_cap, displacement, carry_forfeit, empty_denominator or late_cancel. subject_id is the contact_id for admission, capacity_cap, displacement and late_cancel, the contract_id for carry_forfeit, and the antenna_uid for empty_denominator. detail_value is the predicate index, the clipped volume, the displaced seconds, the forfeited volume, zero, or the deferred volume respectively.

## tie_resolution_report.csv

columns: antenna_uid, period_id, contact_id_kept, contact_id_yielded, decided_at_level

Ordered by antenna_uid, period_id, contact_id_kept, contact_id_yielded.

## cross_source_discrepancy_report.psv

columns: source_left, source_right, subject_id, period_id, left_value, right_value, delta_value, discrepancy_class

delta_value is left_value less right_value. period_id is empty for both families. source_left and source_right name the two sides as fixed slugs rather than as file names: the first family writes canonical_ledger and downlink_report, the second writes rate_schedule and legacy_flat_table.

## invariant_check_report.json

columns: check_count, checks, all_balanced

checks is a list of objects with check_name, left_value, right_value and balanced, in the fixed order below.

## period_reconciliation_totals.json

columns: P1, P2, P3, network

Each period key holds won_pass_count, eligible_seconds, usable_capacity_kib, accepted_kib, deferred_kib, unused_capacity_kib, carry_in_kib, carry_forfeit_kib, carry_out_kib, shortfall_debit_mcr, unused_credit_mcr, outage_credit_mcr, net_mcr, occupied_seconds and available_seconds. The network key holds net_mcr, accepted_kib and won_pass_count summed across the periods.

## network_settlement_summary.xml

columns: settlement, missions, stations, network

See the layout below.

## per_mission_final_summary.md

columns: mission_id, accepted_kib, deferred_kib, unused_capacity_kib, net_mcr

See the layout below.

## stage_digest_manifest.json

columns: artifact_count, core_digest, per_artifact_sha256, stage_count

artifact_count is twenty nine and stage_count is fourteen. per_artifact_sha256 maps each core artifact name to the sha256 of its own bytes. core_digest is the sha256 of the concatenation of those bytes in the order output_artifact_contract.md gives. serialization_and_digest_contract.md owns the digest rules and this manifest is excluded from its own digest.

## invariant check order

  1. admitted_equals_won_plus_displaced
  2. accepted_never_exceeds_allocated
  3. allocated_never_exceeds_demand
  4. unused_matches_capacity_less_accepted
  5. carry_split_matches_accepted
  6. allocation_within_aperture_budget
  7. credit_rows_match_entitlement_rows
  8. ration_trace_groups_are_over_subscribed

Checks two, three, six and eight are counts of violations and their
right value is zero. Checks one, four, five and seven compare two
totals.

## network_settlement_summary.xml layout

    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <settlement>
    <missions>
    <mission id="MSN-01" period="P1"><accepted_kib>0</accepted_kib><deferred_kib>0</deferred_kib><net_mcr>0</net_mcr></mission>
    ... one line per mission period, in mission then period order ...
    </missions>
    <stations>
    <station id="ST-AUR" period="P1"><accepted_kib>0</accepted_kib><utilisation_bp>0</utilisation_bp></station>
    ... one line per station period, in station then period order ...
    </stations>
    <network>
    <net_mcr>0</net_mcr>
    <contract_period_count>0</contract_period_count>
    </network>
    </settlement>

contract_period_count is the number of rows in the credit ledger.

## per_mission_final_summary.md layout

    # mission settlement summary
    (blank line)
    | mission_id | accepted_kib | deferred_kib | unused_capacity_kib | net_mcr |
    | --- | --- | --- | --- | --- |
    | MSN-01 | 0 | 0 | 0 | 0 |
    ... one row per mission, in mission_id order, summed over periods ...
    (blank line)
    network net_mcr 0

Cells are separated by a vertical bar with one space on each side, and
each line begins and ends with a vertical bar.
