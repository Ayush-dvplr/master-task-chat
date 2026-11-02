# Cadence register

Standing obligations, the periods they are measured over, and how a period that
passed without one is counted.

## 1. Cadences

`cadence_register.csv` declares the standing obligations. Where a cadence
carries several revisions, the one that governs is the revision with the
greatest `revision` number, and every field is taken from that row. A lower
revision may carry a different period length or a different anchor, and none of
those values reaches any figure.

The `obligor` of the governing revision is a surface, not a handle, and it is
resolved by `identity-register.md` at that cadence's `anchor_at`. The principal
it resolves to owns the cadence. A cadence whose obligor stands for no principal
at that instant, or stands for two, is owned by nobody, and the debt it carries
reaches no principal anywhere in the closure while the cadence itself is
reported like any other.

A cadence carries a `period_days` and an `anchor_at`. Its periods are the half
open intervals

```
period p  =  [anchor_at + p * period_days * 1440 minutes,
              anchor_at + (p + 1) * period_days * 1440 minutes)
```

for `p` counting from zero. A period is elapsed when its start instant lies
before the window end, and the last elapsed period is cut short at the window
end rather than being dropped. A period whose start instant is at or after the
window end is not elapsed and is not counted.

## 2. Discharge

A period is discharged when at least one commitment whose `cadence_ref` names
that cadence, whose class is `SETTLED`, and whose `due_at` falls inside that
period, exists in the ledger. A commitment naming the cadence in any other class
discharges nothing.

## 3. Waivers

`waivers_desk.csv` and `waivers_partner.psv` carry waivers. A waiver names a
cadence and a period index. A waiver naming a period that is not elapsed changes
nothing and is not counted anywhere, and neither does a waiver naming a cadence
the register never declares. Two waivers naming one cadence and one period are
one waiver.

Each principal holds one allowance of four waivers for the whole window, shared
by every cadence it owns. The waivers in elapsed periods of those
cadences draw on it one each, in ascending order of period start and, for one
start, of cadence id. A waiver that draws while the allowance lasts is granted,
and a waiver that finds the allowance spent is lapsed. A cadence owned by nobody
draws on no allowance, and every waiver in its elapsed periods is granted.

## 4. Debt and streak

Walk the elapsed periods of a cadence in ascending order, holding a debt and a
streak that both begin at zero, and for each period take the first of these that
applies:

```
the period is discharged           the streak returns to zero, the debt is unchanged
the period holds a granted waiver  the debt is unchanged, the streak is unchanged
otherwise                          the debt rises by one, the streak rises by one
```

The discharged periods, the waived periods and the debt of a cadence are the
numbers of periods the walk takes on the first, the second and the third line.

The max streak of a cadence is the greatest value the streak held at any point
of the walk.

The effect of a waiver in an elapsed period is `LAPSED` when it is lapsed, and
otherwise `INERT` when its period is discharged and `SUPPRESSED` when it is not.
A waiver in a period that is not elapsed has no effect and is not recorded.
