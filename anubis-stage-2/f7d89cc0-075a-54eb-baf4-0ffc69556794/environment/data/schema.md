# Meridian Interstate Grid Compact - Reconciliation Schema (v4.0)

This document is the complete regulatory data contract for a Meridian Interstate
Grid Compact (MIGC) monthly retail electricity settlement extract. The MIGC is a
fictional multi-jurisdictional regulator that governs retail electric utility
billing across four member regions (Meridian North, Meridian South, Meridian
East, Meridian West). Every rule that decides a graded value in the settlement
report is written out here. There is no external reference; nothing outside this
document is authoritative.

Read the whole document before touching any figure. Rules from later sections
routinely override the naive reading of earlier ones (a peak-demand interval
falling on a §3.5 holiday is excluded even though §6 says it is the highest),
and multiple sections often layer onto one bill (a grandfathered customer whose
grandfather expires mid-period pays under §9 old tariff up to the expiry date
and §9 new tariff after, and a §11 regulator order may still retroactively
change either half).

## §1. Scope and vocabulary

The extract covers a single MIGC settlement period. For every extract the
period is exactly the month of October 2025 in the Meridian Standard Time
zone (UTC minus five hours before the §5.2 fall-back cutover, UTC minus six
after it). The period starts at 2025-10-01 00:00:00 MST and ends at
2025-10-31 23:59:59 MST inclusive, so the calendar carries 31 civil days and,
by the cutover in §5.2, 745 civil hours rather than 744.

Term glossary, used consistently below:

- **MRC** - Meridian Credit, the settlement currency. All internal figures are
  quoted in integer MRC-cents (mrcc). One MRC equals one hundred mrcc.
- **FTU** - Foreign Trade Unit, the parallel currency used by MIGC-declared
  diplomatic customers (see §12). FTU amounts are quoted in integer FTU-cents
  (ftuc).
- **Rate class** - Residential (RES), Commercial (COM), Industrial (IND).
  Every customer holds exactly one rate class at any given civil timestamp,
  but the class may change mid-period via a §9 rate-class migration ticket.
- **TOU period** - a labelled band of the civil day inside which one rate
  applies. The four labels are `peak`, `shoulder`, `night`, `weekend`.
  Windows per rate class are given in §5.1.
- **DDC** - Declared Demand Component, the peak-kW driver of the demand
  charge. See §6.
- **NMB** - Net Metering Bank, the running kWh balance owed to a solar
  customer against future bills. See §7.
- **FAC** - Fuel Adjustment Charge, a per-kWh adder that changes by
  calendar month. See §8.
- **FY** - Meridian Fiscal Year. The MIGC fiscal year ends October 31 and
  begins November 1. The billing period covered by this extract is the
  last month of FY2025.
- **Grandfather freeze** - a locked tariff schedule some customers keep past
  a general tariff update. See §10.
- **Retroactive order** - a regulator ruling that rewrites a rate for a
  previously settled period. See §11.

## §2. Input file inventory

Every file below sits directly under `/app/data/`. Flat layout, no
subdirectories. Text files are UTF-8 with LF line endings.

| Path | Kind | Contents |
|------|------|----------|
| `schema.md` | markdown | This document. |
| `customers.csv` | CSV | Customer master. §3.1. |
| `premises.csv` | CSV | Premise (service address) master. §3.2. |
| `tariff_schedule.csv` | CSV | Rate schedule versioned by effective date. §3.3. |
| `fac_index.csv` | CSV | Fuel Adjustment Charge index by month. §3.4. |
| `holiday_calendar.json` | JSON | Non-billing holidays. §3.5. |
| `dst_calendar.json` | JSON | Daylight-saving cutovers relevant to the period. §3.6. |
| `currency_rates.json` | JSON | MRC <-> FTU daily conversion. §3.7. |
| `regulator_orders.json` | JSON | Retroactive tariff-modification orders. §3.8. |
| `net_metering_bank.csv` | CSV | Carried-forward net-metering balances at period start. §3.9. |
| `service_tickets.json` | JSON | Move-in, move-out, and rate-class-change events during the period. §3.10. |
| `meter_reads.csv` | CSV | Meter reads recorded during the period. §3.11. |
| `demand_intervals.csv` | CSV | 30-minute interval demand samples for COM and IND customers. §3.12. |

Every one of the twelve data files is snapshot data and may vary between
settlement cases. A later snapshot may change reference rows and row order,
customer currencies or grandfather dates, premise regions, tariff effective
windows and integer rates, signed FAC values, calendar treatments, currency
rates, regulator orders, NMB balances, and transaction rows. Such changes
must still satisfy the file shapes, allowed values, integrity rules, and
October 2025 period defined here. No input row order has semantic significance
unless a section explicitly gives an ordering rule. The shipped extract also
carries this document; other extracts carry the twelve data files only.

## §3. Reference tables

### §3.1 `customers.csv`

Columns, in this order, comma-separated, single header row:

```
customer_id,name,rate_class,premise_code,meter_class,billing_currency,grandfather_flag,grandfather_date,grandfather_expires_on,solar_enrolled,fiscal_group
```

Semantics:

- `customer_id` - five-character identifier `C####` (uppercase C, four digits).
- `name` - display name, free text, ASCII only.
- `rate_class` - one of `RES`, `COM`, `IND`. Class at period start; a mid-period
  migration is recorded in `service_tickets.json` (§3.10).
- `premise_code` - foreign key into `premises.csv`.
- `meter_class` - one of `mech5` (five-digit mechanical, rolls at 99999.999
  kWh), `hybrid6` (six-digit hybrid, rolls at 999999.999 kWh), or `smart7`
  (seven-digit smart meter, effectively rollover-free within a period). See
  §4.1.
- `billing_currency` - one of `MRC` or `FTU`. FTU customers pay in Foreign
  Trade Units under §12.
- `grandfather_flag` - `true` or `false`. `true` locks the customer to the
  tariff schedule in effect on `grandfather_date` until `grandfather_expires_on`.
  See §10.
- `grandfather_date` - ISO date `YYYY-MM-DD`, empty when `grandfather_flag` is
  false.
