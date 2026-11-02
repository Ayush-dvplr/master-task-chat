# S09 deliverable volume

S09 turns the capacity of the surviving passes into an allocation
against the aperture budget. It runs per aperture per settlement period,
over the rows that S07 accepted.

## demand

    demand_kib = min(usable_capacity_kib, opening_backlog_kib)

opening_backlog_kib is the backlog of the mission for the period, taken
from onboard_backlog_reports.csv. Several reports exist per mission
period; the binding one is the report whose report_state is current, and
where more than one is current the highest report_seq. Superseded
reports bind nothing.

The backlog used here is the opening figure of the period, the same
value for every pass of that mission in that period. The running backlog
that S10 keeps is not used at S09. Using the running figure makes the
ration depend on the order the apertures happen to be visited, and it is
wrong.

## the budget test

The aperture period budget lives only in the binding sheet of
aperture_contract_workbook.xlsx, column period_budget_kib.

Let the accepted rows of the aperture period be ordered by the S07
ordering, and let their demands be d1 to dn. When the sum of the demands
is at or below the budget, every row is allocated its whole demand and
the ration does not run. No trace row is written for that aperture
period.

## the ration

When the sum of the demands exceeds the budget, the budget is rationed
by the damped integer procedure in rationing_iteration_notes.md. That
document is binding and carries a worked example.

The allocation of a row is written to allocated_kib. The pass trace is
written to rationing_pass_trace, one row per pass of the procedure per
aperture period that ran it.
