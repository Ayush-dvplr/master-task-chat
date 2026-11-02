# BLIND REPORT 8caff6e — district-heat-flex-procurement (P13)

Session renamed to `8caff6e` (confirmed in `opencode session list`).

## Files read, in order
1. instruction.md
2. environment/Dockerfile, data/program.ini, data/export_manifest.tsv
3. data/schema.md (full)
4. Heads + comment lines of every data file (continuity_waivers.csv, offers.csv, sites.csv, profiles.tsv, recipient_weights.tsv, site_allowances.tsv, targets.tsv, feeder_limits.txt, pools.txt, site_state.jsonl, rate_cards.xml comment, events.json, segment_floors.json)
5. Quick profiling: group sizes per event-region (max 5 sites / 3 offers), manifest counts and field sums (all agree with the files).

## Timing
Started 14:45:46; program fully written by ~14:48:40 (about 3 minutes to first full write). First run 0.83 s.

## Program
`app/derive_report.py` (also copied to `out/derive_report.py`, the path the instruction names for `/app/out/derive_report.py`). Run: `python3 derive_report.py DATA_DIR OUT_DIR`. Stdlib only.
Key choices: Wh->ticks half-up per record; rate = (override or base) + event uplift + segment adder, then min(cap); credit per interval half-to-even; allowance drawn in dispatch_start instant order (ties: descending event_id); exhaustive DFS per event-region with feasibility pruning and a sound shortfall lower bound, tie count over components 1-5, final tie by greatest sorted-id tuple; `[export] waiver_signed = Y` default NOT applied (empty = not signed); largest-remainder grants, ties served in descending beneficiary_id.

## Self-check (shipped data only) — PASS
- All 9 named JSON files exist; each is sorted-keys JSON with trailing newline, no floats/booleans.
- Region files: 500 events ascending, 6 intervals each, grants sum = allocated, funded = allocated + unallocated.
- Segment files: 2000 event-regions in (event_id, region) order; segment totals sum to summary totals (relief 13262700 + 9783817 = 23046517; bid and selected counts also agree).
- policy_audit: 10000 site labels, ordered; compliance counts sum to 10000.
- data_quality row counts equal export_manifest.tsv records for every file; manifest field sums matched the raw files.
- No crash; no crash fix needed.

## Lessons for the master
- Instruction puts the program at `/app/out/derive_report.py` while the blind rules say `app/`; I placed it in both.
- Allowance rows missing for a site are undefined; I treat a missing row as no limit.
- Shipped data produced 0 tie_decisions and 0 duplicate/out-of-range profile rows, so those paths are unexercised by the shipped extract.
- Whether an empty `waiver_signed` should take the `[export]` default is a deliberate trap; schema says `[export]` carries no rule, so I did not apply it.
