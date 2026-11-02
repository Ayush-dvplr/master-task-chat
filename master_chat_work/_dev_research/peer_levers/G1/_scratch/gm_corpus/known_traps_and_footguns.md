# Known Footguns

1. match_uid is per-attempt; the key is account|hero|seed|split.
2. Anchor on the FIRST attempt, not the canonical row.
3. Order verdicts by review_seq; amended_at is backfilled.
4. Weight partitions differ (frozen stratum vs server).
5. Inflate weights before trimming.
6. Calibrate in log-odds space; legacy plaintext multipliers are superseded.
7. Threshold comparison is inclusive (>=).
8. ORE gain is spreadsheet-only; cost/beta/z are PDF-only.
9. Gap drift rows leave the payout artifacts but stay in metrics.
10. Never regroup by current_tier; the frozen stratum is authoritative.
11. Smurf levy and settlement floor are DOCX-only; apply levy then floor last.