- `grandfather_expires_on` - ISO date, empty when `grandfather_flag` is false.
  When the grandfather expires strictly inside the billing period, apply the
  §10 pro-rata split rule.
- `solar_enrolled` - `true` or `false`. Solar-enrolled customers accrue a
  §7 net-metering bank.
- `fiscal_group` - one of `commercial`, `public`, or `residential`. Public
  customers (embassies, agency offices) pay in FTU under §12.

### §3.2 `premises.csv`

Columns:

```
premise_code,street,city,region,latitude,longitude,meter_channel_count,altitude_bracket
```

Semantics:

- `premise_code` - the primary key referenced by `customers.csv`. Format
  `P` followed by a positive decimal number with no leading zeros, of any
  length (`P7`, `P88`, `P1020`). §16.2 defines the numeric-suffix sort order
  for output rendering.
- `region` - one of `Meridian_North`, `Meridian_South`, `Meridian_East`,
  `Meridian_West`. Drives the regional rollup in §14.
- `meter_channel_count` - 1 for a single-register premise, or 2 where the
  premise meters two phase groups on separate channels. Multi-channel
  premises sum their per-channel consumption before any §5 bucketing, and
  sum their per-channel demand per `interval_start` before §6.
- `altitude_bracket` - `low`, `mid`, or `high`. Not used in any graded figure
  in this period; documented so a reader knows the extract is truthful.

### §3.3 `tariff_schedule.csv`

Columns:

```
schedule_id,rate_class,tou_period,effective_from,effective_until,energy_rate_mrcc_per_kwh,demand_rate_mrcc_per_kw,customer_charge_mrcc,order_of_precedence
```

Semantics:

- `schedule_id` - synthetic string, unique per row: `S-YY-NN-XXXX` for a
  standard row, `S-YY-RNN-XXXX` for a row a §11 order introduces (`RNN`
  repeats the order number).
- `rate_class` and `tou_period` - the key into the applicable rate at a given
  civil timestamp. `tou_period = *` means the row supplies the demand rate
  and customer charge but no energy rate (energy rates live in the four
  labelled rows).
- `effective_from` - ISO date, inclusive. The rate applies to consumption on
  and after this date.
- `effective_until` - ISO date, inclusive. Empty means open-ended.
- `energy_rate_mrcc_per_kwh` - integer mrcc per kWh. Read as an integer;
  never divide before rounding.
- `demand_rate_mrcc_per_kw` - integer mrcc per kW, only meaningful when
  `tou_period = *`.
- `customer_charge_mrcc` - flat monthly charge, only meaningful when
  `tou_period = *`. Applied once per customer per period regardless of
  usage.
- `order_of_precedence` - a small integer. When two rows cover the same
  `(rate_class, tou_period, date)` triple (only possible when a §11
  retroactive order supersedes an earlier schedule), the higher
  `order_of_precedence` wins. In the absence of a retroactive order the
  effective-date interval is unique and this field is 10.

The reference tariff versions shipped in this extract include entries with
`order_of_precedence = 10` (the standard schedule) and, where a §11 retroactive
order applies, `order_of_precedence = 20`. Grandfathered customers under §10
consume the `order_of_precedence = 10` entry effective on their
`grandfather_date`, ignoring later rows regardless of precedence: a
precedence-20 row whose window covers the `grandfather_date` was added by a
later order and does not reprice a frozen customer.

### §3.4 `fac_index.csv`

Columns:

```
month,fac_mrcc_per_kwh
```

`month` is ISO `YYYY-MM`. `fac_mrcc_per_kwh` is a signed integer (a fuel
credit is negative). The FAC applied to a kWh is looked up by the calendar
month of that kWh, not by the billing period. See §8.

### §3.5 `holiday_calendar.json`

An array of objects:

```
[
  {"date": "YYYY-MM-DD", "name": "...", "tou_treatment": "weekend|off"},
  ...
]
```

Semantics:

- A holiday with `tou_treatment = "weekend"` re-labels every civil hour on
  that date as TOU period `weekend` for every rate class, regardless of the
  §5.1 default schedule.
- A holiday with `tou_treatment = "off"` does the same for energy and
  additionally excludes every 30-minute interval on that date from the §6
  peak-demand calculation.

### §3.6 `dst_calendar.json`

An object:

```
{
  "fall_back": [ {"date": "YYYY-MM-DD", "civil_hour_repeated": 1} ],
  "spring_forward": [ {"date": "YYYY-MM-DD", "civil_hour_skipped": 2} ]
}
```

`civil_hour_repeated = 1` means the civil hour beginning at 01:00 MST is
lived twice, giving a 25-civil-hour day. `civil_hour_skipped = 2` means the
hour beginning at 02:00 MDT does not happen, giving a 23-civil-hour day. The
period covered by this extract contains exactly one fall-back and no spring-
forward.

See §5.2 for the rule that decides which TOU label attaches to the repeated
hour and which meter-read interval owns its consumption.

### §3.7 `currency_rates.json`

An object:

```
{
  "base": "MRC",
  "rates": [
    {"date": "YYYY-MM-DD", "mrc_per_ftu": 12345},
    ...
  ]
}
```

`mrc_per_ftu` is quoted in integer mrcc per one whole FTU, so `12345` means
one FTU is exactly 123.45 MRC. Rates are dated by MST civil date. Days on
which no rate is supplied use the most recent prior rate (last-known-good).

FTU-billing customers convert only at the §12 timing (period-start rate),
never at settlement date. Retroactive §11 adjustments use the rate on the
original order date being rebilled, not the rate on the order-issue date.

### §3.8 `regulator_orders.json`

An array:

```
[
  {
    "order_id": "R-YY-NN",
    "issued_on": "YYYY-MM-DD",
    "effective_on": "YYYY-MM-DD",
    "supersedes_schedule_id": "S-YY-NN-XXXX",
    "new_schedule_id": "S-YY-RNN-XXXX or empty",
    "period_start": "YYYY-MM-DD",
    "period_end": "YYYY-MM-DD",
    "scope": "retroactive|forward_only",
    "grandfather_immune": true|false
  },
  ...
]
```

Semantics:

