# Billing of settled reservations

Every member of every pool, whatever the exit of the pool, receives one bill line for its traffic class. Amounts are in whole micro-credits.

Rates: the rate card (the workbook rc_23.xlsx, sheet rates) lists, per traffic class, rate rows with an effective date. The row that applies to a class is the row of that class with the latest effective date on or before the date part of the window end of the class. A row gives three rates: ru_rate_micro (micro-credits per settled RU), over_rate_micro (micro-credits per thousand overage units) and round_fee_micro (micro-credits per settlement round).

Reservation charge: the settled reservation of the member times ru_rate_micro; a settled reservation below zero gives a charge below zero.

Overage charge: the overage units of a member are its token units minus its settled reservation times the units per RU of its pool, and zero when that difference is not positive. The overage charge is the overage units times over_rate_micro, divided by one thousand and rounded up (pr_num.md).

Orchestration charge: a pool is charged round_fee_micro for each round of its round count, and for each round of its budget when its round count is -1. The pool charge is shared among its members in equal whole micro-credits; the micro-credits that do not divide evenly go one each to the members in name order, starting from the first name.

Bill total: the sum of the reservation, overage and orchestration charges of the line.

Class totals sum the lines of the class; the grand figures of a run sum the class totals.
