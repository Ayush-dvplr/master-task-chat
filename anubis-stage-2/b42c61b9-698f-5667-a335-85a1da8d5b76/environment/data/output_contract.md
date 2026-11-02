# Output contract for the corrected readout

The corrected run writes the files below into one output directory. Names are exact.
Rules referenced as H-something are in `readout_analysis_handbook.md`.

General rules:

- Text files are UTF-8 with `\n` line endings and end with a newline.
- JSON files hold one document with sorted keys. JSON Lines files hold one object per
  line with sorted keys.
- Delimited files carry the header shown and no quoting beyond what the delimiter
  forces.
- Counts, hops, days and sequence numbers are integers. Money is US dollars. Means,
  differences, variances, standard errors, intervals, caps, thetas, z values, chi-square
  values, lifts and USD amounts are written with exactly six decimals (`12.500000`,
  `-0.031250`); a value that rounds to zero is written without a minus sign. P-values
  and q-values are written in exponent form with six digits after the point
  (`3.141593e-04`, Python `format(x, ".6e")`). Percent settings (`winsor_pct`,
  `weight_pct`, margins) are written as the source prints them.
- In JSON and JSON Lines files a figure written with six decimals or in exponent form is a
  JSON string (`"12.500000"`, `"3.141593e-04"`), and a count, hop, day or sequence number
  is a JSON integer.
