# Vessels, agents, stations and exemptions

`vessel_register.tsv` is tab separated with header
`vessel_id	name	gross_tonnage	net_tonnage	max_draft	flag	agent	segment	certificate`.
Tonnages are whole tonnes and `max_draft` is the vessel's greatest draft in metres to the
centimetre. `flag` is the vessel's flag state and `agent` the id of the shipping agent that
orders its pilots. The segment of a visit is the `segment` of its vessel: `commercial` or
`public`. `certificate` is empty or the id of an exemption certificate.

`agents.tsv` is tab separated with header `agent	name	office	opens	closes`: the city of
the agent's office and the times of day its office opens and closes.

`stations.tsv` is tab separated with header `station	watch_from	watch_to	opens	closes`:
the times of day each pilot station's night watch starts and ends, and the times of day its
office opens and closes.

`certificates.json` maps each certificate id to its `holder` (a vessel id) and its
`expiry` date. A certificate is in force before 00:00 of its expiry date.

A visit of a `public` vessel whose register certificate is in force at the visit's instant
is exempt: its due is 0.00. Every other visit is charged in full.
