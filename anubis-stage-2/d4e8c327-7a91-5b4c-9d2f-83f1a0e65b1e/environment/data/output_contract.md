# Output contract

The nine documents to deliver, with every key named here and the shape of every non-scalar value fixed.

/app/out/summary.json has one key, totals. totals holds granted_hours, claim_hours, demurrage_hours, capacity_hours, residual_hours, ledger_rows, cycles_with_remainder, running_demurrage_max, out_of_scope_rows, late_dropped and identity_checks. Every scalar is a non-negative whole number of berth-hours or a non-negative row count.

/app/out/policy_audit.json carries the audit tallies: substitution_hops, substitution_cycles, no_qualified_berth, resets, lots_expired, lots_cleared, ceiling_binding, ceiling_zero, epoch_reassignments, exceptions_applied, exceptions_unendorsed, exceptions_retracted, illegal_transitions, stale_events, duplicate_version_events, minimums_honoured_full, minimums_honoured_short, minimums_unmatched, circulars_applied, circulars_early, circulars_unendorsed, circulars_retracted, circular_chains_unresolvable, cutover_sides and withheld. Every scalar tally is a non-negative whole number counting how often the named rule fired.

/app/out/data_quality.json carries sources, header_gaps, late_recorded, null_forms, duplicate_identical, duplicate_conflicting, cross_source_collapsed, fold_disambiguated, gap_shifted, log_continuations, unknown_charterer_rows, out_of_horizon_rows, block_unit_rows, paren_negatives and restatement_gaps. Every scalar tally is a non-negative whole number counting rows of the shipped corpus.

/app/out/terminal_<Name>.json carries terminal, cycles (26 of them with cycle, capacity_hours, fill_level, minimum_total_hours, granted_hours, residual_hours, nor_count and binding), ledger (sorted by cycle, then canonical charterer, then nor_ref, with cycle, nor_ref, charterer, segment, booked_berth, laytime_hours, ceiling_hours, claim_hours, carried_in_hours, granted_hours, demurrage_hours, carried_out_hours, granted_to_date_hours, demurrage_to_date_hours, served_berth, hops, outcome, reason, granted_berthhours and minimum_hours) and out_of_scope (with nor_ref, charterer and reason). carried_in_hours is the demurrage a charterer brings into the cycle at that terminal before any ceiling cut, carried_out_hours is the demurrage it still holds there once the row's grant is applied, and the two to-date figures are running sums over that charterer's rows at that terminal in ledger order.

/app/out/segment_<liner|tramp>.json carries segment, totals (granted_hours and claim_hours) and by_terminal.

## Closed vocabularies

Every ledger row carries exactly one outcome from {FULL, PARTIAL, ZERO, EXCLUDED} and exactly one reason from the codes listed in reason_codes.json.

summary.json/totals/identity_checks is a map with three keys: capacity_minus_grant_minus_residual, claim_minus_grant_minus_demurrage, running_demurrage_falls. Each value is a non-negative integer counting the ledger rows where the identity fails.

policy_audit.json/withheld is a map with two keys: survival_cycles (a non-negative integer) and weather_stoppage (a string from {SHEX, SHINC, WWD}). Both are the settled readings reported in the form the rule documents demand.

policy_audit.json/cutover_sides is a map with two keys: before and after, each a non-negative integer counting the ledger rows whose governing NOR instant falls strictly before, respectively on or after, the April cutover declared in derivation_policy.ini.

data_quality.json/sources is a map keyed by source name as it appears in source_declarations.properties, each value a map with three keys: declared (the row count declared in source_declarations.properties), parsed (the number of rows that read without a format error) and admitted (the number of rows that survived admission filtering).

Every terminal document's cycles entry carries a boolean binding; the field is a JSON boolean, not an integer.

Every segment document's by_terminal entry is a map from terminal name to the granted berth-hours contributed to that segment by that terminal, each a non-negative whole number.

## Audit tally semantics

Each policy_audit.json tally counts rows in the shipped corpus that carry its named marker token, as follows. stale_events, duplicate_version_events and illegal_transitions count rows of state_events_p*.jsonl whose event or transition field is stale_event_marker, duplicate_version_marker or illegal_transition_marker respectively. circulars_applied, circulars_unendorsed, circulars_early, circulars_retracted and circular_chains_unresolvable count rows of port_circulars_p*.jsonl whose event field names the matching marker. exceptions_applied, exceptions_unendorsed and exceptions_retracted count rows of commitment_exceptions.csv whose event field names the matching marker. Every data_quality.json anomaly tally (log_continuations, header_gaps, null_forms, duplicate_identical, duplicate_conflicting, cross_source_collapsed, fold_disambiguated, gap_shifted, unknown_charterer_rows, out_of_horizon_rows, block_unit_rows, paren_negatives, restatement_gaps, late_recorded) and the audit tallies that pertain to source anomalies (epoch_reassignments, substitution_hops, substitution_cycles, no_qualified_berth, resets) count the lines in the approval_audit log family whose event token is the marker named after that tally. summary.totals.late_dropped and out_of_scope_rows aggregate those counts for the summary. ceiling_binding counts the terminal cycles whose residual_hours is zero while capacity_hours is positive; ceiling_zero counts the terminal cycles whose capacity_hours is zero. minimums_honoured_full, minimums_honoured_short and minimums_unmatched count ledger rows against the commitment_agreements register as the names describe. lots_expired, lots_cleared and cutover_sides are derived from the ledger spine as the rule documents describe. cycles_with_remainder counts the terminal cycles in which the indivisible remainder step handed out at least one berth-hour.
