# TRUTH: 80877080-fd28-52cb-9067-5022bfd0f888

## Defect

The published plan `cache_plan_published.csv` was produced by the saved query pack
`advisor_query_pack.md`, and every query in the pack breaks at least one rule of
`cache_planning_rulebook.md` (revision 5), the pricing bulletin or the capacity workbook:

- Q01 reads every query-log shaped file instead of the manifest shards (P2), and drops
  batch rows before deduplication.
- Q02 deduplicates over final rows only, so a voided later revision resurrects an older
  final row (P3.2 keeps the largest revision whatever its status).
- Q03 treats every volume as GiB; MiB, KiB and hundredths of a GiB need P2.2.
- Q04 reads the window in UTC and treats local collectors as UTC; the window is wall time
  at `billing_offset` and `local_cluster` / `local_billing` stamps need P2.3.
- Q05 applies one merge hop, ignores `merged_on` (P1.4 time-gates every ledger row and
  walks chains with cycle handling), lets the archive registry win (P6 says main wins),
  and uses the `tier` column for dev projects (P6.4 uses the profile list).
- Q06 applies PENDING entries and skips the late XML half (P4).
- Q07 derives the family from the template prefix (P1.6, Appendix T is authoritative),
  uses `engine_factor_hint.json` (the workbook `ScanFactors` sheet is authoritative) and
  keeps units at full precision (P8 rounds each query to three decimals).
- Q08 drops `C` queries and nets every reservation of any state and end (P7, P9, Table C-1).
- Q09 nets before growth (P10 grows, rounds to two decimals, then nets).
- Q10 drops hours with no rows and keeps outage hours (P5).
- Q11 uses the flat digest rates and no errata (Table R-2 plus Table E-1 in erratum order).
- Q12 takes the node count from the announcement and the DRAFT sheet; the sheet in force
  comes from the `Adoptions` register under the 1904 date system (P11.4, P11.5).
- Q13 is a greedy marginal optimiser without family caps, minimum purchases or memory,
  and checks Table M-0 once, dropping all short clusters together (P13, P13A).
- Q14 discounts only the units above the tier and keeps the discounted rate unrounded
  (P12.5 prices every unit at the rounded discounted rate).
- Q15 rounds half up, sums rounded savings for the total and charges back by team
  (P14, P15).

## Load-bearing work

1. Parse 32 shards in 16 layouts listed by `ingest_manifest_r7.json`, with code maps,
   units and seven timestamp conventions; ignore `scan_rollup_cache_03.jsonl`.
2. Deduplicate by largest revision, then drop voided rows; count lineage.
3. Replay both journal halves in `seq` order, posted only, with VOID, SETQTY, MOVE,
   RETAG and ADD outcomes. RETAG never occurs in the shipped journals and is exercised
   by three held-out corpora.
4. Resolve every project token through `project_merges.psv` as of an instant: query
   tokens at the query start, every other token at W1. Rows take effect at 00:00 of
   `merged_on` at the billing offset; a revisited id ends the walk at the smallest id
   of the cycle with the step count as hops.
5. Read the workbook: the `workbookPr date1904="1"` flag, the `Adoptions` sheet (track
   `RS-C4`, status `ADOPTED`, latest effective date on or before the lookback start
   date). In the shipped corpus A-102 / RS-C4A (2026-08-17) is in force; A-104 / RS-C4D
   is adopted one day after the lookback starts and A-100 is a later WITHDRAWN row.
   Read ScanFactors and Clusters.
6. Read the PDF: pages in `/Kids` order (objects are stored shuffled), every cell its own
   `BT ... ET` at `1 0 0 1 x y Tm`, shuffled within the page, as literal, hex or `TJ`
   strings. Tables R-2, E-1 (rows shuffled; applied in ascending erratum id, so later
   IN FORCE errata override earlier ones on the same field), C-1, M-1 (in force), M-0
   (superseded). One in-scope cluster is missing from M-1 and has no commitment.
7. Scope (P6), exclusion reasons in order (P7), rounded per-query units (P8),
   reservation dispositions (P9), grown and rounded load (P10).
8. Curves per candidate pool with the rounded tier rate (P12), then the exact optimum
   under family caps, the node cap and the memory budget with the P13 tie order.
