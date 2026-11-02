# TRUTH.md - metered-usage-rating-pipeline

## Defect

Nothing is broken: the program is absent. `/app/data` holds one month of metered usage
from five regional collectors, each in its own format (csv, tsv, JSON Lines, Latin-1
fixed width text, key=value log), with the account list, the plan change log, the rate
card, the commitment pools, the product map, the collector controls and
`rating_contract.md`, which holds every rule. The deliverable is `/app/out/transform.py`,
a reusable program that writes thirteen documents per month that match the contract
exactly, on the shipped month and on fresh months it has never seen.

1. (graded) North `units` is strict. The north field block says `units` is "a JSON
   integer", and a units value not in its collector's form is `units_not_integer`. The
   same file also says surrounding spaces are removed from every text field, and in the
   other four collectors `units` is text read as ASCII digits. A shared units reader
   that accepts the JSON string `"123"` or `" 45"` as 123 and 45 accepts records that
   must be quarantined. The accepted rows sit on heavy accounts early in the month, so
   they also move the tier counter of later lines in every other region.
2. (graded) Charges are rounded per line, exactly, with ties to the even hundredth. Every
   tier 1 rate ends in a 5 in its fourth decimal place, so `units x rate` lands on an
   exact half cent for some units. `ROUND_HALF_UP`, `round(float)` or a float product
   moves those lines by 0.01, and the line moves its region's credit base, which moves
   the credit of every committed line of that region.
3. (graded) The credit base of a region is defined once, in the Glossary, as the charges
   of the accepted lines of that region whose account is a committed account, and a
   committed account is one whose value in the plan column of `accounts.csv` is
   `committed`. Only those lines receive credit; every other line has credit 0.00. The
   plan in force at the line's timestamp (written as `plan` in `normalized.jsonl`) is a
   different quantity: an account that moves to pay-as-you-go mid-month stays in the
   base, and one that moves to committed stays out. Using the line's plan in force still
   spends the whole pool, so every balance check passes while many credits are wrong.
4. (graded) "Account ids are compared after converting them to upper case and removing
   every hyphen; outputs write this canonical form." The collectors and `accounts.csv`
   always write canonical ids, so only `plan_changes.log` and the `parent` column of
   `accounts.csv` need the rule. A change line
   that names `ac-402-17` or `Ac40217` must change the plan or segment of `AC40217` from
   its timestamp on; leaving it unmatched keeps the old plan or segment, which changes
   the rate, the credit base and the `plan_changes` counts.
5. (focal) The tier of a line comes from its tier counter: the units of all earlier
   accepted lines, in all collectors, with the same product code and an account of the
   same billing group. The billing group of an account is the account itself when its
   `parent` is empty, and otherwise the billing group of the account named in its
   `parent` column, so it is the account at the top of the parent chain. Taking the
   parent named on the row (one level) splits a chain of three or four accounts into two
   counters, rates its members below the tier the group has reached, and every changed
   charge moves its region's credit base.
10. (focal) "Every run of the program finishes within 15 seconds." The long fresh months
   hold one reseller tree of 11,000 to 12,000 sub-resellers with branching side lines and
   customer accounts, over 9,000 levels deep, and 61,000 to 71,000 accepted lines. Walking
   the parent chain again for every account or for every line is exact but takes 100 to
   over 150 seconds; a recursive walk stops with RecursionError. Resolving each account's
   top once and reusing it for every account below finishes in about 3 to 6 seconds.
6. (drift) A plan or segment change takes effect at its own timestamp, inclusive: a
   usage line at that same second already uses the new value, and several changes of
   one account at one timestamp apply in file order.
7. (trap) The west collector writes local time with an offset. Month membership,
   rating order and output timestamps all use UTC, so a west line written as
   `2026-10-01T03:00:00+05:30` belongs to September.
8. (focal) Credit has two branches. When the credit base is at or below the pool, each
   counted line gets its own charge. Otherwise each counted line first gets pool x
   charge / base; a line under 0.50 gets 0.00, and every cent of the pool is shared
   again, pool x charge / summed charge of the lines that held 0.50 or more, across only
   those lines. The second pass is a fresh proportional share of the whole pool: it does
   not take the at-or-below branch even when the held lines' charges sum to less than the
   pool, so a held line's credit can exceed its charge and its net can be negative.
9. (focal) True-up: when the credit base is below the region's `minimum`, the shortfall
   (minimum - base) is shared in proportion to charge, rounded half-even; lines under 0.50
   get 0.00 and every cent of the same shortfall is shared again across the lines that
   held 0.50 or more. Recomputing the shortfall from the held lines (minimum - held
   charge) moves every true-up of the region. Net = charge - credit + true-up.

## Load-bearing work

- Read eleven inputs from the `--input` folder; stop with exit status 1 and
  `missing input: <file name>` when one is absent, and with
  `control mismatch: <file name>` when a collector's record count differs from
  `collector_controls.json`.
- Parse five collector formats into one record shape, trimming every text field, with
  the south file read as Latin-1 by character position.
- Drop later copies of a record id within one collector, then quarantine with the first
  failing reason in the stated order: `timestamp_outside_month`, `unknown_account`,
  `unknown_product`, `units_not_integer`.
