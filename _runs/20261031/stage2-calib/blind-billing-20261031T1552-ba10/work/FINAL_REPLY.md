I built the billing run as one standard-library program, `/app/out/transform.py`, called as `python3 /app/out/transform.py DATA_DIR OUT_DIR`. I ran it once on `/app/data` with `/app/out` as OUT_DIR. It wrote **13 reports**: data_quality.json, normalized.jsonl, product_summary.json, the five region reports, the four segment reports and summary.json. It printed one `wrote NAME SIZE` line for each.

**How it works.** Handset clock offsets are not given in the extract. The program works them out from the exchange register. For each handset it tries every offset from -19 to 19 minutes and keeps the one that lands the most closings on registered (line, day, minute-slot) calls. On a tie it keeps the smaller absolute offset. On the shipped cycle the offsets are H-08 +1, H-11 -7, H-13 -7, H-15 -11, H-18 -3, H-25 +7, H-31 -15 and H-33 +8. For each one, the next-best offset matched 8 closings or fewer. The rest follows the shipped billing standard:
- legacy rows are merged in and duplicates dropped
- service aliases and upper-case codes are resolved
- amendments, including reverts, are applied
- each closing gets a zone-local business day and a tier, and is priced from the dated rate card named in cycle.json
- allowance credit runs latest-first
- net amounts round to cents with half-even rounding
- the minimum invoice tests gross amounts for regions and net amounts for segments.

**Shipped cycle figures (C202603):**
- summary.json net_micro: **95969825500** (gross 105834988500, credit 9865163000, 1518 billed closings)
- region_central net_micro: **15445059500**
- region_east net_micro: **23863329000**
- region_north net_micro: **20713397500**
- region_south net_micro: **22137983000**
- region_west net_micro: **13810056500**
- Data quality: 1536 closings received (1152 main + 388 legacy - 4 duplicates), 6 rejected as unknown_service, 12 void, 0 unrated, 0 outside the cycle, 0 amendments without effect.

**What-ifs.** Each one is a full rerun of the program on a changed copy of the extract.
1. 96945842500
2. 76399338500
3. 66678709500 (on the shifted copy, region_north net_micro was 20677397500, and that became the minimum invoice)
4. 840
5. 20278774500
6. 34371706500
7. 5077580500
8. 143108240000

**Checks run on the program, with their size:**
- **Shipped-cycle run:** 1 extract, 1536 closings. Exit code 0 in 0.07 s; all 13 reports present, compact JSON with sorted keys and a final line feed.
- **Totals check on that run's outputs:** 1 extract, 1536 closings.
  - normalized.jsonl has 1518 lines, matching closings_billed.
  - Normalized, product, region and segment net totals are all 95969825500, so residual_micro is 0.
  - Region closings and segment closings each add up to 1518.
- **Determinism rerun:** 1 extract, 1536 closings. Run from a different working directory into a different OUT_DIR, the output was byte-identical.
- **Extract unchanged:** 1 extract, 1536 closings. The data directory's hashes before and after the run match.
- **What-ifs:** 19 changed extracts, 29184 closings in total (1536 each). Q3 needed 2 runs and Q4 needed 11. Every run finished in about 0.1 s.
