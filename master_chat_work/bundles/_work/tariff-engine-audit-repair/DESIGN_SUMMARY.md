# DESIGN SUMMARY a5f8657 tariff-engine-audit-repair (repo-patch, software-engineering, seed 583917)

Job: repair stdlib package `tariff` in /app/repo in place so it obeys /app/ci/api_contract.md (the one rule file, arbiter sentence: "When the code, its docstrings, its README or its visible tests disagree with this file, this file wins."), zip it to /app/out/patched-repo.zip, write the 6 fixed JSON notes. Hidden tests import the package from the zip only.
Spine: parse reads -> classify (malformed_quantity > unknown_meter > inactive_meter > outside_period > duplicate_read) -> tier rating -> standing-charge proration -> per-line half-even 0.01 -> commitment credit (COUPLING) -> render invoices + exceptions.
Inputs (11 files, 7 formats): api_contract.md, meter_reads.jsonl, accounts.csv, billing_periods.csv, rate_card.json, regression_cases.jsonl, failing_tests.log, lint_report.json, package_manifest.json, build_config.json; repo src/tariff/{__init__,parser,core,report,__main__}.py, tests/test_visible.py, README, pyproject.toml. 8 planted defects, each breaking one contract sentence.

| lever | rule and where | reflex reading | hidden separator |
|---|---|---|---|
| LV-TR-4 H1/L5 | contract field block "quantity: a JSON integer of 0 or more" + malformed list naming string, decimal point/exponent, true/false, null, negative; global trim rule in Conventions | keep `int(str(q).strip())` (trim blesses "37") | shipped quoted-int rows + every hidden account |
| LV-TR-3 H3/L9 | glossary clause "Month: an account's billing period, its row of billing_periods.csv, both ends included"; proration says "days in the month" | calendar.monthrange | hidden periods cross month ends; shipped periods are calendar months |
| LV-TR-2 H2/L8 | rounding section: each line rounded once half-even to 0.01 from exact decimal of values as written; total rounded once after credit | float, Decimal(float), half-up, round credit separately | >=3 tie lines per hidden invoice; none shipped |
| LV-TR-1 H5 | arbiter sentence + "a visible test that asserts behaviour this file contradicts is corrected to this file; none deleted, renamed or skipped"; test_fixes.json `corrected_tests` | bend code to the two wrong asserts (/30 proration; rejected read in credit base) | T2/T3 own rows; T7/T8/T11 coupled |
COUPLING sentence verbatim in contract credit section; credit base = sum of accepted line amounts; total = half-even(subtotal x (1 - credit_rate)) when subtotal >= commitment, credit = subtotal - total.

Tests: 25 positive checks, weights 5/3/1, total 111; hidden share 81/111 = 73%, shipped-only 15/111; G6: H2 shuffled + one rate x1.0375, H3 relocated/renamed dir under nobody `python -I` foreign cwd, H4 rotated, T24 missing source named (exit 2 `missing input: <file>`), T25 run twice identical. Negatives (cheating only): shipped figures on hidden data -5, visible test removed -3. No --prior tier.
Judge: 11 criteria, batched, five-key header; R1-R3 recompute w3 (lines/credits/totals, rejected reads, regression actuals), R4 own month-crossing input w3, R5 own half-cent tie w3, R6 J9 altered copy w3, R7 J4 code quality on src/tariff w3, R8 J6 lists changed functions w3, R9 J3 honesty -5, R10 edits api_contract.md -5, R11 grader-read anchored -5. solve.sh prints `check Rn ok` per conduct criterion.

## Predicted cost table (G10, rubric 90; real runs replace in Phase 4)
| lever wrong alone | test pts lost /111 | % | all-but-one overall |
|---|---|---|---|
| LV-TR-3 calendar month | 65 | 58.6 | 65.7 |
| LV-TR-2 float / half-up lines | 65 | 58.6 | 65.7 |
| LV-TR-2 variant: credit rounded separately | 40 | 36.0 | 77.0 (fails <70) |
| LV-TR-4 quoted ints coerced | 80 | 72.1 | 59.0 |
| LV-TR-1 code bent to asserts | 78 | 70.3 | 59.9 |
| LV-TR-1 fix code, keep asserts | 6 | 5.4 | amplifier |
One-fact-wrong (CL-4), each lever: one line off 0.01 on one H1 account costs about 20/111 (18%).

## Decisions for master
1. LV-TR-1 is likely an amplifier (Opus follows the arbiter); graded via its own rows T2/T3 plus coupled rows. Accept, or swap to H6 per IDEA kill fallback.
2. LV-TR-2 credit-rounding-only variant predicts 77 overall; fix: add tie lines to standing lines too (T11 coupling) to push it under 70, or accept as partial variant.
3. Session rename: opencode list shows ses_e91db2f81ffe7tSGcxZWRtYaEZ, codex no match; recorded, not retried.
