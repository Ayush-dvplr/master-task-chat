# Telemetry rollup data contract

All files are flat under `/app/data`. This contract states the rules only; it
contains no answer values. Many files in the directory are stale, draft, or
superseded copies that must not be used. Resolve the dependency chain below to
find the one authoritative workload and the one active coefficient set, then
compute each figure exactly as specified.

## 1. Dependency chain (resolve in this order)

1. Read `ingest_handoff_notes.txt`. Take the value on the single line beginning
   `catalog_ref:`. That value names the catalog database file. Ignore every
   other line in that file.
2. Open the named catalog (a SQLite database). It has one table `catalog` with
   columns `key`, `target`, `note`. Look up the row whose `key` is exactly
   `binding_registry`. Its `target` names the binding ledger file. Other keys in
   the table point at unrelated or stale material.
3. Open the binding ledger (a tab-separated file) with columns `role`,
   `generation`, `state`, `file`. Each logical role can have several rows across
   generations and states.
4. Resolve every role you need from the ledger with the supersession rule in
   section 2: `coeff` (the active coefficient set), `segments` (the active
   segment manifest), `meterseeds` (the active per-account meter seed
   overrides), `seedaddendum` (the amendment to those overrides), `regions`
   (the region offset registry), `tariff` (the tariff book), `policy` (the
   admission policy), `calibration` (the calibration controls of section 4c), and the six configuration roles `baseline`, `cost`,
   `hardware`, `queryplan`, `indexcfg`, `thresholds`.
5. Load the resolved `coeff` file (JSON). It carries the scoring coefficients,
   the window bounds per scenario, and the numeric parameters in section 4.
   Load the resolved `meterseeds` file (JSON); its `overrides` object, amended
   by the resolved `seedaddendum`, is the `meter_seed_overrides` parameter of
   section 4. The `regions`, `tariff` and `policy` sources are described in
   section 4b.
6. Open the resolved `segments` manifest (a JSONL file). Each line is an object
   with `file`, `sequence`, and `superseded`. Drop every entry whose
   `superseded` is true. Sort the remaining entries by integer `sequence`
   ascending. Concatenate the data rows of the named shard files in that order
   (shards come in the three events formats of section 3; match columns across
   shards by name as section 3 describes). The
   concatenation is the authoritative event corpus, in that exact row order.
   It is the raw corpus: section 3a decides which of its rows are admitted.

Reaching the corpus requires the entrypoint, the catalog, the ledger, the active
coefficient file, the active manifest, and the shard files it lists. A wrong
choice at any step yields a different corpus and different numbers.

## 2. Supersession rule

For a role, consider only ledger rows whose `state` is `active`. Among those,
the row with the highest integer `generation` wins. Rows whose `state` is
`draft` or `superseded` are never eligible, even if their generation is higher.
An `active` row at a lower generation never wins over an `active` row at a higher
generation. Files named as decoys (older generations, drafts, "old", "legacy",
"prev", "backup", "alt", "raw", "percent") are reachable but are never the
resolved target.

## 3. Event fields

Each corpus row carries these columns: `id`, `ts`, `account`, `region`, `kind`,
`amount`, `units`, `latency_ms`, `flag`, `meter`, `energy_wh`.

An events file (each shard, and any file handed to `aggregate`) is in one of
three formats, decided by its file extension:

- `.csv`: comma-separated, standard CSV quoting, a header line naming the
  columns.
- `.psv`: the same, but separated by `|` instead of a comma.
- `.ndjson`: one JSON object per non-blank line, keyed by column name. A value
  may be a JSON string or a JSON integer; treat it as the text of the field
  (the integer `1500` and the string `"1500"` are the same field).

Identify columns by name, never by position: a file may list the columns in a
different order and may carry extra columns or keys, which are ignored. A file
may begin with a UTF-8 byte-order mark, may use CRLF line endings, and may
contain blank lines; a blank line is not a data row. In a `.csv` or `.psv`
header, and for keys in a `.ndjson` object, identify a column after stripping
surrounding whitespace and converting its name to lower case. Thus ` Account `
and `ACCOUNT` both name the `account` column.
`ts`, `amount`, `units`, `latency_ms`, `meter`, and `energy_wh` are integers.
`meter` is a cumulative per-account counter that wraps (rolls over) at the
modulus in section 4. `energy_wh` is a vendor-supplied per-row delta that is not
trustworthy on wrap and must not be summed directly; derive usage from `meter`
as in section 5.

