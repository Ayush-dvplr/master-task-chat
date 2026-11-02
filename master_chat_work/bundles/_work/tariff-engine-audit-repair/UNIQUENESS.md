# UNIQUENESS: L11 plan codes (7f1d771)

Rule (no sentence anywhere): the plan of an account is the `rate_card.json` entry whose key equals the trimmed `plan` value of its `billing_periods.csv` row; when no key equals it, it is the one entry whose `codes` list (each item trimmed) contains it. The invoice `plan` field stays the row's trimmed value (format statement, contract :101-103).

Witness: the `codes` lists of `environment/ci/rate_card.json` (:7-10 HOME-A, :29-31 HOME-B, :50-53 SME-1 with the padded `" T2319"`, :72-74 SME-2, :93 IND-1 `[]`, :108-110 IND-2), governing the `plan` column of `environment/ci/billing_periods.csv` (503 of 2000 rows carry a code, e.g. :2 `A0001,...,T3415,...`, :159 `A0158,...,T2319,...`). Contract :53 ("Plan: the entry of `rate_card.json` named by the account's `plan`") presupposes that exactly one entry is named; the register is the only place a value such as `T3415` occurs, so it settles which entry names it.

Hidden witnesses: every hidden corpus card carries fresh codes (letter from BDFGHJ plus 4 digits, one padded item, one plan without codes, a plan with two codes, two plans whose codes share their first three characters). Only `recoded` (H7_SEED, 30 accounts, 19 named by code) and its mutated rerun `renamed` (all codes renamed in card and billing together, card order rotated, rows rotated) bill by code; the other five corpora carry codes in the card and bill by key. Generator asserts (`_assert_codes`): codes unique, disjoint from keys and from their casefold/alnum forms; at least 40% of accounts named by code; every code billed; owners include a non-first and a non-last entry; a padded billing value; a two-code plan; a shared three-character stem across two plans.

Fit criterion (WORK/uniq.py): a reading fits a witness set when every billing row resolves to exactly one entry and that entry carries the row's trimmed value as its key or as one of its trimmed strings (the `:53` "named by" relation). The second number is how many rows choose a different entry from R1.

## Results (OUT/uniq.json, OUT/uniq_extra.json)

| reading | shipped (503 by code) | recoded (19) | renamed (19) | 80 extra L11 witness sets (seeds 2000-2039, corpus + renamed) |
|---|---|---|---|---|
| R1 key, else the entry whose trimmed codes list the value | fits, 0 differ | fits, 0 | fits, 0 | fits 80/80 |
| R1b codes first, then key | fits, 0 | fits, 0 | fits, 0 | fits 80/80, differs 0/80 |
| R2 key only (no entry) | NO, 503 | NO, 19 | NO, 19 | fits 0/80 |
| R3 key compared casefolded | NO, 503 | NO, 19 | NO, 19 | 0/80 |
| R4 key compared on letters and digits | NO, 503 | NO, 19 | NO, 19 | 0/80 |
| R5 key sharing the value's first letter | NO, 2000 | NO, 30 | NO, 30 | 0/80 |
| R6 first entry when the value is no key | NO, 396 | NO, 11 | NO, 15 | 0/80 |
| R7 last entry when the value is no key | NO, 398 | NO, 15 | NO, 19 | 0/80 |
| R8 most billed key when the value is no key | NO, 503 | NO, 19 | NO, 19 | 0/80 |
| R9 no invoice when the value is no key | NO, 503 | NO, 19 | NO, 19 | 0/80 |
| R10 codes compared untrimmed | NO, 56 | NO, 2 | NO, 2 | 0/80 |
| R11 code listed first in an entry only | NO, 114 | NO, 9 | NO, 9 | 0/80 |
| R12 code listed last in an entry only | NO, 89 | NO, 10 | NO, 10 | 0/80 |
| R13 three-character stem of a listed code | NO, 206 | NO, 8 | NO, 8 | 0/80 |
| R14 code whose digits are nearest | fits, 0 | fits, 0 | fits, 0 | fits 80/80, differs 0/80 |
| R15 entry at the code's number mod entry count | NO, 503 | NO, 13 | NO, 11 | 0/80 |
| R16 codes compared casefolded | fits, 0 | fits, 0 | fits, 0 | fits 80/80, differs 0/80 |
| R17 codes compared on digits only | fits, 0 | fits, 0 | fits, 0 | fits 80/80, differs 0/80 |

