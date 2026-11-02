# Blind report 529e4de: pilotage-dues-reconstruction (P13 design-stage blind read)

Session rename: ran `name_session.py 529e4de` at 14:19. Output: `codex: no match` / `opencode: ['ses_e6eda2524ffeA3pRiy5YT282kG']`. I could not confirm that this ID is the current session, and I did not retry on another ID.

## Files read, in order
1. instruction.md
2. output_contract.md
3. tariff_circular.md
4. rule_register.md
5. exemption_policy.md
6. station_notices.md
7. Data files: agents.tsv, stations.tsv, holidays.json, certificates.json, vessel_register.tsv, disputed_batch.csv (head), paid_north.csv, paid_south.jsonl, paid_west.txt, paid_east.xml, pilot_movements.log

## Minutes to first full write
4 minutes (14:19 start to 14:23, when app/derive_report.py was written in full and copied to out/).

## Self-check coverage and result: PASS
- All 9 output documents are present, and their shapes match output_contract.md.
- Row counts reconcile: 253 data rows - 5 rejected = 248 disputes, and each station has 250 accepted paid invoices.
- Totals reconcile: billed - recomputed = refund - shortfall = 37356.91, and the segments sum to 248.
- Each station has exactly one valid convention and exactly one tariff per period.
- The fatal path works: with holidays.json missing the program exits 2 with the exact error line and writes no outputs.
- Not covered: fresh data with station notices (two periods), or unresolved periods. The shipped data has neither.
- Every run is logged in CHECKS.md. The longest run took 6.0 s real time.

## Crash fixed
None. The first run exited 0, and the program was not changed after it was written.

## Lessons for the master
- All four stations share the same convention (gross, measured, board, watch, region) and it is the first item in a natural enumeration. A solver that stops at the first match would score the same as a correct one. Give stations different conventions.
- station_notices.md ships with no rows, so the two-period path and the unresolved/cannot_recompute path are never exercised on the visible data.
- Every paid file has exactly 6 rejections spread evenly over the 4 codes. That is a recognisable pattern; vary it.
- Section 6 is silent on exempt visits in unresolved periods (due 0 under any tariff). I followed the text literally and return cannot_recompute.