- `scope = "retroactive"` rewrites the schedule for consumption dated
  between `period_start` and `period_end` (inclusive). The new schedule
  entry appears in `tariff_schedule.csv` with `order_of_precedence = 20`.
  A retroactive order adds a retroactive adjustment line (§11) to each
  bill it touches; the current period's charges are not recomputed.
- `scope = "forward_only"` is declared active from `effective_on` onward.
  It changes bill amounts only when `new_schedule_id` names a published row
  in `tariff_schedule.csv`; an empty `new_schedule_id` is an active
  declaration with no monetary effect yet. If `effective_on` is later than
  the settlement period end, the order does not touch this extract.
- `grandfather_immune = true` means the order rewrites the rate even for
  §10 grandfathered customers. `false` means grandfathered customers keep
  their frozen schedule and the order does not apply to them.
- `new_schedule_id` is empty for a `forward_only` order whose replacement
  row is not yet published.
- `issued_on` is only informational; the effective bound is `effective_on`.

An order whose `period_start`/`period_end` falls entirely outside FY2025 is
still listed for record-keeping but has no effect on this period.

### §3.9 `net_metering_bank.csv`

Columns:

```
customer_id,balance_kwh_start_of_period,last_true_up_date
```

`balance_kwh_start_of_period` is a signed integer quoted in thousandths of
a kWh (`250500` is 250.500 kWh). A positive value is credit the customer
holds against future consumption. A negative value offers no §7.3 credit,
produces no §7.2 payout or forfeit, and is counted in §14.5
`customers_with_negative_nmb_start`. `last_true_up_date` is the FY
true-up date the balance was last reset on (§7.2). Only solar-enrolled
customers appear in this file; non-solar customers implicitly have a zero
balance and are not listed.

### §3.10 `service_tickets.json`

An array:

```
[
  {
    "ticket_id": "T-####",
    "customer_id": "C####",
    "event_type": "move_in|move_out|rate_class_migration",
    "effective_date": "YYYY-MM-DD",
    "new_rate_class": "RES|COM|IND or empty",
    "note": "..."
  },
  ...
]
```

Semantics:

- `move_in` - service begins on `effective_date` at 00:00 MST. Consumption
  before that date is not the customer's.
- `move_out` - service ends at 24:00 MST on `effective_date`. Consumption
  after is not the customer's.
- `new_rate_class` is empty for `move_in` and `move_out` tickets.
- A move_in or move_out prorates the customer charge by service days
  (service days times the monthly charge divided by 31), half-up rounded
  once at the end; a split under §9 or §10 is part of the same single
  rounding.
- `rate_class_migration` - the customer's rate class changes to
  `new_rate_class` at 00:00 MST on `effective_date`. Consumption on and
  after that date is bucketed under the new class's §5.1 TOU windows and
  billed under the new class's tariff rows (§10 grandfathering is
  suspended after a migration).

A customer with no ticket in this file is present for the whole period at
the class stated in `customers.csv`.

### §3.11 `meter_reads.csv`

Columns:

```
read_id,customer_id,channel,read_timestamp,register_reading_kwh
```

- `read_id` - sequence, format `MR-######`.
- `channel` - 1-indexed channel number bounded by
  `premise.meter_channel_count`.
- `read_timestamp` - ISO 8601 `YYYY-MM-DDTHH:MM:SS`. Always in Meridian
  civil time; the two 01:xx-MST hours on the §5.2 fall-back day are
  disambiguated by ordering (§4).
- `register_reading_kwh` - non-negative decimal number with up to three
  fractional digits, matching the customer's meter-class capacity. Reads
  from a `mech5` meter show fewer than 99999.999; reads from a `hybrid6`
  fewer than 999999.999. A subsequent read that is numerically lower than
  its predecessor on the same channel indicates a §4.1 rollover.

A channel normally carries one read on or before its service start date
and one on or after its service end date. A channel that lacks either is a
§15.4 missing boundary read. Two reads with the same timestamp on one
channel are a §15.3 duplicate.

### §3.12 `demand_intervals.csv`

Columns:

```
customer_id,channel,interval_start,demand_kw
```

- `interval_start` - timestamp aligned to 00 or 30 past the hour. Every
  30-minute civil interval is represented for the customer. Two special
  conventions apply:

  - **DST sentinel `T25:00:00` / `T25:30:00`.** The §5.2 fall-back day
    lives 01:00 twice. The FIRST occurrence uses the ordinary `T01:00:00`
    and `T01:30:00` timestamps. The SECOND occurrence uses `T25:00:00`
    and `T25:30:00` on the same civil date. The `T25:xx:xx` form is a
    MIGC operational convention that disambiguates the repeat hour; it
    is not a valid civil clock reading. A decoder must treat `T25:00:00`
    and `T25:30:00` intervals as belonging to the civil date in the
    prefix and as occurring in civil order strictly AFTER the ordinary
    `T23:30:00` interval of that date.
  - **String sort order.** Because civil-time ordering aligns with
    lexicographic sort of the raw `interval_start` string (given the
    T25 sentinel), `interval_start` string comparison is a valid civil
    ordering. §6.2's "later interval_start wins" tie-break is decided
    on that string comparison.

- `demand_kw` - non-negative decimal, three fractional digits.

Only COM and IND customers appear in this file. RES customers have no
demand charge component in this period.

## §4. Consumption derivation

For each customer channel, sort the customer's reads on that channel by
`read_timestamp` (after §15.3 duplicate resolution) and use every
consecutive pair of reads. Only the consumption that the interpolation
below places in civil hours inside `[service_start 00:00, service_end
24:00)` is the customer's, where:

- `service_start` = `max(period_start, move_in_effective_date)`.
- `service_end` = `min(period_end, move_out_effective_date)`.

Consumption for consecutive reads `(read_a, read_b)` is:

```
consumption_kwh = register_delta(read_a, read_b)
```

The delta accounts for §4.1 meter rollover. When multiple channels exist,
sum the per-channel per-interval consumption before bucketing.

Consumption within an inter-read gap must be redistributed to civil hours
by linear interpolation of elapsed civil seconds: each civil hour (or part
of an hour) inside the gap receives the gap's delta times its seconds in
the gap, divided by the gap's total civil seconds. The DST-repeated hour on
the fall-back day counts as two civil hours for the purpose of this
interpolation. Consumption that falls after a channel's last read or before
its first read is not counted, except as §15.4 provides.

