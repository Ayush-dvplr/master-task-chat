# Precision and rounding

Every quantity in this service is a whole number: token counts, token units, reservation units (RU), quarters of a step and micro-credits. No stage uses binary floating point, and no stage rounds except where this file says so.

Demand: a tenant's demand in RU is its token units divided by the units per RU of its pool, rounded up to a whole RU. A tenant with no token units has a demand of zero.

Movements: the raw movement of st_settle.md is rounded to the nearest whole unit.

Targets: the division inside a target keeps its whole part and its remainder exactly; the remainders are compared as whole numbers over the same divisor.

Overage: the overage charge of st_bill.md is rounded up to a whole micro-credit.

Orchestration shares: the orchestration charge of a pool is split in whole micro-credits as st_bill.md states; nothing is rounded there.

Reservation charges and totals are exact products and sums of whole numbers.
