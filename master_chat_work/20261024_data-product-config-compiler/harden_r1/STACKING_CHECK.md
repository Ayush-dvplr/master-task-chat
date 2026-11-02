# STACKING_CHECK: data-product-config-compiler (harden r1, e317de1)

Start: `stacking_check.py <BUNDLE>` (raw output kept in `stacking_check_raw.txt` in this folder), corrected by reading `tests/test_output.py`, `WORK/assemble_tests.py` and `WORK/cost_table.json`. 35 checks, positive 120, negative -5; judge 15 criteria, positive 37, batched.

## (a) Test rows

Levers alone = the lever's full wrong reading injected alone into the oracle fails this row; one-fact = the lever's one-fact-wrong edit fails it (WORK/COST_TABLE.md). Reflex = probe agent program (OUT/agent_program) graded by the real tests/test_output.py (local rewardkit stub, oracle 120/120, nop 0/120).

| test | w | inputs | observable | decisive logic | levers alone | one-fact | reflex |
|---|---|---|---|---|---|---|---|
| status_team | 3 | shipped | config.json status/owner/tier/team columns | _check_status_team | - | - | pass |
| status_team_hard | 5 | hidden | config.json status/owner/tier/team columns | _check_status_team | NL-1 | - | FAIL |
| settings_int | 3 | shipped | config.json integer settings columns | _check_settings_int | NL-4 | - | FAIL |
| settings_int_hard | 5 | hidden | config.json integer settings columns | _check_settings_int | NL-1, NL-4 | - | FAIL |
| settings_other | 3 | shipped | config.json non-integer settings columns | _check_settings_other | NL-4 | - | FAIL |
| settings_other_hard | 5 | hidden | config.json non-integer settings columns | _check_settings_other | NL-1, NL-4 | - | FAIL |
| config_quota | 3 | shipped | config.json header + quota column | _check_quota | - | - | FAIL |
| config_quota_hard | 5 | hidden | config.json header + quota column | _check_quota | NL-3 | NL-3 | FAIL |
| dev_deploy | 3 | shipped | profile_dev.json alerts/pii/replicas | _check_deploy | NL-4 | - | FAIL |
| dev_deploy_hard | 5 | hidden | profile_dev.json alerts/pii/replicas | _check_deploy | NL-1, NL-4 | NL-4 | FAIL |
| dev_quota | 3 | shipped | profile_dev.json header + quota | _check_quota | NL-4 | - | FAIL |
| dev_quota_hard | 5 | hidden | profile_dev.json header + quota | _check_quota | NL-3, NL-4 | NL-3, NL-4 | FAIL |
| prod_deploy | 3 | shipped | profile_prod.json alerts/pii/replicas | _check_deploy | NL-4 | - | FAIL |
| prod_deploy_hard | 5 | hidden | profile_prod.json alerts/pii/replicas | _check_deploy | NL-1, NL-4 | NL-4 | FAIL |
| prod_quota | 3 | shipped | profile_prod.json header + quota | _check_quota | NL-4 | - | FAIL |
| prod_quota_hard | 5 | hidden | profile_prod.json header + quota | _check_quota | NL-3, NL-4 | - | FAIL |
| rejected_overrides | 3 | shipped | validation_report.json | _check_document | - | - | pass |
| rejected_overrides_hard | 5 | hidden | validation_report.json | _check_document | - | - | pass |
| summary | 3 | shipped | summary.json | _check_document | - | - | pass |
| summary_hard | 5 | hidden | summary.json | _check_document | NL-1 | NL-3 | FAIL |
| report_run | 1 | - | report.json after export-report | _check_report | - | - | pass |
| date_shift | 5 | - | config.json status/team, hidden files at D+45 | _check_date_shift | NL-1 | NL-1 | FAIL |
| quota_rescale | 5 | - | quota columns of 3 docs, rescaled quotas + prod default cap | _check_quota_rescale | NL-3, NL-4 | NL-3, NL-4 | FAIL |
| shuffled_relocated | 5 | - | config.json int settings, shuffled rows, relocated folder | _check_shuffled | NL-4 | - | FAIL |
| missing_input | 1 | - | exit 2 naming a deleted input | _expect_error | - | - | pass |
| invalid_date | 1 | - | exit 2 on a bad --date | _expect_error | - | - | pass |
| catalog_mismatch | 1 | - | exit 3 naming the smallest id | _expect_error | - | - | pass |
| determinism | 1 | - | two runs byte-identical | _check_determinism | - | - | pass |
| config_quota_capped | 5 | - | config.json quota, capped tier (30% caps) | _check_quota capped | NL-3 | NL-3 | FAIL |
| dev_quota_capped | 5 | - | profile_dev.json quota, capped tier | _check_quota capped | NL-3, NL-4 | NL-4 | FAIL |
| prod_quota_capped | 5 | - | profile_prod.json quota, capped tier | _check_quota capped | NL-3, NL-4 | NL-3 | FAIL |
| readonly_inputs | 3 | - | whole config.json, hidden files in read-only folder as nobody | _check_read_only | NL-1, NL-3, NL-4 | NL-3 | FAIL |
| document_format | 1 | - | indent 2, sorted keys, newline in all docs | _check_format | - | - | pass |
| tool_zip_layout | 1 | - | cli.py at zip root | _check_layout | - | - | pass |
| negative_hardcoded_sample_answers | -5 | hidden | program restates shipped answers on hidden input | _check_restates_shipped | - | - | not fired |