### §4.1 Meter rollover semantics

Let `max_register(meter_class)` denote:

- `mech5` - 99999.999
- `hybrid6` - 999999.999
- `smart7` - 9999999.999

For consecutive reads `r_a`, `r_b`:

- If `r_b.register_reading_kwh >= r_a.register_reading_kwh`:
  `delta = r_b - r_a`.
- Otherwise a rollover happened:
  `delta = (max_register + 0.001) - r_a + r_b`.
  The `+ 0.001` is the increment beyond the maximum recorded value that a
  register visits before wrapping to zero.

Rollover applies at the individual channel level. Do not sum channels before
detecting rollover.

A read whose implied consumption rate is unusually high is not a rollover
error by itself; the data-quality report flags it under §15.2.

## §5. Time-of-use bucketing

Each civil hour of the period is assigned exactly one TOU label per rate
class. The consumption §4 interpolates into a civil hour is bucketed into
`peak`, `shoulder`, `night`, or `weekend` by the label of that hour under
the rate class the customer holds on that civil date.

### §5.1 TOU windows per rate class

The following bands apply to every civil weekday (Mon-Fri) that is not
declared a §3.5 holiday. Times are inclusive-exclusive intervals in MST.

| Rate class | Peak | Shoulder | Night |
|------------|------|----------|-------|
| RES | 16:00-21:00 | 07:00-16:00 and 21:00-23:00 | 23:00-07:00 |
| COM | 12:00-18:00 | 08:00-12:00 and 18:00-22:00 | 22:00-08:00 |
| IND | 10:00-20:00 | 06:00-10:00 and 20:00-23:00 | 23:00-06:00 |

For every civil Saturday and Sunday (regardless of rate class), and for
every §3.5 holiday hour (regardless of rate class), the TOU label is
`weekend`.

A rate-class migration ticket (§3.10) rebuckets consumption on and after
the migration date under the new class's schedule. The migration does not
affect consumption before its effective date.

### §5.2 DST cutover: the 25-hour day

On the fall-back date the civil hour beginning at 01:00 MST is lived twice.
The first occurrence is labelled by the ordinary §5.1 schedule for that
civil date. Because the fall-back always occurs on a Sunday in MIGC (see
the shipped `dst_calendar.json` for the actual date), the first 01:00
hour resolves to `weekend` for RES, COM, and IND under §5.1's
Saturday/Sunday rule.

The second occurrence is always labelled `night` for RES and IND, and
`weekend` for COM. This overrides §5.1's Saturday/Sunday rule for RES and
IND on the fall-back Sunday only (per the MIGC ruling of 2024-06-11); for
COM the second 01:00 hour keeps the `weekend` label §5.1 already assigned
to the day. The net effect on a fall-back day with no holiday reclassifier
is 25 civil hours: 24 hours labelled `weekend` plus one extra hour labelled
`night` for RES and IND, or 25 hours labelled `weekend` for COM.

Consumption within the first and second 01:00 hours is allocated by §4's
elapsed-civil-seconds interpolation, treating the day as 25 hours long.

### §5.3 Holiday reclassification

Holidays with `tou_treatment = "weekend"` re-label every hour of that
civil date as `weekend` for TOU purposes but leave that date's 30-minute
intervals eligible for §6 peak-demand consideration.

Holidays with `tou_treatment = "off"` re-label the whole date as `weekend`
for TOU purposes AND exclude every 30-minute interval on that date from §6
peak-demand consideration.

## §6. Demand charge

Only COM and IND customers pay a demand charge in this period.

### §6.1 Peak interval identification

Let `intervals` be the customer's 30-minute rows from `demand_intervals.csv`
whose `interval_start` civil date is within the customer's `service_start`
to `service_end` range (§4).

Sum channels for the same `interval_start` timestamp when the premise has
`meter_channel_count > 1`. The interval demand is the summed kW.

The Declared Demand Component (DDC) is the maximum interval demand across
all eligible intervals, after §6.2 exclusions.

The demand charge is `DDC_kw * demand_rate_mrcc_per_kw`, rounded to
integer mrcc by half-up (§13). The `demand_rate_mrcc_per_kw` comes from
the `tou_period = *` row of the customer's effective tariff schedule at
the DDC-interval date, respecting §10 grandfathering and §11 retroactive
orders.

### §6.2 Tie-break and holiday exclusion

Before selecting the max, apply these filters in order:

1. **Holiday exclusion.** Drop every 30-minute interval whose civil date
   is in `holiday_calendar.json` with `tou_treatment = "off"`. These
   intervals are ineligible for peak-demand regardless of demand value.
2. **Fall-back cutover ambiguity.** On the §5.2 fall-back date, the two
   01:00 hours are represented by two 30-minute rows each, four rows total.
   Both hours are eligible for demand consideration.

Then choose the eligible interval with the highest `demand_kw`. If two or
more intervals tie exactly on `demand_kw`, break the tie by choosing the
one with the LATER `interval_start` timestamp. The MIGC ruling of 2024-04-02
established that the later occurrence carries the operational meaning
because it reflects the customer's most recent capability draw.

## §7. Net metering

### §7.1 Net-of-production reads, and the bank as period-start credit

Every solar-enrolled customer's meter reads are already NET of their own
solar generation: the register advances only when the customer imports
from the grid in excess of what they exported to it. In-period solar
export therefore contributes no additional signal to this extract; the
figure that carries the customer's pre-period accumulated credit is the
`balance_kwh_start_of_period` value in `net_metering_bank.csv` (§3.9).

The reconciler treats that value as a lump-sum kWh credit available at
the start of the period. It is drawn down against the customer's
in-period consumption per §7.3. Any residue survives to §7.2's fiscal
true-up.

### §7.2 Fiscal true-up

The MIGC FY ends October 31. The billing period covered by this extract
ends on October 31. On October 31 at 24:00 MST the net-metering bank
true-up fires:

