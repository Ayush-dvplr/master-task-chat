# Tariff engine contract

This file is the contract of the `tariff` package in `/app/repo`, which rates
meter reads into invoices. When the code, its docstrings, its README or its
visible tests disagree with this file, this file wins.

## Package

- The package imports as `tariff` from `/app/repo/src` and uses the Python
  standard library only: no network client, no runtime monkeypatch hook, no
  third-party dependency.
- `tariff.VERSION` is a string equal to `version` in
  `/app/ci/package_manifest.json`. The repaired `pyproject.toml` carries the same
  `version`, a `requires-python` equal to the manifest's `requires_python`, and
  `dependencies = []`.
- `tariff.build_invoices(data_dir)` reads the four input files of the directory
  `data_dir` and returns the invoice document as a dict.
- `tariff.render(document)` returns the document as JSON text.
- `python -m tariff <data_dir>`, run with `/app/repo/src` on the import path,
  writes `render(build_invoices(data_dir))` and a newline to standard output and
  exits 0. When an input file is missing it writes nothing to standard output,
  writes the line `missing input: <file name>` to standard error for the first
  missing file in the order `meter_reads.jsonl`, `accounts.csv`,
  `billing_periods.csv`, `rate_card.json`, and exits 2.

## Conventions

- Every text value in the input files is compared and written after removing
  the spaces around it.
- Dates are ISO `YYYY-MM-DD`. A range of days from one date to another includes
  both dates.
- Every amount in the document is a JSON string with exactly two digits after
  the decimal point, such as `"104.37"` or `"0.00"`.

## Definitions

- Accepted read: a read that receives no exception.
- Active: a meter is active on the days from its `active_from` to its
  `active_to`; an empty `active_to` means the meter stays active.
- Active days: the days of the month on which the meter is active.
- Commitment: the `commitment` of the account's row in `billing_periods.csv`.
- Line amount: the exact value of a line rounded half to even to 0.01.
- Month: the account's billing period, its row of `billing_periods.csv`, from
  `start` to `end` with both days included.
- Period quantity: the sum of `quantity` over the accepted reads of a meter.
- Plan: the entry of `rate_card.json` named by the account's `plan`.
- Tier: one entry of the plan's `tiers` list, numbered from 1 in list order.

## Input files

`meter_reads.jsonl` holds one JSON object per line with these fields:

- `read_id`: a JSON string, unique in the file.
- `account`, `meter`: JSON strings naming the account and its meter.
- `day`: a JSON string holding the ISO date of the read.
- `quantity`: a JSON integer, 0 or more.

`accounts.csv` has the header `account,meter,active_from,active_to` and one row
per meter of an account. `active_to` may be empty. Every account in it has a
row in `billing_periods.csv`.

`billing_periods.csv` has the header `account,start,end,plan,commitment` and
one row per account. `start` is on or before `end`, and the period is 1 to 62
days long. `commitment` is a decimal with two digits after the point.

`rate_card.json` is `{"currency": "EUR", "plans": {<plan name>: <plan>}}`. A plan
has `standing_charge`, the charge for one month of supply (a JSON number with at
most two decimals), `credit_rate` (a JSON number from 0 to 1 with at most four
decimals) and `tiers`, a list of `{"up_to": <JSON integer or null>, "rate":
<JSON number with at most eight decimals>}` with `up_to` increasing and `null`
only on the last tier.

## Reads

Each read receives at most one exception, the first of this list that applies:

1. `malformed_quantity`: A read is `malformed_quantity` when its `quantity` is a
   JSON string, a JSON number written with a decimal point or an exponent,
   `true`, `false`, `null`, or a negative integer.
2. `unknown_meter`: the pair of its `account` and `meter` is no row of
   `accounts.csv`.
3. `inactive_meter`: the meter is not active on the read's `day`.
4. `outside_period`: the read's `day` is outside its account's billing period.
5. `duplicate_read`: an earlier read in file order with the same `account`,
   `meter` and `day` is an accepted read.

An exception row is `{"read_id": <string>, "account": <string>, "reason":
<string>}`. The exception list holds one row per read with an exception, sorted
by `read_id` in ascending string order.

## Invoices

The document has one invoice per row of `billing_periods.csv`, sorted by
`account` in ascending string order. An invoice is `{"account": <string>,
"period": {"start": <ISO date string>, "end": <ISO date string>}, "plan":
<string>, "lines": <list>, "subtotal": <amount>, "credit": <amount>, "total":
<amount>}`. Every meter of the account in `accounts.csv` is billed on the
invoice.