- Rounding. Every six-decimal figure that is an exact rational number of the
  computation is rounded half to even from its exact value: means, adjusted means,
  differences, variances (the ratio metric's `R` and `V` included), caps, theta,
  `mean_x`, `variance_reduction_pct`, expected counts, chi-square values, relative
  lifts `100 x diff / base`, and USD amounts. Example: an exact 0.0078125 is written
  0.007812 and an exact 0.0078135 is written 0.007814. A figure that passes through a
  square root, the normal quantile, `erfc` or `exp` (`se`, `z`, `ci_low`, `ci_high`,
  `lift_ci_low`, `lift_ci_high`, p-values and q-values) is computed in IEEE double
  precision from the double values of its inputs, following the formulas of H11 to H13
  in the order they are written, and the resulting double is formatted. Every output
  is compared exactly as text after parsing the file format; there is no tolerance.
- A value that does not apply is an empty field (delimited files) or `null` (JSON).
- Times are `YYYY-MM-DDTHH:MM:SSZ` in UTC. Ids follow H1.
- Experiments are ordered by code, arms by name, metrics by code, units by id.

## readout.csv

Header `experiment,arm,metric,role,n_control,n_treatment,mean_control,mean_treatment,diff,lift_pct,se,z,p_value,ci_low,ci_high,q_value,significant`.
One row per analysed experiment, treatment arm and registry metric. `role` is `primary`
for the experiment's primary metric and the registry role otherwise. `mean_*` are the
arm means of `Y_adj` (`R` for a ratio metric). `q_value` is set only for primary tests in
the family (H13.1). `significant` is `Y` or `N`, and empty for the primary test of an
experiment that fails the sample ratio check.

## arm_metrics.tsv

Header `experiment	arm	metric	n	raw_mean	adj_mean	variance` (tab separated). One
row per analysed experiment, analysed arm and registry metric. `raw_mean` is the mean of
the winsorized unadjusted value (`R` for a ratio metric), `adj_mean` the mean of
`Y_adj` (`R` again for ratio), `variance` the sample variance of `Y_adj` (the delta-method
variance `V` for a ratio metric).

## winsor_caps.psv

Header `experiment|metric|winsor_pct|n_pooled|cap|covariate_cap|capped_units`. One row
per analysed experiment and winsorized metric. `covariate_cap` is empty when the metric
is not CUPED adjusted. `capped_units` counts pooled participants whose value is above
the cap.

## cuped.json

Object keyed by experiment, then by metric, for every CUPED-adjusted metric:
`theta`, `mean_x` (pooled covariate mean after winsorization), `variance_reduction_pct`
(`100 x (1 - var(Y_adj) / var(Y))` over the pooled participants, six decimals).

## srm_report.csv

Header `experiment,arm,role,weight_pct,observed,expected,chi2,dof,p_value,status`. One
row per analysed experiment and arm (holdout included). `chi2`, `dof`, `p_value` and
`status` (`PASS` or `FAIL`) are the experiment's and repeat on each of its rows.

## bh_family.csv

Header `rank,experiment,arm,metric,p_value,q_value,significant`. One row per primary
family member in rank order (H13.1).

## guardrails.csv

Header `experiment,arm,metric,lift_pct,lift_ci_low,lift_ci_high,margin_pct,breach`. One
row per analysed experiment, treatment arm and guardrail metric. `breach` is `Y` or `N`.

## decisions.json

Object keyed by experiment, then by treatment arm, for every in-scope experiment
(aborted included): `decision`, `primary_metric`, `q_value` (or null),
`guardrail_breaches` (sorted list of breached metrics). `decision` is the decision after
the ship capacity pass of H13.5: `ABORTED`, `INVALID_SRM`, `NO_SHIP_GUARDRAIL`, `SHIP`,
`SHIP_DEFERRED`, `NO_SHIP` or `INCONCLUSIVE`.

## unit_assignments.csv

Header `experiment,unit_id,arm,first_exposure_utc,exposures`. One row per participant
(H7). `exposures` counts the participant's exposures of H7.1.

## excluded_units.jsonl

One object per participant candidate that is not a participant: `experiment`,
`unit_id`, `reason` (H7.2), ordered by experiment then unit.

## identity_resolution.csv

Header `from_id,unit_id,hops`. One row per `from_id` of the link ledger, sorted, each
resolved at `data_cutoff_utc` (H1.5).

## dedup_report.json

Keys `exposure` and `order`. `exposure` holds `rows_read`, `duplicate_rows_dropped`,
`voided`, `live`, `out_of_scope`, `unmapped_variant`; `order` holds `rows_read`,
`duplicate_rows_dropped`, `cancelled`, `live` (H3).

## source_lineage.json

Object keyed by shard file name with `stream`, `rows` (data rows read) and `kept`
(H3.3), for every listed shard.

## refund_outcomes.jsonl

One object per applied journal entry (status POSTED) in the order applied: keys
`journal` (`jsonl` or `xml`), `seq`, `kind` (`refund` or `reversal`, lower case),
`refund_id`, `order_id`, `outcome` (H8.2: `AFTER_CUTOFF`, `NO_ORDER`,
`ORDER_CANCELLED`, `REVERSED`, `NOTHING_TO_REVERSE`, `REPLACED` or `APPLIED`).

## order_valuation.psv

Header `order_id|unit_id|currency|amount_minor|refund_minor|net_minor|fx_date|usd_net|usd_refunded`.
One row per live order placed before the data cutoff, sorted by order id. `unit_id` is the
unit at the order's placed time (H8.1). `fx_date` is the date of the order currency's own
fixing (for a currency quoted per euro, not the EUR fixing's date) and is empty for USD.

## metric_config_used.json

Object keyed by analysed experiment, then by metric: `kind`, `attribution_days`,
`winsor_pct` (string or null), `cuped` (boolean, true only with a covariate),
`covariate` (or null), `role`, `higher_is_better` (boolean), `numerator`,
`denominator` (or null), and `amendments`: the ids of the Table A-1 amendments applied
to that experiment and metric, in the order applied. Also keys `registry_version` and
`fx_sheet` at the top level holding the sheet names applied.

## experiment_windows.xml

Root `<portfolio id="...">` with one `<experiment>` element per in-scope experiment in
code order, attributes `code`, `tz_offset`, `owner_team`, `start_utc`, `end_utc`,
`ruling` (`CONFIRMED`, `EXTENDED`, `SHORTENED`, `ABORTED` or `NONE`), `status`
(`ANALYSED` or `ABORTED`).

## portfolio_summary.json

Keys `portfolio_id`, `registry_version`, `experiments_analysed`, `experiments_aborted`,
`srm_failures`, `family_size`, `decisions` (object: each decision, after H13.5, that at
least one treatment arm received, mapped to its count of treatment arms; a decision no
arm received is left out), `deferred_arms` (sorted list of `EXPERIMENT/ARM` strings decided
`SHIP_DEFERRED`), `participants`, `excluded_candidates`, `live_orders`, `usd_net_total` (six
decimals, over `order_valuation.psv`).

## variance_vs_published.csv

Header `experiment,arm,metric,published_diff,corrected_diff,published_significant,corrected_significant,status`.
One row per key (experiment, arm, metric) of the published readout's `ALL` cut or of
`readout.csv`. Status `NEW` (corrected only), `DROPPED` (published only), `FLIPPED`
(significance differs) or `SAME`. A corrected significance that is empty compares as
`N`.

## reconciliation.md

A title line `# Portfolio <portfolio_id> readout reconciliation`, a blank line, then a
markdown table: the header `| experiment | arm | published_decision | corrected_decision |`,
the separator line `|---|---|---|---|`, and one row per treatment arm of every in-scope
experiment. The published decision is read
from the published readout's `ALL` cut of the experiment's primary metric: `SHIP` when
significant `Y` with a positive diff, `NO_SHIP` when significant `Y` otherwise,
`INCONCLUSIVE` when `N`, and `MISSING` when there is no such row.

## manifest.json

Key `files`: a list, in the order of this contract (`readout.csv` first,
`reconciliation.md` last), of objects with `name`, `bytes` and `sha256` (lower-case hex)
of every other output file.
