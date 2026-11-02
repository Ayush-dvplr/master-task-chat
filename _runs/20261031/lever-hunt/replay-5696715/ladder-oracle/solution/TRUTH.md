# TRUTH.md - 85ba8b43-fa7c-524d-8211-e73c430afb36

## Defect

The shipped `/app/data` is the complete export set and written contract for a
competitive arena game's quarterly *ladder-season settlement*. A prior settlement
pipeline computed the ladder ratings, rarity weights, calibrated smurf verdicts and
credit payouts, but the figures did not tie out and the settlement was rejected.
The agent must recompute the **corrected** settlement from the inputs and emit
twenty-nine data artifacts plus a reusable `settle.py` under `/app/out`. This is a faulty-computation-correction
task: nothing is encoded, encrypted, corrupted, or missing; every rule is written
down. The difficulty is that the obvious reading of several interacting stages is
the wrong one, and three load-bearing constants live only inside a real spreadsheet,
a real PDF, and a real DOCX.

The settlement is a nine-stage pipeline S1..S9 where an early choice cascades: which
match attempts survive (S1), which epoch anchors each match (S2), and the running
baseline (S3) all change the later unit (S4), weighting (S5), calibration (S6),
metric (S7), interval/payout (S8), and levy/floor (S9) figures. The defects the
task is built around, classified:

1. (focal) The population key is the economic match key
   `account_id|hero_handle|seed_hash|ladder_split`, not the per-attempt
   `match_uid`. `match_uid` is minted once per attempt; keying on it inflates the
   population and desyncs every downstream figure. Defeats
   `test_population_membership_exact` and the downstream stage projections.
2. (focal) The anchor is the FIRST attempt (minimum `checkpoint_no`) and the anchor
   epoch is that first attempt's `match_epoch`, while the canonical row is the
   highest-`checkpoint_no` SEALED attempt. Anchoring on the canonical row moves the
   drift-reference lookup (S4) and the maturation window (S2). Defeats the S4
   ledger-unit and downstream payout projections.
3. (focal) The two-level rarity weight is a base rate over the FROZEN tier-server
   stratum times a nonresponse factor over the SERVER - two different partitions, so
   the product does not collapse to population over resolved. Nonresponse inflation
   is applied before quantization and residue allocation. Defeats the S5 weight
   projection; the naive single-level reading is additionally penalized by rubric
   criterion R32.
4. (focal) The ore-to-ledger gain for the `ORE` currency (S4), the review-unit-cost /
   F-beta beta / CI z (S8), and the smurf levy basis points / settlement floor (S9)
   exist ONLY inside `ladder_tuning_grid.xlsx` (LIVE sheet),
   `payout_cost_policy.pdf`, and `settlement_levy_addendum.docx` respectively. A
   solver that reads only the plain-text corpus cannot converge: the xlsx-only gain
   gates the S4 ledger units and therefore the manifest digest, and the DOCX-only
   levy and floor gate the whole payout family. Defeats
   `test_confidence_intervals_exact`, `test_manifest_exact`, the levy-summary
   consistency check, and the S8/S9 payout projections.
5. (drift) The seasoned instinct is to calibrate probabilities with a
   probability-space multiplier and to group by the account's CURRENT tier. The
   contract requires log-odds-space calibration with the LIVE-sheet `a_s/b_s` and
   grouping by the FROZEN stratum; `calibration_legacy_multipliers.csv` is marked
   SUPERSEDED and the DRAFT_v1 sheet is a decoy. Probability-space calibration is
   caught by the S6 projection; using the DRAFT gain is penalized by rubric R29.
6. (trap) Verdict ordering: `amended_at` looks like the authoritative revision
   timestamp but is backfilled and unreliable. Verdicts must be ordered by
   `review_seq` within the 40-day maturation window measured from the match's own
   anchor. This is invisible on matches with a single revision and only bites on
   multi-revision matches and late verdicts. Defeats the label, weight and metric
   projections; the amended-at reading is penalized by rubric R31.
7. (trap) The S9 levy/floor decoy: `levy_floor_decoy_table.csv` ships a per-stratum
   `fake_levy_bps`/`fake_floor` explicitly marked DECOY, and `season_profile.json`
   ships `levy_bps_placeholder` as null. Only the DOCX carries the authoritative
   640-bps levy and 500-credit floor, applied levy-then-floor after the review cost.
   Using the decoy, the placeholder, or omitting S9 entirely breaks the payout
   family and the levy summary. Defeats `test_levy_summary_exact` and
   `test_payout_s9_exact`.

