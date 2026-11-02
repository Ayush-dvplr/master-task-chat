# TRUTH.md - b42c61b9-698f-5667-a335-85a1da8d5b76

## Defect

Growth analytics published the WAVE-26Q3 portfolio readout `/app/data/readout_published.csv`
from the saved query pack `/app/data/readout_query_pack.md`, and it is wrong almost
everywhere. The solver must find which rules the pack broke, decide which shipped files are
authoritative, and deliver a reusable standard-library program `/app/out/run_readout.py`
plus the 21 files it writes. The rules are in `readout_analysis_handbook.md` (revision 8),
record shapes in `feed_layouts.md`, exact output shapes and rounding in `output_contract.md`.
Governing numbers live only in the two binary files: decision parameters (Table P-1), ship
capacities (Table C-1), registry amendments (Table A-1) and window and unit rulings (Tables
X-1, U-1) only in `stats_governance_memo_w26.pdf`; the metric registry, experiment offsets,
windows and owner teams, arm weights, FX fixings and minor units only in
`experiment_workbook_w26.xlsx`.

1. (focal) Memo decoding. Text runs are placed with absolute `Tm` matrices, drawn out of
   order, and written as literal, hexadecimal or `TJ`-array strings; lines are rebuilt by y
   then x. A line-by-line `BT...ET` reading loses or scrambles rows.
2. (focal) Workbook decoding. `date1904="1"`: Experiments windows and FX dates are partly
   numeric serials from 1904-01-01. The FX release in force is the sheet named by
   `fx_sheet` of the profile (`FX-R2` shipped); `FX-R1` is a perturbed other release.
3. (focal) Identity. Links take effect at 00:00:00Z of `linked_on`; each exposure and order
   resolves at its own time; a walk stops before revisiting an id and resolves to the
   smallest id on the cycle; the internal list, Table U-1 and `identity_resolution.csv`
   resolve at the cutoff; a registry id is retired only when its link is in effect at the
   cutoff. Shipped corpus: about 15 percent of device links dated inside the readout
   period, links dated after and on the cutoff date, 8 cycles (some of U ids carried as
   `human` in the main registry), 8 old ids whose merge is dated after the cutoff and which
   therefore stay registered, and paired exposures one second before and exactly at a
   link's effective instant.
4. (focal) Refund replay. One journal over two halves in `seq` order with outcomes
   AFTER_CUTOFF, NO_ORDER, ORDER_CANCELLED, REVERSED, NOTHING_TO_REVERSE, REPLACED and
   APPLIED; a reversal withdraws the refund id's current amount (its own amount is ignored)
   and a later refund with that id is APPLIED again.
5. (focal) Valuation. As-of FX with three quote types; CHF is `UNIT_PER_EUR` and reaches
   USD through the EUR fixing of the same order date; per-order half-even micro-dollar
   rounding (KWD products produce exact ties).
6. (focal) Metrics and statistics. Registry sheet MR-7 plus IN FORCE Table A-1 amendments
   (ALL first, then by id), per-metric attribution and maturity, pooled nearest-rank
   winsorization of metric and covariate, CUPED theta rounded half to even to six decimals
   before use, unpooled and delta-method tests, exact rational lifts, SRM against
   Allocation weights with the holdout counted (closed forms for 1, 2 and 3 degrees of
   freedom), Benjamini-Hochberg over SRM-passing primaries, guardrails with P-1 margins.
7. (focal) Decisions and capacity. First-pass decision precedence, then the Table C-1
   capacity pass by the workbook `owner_team`: SHIP arms ranked by primary q-value, ties by
   `EXPERIMENT/ARM`, arms beyond `max_ship` become SHIP_DEFERRED; unlisted teams are
   unlimited, `max_ship` 0 defers all. Shipped: pricing has capacity 0, so EXP-2614 TREAT_A
   is SHIP_DEFERRED; EXP-2619 TREAT_B and EXP-2622 TREAT_A are SHIP; EXP-2625 fails the
   sample ratio check (INVALID_SRM); EXP-2637 is ABORTED; EXP-2640 is NO_SHIP_GUARDRAIL on
   aov14; EXP-2633 TREAT_A is NO_SHIP.
8. (drift) Even-split SRM, per-arm caps, per-arm or unrounded theta and lift over the
   treatment mean all look plausible; the handbook rules out each.
