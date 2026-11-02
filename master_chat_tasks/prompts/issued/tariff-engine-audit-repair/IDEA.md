# Idea card: tariff-engine-audit-repair (master-drafted, 24 Oct 2026 19:10 IST)
Source: master draft from LEVER_RULES_v1 section 1b (Opus-habit bank); first drafted as pilot IDEA_2 (/Users/Shared/md_pilot, parked). Ayush 24 Oct 19:05 chose '1' (build it now in the main workflow). Archetype repo-patch, adapted to its fixed artifacts.

## Premise
A utility's billing team ships a small stdlib-only Python package `tariff` that rates meter reads into invoices: parse reads, apply the rate card, prorate partial periods, apply commitment credits, round, and render invoice lines. Customers disputed invoices; an audit found the package drifts from the written tariff contract in several places, and its own visible unit tests encode some of the wrong behaviour. The agent repairs the package in place under `/app/repo` so that it follows the contract, and delivers the repo-patch artifacts.

## Inputs (flat, at least 10 files, at least 5 formats)
- `/app/ci/api_contract.md` (scaffold name kept): THE one contract file (W10). Read model, quantity typing, rate-card semantics, proration, credit base, rounding, invoice line and exception keys, every error string, and the arbiter sentence: when the code, its docstrings, its README or its visible tests disagree with this file, this file wins.
- `/app/repo/`: package `src/tariff/` (about 8 modules: reads, ratecard, proration, credits, rounding, invoice, render, cli), `tests/test_visible.py` (passes on the shipped code; two of its asserts encode wrong behaviour), README.md, pyproject.toml.
- `/app/ci/`: `failing_tests.log` (customer dispute replays that fail, honest), `regression_cases.jsonl` (dispute reads with the disputed and the customer-claimed totals, no contract-correct answers), `lint_report.json`, `package_manifest.json`, `build_config.json`, `rate_card.json`, `meter_reads.jsonl` (sample month), `billing_periods.csv`, `accounts.csv`.
- No expected outputs, no corrected totals, no labelled answers.

## Spine
parse reads -> type-check quantities (reject or keep) -> rate by tier -> prorate by billing period -> credit base and commitment credit -> per-line half-even rounding -> invoice totals -> render + exceptions.

## Levers (each a stated single-reading rule in api_contract.md, each alone >= 25% of test points, G10)
- LV-TR-1 (H5 make-it-match): two asserts in the visible test file encode wrong behaviour (one proration, one rejected-read handling); the contract overrides them. Opus habit: keep the shipped tests green. A correct repair edits or replaces those two asserts and says so in test_fixes.json.
- LV-TR-2 (H2 float rounding): each invoice line rounds half-even to 0.01 in exact decimal before summing; shipped sample data has no .xx5 tie, hidden reads carry >= 3 ties per invoice.
- LV-TR-3 (H3 denominator): proration divides by the days in the customer's billing period (from billing_periods.csv), not by the days in the calendar month; shipped periods align with months, hidden periods cross month ends.
- LV-TR-4 (H1 strict coercion): meter quantities are JSON integers; a quoted or float quantity is a rejected read listed in the invoice exceptions, never coerced. Shipped sample has separating rows (L5 only), easy decoys elsewhere.
- COUPLING: the commitment-credit base is the sum of accepted rated lines in the period, so LV-TR-4 and LV-TR-3 move every credit and every invoice total of that account.

## Tests (master direction)
Hidden tests import the repaired package from the delivered patched-repo.zip and run it on verifier-generated reads (relocated, shuffled, one rate scaled 1.0375, foreign uid, foreign cwd). One test per lever family owning its rows, visible version then `_hard`, 30-50 tests at w5; at least one check that the contract, not the visible test file, decides. Module/summary JSON artifacts graded on their own rows. Cost table + one-fact-wrong per lever in WORK/COST_TABLE.md.

## Judge (master direction)
Recompute conduct per output family (w3, solve.sh self-check prints `check <id> ok`), J9 altered-copy rerun, exactly one concrete code-quality criterion on the edited functions, J6 changed-function listing in the final reply, J3 honesty negative, negatives for editing api_contract.md or reading test paths.

## Kill fallback
If a probe scores tests >= 95, swap the weakest lever for H6 (state consumed early: a credit pool drawn down in read order across accounts) and re-probe.
