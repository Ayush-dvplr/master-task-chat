# Counterfactual parameters

The closing message calls for seven counterfactual quantities whose parameters are not scattered across the evidence tables. This document fixes each parameter and names the rival reading or the alternate numeric that defines the counterfactual. These parameters are inputs to the counterfactual arithmetic in the closing message only; none of them is written to any artifact. The arithmetic itself follows the rules in `allocation_rules.md`, `alae_rules.md`, `chain_ladder_rules.md` and `discounting_rules.md`.

## Fixed ALAE pro-rata fraction

The ALAE allocation convention is settled from `claim_adjustment_log.log` by enumeration. The surviving reading is `pro_rata`, under which ALAE is a near-constant fraction of the settled amount on every observed line. That constant fraction is `0.08` (eight percent of settled, half-up rounded to a whole dollar). This value is the one that fits every observation in the log; any other fraction fails at least one row. The fraction `0.08` is used:

- as the default ALAE on a claim whose row carries no explicit adjustment, as `int(round(0.08 * paid_to_date))` with half-up rounding
- to test every log line in the convention-settling pass; an observation whose `alae` is within one dollar of `int(round(0.08 * settled))` counts as consistent with `pro_rata`

## Carried-IBNR-zero (R1 and R2)

Under this counterfactual every claim's carried IBNR is set to zero before the three-step allocation runs. Each claim's unmet becomes `max(0, alae)` because `ultimate` collapses to `paid_to_date`. R1 is the total ceded recoverable that results from allocating that reduced population; R2 is the count of ledger rows whose `outcome` differs from the governing run (every row whose governing unmet exceeded its ALAE-only unmet).

## Rival ALAE allocation (R3 and R4)

Under this counterfactual the module re-runs its allocation with the rival ALAE convention `excess_only` in force. R3 is the count of settled claims whose cession differs from the governing (`pro_rata`) run; R4 is the resulting total ceded recoverable in whole dollars.

## Extended discount curve tenor (R5 and R6)

Under this counterfactual the discount curve is extended by one tenor point. The added tenor is `15` years and its rate equals the maximum observed rate across the shipped curve, plus a fixed increment of `0.5` percentage points. In symbols: `curve_extended[15] = max(curve.values()) + 0.5`. R5 is the count of treaty settlements whose present value differs from the governing run; R6 is the resulting present-valued IBNR at the end of H26.

## Retro offset never applied (R7 and R8)

Under this counterfactual every cat-excess-layer unmet is multiplied by `1.10` before the IBNR total is computed. In symbols: `unmet_without_retro = int(round(unmet * 1.10))` for every ledger row whose booked layer is `cat_excess`; retention and working-excess rows pass through unchanged. R7 is the resulting total year-end IBNR; R8 is the count of ledger rows whose grant would differ (equal to the count of cat-excess rows).

## Indivisible remainder (R9 and R10)

Not a counterfactual: this is the governing-run observation. R9 is the sum of the dollars handed out by Step 3 (the indivisible remainder step) in `allocation_rules.md`, taken across every (lob, cycle) cell. R10 is the count of (lob, cycle) cells that handed out at least one dollar in Step 3.

## Admission instant lifted (R11 and R12)

Under this counterfactual the admission instant `2033-01-15T00:00:00Z` is lifted for every file. R11 is the count of claims whose every source row was recorded after the admission instant (so the governing run would admit none of them) and that would therefore enter the ledger if admission were lifted. R12 is the sum of their `paid_to_date` in whole dollars.

## Unendorsed amendments honoured (R13 and R14)

Under this counterfactual every treaty endorsement circular is honoured regardless of whether its claim appears in any `endorsement_audit.log*` rotation and regardless of whether the underwriter who signed it held LOB authority at the audit instant. R13 is the count of claims whose governing ALAE would differ (equal to the count of circulars whose `claim_ref` was dropped by the governing endorsement filter). R14 is the count of (lob, cycle) cells that would see a different fill level under that counterfactual.