- For a RES solar customer, `nmb_kwh_end` (the positive residual, if any)
  is paid out at the FY avoided-cost rate of 4 mrcc per kWh, credited
  on the customer's bill (it reduces the bill total) and reported as
  `net_metering.avoided_cost_payout_mrcc`, and the bank is set to zero.
- For a COM or IND solar customer, the positive residual is forfeited:
  no payout, but the bank is still set to zero, and the bill records
  `net_metering.avoided_cost_payout_mrcc = 0` and
  `net_metering.forfeited_kwh` equal to the residual.

The RES-versus-COM/IND treatment is selected from the rate class held at
the true-up instant, after applying any §3.10 migration effective on or
before October 31. It is not selected from the original class in
`customers.csv`.

The true-up date is fixed at October 31 24:00 MST regardless of any move-
in / move-out ticket. A customer whose service ended on October 20 still
experiences the true-up on their October bill.

`credit_kwh_carried_forward` is the credit a customer still holds once
this section's true-up has run, in thousandths of a kWh. The true-up
clears every positive balance, as a payout for a RES customer and as a
forfeit for a COM or IND customer, so a customer whose bank was positive
at period start carries nothing forward. A negative balance is a debit
and not a credit: §3.9 gives it no §7.3 draw and no §7.2 payout or
forfeit, so it carries nothing forward either, and it is reported only
through the §14.5 field `customers_with_negative_nmb_start`.
`credit_kwh_carried_forward` is therefore 0 for every customer in this period, and
`net_metering_credit_kwh_carried_forward_total` is 0.

### §7.3 Order of application

Within a bill the sequence is:

1. Compute in-period consumption per §4 and bucket into TOU labels per §5.
2. Apply the bank: draw up to `balance_kwh_start_of_period` off the
   bucketed consumption in the order `peak -> shoulder -> night -> weekend`.
   Each label is drawn to zero before moving to the next. The drawn kWh
   are removed from the taxable base; the remaining balance carries into
   step 4.
3. Compute the energy charge on the reduced TOU buckets.
4. Apply the §7.2 fiscal true-up to whatever bank balance is left after
   step 2.

The rate paid on the drawn-down kWh is implicitly the label's rate, and
the customer's `energy_charge_mrcc` reflects that. When a label's kWh are
billed at more than one rate (a §9 or §10 split), the draw reduces each
rate's share of that label in proportion to its kWh.

## §8. Fuel Adjustment Charge

The FAC is a per-kWh adder that changes by calendar month. It is applied
after §7 net-metering banking (so only the kWh that remain charged after
NMB offset carry the adder) and BEFORE any §11 retroactive-order rebill.

For the current billing period (October 2025) the applicable FAC is
`fac_index.csv[month = "2025-10"]`. For any §11 retroactive order rebilling
a prior period, the FAC used is the one for the ORIGINAL month being
rebilled, not the current month.

## §9. Rate-class migration

A `rate_class_migration` ticket (§3.10) creates a split-billing situation.
Call the migration date `d_m`.

- Consumption on civil dates in `[service_start, d_m - 1 day]` is bucketed
  under the ORIGINAL rate_class's TOU windows and billed under the ORIGINAL
  tariff rows.
- Consumption on and after `d_m` is bucketed under the NEW rate_class's
  TOU windows and billed under the NEW tariff rows.
- The customer charge (`tou_period = *` row) is prorated by service days:
  `original_class_charge * (d_m - service_start).days / period_length_days`
  plus `new_class_charge * (service_end - d_m + 1).days / period_length_days`,
  half-up rounded to integer mrcc at the end.
- The demand charge is computed once, over the whole eligible interval
  set, at the demand rate of the class the customer belongs to on the
  DDC interval's civil date.
- Any §10 grandfather freeze the customer held is broken at `d_m`. On
  and after `d_m` the customer is billed at the current schedule for the
  new class regardless of any grandfather_expires_on date.

At most one `rate_class_migration` ticket exists per customer per period.

## §10. Grandfather clauses

A customer with `grandfather_flag = true` in `customers.csv` is locked to
the tariff schedule that was effective on their `grandfather_date`. On and
after `grandfather_expires_on` the customer reverts to the current
schedule.

If `grandfather_expires_on` falls strictly inside the billing period,
apply pro-rata split:

- Consumption on dates in `[service_start, grandfather_expires_on - 1 day]`
  is billed under the grandfathered schedule.
- Consumption on and after `grandfather_expires_on` is billed under the
  current schedule.

The customer charge, when both halves apply, is prorated by service days
in each half, half-up rounded at the end.

A §11 retroactive order with `grandfather_immune = false` does not touch
grandfathered customers. A §11 order with `grandfather_immune = true`
does touch them, applying to the appropriate half of a split period.

## §11. Retroactive regulator orders

For each order in `regulator_orders.json` whose `scope = "retroactive"`:

1. Determine the affected customers: every customer whose consumption on
   any civil date in `[period_start, period_end]` fell under the
   superseded schedule, which means every customer whose `customers.csv`
   `rate_class` is the superseded row's rate class, less any §10
   grandfathered customer the order does not touch. In this extract,
   `period_start` and `period_end` are the ORDER's own dates, not the
   billing period's.
2. For each such customer, recompute their bill for the affected dates
   using the new schedule. Compare against the amount originally billed
   at the old schedule.
3. The difference (new minus old) is the retroactive adjustment. It is
   an ADDITIONAL LINE on the current bill, not a replacement of any
   charge on the current bill.

The `policy_audit.json` artifact (§14.3) records every retroactive
adjustment. A customer with no retroactive adjustment does not appear
in that section.

The originally-billed amount for a prior month is derived by running
the reconciliation algorithm against the ORIGINAL schedule but with
"assumed prior" transaction quantities, because the original meter
reads and demand intervals for the retro period are NOT shipped in
this extract. The MIGC procedural rule of 2024-11-18 defines the
"assumed prior" quantities as follows, applied to every retroactively
rebilled customer regardless of meter class:

- Assumed prior DDC is the customer's current-period DDC, unchanged.
- Assumed prior energy consumption is the customer's current-period
  total kWh scaled by
  `(days_in_retro_period / days_in_current_period)`, where
  `days_in_current_period` is 31 for every customer.
  The scaling is applied to the customer's total kWh; per-TOU-bucket
  redistribution follows the SAME PROPORTIONS as the current period
  (so if 30% of current-period kWh were in `peak`, the assumed prior
  `peak` kWh is 30% of the scaled total).
