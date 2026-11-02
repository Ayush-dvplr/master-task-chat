# PREMORTEM: how claude-opus-5 solves tariff-engine-audit-repair in its first 10 minutes

Written 2026-10-24 19:25 IST, before DESIGN.md. Board a5f8657.

## Minute 0-2: reading order
1. `/app/instruction.md`: job = repair `/app/repo` in place against `/app/ci/api_contract.md`, deliver 7 files under `/app/out`; arbiter sentence (contract wins over code, docstrings, README, visible tests); outputs graded whole on fresh reads.
2. `/app/ci/api_contract.md` top to bottom, once. It notes: read model, `quantity` field block, malformed list, tiers, standing charge proration, rounding, credit, output schema, error strings, archive rules, report artifacts.
3. `ls /app/repo/src/tariff`, reads `parser.py`, `core.py`, `report.py`, `__main__.py`, then `tests/test_visible.py`, README.
4. Runs `python -m pytest /app/repo/tests` (or `python -m unittest`): all green on shipped code.
5. Skims `/app/ci/failing_tests.log`, `regression_cases.jsonl`, `lint_report.json`, `build_config.json`, `package_manifest.json`, `head` of the data files.

## Minute 3-8: the program it writes once
- Diffs each module against the contract section by section and patches what reads wrong: tier boundary (`<` to `<=`), outside-period reads billed, exception sort key, render of amounts as 2dp strings, credit base taken from rejected reads. These are visible as plain contradictions; Opus fixes them.
- Rewrites the money path with `decimal.Decimal` and `ROUND_HALF_EVEN` because the contract names half-even at 0.01.
- Proration: sees `/ 30` in `core.standing_line`; the contract says the charge is prorated by "days in the month". It writes `calendar.monthrange(start.year, start.month)[1]` (reflex H3: "month" means calendar month).
- Quantity: the parser has `int(str(q).strip())` under a guard that already rejects bools, floats and None. The contract's Conventions section says text values are compared after trimming surrounding spaces. Opus reads the guard plus the trim rule as consistent and keeps the coercion of `"37"` and `" 37 "` (reflex H1).
- Rounding: it reads rates with `json.load` (floats), multiplies `Decimal(units) * Decimal(rate)` or `Decimal(str(units * rate))`, quantize HALF_EVEN. Credit: `credit = round(subtotal * credit_rate)`, `total = subtotal - credit` (reflex: round the credit, not the total).
- Visible tests: after its fix, `test_partial_period_standing_charge` (expects /30) and `test_commitment_credit_base` (expects base with a rejected read) fail. Opus either edits the two asserts to the contract (likely, arbiter sentence) or bends code back to keep them green (H5).
- Builds the zip with `zipfile`, writes the 6 JSON notes, runs the CLI on `/app/ci`.

## Minute 8-10: self-tests it runs
- Visible tests green after its edits; CLI on shipped `/app/ci` data; invariants: subtotal = sum of line amounts, total = subtotal - credit, every read is either billed or in exceptions, determinism over two runs; tiny hand example (one meter, 2 tiers).
- None of these has an expected figure from outside its own program; no file ships contract-correct invoices.

## Per lever: exact failure point and why its self-tests miss it

### LV-TR-3 (H3/L9 proration denominator)
- Failure point: `days_in_month = calendar.monthrange(...)` instead of the length of the account's row in `billing_periods.csv` (glossary: "month" = the billing period, both ends included).
- Why missed: every shipped period is a calendar month (1st to last day), so both readings give identical shipped figures; the visible assert uses /30, which is wrong under both readings, so correcting it to the calendar figure also passes Opus's own check. Invariants (sums, totals) hold under any denominator.

### LV-TR-2 (H2/L8 half-even exact decimal on ties)
- Failure point: float product before quantize, `Decimal(float)`, `round(x, 2)` on float, or ROUND_HALF_UP; or rounding the credit instead of the total.
- Why missed: no shipped line, credit or total sits on a half-cent tie, so every rounding mode prints the same shipped figures; tiny hand examples use round numbers; invariants hold under any mode.

### LV-TR-4 (H1/L5 strict quantity)
- Failure point: keeping `int(str(q).strip())` for JSON strings because of the global trim rule.
- Why missed: separating rows do ship (quoted integers, padded quoted integers), but nothing ships their expected invoice or exception list; the coerced output is internally consistent (every read accounted for once); visible tests cover only float and null rejects.

### LV-TR-1 (H5 make-it-match)
- Failure point A (rare for Opus): keeps the two wrong asserts and restores /30 or the rejected-read base to make them pass.
- Failure point B (likely): fixes code and asserts, but lists no or wrong `corrected_tests` in `test_fixes.json`, or deletes or skips a test instead of correcting it.
- Expected: Opus follows the arbiter sentence, so this lever is an AMPLIFIER (G10): its own rows (delivered visible tests pass on the delivered package; `corrected_tests` exact) cost little alone. Recorded as such; three non-amplifier levers remain (LV-TR-2, LV-TR-3, LV-TR-4).

## Redesign check
- Any lever the first-write program gets right? Rounding (LV-TR-2) is the weakest: Opus reaches for Decimal + HALF_EVEN when the contract names it. Its bite is the coupled credit rule (round the total, credit = subtotal - total) and float-parsed rates; both stay in the design, and the tie rows are in the credit base so every tie miss also moves the subtotal, credit and total of that account in every hidden corpus.
- No lever is self-testable from shipped data (LEAK_LIBRARY "self-testable rules are not levers"): proration and rounding separate only on hidden inputs, and the quantity rows ship without answers.
