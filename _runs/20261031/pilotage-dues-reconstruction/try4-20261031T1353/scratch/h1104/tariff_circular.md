# Pilotage tariff circular, third quarter 2026

The harbour authority's pilot stations North, South, West and East bill every pilot
boarding under this circular. The review covers boardings from 2026-07-01 00:00 to
2026-09-30 23:59, harbour local time.

## 1. Definitions

`pilot_movements.log` holds one line per event, in time order:

    YYYY-MM-DD HH:MM ORDER <station> <visit_id> draft=<m.cc>
    YYYY-MM-DD HH:MM BOARD <station> <visit_id> <vessel_id> draft=<m.cc> tugs=<n>[ assist=<minutes>]
    YYYY-MM-DD HH:MM RELEASE <visit_id>

Lines that start with `NOTE` are remarks of the duty pilot and are not records.

- A visit is one BOARD line. Its station is the station named on it, and its instant is
  the time on it. The ORDER line of a visit is the agent's pilot order, with the draft the
  agent declared; the RELEASE line is the pilot leaving the vessel.
- A visit is known when its BOARD line is in the log and its vessel has a line in
  `vessel_register.tsv`.
- `draft` on the BOARD line is the draft the pilot measured, in metres to the centimetre.
  `tugs` is the number of tugs ordered. `assist` is the minutes of tug assistance; a line
  without it had none.
- `vessel_register.tsv`, `agents.tsv` and `stations.tsv` are described in
  `exemption_policy.md`.

## 2. The due of a visit

A due is the sum of five lines. Every line is worked in cents and rounded half to even to
a whole cent (19.695 becomes 19.70 and 19.685 becomes 19.68).

1. Tonnage: `per_100_tonnes` x the tonnage of the vessel / 100.
2. Draft: `per_tenth` x (tenths - 60) when that is positive, else 0.00, where tenths is the
   draft of the visit in tenths of a metre, a part tenth counting as a whole one.
3. Towage: `per_tug` x tugs.
4. Assist: 40.00 for each 30 minutes of assist, a part block counting as a whole one.
5. Surcharge: (`surcharge_factor` - 1) x (tonnage + draft + towage + assist), when the time
   of the visit falls inside surcharge hours or on a holiday; else 0.00. Hours run from a
   start up to, not including, an end, and pass midnight when the end is earlier.

The due of a visit that is exempt under `exemption_policy.md` is 0.00.

## 3. Listed values

A tariff is one value from each row.

| coefficient | listed values |
|---|---|
| per_100_tonnes | 1.80, 1.95, 2.10, 2.25, 2.40 |
| per_tenth | 2.50, 3.00, 3.50, 4.00 |
| surcharge_factor | 1.25, 1.40, 1.50 |
| per_tug | 35.00, 50.00, 65.00 |

## 4. Periods

A station's review has one period from 2026-07-01. A row of `station_notices.md` opens a
new period of that station at 00:00 of its notice date. A period is named by its first
date, and a visit belongs to the period that holds its instant. Each period has its own
tariff.

## 5. Station conventions and the tariff of a period

Which tonnage and which draft of a vessel the lines are reckoned on, which recorded time
of the visit is its time in line 5, which hours are its surcharge hours and which holiday
calendar applies to it are the conventions of a station. They are written down nowhere;
they hold for every period of the station, and the station's accepted paid invoices are
the only record of them. Exactly one choice of the conventions leaves every period of the
station with at least one listed tariff that reproduces every accepted paid invoice of the
period to the cent.

Under those conventions, the tariff of a period is the listed tariff that reproduces every
accepted paid invoice of the period. When more than one listed tariff does, the period is
unresolved.

## 6. Disputed invoices

Each accepted row of `disputed_batch.csv` is recomputed as the due of its visit. Every
recomputed due and every verdict uses the tariff and conventions recovered for that
station and period, or the station's unresolved status.

- `billed_correctly`: billed equals the recomputed due.
- `overbilled`: billed is above it; the difference is a refund.
- `underbilled`: billed is below it; the difference is a shortfall.
- `cannot_recompute`: the visit's period is unresolved; reason
  `more than one listed tariff reproduces every paid invoice`.

## 7. Paid invoice files

Each station writes its own file; amounts are euros with two decimals.

- `paid_north.csv`: header `invoice_id,visit_id,invoice_date,amount`.
- `paid_south.jsonl`: one object per line with keys `invoice_id`, `visit_id`,
  `invoice_date`, `amount` (a string).
- `paid_west.txt`: fixed width, no header; columns 1-10 `invoice_id`, 11-18 `visit_id`,
  19-28 `invoice_date`, 29-40 `amount` right aligned; text fields are padded on the right.
- `paid_east.xml`: first line `<paid_invoices station="East">`, last line
  `</paid_invoices>`, and between them one `<invoice id="..." visit="..." date="..."
  amount="..."/>` element per line.