- Assumed prior grid_import equals assumed prior consumption; the
  net-metering bank does not apply to the retroactive rebill (§7 is
  computed only against the current period).

Retroactive adjustments use the FAC of the ORIGINAL retro month per §8.
An order does not change the FAC, so the FAC term is the same on both
sides and cancels in the difference.

Compare-against-old: the OLD schedule for the retro month is the
highest-precedence row covering the retro dates other than the row the
order introduces (here the `order_of_precedence = 10` row). The NEW
schedule is the highest-precedence row once the order's row is included
(order_of_precedence = 20). The old and new amounts are each rounded
half-up per TOU label for energy, and once for demand, before the
difference is taken. Both rows are read for the customer's `customers.csv`
rate class on the retro dates, so a §10 freeze the customer held during
the retro period does not change which two rows are compared.

## §12. Currency conversion (MRC and FTU)

Customers with `billing_currency = MRC` are billed in MRC. All internal
computation is in integer mrcc. Only the final artifact values quoted in
MRC.

Customers with `billing_currency = FTU` have their bill computed in
integer mrcc as usual, then converted to integer ftuc using the
`mrc_per_ftu` rate on the period start date, 2025-10-01. Because
`mrc_per_ftu` is quoted as mrcc per whole FTU, the conversion is:

```
amount_ftuc = round_half_up(amount_mrcc * 100 / mrc_per_ftu)
```

Rounding is half-up to integer ftuc.

A §11 retroactive adjustment on an FTU customer uses the
`mrc_per_ftu` rate on the FIRST date of the ORIGINAL retro period, NOT
the current period_start. So the bill without its §11 lines converts at
the period-start rate, each §11 line converts at its own rate, each
conversion is rounded half-up on its own, and `bill_total_ftuc` is their
sum.

Payouts and forfeitures under §7 are computed in mrcc first, then
converted per the same rules.

## §13. Rounding rules

- All internal energy and demand computations use exact arithmetic. The
  kWh input is a decimal with up to three fractional digits; the
  mrcc/kWh rate is an integer. For each customer and TOU label, accumulate
  the exact energy value `sum(kwh_h * rate_h)` across the label's civil
  hours, using the rate in force for each hour. After any §7.3 proportional
  reduction, round that label's accumulated value half-up once to integer
  mrcc. The customer's `energy_charge_mrcc` is the sum of those rounded
  label charges. Do not round per hour or per tariff-rate segment.
- Each customer-level kWh field written to an artifact (`energy_kwh`,
  `net_metering.credit_kwh_carried_forward`, and
  `net_metering.forfeited_kwh`) is the customer's exact quantity rounded
  half-up once to whole thousandths of a kWh. A customer's `fac_mrcc` and
  `net_metering.avoided_cost_payout_mrcc` are computed on exact kWh and
  rounded once.
- Half-up rounding: when the fractional part is exactly 0.5, round
  toward positive infinity. When the fractional part is exactly -0.5
  on a negative amount (rare, only in §11 refunds), round toward
  positive infinity as well, so -1.5 rounds to -1.
- Customer-level rounding: each customer-level rounding target listed in
  §14 is rounded once, at the point named. Do not compound customer-level
  roundings; carry full-precision intermediate values. Interpolated
  quantities are rational, so use exact arithmetic (for example Python
  `fractions.Fraction`); floating-point is not acceptable. The summary,
  rate-class, and regional totals are not separate rounding targets: they
  are arithmetic sums of the published per-customer integers under §14.1.

## §14. Output artifact schemas

Every artifact is written to `/app/out/<name>.json` (except the
reusable script). Every JSON file is serialised with `sort_keys=True`,
`separators=(",", ": ")` conceptually - see §16.

The ten declared artifacts are:

1. `reconcile.py` - the reusable script, described in the instruction.
2. `summary.json` - corpus-wide totals.
3. `rate_class_residential.json` - RES rate-class rollup.
4. `rate_class_commercial.json` - COM rate-class rollup.
5. `rate_class_industrial.json` - IND rate-class rollup.
6. `region_meridian_north.json` - Meridian North regional rollup.
7. `region_meridian_south.json` - Meridian South regional rollup.
8. `region_meridian_east.json` - Meridian East regional rollup.
9. `policy_audit.json` - every rule-application record.
10. `data_quality.json` - record and threshold checks.

### §14.1 `summary.json`

```
{
  "period": {
    "start": "2025-10-01",
    "end":   "2025-10-31",
    "civil_days": 31,
    "civil_hours": 745
  },
  "customer_count": <int>,
  "energy_kwh_total": <int, thousandths of a kWh; 1234567 = 1234.567 kWh>,
  "energy_charge_mrcc_total": <int mrcc>,
  "demand_charge_mrcc_total": <int mrcc>,
  "customer_charge_mrcc_total": <int mrcc>,
  "fac_mrcc_total": <int mrcc, signed>,
  "net_metering_credit_kwh_carried_forward_total": <int, thousandths of a kWh>,
  "net_metering_avoided_cost_payout_mrcc_total": <int mrcc>,
  "net_metering_forfeited_kwh_total": <int, thousandths of a kWh>,
  "retroactive_adjustment_mrcc_total": <int mrcc, signed>,
  "bill_total_mrcc": <int mrcc>,
  "bill_total_ftuc": <int ftuc>
}
```

Build every summary from the customers in its scope. `customer_count` is
the number of those customers. Every other top-level total is the arithmetic
sum of the corresponding published per-customer integer field:

- `energy_kwh_total` sums `energy_kwh`.
- `energy_charge_mrcc_total` sums `energy_charge_mrcc`.
- `demand_charge_mrcc_total` sums `demand_charge_mrcc`.
- `customer_charge_mrcc_total` sums `customer_charge_mrcc`.
- `fac_mrcc_total` sums `fac_mrcc`.
- `net_metering_credit_kwh_carried_forward_total` sums
  `net_metering.credit_kwh_carried_forward`.
