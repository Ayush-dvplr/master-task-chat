# Output contract

Nine JSON files are produced. Every number in them is a whole number. Each
file is written with two spaces of indentation absent, one space of
indentation present, and keys sorted, that is `indent=1` and `sort_keys=True`.
Every customer is named in canonical identity form, for example `CUS-0412#2`.
Every cycle is named `C01` to `C24`. Every site is named `North`, `South`,
`West` or `East`. Every segment is named `commercial` or `public`. The as of
instant is reported as the string in `derivation_policy.ini`.

## region_North.json, region_South.json, region_West.json, region_East.json

Keys `site`, `as_of`, `cycles`, `ledger`, `out_of_scope`, `totals`.

`cycles` holds twenty four objects in cycle order, each with `cycle`,
`capacity_equiv`, `fill_level`, `floor_total_equiv`, `granted_equiv`,
`residual_equiv`, `request_count`, `binding`. `floor_total_equiv` is the sum of
the honoured minimums of the cycle. `binding` is a JSON boolean.

`ledger` holds one object per request of the site inside the horizon, ordered
by cycle, then canonical identity, then reported reference, each with `cycle`,
`request_ref`, `customer`, `segment`, `requested_node`, `served_node`, `hops`,
`quantity_equiv`, `carried_in_equiv`, `ceiling_equiv`, `claim_equiv`,
`floor_equiv`, `granted_equiv`, `granted_wafers`, `deficit_equiv`,
`carried_out_equiv`, `granted_to_date_equiv`, `deficit_to_date_equiv`,
`outcome`, `reason`. A request that does not claim carries zero in every
figure except `quantity_equiv`, `ceiling_equiv` and the two running totals.
Where the walk found no served node, `served_node` is an empty string and
`hops` is zero.

`out_of_scope` holds one object per request of the site outside the horizon or
with a customer that cannot be resolved, ordered by reported reference, each
with `request_ref`, `customer`, `site`, `reason`. An unresolved customer is
reported with the reference as it was written.

`totals` carries `ledger_rows`, `granted_equiv`, `claim_equiv`,
`deficit_equiv`, `capacity_equiv`, `residual_equiv`.

## segment_commercial.json, segment_public.json

Keys `segment`, `as_of`, `sites`, `cycles`, `outcome_counts`,
`reason_counts`, `totals`.

`sites` holds four objects in the order North, South, West, East, each with
`site`, `granted_equiv`, `claim_equiv`, `deficit_equiv`, `ledger_rows`.
`cycles` holds twenty four objects in cycle order, each with `cycle`,
`granted_equiv`, `claim_equiv`, `deficit_equiv`, `ledger_rows`.
`outcome_counts` is an object keyed by the four outcome names.
`reason_counts` is an object keyed by every reason that occurs, the key
`NONE` included. `totals` carries `granted_equiv`, `claim_equiv`,
`deficit_equiv`, `ledger_rows` and `customers`, the count of distinct
canonical identities with a ledger row in that segment.

A request belongs to the segment of its own epoch, so one customer id can
appear in both segment files.

## summary.json

Keys `as_of`, `sites`, `segments`, `cycles`, `totals`.

`sites` holds four objects with `site`, `capacity_equiv`, `granted_equiv`,
`claim_equiv`, `deficit_equiv`, `residual_equiv`, `ledger_rows`. `segments`
holds two objects with `segment`, `granted_equiv`, `claim_equiv`,
`deficit_equiv`, `ledger_rows`. `cycles` holds twenty four objects with
`cycle`, `capacity_equiv`, `granted_equiv`, `claim_equiv`, `deficit_equiv`,
`residual_equiv`, `ledger_rows`.

`totals` carries `ledger_rows`, `granted_equiv`, `claim_equiv`,
`deficit_equiv`, `capacity_equiv`, `residual_equiv`, `out_of_scope_rows`,
`customers_served`, then `identity_checks` and `spine`.

`identity_checks` is an object with `region_minus_segment_granted`,
`capacity_minus_granted_minus_residual` and
`claim_minus_granted_minus_deficit`. Each is the difference the name
describes, summed over the whole horizon, and each is zero in a sound result.

`spine` is an object with `binding_cells`, `non_binding_cells` and
`largest_deficit_to_date`, the last an object with `customer`, `site` and
`value` for the largest running deficit total reached anywhere in the
horizon, ties broken by canonical identity ascending then site ascending.

## policy_audit.json

A single object of whole number tallies with these keys:
`floors_honoured_full`, `floors_honoured_short`, `floors_unmatched`,
`exceptions_applied`, `exceptions_unendorsed`, `exceptions_retracted`,
`illegal_transitions`, `stale_events`, `duplicate_version_events`,
`amendments_applied`, `amendments_unendorsed`, `amendments_early`,
`amendments_retracted`, `amendment_chains_unresolvable`, `no_qualified_node`,
`substitution_cycles`, `resets`, `lots_expired`, `lots_cleared`,
`ceiling_binding`, `ceiling_zero`, `epoch_reassignments`.

It also carries `substitution_hops`, an object keyed `0`, `1`, `2`, `3`
counting ledger rows by hop count; `cutover_sides`, an object keyed `before`
and `from` counting ledger rows by the side of the cutover they fall on;
and `withheld`, an object with `quantity_governed_before_cutover` and
`carry_forward_age`.

`epoch_reassignments` counts the requests whose epoch is not the first epoch
of their customer id.

## data_quality.json

Keys `sources`, `header_gaps`, `null_forms`, `late_recorded`,
`duplicate_identical`, `duplicate_conflicting`, `cross_source_collapsed`,
`fold_disambiguated`, `gap_shifted`, `log_continuations`,
`unknown_customer_rows`, `out_of_horizon_rows`, `lot_unit_rows`,
`paren_negatives`, `restatement_gaps`.

`sources` is an object keyed by source code, as declared in
`source_declarations.properties`, each with `declared_rows`, `parsed_rows` and
`admitted_rows`. `declared_rows` is the figure the file reported, `parsed_rows`
the data rows the file actually carried, `admitted_rows` those at or before the
as of instant. `header_gaps` is an object keyed by file name holding the
declared figure minus the parsed figure, and carries an entry only for a file
where the two differ.

`null_forms` is an object with `node_empty`, `node_backslash_n` and
`row_truncated`, counting registry rows of each shape. `late_recorded` is an
object keyed by source code. `fold_disambiguated` counts stamps resolved
inside a repeated window and `gap_shifted` counts stamps moved out of a
missing window. `log_continuations` counts audit lines that continue the entry
above them. `lot_unit_rows` counts rows whose unit is a lot form anywhere in
the corpus. `paren_negatives` counts declared values written in parentheses.
`restatement_gaps` counts order book rows whose two quantity columns differ.