The reference implementation is Python standard library only. Grading uses two
non-overlapping channels: **Channel A** (`tests/test_output.py`, deterministic core
projections and byte-exact derived-view consistency) and **Channel B**
(`tests/judge.toml`, LLM-judged trajectory and closing-message quality). The rule
that combines the two channels belongs to the runner harness and is not transcribed
into the task. Core values are graded once; the remaining views are graded for
byte-exact consistency with those delivered core values.

Out of bounds: keying on `match_uid` (fails `test_population_membership_exact`,
rubric R28) or anchoring on the canonical row (fails downstream projections and
the R11 verification); using the DRAFT_v1 gain 0.0448 or the SUPERSEDED plain-text
multipliers (fails the S4/S6 projections, rubric R29); calibrating in probability
space (fails the S6 and downstream core projections); a
naive single-level weighting (fails `test_weights_rarity_weights`, rubric R32);
using the decoy levy/floor or omitting S9 (fails
`test_levy_summary_exact` and `test_payout_s9_exact`); ordering verdicts by
`amended_at` (fails the S2, S6 and S7 projections, rubric R31); reusing precomputed
artifacts instead of rebuilding from `/app/data` (rubric R30); a manifest digest
that does not match the delivered core bytes (fails `test_manifest_exact`).

## Load-bearing work

The graded artifacts, all under `/app/out`:

- `settle.py` - reusable standard-library implementation accepting `DATA_DIR` and
  `OUT_DIR`; the verifier runs it on twelve independently seeded valid corpora.

- `population.csv` - one canonical row per surviving match key (S1).
- `weights.csv` - per-match stratum, label, decision, ledger_units, p_eff, p_cal,
  weight (S3+S4+S5+S6); the interacting spine.
- `payout.csv`, `payout_breakdown.tsv`, `payout_ledger.psv`,
  `net_payout_summary.json` - rewarded/forfeited/review/levy/net credits (S4+S8+S9).
- `levy_summary.json` - the DOCX-only levy bps, settlement floor, per-stratum levy,
  and floored strata (S9).
- `metrics.json` + nine `metrics_<slug>.json` - overall (ratio-of-weighted-totals)
  + macro (weight-share means) + per-stratum precision/recall/F-beta (S7).
- `forfeited_shares.csv` - basis-point shares summing to exactly 10000 (S8,
  largest-remainder).
- `confidence_intervals.csv` - Wilson intervals on Kish n_eff (S8).
- `stratum_metrics_stream.jsonl`, `overall_metrics.md`, `reconciliation_report.md`,
  `rollup.xml`, `label_distribution.json`, `decision_distribution.json`,
  `frame_counts.json`, `weight_diagnostics.json`, `audit_summary.json` - derived
  views.
- `manifest.json` - SHA-256 over the exact bytes of the four core files
  (`population.csv`, `weights.csv`, `payout.csv`, `metrics.json`) in that order.

The exact shape of every artifact (column headers, JSON keys, numeric types, row
order and precision) is written in the agent-visible `output_artifact_schemas.md`,
so the output schema is reachable from the shipped data alone. Fixed-width decimal
fields are strings, while counts and credits are integers where the schema says so.
Rows are sorted by `match_key` or stratum as documented; files use line-feed endings
and a trailing newline. The manifest digest is computed over the delivered core
bytes, so any drift in a core file changes the digest.

Out of bounds by design: the agent never sees the verifier's sample seed, and no
graded value depends on it; the seed decides which concrete rows appear, the shipped
contract decides how to reduce any of them.

## Verification

`tests/test.sh` hardens the verifier and execs rewardkit, which scores Channel A
(`tests/test_output.py`, `@criterion` checks registered with `criteria.<name>(weight=W)`)
and Channel B (`tests/judge.toml`) and combines them as `tests/reward.toml` declares.

Channel A positive weight total is 118 across 34 positive tests. Core stage facts are
projected and compared with the reference once; derived artifacts are checked for
byte-exact consistency with the delivered core artifacts. Twelve weight-5 checks run
the delivered `settle.py` in isolated processes on different verifier-generated
corpora and compare one core outcome per corpus. The concrete rows, workbook sheet
order, and authoritative XLSX/PDF/DOCX values vary while every selection rule and
serialization requirement is published. The single negative is
worth -5 and detects undeclared copied input or reference files under `/app/out`, an
observable distinct from settlement correctness.

