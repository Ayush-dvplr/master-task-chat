# Saved cache advisor query pack (plan QA26-Q4)

This is the pack the platform team ran to publish `cache_plan_published.csv`. The
pricing committee has since found that the published plan disagrees with Bulletin
Q4-26 and the capacity workbook, and tenants raised the tickets in
`ops_tickets.ndjson`. No query in this pack is known to be right. It is kept so the
published figures can be explained and compared, not as a model of the correct
computation.

## Q01 load query logs

```sql
CREATE TEMP VIEW qlog_all AS
SELECT query_id, started, project_id, cluster, template_id, wh_size, scanned,
       cache_option, query_status, revision
FROM query_log                -- every *.jsonl, *.csv, *.xml ... in the data folder
WHERE cache_option <> 'B';
```

## Q02 latest revision

```sql
CREATE TEMP VIEW qlog_live AS
SELECT * FROM qlog_all q
WHERE query_status = 'F'
  AND revision = (SELECT MAX(revision) FROM qlog_all x
                  WHERE x.query_id = q.query_id AND x.query_status = 'F');
```

## Q03 scanned volume

```sql
-- every export reports GiB
UPDATE qlog_live SET scanned_gib = CAST(scanned AS REAL);
```

## Q04 lookback window

```sql
DELETE FROM qlog_live
WHERE started < '2026-09-14T00:00:00Z' OR started >= '2026-09-28T00:00:00Z';
-- local collectors (psv, kv, yml) write wall time; treated as UTC
```

## Q05 projects

```sql
UPDATE qlog_live SET project_id = COALESCE((SELECT merged_into FROM merges WHERE from_project = project_id), project_id);
-- merged_on ignored: every ledger row applied from the start of the lookback
CREATE TEMP VIEW registry AS
SELECT * FROM proj_registry_archive UNION SELECT * FROM proj_registry_main;   -- archive listed first wins
DELETE FROM qlog_live WHERE project_id NOT IN (SELECT project_id FROM registry WHERE status <> 'Closed');
-- dev projects: tier column of the registry
```

## Q06 adjustments

```sql
INSERT INTO adjustments SELECT * FROM scan_adjustments WHERE status IN ('POSTED', 'PENDING');
-- late desk XML arrives after the plan freeze; skipped
```

## Q07 family and normalization

```sql
UPDATE qlog_live SET family = LOWER(SUBSTR(template_id, 1, INSTR(template_id, '-') - 1));
UPDATE qlog_live SET units = scanned_gib * (SELECT factor FROM engine_factor_hint WHERE size = wh_size);
-- units kept at full precision; hourly sums rounded at the end
```

## Q08 existing reservations

```sql
DELETE FROM qlog_live WHERE cache_option = 'C';           -- already cached
CREATE TEMP VIEW netted AS
SELECT family, cluster, SUM(units) AS units FROM cache_reservations
WHERE state IN ('ACTIVE', 'QUEUED') GROUP BY family, cluster;   -- every reservation, any end date
```

## Q09 growth

```sql
UPDATE pool_hour SET load = MAX(0, usage - netted.units) * (100 + growth_pct) / 100.0;
```

## Q10 hours

```sql
-- hours with no query rows do not exist in pool_hour; outage windows are not removed
SELECT pool_id, COUNT(*) AS hours FROM pool_hour GROUP BY pool_id;
```

## Q11 rates

```sql
SELECT family, scan_rate, node_rate FROM scan_rates_digest_draft;   -- flat rates, all clusters
-- bulletin errata are pending review; not applied
```

## Q12 limits

```sql
SELECT 'node_cap_total', value FROM capacity_announce_oct WHERE key = 'approved_nodes';
SELECT * FROM workbook_sheet('DRAFT_RS-C4C');                 -- family limits and node sizes
-- Adoptions sheet: latest row of the track, read as 1900 serials
-- memory budget: not enforced this quarter (announcement)
```

## Q13 optimiser

```sql
-- buy one node at a time in the pool with the best next-node saving until the
-- approved nodes run out; family limits, minimum purchases and memory are checked later
-- cluster commitments: Table M-0 checked once, every short cluster dropped together
```

## Q14 volume tier

```sql
-- tier discount applies to the cache units above tier_units only
-- RETAG adjustments ignored
UPDATE plan SET node_cost = node_rate * LEAST(units, tier_units)
                          + node_rate * (1 - tier_discount_pct / 100.0) * GREATEST(units - tier_units, 0);
```

## Q15 rounding and chargeback

```sql
SELECT pool_id, ROUND(saving, 0) AS saving_cents FROM plan;    -- half up
SELECT SUM(saving_cents) AS total_saving_cents FROM plan;
-- chargeback: saving_cents split by team, remainder to the last team
```
