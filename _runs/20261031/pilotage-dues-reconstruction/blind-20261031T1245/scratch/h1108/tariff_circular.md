# Pilotage tariff circular, third quarter 2026

The harbour authority's pilot stations North, South, West and East bill every pilot
boarding under this circular. The review covers boardings from 2026-07-01 00:00 to
2026-09-30 23:59, harbour local time.

## 1. Definitions

`pilot_movements.log` holds one line per event, in time order:

    YYYY-MM-DD HH:MM BOARD <station> <visit_id> <vessel_id> draft=<m.cc> tugs=<n>[ assist=<minutes>]
    YYYY-MM-DD HH:MM RELEASE <visit_id>

Lines that start with `NOTE` are remarks of the duty pilot and are not records.

- A visit is one BOARD line. Its instant is the time on that line, and its station is the
  station named on it.
- A visit is known when its BOARD line is in the log and its vessel has a line in
  `vessel_register.tsv`.
- `draft` is the measured draft in metres to the centimetre. `tugs` is the number of tugs
  ordered. `assist` is the minutes of tug assistance; a line without it had none.
- The gross tonnage of a visit is the `gross_tonnage` of its vessel in the register.

## 2. The due of a visit

A due is the sum of five lines. Every line is worked in cents and rounded half to even to
a whole cent (19.695 becomes 19.70 and 19.685 becomes 19.68).

1. Tonnage: `base_per_100gt` x gross tonnage / 100.
2. Draft: `draft_per_dm` x (billed tenths - 60) when that is positive, else 0.00. The billed
   tenths are the whole tenths of a metre in the draft, plus one when the centimetres left
   over reach the station's draft mark, a whole number of centimetres no longer than a
   tenth of a metre.
3. Towage: `per_tug` x tugs.
4. Assist: 40.00 for each whole block of 30 minutes, plus 40.00 for the part block left
   over when its minutes reach the station's assist mark, a whole number of minutes no
   longer than a block.
5. Surcharge: (`night_factor` - 1) x the surcharge base, when the instant falls inside the
   station's surcharge hours or on a holiday the station keeps; else 0.00. The surcharge
   base is the tonnage, draft and towage lines, together with the assist line where that
   is the station's convention. Surcharge hours run from a start up to, not including, an
   end; both are times of day to the minute, they differ, and the hours pass midnight when
   the end is earlier than the start.

The due of a visit that is exempt under `exemption_policy.md` is 0.00.

## 3. Listed values

A tariff is one value from each row.

| coefficient | listed values |
|---|---|
| base_per_100gt | 1.80, 1.95, 2.10, 2.25, 2.40 |
| draft_per_dm | 2.50, 3.00, 3.50, 4.00 |
| night_factor | 1.25, 1.40, 1.50 |
| per_tug | 35.00, 50.00, 65.00 |

## 4. Periods

A station's review has one period from 2026-07-01. A row of `station_notices.md` opens a
new period of that station at 00:00 of its notice date. A period is named by its first
date, and a visit belongs to the period that holds its instant. Each period has its own
tariff.

## 5. Station conventions and the tariff of a period

The draft mark, the assist mark, the surcharge hours, whether the surcharge base takes the
assist line, the holiday calendar kept and whether the Monday after a Sunday holiday is
kept are the conventions of a station (`holidays.json` describes the last two). They are
written down nowhere; they hold for every period of the station, and the station's
accepted paid invoices are the only record of them. Exactly one choice of the conventions
leaves every period of the station with at least one listed tariff that reproduces every
accepted paid invoice of the period to the cent.

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