9. The commitment pass (P13A): close the short cluster with the smallest exact saving,
   re-solve, repeat. The shipped corpus needs four rounds (WH-AUE1, WH-EUC1, WH-USE1,
   WH-SGP1). Closing all short clusters at once, using Table M-0, or skipping the pass
   each gives a different plan.
10. Reporting: rounded pool savings, once-rounded total, largest-remainder chargeback
    to the query-time project, rollups, variance and reconciliation, manifest.

## Verification

Channel A (`tests/test_output.py`) embeds the shipped corpus, the corpus generator and
an independent reference. Eight held-out corpora are generated at grade time:

| corpus | what moves |
|---|---|
| h_track | billing -03:30, other window, adoption effective exactly on the lookback start date (RS-C4D in force) |
| h_retag | 40 RETAG entries, three merge cycles, 40 percent in-window merges |
| h_closure | six other in-scope clusters, tighter Table M-1, two clusters missing from it |
| h_shards | 24 shards, two unlisted feed-shaped files, billing +05:45, ten-day window |
| h_dense | 40 queries on and one second before merge instants, ten overriding errata pairs, RETAG |
| h_org | another org, plan and quarter, RS-C4D adopted three days before the window |
| m_policy | shipped feeds, other errata statuses and Table M-1 values |
| m_profile | shipped feeds, extra dev projects and outages, one cluster fewer in scope |

The full-core gate requires `cache_plan.csv`, `pool_curves.psv`, `pool_hourly.tsv`,
`rates_used.csv`, `ruleset_used.json`, `cluster_commitments.jsonl`, `chargeback.csv` and
`plan_summary.json` to be exact in `/app/out` and in the program's rerun on all eight
corpora before any gated check pays. Weights: six shape checks at 1, seven gated shipped
leaf checks at 3, eight held-out checks at 5 (positive total 67), fourteen negatives
(-46). Channel B (`tests/judge.toml`) has 35 criteria, positive total 88.

Measured test-channel scores (local run of the verifier with rewardkit stubbed): oracle
67/67 = 1.000; empty output 0.000; empty-file stub 0.015; a program that pastes the
shipped answers 0.015; single-rule mutants of the oracle: no staged rounding 0.030,
date-blind merges 0.045, no commitment pass 0.045, no RETAG 0.090, unrounded tier rate
0.090, summed rounded total 0.075. These are test-channel numbers only; no judged-channel
score exists for the oracle.

## Root cause

The query pack implements a plausible first pass of every stage and none of the
interacting rules: time-gated identity, staged rounding, adoption by date under the 1904
system, errata order, and the commitment pass that only appears after a first optimum.

## Solution shape

`solution/solve.py` is a single stdlib program: a PDF tokenizer that walks the page
tree, an xlsx reader that resolves sheet names through the workbook relationships, a
`Plan` class with stages `ingest`, `adjustments`, `classify`, `reservations`, `curves`,
`optimise` (closing loop around `solve`), `chargeback` and `render`, and a manifest
writer. It reads only `DATA_DIR` and writes only `OUT_DIR`.

## Ordered plan

1. Read the rulebook, layouts and contract. 2. Build the PDF and xlsx readers and confirm
the tables. 3. Ingest, dedupe, replay. 4. Merge ledger with instants and cycles.
5. Scope, exclusions, units, reservations, load. 6. Curves and optimum. 7. Commitment
rounds. 8. Reports and manifest. 9. Rerun on edited copies.

## Pitfalls

Reading streams in file order; splitting text on `BT`/`ET` inside strings such as
`(ETLX)`; treating serials as 1900-based; picking the latest adoption regardless of date;
applying errata in table order; resolving merges once per token; rounding once at the
end; pricing only units above the tier or leaving the discounted rate unrounded;
skipping or batching commitment closures; summing rounded pool savings for the total.

## Provenance

Solvable from `instruction.md` and `environment/data/` alone: every rule above is
written in the rulebook, layouts or contract with a worked example, and every value is
in the shipped files. The checks grade only what the instruction and the contract ask
for. No shortcut scores: echoing the shipped answers fails every held-out corpus and
fires the hardcoding detector.
