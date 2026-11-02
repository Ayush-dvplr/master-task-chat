# Final reply 529e4de: pilotage-dues-reconstruction

Built `/app/out/derive_report.py` (stdlib only). It parses the four paid-invoice layouts and the disputed batch, and applies the rejection codes in contract order (malformed > duplicate > unknown visit > station mismatch). It then searches 216 station conventions (tonnage x draft x line-5 time x surcharge hours x holiday calendar) against the 180 listed tariffs per period, recomputes each accepted dispute, and writes the 9 JSON documents. A missing or unreadable input exits 2 with `ERROR unreadable input: <file>`.

Checked on shipped data: exit 0 in 6.0 s with 9 documents. Row counts and totals reconcile (billed - recomputed = refund - shortfall = 37356.91). Each station has exactly one valid convention and one tariff, so no tie-break was used. A copy of the data without holidays.json gives exit 2 and no outputs.

Key figures: 248 disputes. Verdicts: 106 billed correctly, 100 overbilled, 42 underbilled, 0 cannot_recompute. Billed 262074.04, recomputed 224717.13, refund 39594.60, shortfall 2237.69. Largest refund is D8500901 at 3896.52. 29 records rejected (9 malformed, 10 duplicate, 5 unknown visit, 5 station mismatch).

Convention for all four stations: gross tonnage, BOARD-measured draft, BOARD time, watch hours 22:00-06:00, regional holiday calendar.

Periods (shipped station_notices.md has no rows, so each station has one period):
- North 2026-07-01: per_100_tonnes 1.95, per_tenth 3.00, surcharge_factor 1.50, per_tug 35.00
- South 2026-07-01: per_100_tonnes 1.80, per_tenth 2.50, surcharge_factor 1.40, per_tug 65.00
- West 2026-07-01: per_100_tonnes 2.10, per_tenth 3.00, surcharge_factor 1.25, per_tug 35.00
- East 2026-07-01: per_100_tonnes 2.25, per_tenth 4.00, surcharge_factor 1.50, per_tug 65.00
- Unresolved periods: none

Underbilled invoices (42): D1357552 D1506797 D2023688 D2035687 D2489721 D2507683 D2618808 D2991942 D3237743 D3484782 D4273795 D4640960 D4845117 D4931673 D4947444 D4987865 D5109541 D5130058 D5152111 D5446395 D5538221 D5616052 D5668575 D5679740 D6517941 D6529211 D7224571 D7230263 D7405830 D8226813 D8263617 D8482969 D8754709 D9152833 D9209659 D9330148 D9396600 D9428485 D9756400 D9759806 D9765523 D9903845
