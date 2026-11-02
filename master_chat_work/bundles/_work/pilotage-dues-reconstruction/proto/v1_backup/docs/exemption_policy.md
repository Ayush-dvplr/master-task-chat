# Public Vessel Exemption Policy

## Segments

`vessel_register.tsv` is tab separated with the header
`vessel_id	name	gross_tonnage	segment	exemption_expiry`. `gross_tonnage` is a whole number;
`segment` is `commercial` or `public`. A commercial vessel has `-` as `exemption_expiry`; a public
vessel has a date `YYYY-MM-DD`.

## Certificates

A public vessel holds an exemption certificate. A public vessel's certificate covers its on-board time
before 00:00 on its exemption_expiry date. Pilotage time covered by the certificate is not billed.
Billed minutes and the due that follows from them are set out in `tariff_circular.md` section 2a.

A disputed invoice of a public vessel is judged against that due like any other invoice.
