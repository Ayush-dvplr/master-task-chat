# TRUTH.md - tariff-engine-audit-repair

## Defect

`/app/repo` holds `tariff`, a stdlib-only Python package that rates utility meter reads
into invoices: it parses `meter_reads.jsonl`, checks each read, rates the accepted
quantity of each meter through its plan's tiers, adds a standing line per meter, applies a
commitment credit and renders one JSON document of invoices and exceptions.
`/app/ci/api_contract.md` is the single document that states every rule. The shipped code
drifted from it in twelve places, the packaging metadata disagrees with
`/app/ci/package_manifest.json`, and two assertions in `/app/repo/tests/test_visible.py`
were written against the drifted behaviour. The contract says that when the code, its
docstrings, its README or its visible tests disagree with it, the contract wins. The
deliverable is the repaired repository as `/app/out/patched-repo.zip` plus six JSON
reports; every invoice figure is judged on the package inside the archive, run on the
shipped files and on fresh corpora.

1. (focal, lever N1) `billing_periods.csv` carries an `allowance` column that the shipped
   package ignores. The Definitions entry "Energy share" gives each energy line of the
   account an equal part of the allowance, capped at the line's exact value, and leaves
   what a line cannot take unshared. A different paragraph, Amounts, shares the unshared
   rest again in equal parts among the energy lines not yet at zero, as often as some
   stays unshared. Shipped and regression allowances are always taken in the first share;
   on half of the fresh, rescaled, relocated and rotated accounts the allowance needs at
   least three shares, and stopping after one or two leaves a different cent.
2. (focal, lever N2) `core.standing_line` divides by 30. The Definitions entry Month is a
   calendar month, and the Standing lines paragraph sums `standing_charge` x active days
   in each month / days in that month over every month holding an active day of the
   billing period. Shipped periods are whole calendar months or lie inside one month, so
   the calendar month of `start` gives the same figure there; fresh, rescaled and api
   periods start mid-month and cross a month end (27, 29, 32, 33 or 34 days).
3. (focal, lever N3) `core.rate_tiers` fills the tiers from zero for every meter. The
   Definitions entry "Account position" numbers the account's accepted units over its
   meters in ascending `meter` order, and the Energy lines paragraph places tiers on that
   position, so a later meter starts where the earlier meters stopped. Every shipped and
   regression account stays within tier 1 in total; relocated, rotated and api accounts
   cross a tier boundary only through the sum of their meters.
4. (focal, uncounted gate) `parser._quantity` turns a quoted integer such as `"37"` into
   37 with `int(str(value).strip())`. The field block says `quantity` is a JSON integer,
   0 or more, and `malformed_quantity` is a read whose quantity is not what that rule
   allows. The Conventions trim rule covers text values; it never turns a string into a
   number.
5. (focal, uncounted gate) `core` works in binary floats, keeps line amounts unrounded and
   rounds only the total. The contract computes from the decimal values as written,
   rounds each line amount half to even to 0.01, and sums rounded lines. Every fresh
   account that does not need a third share has at least three half-cent lines.
6. (focal, uncounted gate) `report.build_invoices` builds the credit base from every
   numeric quantity in the read file. The contract computes the credit on the subtotal.
7. (focal) `core.rate_tiers` treats `up_to` as exclusive; the contract includes it.
8. (focal) `parser.classify` never reports `outside_period`.
9. (focal) exceptions are sorted by account then read id; the contract sorts by `read_id`.
10. (focal) amounts are rendered as JSON numbers; the contract writes two-decimal strings.
11. (focal) `python -m tariff` on a directory missing an input dies with a traceback; the
    contract wants no stdout, `missing input: <file name>` on stderr, exit status 2.
12. (focal) `tariff.VERSION` and `pyproject.toml` say `2.3.9`, `>=3.13` and depend on
    `requests`; the manifest says `2.4.1`, `>=3.12` and stdlib only.
13. (drift) The README and the `standing_line` docstring describe a 30-day month and a
    credit on "metered consumption". Both are corrected with the code.
14. (trap) `test_partial_period_standing_charge` asserts `8.68` for a 14-day stay in
    February (18.60 x 14 / 30); the contract figure is `9.30`.
    `test_commitment_credit_base` asserts credit `0.99` and total `47.75`; the contract
    figures are credit `0.00` and total `48.74`. The contract says to correct the
    assertions, keep every test function, and list them in `corrected_tests`.