Energy lines. Tier 1 covers the period quantity from 0 up to and including its
`up_to`; every later tier covers the quantity above the previous `up_to` up to
and including its own, and the `null` tier has no upper end. A tier that covers
no unit of the period quantity has no line. An energy line is `{"meter":
<string>, "kind": "energy", "tier": <tier number, integer>, "units": <integer
units in that tier>, "amount": <amount>}` and its exact value is the units
multiplied by the tier `rate`.

Standing lines. A meter pays `standing_charge` x active days / days in the
month, where active days are the days of the month on which the meter is
active. A standing line is `{"meter": <string>, "kind": "standing", "tier": 0,
"units": <integer active days>, "amount": <amount>}`. A meter with no active day
has no standing line.

Line order. Lines are sorted by `meter` in ascending string order; the lines of
one meter are its energy lines by tier number, then its standing line.

Amounts. Every amount is computed from the decimal values as written in the
input files. Each line amount is its exact value rounded half to even to 0.01.
The subtotal is the sum of the line amounts.

Credit. The commitment credit of an account is computed on the sum of its
accepted, rated, prorated lines in the billing period, before rounding of the
total. When the subtotal is at least `commitment`, the total is subtotal x (1 -
`credit_rate`) rounded half to even to 0.01 and the credit is subtotal minus
total; otherwise the credit is 0.00 and the total is the subtotal.

The document is `{"invoices": <list>, "exceptions": <list>}`; key order and
whitespace are free.

## Visible tests

A visible test that asserts behaviour this file contradicts is corrected to this
file; no visible test function is deleted, renamed or skipped. The repaired
`/app/repo/tests/test_visible.py` passes against the repaired package.

## Repair deliverables

`/app/out/patched-repo.zip` holds every file of the repaired `/app/repo` under
its path relative to `/app/repo` (for example `src/tariff/core.py`), with no
`__pycache__` directory and no `.pyc` file. It follows
`/app/ci/build_config.json`: members sorted by name, no directory entries, every
member's timestamp equal to `archive.timestamp`, compressed with
`archive.compression` (`stored` or `deflated`), and with unix permission bits
equal to `archive.mode`.

Each report under `/app/out` is one JSON object; key order and whitespace are
free.

- `repair-report.json`: `package` (the string `"tariff"`), `fixes` (a non-empty
  list of strings, one per repair, in your own words) and `checks` (a list of
  `{"name": <string>, "passed": <bool>}` objects for the checks you ran; at least
  one passed).
- `module_core.json`, `module_parser.json`, `module_report.json`: `module` (the
  string `core`, `parser` or `report`), `status` (`fixed` or `unchanged`),
  `fixes` (a list of strings in your own words, non-empty when `status` is
  `fixed`) and `lint_errors` (an integer: the number of
  `/app/ci/lint_report.json` issues whose `module` is `tariff.<module>` and
  whose `severity` is `error`). `module_core.json` adds `validations`, a
  non-empty list of strings naming the checks you ran against `core`;
  `module_parser.json` adds `contract_terms`, the sorted names of the three
  Python entry points this contract lists (`VERSION`, `build_invoices`,
  `render`); `module_report.json` adds `deterministic`, `true` when two
  `build_invoices` calls on the same directory return equal documents.
- `test_fixes.json`: `visible_tests_preserved` (bool), `corrected_tests` (the
  sorted names of the visible test functions whose assertions you changed),
  `previously_failing` (the sorted case names whose test is reported `FAIL` or
  `ERROR` in `/app/ci/failing_tests.log`; a test named `test_<name>` belongs to
  case `<name>`), `regression_cases` and `all_regressions_passed` (bool, true
  when every regression case passed).
- `regression_cases` holds one `{"name": <string>, "expected": <string>,
  "actual": <string>, "passed": <bool>}` object per line of
  `/app/ci/regression_cases.jsonl`, in file order. `expected` is the case's
  `customer_claim`, the total the customer says is right, which nobody has
  checked. `actual` is the `total` of the case's invoice when the repaired
  package runs on a directory holding the case: its `reads` as
  `meter_reads.jsonl`, one `accounts.csv` row per entry of `meters` under the
  case's `account`, one `billing_periods.csv` row from the case's `account`,
  `period`, `plan` and `commitment`, and `/app/ci/rate_card.json`. `passed` is
  true when `actual` equals `expected`.
- `summary.json`: `package` (`"tariff"`), `status` (`"complete"`), `inputs_used`
  (the sorted names of every file in `/app/ci`), `artifacts` (the seven
  deliverable paths in the order the task lists them), `artifact_count` (the
  integer 7) and `stdlib_only` (bool).