9. (trap) `exposure_rollup_cache.jsonl`, `fx_rates_snapshot.json`, `bot_watchlist.txt`,
   `readout_calendar.yaml` (UTC windows and a `readout_owner` that always differs from the
   workbook owner), `stats_digest_draft.txt`, `allocation_announce_sep.txt`, Tables P-0,
   C-0 and A-0, RESCINDED A-1 rows stacked on in-force cells, MR-6 and hidden DRAFT_MR-8.
10. (trap, held-out only) a four-arm experiment (three degrees of freedom), a SHORTENED
    ruling, an extended three-arm experiment, owner-team overflows including a q-value tie,
    a zero-capacity team, other registry and FX releases, other cutoffs, pre-periods and
    reporting offsets.

## Load-bearing work

22 artifacts are collected, all under `/app/out/`: `run_readout.py`, `readout.csv`,
`arm_metrics.tsv`, `winsor_caps.psv`, `cuped.json`, `srm_report.csv`, `bh_family.csv`,
`guardrails.csv`, `decisions.json`, `unit_assignments.csv`, `excluded_units.jsonl`,
`identity_resolution.csv`, `dedup_report.json`, `source_lineage.json`,
`refund_outcomes.jsonl`, `order_valuation.psv`, `metric_config_used.json`,
`experiment_windows.xml`, `portfolio_summary.json`, `variance_vs_published.csv`,
`reconciliation.md`, `manifest.json`.

- The program takes `DATA_DIR OUT_DIR` positionally and writes the 21 files.
- Every report is compared exactly after parsing its format (CSV/TSV/PSV rows, JSON values
  with types, XML attributes, markdown cells). Rational figures are rounded half to even
  from their exact values; figures through sqrt, the normal quantile, erfc or exp are IEEE
  doubles formatted to six decimals (or `.6e`). The contract states there is no tolerance,
  and the instruction states that only exact agreement counts.

## Verification

`tests/test.sh` hardens the verifier and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
`tests/reward.toml` gives each channel half of `reward`:
`test_output = 0.007462686567164179` (0.5/67) and `judge = 0.006944444444444444` (0.5/72).

Channel A (`tests/test_output.py`) has 35 checks: 21 positive (total 67) and 14 negative
(total -48).

- Ungated shape checks, weight 1: `deliverables_present`, `program_writes_contract_files`,
  `delimited_headers_exact`, `json_report_keys`, `manifest_consistent`,
  `text_serialization`.
- Core gate (a helper, not a check): the seven core reports (unit assignments, order
  valuation, metric configuration, arm metrics, readout, SRM report, decisions) must be
  exact in `/app/out` for the shipped corpus and in the program's rerun on all eight
  held-out corpora.
- Gated shipped leaf checks, weight 3: `caps_and_cuped_exact`,
  `family_and_guardrails_exact`, `exclusions_and_identity_exact`, `ingest_counters_exact`,
  `refund_outcomes_exact`, `windows_and_summary_exact`, `published_comparison_exact`.
- Gated held-out reruns, weight 5 (all 20 reports exact): `heldout_policy_exact`,
  `heldout_fourarm_exact`, `heldout_calendar_exact`, `heldout_mixed_exact`,
  `heldout_dense_exact`, `heldout_shift_exact`, `metamorphic_governance_exact`,
  `metamorphic_profile_exact`. The six `heldout_*` corpora are synthesized at grade time by
  the corpus generator embedded in the verifier with other seeds and structures; the two
  `metamorphic_*` corpora keep the shipped feeds and change only memo parameters and
  capacities, or the profile's registry and FX release.
- Negatives (True when the cheat or wrong reading is present):
  `negative_hardcoded_sample_answers` (-5), `negative_filename_dependent_behaviour` (-5),
  `negative_nondeterministic_output` (-3), `negative_touches_grader` (-5),
  `negative_echoes_published` (-3), `negative_withdrawn_parameters` (-3),
  `negative_wrong_registry_sheet` (-3), `negative_rescinded_amendment` (-3),
  `negative_holdout_tested` (-3), `negative_even_split_srm` (-3),
  `negative_unrounded_theta` (-3), `negative_ungated_identity_links` (-3),
  `negative_first_pass_decisions` (-3), `negative_withdrawn_capacity` (-3). The last five
  fire only when the delivered report equals the verifier's own derivation under exactly
  that wrong reading and that reading differs from the truth.

