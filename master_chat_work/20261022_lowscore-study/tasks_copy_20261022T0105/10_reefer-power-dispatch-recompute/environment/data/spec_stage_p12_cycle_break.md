# Stage P12, the cycle detection and the break

RULE P12.a  A displacement is the triple of the short reefer, the
reefer it displaced and the interval it happened in. Every
displacement a sweep applies is remembered.

RULE P12.b  The state of a sweep is the set of reefer and interval
pairs standing powered at the close of that sweep. Its signature is
the sha256 of those pairs written as the reefer identifier, an at
sign and the interval, joined by semicolons in ascending order. The
opening state is recorded before the first sweep and the closing
state of every sweep after it.

RULE P12.c  The sweep budget is the dependency protection depth of
dispatch_operations_memo.pdf plus two.

RULE P12.d  A sweep that applies no displacement closes the
correction. The closing state reads settled.

RULE P12.e  A displacement whose reverse triple was applied in an
earlier sweep is a cycle. Every cycle of a sweep is recorded, in
ascending order of the short reefer, the displaced reefer and the
interval.

RULE P12.f  The cycle of a sweep carrying the lowest incremental
penalty is the one that is broken, and it publishes a broken flag of
true while every other cycle of that sweep publishes false. The
penalty of a cycle is the draw of the displaced reefer in that
interval, then the interval, then the displaced identifier, then the
short identifier, compared in that order.

RULE P12.g  Breaking a cycle freezes both of its reefers. A frozen
reefer is neither corrected nor displaced again. The sweeps carry on
after the break.

RULE P12.h  Sweeps that run the budget out without a sweep applying
nothing close with a closing state of budget_spent.

## Published document

cycle_break_report.json, whose keys are day_id, sweeps_run,
sweep_budget, closing_state, settled_at_sweep, correction_count,
cycle_count, cycles, frozen_reefers and state_signatures, in that
order. settled_at_sweep is zero when the closing state is not
settled. Each entry of cycles carries sweep, short_reefer,
displaced_reefer, interval and broken, in that order.
