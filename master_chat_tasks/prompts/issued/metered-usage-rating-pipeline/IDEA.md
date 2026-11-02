# Idea card: metered-usage-rating-pipeline (master-drafted, 24 Oct 2026 16:05 IST)
Source: master draft from LEVER_RULES_v1 section 1b (Opus-habit bank), approved route by Ayush 24 Oct ("I draft idea"). First build on P2_build_v3 with the G10 cost-table gate. Not from a ChatGPT batch.

## Premise
A cloud provider bills metered usage (compute hours, storage GB-days, egress GB, support minutes) collected by five regional collectors (central, east, north, south, west), each in its own export format. Accounts belong to four customer segments (consumer, smb, corporate, enterprise) and sit on either a committed plan or pay-as-you-go; accounts move between plans and segments mid-month through a plan-change event log. The agent writes one reusable `transform.py` that turns any month of collector exports into one rated record stream plus the summary, quality, product, region and segment reports of the data-pipeline archetype.

## Inputs (at least 10 files, at least 5 formats, flat)
- `rating_contract.md`: THE one contract file (W10). Record model, field blocks per collector, the malformed-value list, rating (tier tables, rounding step), commitment credit, identifiers, plan-change semantics, dedupe, every output key and error string, and which document wins when two disagree.
- Collector exports: `collector_central.csv`, `collector_east.tsv`, `collector_north.jsonl`, `collector_south.txt` (fixed-width), `collector_west.log` (key=value lines). Each a few thousand lines.
- `rate_card.json` (per product tier tables, 4-decimal unit rates), `accounts.csv` (account id, segment, plan at month start), `commitments.xml` (credit pool per region and month), `plan_changes.log` (timestamped plan/segment moves; rarely joined), `products.ini` (product codes, units, collector field names), `collector_controls.json` (per-collector record counts and unit sums: L1-style parse control, honest and described in the contract; never the lever).
- No expected outputs, no sample reports, no labelled answers.

## Spine
parse 5 collectors -> validate per field block (quarantine to data_quality with stated reason) -> canonical account id -> plan and segment in force at each record's timestamp (plan_changes.log) -> dedupe -> rate per line (tier, exact decimal, half-even at the stated step) -> commitment credit per region-month -> normalized.jsonl -> product, region, segment, summary, data_quality documents.

## Levers (each a stated single-reading rule; each must cost >= 25% of test points alone, G10)
- LV-MU-1 (H1 / L5 strict integer): in `collector_north.jsonl` the `units` field "is a JSON integer"; a quoted integer ("120"), a "12.0" string or any string is malformed and the record is quarantined with reason `units_not_integer`. A global rule elsewhere in the contract trims surrounding whitespace from text fields. Easy-reject decoys of the same field ship too (true/false, 12.5). State the strict rule twice: in the north field block and in the malformed-value list. Shipped data carries separating rows (W5 allows it for L5 only). Every quarantined record leaves every downstream document.
- LV-MU-2 (H2 / L8 exact-decimal half-even): line charge = units x unit rate in exact decimal, rounded half-even to 0.01 per line, then summed; credits likewise. Hidden inputs plant at least 3 exact .xx5 ties per region and per segment (rates with 4 decimals make them reachable). Shipped data has no tie, so shipped output cannot separate float or half-up from the rule.
- LV-MU-3 (H3 / L9 denominator scope): each region-month credit pool from `commitments.xml` is allocated pro rata by line charge where the glossary defines the base as "charges of lines whose account is on a committed plan at the line's timestamp in that region and month"; only those lines receive credit. A wrong all-lines base still allocates the whole pool, so every pool total and region total control still balances.
- LV-MU-4 (H4 / L10 normalisation in a rarely joined field): the identifiers section states account ids compare after upper-casing and removing every hyphen. The collectors and accounts.csv already carry the canonical form; only `plan_changes.log` writes ids in mixed case with hyphens. An exact-match join silently drops those plan changes, so segment and committed status (and so LV-MU-3 credit) go wrong for the moved accounts.
- Interaction: LV-MU-4 feeds LV-MU-3 (committed status), LV-MU-1 removes records before LV-MU-2 and LV-MU-3; a slip on one never forces a slip on another (independent wrong readings).
- Noise only (never scoring levers, LEVER_RULES 1b): one collector declares latin-1 encoding; duplicate record ids with a stated dedupe rule; easy decoys of LV-MU-1. Keep noise rules few: every contract rule needs a RULE_COVERAGE mutant (G11).

## Grading shape (LEVER_RULES section 3)
- 14 downstream documents: whole-document test each on shipped data and on hidden reseeded months from an embedded generator (G1, G3 >= 30%); hidden seeds plant every lever's separating case in every region and segment so one slip fails many documents (amplification by design, every slip a stated rule).
- Mutation tests (G6): shuffle rows + scale one tier curve by 1.0375; relocate and rename the export directory; delete one declared collector (non-zero exit naming it).
- Generator bounds asserts (G12); check_exact.py independent of solve.py (G9).

## Gate notes for the build
- G10 cost table must show each LV-MU lever alone >= 25% of test points and every all-but-one row overall < 70. If LV-MU-2 or LV-MU-3 is under 25%, plant more separating cases in more documents before Phase 5, never raise a weight above 5.
- Kill risk: if the probe's tests come back >= 95, Opus read all four rules strictly; harden by swapping the weakest lever from the 1b bank (H5 make-it-match on the L1 control, or H6 allowance consumed early), not by adding volume.
