# Counterfactual parameters

The closing message calls for seven counterfactual quantities, fourteen integers in all. This document fixes each parameter and the exact arithmetic behind each integer. None of them is written to any artifact. Terms used below: a claim's `want` is `max(0, ultimate + alae - paid_to_date)` as `allocation_rules.md` defines it, taken from its ledger row before allocation; a retracted or excluded ledger row has `want` and `alae` of zero; a claim's cycle is the cycle its governing `recorded_instant` is placed in.

## Fitted ALAE fraction

The ALAE allocation convention is settled from `claim_adjustment_log.log` by enumeration against the two candidates named in `alae_rules.md`. The `pro_rata` convention uses a single fraction shared across every observation, fitted from the shipped log as the unique value, written with the fewest decimal places, for which every row's `alae` lies within one dollar of `fraction * settled` rounded half-up to a whole dollar. The same fraction prices every claim without an adjustment-log row.

## Carried-IBNR-zero (R1 and R2)

Under this counterfactual every claim's ultimate collapses to its `paid_to_date`, so a claim's `want` shrinks to its `alae`. R1 is the sum of `alae` over every ledger row whose claim is not in `retraction_notices.csv`. R2 is the count of ledger rows whose governing `want` exceeds their `alae`.

## Rival ALAE allocation (R3 and R4)

Under this counterfactual the ledger is rebuilt with the rival of the surviving ALAE convention in force (the two candidates are declared in `alae_rules.md`; whichever one did not survive the enumeration is the rival here). R3 is the count of ledger rows whose `want` under the rival convention differs from their governing `want`. R4 is the sum of `want` over every row of the rebuilt ledger.

## Extended discount curve tenor (R5 and R6)

A cycle `Hnn` sits `nn / 2` years out (H01 is half a year, H26 is thirteen years). Its discount factor under the settled curve reading is `(1 + rate / 100) ^ (-years)` rounded to six decimal places, where under `duration_matched` the rate is the mark at that tenor, interpolated linearly between the nearest marks below and above it, and held at the end mark beyond either end of the curve. Under this counterfactual the curve gains one tenor point. The added tenor is `15` years and its rate equals the maximum observed rate across the shipped curve, plus a fixed increment of `0.5` percentage points. In symbols: `curve_extended[15] = max(curve.values()) + 0.5`. R5 is the count of claims not in `retraction_notices.csv` whose discount factor at their own cycle differs between the shipped curve and the extended curve. R6 is the present-valued IBNR at the end of H26 on the shipped curve: for every claim not in `retraction_notices.csv`, its governing `want` times the H26 discount factor, rounded to the nearest whole dollar with exact halves going to the even dollar, summed.

## Retro offset never applied (R7 and R8)

Under this counterfactual the retro offset is undone on every claim not in `retraction_notices.csv` whose first line in `claim_adjustment_log.log` records `layer=cat_excess` (the first line, even where the booked layer differs): its `want` is multiplied by `1.10` before the total is taken, rounded half-up to a whole dollar. Every other claim keeps its governing `want`. R7 is the resulting total of `want` across every claim not in `retraction_notices.csv`. R8 is the count of claims whose `want` was multiplied.

## Indivisible remainder (R9 and R10)

Not a counterfactual: this is the governing-run observation. R9 is the sum of the dollars handed out by Step 3 (the indivisible remainder step) in `allocation_rules.md`, taken across every (lob, cycle) cell. R10 is the count of (lob, cycle) cells that handed out at least one dollar in Step 3.

## Admission instant lifted (R11 and R12)

Under this counterfactual the admission instant `2033-01-15T00:00:00Z` is lifted for the claim transaction logs. R11 is the count of distinct claims with at least one claim transaction row recorded strictly after the admission instant. R12 is the sum of the column-4 `paid_to_date` over those dropped claim transaction rows, in whole dollars.

## Unendorsed amendments honoured (R13 and R14)

Under this counterfactual every treaty endorsement circular is honoured, including those that fail the filter in `amendment_rules.md`, so each dropped circular's `cede_cap_raise` reaches its claim's `alae`. R13 is the count of distinct claims that hold a ledger row and carry at least one dropped circular. R14 is the count of distinct (lob, cycle) cells holding a ledger row of such a claim.