- `net_metering_avoided_cost_payout_mrcc_total` sums
  `net_metering.avoided_cost_payout_mrcc`.
- `net_metering_forfeited_kwh_total` sums
  `net_metering.forfeited_kwh`.
- `retroactive_adjustment_mrcc_total` sums
  `retroactive_adjustment_mrcc`.
- `bill_total_mrcc` sums `bill_total_mrcc`, and `bill_total_ftuc` sums
  `bill_total_ftuc`.

Do not recompute or re-round a total from hidden exact quantities. In
particular, `energy_kwh_total` can differ from rounding the exact aggregate
kWh because it sums the published customer-level thousandths. Every monetary
and energy figure in every artifact is an integer; no floating-point value
appears anywhere.

`bill_total_mrcc` and `bill_total_ftuc` are the totals expressed in each
currency; a customer contributes to `bill_total_mrcc` only if their
`billing_currency = MRC`, and to `bill_total_ftuc` only if
`billing_currency = FTU`. There is no cross-conversion at the aggregate
level.

Serialisation: sorted keys, trailing newline, UTF-8.

### §14.2 Rate-class rollups

Each `rate_class_<class>.json` carries every `summary.json` key, scoped to
the customers of that class (so `bill_total_ftuc` is the FTU total of the
class's FTU customers and `customer_count` counts the class). A customer
rolls up under the `rate_class` stated in `customers.csv`, even after a
§9 migration. Apply the §14.1 published-integer summation rule only to
customers in the class. It also carries:

```
{
  ...,
  "customers": [
    {
      "customer_id": "C####",
      "premise_code": "P<number>",
      "energy_kwh": <int thousandths>,
      "energy_charge_mrcc": <int mrcc>,
      "demand_charge_mrcc": <int mrcc>,
      "customer_charge_mrcc": <int mrcc>,
      "fac_mrcc": <int mrcc, signed>,
      "net_metering": {
        "credit_kwh_carried_forward": <int thousandths>,
        "avoided_cost_payout_mrcc": <int mrcc>,
        "forfeited_kwh": <int thousandths>
      },
      "retroactive_adjustment_mrcc": <int mrcc, signed>,
      "bill_total_mrcc": <int mrcc>,
      "bill_total_ftuc": <int ftuc>
    },
    ...
  ]
}
```

The `customers` array is sorted by `premise_code` under §16.2 rule. In a
customer entry, `bill_total_mrcc` is 0 for an FTU customer and
`bill_total_ftuc` is 0 for an MRC customer.

### §14.3 `policy_audit.json`

```
{
  "grandfather_applied": [
    {"customer_id": "C####", "grandfather_date": "YYYY-MM-DD",
     "expires_on": "YYYY-MM-DD", "prorata_split_at": "YYYY-MM-DD" or null},
    ...
  ],
  "rate_class_migrations": [
    {"customer_id": "C####", "migration_date": "YYYY-MM-DD",
     "from_class": "...", "to_class": "..."},
    ...
  ],
  "retroactive_orders_applied": [
    {"order_id": "R-YY-NN", "customer_id": "C####",
     "adjustment_mrcc": <int, signed>},
    ...
  ],
  "holiday_reclassifications": [
    {"date": "YYYY-MM-DD", "name": "...", "tou_treatment": "..."},
    ...
  ],
  "dst_cutover_applied": {
    "date": "YYYY-MM-DD",
    "civil_hours_in_day": 25 or 23 or 24
  }
}
```

Every list is sorted:

- `grandfather_applied` by `customer_id` ascending.
- `rate_class_migrations` by `customer_id` ascending.
- `retroactive_orders_applied` by (`order_id`, `customer_id`) ascending
  lexicographic - `order_id` first, then `customer_id`.
- `holiday_reclassifications` by `date` ascending.

`grandfather_applied` lists every `grandfather_flag = true` customer.
`prorata_split_at` is the date the freeze ends (`grandfather_expires_on`, or
an earlier §9 migration date) when that date falls after the period's
first day and on or before its last day, and `null` otherwise.
`retroactive_orders_applied` holds one entry per order and customer with a
non-zero adjustment, quoted in mrcc for every customer.

### §14.4 Regional rollups

Same shape as the rate-class rollup, but scoped to premises in that
region. Apply the §14.1 published-integer summation rule only to customers
in the region. Customer array again sorted by §16.2.

### §14.5 `data_quality.json`

```
{
  "meter_read_count": <int>,
  "demand_interval_count": <int>,
  "customers_with_negative_nmb_start": <int>,
  "customers_with_missing_read_at_service_start": <int>,
  "customers_with_missing_read_at_service_end": <int>,
  "high_variance_reads_flagged": <int>,
  "service_tickets_by_type": {
    "move_in": <int>,
    "move_out": <int>,
    "rate_class_migration": <int>
  },
  "regulator_orders_active_this_period": <int>,
  "regulator_orders_out_of_period_declared": <int>,
  "duplicate_read_timestamps_flagged": <int>
}
```

`meter_read_count` and `demand_interval_count` count every row of their
files, duplicates and every channel included. The two missing-read fields
count customers, not channels.

`regulator_orders_active_this_period` counts declarations in
`regulator_orders.json` that are active for this settlement: every order
with scope `retroactive`, because §11 adds its adjustment line to the
current bill, together with every order with scope `forward_only` whose
`effective_on` falls on or before the period end. A forward-only order
with an empty `new_schedule_id` is included in this declaration count even
though §3.8 gives it no monetary effect yet.
`regulator_orders_out_of_period_declared` counts the orders with scope
`forward_only` whose `effective_on` falls after the period end, which
this period's bills never reach. The `period_start` and `period_end` an
order declares for itself do not enter either count: a retroactive order
is active because of the adjustment it creates, not because its own dates
overlap the billing period.

## §15. Data quality contract

### §15.1 Referential integrity

Every `customer_id` in every transaction file must map to
`customers.csv`. Every `premise_code` in `customers.csv` must map to
`premises.csv`. A customer whose premise does not map is invalid, and all
transactions for that customer are orphan records. A referential-integrity
failure is a data-quality event, but the reconciler MUST still produce an
output: drop the invalid customer and every orphan transaction from every
bill, rollup and flag, including `service_tickets_by_type`, while the
§14.5 raw row counts (`meter_read_count`, `demand_interval_count`) still
include orphan meter-read and demand-interval rows.

### §15.2 High-variance reads

A read whose implied rate (the §4.1 delta from the prior read divided by
the §4 civil seconds since it) is strictly greater than 20 times the
median of all inter-read rates on the same channel is flagged as
high-variance (the median of an even count is the mean of the two middle
values). The read is NOT excluded from computation; it is counted in
`high_variance_reads_flagged`. Rates are taken after §15.3 duplicate
resolution.

### §15.3 Duplicate timestamps

Two reads on the same `(customer_id, channel)` with identical
`read_timestamp` are flagged as duplicate. Retain only the read with
the highest `register_reading_kwh` (rollover-aware: the one with the
greatest §4.1 forward distance from the retained read before it, or the
numerically highest when it is the channel's first read); count each
discarded read in `duplicate_read_timestamps_flagged`.

### §15.4 Missing boundary reads

If a channel has no read whose civil date is on or before
`service_start`, or none whose civil date is on or after `service_end`,
count the customer in the respective §14.5 field. In that case,
extrapolate across the missing boundary: the rate of the nearest
inter-read gap on that channel (its §4.1 delta divided by its §4 civil
seconds) is extended from `service_start 00:00` up to the channel's first
read, or from its last read up to `service_end 24:00`, and that
consumption is interpolated into civil hours exactly as §4 does. The
estimate is not rounded; it is used for consumption computation and the
flag is still raised.

## §16. Serialization contract

### §16.1 JSON serialisation

Every JSON artifact is written with:

- `sort_keys = True`
- `separators = (",", ": ")` (a JSON encoder's default when
  `indent = 2` is used with sorted keys)
- A trailing newline after the closing brace
- UTF-8, LF line endings, no BOM

The specific Python invocation the oracle uses is:

```
json.dump(data, fh, sort_keys=True, indent=2)
fh.write("\n")
```

Any equivalent producing byte-identical output is acceptable. The
byte-identical requirement applies to every artifact.

### §16.2 List ordering

Customer lists inside every artifact are sorted by `premise_code`
NUMERIC suffix ASCENDING. The sort key is `int(premise_code[1:])`, so
`P9` comes before `P12` and `P12` before `P101`, even though a string
comparison would put `P101` first.

### §16.3 Determinism

Running `python3 /app/out/reconcile.py DATA_DIR OUT_DIR` twice on the
same inputs produces byte-identical outputs.

### §16.4 Persistent session protocol

The reusable program also supports:

```
python3 /app/out/reconcile.py --session OUT_DIR
```

In this mode standard input is NDJSON. Each non-empty input line is one JSON
object with exactly two string fields:

```
{"data_dir":"/path/to/complete/snapshot","turn_id":"opaque-id"}
```

`data_dir` contains a complete independent copy of the twelve data files in
§2. For each command, discard all derived state from earlier commands, read
only that command's snapshot, and fully replace all nine JSON reports in the
shared `OUT_DIR`. After every artifact has been closed, write exactly one
acknowledgement object on one standard-output line and flush it:

```
{"status":"ok","turn_id":"opaque-id"}
```

The acknowledgement carries the input `turn_id` unchanged. Emit no other
standard-output lines. Continue until input EOF, then exit with status zero.
Returning to a previously processed snapshot must reproduce all nine files
byte for byte; intervening turns cannot influence it. Session mode does not
change any settlement rule, output shape, serialization rule, or file access
boundary.

## §17. Worked example: customer C0004

Customer C0004 is a residential solar-enrolled customer at premise
P27 in Meridian North. Meter class `hybrid6`. Grandfather flag
`false`. Currency MRC.

Suppose, for illustration only and with no service ticket, the meter
reads are:

```
MR-000041, C0004, 1, 2025-09-30T23:00:00, 128456.780
MR-000106, C0004, 1, 2025-10-15T09:30:00, 128712.340
MR-000175, C0004, 1, 2025-10-31T23:00:00, 129001.150
```

Consumption:

- Interval 1 (Sep 30 23:00 -> Oct 15 09:30): 128712.340 - 128456.780 =
  255.560 kWh. Only the portion inside October counts. Elapsed civil
  seconds from Oct 1 00:00 to Oct 15 09:30 = 14 days 9h 30m = 1,243,800
  seconds; total interval seconds = 14 days 10h 30m = 1,247,400
  seconds. October's share = 255.560 * 1,243,800 / 1,247,400 =
  254.822453... kWh, carried exactly (never rounded mid-calculation).
- Interval 2 (Oct 15 09:30 -> Oct 31 23:00): 129001.150 - 128712.340 =
  288.810 kWh, entirely in October. It spans the fall-back day, so its
  civil seconds include the repeated 01:00 hour.

October total: 543.632453... kWh, written as `energy_kwh = 543632`.

Bucketing that consumption into RES TOU windows, civil hour by civil hour:

- Weekend hours in October 2025 (Saturdays and Sundays, plus any §5.3
  weekend-relabelled or off holiday) - use an integrator over civil
  seconds, so the weekend bucket picks up the interval-share for those
  days. The DST fall-back Oct 26 (Sunday) contributes 25 civil hours
  instead of 24; per §5.2 the first 01:00 hour is `weekend` (Sunday
  rule) and the second 01:00 hour is `night` for a RES customer.
- Peak hours are 16:00-21:00 weekdays: five peak hours per non-holiday
  weekday, and the count of non-holiday weekdays is derived from the
  shipped `holiday_calendar.json` per §5.3, since a holiday with
  `tou_treatment = "weekend"` or `"off"` relabels its whole date away
  from the ordinary weekday schedule.

The rest of the worked example (net-metering banking, FAC application
and the fiscal true-up) follows §7 and §8. A residential customer is not
touched by either shipped retroactive order, and an MRC customer needs no
§12 conversion.

## §18. Provenance

- Extract dated 2025-11-05.
- Schema version 4.0, ratified by MIGC on 2025-10-28.
- This version adds complete-snapshot session processing; it does not define
  delta extracts or partial-table inheritance.
