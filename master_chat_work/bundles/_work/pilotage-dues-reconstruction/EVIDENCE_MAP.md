# EVIDENCE_MAP (v2)

Every graded rule is stated in its governing file (DESIGN.md s4). The rows below are the
deliverable facts that the stated principle leaves to the data: which convention choice a
station uses is not written anywhere; it is settled by one determinate fact, the unique fit
over the station's own accepted paid invoices (LEVER_RULES 0b, AL-1 05:21, FC:492).
Line ranges are filled from the bundle data in Phase 2 (coverage plants are listed by line).

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| SR1 assist mark of station S | test_hidden_k_region_<S>, test_hidden_k_audit, test_hidden_k_totals, test_shipped_regions | paid_<s> lines of invoices whose assist leaves a part block of mark-1 and mark minutes (Phase 2 cites) | every other mark 1..30 |
| SR1 draft mark of S | same | paid_<s> lines with remaining centimetres mark-1 and mark above 6.0 m | every other mark 1..10 |
| SR1 surcharge hours of S | same | paid_<s> lines boarded within 15 minutes either side of start and end on plain days | every other quarter-hour window |
| SR1 assist reckoned by S | same | paid_<s> surcharged lines with assist > 0 | the other reckoning |
| SR1 calendar of S | same | paid_<s> daytime lines on each date where calendars differ | the 6 other calendars |
| SR1 Monday kept by S | same | paid_<s> daytime lines on each Monday after a Sunday holiday | the other choice |
| SR1 station-wide (one choice across periods) | test_hidden_k_region_<S> of notice stations | circular s5 sentence (stated); UNIQUENESS.md column 5 shows 2..288 per-period fits | per-period fitting |
| SR2 unresolved period | test_hidden_k_region_<S>, test_hidden_k_audit, test_hidden_k_totals | stated in circular s6 (verdict and reason); hidden only (shipped 0) | first fitting tariff |

Shipped witness count (proto2): one choice fits each shipped station over the stated space
(UNIQUENESS.md). Hidden: one choice per station in every corpus, asserted by the generator.
