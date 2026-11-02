# CHECKS 529e4de (every run under perl alarm 600, timed with /usr/bin/time -p)
- `python3 out/derive_report.py --data environment/data --out work/run1` | input environment/data | exit 0, real 6.00 s, 9 JSON docs written; stderr convention gross,measured,board,watch,region for all 4 stations
- `cat work/run1/*.json` controls | work/run1 | 248 disputes = 253 data rows - 5 rejected; 250 accepted paid per station (= data lines - 6 rejected each); billed-recomputed 37356.91 = refund 39594.60 - shortfall 2237.69; segments 203+45=248; 29 rejections (9/10/5/5); no unresolved periods
- `python3 -c "...solve_station per station..."` | environment/data | real 5.71 s; exactly 1 valid convention per station, exactly 1 tariff per period (uniqueness holds, no tie-break used)
- `python3 out/derive_report.py --data work/fatal_data --out work/run_fatal` (copy of data minus holidays.json) | work/fatal_data | stderr `ERROR unreadable input: holidays.json`, exit 2, 0 outputs, real 0.27 s; temp dirs removed
- `python3 -c "...underbilled ids..."` | work/run1/policy_audit.json | 248 rows, 42 underbilled ids listed in FINAL_REPLY.md
