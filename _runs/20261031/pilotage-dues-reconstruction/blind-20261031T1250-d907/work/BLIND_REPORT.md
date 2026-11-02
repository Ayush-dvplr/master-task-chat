# BLIND REPORT 5456c27 — pilotage-dues-reconstruction (P13, design-stage blind)

Session renamed: opencode `ses_e6f282240ffeKks2zdDA3btLkx` matched (codex: no match).

## Files read, in order
1. instruction.md
2. environment/data/output_contract.md, tariff_circular.md, rule_register.md, exemption_policy.md, station_notices.md, holidays.json
3. Heads and tails of paid_north.csv, paid_south.jsonl, paid_west.txt, paid_east.xml, disputed_batch.csv, vessel_register.tsv, pilot_movements.log; the start of certificates.json
4. Regex scans of the log and of every paid and disputed file, plus a quick certificate/register consistency script

## Timing
Started 12:54:24 IST and wrote the full program before 12:58:09, so about 3–4 minutes to the first full write. The single run took 0.72 s.

## Self-check (shipped data only): PASS
- The run exited 0 and wrote all 9 documents with the keys the contract lists.
- Disputed rows add up: 253 data rows minus 5 rejected leaves 248 disputes. The verdict counts add up to 248, the four regions to 62 × 4 = 248, and the two segments to 212 + 36 = 248.
- Paid rows add up: 296 data lines minus 6 rejected leaves 290 accepted per station.
- The recovery found exactly one convention set per station and printed no ambiguity warning.
- The fatal-input path was not exercised; the task said not to build extra inputs.

## Crash fixed
None.

## Observation
All four stations came out with the same draft mark (1), assist mark (1), surcharge-base flag (assist included), surcharge hours (22:00–06:00) and Monday rule (kept). Only the calendar differs, and each station keeps its own namesake calendar. The search reported a unique fit in each case, but identical marks of 1 for every station could also mean the paid data barely constrains those marks. The master may want to check this.

## Lessons for the master
- `shortfall_total` and "the difference is a shortfall" do not say whether the shortfall is negative (billed − recomputed) or a positive amount. I used a positive amount.
- `vessels` in the segment files could be a count or a list. I used a count.
- The fatal rule mentions "a JSON file that does not parse", which leaves open whether one bad line in `paid_south.jsonl` is fatal or a `malformed_record`. I used `malformed_record`.
- Surcharge hours are only determined if the paid invoices fall right at the window edges. The contract does not say what to do when the paid data leaves the window loose.
- Draft and assist marks of 0 ("reach a mark") and certificates whose `holder` is a different vessel are both left undefined. I used marks of 1 or more and required the holder to match.
