# Metered usage rating contract

This contract covers one billing month of metered usage. It says how the
input files are read, how each usage record is checked, rated and credited,
and what every output document holds. Money is in USD.

## Glossary

- **collector**: one of the five regional usage feeds: central, east, north,
  south and west. The collector's name is also the line's region.
- **record**: one data line of a collector file. The header line of
  collector_central.csv and of collector_east.tsv is not a record.
- **accepted line**: a record that is not a duplicate and passes every check
  in "Checking records".
- **month**: the month named by the `month` key of collector_controls.json,
  from 00:00:00 UTC on its first day up to, but not including, 00:00:00 UTC on
  the first day of the next month.
- **rating order**: accepted lines sorted by UTC timestamp, then by
  record_id compared as plain text.
- **plan in force** and **segment in force**: the plan and segment of an
  account at a given UTC timestamp, as set out in "Plans and segments".
- **committed account**: an account whose value in the plan column of
  accounts.csv is `committed`.
- **billing group** (of an account): the account itself when its parent
  column in accounts.csv is empty, and otherwise the billing group of the
  account named in its parent column.
- **tier counter** (of a line): the total units of all earlier accepted
  lines, in all collectors, with the same product code as the line and an
  account of the same billing group as the line's account.
- **credit base** (of a region): the sum of the charges of the accepted lines
  of that region whose account is a committed account.
- **credit pool** (of a region): the `amount` of that region's `pool` element
  in commitments.xml.
- **minimum** (of a region): the `minimum` of that region's `pool` element in
  commitments.xml.

## Program

The program is run as

    python3 transform.py --input <input directory> --output <output directory>

The program reads every input file from the input directory, by the file
names below, and writes every output document into the output directory,
creating that directory when it does not exist. It does not depend on the
directory it is started from. The same input gives the same output documents
on every run. It uses only the Python 3 standard library and needs no file
other than itself and the input files.

Input files: collector_central.csv, collector_east.tsv, collector_north.jsonl,
collector_south.txt, collector_west.log, accounts.csv, plan_changes.log,
rate_card.json, commitments.xml, products.ini and collector_controls.json.

If an input file is missing, the program exits with a non-zero status and
prints `missing input: <file name>` on standard error, naming the first
missing file in the order of the list above.

## Reading files

Every file is UTF-8 except collector_south.txt, which is Latin-1. Surrounding
spaces are removed from every text field before it is read.

### Collector files

- collector_central.csv: comma separated, one header line, columns
  `record_id,timestamp,account,product,units`. The timestamp is
  `YYYY-MM-DD HH:MM:SS` in UTC.
- collector_east.tsv: tab separated, one header line, columns
  `id,epoch,account,product,qty` (`id` is the record_id, `qty` is the units).
  The timestamp is whole seconds since 1970-01-01T00:00:00Z.
- collector_north.jsonl: one JSON object per line with keys `id` (record_id),
  `at` (timestamp `YYYY-MM-DDTHH:MM:SSZ`, UTC), `acct` (account), `sku`
  (product) and `units` (a JSON integer).
- collector_south.txt: fixed width, no header. Characters 1-10 record_id,
  11-24 timestamp `YYYYMMDDHHMMSS` in UTC, 25-34 account, 35-46 product, 47-52
  units, 53-72 site name. The site name is not used.
- collector_west.log: one record per line: an ISO 8601 timestamp with a UTC
  offset, then space separated `key=value` tokens `rec` (record_id), `acct`
  (account), `product` and `qty` (units). The timestamp is converted to UTC
  before any use.

In collector_central.csv, collector_east.tsv, collector_south.txt and
collector_west.log, units is one or more ASCII digits 0-9, read as a whole
number.

Every timestamp in every input file is well formed. Every units value in its
collector's form is between 1 and 999.

### Identifiers

Account ids are compared after converting them to upper case and removing
every hyphen; outputs write this canonical form.

### Reference files

- accounts.csv: header `account_id,segment,plan,parent`. One line per account
  with the segment (consumer, smb, corporate or enterprise) and the plan
  (committed or payg) at the start of the month. `parent` is empty or the
  account_id of another account in the file.
- plan_changes.log: one change per line:
  `<YYYY-MM-DDTHH:MM:SSZ> change account=<id>`, followed by `plan=<plan>`,
  `segment=<segment>` or both. A line whose account is not in accounts.csv is
  unmatched and is ignored.
- products.ini: one section per product code (CMP, STO, EGR, SUP). In each
  section, `unit` is the billing unit and the keys central, east, north,
  south and west give the product name that collector writes. A collector's
  product name is matched exactly, after trimming, against the names on its
  own key only.
- rate_card.json: `products` maps each product code to `tiers`, a list of
  objects with `tier` (number), `from` (cumulative units at which the tier
  starts; the first tier starts at 0) and `rates` (unit rate per segment).
  Rates are written with four decimal places.
- commitments.xml: one `pool` element per region with attributes `region`,
  `amount` (the credit pool for the month) and `minimum` (the committed
  spend for the month).
