# DIAGNOSIS 25c745d: cold-chain-backbone-quote, Law-1 condition (3)

Measured 27 Oct 20:38-20:46 IST in Docker (`--memory 4g --cpus 2`, image `warm-cold-chain-backbone-quote:w1`,
tests mounted from BUNDLE at tree b2df10e170e9). Tool `WORK/time_projects.py`; logs `WORK/runs/time_before.log`
and `WORK/runs/time_2611_shipped.log`. Per-project cap 12 s; after two capped projects the rest of a book is skipped.
Book budget = 4 s x projects + 10 s (`api_contract.md:91-92`), so 50 s for every 10-project book.

| program | book | cold rooms | sites | max s / project | sum s (solved) | capped >12 s |
|---|---|---|---|---|---|---|
| blind eac8712 (DW over cold rooms) | shipped (90) | 4-10 | 10-52 | 0.19 | 2.24 | 0 |
| blind eac8712 | fresh_1, fresh_2, fresh_3, rescaled, relocated | 16-17 | 38-52 | >12 | - | 2 of 2 tried, every book |
| kill DW over all cold rooms | shipped (90) | 4-10 | 10-52 | 0.16 | 1.89 | 0 |
| kill DW over all cold rooms | fresh_1..3, rescaled, relocated | 16-17 | 38-52 | >12 | - | 2 of 2 tried, every book |
| probe package, span lifted | shipped / fresh / rescaled / relocated | 4-17 | 10-52 | 0.10 / 0.012 | 0.56 / <=0.07 | 0 |
| blind d7a0, span lifted | shipped / fresh / rescaled / relocated | 4-17 | 10-52 | 0.10 / 0.006 | 0.46 / <=0.03 | 0 |
| blind 2611, span lifted | fresh / rescaled / relocated | 16-17 | 38-52 | 0.013 | <=0.10 | 0 |
| blind 2611, span lifted | shipped | 4-10 | 10-52 | 9.0 | 19.1 (first 64) | P4080, P6862 >12 s; second run OOM-killed at P4080 (18 sites, 7 cold rooms) |

rerun_identical runs fresh_1 twice, so it inherits fresh_1's row. Earlier tuned-DW figures (COST_TABLE, n 47-52):
12 cold rooms 0.5 s, 15 13-15 s, 16 41 s, 17 128 s per project.

## Cause
The fresh book generator (`_fresh_book_parts`, tests/test_output.py:6087-6106) still draws 16 or 17 cold rooms per
project, a remnant of the pre-wave-1 design (M6) that made the fresh books the DW kill. Wave 1 moved the lever to
the wide books but left the fresh draw at 16-17. Shipped projects carry 4-10 cold rooms. Every program whose time
grows as 3^cold rooms (blind eac8712, the kill DW) is fast on all shipped data and on the wide books' own share is a
lever loss, but it also needs 41-128 s per fresh project, so fresh_1..3 core/report/summary,
fresh_networks_feasible, fresh_rollups_follow_network, rescaled, relocated and rerun (54 non-lever points) time out.
It is not the one-call book budget: each fresh project alone is over the 4 s share.

## Chosen fix (smallest)
Only the fresh generator's cold-room draw changes: `rng.randint(16, 17)` -> `rng.randint(8, 10)` with its shape
assert and docstring (test_template.py:876/886/892, rebuilt into tests/test_output.py). 8-10 is the top of the
shipped range (34 of 90 shipped projects have 8-10 cold rooms; sites 38-52 and links 65-92 stay inside shipped
sites 10-52 and links). Rescaled, relocated, missing and rerun derive from the fresh books and follow. Check bodies,
weights, the wide generator and wide checks, the rejection and tie generators are byte-unchanged. At 10 cold rooms
the kill DW and eac8712 need <=0.2 s per project (shipped measurement), far inside the 4 s share.

## Why no hole
No doc sentence changes; no size bound, cold-room limit, method word or span word is added anywhere an agent reads.
The hidden non-lever books now sit inside the distribution the agent can see in `/app/ci`, so passing them needs
nothing the shipped data does not already show (section 8: no unstated size gate). The only stated limit is the
unchanged time sentence; the wide books (30-41 cold rooms, far reach) remain the single timeout lever (24 points =
22.2% of 108). TRUTH.md text that describes fresh books as 16-17 cold rooms is rewritten by script at the end.

## Not fixed here (master decision)
Blind 2611's window sweep with the span check lifted is slow on SHIPPED data (P4080: >12 s, then OOM at 4 GB), a
visible failure under v3.5 condition (1), so its shipped-document checks fail for a reason the agent can see. Making
it fast would need short-reach shipped links, which recreates the span-regularity hidden rule wave 1 removed. The
fix leaves the shipped data unchanged; Phase 3 reports the row with "shipped inputs fast: no".

## Lessons for the master
- none (see FIX_REPORT.md)