Positive tests: `test_population_membership_exact` (5),
the S3/S4/S5/S6 weight projections (1/5/5/5), the overall and per-stratum S7
metric projections (5/3), `test_per_stratum_metrics_exact` (1), the S8 and S9
payout projections (5/5), `test_levy_summary_exact` (1),
`test_payout_breakdown_exact` (5), `test_payout_ledger_exact` (5),
`test_net_payout_summary_exact` (5), `test_forfeited_shares_exact` (3),
`test_confidence_intervals_exact` (3), `test_manifest_exact` (3),
`test_frame_counts_exact` (1), `test_stratum_metrics_stream_exact` (5),
`test_label_distribution_exact` (1), `test_decision_distribution_exact` (1),
`test_weight_diagnostics_exact` (1), `test_audit_summary_exact` (1),
`test_overall_metrics_md_exact` (1), `test_reconciliation_report_exact` (1),
`test_rollup_exact` (1).

Unseen-corpus tests: `test_hidden_population_exact`,
`test_hidden_weights_exact`, `test_hidden_metrics_exact`,
`test_hidden_payout_exact`, `test_hidden_intervals_exact`,
`test_hidden_forfeiture_exact`, `test_hidden_levy_exact`, and
`test_hidden_manifest_exact` (5 each). The payout breakdown, payout ledger, net
payout summary, and stratum metrics stream checks add four more unseen corpora at
weight 5 while retaining their original check names.

Negative test: `negative_copies_input_or_reference_tree` (-5). It has inverted
polarity and fires only when `/app/out` contains an undeclared file. Correctness of
the declared settlement artifacts is graded only by positive checks.

The verifier regenerates the sample corpus from its embedded seed and recomputes the
settlement with an independent reader, then grades `/app/out` byte-for-byte. The
oracle (`solution/solve.py`) is a separate implementation, so the Step 10 oracle run
scoring 1.000 is real agreement between two independent solvers rather than a copy of
the grader. Flipping the xlsx-only ORE gain changes `weights.csv`, `payout.csv` and
the manifest digest; changing the DOCX-only levy/floor changes `payout.csv`,
`levy_summary.json` and the digest; all confirmed locally.

Channel B is `tests/judge.toml`: 35 criteria (29 positive with total weight 79,
6 negative with total magnitude 30). The
instruction-following items cover the required reading order, output discipline and
closing account. The process items ask for one compact constructed-case verification
per load-bearing parser or stage plus a replay from a reordered nondefault data tree,
so they grade evidence that could have caught a wrong implementation rather than
paying again for artifact bytes. The six negatives cover
distinct trajectory evidence: match_uid keying or a canonical-row anchor; DRAFT gain
or SUPERSEDED multipliers; reuse of precomputed artifacts instead of rebuilding from
`/app/data`; amended_at ordering; naive single-level weights; and an unsupported claim
that the reusable replay was performed. None duplicates the Channel A negative or a
deterministic artifact comparison. R33 judges the quality of the Python the agent
writes.

## Root cause

**Key vs. identifier.** `match_uid` is a per-attempt surrogate; the economic identity
is the four-field match key. Confusing the two is the first and most cascading error.

**Anchor vs. canonical.** The row that *locks* the match (canonical, last SEALED) is
not the row that *dates* it (anchor, first attempt). The anchor date drives the drift
lookup and the maturation window; using the canonical date silently shifts both.

**Two partitions, one product.** The base rate and the nonresponse factor are defined
on different partitions on purpose; collapsing them to one partition is the natural
but wrong reading, and quantization residue is assigned only after inflation.

**Log-odds vs. probability space.** Calibration composes in log-odds space with the
LIVE-sheet slope and intercept; a probability-space multiplier is the seasoned-but-
wrong instinct, and the plain-text multipliers are explicitly superseded.

**Binary-only constants.** The ORE gain, the cost/beta/z, and the levy/floor are
authoritative only inside the xlsx, PDF, and DOCX; the plain-text corpus documents
*that* they live there and *how* to read them, never their values, and ships explicit
decoys (`levy_floor_decoy_table.csv`, `calibration_legacy_multipliers.csv`,
`levy_bps_placeholder: null`) to punish a plain-text skim.

**Red lines.** No graded value depends on a hidden seed, environment variable,
network, or `tests/`-only constant. Every rule, including the full output schema in
`output_artifact_schemas.md`, is in the shipped `environment/data`. Difficulty is
breadth and interaction of documented rules, never hidden text.

## Solution shape

