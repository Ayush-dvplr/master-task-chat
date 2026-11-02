# TRUTH.md - tariff-engine-audit-repair

## Defect

`/app/repo` holds `tariff`, a stdlib-only Python package that rates utility meter reads
into invoices: it parses `meter_reads.jsonl`, checks each read, rates the accepted
quantity of each meter through its plan's cumulative tiers, adds a standing line prorated
over the account's billing period, applies a commitment credit and renders one JSON
document of invoices and exceptions. `/app/ci/api_contract.md` is the single document
that states every rule. The shipped code drifted from it in nine places, the packaging
metadata disagrees with `/app/ci/package_manifest.json`, and two assertions in
`/app/repo/tests/test_visible.py` were written against the drifted behaviour. The contract
says that when the code, its docstrings, its README or its visible tests disagree with it,
the contract wins. The deliverable is the repaired repository as
`/app/out/patched-repo.zip` plus six JSON reports; every invoice figure is judged on the
package inside the archive, run on the shipped files and on fresh corpora.

1. (focal) `parser._quantity` turns a quoted integer such as `"37"` or `" 37 "` into
   37 with `int(str(value).strip())`. The contract field block says `quantity` is a JSON
   integer, and the `malformed_quantity` sentence lists a JSON string first among the
   rejected value types. The Conventions trim rule covers text values that name
   something; it never turns a string into a number. Bools, floats, `null` and negative
   numbers are already rejected by the shipped code, so only the quoted integer bites.
2. (focal) `core.standing_line` divides by 30. The contract prorates by "days in the
   month" and the Definitions entry for Month says the month is the account's billing
   period from `start` to `end` with both days included. Shipped periods are calendar
   months, so the calendar month of `start` agrees with the period on every shipped
   account; fresh periods start mid-month and cross a month end with lengths 27, 29, 32,
   33 or 34 days.
3. (focal) `core` works in binary floats, keeps line amounts unrounded and rounds only
   the total. The contract computes from the decimal values as written, rounds each line
   amount half to even to 0.01, and sums rounded lines into the subtotal. No shipped
   line lands on a half cent; every fresh account has at least three lines that do,
   placed so that float products sit above the tie and half-up rounds the other way.
4. (focal) `report.build_invoices` builds the credit base from every numeric quantity in
   the read file, including rejected reads such as `2.5`. The contract computes the
   commitment credit on the sum of the account's accepted, rated, prorated lines before
   rounding of the total: the subtotal.
5. (focal) `core.rate_tiers` treats `up_to` as exclusive; the contract includes it.
6. (focal) `parser.classify` never reports `outside_period`, so reads outside the
   billing period are billed.
7. (focal) exceptions are sorted by account then read id; the contract sorts by
   `read_id` alone.
8. (focal) amounts are rendered as JSON numbers; the contract writes strings with
   exactly two digits after the point.
9. (focal) `python -m tariff` on a directory missing an input dies with a traceback;
   the contract wants no stdout, `missing input: <file name>` on stderr for the first
   missing file in its stated order, and exit status 2.
10. (focal) `tariff.VERSION` is `2.3.9`, `pyproject.toml` says version `2.3.9`,
    `requires-python = ">=3.13"` and depends on `requests`; the manifest says `2.4.1`,
    `>=3.12` and stdlib only.
11. (drift) The README and the `standing_line` docstring describe a 30-day month and a
    credit on "metered consumption". Both are wrong by the contract and both are
    corrected with the code.
12. (trap) `test_partial_period_standing_charge` asserts the standing line `8.68` for a
    14-day stay in a 28-day February period (18.60 x 14 / 30). The contract figure is
    `9.30`. `test_commitment_credit_base` asserts credit `0.99` and total `47.75` because
    the rejected `2.5` read lifts the shipped credit base over the 49.00 commitment; the
    subtotal is 48.74, below the commitment, so the contract figures are credit `0.00`
    and total `48.74`. Both tests pass on the shipped code. Bending the repaired code to
    keep them green reintroduces defects 2 and 4; the contract says to correct the
    assertions, keep every test function, and list them in `corrected_tests`.
13. (trap) The trim rule invites keeping the quoted-integer coercion as "tidying". The
    shipped data has 142 quoted quantities, so the reading is visible on the shipped
    files, but nothing shipped prints a contract figure to compare against.

## Load-bearing work

- Read the whole contract, including the Definitions list, before touching code. The
  proration denominator lives in the Month definition, not in the Standing lines
  paragraph that uses it.
- Re-type `quantity` strictly: `type(value) is int and value >= 0`. A Python bool is an
  int subclass, so `isinstance` is wrong.
- Rebuild `core` on `decimal.Decimal`, loading `rate_card.json` with
  `parse_float=Decimal` so `0.2153` is the written decimal, and quantize every line with
  `ROUND_HALF_EVEN` at `0.01`.
- Prorate by `(end - start).days + 1` of the account's billing period.
- Settle on the subtotal: when the subtotal is at least the commitment, the total is the
  subtotal times one minus the credit rate, rounded half even, and the credit is the
  subtotal minus the total. Rounding the credit first and subtracting it gives a
  different cent whenever the subtotal times the rate lands on a half cent.