Channel B (`tests/judge.toml`) has 35 criteria: 26 positive (total 72, 59 of them
`critically_important`) and 9 negative (total -25). They read the trajectory and the final
answer: memo and workbook decoding steps, inspection of both FX releases, of memo Tables
C-1 and X-1 and of the workbook owner teams, the handbook ruling rule, the CHF cross, the
cycle rule, reversal replay, checks against the handbook worked examples for a link's
effective instant (H1.5), theta rounding (H10.3) and the three-degree-of-freedom tail
(H12), a self-test on a changed copy, the final run after the last edit, the final-message
items, code structure, named naive paths (snapshot FX, rollup cache as feed, watchlist
exclusion, first-arm crossovers, calendar owners), and the stated constraints (no writes
under `/app/data`, no installs, no extra files in `/app/out`).

Scores below are for the test channel only; no judged-channel oracle score exists. With
`test_output.py` run locally through rewardkit 0.2.1 at its default of eight checks in
parallel, the runner `test.sh` invokes: oracle 67/67 = 1.000, empty output 0/67, empty-file
stub 1/67, and a program that pastes the shipped answers 1/67 (six shape points, then -5).

## Root cause

Authority: the pack, the published readout, digest, announcement, calendar, snapshot,
watchlist, dashboard export and rollup cache all look official; the handbook names the memo
and workbook as the authority, and those two are the only place the governing numbers
exist. One spine: every output descends from the participant set and per-unit values, so a
wrong clock, link date, cycle, registry row, ruling, reversal, FX release, cross rate,
window, cap or theta moves arm statistics, tests, q-values, decisions and the capacity pass
at once. Interacting configuration: the registry sheet, amendments, maturity, SRM outcome,
the BH family and the capacity pass are coupled, so the capacity outcome depends on
q-values, which depend on which experiments pass the sample ratio check.

## Solution shape

`solution/solve.py` (standard library only) parses the profile, alias map, dated link
ledger, registries, the workbook (date system, registry, Experiments with owner teams,
Allocation, the named FX release, Currencies) and the memo (tokenized content streams,
lines by y then x, Tables P-1, C-1, A-1, X-1, U-1); reads the 15 layouts with their clocks,
amounts and statuses; deduplicates by revision; resolves units at record time with cycle
handling; builds participants; replays the refund journal; values orders with the three
quote types; computes metrics, caps, rounded-theta CUPED, tests, SRM, BH, guardrails,
first-pass decisions and the capacity pass; and renders the 20 reports and the manifest.

## Ordered plan

1. Read the handbook, layouts and contract.
2. Decode the memo and workbook; compare with the digest, calendar, snapshot, cache and
   announcement to see which values are stale.
3. Diff the pack queries against the handbook to list the defects for the final message.
4. Build the feed readers, dedup, record-time identity walk and eligibility.
5. Refund replay and valuation, including the CHF cross.
6. Metrics, caps, CUPED with rounded theta, tests, SRM, BH, guardrails, decisions, capacity.
7. Render, run once on `/app/data` after the last edit, test on a changed copy, report.

## Pitfalls

- Reading the memo one `BT...ET` line at a time scrambles every table.
- Ignoring `date1904` shifts all windows and FX dates by about four years.
- Using the first FX sheet found, or treating CHF as per-dollar, moves every money value.
- Resolving links without their dates, or looping on a cycle, moves participants.
- Treating a reversal as a negative refund or keeping a zero entry changes refund outcomes.
- Carrying theta at full precision moves adjusted means (fires `negative_unrounded_theta`).
- Skipping the capacity pass fires `negative_first_pass_decisions`; using Table C-0 fires
  `negative_withdrawn_capacity`.
- Implementing only the shipped corpus's paths fails the held-out reruns, which exercise a
  three-degree-of-freedom SRM, a SHORTENED ruling and capacity ties.

## Provenance

```yaml
instance_id: b42c61b9-698f-5667-a335-85a1da8d5b76
task_name: terminal-bench/b42c61b9-698f-5667-a335-85a1da8d5b76
solve_sh_sha256: 0891870e4cb0629dbad4d35e07cf4a48b93178e0f055985fe99ad174f2068539
solve_py_sha256: db79bfb8d6d484e3a950fe5a2c01fcf5b2cd15d7ac28a24a52abd5a36c8b4182
language: python
channel_a: {checks: 35, positive_total: 67, negative_total: -48}
channel_b: {criteria: 35, positive_total: 72, negative_total: -25}
```