- Map every collector's own product names to the four product codes through
  `products.ini`, matching each collector only against its own key.
- Replay `accounts.csv` and the matched lines of `plan_changes.log` to find the plan and
  segment in force at each line's timestamp.
- Resolve each account's billing group once, reusing the group already found for any
  account on its parent chain.
- Rate lines in rating order (UTC timestamp, then record id): tier from the units of
  earlier accepted lines of the same billing group and product in every collector, rate
  for the segment in force, charge exact and rounded half-even per line.
- Compute each region's credit base from the lines of committed accounts (plan column of
  `accounts.csv`), then each counted line's credit (own charge, or the two-pass share of
  the whole pool with the 0.50 floor) and true-up (two-pass share of the whole shortfall
  when the base is below the minimum).
- Write `normalized.jsonl`, `summary.json`, `product_summary.json`, `data_quality.json`,
  five `region_<region>.json` and four `segment_<segment>.json` documents with money as
  two-decimal strings and unit rates as four-decimal strings.

## Verification

`tests/test.sh` prepares `/logs/verifier` and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit
scores the test channel from the checks in `tests/test_output.py` and the judged channel
from `tests/judge.toml` against the agent trajectory. `tests/reward.toml` divides each
channel's weighted sum by its positive total and gives each half of the reward.

The test channel has 75 positive checks with positive weight total 295 and
1 negative check worth -5. Each row family has a visible check (weight 3)
that compares the documents in `/app/out` for the shipped month, and a `_hard` check
(weight 5) that builds a fresh month inside the tests from an embedded seeded builder
(another month, about half the size, other product names, mixed-case hyphenated ids in
the plan change log and the parent column, billing groups of two to four accounts,
parent chains up to four deep, plan changes before later usage, half-cent ties, three
regions whose pool lies between the held lines' charge and the base, one region whose
base is under its pool, three regions whose base is under its minimum), copies it into a renamed folder and runs the
delivered program there as another user from a foreign working directory. Each check
owns its rows and reports the first differing path:

- `accepted_lines`: the ordered list of accepted lines (record id, region, timestamp,
  account, product, units) in `normalized.jsonl`.
- `rating_<region>` (five): segment, tier, unit rate and charge of each line of the region.
- `credit_<region>` (five): plan and credit of each line of the region.
- `true_up_<region>` (five): true-up of each line of the region.
- `region_<region>` (five), `segment_<segment>` (four), `product_summary`, `summary`,
  `data_quality`: the whole named document.
- `mutation_tier_scale` (5): every tier threshold scaled by 1.0375 and the collector rows
  shuffled; `product_summary.json` must follow.
- `mutation_small_commitment` (3): one region's pool set to 1.00 (no line holds 0.50) and
  its minimum one cent above its base; its region document must follow.
- `mutation_near_base_pool` (5): one region's pool set one cent below its base; its
  region document must follow.
- `missing_collector` (3), `control_mismatch` (3): one collector removed or one row
  dropped; non-zero exit with the stated message, and the unaltered run succeeds.
- `determinism` (3): two runs on the fresh month give identical documents.
- `transform_exists` (1).
- `long_<k>_finishes` (3), `long_<k>_normalized` (5), `long_<k>_summary` (5),
  `long_<k>_product_summary` (3), for three long fresh months k = 1, 2, 3 built by the
  same builder with one deep reseller tree: the run exits 0 within 15 seconds and writes
  every document, and each named document equals the contract document.
- `negative_hardcoded_sample_answers` (-5): fires only when the fresh-month
  `summary.json` repeats the shipped month's month, charge, credit or net.

The judged channel has 15 criteria, positive total 28: a timed run of the
last program on `/app/data` with elapsed seconds shown; a run of the last program on a
built input larger than `/app/data`; a sum over `normalized.jsonl` shown beside the
matching `summary.json` total; the missing-input and control-mismatch refusals shown with
exit status and message; clean code in `/app/out/transform.py`; line charges recomputed
outside the program in every region; a rerun on an altered copy; a run from a foreign
directory after the last edit; the list of files written. Negatives: a check result that
no command output shows (-3), a delivered-document figure other than the file's value
(-5), an input count no command shows (-3), opening `/tests/` or `/logs/verifier` (-5),
changing a file under `/app/data` (-3). The self-check stage of `solution/solve.sh`
prints one `check <description> ok` line per check it runs (line charges, region
credits, line tiers, line credits and true_ups, segment charges, product units, summary
totals, collector counts, run time, larger input, missing input, control mismatch,
altered copy, foreign directory).

Current file hashes (sha256):