15. (focal, lever L11) `report.build_invoices` looks the plan up as
    `card["plans"][period["plan"]]`. 503 of the 2000 shipped billing rows carry in `plan`
    a code such as `T3415` that is no key of `rate_card.json`; each code is listed in the
    `codes` list of exactly one plan (`rate_card.json` lines 7-10, 29-31, 50-53, 72-74, 93,
    108-110, one listed code padded with a space). The contract defines Plan as the entry
    named by the account's `plan` and has no sentence about codes; the shipped card is the
    only thing that settles which entry a code names. The invoice `plan` field is the row's
    trimmed `plan` value (contract invoice shape). Every hidden corpus plants fresh codes;
    recoded and renamed accounts are named by code on at least 40% of their rows.
16. (quiet rule Q1) `parser` ignores the `estimated` field of a read. The contract makes
    `duplicate_read` compare reads of the same `estimated` value and adds the reason
    `replaced_estimate`: an estimated read gives way to an accepted actual read of the same
    account, meter and day wherever that read stands in the file. The shipped reads carry
    no `estimated` field; every hidden corpus plants estimates before and after their
    actual read, a lone estimate, two estimates of one day, an estimate whose actual read is
    malformed and an explicit `false`.
17. (quiet rule Q2) `core` prices every day at the plan's `standing_charge`. A plan can
    carry `standing_changes`; the charge of a day is the entry with the latest `from` on or
    before it, and the standing line sums the charge of each active day over the length of
    that day's month. The shipped card has no `standing_changes`; hidden plans carry
    unsorted lists with entries before, inside and after the periods.
18. (quiet rule Q3) `report` keeps one billing row per account. An account can have
    several rows that never share a day; each row is its own invoice, invoices sort by
    account and then `start`, a read belongs to the row whose period holds its day, and a
    read in no row of its account is `outside_period`. Account position (N3) is counted
    per invoice row over the accepted reads that belong to that row, and the plan of each
    row is resolved by key or listed code (L11) from that row's own `plan` value. The
    shipped billing file has one row per account; hidden rows are written out of order.
19. (quiet rule Q4) allowance no energy line of an invoice can take is added to the
    allowance of the account's next invoice by `start`, and is dropped after the last one.
    Hidden chains of two and three rows, one with an empty middle row, carry it on.
20. (quiet rule Q5) `report` keeps one accounts row per meter. A meter can have several
    rows for its account that never share a day; it is active on the days of any of them
    and keeps one standing line whose units count all those days. Hidden meters have two
    windows with a gap read that is `inactive_meter`.
21. (lever U1) `report` rates every invoice with the plan's own `tiers`. A plan can carry
    `revisions`, and the optional `payments.csv` gives paid amounts per invoice. The
    contract's Tier definition rates a plan's invoices with the `tiers` of the one revision
    under which every invoice on the plan that has a paid amount totals exactly that
    amount, and with the plan's own `tiers` when no revision or more than one does. The
    totals that must match come out of the whole account chain (carried allowance,
    account position over meters, re-shared allowance, arrears), so a revision fits only
    when every other rule is read right. The shipped card has no `revisions` and no
    `payments.csv` ships; every hidden corpus plants a plan with one fitting revision
    listed after a revision that fits only some paid amounts, a plan with two fitting
    revisions and a plan with none, plus two-row accounts on the first plan.
22. (lever D1) the credit ignores payments. The Credit paragraph gives an invoice no
    credit when the account's previous invoice by `start` has a paid amount below that
    invoice's total; an invoice with no `payments.csv` row has no paid amount. Hidden
    corpora plant four-invoice chains (underpaid, then paid at the credited figure of an
    invoice that lost its credit, then paid in two rows, then unpaid) and three-invoice
    chains with carried allowance and a standing change, rows written out of order.
23. (lever D2) a read with `cumulative` `true` holds the meter's running count. Its billed
    quantity is its count less the count of the same account and meter's accepted
    cumulative read with the latest earlier `day`; 0 without one, the whole count when the
    earlier count is larger. Hidden corpora plant counts written out of day order, a
    rejected count before the period, an estimated count replaced by an actual one, a
    drop to a lower count, chains across two billing rows and a meter exchange across two
    accounts rows with an inactive count in the gap.
