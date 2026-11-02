# Public Vessel Exemption Policy

## Vessel register

`vessel_register.tsv` is tab separated with the header
`vessel_id	name	gross_tonnage	segment	certificate	measured_from`. `gross_tonnage` is a whole
number; `segment` is `commercial` or `public`. A commercial vessel has `-` as `certificate`; a public
vessel has the id of its certificate in `certificates.json`, or `-` when it holds none.
`measured_from` is `-` or a date `YYYY-MM-DD`.

A vessel has one row with `measured_from` `-` and may have further rows, each with its own date, when
it was re-measured; its rows differ only in `gross_tonnage` and `measured_from`. The row in force at an
instant is the row with the latest `measured_from` date on or before the instant's date, and the row
with `-` when there is none. Example on invented values: rows `-` with 4,000 and `2030-05-10` with
4,400 give 4,000 for a visit on 2030-05-09 and 4,400 for a visit on 2030-05-10.

## Certificates

`certificates.json` is one JSON object. Each key is a certificate id and maps to an object with the
keys `holder` (text), `expiry` (a date `YYYY-MM-DD`) and `allowance_minutes` (a whole number).

A certificate covers on-board time of the vessels registered under it, before 00:00 on its expiry date,
up to its allowance_minutes in total. Visits draw on the allowance in the order of their instants, the
lower visit id first on a tie. Every visit of those vessels draws, whether invoiced or not and at
whichever station. A visit's covered minutes are its on-board minutes before 00:00 on the expiry date,
or the allowance left when that is less; the allowance left drops by the minutes covered.

A public vessel without a certificate has no covered minutes. Pilotage time that is covered is not
billed; billed minutes and the due that follows from them are set out in `tariff_circular.md` section
2a. A disputed invoice of a public vessel is judged against that due like any other invoice.
Example on invented values: a public vessel with `-` as `certificate` and 200 on-board minutes has
200 billed minutes.
