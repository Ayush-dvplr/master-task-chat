# PREMORTEM b5f7557 metered-usage-rating-pipeline (written before any other design file)

How claude-opus-5 solves this task in its first 10 minutes, step by step, and where its first-write program goes wrong per lever.

## Minute 0-2: reading order
1. `instruction.md`: learns the job (one reusable `/app/out/transform.py`, 14 output paths, whole-document exactness on fresh months, `rating_contract.md` wins every disagreement).
2. `ls -la /app/data`, `head -5` of every file, `wc -l`. It sees five collector formats, `accounts.csv` (canonical ids such as `AC40217`), `plan_changes.log` (shipped lines all canonical ids, a few ids missing from accounts.csv), `rate_card.json`, `commitments.xml`, `products.ini`, `collector_controls.json`.
3. `rating_contract.md` top to bottom, once. It skims the glossary (read first, then mostly forgotten) and reads the per-collector field blocks closely because it must write five parsers. It notes the error strings and the output key lists.
4. It greps the north file for odd `units` values and sees `"120"`, `" 45 "`, `"12.0"`, `true`, `12.5`.

## Minute 2-7: the program it writes once
- One `parse_<collector>()` per format, each yielding a dict with string fields, then a shared `clean_units(value)` that does `str(value).strip()` and `int(...)` or `isdigit()` (the global trim rule says "surrounding whitespace is removed from every text field", and the shared helper is the tidy design).
- A `canon(account_id)` helper only if the identifiers paragraph is still in mind; otherwise accounts are joined by the raw string because every collector row matches accounts.csv exactly on the shipped month.
- Plan changes loaded into `dict[account_id] -> sorted events`, keyed by the raw `account` field.
- Rating: `Decimal(str(rate))` or `float(rate)`; per-line `round(units * rate, 2)` or `quantize(Decimal("0.01"))` whose rounding mode depends on what it remembers (half-even is the Decimal context default only when no `rounding=` is passed; Opus often passes `ROUND_HALF_UP` for money by habit).
- Credits: "pool allocated pro rata by line charge" -> `share = charge / total_charge_in_region`, applied to every line in the region; or base = committed lines by the month-start plan in accounts.csv.
- Writes all 14 documents, sorts, dumps JSON with 2-decimal strings.

## Minute 7-10: self-tests it runs
- Runs on `/app/data`; checks every output parses and has the listed keys.
- Compares parsed row counts with `collector_controls.json` (records, distinct record ids): green under every reading of every lever, by design (the control counts raw data rows, not accepted rows).
- Invariants: sum of region charges == summary charge; credit applied <= pool; pool - applied small; net = charge - credit. All green under every wrong reading below.
- Perhaps one tiny hand example of a tier boundary. It rarely builds a tie by hand, a mixed-case hyphenated plan-change id, or a pay-as-you-go line in a pooled region.

## Per lever: where the first-write program goes wrong and why no self-test catches it

### LV-MU-1 (H1, L5): north `units` is a JSON integer
- Wrong point: the shared `clean_units(str(v).strip())` accepts `"120"`, `" 45 "` and `"12.0"`-as-12 (if it uses `float()` then `int()`), and Python `isinstance(True, int)` accepts `true` if it goes the type route without excluding bool.
- Why no self-test catches it: the controls count raw rows, so they match either way; the outputs are well formed either way; no shipped document says how many north records were accepted. The separating rows ship (W5 allows it for L5), so the only defence is reading the north field block or the malformed-value list, which both say it once each.
- Status: survives the pre-mortem (a careful reader can catch it, which is the L5 design; the cost is the reflex shared helper).

### LV-MU-2 (H2, L8): exact decimal, half-even per line at 0.01
- Wrong point: `rate_card.json` writes rates as JSON numbers (`0.0150`), so `json.load` hands floats; `Decimal(rate_float)` or float arithmetic breaks exact ties; or `quantize(..., ROUND_HALF_UP)` by money habit; or rounding only the totals.
- Why no self-test catches it: the shipped month has no `.xx5` line product, so every reading prints the same shipped documents. Totals invariants hold for every reading. Only an agent that builds its own tie (units 3 at rate 0.0150 -> 0.045 -> 0.04) can see it.
- Risk: a careful Opus that writes `json.load(parse_float=Decimal)` and plain `quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)` gets it right. Accepted risk; it is the master's chosen lever and the kill rule covers it.

### LV-MU-3 (H3, L9): credit base = committed-plan lines at the line timestamp in that region-month
- Wrong point: "allocated pro rata by line charge" is implemented over all lines of the region (H3), or committed status read from accounts.csv `plan` (month-start) instead of the plan in force at the line timestamp.
- Why no self-test catches it: every reading allocates the whole pool and keeps applied <= pool; there is no shipped figure of the credit base; controls carry no money.
- Status: survives; the base is defined once, in the glossary, and the credit paragraph uses the term.

### LV-MU-4 (H4, L10): account ids compare after upper-casing and removing every hyphen
- Wrong point: plan changes keyed by the raw `account` field; the hidden months write `ac-40217`, `Ac4-0217`; exact match drops them into `unmatched`; segment (rate) and plan (credit) stay at month start for the moved accounts.
- Why no self-test catches it: shipped plan_changes.log writes only canonical ids, so the shipped join is exact; the shipped unmatched count is non-zero by design (genuinely unknown accounts), so a non-zero count on a fresh month looks normal.
- Status: survives.

## Levers its first-write program would get right
None of the four is right by construction of the first program: each wrong point is the tidy default of the code shape above, and each is invisible to the self-tests above. No redesign needed before Phase 1. Deviation from IDEA recorded here and in DESIGN.md: `collector_controls.json` carries record counts only, no unit sums, because a unit sum of accepted north units would confirm the LV-MU-1 strict reading on shipped data (a separating control, LEAK_LIBRARY "self-testable rule as lever").
