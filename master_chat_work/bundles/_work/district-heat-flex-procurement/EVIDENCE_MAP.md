# EVIDENCE_MAP district-heat-flex-procurement (wave 1, 7d95b18)

Every tie and no-feasible case of the wave-1 wide checks is settled by a stated verdict. No graded rule of wave 1 lacks a sentence; the rows below name the sentences the wide checks rest on.

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| tie among best portfolios | wide_0_selection_match, wide_1_selection_match, wide_0_tie_decisions_match, wide_1_tie_decisions_match | `environment/data/schema.md:135` (greatest identifier wins; a set compares as its sorted tuple, lines 135-137) and `schema.md:322` (tie_decisions entry and `tied_portfolio_count`, lines 322-325) | least sorted tuple; first portfolio found; count of distinct value classes instead of portfolios |
| no feasible portfolio | wide_0_portfolios_feasible, wide_1_portfolios_feasible | `environment/data/schema.md:175` (no offer at a site and the empty portfolio are allowed, lines 175-176); ceilings are non-negative, so the empty portfolio is always feasible | an event-region with no row or a null selection |
| run limit and size | every wide_* check | `environment/data/schema.md:162` (at most 3 candidate offers per site in an event; each run within 120 seconds, lines 162-163) | a program that assumes a bound on sites per event-region |
