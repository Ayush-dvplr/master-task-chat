# Saved readout query pack WAVE-26Q3 (analytics workspace export)

Saved queries behind `readout_published.csv`. They ran against a staging warehouse where
every feed had been loaded into `exposures`, `orders`, `refunds` and lookup tables. The
pack is kept for reference; it is not a specification.

```sql
-- Q01 exposure source: every assignment-service export in the drop folder
CREATE TABLE exposures AS
SELECT * FROM read_files('/drop/*.{jsonl,ndjson,csv,tsv,psv,txt,xml,yaml,sqlite,json}')
WHERE stream_guess = 'exposure';            -- includes exposure_rollup_cache.jsonl

-- Q02 live exposures
SELECT * FROM exposures WHERE status IN ('ok','LIVE','A','0','live','L','valid','1','ACTIVE')
QUALIFY row_number() OVER (PARTITION BY exposure_id ORDER BY revision DESC) = 1;

-- Q03 units: one hop through the link table, link dates ignored
SELECT coalesce(l.linked_to, e.unit_token) AS unit_id, e.* FROM live_exposures e
LEFT JOIN identity_links l ON l.from_id = e.unit_token;

-- Q04 analysis window in UTC from the readout calendar
SELECT * FROM live_exposures e JOIN calendar c USING (experiment)
WHERE e.ts_utc BETWEEN c.start_utc AND c.end_utc;

-- Q05 arm of a unit: the arm of its first exposure
SELECT unit_id, experiment, first_value(arm) OVER w AS arm, min(ts_utc) OVER w AS fe
FROM windowed WINDOW w AS (PARTITION BY unit_id, experiment ORDER BY ts_utc);

-- Q06 bots: legacy registry plus the security watchlist
DELETE FROM units WHERE unit_id IN (SELECT UNIT FROM legacy_registry WHERE AccountType='bot')
                     OR unit_id IN (SELECT token FROM bot_watchlist);

-- Q07 revenue in USD at the dashboard snapshot, amounts treated as cents
SELECT order_id, amount / 100.0 * s.rate AS usd FROM orders JOIN fx_snapshot s USING (currency);

-- Q08 refunds: early journal only, every row regardless of status; reversals subtract their amount
SELECT order_id, sum(CASE WHEN kind ILIKE 'reversal' THEN -amount_minor ELSE amount_minor END)
FROM refunds_jsonl GROUP BY order_id;

-- Q09 metric windows: 14 days for every metric, no maturity filter
SELECT * FROM orders o JOIN assignments a ON o.unit_id = a.unit_id
 AND o.ts_utc >= a.fe AND o.ts_utc < a.fe + INTERVAL 14 DAY;

-- Q10 winsorization: per arm, interpolated 99th percentile
SELECT arm, percentile_cont(0.99) WITHIN GROUP (ORDER BY rev14) FROM unit_values GROUP BY arm;

-- Q11 CUPED: theta fitted inside each arm, full precision
SELECT arm, covar_samp(rev14, pre_rev) / var_samp(pre_rev) AS theta FROM unit_values GROUP BY arm;

-- Q12 test: pooled-variance z test, population variances
SELECT (avg_t - avg_c) / sqrt(var_pop_pooled * (1.0/n_t + 1.0/n_c)) AS z FROM arm_stats;

-- Q13 SRM: equal split over control and treatment arms only
SELECT experiment, chi2_equal_split(n_by_arm) FROM arm_counts WHERE role <> 'holdout';

-- Q14 multiple testing: none; significant when p < 0.10 (digest)
SELECT *, p_value < 0.10 AS significant FROM tests;

-- Q15 registry: sheet MR-6, memo amendments not loaded; FX from the first FX sheet found
SELECT * FROM xlsx_sheet('experiment_workbook_w26.xlsx', 'MR-6');
SELECT * FROM xlsx_sheet('experiment_workbook_w26.xlsx', 'FX-R1');

-- Q16 relative lift over the treatment mean
SELECT 100.0 * diff / mean_t AS lift_pct FROM tests;

-- Q17 launch: every significant positive arm ships, no capacity check
SELECT experiment, arm, 'SHIP' FROM tests WHERE role = 'primary' AND significant AND diff > 0;

-- Q18 CHF: treated like the other per-dollar quotes
SELECT order_id, amount / rate AS usd FROM orders JOIN fx USING (currency) WHERE currency = 'CHF';
```
