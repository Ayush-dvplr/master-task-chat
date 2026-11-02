# Pilotage Tariff Circular PC-7

Applies to the pilot stations North, South, West and East for boardings from 2026-07-01 00:00 to
2026-09-30 23:59.

## 1. Definitions and the movements log

- Times are port local time, written `YYYY-MM-DD HH:MM`, to the minute.
- `pilot_movements.log` holds one record per line, fields separated by single spaces:
  - `YYYY-MM-DD HH:MM BOARD <station> <visit_id> <vessel_id> draft_dm=<integer> tugs=<integer>`,
    optionally followed by ` assist=<integer>`
  - `YYYY-MM-DD HH:MM RELEASE <visit_id>`
  - `YYYY-MM-DD HH:MM CANCEL <station> <visit_id> <vessel_id>`, a cancelled booking
    (`station_notices.md`)
  - `YYYY-MM-DD HH:MM NOTE <station> <free text>` lines are station diary notes, not records.
- `<station>` is one of North, South, West, East; `draft_dm`, `tugs` and `assist` are whole numbers.
- A BOARD line may give the draft as `draft_m=<metres with two decimals>` in the place of
  `draft_dm=<integer>`. Its `draft_dm` is the draft in metres rounded up to the next 0.1 m, in
  decimetres. Example on invented values: `draft_m=8.21` gives draft_dm 83; `draft_m=8.20` gives 82.
- A visit is one pilotage act: the BOARD line and the RELEASE line that carry the same visit id, or a
  CANCEL line. Its station, vessel, draft (`draft_dm`, decimetres), tug count and assist minutes come
  from the BOARD line; a visit without `assist` has 0 assist minutes.
- A visit id is on at most one accepted BOARD or CANCEL line and at most one accepted RELEASE line, and
  never on both a BOARD line and a CANCEL line.
- A visit's instant is its boarding instant; a cancelled booking's instant is the time of its CANCEL
  line.

## 2. Due

The due of a visit is the sum of five lines. Each line is rounded half-even to the cent (an amount
exactly half way between two cents goes to the even cent) before it is used anywhere else.

1. tonnage line = base_per_100gt x gross_tonnage / 100 (gross tonnage from `vessel_register.tsv`)
2. draft line = draft_per_dm x excess, where excess = draft_dm - 60 when draft_dm is above 60, else 0
3. towage line = per_tug x tugs
4. assist line = 40.00 for each started 30 minutes of assist minutes
5. surcharge line = (night_factor - 1) x (tonnage line + draft line + towage line) when the visit's
   instant is at or after 22:00 or before 06:00, or falls on a holiday of the visit's station;
   otherwise 0.00. A visit at night on a holiday carries one surcharge line.

Example on invented values: base_per_100gt 2.00, gross tonnage 1,234, draft_dm 63, draft_per_dm 1.10,
no tugs, assist 31 minutes, night_factor 1.30, boarding 23:15 on an ordinary date. Tonnage 24.68,
draft 3.30, towage 0.00, assist 80.00, surcharge 0.30 x 27.98 = 8.394, rounded 8.39; due 116.37.
Half-even: 19.695 rounds to 19.70 and 19.685 rounds to 19.68.

`holidays.json` is one JSON object. Each station name maps to a list of `YYYY-MM-DD` dates that are
holidays of that station, and the key `all` maps to a list of dates that are holidays of every station.
A holiday that falls on a Sunday is also kept on the Monday after it. Example on invented values: a
station holiday on 2031-03-02, a Sunday, makes 2031-03-03 a holiday of that station too.
Example on invented values: `{"North": ["2031-01-06"], "all": ["2031-01-01"]}` makes 2031-01-01 a
holiday of every station and 2031-01-06 a holiday of North only.

### 2a. Billed minutes

- On-board minutes: the whole minutes from the boarding instant to the release instant.
- Billed minutes: the on-board minutes less the covered minutes of `exemption_policy.md`. A commercial
  vessel has no covered minutes.
- When billed minutes equal on-board minutes, the due is the sum of the five rounded lines.
- When billed minutes are 0, the due is 0.00.
- Otherwise each of the five rounded lines (the surcharge line computed from the rounded lines before
  it) is multiplied by billed minutes / on-board minutes and rounded half-even to the cent again; the
  due is the sum of the five results.
- A visit's period, tariff and surcharge test do not depend on its billed minutes.
- A cancelled booking has 0 on-board and 0 billed minutes; its due is set in `station_notices.md`.

## 3. Listed values

A station's tariff takes its coefficients from these lists.

| coefficient | listed values |
|---|---|
| base_per_100gt | 1.80, 1.95, 2.10, 2.25, 2.40 |
| draft_per_dm | 2.50, 3.00, 3.50, 4.00 |
| night_factor | 1.25, 1.40, 1.50 |
| per_tug | 35.00, 50.00, 65.00 |

## 4. Periods

`station_notices.md` lists tariff notices, at most one per station, as table rows
`| <station> | <notice_date> | <coefficients> |`, where `<coefficients>` names coefficients of section 3
separated by commas. A station's first period starts at 2026-07-01 00:00. A notice starts a new period
at 00:00 on its notice date. A period is named by its start date (`period_start`, `YYYY-MM-DD`). A
visit belongs to the period of its station that holds its instant.

## 5. Recovering a tariff

A paid invoice counts here when `output_contract.md` section "Rejected records" does not reject it. A
station's tariff gives each coefficient one listed value in each of its periods; a coefficient that the
station's notice does not name has the same value in both periods. The tariff reproduces every accepted
paid invoice of the station, each with the values of its own period, to the cent: the due of the
invoice's visit equals the paid amount. The combination of a period is the four values that such a
tariff gives the period.

## 6. Verdicts

`disputed_batch.csv` has the header `invoice_id,visit_id,station,invoice_date,billed,supersedes`;
`station` is one of the four station names and `billed` is an amount with two decimals or a whole
number of cents followed by `c` (for example `705c` is 7.05). `supersedes` is set out in
`output_contract.md`. Every recomputed due and every verdict uses the tariff recovered for that station
and period, or the station's unresolved status. An accepted disputed invoice gets one verdict:

- `billed_correctly`: billed equals the recomputed due.
- `overbilled`: billed is above the recomputed due; the refund is billed minus the recomputed due.
- `underbilled`: billed is below the recomputed due; the shortfall is the recomputed due minus billed.
- `cannot_recompute`: the station and period has no such combination, or has more than one.

A `cannot_recompute` invoice carries the reason `no listed tariff reproduces every paid invoice` when
the station and period has no such combination, and `more than one listed tariff reproduces every paid
invoice` when it has more than one. Invoices with the other verdicts carry no reason.

## 7. Paid invoice files

Each file holds the invoices paid at one station; `invoice_date` is the issue date and `amount` the paid
amount with two decimals.

- `paid_north.csv`: header `invoice_id,visit_id,invoice_date,amount`, one invoice per line.
- `paid_south.jsonl`: one JSON object per line with the keys `invoice_id`, `visit_id`,
  `invoice_date`, `amount` (a string).
- `paid_west.txt`: fixed width, no header; columns 1-10 `invoice_id`, 11-18 `visit_id`, 19-28
  `invoice_date`, 29-40 `amount` right aligned; text fields are padded with spaces on the right.
- `paid_east.xml`: first line `<paid_invoices station="East">`, last line `</paid_invoices>`, and between
  them one `<invoice id="..." visit="..." date="..." amount="..."/>` element per line.