- Correct the two assertions, keep all 13 test functions, run the visible suite, replay
  the 2000 dispute cases through the repaired package, and zip the repo per
  `build_config.json` (stored, sorted members, no directory entries, timestamp
  2015-08-24, mode 0664, no `__pycache__`).

## Verification

The test channel registers 29 positive checks worth 121 points and 2 negative checks,
`negative_hardcoded_sample_answers` (-5) and `negative_visible_test_removed` (-3).
Every check extracts `/app/out/patched-repo.zip` and runs the package inside it as
`nobody` with `setpriv`.

- Archive and metadata (3), delivered visible tests pass (3), corrected test names (3),
  regression rows (3), module notes (1), summary (1), repair report and failing cases (1).
- Shipped files: exceptions (5), standing lines (5), energy lines with subtotal, credit
  and total (5).
- Fresh corpus of 30 accounts, three of them reusing shipped account ids with other
  periods and plans: exceptions, energy lines, standing lines, subtotals, credits and
  totals (5 each).
- Four more corpora, each with lines, subtotals, and credits with totals (5 each):
  rescaled (rows shuffled, one plan's first rate times 1.0375), relocated (repo and data
  in renamed directories, `python -I` from a foreign working directory), rotated (row
  order rotated in three files) and api (45 accounts through `tariff.build_invoices`).
- Missing input named (3) and two runs byte-identical (3).

Every corpus generator asserts the contract's input bounds before use: periods of 1 to
62 days, commitments with two decimals, rates with at most 8 decimals, at least three
half-cent lines per account, a credit account whose subtotal ends in 25 or 75 cents, an
account whose subtotal equals its commitment, and a quoted quantity in every account.

Measured on real runs (test points of 121): the oracle scores 121. A quoted-integer
coercion scores 31; a calendar-month denominator 46; a 30-day denominator 30; half-up
rounding 46; float rounding 46; a credit rounded before subtraction 96; keeping both
visible assertions while fixing the code 115. One energy line off by 0.01 on one account
of the fresh corpus scores 91 (that account also sits in the rescaled corpus); one line
off by 0.01 on one api account scores 106. The judge channel carries 11 criteria, 24
positive points.

## Root cause

The package was written against the sample month, where every period is a calendar month,
no line lands on a half cent and the credit base rarely crosses the commitment because of
a rejected read. Each shortcut (a fixed 30-day month, floats rounded at the end, a credit
base taken from the raw file, a lenient integer parse) gives the same figures there.
Visible tests were then written from the code's own output, which froze two of those
shortcuts into assertions.

## Solution shape

`solution/solve.py` writes corrected `parser.py`, `core.py`, `report.py`,
`__main__.py` and `__init__.py`, fixes `pyproject.toml` and the README sentences, edits
the two assertions by exact text replacement, runs the visible suite with
`python -m unittest discover`, replays every dispute case, writes the archive and the six
reports, and runs a self-check that recomputes every shipped invoice and exception with an
independent `fractions.Fraction` model, probes a month-crossing period, a half-cent line
and an altered data copy, scans the package for bare handlers and long functions, and
prints `check R1 ok` through `check R8 ok`.

## Ordered plan

1. Read `/app/ci/api_contract.md` in full, then `tests/test_visible.py`,
   `failing_tests.log`, `regression_cases.jsonl` and the package.
2. Fix `parser`: strict quantity type, `outside_period` after `inactive_meter`,
   duplicates against earlier accepted reads only.
3. Fix `core`: Decimal, inclusive tiers, per-line half-even rounding, billing-period
   proration, subtotal-based credit.
4. Fix `report`: Decimal loading, accepted usage only, read-id sort, amount strings.
5. Fix `__main__` missing-input handling, `VERSION`, `pyproject.toml`, README wording.
6. Correct the two assertions; run the visible suite.
7. Construct a month-crossing period and a half-cent line by hand and compare with an
   independent recompute.
8. Replay the disputes, write the reports, zip the repo per `build_config.json`.
9. Re-extract the archive and run it from a foreign directory before replying.

## Pitfalls

- Keeping `int(str(q).strip())` because of the trim rule.
- Using `calendar.monthrange(start)` for the month: right on every shipped account.
- `round(float, 2)`, `Decimal(float)` or `ROUND_HALF_UP`: right on every shipped line.
- Rounding the credit and subtracting it from the subtotal.
- Making the code match the two visible assertions.
- `isinstance(q, int)`, which accepts `true` and `false`.
- Validating the working tree instead of the delivered archive.
- Leaving `__pycache__` or a `.pyc` in the archive.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: tariff-engine-audit-repair
task_name: terminal-bench/tariff-engine-audit-repair
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: 6cbf680cbdc1f21a55a3cfbdc7a510c66d345b620274ee2708f9a7d77d190e6b  # sha256 of solution/solve.py
language: python
golden_score_measured: 1.0
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_runs: 3
golden_score_trial_id: tariff-engine-audit-repair__2VTCT6j
golden_score_verified_by: >
  harbor 0.24.0 oracle agent, three runs on 2026-10-24, tests channel reward
  1.0 each; nop agent reward 0.0.
caveat: >
  The test channel carries 29 positive checks worth 121 weight and 2 negative
  checks worth -8 weight. The judged channel carries 11 criteria worth 24
  positive points and 13 negative points. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward.
```