Non-L11 corpora (fresh, rescaled, relocated, rotated, api) bill by key only: every reading except R5 fits there, which is expected (they are not L11 witnesses; their rows are graded for N1-N3).

## Verdict: ONE

- Every reading that picks a different entry for some row is contradicted by the shipped witness and by both graded L11 witnesses: R2-R4, R8, R9, R15 (no entry carries the value), R5-R7 (the chosen entry does not list it), R10 (padded `" T2319"` at :52 matches no untrimmed value), R11/R12 (a two-code plan bills both codes), R13 (HOME-A `T1108`/`T1131` and HOME-B `T1140` share `T11`).
- R1b, R14, R16 and R17 are not separate readings: each is R1's lookup with a looser match that returns the exact listed code whenever one exists, and contract :53 with :28-29 presupposes one exists for every row. They choose the same entry as R1 on every row of every witness set (0 differ, 83/83 sets), so they produce byte-identical graded documents; no contract-valid input can separate them. They are the R1 class.
- Binding time, ordering and rounding variants do not apply: the lookup is static per row, carries no amount, and its operand (the row's `plan`) is the only billing field that names a plan.
- IN-16 fallback (if QC rules the register silence): QC_DEFENCE entry L11, playbook AL-1 DO direction (4b) already applied; second line is the IN-16 DO (one settling clause in the governing file, written for the general case) recorded there, which would end the pilot as an explicit lever.

# Q1 estimate and actual in either order (78d433c)

Sentence: contract :111-115. Readings checked on every hidden corpus by `_assert_quiet` and the Q variants of WORK/measure_variants.py.

| case (planted in every hidden corpus) | R1 stated (rule 5 compares `estimated`; rule 6 wherever the actual stands) | R2 `estimated` ignored | R3 rule 6 only when the actual is earlier in the file |
|---|---|---|---|
| estimate, then actual (other quantity) | actual billed, estimate `replaced_estimate` | estimate billed, actual `duplicate_read` | estimate billed, actual accepted too (both billed) |
| actual (`"estimated": false` written out), then estimate | actual billed, estimate `replaced_estimate` | actual billed, estimate `duplicate_read` | same as R1 |
| two estimates of one day, no actual | first billed, second `duplicate_read` | same | same |
| estimate with a malformed actual (`-3`) | estimate billed, actual `malformed_quantity` | same | same |
| lone estimate | billed | billed | billed |

Either order gives the same document under R1 (the actual is billed and the estimate set aside), so R1 is unique for both orders; R2 and R3 each differ from R1 on at least one planted account per corpus (estimated_read_accounts_on_* fails for both: M63_estimated_ignored, M64_estimate_file_order in RULE_COVERAGE.md).

## U1 (15b380e): fit per plan, every hidden corpus
Candidate set = the plan's `revisions` list (stated). Fit = every invoice on the plan with a paid amount totals that amount (Ledger `_fits`, whole account chains incl. carry and D1).
| plan | revisions | fit count | truth | first-fit reading |
|---|---|---|---|---|
| A | 3 (far, near, fit; near before fit) | 1 (fit) | fit tiers | same (near fails witness a2 crossing tier 2) |
| B | 2 (agree on witnessed tier-1 use) | 2 | own tiers | revision 1: wrong on unwitnessed crossing account |
| C | 2 | 0 | own tiers | first revision under U1nofit: wrong |
Asserted per corpus and on 300 seeds in `_levers_once`; under Q3, N1 or N3 off plan A's choice differs, so the true fit depends on those rules.
