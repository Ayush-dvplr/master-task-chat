# LEVERS

All rules live in `environment/ci/api_contract.md` (agent path `/app/ci/api_contract.md`, W10).
Owned tests are the checks in `tests/test_output.py` whose rows the lever decides.

## LV-TR-4 (H1, L5) quantity is a JSON integer
- Rule: L56 "`quantity`: a JSON integer, 0 or more." and L77-79 "A read is `malformed_quantity` when its
  `quantity` is a JSON string, a JSON number written with a decimal point or an exponent, `true`, `false`,
  `null`, or a negative integer." Normalising rule elsewhere: L28-29 "Every text value in the input files
  is compared and written after removing the spaces around it."
- Reflex reading: the shipped `int(str(value).strip())` stays, blessed by the trim rule; quoted integers
  are billed.
- Shipped separating rows (W5 allows for L5): 142 quoted quantities in `meter_reads.jsonl` plus bool,
  float, exponent, null and negative decoys.
- Hidden: every account of every fresh corpus has a quoted integer on a tie meter on a day with no other
  read, so coercion moves an energy line, the subtotal, the credit and the total.
- Owned: shipped_exceptions_exact, shipped_energy_and_settlement_exact, fresh_exceptions_exact,
  fresh_energy_lines_exact and the COUPLING rows (subtotals, credits and totals in all five corpora).
- Measured alone: 90 of 121 points (74.4%).

## LV-TR-3 (H3, L9) proration denominator = days of the billing period
- Rule: L108-110 "A meter pays `standing_charge` x active days / days in the month, where active days are
  the days of the month on which the meter is active." with L43-44 Definitions "Month: the account's
  billing period, its row of `billing_periods.csv`, from `start` to `end` with both days included."
- Reflex reading: calendar month length (`calendar.monthrange`) or the shipped 30.
- Shipped data: every period is a calendar month, so the calendar reading matches every shipped figure;
  `/30` is wrong on shipped data and in visible assert A.
- Hidden: every period crosses a month end with 27, 29, 32, 33 or 34 days; one partially active meter or
  more per corpus.
- Owned: shipped_standing_lines_exact, fresh_standing_lines_exact, the lines rows of the four trios and
  the COUPLING rows.
- Measured alone: calendar 75 (62.0%), thirty days 91 (75.2%).

## LV-TR-2 (H2, L8) exact decimal, half to even per line at 0.01
- Rule: L42 Definitions "Line amount: its exact value rounded half to even to 0.01." and L117-119
  "Every amount is computed from the decimal values as written in the input files. Each line amount is its
  exact value rounded half to even to 0.01. The subtotal is the sum of the line amounts."
- Reflex reading: binary floats with `round(x, 2)`, or Decimal with ROUND_HALF_UP.
- Shipped data: no line, no credited total sits on a half cent (screened by datagen.py).
- Hidden: three tie meters per account, each with a top tier line exactly on a half cent whose lower cent
  is even and whose binary float product lies above the tie.
- Owned: fresh_energy_lines_exact, lines rows of the trios, COUPLING rows.
- Measured alone: half up 75 (62.0%), floats 75 (62.0%). Partial variant (credit rounded on its own)
  25 (20.7%), accepted by master.

## COUPLING (G1) commitment credit base
- Rule: L121-123 "The commitment credit of an account is computed on the sum of its accepted, rated,
  prorated lines in the billing period, before rounding of the total." and L123-125 the at-least rule.
- Carries every lever into the subtotal, credit and total of each account: subtotals and credits_and_totals
  rows of the fresh corpus and of the rescaled, relocated, rotated and api trios.
- Shipped defect P4 (credit base includes rejected numeric reads) and visible assert B encode the wrong
  base.

## LV-TR-1 (H5) contract beats visible tests: amplifier
- Rule: L3-5 "When the code, its docstrings, its README or its visible tests disagree with this file, this
  file wins." and L132-134 Visible tests section with `corrected_tests`.
- Visible assert A (`test_partial_period_standing_charge`, 8.68 from `/30`) and assert B
  (`test_commitment_credit_base`, credit from the inflated base).
- Own rows: delivered_visible_tests_pass (3), corrected_tests_name_the_changed_tests (3). Measured 6 (5.0%)
  when the code is fixed and the asserts kept; bending the code to the asserts is the LV-TR-3 `/30` row.