- collector_controls.json: `month` (`YYYY-MM`) and, under `collectors`, one
  object per region with `file` and `records`, the number of records in that
  file. If a collector file holds a different number of records, the program
  exits with a non-zero status and prints `control mismatch: <file name>` on
  standard error.

## Checking records

Within one collector file, a record whose record_id already appeared on an
earlier record of the same file is a duplicate. Duplicates are dropped
before any other check and counted as duplicates; the first record with that
record_id is processed.

Each remaining record is checked in this order, and the first failing check
gives its quarantine reason:

1. `timestamp_outside_month`: the UTC timestamp is not in the month.
2. `unknown_account`: the account is not in accounts.csv.
3. `unknown_product`: the product name is not listed for that collector in
   products.ini.
4. `units_not_integer`: the units value is not in its collector's form.

A record that fails a check is quarantined and is not rated. Every other
record is an accepted line, rated under the product code its name maps to.

## Plans and segments

The plan and segment in force for an account at a timestamp start from
accounts.csv. Each matched line of plan_changes.log takes effect at its own
timestamp: a usage line at the same timestamp or later uses the new value of
each field the change names, and fields it does not name keep their value.
When one account has several changes at the same timestamp, they take effect
in file order.

## Rating

Accepted lines are rated in rating order. The tier of a line is the tier
with the largest `from` that is less than or equal to its tier counter. The
whole line is rated at that one tier. The unit rate is the rate of
that tier for the segment in force at the line's timestamp.

The charge of a line is its units times its unit rate, computed exactly in
decimal arithmetic on the rate as written in rate_card.json, then rounded to
0.01 with ties to the even hundredth. Totals are sums of rounded line
charges.

## Credit

The lines counted in the credit base of a region share its credit pool;
every other line has credit 0.00.

When the credit base of a region is at or below its credit pool, each
counted line receives its own charge as credit, and the rest of the pool is
left unused.

When the credit base exceeds the credit pool, each counted line first
receives credit pool times line charge divided by credit base, computed
exactly and rounded to 0.01 with ties to the even hundredth. A line whose
credit is then below 0.50 receives 0.00, and every cent of the credit pool is
shared again, pool × line charge ÷ summed charge of the lines that held 0.50
or more, rounded half-even to 0.01, across only those lines. When no line
holds 0.50 or more, every credit in the region is 0.00.

## True-up

When the credit base of a region is at or above its minimum, every line of
the region has true-up 0.00. Otherwise the shortfall of the region is its
minimum minus its credit base, and each line counted in the credit base first
receives a true-up of the shortfall in proportion to charge, rounded
half-even to 0.01. A line whose true-up is then below 0.50 receives 0.00, and
every cent of the shortfall is shared again, in proportion to charge, rounded
half-even to 0.01, across only the lines that held 0.50 or more. When no line
holds 0.50 or more, every true-up in the region is 0.00. Lines not counted in
the credit base have true-up 0.00.

The net of a line is its charge minus its credit plus its true-up. Credit,
true-up and net totals are sums of the line values.

## Output documents

Money values are JSON strings with exactly two decimal places and a leading
`-` when negative, for example `"1234.50"`. Unit rates are JSON strings with
exactly four decimal places. Counts and units are JSON integers. Timestamps
are `YYYY-MM-DDTHH:MM:SSZ` in UTC. Account ids are canonical. Key order inside
an object is free.

- transform.py: the program itself.
- normalized.jsonl: one JSON object per accepted line, in rating order, with
  keys `record_id`, `region`, `timestamp`, `account_id`, `segment` and
  `plan` (in force at the timestamp), `product` (code), `units`, `tier`,
  `unit_rate`, `charge`, `credit`, `true_up` and `net`.
- summary.json: `month`, `lines` (accepted lines), `accounts_billed`
  (distinct accounts among accepted lines), `units` (object with one key per
  product code: total units), `charge`, `credit`, `true_up` and `net`.
- product_summary.json: `month` and `products`, an object with one key per
  product code, each holding `unit` (from products.ini), `lines`, `units`,
  `charge`, `credit`, `true_up` and `net`.
- region_<region>.json, one per region: `region`, `month`, `lines`,
  `accounts` (distinct accounts), `units` (per product code), `charge`,
  `credit_pool`, `credit_base`, `credit_applied` (sum of line credits),
  `credit_unallocated` (credit_pool minus credit_applied; it may be negative),
  `minimum`, `true_up` (sum of line true-ups) and `net`.
- segment_<segment>.json, one per segment: `segment`, `month`, `lines`,
  `accounts`, `by_product` (an object with one key per product code, each
  holding `lines`, `units` and `charge`), `charge`, `credit`, `true_up` and
  `net`. A line belongs to the segment in force at its timestamp.
- data_quality.json: `month`; `collectors`, an object with one key per region,
  each holding `file`, `records`, `duplicates`, `quarantined` and `accepted`;
  `quarantine_reasons`, an object with the four reasons as keys and their
  counts; `quarantined_records`, a list of objects with `collector`,
  `record_id` and `reason`, sorted by collector and then record_id; and
  `plan_changes`, an object with `lines` (lines in plan_changes.log),
  `applied` (matched lines) and `unmatched`.