## 3a. Row admission

The raw corpus (and any events CSV handed to `aggregate`) is not clean. It
contains vendor re-sends of earlier rows, void notices, rows of retired event
kinds, and fields with stray whitespace and inconsistent letter case. Process every data
row in file order through these steps, in exactly this order, before any window
filter, score, checksum or meter walk:

1. **Normalise.** Strip surrounding whitespace from every field. Lower-case
   `id`, upper-case `account`, and lower-case `region`, `kind` and `flag`.
   Then apply the optional alias maps `account_aliases`, `region_aliases`,
   `kind_aliases` and `flag_aliases` from section 4. An alias lookup is a single
   lookup, not a chain; its result is already canonical. Every later step,
   every lookup in the rules, and every key written to an output uses these
   canonical values.
2. **Replay and void.** If the normalised `id` already occurred on an earlier row of the
   file, this row is a *replay* and is discarded entirely. The first occurrence
   in file order always wins, even when the replay carries different values,
   and even when that first occurrence lies outside the scenario window or is
   itself quarantined in step 3. Replay detection is done over the whole file,
   never only over the windowed rows. A replay whose normalised `flag` equals
   the active admission policy's `void_flag` (section 4b; for `aggregate`, the
   rules object's `void_flag`) is a *void notice*. Only a replay can be a void
   notice: a first occurrence carrying that flag is an ordinary event. A void
   notice is never an ordinary event and withdraws the earlier non-void
   occurrence of the same id. A withdrawn row is no longer admitted, exactly
   as if it had never been admitted. Count an id as withdrawn only when the file
   contains a non-void occurrence that would have survived quarantine. More
   than one notice for the same id has no extra effect. A rules object without
   `void_flag` has no void notices.
3. **Quarantine.** If the normalised `kind` is not a key of `kind_weights`, the
   row is *quarantined* and discarded entirely. (Its `id` still counts as having
   occurred for step 2.) An unknown `region` is not quarantined: it scores with
   an offset of 0 and still gets its own `region_totals` key. An unknown `flag`
   likewise scores with a penalty of 0 and still gets its own `flag_counts` key.
4. Every row that survives steps 2 and 3 and is never withdrawn is *admitted*.
   Only admitted rows take part in anything in section 5, including the
   pre-window meter reading.

`id` values end in a non-empty decimal integer and may have any non-empty ASCII
letter prefix, for example `e95` and `event1203`. The integer suffix is the
checksum id number. Leading zeroes in that suffix have no significance.

## 4. Coefficient and rules parameters