1. Read `00_pipeline_contract_overview.md` and `ordering_dependencies.yaml`; apply
   S1..S9 in the declared order, not file order. Read `output_artifact_schemas.md`
   for the exact shape of every output file.
2. S1: cluster raw matches by the four-field key; keep the highest-`checkpoint_no`
   SEALED row; drop never-sealed keys.
3. S2: anchor on the first attempt; resolve the verdict by `review_seq` within 40
   days of the anchor; map through the crosswalk; exclude holds and unmatured cases
   from both numerator and denominator.
4. S3: fold the per-stratum running baseline in ascending `match_key` order from
   `base_p`.
5. S4: convert loot to integer ledger units with the per-currency exponent, the
   xlsx-only ORE gain, and the drift multiplier dated on/before the anchor within the
   latest reference dated on or before the anchor.
6. S5: base rate over frozen stratum x nonresponse over server; inflate, quantize,
   and allocate the residue. The reported ceiling is inactive for this census.
7. S6: calibrate `sigmoid(a_s + b_s*logit(p_eff))` with the LIVE sheet; decide
   `p_cal >= tau_s`.
8. S7: weighted precision/recall/F-beta; overall as ratios of weighted totals, macro
   as weight-share means.
9. S8: Wilson intervals on Kish n_eff with the PDF z; rewarded = TP*recovery,
   forfeited = FN, review = flagged*cost; net-before-adjust = rewarded - review;
   basis-point shares to 10000 by largest remainder.
10. S9: subtract the DOCX-only smurf levy (round_half_even(rewarded*640/10000)), then
    floor the net at the DOCX-only 500 credits, last of all.
11. Emit all 29 data artifacts with the documented precision and byte discipline;
    digest the four core files; deliver the same implementation as `settle.py` and
    verify it from a nondefault data directory.

## Ordered plan

1. Survey the contract and the per-stage specs; build a stage-by-stage matrix of the
   correct reading and its source file.
2. Implement the three binary readers, then exercise each against a scratch binary
   variant that changes packaging while preserving the documented values.
3. Implement S1 through S4 and verify each stage on a compact input that separates
   the two plausible readings of its key, anchor, ordering, baseline, units and drift
   boundary.
4. Implement S5 and verify frozen-tier selection, the two partitions and
   quantization-residue handling on deliberately asymmetric examples.
5. Implement S6 through S9 and verify calibration, equality at the threshold,
   overall versus macro aggregation, unequal-weight intervals, levy/floor order and
   largest-remainder ties on small hand-worked vectors.
6. Generate the core artifacts twice, mutate one scratch byte to check digest
   sensitivity, emit all views, and report the stage readings and source files.

## Pitfalls

- Keying on `match_uid` -> fails `test_population_membership_exact` and R28.
- Anchoring on the canonical row -> fails the downstream stage projections and R11.
- DRAFT gain 0.0448 or SUPERSEDED multipliers -> fails the S4/S6 and payout
  projections, R29.
- Probability-space calibration -> fails the S6 calibration projection and the
  downstream core projections it changes.
- Decoy or omitted DOCX levy/floor -> fails `test_levy_summary_exact` and
  `test_payout_s9_exact`.
- Copying precomputed settlement files instead of rebuilding from `/app/data` -> R30.
- Ordering verdicts by `amended_at` or ignoring the window -> fails the S2, S6 and
  S7 projections, R31.
- Naive single-level weighting -> fails `test_weights_rarity_weights`, R32.
- Reading only plain text and missing the xlsx/pdf/docx constants -> fails
  `test_manifest_exact`, `test_confidence_intervals_exact`, `test_levy_summary_exact`,
  R7, R8, R9.
- A digest that does not match the delivered core bytes -> fails `test_manifest_exact`.

## Provenance

```yaml
instance_id: 85ba8b43-fa7c-524d-8211-e73c430afb36
task_name: terminal-bench/85ba8b43-fa7c-524d-8211-e73c430afb36
solve_py_sha256: c2d551ab1c82945c8ceb5d39437606984138be8491bfc7f08622770598533298
language: python
category: Data Processing
channel_a_positive_total: 118
channel_a_negative_total: -5
data_file_count: 59
artifact_count: 30
measured_oracle_reward: 1.000 # test channel, five Harbor runs
measured_nop_reward: 0.000 # test channel, one Harbor run
measured_stub_reward: 0.000 # test channel, one Harbor run
measured_owner_only_reward: 1.000 # test channel, one Harbor run
```