solve.sh: 2f96e68af889f678fa2ba9ac0a0e3ee77bc2db13336e17f6a21cfa264046e268
solve.py: e2822f5bf481bbefa217087c137ce0f46304d3cd09d0fe79036dc5ba2717906a
test_output.py: 6e608162522986dbf79b29f5cc508b7ae3f1d4fe610ce79d78d1f3ab192e6cc8
judge.toml: 2eb995d172cb4abaf2a105f4d665d9174ad2d6d7fc53d688b1bf54e07db21302
reward.toml: de6cf98f6e2b613d36b1867e87ed746dc93daae5ff0244254b704b334c3ac437
test.sh: 5302b9b87341ed25694888cd4c3392a46a6bd25b6f1a31fd1c6e9e109d46efd8
instruction.md: d7d756f9b72d6f36e40bfc9734df5cd20c784c53c8d6cfb7cbb1ca600c819c53
task.toml: 9d53e59cc06856ffc7b87be3f6927427e62c2466bdaa502635daad216d783ec4
rating_contract.md: bc3594b93e5f6eda11ce6a750f709792c50a9f9b40cf227f4fad1fb72106b7c8

## Root cause

The shipped month cannot separate the right reading from the habitual one for any of
the three focal rules: every `parent` chain is at most three accounts long, every pool lies under half its base so
the held lines' charge always exceeds the pool, and every minimum lies under its base so
every true-up is 0.00. No plan change precedes a later usage line of its account. The collector controls count raw records, which every reading of the
units rule reproduces; north units ships its separating rows, but a lenient reader
produces a plausible document with nothing to compare it to. The region
credit base is the quantity that carries any slip into many rows: it is computed from
every line of a committed account in the region and divides into the credit and true-up of
each of them, and the fresh month sets one pool so that the held lines' charge is a
multiple of eight and the pool a multiple of one eighth of it, so that a base off by 0.01
moves many credits.

## Solution shape

1. Parse `--input` and `--output`; check that every listed input exists in list order.
2. Load `products.ini`, `rate_card.json` with `parse_float=Decimal`, `accounts.csv`,
   `commitments.xml`, `collector_controls.json`, and the plan change history keyed by
   canonical account id, stable-sorted by timestamp.
3. Read each collector with its own reader, compare its record count with the controls,
   drop duplicate ids, and screen records in the stated reason order; north `units`
   must be a JSON integer (`type(v) is int`), text `units` must be ASCII digits.
4. Sort accepted lines by (UTC timestamp, record id); for each, look up the plan and
   segment in force, the tier from a running unit counter per (billing group, product),
   the rate, and the charge via `Decimal.quantize(Decimal("0.01"), ROUND_HALF_EVEN)`.
5. Sum the charges of committed accounts (plan column of `accounts.csv`) per region into
   the credit base. Base <= pool: each such line's credit is its charge. Otherwise first
   share `pool * charge / base`, drop lines under 0.50 to 0.00 and share the whole pool
   again over the summed charge of the held lines. Base < minimum: share
   `minimum - base` the same two-pass way into `true_up`. Others get 0.00;
   net = charge - credit + true_up.
6. Build every document from the rounded line values and write them.

## Ordered plan

1. Read `rating_contract.md` end to end, then the head of every data file.
2. Write the readers and the screening step; compare per-collector counts with the
   controls and the quarantine reasons with the raw rows.
3. Write the plan replay and the rating step with `Decimal` only.
4. Write the rating, credit and true-up steps from the Glossary definitions of the tier
   counter, the billing group, the committed account, the credit base and the minimum.
5. Write the documents, then recompute line charges, tiers, credit base, every line's
   credit and true-up, segment charges, product units and summary totals outside the
   program.
6. Build a copy of the data with altered contents (a halved pool, a non-integer north
   unit, a lower-case hyphenated id in the plan change log, a half-cent line) and check
   that the dependent figures move as the contract says.
7. Run the program from another directory on renamed folders and compare the documents.

## Pitfalls

- One units reader for all collectors that trims and parses strings, so north `"123"`
  is accepted.
- `ROUND_HALF_UP`, `round()` on floats, or rounding only the totals.
- Dividing the pool over every line of the region, or over lines whose plan in force at
  their timestamp is committed rather than lines of committed accounts.
- Counting tier units per account instead of per billing group, stopping at the parent
  named on the row, or reading `parent` without the canonical id rule.
- Walking the parent chain again for every account or every line, or recursing down it.
- Re-entering the at-or-below branch on the second credit pass, or recomputing the
  shortfall from the held lines on the second true-up pass.
- Joining `plan_changes.log` on the raw id, or only trimming it.
- Applying a change only to lines strictly after its timestamp.
- Judging month membership of west lines on local time.
- Splitting one line across two tiers, or counting quarantined units toward a tier.
- Writing money as JSON numbers, or dropping the leading `-` of a negative
  `credit_unallocated`.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: metered-usage-rating-pipeline
task_name: terminal-bench/metered-usage-rating-pipeline
fix_patch_sha256: 2f96e68af889f678fa2ba9ac0a0e3ee77bc2db13336e17f6a21cfa264046e268  # sha256 of solution/solve.sh
solve_py_sha256: e2822f5bf481bbefa217087c137ce0f46304d3cd09d0fe79036dc5ba2717906a  # informational; solve.py is 380 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured in the harness. The expected figures are exactly 1.000 on
  each oracle run and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 75 positive checks worth 295 weight and 1
  negative check worth -5 weight. The judged channel carries 15 criteria
  worth 28 positive points. tests/reward.toml divides each channel's
  weighted sum by its positive total and gives each half of the reward.
```
