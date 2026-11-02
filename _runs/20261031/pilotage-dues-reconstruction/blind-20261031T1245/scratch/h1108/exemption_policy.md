# Segments and exemptions

`vessel_register.tsv` is tab separated with header
`vessel_id	name	gross_tonnage	segment	certificate`. The segment of a visit is the
`segment` of its vessel: `commercial` or `public`. `certificate` is empty or the id of an
exemption certificate.

`certificates.json` maps each certificate id to its `holder` (a vessel id) and its
`expiry` date. A certificate is in force before 00:00 of its expiry date.

A visit of a `public` vessel whose register certificate is in force at the visit's instant
is exempt: its due is 0.00. Every other visit is charged in full.
