# STACKING_CHECK: data-product-config-compiler (13a9939)

Started from `tools/stacking_check.py` (24 Oct 20:42 IST, exit 0); every hint below was checked against `tests/test_output.py` and corrected where the static parser could not see the code.

## (a) Test rows

Reflex program = the repaired oracle tool with all three wrong readings of WORK/COST_TABLE.md injected together (the PREMORTEM first-write program); it scores 25/125.

| test | w | input | observable | decisive logic | levers whose misread fails it | reflex program |
|---|---|---|---|---|---|---|
| catalog_status | 3 | delivered /app/out, shipped release | config.json: status, owner, tier per product | _check_status: dict-by-id equality, first differing path | none (graded work) | pass |
| catalog_status_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | config.json: status, owner, tier per product | _check_status: dict-by-id equality, first differing path | LV-CC-1, LV-CC-4 | fail |
| team | 3 | delivered /app/out, shipped release | config.json: team per product | _check_team: dict-by-id equality | none (graded work) | pass |
| team_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | config.json: team per product | _check_team: dict-by-id equality | LV-CC-1, LV-CC-4 | fail |
| settings_int | 3 | delivered /app/out, shipped release | config.json settings: weight, retention_days, replicas, partitions, freshness_sla_min per product | _check_settings_int: dict-by-id equality | LV-CC-2 | fail |
| settings_int_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | config.json settings: weight, retention_days, replicas, partitions, freshness_sla_min per product | _check_settings_int: dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| settings_other | 3 | delivered /app/out, shipped release | config.json settings: pii_scan, alerts_enabled, encryption, notify, tags, cost_center per product | _check_settings_other: dict-by-id equality | LV-CC-2 | fail |
| settings_other_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | config.json settings: pii_scan, alerts_enabled, encryption, notify, tags, cost_center per product | _check_settings_other: dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| config_quota | 3 | delivered /app/out, shipped release | config.json header + quota per product | _check_quota: header and dict-by-id equality | LV-CC-2 | fail |
| config_quota_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | config.json header + quota per product | _check_quota: header and dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| dev_deploy | 3 | delivered /app/out, shipped release | profile_dev.json: alerts_enabled, pii_scan, replicas per active product | _check_deploy: dict-by-id equality | LV-CC-2 | fail |
| dev_deploy_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | profile_dev.json: alerts_enabled, pii_scan, replicas per active product | _check_deploy: dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| dev_quota | 3 | delivered /app/out, shipped release | profile_dev.json header + quota per product | _check_quota: header and dict-by-id equality | LV-CC-2 | fail |
| dev_quota_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | profile_dev.json header + quota per product | _check_quota: header and dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| prod_deploy | 3 | delivered /app/out, shipped release | profile_prod.json: alerts_enabled, pii_scan, replicas per active product | _check_deploy: dict-by-id equality | LV-CC-2 | fail |
| prod_deploy_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | profile_prod.json: alerts_enabled, pii_scan, replicas per active product | _check_deploy: dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| prod_quota | 3 | delivered /app/out, shipped release | profile_prod.json header + quota per product | _check_quota: header and dict-by-id equality | LV-CC-2 | fail |
| prod_quota_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | profile_prod.json header + quota per product | _check_quota: header and dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| rejected_overrides | 3 | delivered /app/out, shipped release | validation_report.json whole document | _check_document: parsed JSON equality, first differing path | LV-CC-2 | fail |
| rejected_overrides_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | validation_report.json whole document | _check_document: parsed JSON equality, first differing path | LV-CC-2, LV-CC-4 | fail |
| summary | 3 | delivered /app/out, shipped release | summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-CC-2 | fail |
| summary_hard | 5 | fresh hidden release (seed 318907, nobody, renamed dir, foreign cwd) | summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| report_run | 3 | delivered /app/out, shipped release | report.json: ok, tool, sha256 of the five delivered documents | _check_report: field equality | none (graded work) | pass |
| date_shift | 5 | hidden release compiled for D+45 days | config.json status + team per product | _check_date_shift: dict-by-id equality | LV-CC-1, LV-CC-4 | fail |
| quota_rescale | 5 | hidden release with cluster quotas x3 plus offset | quota column of config.json, profile_dev.json, profile_prod.json | _check_quota_rescale: dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| shuffled_relocated | 5 | hidden release, overrides and owners.csv rows shuffled, renamed dir | config.json integer settings | _check_shuffled: dict-by-id equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| missing_input | 3 | hidden release with two inputs removed | exit status + stderr line + no document | _expect_error: exit 2, `error: missing input <first>` | none (graded work) | pass |
| invalid_date | 3 | hidden release, impossible --date | exit status + stderr line + no document | _expect_error: exit 2, `error: invalid date <value>` | none (graded work) | pass |
| catalog_mismatch | 3 | hidden release, two ids dropped from manifest catalog | exit status + stderr line + no document | _expect_error: exit 3, smallest dropped id | none (graded work) | pass |
| determinism | 3 | two runs on the hidden release | bytes of the five documents | _check_determinism: byte identity, non-empty | none (graded work) | pass |
| readonly_inputs | 3 | hidden release in read-only (555/444) renamed dir, nobody, /tmp cwd | config.json whole document | _check_read_only: parsed JSON equality | LV-CC-1, LV-CC-2, LV-CC-4 | fail |
| document_format | 3 | hidden release run | bytes of each document vs json.dumps(indent=2, sort_keys=True) | _check_format: byte equality | none (graded work) | pass |
| tool_zip_layout | 1 | delivered /app/out/tool.zip | archive namelist | _check_layout: cli.py at root | none (graded work) | pass |
| negative_hardcoded_sample_answers | -5 | hidden release run | config.json release | _check_restates_shipped: equals shipped release where fresh differs | none (graded work) | n/a (does not fire) |

