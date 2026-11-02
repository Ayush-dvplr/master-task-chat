# Serialisation and digest contract

Bytes are graded, so serialisation is part of the answer.

## Every file

- utf-8, line feed endings, and exactly one trailing line feed.
- No byte order mark and no carriage returns.
- Ascii only. Nothing in this corpus needs anything else.

## Delimited files

- csv uses a comma, tsv uses a tab, psv uses a vertical bar.
- One header row carrying the column names in the published order.
- No quoting, no escaping and no spaces around a delimiter. No published
  value contains a delimiter.
- A file with no data rows is its header row and one line feed.

## json

- Two space indent, keys sorted at every level, ascii escaping, and one
  trailing line feed.

## jsonl

- One compact object per line, keys sorted, no spaces after the separators,
  and one trailing line feed.
- A ledger with no records is a single line feed.

## Numbers

- Every frame count, minor unit amount and count is a whole number written
  with no sign unless it is negative, no leading zero and no exponent.
- Every ratio is written to exactly ten decimal places, with halves going to
  the even value, no exponent and no negative zero.
- Rounding happens only when a value is written. No intermediate value is
  rounded anywhere in the pipeline.

## The core order

The digest in `manifest.json` runs over the concatenated bytes of these
seven artifacts in exactly this order:

  1. `asset_register.csv`
  2. `segment_conform.csv`
  3. `break_positions.csv`
  4. `slot_placement.csv`
  5. `avail_plan.tsv`
  6. `settlement_ledger.psv`
  7. `minutage_report.csv`

The digest is the lower case hexadecimal sha256 of that concatenation.
