# Final reply

I wrote `/app/out/derive_report.py` (standard library only) and ran it once with `--data /app/data --out /app/out`. It finished in 0.7 s and wrote all nine documents.

**How it works.** It checks every data file first. If one is missing or unreadable, it prints `ERROR unreadable input: <file>` to stderr, writes nothing and exits with status 2. Next it rejects records with the four contract codes, in contract order. For each station it then searches every combination of conventions against the accepted paid invoices: draft mark 1–10 cm, assist mark 1–30 min, whether the assist line is in the surcharge base, the 7 calendars, and the Sunday-to-Monday rule. The surcharge hours come out of the same search, as a circular window that must contain the surcharged minutes and exclude the unsurcharged ones. Finally it fixes each period's tariff, or marks the period unresolved, and recomputes the disputed batch.

**Conventions recovered.** Exactly one choice fit each station. For all four:
- draft mark 1 cm and assist mark 1 min
- the surcharge base includes the assist line
- surcharge hours run 22:00 to 06:00
- the Monday after a Sunday holiday is kept

Each station keeps its own calendar: North uses `north`, South `south`, West `west` and East `east`.

**Periods.** `station_notices.md` has no rows, so each station has one period. None is unresolved.

| Station | period_start | base_per_100gt | draft_per_dm | night_factor | per_tug |
|---|---|---|---|---|---|
| North | 2026-07-01 | 2.10 | 3.00 | 1.25 | 65.00 |
| South | 2026-07-01 | 2.40 | 2.50 | 1.50 | 35.00 |
| West | 2026-07-01 | 2.10 | 4.00 | 1.25 | 50.00 |
| East | 2026-07-01 | 2.10 | 4.00 | 1.40 | 50.00 |

**Disputed batch.** 248 rows were accepted:

| Verdict | Count |
|---|---|
| billed_correctly | 103 |
| overbilled | 102 |
| underbilled | 43 |
| cannot_recompute | 0 |

| Total | Amount (€) |
|---|---|
| Billed | 286216.70 |
| Recomputed | 245926.65 |
| Refunds | 42235.29 |
| Shortfalls | 1945.24 |

The largest refund is D5893719 at €3942.71.

**Rejected records.** 29 in all: 9 `malformed_record`, 10 `duplicate_invoice`, 5 `unknown_visit` and 5 `station_mismatch`. That leaves 290 accepted paid invoices per station.

**Underbilled invoices (43):** D1055294, D1437508, D1703566, D1812440, D2432758, D2711551, D2798857, D3197326, D3383584, D3709006, D3961195, D4011732, D4116724, D4162919, D4687407, D5062249, D5160802, D5294865, D5633491, D6098686, D6483614, D7021205, D7074311, D7247115, D7656929, D7833540, D8021026, D8348975, D8389354, D8414182, D8439816, D8702918, D8752663, D8787804, D8792851, D9157908, D9326863, D9576839, D9690783, D9719638, D9727945, D9762667, D9926108.

**Choices where the contract left room:**
- `shortfall_total` is reported as a positive amount.
- `vessels` in the segment files is a count.
- A paid-invoice line that is not valid JSON counts as `malformed_record`, not as a fatal input.
- A certificate exempts a vessel only if its `holder` is that vessel.
- If the paid data ever leaves the surcharge window loose, the program uses the tightest window around the surcharged minutes.