24. (lever S1) the package has no statement document. The contract adds
    `python -m tariff --statements <data_dir>`: one statement per account in the optional
    `vouchers.csv`, with `balance` (invoice totals less paid amounts, 0.00 below zero),
    `redeemed` (the ids, in plain string order, of the vouchers whose amounts add up to the
    largest sum not above the balance, the first id list on ties, `[]` when none fits) and
    `due`, within 10 seconds. The oracle sorts the amounts and looks for the fewest
    small vouchers whose total stays below the common unit (greatest common divisor) of
    the rest. The rest is searched in that unit: for each voucher in id order it keeps the
    set of unit counts the later vouchers reach (an integer used as a bit set), takes the
    top count not above the balance and walks the vouchers in id order, taking each one
    whose remainder is still reachable. The small vouchers are tried in every combination
    for what is left; the first id list of each part together is the first id list of the
    whole, and no smaller unit part can win because the small ones add up to less than one
    unit. This is exact on every input. Hidden corpora copy three
    accounts with their reads scaled so the balance is 50,000.00 to 90,000.00, give each
    45 to 70 vouchers whose amounts share a factor the balance lacks (the balance itself
    is never reached), and add small accounts with equal-sum ties, an overpaid account at
    balance 0.00, and accounts that carry one quiet rule (cumulative reads, arrears,
    estimated reads, standing changes, meter rows, carried allowance, revisions), so a
    slip there moves the balance and the redeemed set. Seven further ledger corpora copy
    three accounts with their reads scaled so the balance is 400 to 800 million (in
    cents 4e10 to 8e10), and give each 46 to 55 vouchers that are multiples of one unit
    of 500.00 to 999.99 plus 9 to 11 small vouchers adding up to less than that unit, with
    equal-sum ties planted in both groups; a table over cents or over one sum, a split in
    two halves, a list of kept sums or a bounded search gives no output within 10 seconds.
    The shipped account A1643 shows the same two groups at a small balance (311.48).

## Load-bearing work

- Read the whole contract, including the Definitions list, before touching code. Three
  rules live in a definition and are applied in a later paragraph: Energy share and
  Amounts, Month and Standing lines, Account position and Energy lines.
- Share the allowance as a loop: equal parts capped at each line's remaining exact value,
  repeated over the lines still above zero until nothing is left or no line remains.
- Prorate standing per calendar month: split the meter's active days in the billing
  period by month and divide each part by that month's length; round the sum once.
- Resolve the plan: the entry whose key equals the trimmed `plan` value, else the one
  entry whose trimmed `codes` list holds it; write the trimmed value as the invoice `plan`.
- Carry the account position across the meters in `meter` order when placing tiers,
  counted per invoice row over the reads belonging to that row.
- Classify actual reads before estimated reads: `duplicate_read` keys on account, meter,
  day and `estimated`; an estimate whose actual read is accepted gets `replaced_estimate`.
- Price each active day at the standing charge in force that day (`standing_changes`).
- Bill every billing row as its own invoice, sorted by account then `start`, and carry
  allowance no energy line could take into the account's next invoice.
- Treat a meter as active on the days of any of its accounts rows.
- Re-type `quantity` strictly: `type(value) is int and value >= 0`.
- Work in exact decimals or fractions, round each line half to even at 0.01.
- Settle on the subtotal: total = subtotal x (1 - credit_rate) rounded half even.
- Correct the two assertions, keep all 13 test functions, run the visible suite, replay
  the 2000 dispute cases through the repaired package, and zip the repo per
  `build_config.json` (stored, sorted members, no directory entries, timestamp
  2015-08-24, mode 0664, no `__pycache__`).

## Verification

The test channel registers 110 positive checks worth 488 points and 2 negative checks,
`negative_hardcoded_sample_answers` (-5) and `negative_visible_test_removed` (-3).
Every check extracts `/app/out/patched-repo.zip` and runs the package inside it as
`nobody` with `setpriv`.

- Archive and metadata (3), delivered visible tests pass (3), corrected test names (3),
  regression rows (3), module notes (1), summary (1), repair report and failing cases (1).
- Shipped files: exceptions (3), standing lines (5), energy lines with subtotal, credit
  and total (5).
- Fresh corpus of 30 accounts (allowance re-shares and month-crossing periods), three of
  them reusing shipped account ids: exceptions (3), energy lines, standing lines,
  subtotals, credits and totals (5 each).