The active `coeff` file provides: `label`; `kind_weights` (map kind to integer);
`region_offsets` (map region to integer); `flag_penalties` (map flag to integer);
`top_n` (integer); `meter_modulus` (integer); `meter_seed` (integer, the counter
value assumed immediately before an account's first event); `tariff_bps`
(integer basis points); `tariff_tiers` (a list of `[start_wh, bps]` pairs,
described below); `unit_divisor` (integer, watt-hours per kilowatt-hour; it is
published only through calibration, section 4c);
and `scenario_windows`, a map from each scenario name to a two-element
`[window_start, window_end]` bound. The per-account `meter_seed_overrides` (map
account to integer seed) comes from the resolved `meterseeds` file, not from the
coefficient file.

A resolved rules object may also carry these optional maps and flags:

- `account_aliases`, `region_aliases`, `kind_aliases`, and `flag_aliases` map a
  normalised input value to its canonical value. Normalise both sides in the
  same way as their field before use.
- `account_meter_modulus` maps a canonical account to the modulus for that
  account's meter walk. Other accounts use `meter_modulus`.
- `account_unit_divisor` maps a canonical account to its watt-hours-per-kWh
  divisor. Other accounts use `unit_divisor`.
- `account_tariff_tiers` maps a canonical account to that account's list of
  `[start_wh, bps]` pairs. Other accounts use `tariff_tiers`.
- `account_tariff_credit_wh` maps a canonical account to a non-negative credit.
  Subtract that credit from the account's `pre_wh`, clamping at zero, before
  placing the window usage into tariff tiers.
- `meter_reset_flag`, when present, is normalised like `flag`. A row carrying
  it is still scored and counted, but its meter reading establishes a new
  baseline and contributes zero watt-hours to whichever meter walk contains
  it.

These optional keys are part of the reusable `aggregate` contract.
`resolve_rules` carries through each one present in the active coefficient set.

`tariff_tiers` is a block tariff. Sort the pairs by `start_wh` ascending (the
file need not list them in order; the lowest start is 0). The tier starting at
`start_wh` bills every watt-hour from `start_wh` (inclusive) up to the next
tier's `start_wh` (exclusive) at its `bps`; the last tier is open ended. When a
rules object has no `tariff_tiers` key, treat it as the single tier
`[[0, tariff_bps]]`; when `tariff_tiers` is present, `tariff_bps` is not used.

`meter_seed_overrides` keys are account ids written loosely: strip and
upper-case each key before use. A key ending in `*` is a prefix override. An
exact key wins; otherwise the matching wildcard with the longest prefix wins,
with lexicographically smaller keys breaking an equal-length tie. A rules
object without the key has no overrides.

## 4b. Sources beyond the coefficient file, and their precedence

- `regions` resolves to a SQLite database with one table `region_offsets`
  (columns `region`, `offset`, `state`, possibly with further columns that are
  ignored). The rows whose `state` is `active` form the `region_offsets` map
  (region to integer offset); a region name there is normalised like the
  `region` field.
- `tariff` resolves to an xlsx workbook. Its tier sheets are named
  `tiers_<year>Q<quarter>` (for example `tiers_2025Q3`); a sheet whose name adds
  `_draft`, or any sheet not named that way, is never used. The tier sheet with
  the latest year and quarter wins. Row 1 of that sheet is a header (`start_wh`,
  `bps`); every later row with both cells filled is one `[start_wh, bps]` pair of
  `tariff_tiers`. The workbook is a standard xlsx package: a cell may hold its
  value as a number or as text, inline or in the shared-strings part.
- `seedaddendum` resolves to a docx document holding one table with a header
  row (`account`, `seed`) and one row per amendment; a cell's text is the
  concatenation of all its text runs. Apply the rows in table
  order to the overrides loaded from `meterseeds`: normalise the account like the
  `account` field; a numeric seed sets that account's override, and the word
  `remove` deletes it.
- `policy` resolves to a YAML file of flat `key: value` lines (`#` starts a
  comment; a key or value may be wrapped in single or double quotes). Its `void_flag` value, normalised like `flag`, is the flag of a void
  notice in section 3a.

## 4c. Calibrated parameters

Two parameters may be held back and published only through calibration
controls with known outputs: `unit_divisor`, and the `bps` of at most one tariff
tier (a tier sheet cell reading `calibrate`; in a rules object, a tier written
`[start_wh, null]`). The controls come from the resolved `calibration` file
(JSON) and, for `aggregate`, from the rules object's `calibration` key; both
have the shape `{"energy": [{"usage_wh": U, "energy_kwh": K}, ...], "cost":
[{"pre_wh": P, "usage_wh": U, "cost_cents": C}, ...]}`.

- `unit_divisor`, when not given, is the smallest integer `D >= 1` such that
  `half_up(U, D) == K` for every energy control. A given `unit_divisor` is used
  as is.
- A held-back tier rate is the smallest integer `bps >= 0` such that, with that
  rate in that tier and every other tier as given, the section 5 cost formula
  (`half_up(tier_sum, 10000)` over the range `[P, P + U)`) gives exactly `C` for
  every cost control.

The canonical corpus holds back both: the coefficient file carries no
`unit_divisor`, and the winning tier sheet marks one rate `calibrate`.

**Precedence.** A value from a dedicated role (`regions`, `tariff`,
`seedaddendum`, `policy`) always wins over the same parameter wherever else it
appears, including the `region_offsets` and `tariff_tiers` that the coefficient
file still carries. The addendum amends the `meterseeds` overrides; it does not
replace them. Only files reached through the ledger are sources.

## 5. Corrected computation

For a scenario with bounds `[window_start, window_end]`:

- Window filter is half open. Keep an admitted row only when
  `window_start <= ts < window_end`. The upper bound is exclusive. The kept
  rows are the *windowed rows*.
- *Meter order* is admitted corpus order: the order in which the rows occur in
  the events file after replay, quarantine and withdrawal are applied. Do not
  sort meter readings by timestamp or id. The source exports cumulative counters
  in ingestion order; timestamps describe when an event occurred and can move
  backwards between consecutive readings.
- Row score is
  `amount * units * kind_weights[kind] + region_offsets.get(region, 0)
  - flag_penalties.get(flag, 0) - latency_ms // 10`
  using integer arithmetic and integer floor division for the latency term.
- `account_totals`, `region_totals`, `kind_totals` sum row scores per key over
  the windowed rows; `flag_counts` counts windowed rows per flag. Each map is
  sorted by key ascending.
- `event_count` is the number of windowed rows.
- `top_accounts` is the list of `[account, total]` pairs from `account_totals`,
  ordered by total descending then account ascending, truncated to `top_n`.
- `checksum` starts at zero and, for each windowed row in file order (the order
  the admitted rows appear in the events file, not row order), updates
  to `(checksum * 1315423911 + score * position + id_number) & 0xFFFFFFFF`,
  where `position` is the 1-based index among the windowed rows and `id_number`
  is the trailing decimal integer of the normalised id.
- Per-account energy usage, for every account that has at least one windowed
  row: walk that account's windowed rows in meter order. The running previous
  value starts at the `meter` of that account's last row in meter order whose
  `ts` is strictly below `window_start`; if the account has
  no admitted row before `window_start`, previous starts at that account's
  `meter_seed_overrides` value, or at `meter_seed` when the account has no
  override. An override never replaces a pre-window reading. Rows at
  or after `window_end` never take part. For each windowed row add
  `(meter - previous) % modulus_for_this_account` to the account usage, then set
  previous to `meter`. A row whose flag is `meter_reset_flag` instead adds zero
  and only sets previous. This modular difference is mandatory: it recovers the true
  increment across counter rollovers. Summing `energy_wh`, or subtracting first
  and last `meter` without the modulus, is wrong.
- `account_usage_wh` maps account to summed usage (sorted by key).
- `account_energy_kwh` maps account to `half_up(usage_wh, divisor_for_this_account)`, a
  single division rounded once at the end. Do not round or divide per row.
- `account_cost_cents` maps account to `half_up(tier_sum, 10000)`. Tiers are
  positions in the account's cumulative consumption, not in the window alone.
  Let `pre_wh` be the usage of the same modular walk over the account's admitted
  rows with `ts` strictly below `window_start`, in meter order, with previous
  starting at the account's `meter_seed_overrides` value, or at `meter_seed`
  when it has no override (`pre_wh` is 0 when there are no such rows). The
  Apply `account_tariff_credit_wh` to `pre_wh` as section 4 describes. The
  window's `usage_wh` watt-hours occupy the cumulative range from the resulting `pre_wh`
  (inclusive) to `pre_wh + usage_wh` (exclusive), and `tier_sum` is the sum over
  the sorted tiers of `(watt-hours of that range that fall in that tier) * bps`.
  For example, with tiers `[[0, 1000], [100, 3000]]`, `pre_wh = 0` and a usage
  of 150 Wh, `tier_sum = 100*1000 + 50*3000`; with `pre_wh = 60` and a usage of
  50 Wh, `tier_sum = 40*1000 + 10*3000`. It is applied once to the summed
  usage. Do not apply the tariff per row, do not round per tier, and
  do not reuse the already-rounded kilowatt-hour value.

`half_up(numerator, denominator)` is exact decimal division rounded half up to an
integer (Decimal ROUND_HALF_UP), never floating point.

## 6. `aggregate(events_path, rules_path)` return object

`aggregate` reads one events file (any of the section 3 formats, by column name)
and one rules JSON (whose keys mirror section 4, including the optional alias,
per-account meter and tariff keys, `meter_reset_flag`, `tariff_tiers`,
`meter_seed_overrides`, `void_flag` and `calibration`, plus
`window_start` and
`window_end`; a rules object is already resolved, so no precedence applies
inside `aggregate`), applies section 3a to the rows of that file,
then section 5, and returns an object with keys: `label`,
`window` (the two-element `[window_start, window_end]`), `event_count`,
`account_totals`, `region_totals`, `kind_totals`, `flag_counts`,
`account_usage_wh`, `account_energy_kwh`, `account_cost_cents`, `top_accounts`,
and `checksum`. All maps are sorted by key.

## 6b. `resolve_rules(data_dir, scenario)` return object

`resolve_rules` resolves the sources under `data_dir` (a directory laid out like
`/app/data`) exactly as sections 1, 2, 4, 4b and 4c describe, reading nothing
outside `data_dir`, and returns the rules object for the named scenario with
keys `label`, `window_start`, `window_end`, `kind_weights`, `region_offsets`,
`flag_penalties`, `top_n`, `meter_modulus`, `meter_seed`,
`meter_seed_overrides` (keys normalised like `account`), `tariff_tiers` (the
`[start_wh, bps]` pairs sorted by `start_wh`, every rate filled in, a held-back
one recovered), `unit_divisor` (recovered when held back) and `void_flag`
(normalised like `flag`), plus every optional alias, per-account meter and
tariff key from section 4 that is present in the active coefficient set.

## 7. Artifacts

Write every artifact as deterministic JSON with sorted keys.

Wherever an artifact lists the scenarios, list them in this canonical order:
`visible`, `peak`, `steady`, `burst`, `latency`. This is the order used by
`scenarios` in the performance report and by `scenario_checks` in the data
quality report. It is the order the artifact filenames are given in and the
order the resolved index config lists under `materialized_outputs`; it is not
alphabetical. Object keys are still sorted alphabetically everywhere.

- `scenario_visible.json`, `scenario_peak.json`, `scenario_steady.json`,
  `scenario_burst.json`, `scenario_latency.json`: each carries `scenario`,
  `source` (the resolved coefficient file plus the resolved manifest, joined by
  `+`), `result` (the aggregate object for that scenario window), `metrics`
  (`average_score` = total account score over `event_count` rounded to three
  places, `top_account`, `top_account_score`, `total_score`), and `thresholds`
  (`max_relative_median`, `max_latency_warning_ms` from the resolved thresholds
  config).
- `perf_report.json`: `ok` (the boolean `true`), `module`
  (`/app/out/optimize.py`), `benchmark_method` (the fixed string
  `repeated in-process median of aggregate vs baseline rescan engine`),
  `observed_relative_median`, `relative_target` (the thresholds
  `max_relative_median`), `scenario_count` (5), `artifact_count` (10),
  `scenarios` (the five names in the canonical order above), `baseline_name`
  (the resolved baseline config's `baseline_name`), and `hardware_profile` (the
  resolved hardware config's `profile_name`).
  `observed_relative_median` is the number you measure on the machine you are
  running on: the median wall time of your `aggregate` divided by the median wall
  time of a rescan baseline, where the rescan baseline is a straightforward
  implementation of section 5 that walks the windowed rows again for every output
  group it fills. Take the medians over repeated calls after at least one warmup
  call, and report a float greater than 0 and at most `relative_target`. Take the
  measurement outside `optimize.py`, because `optimize.py` itself must stay free
  of clock reads.
- `bottleneck_analysis.json`: `primary_bottleneck` (the fixed string
  `per_key_rescan`), `baseline_complexities` (the resolved query-plan config's
  `baseline_stages` list, copied in its stored order),
  `optimized_complexities` (that same config's `optimized_stages` list, copied
  in its stored order), `baseline_median_ms_by_scenario` (from the resolved
  query-plan config), and `highest_baseline_scenario` (the scenario with the
  greatest baseline median, with the alphabetically first scenario name winning
  a tie).
- `recommendations.json`: `group_keys`, `top_accounts_order`,
  `materialized_outputs` (from the resolved index config),
  `estimated_rewrite_fixed_cost` (from the resolved cost config), and
  `recommendations`, which is exactly these three strings in exactly this order:
  `resolve the active coefficient generation before scoring`, then
  `apply the half-open window and rollover-safe meter usage`, then
  `round energy and tariff once per account at the end`.
- `data_quality.json`: `flat_input_file_count`, `input_files` (the sorted list
  of every file name present under `/app/data`), `corpus_row_count` (data rows
  in the raw authoritative corpus of section 1), `admitted_row_count`,
  `replayed_row_count`, `quarantined_row_count` and `withdrawn_row_count` (the
  section 3a outcome over that whole raw corpus, independent of any window,
  judged with the active `kind_weights`; void notices count as replayed rows,
  and the four always add up to `corpus_row_count`), and
  `scenario_checks` (one
  entry per scenario in the canonical order above, each carrying `scenario`,
  `event_count`, `unique_accounts`, `checksum`).
