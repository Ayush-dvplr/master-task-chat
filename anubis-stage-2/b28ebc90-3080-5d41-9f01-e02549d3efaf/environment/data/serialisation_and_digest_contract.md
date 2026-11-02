# Serialisation and digest contract

- Every document is UTF-8 with line feed endings and exactly one
  trailing line feed, except a JSONL document with no records, which
  is zero bytes.
- JSON is `indent=2`, `sort_keys=true`, `ensure_ascii=true`.
- JSONL is one object per line, `sort_keys=true`, separators `,` and
  `:` with no spaces.
- CSV is comma separated with no quoting. No published field carries
  a comma. A CSV whose group is empty is published as its header line
  alone.
- Booleans publish as `true` and `false`.
- Whole quantities publish as integers in the base unit of their
  stage. Ratios publish at exactly twelve decimal places. Negative
  zero never appears.

## Digests

- The core digest is the SHA-256, in lower case hexadecimal, of the
  concatenated bytes of `unit_normalization.json`,
  `canonical_action_order.json`, `final_action_order.json`,
  `daily_automation_manifest.json` and `next_state_snapshot.json`, in
  that order.
- The manifest body is one line per document other than
  `run_manifest.txt` and `summary.json`, in ascending file name
  order, each being the SHA-256 of that document's bytes, then two
  spaces, then the file name.
- The publication digest is the SHA-256 of the manifest body: every
  body line followed by one line feed, taken before the two trailer
  lines are appended.
- `run_manifest.txt` is the manifest body followed by `core <hex>`
  and `publication <hex>`.
- `summary.json` carries both digests and is written last.
- Both digests are taken over bytes already written. Nothing is
  recomputed after a digest is taken.

## Reading the working papers

- A text paper may open with a UTF-8 byte order mark. The mark is
  not part of the paper: it never belongs to the first line, the
  first header name or the first field.
- A line may end with a carriage return and a line feed or with a
  line feed alone. The carriage return is not part of the last
  field.
- In a delimited register (`.csv`, `.tsv`, `.psv`) a field that
  opens with a double quote runs to its closing double quote. A
  separator inside the quotes is text, a doubled double quote
  inside them is one literal double quote, and the enclosing
  quotes are not part of the value. Every other field runs from
  separator to separator exactly as written.
- A workbook grid's key cell is compared with
  `cycle_header.json.cycle_key` byte for byte. A key cell that
  differs in case, or carries a space the cycle key does not,
  names some other cycle.
