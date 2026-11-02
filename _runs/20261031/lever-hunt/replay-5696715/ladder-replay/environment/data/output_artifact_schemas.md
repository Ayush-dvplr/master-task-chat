# Output Artifact Schemas

## Reusable program

`settle.py` is a Python 3.12 standard-library program. Invoke it as
`python3 settle.py DATA_DIR OUT_DIR`. It reads the complete contract and corpus
from `DATA_DIR`, creates `OUT_DIR` if needed, and overwrites the twenty-nine data
artifacts defined below. It must not read a fixed `/app/data` path when another
`DATA_DIR` is supplied. A valid corpus has the same filenames and schemas as this
one, but its rows, dates, workbook sheet order, generated identifiers, and the
authoritative constants inside the selected LIVE sheet, PDF, and DOCX may differ.
Read those sources for every run rather than embedding values from this corpus.
The program writes no undeclared files.

This file is part of the written contract. It fixes the EXACT shape of every
artifact the settlement writes under /app/out: the column headers of each
delimited table, the key names of each JSON object, the line layout of each
text and XML file, and the row order. Only names and layout are given here;
every number must be computed from the inputs per the stage specs, so no
value is leaked. All files use UTF-8, line-feed endings and a trailing
newline. JSON objects are emitted with two-space indentation and keys sorted
lexicographically, so key order in the file is alphabetical regardless of the
order listed below. Decimals are emitted as strings at the stated precision.
Delimited rows are sorted by match_key ascending, or listed in the fixed
stratum order below when the row key is a stratum.

Fixed stratum order (used for every per-stratum row and per-stratum key):
BRONZE-NA, BRONZE-EU, BRONZE-APAC, SILVER-NA, SILVER-EU, SILVER-APAC,
GOLD-NA, GOLD-EU, GOLD-APAC.

Per-stratum metrics filename slugs:
BRONZE-NA to metrics_bro_na.json, BRONZE-EU to metrics_bro_eu.json,
BRONZE-APAC to metrics_bro_ap.json, SILVER-NA to metrics_sil_na.json,
SILVER-EU to metrics_sil_eu.json, SILVER-APAC to metrics_sil_ap.json,
GOLD-NA to metrics_gld_na.json, GOLD-EU to metrics_gld_eu.json,
GOLD-APAC to metrics_gld_ap.json.

## population.csv
Comma-separated. Header row, then one row per surviving match key sorted by
match_key ascending. Columns in this exact order:
match_key, account_id, stratum, drawn, loot_currency, anchor_date

## weights.csv
Comma-separated. Header row, then one row per resolved-and-drawn match sorted
by match_key ascending. Columns in this exact order:
match_key, stratum, y, yhat, loot_currency, ledger_units, p_eff, p_cal, weight
ledger_units is an integer ledger amount. p_eff and p_cal are strings with
eight decimals; weight is a string with six decimals.

## payout.csv
Comma-separated. Header row, then one row per stratum in the fixed stratum
order, then a final row whose first field is TOTAL carrying the column sums.
Columns in this exact order:
stratum, rewarded_credits, forfeited_credits, review_credits, levy_credits, net_credits

## payout_breakdown.tsv
Tab-separated. Header row, then one row per stratum in the fixed stratum
order. Columns in this exact order:
stratum, rewarded_credits, forfeited_credits

## payout_ledger.psv
Pipe-separated. Header row, then one row per stratum in the fixed stratum
order. Columns in this exact order:
stratum, review_credits, levy_credits, net_credits

## forfeited_shares.csv
Comma-separated. Header row, then one row per stratum in the fixed stratum
order. Columns in this exact order:
stratum, forfeited_credits, share_bps

## confidence_intervals.csv
Comma-separated. Header row, then one row per stratum in the fixed stratum
order. Columns in this exact order:
stratum, recall_lo, recall_hi, prec_lo, prec_hi, n_eff_recall, n_eff_precision
All six numeric columns are strings with six decimals.

## metrics.json
JSON object with exactly two keys, overall and strata. overall is an object
with keys precision, recall, fbeta, macro_precision, macro_recall. strata is
an object keyed by stratum name, each value an object with keys precision,
recall, fbeta. Every value is a six-decimal string.

## metrics_<slug>.json (nine files, one per stratum)
JSON object with keys stratum, precision, recall, fbeta, tp, fp, fn. stratum
is the stratum name; precision, recall and fbeta are six-decimal strings; tp,
fp and fn are six-decimal strings of the weighted counts.

## stratum_metrics_stream.jsonl
One JSON object per line, one per stratum in the fixed stratum order, each
with keys stratum, precision, recall, fbeta (six-decimal strings). The file
ends with a trailing newline.

## overall_metrics.md
Markdown. First line is a level-one heading reading Overall Settled Metrics,
then a blank line, then one bullet line per figure in this order: precision,
recall, fbeta, macro_precision, macro_recall, each written as `- name: value`.

## reconciliation_report.md
Markdown. First line is a level-one heading reading Settlement Reconciliation
Report, then a blank line, then one bullet line each in this order:
population, resolved, weighted, total_net_credits, calibration_version, each
written as `- name: value`.

## rollup.xml
XML. An xml declaration line, then a rollup root element holding one stratum
element per stratum in the fixed stratum order. Each stratum element carries
an id attribute of the stratum name and child elements precision, recall and
fbeta with six-decimal string text.

## label_distribution.json
JSON object with keys positive, negative, resolved_total, population_total,
all integer counts.

## decision_distribution.json
JSON object with keys flagged, cleared, weighted_total, all integer counts.

## frame_counts.json
JSON object with keys population_by_stratum, sampled_by_stratum,
resolved_weighted. Each value is an object keyed by stratum name with integer
counts.

## weight_diagnostics.json
JSON object with keys weight_sum_by_stratum, cap, max_weight.
weight_sum_by_stratum is an object keyed by stratum name with six-decimal
string sums. cap is the weight cap as a string. max_weight is a six-decimal
string.

## net_payout_summary.json
JSON object with keys total_rewarded_credits, total_forfeited_credits,
total_review_credits, total_levy_credits, total_net_credits (integers) and
by_stratum, an object keyed by stratum name with the integer net_credits.

## levy_summary.json
JSON object with keys levy_bps (integer), settlement_floor (integer),
total_levy_credits (integer), levy_by_stratum (object keyed by stratum name
with integer levy credits) and floored_strata (a list of the stratum names
whose pre-floor net fell below the floor, sorted ascending).

## audit_summary.json
JSON object with keys population, resolved, weighted, flagged (integer
counts), overall_fbeta (six-decimal string) and calibration_version (string).

## manifest.json
JSON object with keys core_order and digest_sha256. core_order is the list
population.csv, weights.csv, payout.csv, metrics.json. digest_sha256 is the
hex SHA-256 over the concatenated exact bytes of those four files in that
order.
