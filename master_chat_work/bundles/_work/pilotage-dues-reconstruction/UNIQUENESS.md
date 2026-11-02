# UNIQUENESS (v2): SR1 convention fit and SR2 tariff fit

Candidate space per station (stated in tariff_circular.md s1 ranges, s2 families, holidays.json):
assist mark 1..30 x draft mark 1..10 x Monday kept yes/no x assist reckoned yes/no x
7 calendars x 9,120 quarter-hour windows (start != end) = 76,608,000 convention choices, each
paired with 180 listed tariffs per period. Counted by proto2/core2.fit (decomposed: tariff x
invoice options, then mark x mark x reckoning, then calendar x Monday x window bitmasks).

Witness: the station's accepted paid invoices (one paid file per station). Every candidate is
fitted to every shipped and hidden witness; the generator asserts exactly one survivor per
station (G-1) and, for SR2, exactly one tariff in a non-ambiguous period and three in an
ambiguous one.

| corpus | station | full stated space | natural-wide space (marks {1,15,16,30}/{1,5,6,10}, whole-hour windows, 7 calendars) | second period fitted alone |
|---|---|---|---|---|
| shipped 482617 | North/South/West/East | 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 | no notice |
| 1101 | North | 1 | 0 | - |
| 1101 | South | 1 | 0 | 100 |
| 1101 | West | 1 | 0 | - |
| 1101 | East | 1 | 0 | 64 |
| 1102 | North | 1 | 0 | 6 |
| 1102 | South / West / East | 1 / 1 / 1 | 0 / 0 / 0 | - |
| 1103 | North | 1 | 0 | 40 |
| 1103 | South | 1 | 0 | 2 |
| 1103 | West | 1 | 0 | - |
| 1103 | East | 1 | 0 | 12 |
| 1104 | North / West | 1 / 1 | 0 / 0 | - |
| 1104 | South | 1 | 0 | 24 |
| 1104 | East | 1 | 0 | 288 |

Reading: exactly one choice fits each station over the stated space in every corpus. A narrower
space finds no choice on hidden data (K4w WRONG), and fitting a notice period on its own leaves
2 to 288 choices; the station-wide sentence (circular s5) is what makes the fit unique.
Shipped: the headline choice is the only fit, so shipped data cannot tell a narrow search from
the stated one (degenerate instance, S2). Re-run on the bundle generator in Phase 2 and on 300
seeds in Phase 4 (G12).

SR2 tariff space: 5 x 4 x 3 x 3 = 180 listed tariffs. Non-ambiguous period: 1 fits.
Ambiguous period (every accepted paid invoice has tugs 0): 3 fit (per_tug free), status
unresolved, reason `more than one listed tariff reproduces every paid invoice`.
