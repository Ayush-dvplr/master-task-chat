# Pilotage Tariff Circular PC-7

Applies to the pilot stations North, South, West and East for boardings from 2026-07-01 00:00 to
2026-09-30 23:59.

## 1. Definitions and the movements log

- Times are port local time, written `YYYY-MM-DD HH:MM`, to the minute.
- `pilot_movements.log` holds one record per line, fields separated by single spaces:
  - `YYYY-MM-DD HH:MM BOARD <station> <visit_id> <vessel_id> draft_dm=<integer> tugs=<integer>`
  - `YYYY-MM-DD HH:MM RELEASE <visit_id>`
  - `YYYY-MM-DD HH:MM NOTE <station> <free text>` lines are station diary notes, not records.
- `<station>` is one of North, South, West, East; `draft_dm` and `tugs` are whole numbers.
- A visit is one pilotage act: the BOARD line and the RELEASE line that carry the same visit id. Its
  station, vessel, draft (`draft_dm`, decimetres) and tug count come from the BOARD line.
- A visit's instant is its boarding instant. Every date rule in this circular reads the boarding instant.

## 2. Due

The due of a visit is the sum of four lines. Each line is rounded half-even to the cent (an amount
exactly half way between two cents goes to the even cent) before it is used anywhere else.

1. tonnage line = base_per_100gt x gross_tonnage / 100 (gross tonnage from `vessel_register.tsv`)
2. draft line = draft_per_dm x excess, where excess = draft_dm - 60 when draft_dm is above 60, else 0
3. towage line = per_tug x tugs
4. surcharge line = (night_factor - 1) x (tonnage line + draft line + towage line) when the visit's
   instant is at or after 22:00 or before 06:00, or falls on a date listed for the visit's station in
   `holidays.json`; otherwise 0.00. A visit at night on a holiday carries one surcharge line.

`holidays.json` is one JSON object: each station name maps to a list of `YYYY-MM-DD` dates.

### 2a. Billed minutes

- On-board minutes: the whole minutes from the boarding instant to the release instant.
- Billed minutes: for a commercial vessel, all on-board minutes. For a public vessel
  (`exemption_policy.md`), the on-board minutes at or after 00:00 on its `exemption_expiry` date; that
  is, from the later of the boarding instant and 00:00 on that date, to the release instant, and 0 when
  the release instant is at or before 00:00 on that date.
- When billed minutes equal on-board minutes, the due is the sum of the four rounded lines.
- When billed minutes are 0, the due is 0.00.
- Otherwise each of the four rounded lines (the surcharge line computed from the three rounded lines
  before it) is multiplied by billed minutes / on-board minutes and rounded half-even to the cent again;
  the due is the sum of the four results.
- The tariff, the surcharge test and the period are those of the boarding instant, also when the billed
  minutes start on a later date or after a later notice date.

Example on invented values: base_per_100gt 2.00, gross tonnage 1,234, draft_dm 63, draft_per_dm 1.10,
no tugs, night_factor 1.30, boarding 23:15 on an ordinary date. Tonnage 24.68, draft 3.30, towage 0.00,
surcharge 0.30 x 27.98 = 8.394, rounded 8.39; due 36.37. Half-even: 19.695 rounds to 19.70 and 19.685
rounds to 19.68.

## 3. Listed values

A station's tariff is one value from each list.

| coefficient | listed values |
|---|---|
| base_per_100gt | 1.80, 1.95, 2.10, 2.25, 2.40 |
| draft_per_dm | 2.50, 3.00, 3.50, 4.00 |
| night_factor | 1.25, 1.40, 1.50 |
| per_tug | 35.00, 50.00, 65.00 |

## 4. Periods

`station_notices.md` lists tariff notices, at most one per station, as table rows
`| <station> | <notice_date> |`. A station's first period starts at 2026-07-01 00:00. A notice starts a
new period at 00:00 on its notice date; the tariff before and the tariff from that instant are
recovered separately. A period is named by its start date (`period_start`, `YYYY-MM-DD`). A visit
belongs to the period of its station that holds its instant.

## 5. Recovering a tariff

A paid invoice counts here when `output_contract.md` section "Rejected records" does not reject it. A
station's tariff for a period is the combination of listed values that reproduces every accepted paid
invoice of that station and period to the cent: the due of the invoice's visit under that combination
equals the paid amount.

## 6. Verdicts

`disputed_batch.csv` has the header `invoice_id,visit_id,station,invoice_date,billed`; billed is an
amount with two decimals and `station` is one of the four station names. Every recomputed due and every
verdict uses the tariff recovered for that station and period, or the station's unresolved status. An
accepted disputed invoice gets one verdict:

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
