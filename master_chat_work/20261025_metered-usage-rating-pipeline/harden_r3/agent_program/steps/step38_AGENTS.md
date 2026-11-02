# Metered usage rating workspace

- `/app/data` is a read-only monthly extract; `/app/data/rating_contract.md` is the
  authoritative spec and wins over anything else in that folder.
- `/app/out/transform.py` is the reusable program:
  `python3 /app/out/transform.py --input <dir> --output <dir>`. Standard library only,
  cwd-independent, deterministic; it writes the 13 output documents.

## Contract points that are easy to get wrong

- **Committed account** is decided by the `plan` column of `accounts.csv` only (start of
  month), even though the `plan` written on each normalized line is the plan *in force*
  at the line's timestamp. Credit base / true-up therefore ignore plan changes.
- **Billing group** follows the `parent` chain to its root; the tier counter is keyed by
  (billing group, product code) and counts only *earlier* accepted lines in rating order.
- **Duplicates** are per collector file, dropped before any other check, and are counted
  separately from quarantines.
- Quarantine order is fixed: timestamp → account → product → units.
- Money rounds half-even to a cent; credit and true-up are shared proportionally, shares
  under $0.50 are zeroed and the pool is re-shared over the survivors only, so the sums
  need not equal the pool exactly (`credit_unallocated` may be negative).
- north `units` must be a JSON integer (booleans, floats, strings all quarantine);
  the other collectors require ASCII digits only.
- `collector_south.txt` is Latin-1 and fixed width; `collector_west.log` timestamps carry
  UTC offsets and must be converted.

## Checking work

`/tmp/verify.py <input> <output>` (scratch, not shipped) recomputes every document a
second way and diffs it; `/tmp/make_tiny.py` builds a hand-computed 6-line fixture and
`/tmp/make_month.py` builds a different month/size extract from the real one.