TS-26 by hand: the static tool groups visible, `_hard` and `_capped` rows that call the same helper. They are not duplicates: each reads a different input set (shipped files, the hidden corpus of seed 318907, the capped tier of seed 318910), and the visible row is the honest-attempt row (G1 visible then hidden). The ten rows it lumps as `%s%r: %s` are ten different helpers with different observables (table above). No two rows share both inputs and observable. TS-13: every row checks one property (one column group of one document, one whole document, or one exit code); the tool found 0 multi-assert hints.

Mutation tests (G6), classified by hand (the tool calls them hidden_rows): date_shift (date moved +45 days), quota_rescale (quotas x3 + odd amount, default prod cap), shuffled_relocated (rows shuffled, folder relocated; content mutation paired with judge R7/J9), readonly_inputs (read-only folder, run as nobody), missing_input (two inputs deleted), catalog_mismatch (catalog altered). 6 >= 2: PASS.

## (b) Penalty groups by act (AL-28)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R11 -3 | 3 | PASS |
| naming or reading grader files | - | R12 -5 | 5 | PASS |

No negative grades a lever: the -5 fires only when the program writes the shipped answers on hidden input; every lever reading leaves it unfired (cost table rows).

## (c) Weight shares (G3) and caps

- Hidden or mutated reruns: 88/120 = 73.3% (>= 30%: PASS). Hidden `_hard` rows 50, capped rows 15, date_shift/rescale/shuffled 15, readonly 3, missing/invalid/catalog/determinism/format 5 (all on the hidden corpus), counted 88 (the tool files missing/invalid/catalog as whole_doc; same total).
- Shipped-only (ten visible honest-attempt rows + report_run): 31/120 = 25.8%. Each visible row also requires the /app/out document it reads to be byte-equal to what the delivered tool writes for the shipped release (`_load`), so documents written without a working program score 2/120 (forgery run). Whole-document rows: rejected_overrides(+_hard), summary(+_hard), readonly_inputs = 19/120 = 15.8%. Isolated: tool_zip_layout 1 (0.8%). 88 + 31 + 1 = 120.
- Counts: 35 tests, 15 criteria (kit floors 10 / 8; no cap). Weights only 1, 3, 5; weight-1 rows are the seven non-core rows (report_run, missing_input, invalid_date, catalog_mismatch, determinism, document_format, tool_zip_layout): TS-20 PASS (no core check at 1).
- Judge J2 conduct (tool shows none because it matches a different phrasing): R1-R6 recompute per output family on the shipped folder and an altered copy, R7 altered copy (J9), R10 delivered zip from another folder, R13-R15 per-lever constructed inputs; solve.sh prints `check <id> ok` for R1-R7, R10, R13-R15.

## (d) Cost table (G10), from WORK/COST_TABLE.md

| lever | alone lost | >= 25% | all-but-this overall (rubric 90) | < 70 | one-fact lost |
|---|---|---|---|---|---|
| NL-1 assignment on D (H3) | 38/120 = 31.7% | PASS | 79.2 | no | 4.2% (date_shift) |
| NL-3 quota_cap re-share (H7 + COUPLING) | 38/120 = 31.7% | PASS | 79.2 | no | 27.5% (two rounds only) |
| NL-4 text-layer reading (H1) | 71/120 = 59.2% | PASS | 65.4 | yes | 20.8% (isdigit) |
| all three wrong | 96/120 = 80.0% | | 55.0 | yes | |

The all-but-one < 70 line holds for NL-4 only; NL-1 and NL-3 each cost 31.7% alone, inside the master's 25-40% band, kept honest under CL-4 rather than amplified. Differential fuzz (OUT/fuzz/cf_out_r3.jsonl, 320 valid corpora): reflex differs NL-1 88.0%, NL-3 81.8%, NL-4 100%; probe program differs 96.6%; oracle 0.

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 55 rule rows, each mutant fails at least one test; 0 rows with 0 tests failed.

## Reflex gate (section 6)

Probe agent program on the new tests: 21/120 = 0.175 (<= 0.20). Passes status_team, rejected_overrides(+_hard), summary, and the seven weight-1 rows.

STACKING PASS
