# LEVERS: data-product-config-compiler

Lever ids per check come from the measured cost table: a check carries a lever when that lever's wrong reading alone fails it (`WORK/cost_table.py`).

Counted levers (Harden round 1): NL-1 assignment on D (latest active_from), NL-3 quota_cap re-share, NL-4 text-layer type reading. The build levers LV-CC-1, LV-CC-2, LV-CC-4 stay as background rules (their giveaway wording removed) and are listed in the last column; they are not counted.

| check | weight | levers | graded property | background |
|---|---|---|---|---|
| status_team | 3 | none (graded work) | status, owner, tier, team per product (shipped release) | - |
| status_team_hard | 5 | NL-1 | status, owner, tier, team per product (hidden release) | LV-CC-1, LV-CC-4 |
| settings_int | 3 | NL-4 | integer settings per product (shipped release) | LV-CC-2 |
| settings_int_hard | 5 | NL-1, NL-4 | integer settings per product (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| settings_other | 3 | NL-4 | boolean, enum, list, string settings per product (shipped release) | LV-CC-2 |
| settings_other_hard | 5 | NL-1, NL-4 | boolean, enum, list, string settings per product (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| config_quota | 3 | none (graded work) | config.json quota per product (shipped release) | LV-CC-2 |
| config_quota_hard | 5 | NL-3 | config.json quota per product (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| dev_deploy | 3 | NL-4 | profile_dev.json deploy keys (shipped release) | LV-CC-2 |
| dev_deploy_hard | 5 | NL-1, NL-4 | profile_dev.json deploy keys (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| dev_quota | 3 | NL-4 | profile_dev.json quota per product (shipped release) | LV-CC-2 |
| dev_quota_hard | 5 | NL-3, NL-4 | profile_dev.json quota per product (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| prod_deploy | 3 | NL-4 | profile_prod.json deploy keys (shipped release) | LV-CC-2 |
| prod_deploy_hard | 5 | NL-1, NL-4 | profile_prod.json deploy keys (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| prod_quota | 3 | NL-4 | profile_prod.json quota per product (shipped release) | LV-CC-2 |
| prod_quota_hard | 5 | NL-3, NL-4 | profile_prod.json quota per product (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| rejected_overrides | 3 | none (graded work) | validation_report.json (shipped release) | LV-CC-2 |
| rejected_overrides_hard | 5 | none (graded work) | validation_report.json (hidden release) | LV-CC-2, LV-CC-4 |
| summary | 3 | none (graded work) | summary.json (shipped release) | LV-CC-2 |
| summary_hard | 5 | NL-1 | summary.json (hidden release) | LV-CC-1, LV-CC-2, LV-CC-4 |
| report_run | 1 | none (graded work) | report run | - |
| date_shift | 5 | NL-1 | date shift | LV-CC-1, LV-CC-4 |
| quota_rescale | 5 | NL-3, NL-4 | quota rescale | LV-CC-1, LV-CC-2, LV-CC-4 |
| shuffled_relocated | 5 | NL-4 | shuffled relocated | LV-CC-1, LV-CC-2, LV-CC-4 |
| missing_input | 1 | none (graded work) | missing input | - |
| invalid_date | 1 | none (graded work) | invalid date | - |
| catalog_mismatch | 1 | none (graded work) | catalog mismatch | - |
| determinism | 1 | none (graded work) | determinism | - |
| config_quota_capped | 5 | NL-3 | config quota capped | LV-CC-1, LV-CC-2, LV-CC-4 |
| dev_quota_capped | 5 | NL-3, NL-4 | dev quota capped | LV-CC-1, LV-CC-2, LV-CC-4 |
| prod_quota_capped | 5 | NL-3, NL-4 | prod quota capped | LV-CC-1, LV-CC-2, LV-CC-4 |
| readonly_inputs | 3 | NL-1, NL-3, NL-4 | readonly inputs | LV-CC-1, LV-CC-2, LV-CC-4 |
| document_format | 1 | none (graded work) | document format | - |
| tool_zip_layout | 1 | none (graded work) | tool zip layout | - |
| negative_hardcoded_sample_answers | -5 | none (graded work) | negative hardcoded sample answers | - |

| lever | positive weight carried | share of P = 120 |
|---|---|---|
| NL-1 | 38 | 31.7% |
| NL-3 | 38 | 31.7% |
| NL-4 | 71 | 59.2% |

Checks: 35. Positive weight: 120. Negative: negative_hardcoded_sample_answers -5.

## Lessons for the master
- Deriving lever columns from measured failures keeps LEVERS.md and COST_TABLE.md in step | no change: script reads cost_table.json.
