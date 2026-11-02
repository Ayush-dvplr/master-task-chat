# Chain-ladder rules

Age-to-ultimate development factors are computed volume-weighted across lines of business within each development year, then applied in one multiplication to project immature accident years to ultimate.

## Governing claim row

The governing claim row for a claim is the single row chosen for that claim by the cross-source collapse stage: the row whose `_source` and recorded instant win under the precedence declared in `source_declarations.properties`, carrying the governing `paid_to_date` (column 4 of its claim transaction log, per `source_manifest.md`) and the governing `incurred` (column 5 of the same row). All chain-ladder arithmetic reads these two values.

## Development year

For each admitted claim transaction row (that is, every row that survived the admission filter against the admission instant `2033-01-15T00:00:00Z`), the development year is `recorded_instant.year - accident_year`. Rows whose computed development year is negative are clipped to zero. The accident year is the integer suffix of the `AY` prefix on the row (for example `AY2028` has accident year 2028).

## Age-to-ultimate factor per development year

Within each development year `d`, the factor is

```
factor[d] = sum over all admitted claim transaction rows of row.incurred  /  sum over all admitted claim transaction rows of row.paid_to_date
```

where the sum is taken across every line of business and only over the admitted rows. If the denominator is zero, the factor for that development year is 1.0.

The computed factor is clipped to the interval `[1.0, 2.5]` and rounded to six decimal places using half-up rounding (if the seventh decimal is five or more, round up; otherwise, round down). This clipping bound is reported in `methodology_audit.json` under `chain_ladder.factors_bounded`.

## Per-claim ultimate

For each governing claim row, the ultimate dollar amount is

```
ultimate = half_up_round(paid_to_date * factor[dev_year])
```

where `dev_year` is the development year computed from the governing row's `recorded_instant` and the claim's accident year, and `half_up_round` rounds a positive number up when the fractional part is one half or more and down otherwise. The resulting integer is the `ultimate` field on every ledger row for that claim.

## Carryforward of IBNR

The IBNR increment for a claim is `ultimate - paid_to_date`, accumulated by cycle. Running totals never heal: a wrong estimate at an early cycle is still visible at cycle 26. The chain-ladder stage ships through to the carryforward unchanged; discounting (`discounting_rules.md`) is applied after chain-ladder on the three long-tail LOBs.