TS-26 hint corrected: the tool paired each `<family>` with `<family>_hard` and grouped the ten extra checks because it keys on helper names and the shared `_holds` format string. By reading the code: `<family>` reads the delivered shipped-release document in /app/out and `<family>_hard` reads the document written by the delivered tool.zip on a fresh release from another seed and scale, so the observables differ (QC_RULINGS district-heat v3:185 PASS). The ten extra checks call ten different helpers on different inputs (shifted date, rescaled quotas, shuffled rows, removed inputs, impossible date, short catalog, two runs, read-only folder, byte format, archive listing) and observe different things. No two rows share both observable and logic.
TS-13: every check makes one comparison (one equality, or one exit-status-plus-line rejection); the tool found no multi-assert hint.

## (b) Penalty groups by act (tests + judge)

| act | tests | judge | sum abs w | result |
|---|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | none | 5 | PASS |
| claiming a check passed with no run after the last edit that shows it | none | R11 -3 | 3 | PASS |
| opening /tests/ or /logs/verifier | none | R12 -5 | 5 | PASS |

No negative grades a lever: none fires on the oracle or on any cost-table or rule-coverage mutant (every run reports no negative fired).

## (c) Weight shares and caps

- Positive test weight 125, negative -5; judge positive 28, negatives -8; 12 criteria, mode batched.
- Hidden or mutated reruns (11 `_hard` w5 + date_shift, quota_rescale, shuffled_relocated w5 + missing_input, invalid_date, catalog_mismatch, determinism, readonly_inputs, document_format w3): 88 / 125 = 70.4% (>= 30%, G3 PASS). The tool's 12.0% counts only checks it could classify as whole-document or format; the row-owned `_hard` families and the mutation checks also run the delivered tool on hidden corpora.
- Every downstream document family (config.json, profile_dev.json, profile_prod.json, validation_report.json, summary.json) has a hidden version (G3); report.json is graded on the delivered run only.
- Whole-document checks (rejected_overrides, summary visible + hard, readonly_inputs): 19 / 125 = 15.2%; row-owned family checks (nine families, visible + hard): 72 / 125 = 57.6%; shipped-only (visible families + report_run + tool_zip_layout): 37 / 125 = 29.6% (no cap).
- Tests 34 (no cap; kit floor 10), criteria 12 (>= 8). One weight-1 check (tool_zip_layout, existence only, TS-20). J1 hint on R8 is the code-quality line limit (150 lines), not an output figure.

## (d) Cost table (G10)

From `WORK/COST_TABLE.md` (rubric assumed 90):

| lever | alone lost | all but this right overall | one fact wrong tests score | gate |
|---|---|---|---|---|
| LV-CC-1 | 54.4% | 67.8 | 45.6% | PASS |
| LV-CC-2 | 68.0% | 61.0 | 74.4% | PASS |
| LV-CC-4 | 58.4% | 65.8 | 41.6% | PASS |

Every lever alone >= 25% (lowest 54.4%); every all-but-one overall < 70 (highest 67.8).

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 47 rule rows, 0 rows with 0 tests failed.

STACKING PASS

## Lessons for the master
- stacking_check.py G3 counts only whole-document, mutation and format classes, so row-owned `_hard` families read as 12% | template_change: tools/stacking_check.py:264 count `_hard` names as hidden reruns.