- Rescaled (fresh rows shuffled, one plan's first rate times 1.0375): energy lines,
  standing lines, subtotals, credits with totals (5 each).
- Relocated (allowance re-shares and account tier crossings; repo and data in renamed
  directories, `python -I` from a foreign working directory) and rotated (row order
  rotated in three files): lines, subtotals, credits with totals (5 each).
- Api (45 accounts through `tariff.build_invoices`, month-crossing periods and account
  tier crossings): energy lines, standing lines, subtotals, credits with totals (5 each).
- Recoded (30 accounts, codes freshly drawn and planted in the card; at least 40% of
  rows name the plan by a code, one padded) and renamed (fresh codes in card and billing
  together, plan order rotated, rows rotated): lines, subtotals, credits with totals
  (5 each).
- Missing input named (3) and two runs byte-identical (3).
- Owned quiet-rule accounts: every hidden corpus also holds 17 planted accounts (27
  invoices) owned by the quiet rules; the checks above compare only the other accounts
  and exception rows, and fifteen owned-account checks compare the planted ones whole:
  estimated reads, standing changes and meter rows (5 + 5 + 5 each, over fresh with
  rescaled, relocated with rotated, api with recoded and renamed), billing rows (5 + 5),
  carried allowance (5 + 3) and accounts combining two or three rules (3 + 3). The planted
  accounts use their own random stream (`_quiet`, seed x 31 + 7), plain plans with
  first tiers above every planted quantity, no half-cent line and allowance only on the
  carry chains; `_assert_quiet` checks that each rule, read the habitual way, changes
  exactly the accounts it owns and that the unowned part of every corpus is unchanged.
- Owned lever accounts: every hidden corpus also holds accounts owned by U1, D1 and D2
  (own random stream `_levers`, seed x 37 + 11), with `payments.csv` added: plan
  revisions (5 + 5 + 5) and revisions on two-row accounts (5 + 5), arrears chains
  (5 + 5 + 5) and arrears chains with carried allowance and a standing change (5 + 5),
  cumulative reads (5 + 5 + 5), cumulative reads across billing rows (5) and across a
  meter exchange (5). `_assert_levers` checks that each lever read the habitual way
  changes exactly its accounts and that the rest of the corpus is unchanged.
- Statements: the shipped statement document whole (5); on each hidden statement corpus
  (own random stream, seed x 53 + 29) the accounts, balances and a feasible redeemed set
  (3), every `due` (5) and every `redeemed` list (5). The statement command is run with
  `--statements` and stopped after 10 seconds. The invoice corpora are not changed by
  the statement planting; `_assert_statements` checks that every invoice outside the
  copied accounts is unchanged and that each corpus holds at least two ties.
- Ledger statements: on each hidden ledger corpus (own random stream, seed x 59 + 31)
  the accounts, balances and a feasible redeemed set (3), every `due` (5) and every
  `redeemed` list (5), run and stopped the same way. `_assert_ledger` checks that every
  invoice outside the copied accounts is unchanged, that each big balance lies between
  3e10 and 1e11 cents, that both voucher groups are used, that the overpaid account has
  balance 0.00, and that each corpus holds a tie in each group.

Every corpus generator asserts its input bounds before use: periods of 1 to 62 days that
cross a month end or are whole calendar months, two-decimal commitments and allowances,
allowances that need at least three shares where planted and 0.00 elsewhere, accounts
that cross tier 1 only through their meters where planted and stay inside it elsewhere,
at least three half-cent lines per account where no allowance is shared, a credit account
whose subtotal ends in 25 or 75 cents, an account whose subtotal equals its commitment,
a quoted quantity in every account, and in the recoded families unique codes disjoint
from every key under case and punctuation folding, a plan with two codes, two plans whose
codes share a three-character stem, a plan without codes and a padded code.

Measured on real runs (test points of 488): the oracle scores 488; the round-3 blind program (a bit set over cents) 397; a bit set over cents 397; a table of sums 306; two halves 306; a list of kept sums 306; a bounded search 306; largest voucher first 343; every subset tried 306; revisions ignored 442. Before the wave-1 ledger statements (test points of 397): the oracle scores 397; no statement command 301; largest voucher first 322; every subset tried, or a table of sums, 306 (no output in 10 seconds on any hidden corpus); a different set reaching the best sum, or ids in numeric order, 357. Before the round-3 statements (test points of 301): the oracle scores 301; revisions ignored, the first revision taken, payments ignored by the credit, or counts billed as written each 276; the first fitting revision 286; a missing payment row read as 0.00 232; all eight rules of rows 16 to 23 read the habitual way 157. Before the round-2 levers (test points of 226): `estimated` ignored
205; `standing_changes` ignored 205; last billing row only 202; allowance not carried 212;
last accounts row only 205; all five quiet rules read the habitual way 157. An unknown
plan value falling to the first or the last plan scores 186; a key-only lookup crashes on
the shipped data. Allowance shared in one or in two shares scores 166; allowance ignored
144; standing by the month of `start` 181; standing by the period length 147; tiers per
meter 181; a quoted-integer coercion 110. The judge channel carries 14 criteria, 33
positive points.

## Root cause

The package was written against the sample month, where every period lies inside one
calendar month, no account passes its first tier, every allowance is taken in one share
and no line lands on a half cent. Each shortcut (a fixed 30-day month, tiers per meter,
no allowance, floats rounded at the end, a credit base from the raw file, a lenient
integer parse) gives figures that look plausible there. Visible tests were written from
the code's own output, which froze two shortcuts into assertions.

## Solution shape

`solution/solve.py` writes corrected `parser.py`, `core.py`, `report.py`,
`__main__.py` and `__init__.py`, fixes `pyproject.toml` and the README sentences, edits
the two assertions by exact text replacement, runs the visible suite with
`python -m unittest discover`, replays every dispute case, writes the archive and the six
reports, and runs a self-check that recomputes every shipped invoice and exception with an
independent `fractions.Fraction` model, probes a month-crossing period, a half-cent line,
an altered data copy, an allowance that needs a third share and an account whose meters
cross a tier together, scans the package for bare handlers and long functions, and prints
`check R1 ok` through `check R8 ok`, `check R12 ok`, `check R13 ok` and `check R14 ok`
(two own billing rows that name their plan by a listed code, one of them padded,
recomputed and compared).

## Ordered plan

1. Read `/app/ci/api_contract.md` in full, then `tests/test_visible.py`,
   `failing_tests.log`, `regression_cases.jsonl` and the package.
2. Fix `parser`: strict quantity type, `outside_period` after `inactive_meter`,
   duplicates against earlier accepted reads of the same `estimated` value only,
   `replaced_estimate`, several accounts rows and billing rows.
3. Fix `core`: exact arithmetic, account-position tiers with inclusive `up_to`, calendar
   month standing, allowance sharing until nothing can be taken, per-line half-even
   rounding, subtotal-based credit.
4. Fix `report`: decimal loading including `allowance`, plan resolution by key or listed
   code, accepted usage only, read-id sort, amount strings.
5. Fix `__main__` missing-input handling, `VERSION`, `pyproject.toml`, README wording.
6. Correct the two assertions; run the visible suite.
7. Construct a month-crossing period, a half-cent line, a three-share allowance and a
   two-meter tier crossing by hand and compare with an independent recompute.
8. Replay the disputes, write the reports, zip the repo per `build_config.json`.
9. Re-extract the archive and run it from a foreign directory before replying.

## Pitfalls

- Sharing the allowance once, or twice, instead of until nothing is left.
- Dividing standing by the length of the start month or of the billing period.
- Restarting the tiers for each meter.
- Falling back to a default plan, or comparing codes untrimmed, when `plan` is no key.
- Keeping `int(str(q).strip())` because of the trim rule; `isinstance(q, int)`.
- `round(float, 2)`, `Decimal(float)` or `ROUND_HALF_UP`.
- Rounding the credit and subtracting it from the subtotal.
- Making the code match the two visible assertions.
- Ignoring `estimated`, or letting the first read of a day win whatever its kind.
- Pricing a day at the plan's own `standing_charge` when a change is in force, or taking
  the last listed change instead of the latest `from`.
- Keeping the last billing row or accounts row per key in a dict.
- Dropping allowance no line can take instead of carrying it to the next invoice.
- Ignoring `revisions` and `payments.csv`, or taking the first revision that fits.
- Crediting an invoice whose account's previous invoice was paid below its total, or
  treating an invoice with no payment row as paid 0.00.
- Billing a cumulative count as written, or chaining counts in file order or per row.
- Redeeming the largest vouchers first, a search that cannot finish in 10 seconds on a
  large balance, a different set of equal sum, or ids in numeric order.
- A table over cents or a split in two halves on a ledger balance of hundreds of millions.
- Validating the working tree instead of the delivered archive.
- Leaving `__pycache__` or a `.pyc` in the archive.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: tariff-engine-audit-repair
task_name: terminal-bench/tariff-engine-audit-repair
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: ceb1015ab794920d46a4bedcf45bd3e9dd003db9df57dd23eebaec84bfb0f55c  # sha256 of solution/solve.py
language: python
golden_score_measured: 1.0
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_runs: 3
golden_score_trial_id: plain__6EdDt3N
golden_score_verified_by: >
  harbor 0.24.0 oracle agent, three runs on 2026-10-27 (test-hardening round
  d11904c), tests channel reward 1.0 each; owner-only copy 1.0; nop agent reward 0.0.
caveat: >
  The test channel carries 110 positive checks worth 488 weight and 2 negative
  checks worth -8 weight. The judged channel carries 14 criteria worth 33
  positive points and 13 negative points. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward.
```
