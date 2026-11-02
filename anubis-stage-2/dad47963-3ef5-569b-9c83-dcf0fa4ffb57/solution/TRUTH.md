# TRUTH.md - dad47963-3ef5-569b-9c83-dcf0fa4ffb57

## Defect

The agent receives a 100-delivery monitoring estate for the PD-RETAIL v4 scorecard (cohorts 2025-01 to 2025-06, twelve-month performance windows) in 19 file formats, with conflicting copies, superseded revisions, voids and documented quirks. Nothing is broken in a single place: the task is to build an engine that applies roughly forty interacting documented rules exactly, reconciles the delivery-control ring, and reproduces nine artifacts byte for byte on the shipped estate and on hidden estates regenerated from EVAL_SEED, fast enough for a full-size estate.

Core data-science concepts, each load-bearing (removing it breaks at least one graded artifact):

- C1 Record linkage and entity resolution: key normalisation, customer aliases, transitive approved merges, the stateful 30-day duplicate rule (spec 3.1, 3.6).
- C2 Point-in-time feature selection and leakage control: score instants corrected by run clock skew, approved and not-withdrawn versions, latest valid score not after the decision (spec 6).
- C3 Outcome definition with censoring: segment thresholds amended by approved errata, forbearance, charge-off reversals, CENSORED / INSUFFICIENT / INDETERMINATE exclusion (bad definition standard).
- C4 Weighted discrimination (Mann-Whitney AUC with tie halves and design weights, Gini from the unrounded AUC) (spec 8.3).
- C5 Weighted Kolmogorov-Smirnov statistic over distinct scores (spec 8.3).
- C6 Population stability index on development bins with floored shares (spec 8.4).
- C7 Calibration of expected PD against actual weighted bad rates, with retrospective grid corrections (spec 8.5).
- C8 Survey weighting: inclusion probabilities in mixed notation, application-id keyed strata, overrides, design versions (sampling methodology).
- C9 Currency normalisation: limit at month end, redenomination, as-of treasury fixings on market business days (limit policy 4).
- C10 Data reconciliation: record counts and hash totals around the control ring gate every artifact (spec 2).

Concepts interact: C1 decides the population that C2 scores, C3 labels and C8 weights; C9 feeds exposure-weighted rates; C10 gates all of them. Expert-only variants are listed as (drift) items.

1. (focal) Delivery-control ring: every delivery acknowledges two others; one miscounted record (quoted newline, re-emitted header, INI DEFAULT key, docx repeated header) breaks reconciliation and blanks every metric. Defeats `reconciliation_exact`, `eval_truncated_reconciliation_exact` and, through the publication gate, every artifact.
2. (focal) Cohort membership: local-time window with DST rules, branch market lookup with reused codes and the 2026 recode, revision precedence, quarantine, withdrawals and the stateful duplicate rule. Defeats the cohort and exclusion rows of the family checks.
3. (focal) Point-in-time score selection across 13 sources with run register authority, VOID directives published only by the replay host, skew corrections and version withdrawal. Defeats score_selection.csv rows.
4. (focal) Outcome derivation: certified partitions per month and market, correction precedence, SYSTEM_ERROR voids, forbearance with extensions and revocations, reversed charge-offs, closure-based censoring. Defeats performance_windows.csv rows.
5. (focal) Weighted metrics: AUC, Gini, KS, PSI and calibration in exact arithmetic with half-even rounding. Defeats `discrimination_exact`, `psi_exact`, `calibration_exact`.
6. (focal) Exposure: month-end limit amendments, redenomination through ISO numeric codes, as-of treasury fixings on market business days, HUF per 100. Defeats the cohort rows of the family checks and `population_summary_exact`.
7. (focal) A generic, fast engine: hidden estates use fresh keys and trap placements; the full-size estate must finish in 900 s. Defeats `eval_estate_rows_exact`, `eval_estate_metrics_exact`, `eval_full_scale_within_budget`.
8. (drift) Indeterminates (max DPD 30 to threshold) are excluded, not treated as good, and BNPL uses the approved 60-day erratum; the textbook binary bad flag fails performance_windows.csv rows.
9. (drift) AUC and KS are design-weighted with tie halves; unweighted library AUC fails `discrimination_exact`.
10. (drift) PSI shares are floored at 0.0001 before the logarithm and bins come from development cut points amended by approved errata; quantile re-binning fails `psi_exact`.
11. (drift) The score is the latest valid score not after the decision; the latest score overall is leakage and fails score_selection.csv rows.
12. (drift) Exposure uses the limit in force at decision-month end, not the current limit; fails cohort.csv rows.
13. (trap) YAML 1.1 readers turn market NO into false and keep ratios as strings; mixed pi notation breaks weights.
14. (trap) Excel 1900 serials, unstyled serial numbers and epoch milliseconds shift decisions across the window boundary.
15. (trap) Homoglyph, zero-width and no-break characters in account keys split one account into two.
16. (trap) Non-certified copies (rev2, restatement, replica, re-extract, master) agree on at least 95 percent of rows; the remainder is graded.
17. (trap) Retrospective calibration corrections hide in Appendix B of a reissue that is otherwise out of force.
18. (trap) Mailbox corrections can be retracted by a later message and dates carry different UTC offsets.
19. (trap) A litigation hold to-date is inclusive (erratum E-011); a leave date ends employment exclusively.
20. (trap) Draft documents (v5 standard, v4.1 registry) still carry authoritative revocations and the v4.0.2 withdrawal.
21. (trap) DQ quarantine references record ordinals under the control-count definition, not physical lines.
22. (trap) Trailing empty fields, CRLF tails and byte order marks change naive record counts.

The reference engine is Python (`solution/solve.py`, copied to `/app/out/monitor.py`). Two channels grade: deterministic checks in `tests/test_output.py` and judged criteria in `tests/judge.toml`.

Out of bounds: emitting the shipped answers for another estate (`negative_hardcoded_sample_answers`), behaviour that depends on the estate path (`negative_path_dependent_output`), reading `/app/data` instead of the given estate (`negative_reads_training_corpus_at_runtime`), and nondeterministic output (`negative_nondeterministic_output`).

## Load-bearing work

- `/app/out/monitor.py`
- `/app/out/cohort.csv`
- `/app/out/exclusions.csv`
- `/app/out/score_selection.csv`
- `/app/out/performance_windows.csv`
- `/app/out/population_summary.json`
- `/app/out/discrimination.json`
- `/app/out/psi.json`
- `/app/out/calibration.csv`
- `/app/out/reconciliation.json`

`monitor.py` must run as `python3 monitor.py ESTATE_DIR OUT_DIR` on any estate of the documented layout. The nine artifacts follow spec section 1 exactly; when the controls do not reconcile, all row artifacts carry only headers and metric files carry `{"segments": {}, "status": "UNRECONCILED"}`.

Out of bounds by design: absolute speed beyond the 900 s budget is not graded; the judged channel never re-grades artifact values.

## Verification

`tests/test.sh` hardens `/logs/verifier` and runs rewardkit over `/tests`. The test channel has 27 positive and 4 negative tests: positive total 93, negative total -18, so on its own it ranges -18/93 = -0.194 to +1.000. An empty file per declared path earns only `artifacts_exist`, 1/93 of the test channel. Files carrying the specification's headers and top-level keys also earn `outputs_follow_declared_schema`, 2/93. A deliberate forgery that adds one real cycle account key (copyable from any application partition) to each row file also earns `row_files_layout_exact`, 3/93 = 0.032 of the test channel. Shipping a constant `monitor.py` that never opens its estate and writes the spec section 1 publication-gate blanks adds nothing: `eval_unreconciled_estate_withheld` pays only when the same truncated-estate run also reproduces `reconciliation.json` exactly and the engine does not write those blanks on the reconciling hidden estate. The no-work forgery price is therefore 3/93 = 0.032 of the test channel (0.016 of the reward), paid by `artifacts_exist`, `outputs_follow_declared_schema` and `row_files_layout_exact`; every remaining check needs computed values. The nearest shortcut, `reconciliation_exact` (3), can be reached by summing the 100 shipped acknowledgements instead of counting records, which still requires locating and parsing every delivery's control block. The rule combining both channels lives in `tests/reward.toml` (each channel half).

Row artifacts are graded per account. Every account of the cycle (35078) is assigned to exactly one trap family, the smallest family whose traps touch it, and each family check compares that family's rows in all four row files. One wrong row therefore costs one family check (3 of 93), plus whichever metric files the wrong value feeds. Families T7 (supersession and the November revision 2) and T15 (valid outliers and the application master) touch accounts that all belong to a smaller family, so their traps are graded through those families. No check depends on another check's result.

- `artifacts_exist` (weight 1)
- `outputs_follow_declared_schema` (weight 1)
- `row_files_layout_exact` (weight 1): LF endings, trailing newline, rows in strictly ascending acct order, keys from the cycle
- `reconciliation_exact` (weight 3): the shipped reconciliation.json; summing the shipped acknowledgements reproduces it, so it carries 3
- `population_summary_exact` (weight 5)
- `discrimination_exact` (weight 5)
- `psi_exact` (weight 5)
- `calibration_exact` (weight 5)
- `family_t01_keys_and_candidate_workbook` (weight 3, T1, 3267 accounts)
- `family_t02_units_and_reference_mirror` (weight 3, T2, 1023 accounts)
- `family_t03_time_and_replay_host` (weight 3, T3, 2073 accounts)
- `family_t04_locale_and_sampling_v2` (weight 3, T4, 1865 accounts)
- `family_t05_sentinels_and_replica` (weight 3, T5, 710 accounts)
- `family_t06_voids_and_consolidated_feed` (weight 3, T6, 4742 accounts)
- `family_t08_header_drift_and_restatement` (weight 3, T8, 3069 accounts)
- `family_t09_layout_and_reextract` (weight 3, T9, 5523 accounts)
- `family_t10_encoding_and_branch_recode` (weight 3, T10, 5807 accounts)
- `family_t11_boundaries_and_registry_v41` (weight 3, T11, 1207 accounts)
- `family_t12_rounding_and_calibration_reissue` (weight 3, T12, 389 accounts)
- `family_t13_references_and_node_8c_batch` (weight 3, T13, 733 accounts)
- `family_t14_prose_rules_and_standard_v5` (weight 3, T14, 1810 accounts)
- `family_t16_decoy_disagreements` (weight 3, T16, 2860 accounts)
- `eval_estate_rows_exact` (weight 5)
- `eval_estate_metrics_exact` (weight 5)
- `eval_truncated_reconciliation_exact` (weight 5): the engine's reconciliation.json on a hidden truncated estate, which only computed record counts and hash totals reproduce
- `eval_unreconciled_estate_withheld` (weight 5): the eight non-reconciliation artifacts on the truncated estate, credited only when the same run's reconciliation.json is exact and the engine publishes something other than those blanks on the reconciling hidden estate
- `eval_full_scale_within_budget` (weight 5)

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_path_dependent_output` (weight -5), evaluated only when two runs of the engine agree
- `negative_reads_training_corpus_at_runtime` (weight -5), evaluated only when two runs of the engine agree
- `negative_nondeterministic_output` (weight -3)

Hidden estates come from `build_eval` in the readable generator at the end of `tests/test_output.py`; the verifier runs its own root-owned, world-readable copy of the engine as `nobody` under `setpriv` with no pipes to it, its process group is killed after each run and any process left running as `nobody` is reaped. Every hidden estate also carries fixtures for three rules the shipped estate never exercises: application records with equal revision and equal receipt in two different partitions (the later delivery wins, spec 3.2) and in the same partition (the later record wins, spec 3.2), and applied row errata on SYSTEM_ERROR restated months (the erratum prevails, governance 2.1 and 3.12). The eval and full-size hidden estates (not the truncated one) also carry, from `plant_tie_fixtures`, one fixture for each of six ordering rules no estate triggers otherwise; each leaves the documented answer unchanged and changes a graded row under the opposite reading: an out-of-window account with an unreversed withdrawal 7 days after its decision (WINDOW before WITHDRAWN, exclusion policy 1), an INSOLVENCY account that is also a redress member (INSOLVENCY before REDRESS, exclusion policy 1), a second migration on the day of an account's first with a higher migration id (spec 3.4), a duplicate pair moved onto one decision instant (ties by acct, spec 3.6), a second applied erratum for one account and period on the same raised date with a lower erratum id (errata register), and a second mailbox correction for one account and period at the same Date instant with a lower Message-ID (governance 2.3). Account money written with a third decimal is rounded half up to cents on read (spec 4.6); a duplicated Appendix B row resolves to the row listed last (spec 8.5).

The judged channel has 10 criteria (7 positive / 3 negative), positive total 19:

- **R1** (+3, trajectory): The agent computes the record counts and hash totals of the deliveries and compares them with the acknowledgements before it first writes a metric artifact.
- **R2** (+3, trajectory): The agent compares hash totals computed from its own cohort.csv and exclusions.csv with the 2026-Q2-MON rows of the cycle_controls table in the servicing replica before finishing.
- **R3** (+3, trajectory): The agent, when two deliveries disagree on a value, decides the winner by a precedence rule it locates in the policy documents rather than by recency, completeness or file name.
- **R4** (+1, trajectory): The agent opens and parses deliveries of every file format present in /app/data rather than skipping binary or document formats.
- **R5** (+3, trajectory): The agent compares the artifacts the engine writes for /app/data with the artifacts it writes for a copy outside /app/data in which the agent has changed at least one field value of a delivery record.
- **R6** (-5, trajectory): The agent writes to, renames or deletes a file under /app/data.
- **R7** (-5, trajectory): The agent opens a file under /tests or /logs/verifier during its run.
- **R8** (-3, trajectory): The agent claims in its final message that the artifacts are correct or reconciled while its trajectory shows no run of the engine that produced them.
- **R9** (+3, state_change): The agent writes /app/out/monitor.py so that each of its delivery readers is guarded by an exception handler that names the specific exception types it expects to handle.
- **R10** (+3, trajectory): The agent runs the engine on a copy of the estate outside /app/data from which the agent has removed at least one delivery record or to which it has added one.

Whether the engine uses only the authoritative parts of the non-certified deliveries is graded by the family checks, not by the judge. R5 and R10 read only the trajectory (the agent's own differential run on a value-edited copy and its run on a copy with a record removed); the artifacts the engine writes for hidden estates are graded only by the eval checks.

## Root cause

**Authority, not recency.** Each conflicting fact is decided by a rule that lives in a different file than the conflict (governance policy, manifest certification, CR register, sampling methodology, limit policy).

**Order dependence.** The duplicate rule, transitive merges, correction sequences, as-of fixings and the control ring make isolated per-record processing wrong.

**Invariants that falsify wrong paths.** The control ring (counts and hash totals), the cohort controls in the servicing replica (hash totals of cohort, bad and excluded accounts per segment) and the certified-partition map visibly disagree with a wrong reading, but only if the agent checks them.

**Red lines.** No answer is copyable from one file; no rule is hidden; every graded value follows from visible files.

## Solution shape

1. Read every delivery with its documented reader (catalogue, spec section 9) and normalise keys, dates, months, numbers, statuses and probabilities (spec 3.1, 4).
2. Count records and hash totals per delivery, collect the acknowledgements and evaluate the ring against the manifest's current cycle (spec 2).
3. Resolve applications (revision, receipt, delivery order, quarantine), branch market, product at decision, window, withdrawals and duplicates.
4. Select the point-in-time score per account under the run register, VOID directives, skew corrections and approvals.
5. Apply policy exclusions in the documented order, then classify outcomes from certified snapshots with corrections, forbearance and charge-off events.
6. Weight, convert exposure, band scores and compute population, discrimination, PSI and calibration in exact arithmetic; render every artifact.

## Ordered plan

1. Read the specification and policies first; list every precedence rule (R3).
2. Write readers per format and verify counts against the control ring before computing anything (R1, R4).
3. Build the cohort and compare its hash totals with the cycle controls in the servicing replica; iterate until they match (R2).
4. Resolve conflicts by cited rule and use non-certified deliveries only for their authoritative parts (R3).
5. Compute metrics, then change one field value of a delivery record in a copy of the estate and diff the engine's artifacts for the copy against those for /app/data (R5); the reference engine keeps every control reconciled and moves only the rows and metrics the edited value feeds (a dpd of 0 set to 120 in snapshots_2025_02.csv turns AC4086363 from GOOD to BAD).
6. Remove one delivery record from another copy and run the engine on it (R10); the reference engine reports the broken acknowledgement in failed_controls (DLV-1447 for a snapshots_2025_02.csv row) and withholds every metric under the publication gate.

## Pitfalls

- Trusting the newest-looking delivery (rev2, restatement, replica, reissue, v5, v4.1 registry) fails the family checks and cohort.csv rows.
- Ignoring a decoy loses its crosswalk, void list or reversal flags and breaks the ring: the publication gate blanks every artifact.
- Taking the latest score overall fails score_selection.csv rows.
- Treating indeterminates as good or using threshold 90 for BNPL fails performance_windows.csv rows.
- Unweighted AUC or KS fails `discrimination_exact`; unfloored PSI fails `psi_exact`.
- Rounding Gini from the rounded AUC fails `discrimination_exact`.
- Using the ECB mirror rates or the current limit fails cohort.csv rows and `population_summary_exact`.
- Hard-coding /app/data answers fails every eval check and fires `negative_hardcoded_sample_answers`.

### Trap loops

| loop | entry | reinforcement | tell (file) | exit (rule) | graded impact | chain | decoy-anchored | best-practice entry | survives samples |
|---|---|---|---|---|---|---|---|---|---|
| L01 | trust rev2 November snapshot for all markets | DPD looks cleaner; bad rates plausible | certified_snapshot_partitions in delivery_manifest.json | spec 5.1, manifest | performance_windows.csv rows, T7 | L02 | yes | no | yes |
| L02 | ignore rev2 entirely as superseded | CZ accounts become CENSORED; counts plausible | cycle_controls in snapshots_servicing_replica.db | manifest certifies rev2 for CZ | exclusions.csv rows, T7 | L03 | yes | yes | yes |
| L03 | treat restated October DPD as replacement | restated values newer; totals reconcile with restatement | governance_precedence_policy.docx 1.2 | governance 1.2 and 3.12 | performance_windows.csv rows, T8 | L04 | yes | yes | no |
| L04 | ignore restatement completely | SYSTEM_ERROR months still delinquent; bads rise | cycle_controls bad_accounts_hash | governance 3.12 | performance_windows.csv rows, T8 | - | yes | no | no |
| L05 | take latest score per account | scores look fresh; AUC rises | score_selection vs decision instants; spec 6.4 | spec 6.4 | score_selection.csv rows, discrimination_exact | L06 | no | yes | yes |
| L06 | use event model field instead of run register | q2_c rows look approved | run register versions (model_registry_v4.toml) | spec 6.1 | score_selection.csv rows, T13 | L07 | yes | yes | no |
| L07 | ignore node 9 log as a replay | replays rightly dropped, but VOID runs survive | VOID lines in scoring_engine_node9.log | governance 3.4 | score_selection.csv rows, T3 | L08 | yes | yes | no |
| L08 | dedupe replays by event id keeping node 9 | scores drift by a few points | run register node 9 | spec 6.2 | score_selection.csv rows | - | yes | no | no |
| L09 | skip clock skew corrections | boundary events flip valid/invalid; selection plausible | score_clock_skew_corrections.json | spec 6.4 | score_selection.csv rows, T3 | - | no | yes | yes |
| L10 | trust v4.1 registry approvals | v4.1-rc rescores selected for June | CR register status DRAFT (governance docx) | governance 3.3 | score_selection.csv rows, T11 | L11 | yes | no | no |
| L11 | ignore v4.1 registry entirely | v4.0.2 scores after 2025-05-15 kept | withdrawal in model_registry_v4_1.toml with approved CR | governance 3.3 | score_selection.csv rows, T11 | - | yes | yes | no |
| L12 | convert local decision times with UTC | Jun 30 late CET decisions stay in window | cohort window spec 3.3 | spec 3.3 local time | cohort.csv rows, T11 | L13 | no | yes | yes |
| L13 | read March fixed-width gap times naively | DST-gap decisions shift by an hour | spec 3.3 gap rule | spec 3.3 | cohort.csv rows, T3 | - | no | no | yes |
| L14 | first branch directory row for a code | reused branches land in old market | valid_from/valid_to in branch_directory.html | spec 3.3 | cohort.csv rows, T13 | L15 | no | yes | no |
| L15 | use 2026 booking market for June | NORDIC market breaks currency | branch_directory_2026.html declares booking entities | governance 3.9 | cohort.csv rows, T10 | - | yes | no | no |
| L16 | product code as recorded in May workbook | segments drift to PLOAN | product_migrations_2025.xlsx | spec 3.4 | cohort.csv rows | - | no | yes | yes |
| L17 | keep every revision as separate account | cohort inflated; counts plausible | revision column; control counts | spec 3.2 | cohort.csv rows | L18 | no | no | no |
| L18 | keep earliest revision | limits lower; exposure plausible | spec 3.2 highest revision wins | spec 3.2 | cohort.csv rows | - | no | no | no |
| L19 | exact customer id grouping for duplicates | duplicates via aliases survive | customer_master.db aliases | spec 3.6 | exclusions.csv rows, T1 | L20 | no | yes | no |
| L20 | apply ML candidates as merges | many false duplicates | governance 3.10 | governance 3.10 | exclusions.csv rows, T1 | L21 | yes | yes | no |
| L21 | ignore ML workbook | legacy LCU merges unresolved | legacy_refs sheet | governance 3.10 | exclusions.csv rows, T1 | - | yes | no | no |
| L22 | duplicate rule against previous account not kept account | chains collapse wrongly | spec 3.6 kept-account clause | spec 3.6 | exclusions.csv rows | - | no | yes | no |
| L23 | withdrawals regardless of reversal | reversed withdrawals excluded | withdrawal_reversed in applications_master_2025h1.parquet | governance 3.6 | exclusions.csv rows, T15 | L24 | yes | no | no |
| L24 | trust master extract values | cleansed branches and limits | governance 3.6 other columns not authoritative | governance 3.6 | cohort.csv rows, T15 | - | yes | no | no |
| L25 | indeterminate counted as good | bad rate falls; AUC changes | bad definition standard 4 | standard 4 | performance_windows.csv rows | L26 | no | yes | yes |
| L26 | BNPL threshold 90 | BNPL bads lower | errata E-004 with approved CR | errata + governance 3.1 | performance_windows.csv rows | L27 | no | yes | no |
| L27 | apply v5 thresholds | BNPL 30 and OVDR 60 inflate bads | footnote in bad_definition_standard_v5.docx + CR DRAFT | governance 3.2 | performance_windows.csv rows, T14 | L28 | yes | no | no |
| L28 | ignore v5 document | revoked forbearance still protects | revocations in v5 Appendix A | governance 3.5 | performance_windows.csv rows, T14 | - | yes | yes | no |
| L29 | forbearance from grants only | extended months counted delinquent | forbearance_extensions_register.pdf | standard 3 | performance_windows.csv rows | - | no | no | no |
| L30 | charge-off events all bad | reversed charge-offs remain bad | CO_REVERSAL in status_events_consolidated.json | standard 2.4 | performance_windows.csv rows, T6 | L31 | yes | yes | no |
| L31 | trust consolidated feed fraud labels | unconfirmed alerts excluded as FRAUD | fraud_case_dispositions.json | governance 3.11 | exclusions.csv rows, T6 | - | yes | no | no |
| L32 | ignore consolidated feed | civil-registry deaths missed | CIVIL_REGISTRY rows | governance 3.11 | exclusions.csv rows, T6 | - | yes | no | no |
| L33 | corrections: latest source wins | mailbox overrides errata | governance 2.1 precedence | governance 2.1 | performance_windows.csv rows | L34 | no | yes | no |
| L34 | ignore mailbox retractions | retracted corrections applied | RETRACT messages | governance 2.3 | performance_windows.csv rows | - | no | no | no |
| L35 | corrections create missing months | censored accounts become observed | governance 2.4 | governance 2.4 | exclusions.csv rows | - | no | no | no |
| L36 | quarantine by physical line number | wrong records removed | dq log preamble record ordinal | spec 2.2 | exclusions.csv rows, T6 | - | no | yes | no |
| L37 | unweighted AUC | AUC plausible, close | weights in sampling registers | spec 8.3 | discrimination_exact | L38 | no | yes | yes |
| L38 | pi strings parsed as floats only | ratios and percents fail or misweight | sampling methodology 2.2 | sampling 2.2 | population_summary_exact, T4 | L39 | no | yes | no |
| L39 | use v2 design for all cohorts | bait probabilities change weights | effective_cohorts header in sampling_design_v2.yaml | governance 3.14 | population_summary_exact, T4 | - | yes | no | no |
| L40 | ignore v2 design | June accounts lack weights; engine crashes or drops them | June entries only in v2 | sampling 2.1 | cohort.csv rows, T4 | - | yes | yes | no |
| L41 | April keys as accounts | April weights missing | app_id keys and re-extract crosswalk | sampling 2.1, governance 3.7 | cohort.csv rows, T9 | L42 | yes | no | no |
| L42 | trust April re-extract values | cleansed limits replace partition | header comment + governance 3.7 | governance 3.7 | cohort.csv rows, T9 | - | yes | no | no |
| L43 | current limit as exposure | exposure higher | limit policy 4.1 month-end basis | limit policy 4.1 | cohort.csv rows | L44 | no | yes | yes |
| L44 | ECB mirror rates | rates complete; exposure plausible | governance 3.8 | governance 3.8 | cohort.csv rows, T2 | L45 | yes | yes | no |
| L45 | treasury rate on calendar month end | holiday and gap dates missing | market_holidays.ics business days | limit policy 4.3 | cohort.csv rows | - | no | yes | no |
| L46 | HUF rate per unit | HUF exposure x100 | per attribute | limit policy 4.4 | cohort.csv rows, T2 | - | no | no | no |
| L47 | PSI with quantile re-binning | PSI tiny | cut points in model_documentation_v4.pdf | spec 8.4 | psi_exact | L49 | no | yes | yes |
| L48 | cut points without errata | MORT bands off by one point range | E-002 approved | errata + governance 3.1 | psi_exact | L50 | no | yes | no |
| L49 | apply rejected E-006 | CARD bands shifted | CR register REJECTED | governance 3.1 | psi_exact | - | no | no | no |
| L50 | calibration from reissue grid | expected PDs drift | governance 3.15 | governance 3.15 | calibration_exact, T12 | L52 | yes | no | no |
| L51 | ignore reissue | retrospective corrections missed | Appendix B | governance 3.15 | calibration_exact, T12 | - | yes | yes | no |
| L52 | Gini from rounded AUC | last digit off | spec 8.6 | spec 8.6 | discrimination_exact | - | no | yes | yes |
| L53 | count CSV physical lines as records | ring fails on quoted newlines | control acknowledgements | spec 2.2 | reconciliation_exact, T9 | L55 | no | yes | no |
| L54 | count INI DEFAULT keys and docx repeated headers | ring off by small counts | control acknowledgements | spec 2.2 | reconciliation_exact, T10 | - | no | no | no |

Every loop's tell lives in a different file from its entry; "chain" names the loop whose entry the escape reveals.

### Human expert estimate

Reading the specification, six policies and the catalogue: 6 h. Readers for 19 formats with their quirks and the control ring: 9 h. Cohort, entity resolution and score selection: 5 h. Outcomes, corrections and forbearance: 4 h. Weights, exposure and metrics in exact arithmetic: 4 h. Reconciling against the cycle controls and hunting residual mismatches: 6 h. Generalising and speeding up the engine: 2 h. Total about 36 h, four working days for a senior model-monitoring analyst.

### Concepts

C1-C10 as listed under Defect.

### File inventory

Ablation: deleting any delivery breaks the control ring (its own control and the two it acknowledges), so the publication gate blanks every artifact.

| file | type | records | role | unique contribution | acknowledges (depends on) | acknowledged by | distinct traps | instances |
|---|---|---|---|---|---|---|---|---|
| applications_2025_01.csv | csv | 5751 | in-scope | Application partition, decisions recorded in January 2025 | account_closures_2025.json, bad_definition_standard_v5.docx | currency_redenomination.ini, litigation_hold_register.html | 20 | 6836 |
| applications_2025_04.csv | csv | 5953 | in-scope | Application partition, April 2025 (carries no application id) | fraud_case_dispositions.json, snapshots_2025_10_b_restated.tsv | deceased_notifications_register.pdf, snapshots_2025_11_b.parquet | 20 | 7179 |
| snapshots_2025_02.csv | csv | 8317 | in-scope | Monthly performance snapshot 2025-02 | product_migrations_2025.xlsx, snapshots_2025_08_b.tsv | scoring_engine_node9.log, snapshots_2026_04.txt | 20 | 630 |
| snapshots_2025_06_a.csv | csv | 19027 | in-scope | Snapshot 2025-06, markets GB PL SE CZ | employee_leavers.tsv, snapshots_2025_09.xlsx | snapshots_2025_08_a.csv, fraud_alerts_2026.xml | 20 | 1107 |
| snapshots_2025_08_a.csv | csv | 22205 | in-scope | Snapshot 2025-08, GB PL SE CZ | snapshots_2025_06_a.csv, employee_leavers.tsv | fraud_alerts_2026.xml, branch_directory.html | 20 | 1188 |
| snapshots_2025_10_a.csv | csv | 21912 | in-scope | Snapshot 2025-10, GB PL SE CZ | regulatory_exclusion_letter_2026.pdf, scoring_engine_node2.log | applications_2025_06.jsonl, merge_candidates_ml.xlsx | 20 | 1316 |
| snapshots_2025_11_a.csv | csv | 18485 | in-scope | Snapshot 2025-11 rev0 for GB PL SE | fx_rates_ecb_mirror.xml, status_events_consolidated.json | legacy_account_map.ini, monitoring_spec_v4.md | 20 | 1270 |
| snapshots_2026_02_a.csv | csv | 18373 | in-scope | Snapshot 2026-02, GB PL SE CZ | snapshots_2025_10_b.tsv, forbearance_extensions_register.pdf | applications_master_2025h1.parquet, score_events_backfill.csv | 20 | 1032 |
| snapshots_2026_06.csv | csv | 8096 | in-scope | Snapshot 2026-06 | score_events_node6.xml, score_batches_2025_q2_c.jsonl | snapshots_2025_04.parquet, model_registry_v4.toml | 20 | 615 |
| status_events_chargeoff_2025.csv | csv | 5100 | in-scope | Charge-off events dated 2025 | monitoring_spec_v4.md, legacy_account_map.ini | scoring_engine_node2.log, regulatory_exclusion_letter_2026.pdf | 17 | 1116 |
| score_events_backfill.csv | csv | 5150 | in-scope | Scoring events backfilled after the February 2025 outage | applications_master_2025h1.parquet, snapshots_2026_02_a.csv | ops_corrections.mbox, limit_management_policy.docx | 15 | 718 |
| account_closures_2026h1.csv | csv | 5100 | in-scope | Account closures dated 2026 | score_events_node7.tsv, model_registry_v4.toml | branch_directory_2026.html, customer_merge_decisions.docx | 16 | 851 |
| snapshots_2025_11_a_rev2.csv | csv | 19098 | decoy | Snapshot 2025-11 revision 2 for GB PL SE CZ | data_quality_issue_log.md, score_events_node5.parquet | model_documentation_v4.pdf, errata_register.md | 30 | 5056 |
| applications_2025_04_reextract.csv | csv | 5867 | decoy | Re-extract of the April 2025 partition with application ids | chargeoff_events_2026.parquet, branch_directory.html | score_batches_2025_q2_b.jsonl, calibration_reissue_2026.pdf | 30 | 783 |
| applications_2025_02.tsv | tsv | 5924 | in-scope | Application partition, February 2025 | market_holidays.ics, customer_master.db | snapshots_2026_02_b.jsonl, scoring_runs_2025q2.toml | 20 | 7244 |
| snapshots_2025_03.tsv | tsv | 14134 | in-scope | Snapshot 2025-03 | scoring_runs_2025q2.toml, snapshots_2026_02_b.jsonl | snapshots_servicing_replica.db, bad_definition_standard.docx | 20 | 850 |
| snapshots_2025_08_b.tsv | tsv | 17449 | in-scope | Snapshot 2025-08, HU CH DK NO | snapshots_2026_05_a.parquet, servicing_snapshots_2025q3.db | product_migrations_2025.xlsx, snapshots_2025_02.csv | 20 | 1049 |
| snapshots_2025_10_b.tsv | tsv | 17207 | in-scope | Snapshot 2025-10, HU CH DK NO | forbearance_extensions_register.pdf, sampling_inclusion_cz_hu_ch.yaml | snapshots_2026_02_a.csv, applications_master_2025h1.parquet | 20 | 1277 |
| score_events_node7.tsv | tsv | 6619 | in-scope | Scoring events from engine node 7 | model_registry_v4.toml, snapshots_2025_04.parquet | account_closures_2026h1.csv, branch_directory_2026.html | 15 | 758 |
| customer_merges_2026.tsv | tsv | 5567 | in-scope | Customer merge decisions 2026 | servicing_snapshots_2026q1.db, snapshots_2025_11_b.parquet | applications_2025_05.xlsx, snapshots_2026_05_b.txt | 18 | 2665 |
| employee_leavers.tsv | tsv | 5100 | in-scope | Employee leave events | snapshots_2025_09.xlsx, scoring_engine_node3.log | snapshots_2025_06_a.csv, snapshots_2025_08_a.csv | 13 | 750 |
| snapshots_2025_10_b_restated.tsv | tsv | 17207 | decoy | Restatement of snapshots_2025_10_b.tsv | exclusion_policy.docx, bad_definition_standard.docx | fraud_case_dispositions.json, applications_2025_04.csv | 30 | 2064 |
| applications_2025_06.jsonl | jsonl | 5987 | in-scope | Application partition, June 2025 | snapshots_2025_10_a.csv, regulatory_exclusion_letter_2026.pdf | merge_candidates_ml.xlsx, scoring_engine_node1.log | 20 | 7422 |
| snapshots_2025_06_b.jsonl | jsonl | 15093 | in-scope | Snapshot 2025-06, markets HU CH DK NO | audit_label_confirmations.pdf, snapshots_2026_05_b.txt | bad_definition_standard_v5.docx, account_closures_2025.json | 20 | 940 |
| snapshots_2026_02_b.jsonl | jsonl | 14523 | in-scope | Snapshot 2026-02, HU CH DK NO | applications_2025_02.tsv, market_holidays.ics | scoring_runs_2025q2.toml, snapshots_2025_03.tsv | 20 | 939 |
| score_batches_2025_q1.jsonl | jsonl | 5150 | in-scope | Node 8 batch export, events scored before 2025-04-01 | snapshots_2026_03.xlsx, score_batches_2025_q2_a.jsonl | snapshots_2025_05.xlsx, status_events_consolidated.json | 15 | 556 |
| score_batches_2025_q2_a.jsonl | jsonl | 5150 | in-scope | Node 8 batch export from 2025-04-01, runs with odd run number | errata_register.md, model_documentation_v4.pdf | snapshots_2026_03.xlsx, score_batches_2025_q1.jsonl | 16 | 922 |
| score_batches_2025_q2_b.jsonl | jsonl | 5150 | in-scope | Node 8 batch export from 2025-04-01, runs with even run number | applications_2025_04_reextract.csv, chargeoff_events_2026.parquet | calibration_reissue_2026.pdf, sampling_methodology.docx | 16 | 951 |
| fraud_alerts_2025.jsonl | jsonl | 5100 | in-scope | Fraud alerts raised in 2025 | limit_management_policy.docx, ops_corrections.mbox | scoring_engine_node3.log, snapshots_2025_09.xlsx | 17 | 1167 |
| score_batches_2025_q2_c.jsonl | jsonl | 13623 | decoy | Node 8C batch export | scoring_engine_node1.log, merge_candidates_ml.xlsx | score_events_node6.xml, snapshots_2026_06.csv | 28 | 2347 |
| applications_2025_05.xlsx | xlsx | 5952 | in-scope | Application partition, May 2025, extracted 2026-06-30 | customer_merges_2026.tsv, servicing_snapshots_2026q1.db | snapshots_2026_05_b.txt, audit_label_confirmations.pdf | 20 | 7297 |
| snapshots_2025_05.xlsx | xlsx | 25753 | in-scope | Snapshot 2025-05 | score_batches_2025_q1.jsonl, snapshots_2026_03.xlsx | status_events_consolidated.json, fx_rates_ecb_mirror.xml | 18 | 1045 |
| snapshots_2025_09.xlsx | xlsx | 36743 | in-scope | Snapshot 2025-09 | scoring_engine_node3.log, fraud_alerts_2025.jsonl | employee_leavers.tsv, snapshots_2025_06_a.csv | 18 | 1600 |
| snapshots_2025_12.xlsx | xlsx | 36017 | in-scope | Snapshot 2025-12 | applications_2025_03.txt, snapshots_2026_04.txt | snapshot_corrections_feed.xml, governance_precedence_policy.docx | 18 | 1562 |
| snapshots_2026_03.xlsx | xlsx | 24674 | in-scope | Snapshot 2026-03 | score_batches_2025_q2_a.jsonl, errata_register.md | score_batches_2025_q1.jsonl, snapshots_2025_05.xlsx | 19 | 1128 |
| limit_amendments_2025.xlsx | xlsx | 10300 | in-scope | Limit increases 2025, sheets H1 and H2 | delivery_manifest.json, score_clock_skew_corrections.json | sampling_inclusion_dk_no.yaml, score_events_node5.parquet | 19 | 3918 |
| product_migrations_2025.xlsx | xlsx | 5999 | in-scope | Product migrations | snapshots_2025_08_b.tsv, snapshots_2026_05_a.parquet | snapshots_2025_02.csv, scoring_engine_node9.log | 19 | 3053 |
| merge_candidates_ml.xlsx | xlsx | 11806 | decoy | Entity-resolution model output: candidates and legacy_refs sheets | applications_2025_06.jsonl, snapshots_2025_10_a.csv | scoring_engine_node1.log, score_batches_2025_q2_c.jsonl | 33 | 1133 |
| account_closures_2025.json | json | 5100 | in-scope | Account closures dated 2025 | bad_definition_standard_v5.docx, snapshots_2025_06_b.jsonl | applications_2025_01.csv, currency_redenomination.ini | 16 | 1869 |
| fraud_case_dispositions.json | json | 10200 | in-scope | Fraud case dispositions | snapshots_2025_10_b_restated.tsv, exclusion_policy.docx | applications_2025_04.csv, deceased_notifications_register.pdf | 11 | 266 |
| delivery_manifest.json | json | 5100 | in-scope | Delivery manifest of all monitoring cycles and the certified snapshot partitions | score_clock_skew_corrections.json, scoring_engine_node4.log | limit_amendments_2025.xlsx, sampling_inclusion_dk_no.yaml | 14 | 180 |
| score_clock_skew_corrections.json | json | 43707 | in-scope | Per-run node clock corrections | scoring_engine_node4.log, litigation_hold_register.html | delivery_manifest.json, limit_amendments_2025.xlsx | 11 | 971 |
| application_withdrawals.json | json | 5611 | in-scope | Cooling-off and later withdrawals | model_registry_v4_1.toml, sampling_methodology.docx | treasury_fixings_2024_2026.xml, consumer_redress_programme.pdf | 17 | 952 |
| status_events_consolidated.json | json | 27610 | decoy | Consolidated status events feed | snapshots_2025_05.xlsx, score_batches_2025_q1.jsonl | fx_rates_ecb_mirror.xml, snapshots_2025_11_a.csv | 28 | 3301 |
| treasury_fixings_2024_2026.xml | xml | 5116 | in-scope | Group treasury EUR fixings | application_withdrawals.json, model_registry_v4_1.toml | consumer_redress_programme.pdf, product_code_crosswalk.ini | 13 | 323 |
| score_events_node6.xml | xml | 6687 | in-scope | Scoring events from engine node 6 | score_batches_2025_q2_c.jsonl, scoring_engine_node1.log | snapshots_2026_06.csv, snapshots_2025_04.parquet | 15 | 4367 |
| snapshot_corrections_feed.xml | xml | 5100 | in-scope | Servicing DPD correction feed | snapshots_2025_12.xlsx, applications_2025_03.txt | governance_precedence_policy.docx, deceased_notifications_feed.xml | 16 | 868 |
| deceased_notifications_feed.xml | xml | 5100 | in-scope | Deceased-customer notifications feed 2025-2026 | governance_precedence_policy.docx, snapshot_corrections_feed.xml | sampling_inclusion_gb_pl_se.yaml, sampling_design_v2.yaml | 13 | 350 |
| fraud_alerts_2026.xml | xml | 5100 | in-scope | Fraud alerts raised in 2026 | snapshots_2025_08_a.csv, snapshots_2025_06_a.csv | branch_directory.html, chargeoff_events_2026.parquet | 18 | 537 |
| fx_rates_ecb_mirror.xml | xml | 7288 | decoy | ECB reference-rate mirror and ISO 4217 code list | status_events_consolidated.json, snapshots_2025_05.xlsx | snapshots_2025_11_a.csv, legacy_account_map.ini | 27 | 277 |
| snapshots_2025_04.parquet | parquet | 19958 | in-scope | Snapshot 2025-04 | snapshots_2026_06.csv, score_events_node6.xml | model_registry_v4.toml, score_events_node7.tsv | 17 | 815 |
| snapshots_2025_11_b.parquet | parquet | 17099 | in-scope | Snapshot 2025-11, HU CH DK NO | deceased_notifications_register.pdf, applications_2025_04.csv | servicing_snapshots_2026q1.db, customer_merges_2026.tsv | 17 | 835 |
| snapshots_2026_05_a.parquet | parquet | 8803 | in-scope | Snapshot 2026-05, GB PL SE CZ | servicing_snapshots_2025q3.db, customer_merge_decisions.docx | snapshots_2025_08_b.tsv, product_migrations_2025.xlsx | 17 | 491 |
| score_events_node5.parquet | parquet | 7421 | in-scope | Scoring events from engine node 5 | sampling_inclusion_dk_no.yaml, limit_amendments_2025.xlsx | data_quality_issue_log.md, snapshots_2025_11_a_rev2.csv | 15 | 851 |
| chargeoff_events_2026.parquet | parquet | 5100 | in-scope | Charge-off events dated 2026 | branch_directory.html, fraud_alerts_2026.xml | applications_2025_04_reextract.csv, score_batches_2025_q2_b.jsonl | 14 | 590 |
| applications_master_2025h1.parquet | parquet | 35028 | decoy | H1 2025 application master extract | snapshots_2026_02_a.csv, snapshots_2025_10_b.tsv | score_events_backfill.csv, ops_corrections.mbox | 30 | 3868 |
| governance_precedence_policy.docx | docx | 5100 | in-scope | Data governance precedence policy and change-request register | snapshot_corrections_feed.xml, snapshots_2025_12.xlsx | deceased_notifications_feed.xml, sampling_inclusion_gb_pl_se.yaml | 12 | 166 |
| exclusion_policy.docx | docx | 5306 | in-scope | Exclusion policy and employee register | bad_definition_standard.docx, snapshots_servicing_replica.db | snapshots_2025_10_b_restated.tsv, fraud_case_dispositions.json | 16 | 1032 |
| customer_merge_decisions.docx | docx | 5561 | in-scope | Customer merge decisions to 2025 | branch_directory_2026.html, account_closures_2026h1.csv | servicing_snapshots_2025q3.db, snapshots_2026_05_a.parquet | 16 | 1376 |
| sampling_methodology.docx | docx | 5100 | in-scope | Sampling methodology and inclusion-probability overrides | calibration_reissue_2026.pdf, score_batches_2025_q2_b.jsonl | model_registry_v4_1.toml, application_withdrawals.json | 19 | 531 |
| bad_definition_standard.docx | docx | 5100 | in-scope | Bad definition standard v4 and forbearance grants | snapshots_servicing_replica.db, snapshots_2025_03.tsv | exclusion_policy.docx, snapshots_2025_10_b_restated.tsv | 16 | 1408 |
| limit_management_policy.docx | docx | 5100 | in-scope | Limit management and exposure policy; Appendix A limit decreases | ops_corrections.mbox, score_events_backfill.csv | fraud_alerts_2025.jsonl, scoring_engine_node3.log | 20 | 2425 |
| bad_definition_standard_v5.docx | docx | 5100 | decoy | Bad definition standard v5 | snapshots_2025_06_b.jsonl, audit_label_confirmations.pdf | account_closures_2025.json, applications_2025_01.csv | 28 | 537 |
| model_documentation_v4.pdf | pdf | 5400 | in-scope | Model documentation v4: score bands and calibration grid | snapshots_2025_11_a_rev2.csv, data_quality_issue_log.md | errata_register.md, score_batches_2025_q2_a.jsonl | 13 | 155 |
| consumer_redress_programme.pdf | pdf | 5100 | in-scope | Consumer redress programme membership | treasury_fixings_2024_2026.xml, application_withdrawals.json | product_code_crosswalk.ini, customer_master.db | 12 | 157 |
| deceased_notifications_register.pdf | pdf | 5100 | in-scope | Historical deceased-customer register | applications_2025_04.csv, fraud_case_dispositions.json | snapshots_2025_11_b.parquet, servicing_snapshots_2026q1.db | 12 | 195 |
| audit_label_confirmations.pdf | pdf | 5100 | in-scope | Internal audit outcome confirmations | snapshots_2026_05_b.txt, applications_2025_05.xlsx | snapshots_2025_06_b.jsonl, bad_definition_standard_v5.docx | 13 | 909 |
| regulatory_exclusion_letter_2026.pdf | pdf | 5100 | in-scope | Regulator letter: accounts in insolvency proceedings | scoring_engine_node2.log, status_events_chargeoff_2025.csv | snapshots_2025_10_a.csv, applications_2025_06.jsonl | 13 | 438 |
| forbearance_extensions_register.pdf | pdf | 5100 | in-scope | Forbearance extensions | sampling_inclusion_cz_hu_ch.yaml, sampling_design_v2.yaml | snapshots_2025_10_b.tsv, snapshots_2026_02_a.csv | 12 | 1520 |
| calibration_reissue_2026.pdf | pdf | 5526 | decoy | Calibration reissue 2026 with Appendix B | score_batches_2025_q2_b.jsonl, applications_2025_04_reextract.csv | sampling_methodology.docx, model_registry_v4_1.toml | 28 | 177 |
| scoring_engine_node1.log | log | 7189 | in-scope | Engine log, node 1 | merge_candidates_ml.xlsx, applications_2025_06.jsonl | score_batches_2025_q2_c.jsonl, score_events_node6.xml | 15 | 838 |
| scoring_engine_node2.log | log | 7186 | in-scope | Engine log, node 2 | status_events_chargeoff_2025.csv, monitoring_spec_v4.md | regulatory_exclusion_letter_2026.pdf, snapshots_2025_10_a.csv | 15 | 870 |
| scoring_engine_node3.log | log | 7383 | in-scope | Engine log, node 3 | fraud_alerts_2025.jsonl, limit_management_policy.docx | snapshots_2025_09.xlsx, employee_leavers.tsv | 16 | 4780 |
| scoring_engine_node4.log | log | 7829 | in-scope | Engine log, node 4 | litigation_hold_register.html, currency_redenomination.ini | score_clock_skew_corrections.json, delivery_manifest.json | 15 | 982 |
| scoring_engine_node9.log | log | 8216 | decoy | Engine log, node 9 | snapshots_2025_02.csv, product_migrations_2025.xlsx | snapshots_2026_04.txt, applications_2025_03.txt | 28 | 1038 |
| servicing_snapshots_2025q3.db | sqlite | 37230 | in-scope | Servicing database, snapshot table snap_2025_07 | customer_merge_decisions.docx, branch_directory_2026.html | snapshots_2026_05_a.parquet, snapshots_2025_08_b.tsv | 20 | 2017 |
| servicing_snapshots_2026q1.db | sqlite | 35698 | in-scope | Servicing database, table snap_2026_01 | snapshots_2025_11_b.parquet, deceased_notifications_register.pdf | customer_merges_2026.tsv, applications_2025_05.xlsx | 20 | 2045 |
| customer_master.db | sqlite | 46300 | in-scope | Customer master: customers and customer_alias tables | product_code_crosswalk.ini, consumer_redress_programme.pdf | market_holidays.ics, applications_2025_02.tsv | 20 | 2971 |
| snapshots_servicing_replica.db | sqlite | 120616 | decoy | Read replica of the servicing database (tables snap_2025_08, snap_2025_09, snap_2025_10) and monitoring cycle controls (cycle_controls) | snapshots_2025_03.tsv, scoring_runs_2025q2.toml | bad_definition_standard.docx, exclusion_policy.docx | 28 | 9628 |
| sampling_inclusion_gb_pl_se.yaml | yaml | 13733 | in-scope | Inclusion probabilities, design PSD-2025H1, markets GB PL SE | deceased_notifications_feed.xml, governance_precedence_policy.docx | sampling_design_v2.yaml, sampling_inclusion_cz_hu_ch.yaml | 18 | 747 |
| sampling_inclusion_cz_hu_ch.yaml | yaml | 8581 | in-scope | Inclusion probabilities, markets CZ HU CH | sampling_design_v2.yaml, sampling_inclusion_gb_pl_se.yaml | forbearance_extensions_register.pdf, snapshots_2025_10_b.tsv | 18 | 451 |
| sampling_inclusion_dk_no.yaml | yaml | 6814 | in-scope | Inclusion probabilities, markets DK NO | limit_amendments_2025.xlsx, delivery_manifest.json | score_events_node5.parquet, data_quality_issue_log.md | 18 | 366 |
| sampling_design_v2.yaml | yaml | 7932 | decoy | Inclusion probabilities, design PSD-2025H1-v2 | sampling_inclusion_gb_pl_se.yaml, deceased_notifications_feed.xml | sampling_inclusion_cz_hu_ch.yaml, forbearance_extensions_register.pdf | 28 | 490 |
| model_registry_v4.toml | toml | 13397 | in-scope | PD-RETAIL v4 model registry and run register before 2025-04-01 | snapshots_2025_04.parquet, snapshots_2026_06.csv | score_events_node7.tsv, account_closures_2026h1.csv | 14 | 444 |
| scoring_runs_2025q2.toml | toml | 30310 | in-scope | Run register from 2025-04-01 | snapshots_2026_02_b.jsonl, applications_2025_02.tsv | snapshots_2025_03.tsv, snapshots_servicing_replica.db | 12 | 981 |
| model_registry_v4_1.toml | toml | 5410 | decoy | PD-RETAIL v4.1 registry | sampling_methodology.docx, calibration_reissue_2026.pdf | application_withdrawals.json, treasury_fixings_2024_2026.xml | 26 | 173 |
| product_code_crosswalk.ini | ini | 5160 | in-scope | Product code to monitoring segment, one section per segment | consumer_redress_programme.pdf, treasury_fixings_2024_2026.xml | customer_master.db, market_holidays.ics | 11 | 106 |
| legacy_account_map.ini | ini | 5100 | in-scope | Legacy account numbers | snapshots_2025_11_a.csv, fx_rates_ecb_mirror.xml | monitoring_spec_v4.md, status_events_chargeoff_2025.csv | 13 | 222 |
| currency_redenomination.ini | ini | 5100 | in-scope | Accounts denominated in a currency other than the market currency | applications_2025_01.csv, account_closures_2025.json | litigation_hold_register.html, scoring_engine_node4.log | 13 | 1213 |
| monitoring_spec_v4.md | md | 5400 | in-scope | This specification; Appendix A development distribution | legacy_account_map.ini, snapshots_2025_11_a.csv | status_events_chargeoff_2025.csv, scoring_engine_node2.log | 13 | 146 |
| errata_register.md | md | 5100 | in-scope | Errata register: rule errata and row errata | model_documentation_v4.pdf, snapshots_2025_11_a_rev2.csv | score_batches_2025_q2_a.jsonl, snapshots_2026_03.xlsx | 20 | 438 |
| data_quality_issue_log.md | md | 5100 | in-scope | Data quality issue log | score_events_node5.parquet, sampling_inclusion_dk_no.yaml | snapshots_2025_11_a_rev2.csv, model_documentation_v4.pdf | 12 | 4849 |
| branch_directory.html | html | 5418 | in-scope | Branch directory 2025 | fraud_alerts_2026.xml, snapshots_2025_08_a.csv | chargeoff_events_2026.parquet, applications_2025_04_reextract.csv | 15 | 307 |
| litigation_hold_register.html | html | 5100 | in-scope | Litigation hold register | currency_redenomination.ini, applications_2025_01.csv | scoring_engine_node4.log, score_clock_skew_corrections.json | 20 | 486 |
| branch_directory_2026.html | html | 5200 | decoy | Branch directory 2026 (recode) | account_closures_2026h1.csv, score_events_node7.tsv | customer_merge_decisions.docx, servicing_snapshots_2025q3.db | 28 | 307 |
| applications_2025_03.txt | fw | 5981 | in-scope | Application partition, March 2025 | snapshots_2026_04.txt, scoring_engine_node9.log | snapshots_2025_12.xlsx, snapshot_corrections_feed.xml | 20 | 7272 |
| snapshots_2026_04.txt | fw | 19061 | in-scope | Snapshot 2026-04 | scoring_engine_node9.log, snapshots_2025_02.csv | applications_2025_03.txt, snapshots_2025_12.xlsx | 15 | 698 |
| snapshots_2026_05_b.txt | fw | 7347 | in-scope | Snapshot 2026-05, HU CH DK NO | applications_2025_05.xlsx, customer_merges_2026.tsv | audit_label_confirmations.pdf, snapshots_2025_06_b.jsonl | 14 | 344 |
| ops_corrections.mbox | mbox | 5100 | in-scope | Servicing desk mailbox | score_events_backfill.csv, applications_master_2025h1.parquet | limit_management_policy.docx, fraud_alerts_2025.jsonl | 17 | 592 |
| market_holidays.ics | ics | 5211 | in-scope | Market calendars | customer_master.db, product_code_crosswalk.ini | applications_2025_02.tsv, snapshots_2026_02_b.jsonl | 12 | 69 |

### Decoys

| decoy | why it looks authoritative | demoting rule | load-bearing roles | graded impact if ignored | graded impact if trusted |
|---|---|---|---|---|---|
| snapshots_2025_11_a_rev2.csv | REVISION 2 - FINAL label, newer, includes CZ | manifest certified_snapshot_partitions (CZ only); governance 1.2 | a ring; e CZ rows authoritative; d header comment | every artifact (publication gate) | family checks of the affected accounts (19098 accounts) |
| applications_2025_04_reextract.csv | cleansed limits and branches, carries app ids | governance 3.7; header comment | a ring; c only app_id-account crosswalk; d | every artifact (publication gate) | family_t09, family_t16 (5867 accounts) |
| snapshots_2025_10_b_restated.tsv | newer restatement run | governance 1.2 and 3.12; header comment | a ring; b only SYSTEM_ERROR voids; d | every artifact (publication gate) | family_t08, family_t16 (14551 accounts) |
| score_batches_2025_q2_c.jsonl | newest engine build, complete Q2 coverage | spec 6.1 run register; governance 3.13 | a ring; e rows of approved runs authoritative | every artifact (publication gate) | family_t13, family_t16 (12742 accounts) |
| merge_candidates_ml.xlsx | AUTO-MERGE suggestions with high probabilities | governance 3.10 | a ring; c only legacy LCU mapping | every artifact (publication gate) | family_t01, family_t16 (80 accounts) |
| status_events_consolidated.json | one feed with every event, newest | governance 3.11; scope metadata | a ring; b only CO_REVERSAL evidence; e CIVIL_REGISTRY rows; d | every artifact (publication gate) | family_t06, family_t16 (1388 accounts) |
| fx_rates_ecb_mirror.xml | complete daily rates incl. holidays | governance 3.8 | a ring; c only ISO numeric crosswalk | every artifact (publication gate) | family_t02, family_t16 (1035 accounts) |
| applications_master_2025h1.parquet | cleansed master of all H1 applications | governance 3.6; description metadata | a ring; b only withdrawal reversals | every artifact (publication gate) | family checks of the affected accounts (35028 accounts) |
| bad_definition_standard_v5.docx | newer standard, committee endorsement | governance 3.2 + CR DRAFT; footnote | a ring; b only forbearance revocations; d footnote | every artifact (publication gate) | family_t14, family_t16 (212 accounts) |
| calibration_reissue_2026.pdf | newer calibration grid, approved CR | governance 3.15 | a ring; e Appendix B retrospective rows | every artifact (publication gate) | family_t12, family_t16 (0 accounts) |
| scoring_engine_node9.log | complete replay of node 4 | spec 6.2 node 9; run register | a ring; b only VOID directives | every artifact (publication gate) | family_t03, family_t16 (7910 accounts) |
| snapshots_servicing_replica.db | every account for three months | governance 1.3 | a ring and only cohort controls; d | every artifact (publication gate) | family_t05, family_t16 (34315 accounts) |
| sampling_design_v2.yaml | newer design v2 | governance 3.14; sampling 2.1 | a ring; e 2025-06 entries authoritative | every artifact (publication gate) | family_t04, family_t16 (7332 accounts) |
| model_registry_v4_1.toml | newer registry, APPROVED title | governance 3.3 + CR DRAFT | a ring; b only v4.0.2 withdrawal | every artifact (publication gate) | family_t11, family_t16 (5422 accounts) |
| branch_directory_2026.html | newer directory | governance 3.9 | a ring; c only 2026-to-2025 recode | every artifact (publication gate) | family_t10, family_t16 (5940 accounts) |

### Trap-family coverage

| file | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| applications_2025_01.csv | 5 | 0 | 0 | 0 | 0 | 3 | 2 | 2 | 3 | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| applications_2025_04.csv | 5 | 0 | 1 | 1 | 0 | 3 | 2 | 1 | 2 | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| snapshots_2025_02.csv | 5 | 0 | 2 | 1 | 1 | 1 | 4 | 1 | 3 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| snapshots_2025_06_a.csv | 4 | 0 | 2 | 1 | 2 | 1 | 4 | 1 | 2 | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_08_a.csv | 5 | 0 | 1 | 1 | 2 | 1 | 4 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_10_a.csv | 4 | 0 | 2 | 1 | 2 | 1 | 4 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_11_a.csv | 4 | 0 | 2 | 1 | 2 | 1 | 4 | 1 | 3 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2026_02_a.csv | 5 | 0 | 2 | 1 | 2 | 1 | 4 | 2 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2026_06.csv | 3 | 0 | 2 | 1 | 2 | 1 | 4 | 1 | 2 | 3 | 0 | 0 | 0 | 1 | 0 | 0 |
| status_events_chargeoff_2025.csv | 4 | 0 | 3 | 1 | 0 | 1 | 0 | 2 | 3 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| score_events_backfill.csv | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 3 | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| account_closures_2026h1.csv | 5 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 2 | 3 | 1 | 0 | 0 | 0 | 0 | 0 |
| snapshots_2025_11_a_rev2.csv | 7 | 0 | 2 | 2 | 2 | 1 | 4 | 1 | 3 | 2 | 0 | 1 | 1 | 2 | 0 | 2 |
| applications_2025_04_reextract.csv | 8 | 0 | 3 | 1 | 0 | 1 | 1 | 2 | 5 | 3 | 0 | 1 | 1 | 1 | 0 | 3 |
| applications_2025_02.tsv | 6 | 0 | 0 | 0 | 0 | 3 | 2 | 1 | 4 | 1 | 1 | 0 | 1 | 0 | 1 | 0 |
| snapshots_2025_03.tsv | 4 | 0 | 3 | 1 | 1 | 1 | 4 | 1 | 2 | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_08_b.tsv | 3 | 0 | 3 | 1 | 2 | 1 | 4 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_10_b.tsv | 4 | 0 | 3 | 0 | 2 | 2 | 4 | 1 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| score_events_node7.tsv | 2 | 0 | 1 | 0 | 0 | 3 | 0 | 1 | 4 | 1 | 1 | 0 | 2 | 0 | 0 | 0 |
| customer_merges_2026.tsv | 6 | 0 | 3 | 0 | 0 | 1 | 0 | 2 | 3 | 2 | 0 | 0 | 1 | 0 | 0 | 0 |
| employee_leavers.tsv | 1 | 0 | 3 | 0 | 0 | 0 | 1 | 2 | 3 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| snapshots_2025_10_b_restated.tsv | 7 | 0 | 3 | 3 | 2 | 2 | 2 | 1 | 3 | 2 | 0 | 1 | 1 | 1 | 0 | 2 |
| applications_2025_06.jsonl | 6 | 0 | 0 | 2 | 0 | 3 | 2 | 0 | 2 | 1 | 1 | 0 | 2 | 0 | 1 | 0 |
| snapshots_2025_06_b.jsonl | 5 | 0 | 2 | 2 | 3 | 1 | 4 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2026_02_b.jsonl | 4 | 0 | 2 | 2 | 3 | 1 | 4 | 0 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| score_batches_2025_q1.jsonl | 5 | 1 | 0 | 1 | 0 | 3 | 0 | 0 | 3 | 0 | 1 | 0 | 1 | 0 | 0 | 0 |
| score_batches_2025_q2_a.jsonl | 5 | 1 | 0 | 1 | 0 | 3 | 0 | 0 | 3 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| score_batches_2025_q2_b.jsonl | 5 | 1 | 0 | 1 | 0 | 3 | 0 | 0 | 3 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| fraud_alerts_2025.jsonl | 6 | 0 | 3 | 1 | 0 | 1 | 0 | 0 | 2 | 3 | 1 | 0 | 0 | 0 | 0 | 0 |
| score_batches_2025_q2_c.jsonl | 6 | 2 | 0 | 3 | 1 | 2 | 1 | 0 | 3 | 2 | 2 | 0 | 3 | 1 | 0 | 2 |
| applications_2025_05.xlsx | 6 | 0 | 1 | 0 | 1 | 3 | 2 | 1 | 1 | 1 | 1 | 0 | 2 | 0 | 1 | 0 |
| snapshots_2025_05.xlsx | 4 | 0 | 2 | 0 | 3 | 1 | 4 | 2 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_09.xlsx | 4 | 0 | 2 | 0 | 3 | 1 | 4 | 2 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_12.xlsx | 3 | 0 | 2 | 0 | 3 | 1 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2026_03.xlsx | 4 | 0 | 2 | 0 | 3 | 1 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| limit_amendments_2025.xlsx | 6 | 0 | 1 | 3 | 1 | 0 | 0 | 1 | 1 | 2 | 3 | 1 | 0 | 0 | 0 | 0 |
| product_migrations_2025.xlsx | 7 | 0 | 4 | 1 | 1 | 0 | 1 | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| merge_candidates_ml.xlsx | 16 | 0 | 1 | 1 | 1 | 1 | 1 | 2 | 3 | 3 | 0 | 0 | 1 | 0 | 1 | 2 |
| account_closures_2025.json | 5 | 0 | 3 | 0 | 1 | 0 | 0 | 1 | 1 | 3 | 2 | 0 | 0 | 0 | 0 | 0 |
| fraud_case_dispositions.json | 3 | 0 | 0 | 0 | 1 | 1 | 0 | 2 | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| delivery_manifest.json | 3 | 0 | 2 | 0 | 1 | 1 | 0 | 1 | 3 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| score_clock_skew_corrections.json | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 3 | 1 | 0 | 0 | 1 | 0 | 1 | 0 |
| application_withdrawals.json | 5 | 0 | 3 | 0 | 1 | 1 | 0 | 1 | 1 | 3 | 2 | 0 | 0 | 0 | 0 | 0 |
| status_events_consolidated.json | 9 | 0 | 3 | 0 | 1 | 2 | 1 | 1 | 4 | 2 | 0 | 0 | 1 | 1 | 0 | 3 |
| treasury_fixings_2024_2026.xml | 1 | 1 | 0 | 1 | 2 | 0 | 1 | 0 | 5 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| score_events_node6.xml | 3 | 0 | 2 | 0 | 0 | 3 | 0 | 0 | 4 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| snapshot_corrections_feed.xml | 5 | 0 | 2 | 1 | 0 | 0 | 1 | 0 | 5 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| deceased_notifications_feed.xml | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 4 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| fraud_alerts_2026.xml | 6 | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 5 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| fx_rates_ecb_mirror.xml | 1 | 1 | 0 | 2 | 1 | 1 | 1 | 1 | 8 | 2 | 1 | 1 | 2 | 1 | 1 | 3 |
| snapshots_2025_04.parquet | 4 | 1 | 0 | 1 | 3 | 1 | 4 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2025_11_b.parquet | 4 | 1 | 0 | 1 | 3 | 1 | 4 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2026_05_a.parquet | 3 | 1 | 0 | 1 | 3 | 1 | 4 | 0 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| score_events_node5.parquet | 3 | 1 | 0 | 1 | 1 | 3 | 0 | 0 | 3 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| chargeoff_events_2026.parquet | 6 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| applications_master_2025h1.parquet | 11 | 0 | 1 | 3 | 1 | 2 | 1 | 0 | 3 | 3 | 0 | 1 | 1 | 1 | 0 | 2 |
| governance_precedence_policy.docx | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| exclusion_policy.docx | 5 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 0 | 0 | 2 | 1 | 0 | 0 |
| customer_merge_decisions.docx | 6 | 0 | 3 | 0 | 0 | 1 | 0 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| sampling_methodology.docx | 7 | 0 | 0 | 3 | 0 | 1 | 0 | 2 | 2 | 2 | 0 | 0 | 0 | 1 | 1 | 0 |
| bad_definition_standard.docx | 6 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 2 | 2 | 1 | 0 | 0 | 1 | 0 | 0 |
| limit_management_policy.docx | 6 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 2 | 2 | 4 | 0 | 0 | 1 | 0 | 0 |
| bad_definition_standard_v5.docx | 8 | 0 | 3 | 0 | 0 | 1 | 1 | 2 | 3 | 2 | 1 | 0 | 2 | 2 | 0 | 3 |
| model_documentation_v4.pdf | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 2 | 4 | 0 | 0 | 0 | 1 | 2 | 0 | 0 |
| consumer_redress_programme.pdf | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 1 | 0 |
| deceased_notifications_register.pdf | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 1 | 0 | 1 | 0 | 1 | 1 | 0 | 0 |
| audit_label_confirmations.pdf | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| regulatory_exclusion_letter_2026.pdf | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| forbearance_extensions_register.pdf | 1 | 0 | 2 | 0 | 0 | 1 | 2 | 2 | 2 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| calibration_reissue_2026.pdf | 2 | 0 | 0 | 2 | 1 | 1 | 2 | 3 | 4 | 2 | 1 | 0 | 3 | 3 | 3 | 1 |
| scoring_engine_node1.log | 4 | 0 | 1 | 0 | 0 | 3 | 0 | 2 | 2 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| scoring_engine_node2.log | 4 | 0 | 1 | 0 | 0 | 3 | 0 | 2 | 2 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| scoring_engine_node3.log | 4 | 0 | 2 | 0 | 0 | 3 | 0 | 2 | 2 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| scoring_engine_node4.log | 4 | 0 | 1 | 0 | 0 | 3 | 0 | 2 | 2 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| scoring_engine_node9.log | 5 | 0 | 2 | 0 | 0 | 3 | 1 | 4 | 2 | 2 | 3 | 0 | 2 | 1 | 0 | 3 |
| servicing_snapshots_2025q3.db | 5 | 0 | 2 | 2 | 2 | 1 | 4 | 1 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| servicing_snapshots_2026q1.db | 4 | 0 | 2 | 2 | 2 | 1 | 4 | 1 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| customer_master.db | 12 | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 1 | 3 | 0 | 0 | 1 | 0 | 0 | 0 |
| snapshots_servicing_replica.db | 7 | 0 | 2 | 2 | 1 | 1 | 1 | 2 | 2 | 2 | 1 | 0 | 2 | 1 | 1 | 3 |
| sampling_inclusion_gb_pl_se.yaml | 5 | 0 | 2 | 3 | 1 | 0 | 0 | 1 | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| sampling_inclusion_cz_hu_ch.yaml | 5 | 0 | 2 | 3 | 1 | 0 | 0 | 1 | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| sampling_inclusion_dk_no.yaml | 5 | 0 | 2 | 3 | 1 | 0 | 0 | 1 | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| sampling_design_v2.yaml | 6 | 0 | 2 | 3 | 1 | 1 | 1 | 2 | 4 | 2 | 1 | 0 | 1 | 1 | 0 | 3 |
| model_registry_v4.toml | 4 | 0 | 2 | 0 | 1 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 2 | 0 | 1 | 0 |
| scoring_runs_2025q2.toml | 3 | 0 | 1 | 0 | 1 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 2 | 0 | 1 | 0 |
| model_registry_v4_1.toml | 3 | 0 | 1 | 2 | 0 | 1 | 3 | 1 | 6 | 1 | 1 | 0 | 2 | 2 | 2 | 1 |
| product_code_crosswalk.ini | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 7 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| legacy_account_map.ini | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 1 | 0 | 0 | 0 |
| currency_redenomination.ini | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 2 | 0 | 0 | 2 | 0 | 1 | 0 |
| monitoring_spec_v4.md | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 5 | 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| errata_register.md | 7 | 0 | 4 | 0 | 0 | 2 | 1 | 0 | 3 | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| data_quality_issue_log.md | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 5 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| branch_directory.html | 3 | 0 | 3 | 0 | 2 | 0 | 0 | 2 | 3 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| litigation_hold_register.html | 6 | 0 | 3 | 0 | 1 | 0 | 0 | 2 | 2 | 3 | 2 | 0 | 0 | 1 | 0 | 0 |
| branch_directory_2026.html | 6 | 0 | 3 | 0 | 1 | 1 | 1 | 2 | 5 | 2 | 2 | 0 | 2 | 2 | 0 | 1 |
| applications_2025_03.txt | 4 | 1 | 1 | 0 | 0 | 3 | 2 | 1 | 2 | 2 | 1 | 1 | 1 | 0 | 1 | 0 |
| snapshots_2026_04.txt | 3 | 1 | 0 | 0 | 3 | 1 | 4 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| snapshots_2026_05_b.txt | 2 | 1 | 0 | 0 | 3 | 1 | 4 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| ops_corrections.mbox | 5 | 0 | 3 | 0 | 0 | 1 | 1 | 0 | 3 | 3 | 1 | 0 | 0 | 0 | 0 | 0 |
| market_holidays.ics | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 1 | 2 | 0 | 0 | 0 | 2 | 0 |

Distinct traps: 1833 (in-scope 1403, decoys 430); instances: 160941. Accounts touched per trap family (before each account is assigned to its smallest family): T1 10818, T2 1035, T3 15891, T4 8420, T5 34422, T6 5417, T7 35078, T8 14551, T9 8856, T10 7642, T11 17396, T12 389, T13 17469, T14 1887, T15 35033, T16 9299.

### Test trace

| test | rule | contract location |
|---|---|---|
| artifacts_exist | instruction artifact list | instruction.md |
| outputs_follow_declared_schema | deliverable table | spec 1 |
| row_files_layout_exact | CSV conventions and row order | spec 1 |
| reconciliation_exact | delivery controls | spec 2 |
| eval_truncated_reconciliation_exact | delivery controls on other estates | spec 2, instruction.md engine paragraph |
| population_summary_exact | population | spec 8.2 |
| discrimination_exact | AUC, Gini, KS | spec 8.3, 8.6 |
| psi_exact | stability | spec 8.4 |
| calibration_exact | calibration | spec 8.5 |
| family_t01..family_t16 | cohort, exclusion, score and outcome rows of the family's accounts | spec 1, 3-7; exclusion policy; bad definition standard; limit policy; sampling methodology |
| eval_estate_rows_exact, eval_estate_metrics_exact | engine on other estates | instruction.md engine paragraph |
| eval_unreconciled_estate_withheld | publication gate | spec 1 publication gate, spec 2.3 |
| eval_full_scale_within_budget | 900 s budget | instruction.md |
| negative_hardcoded_sample_answers | outputs derived from ESTATE_DIR | instruction.md |
| negative_path_dependent_output | not depend on where ESTATE_DIR lives | instruction.md |
| negative_reads_training_corpus_at_runtime | read only ESTATE_DIR | instruction.md |
| negative_nondeterministic_output | byte-identical across runs | instruction.md |

### Trap manifest

One line per distinct trap: file, code, family, decoy flag, direction, rule, instance count.

```csv
file,code,family,decoy,direction,rule,instances
account_closures_2025.json,closure_on_month_six_start,T11,0,-,"bad definition standard 4",111
account_closures_2025.json,closure_window,T11,0,-,"bad definition standard 4",1511
account_closures_2025.json,control_object_last,T9,0,-,"specification catalogue",1
account_closures_2025.json,date_compact@closed,T3,0,-,"catalogue date and month notations",21
account_closures_2025.json,date_dmy_dot@closed,T3,0,-,"catalogue date and month notations",21
account_closures_2025.json,date_dmy_slash@closed,T3,0,-,"catalogue date and month notations",23
account_closures_2025.json,json_null_field,T5,0,-,"spec 4 conventions",14
account_closures_2025.json,json_unicode_escapes,T10,0,-,"spec 4 conventions",18
account_closures_2025.json,key_homoglyph@account,T1,0,-,"spec 4 conventions",22
account_closures_2025.json,key_hyphen@account,T1,0,-,"spec 4 conventions",21
account_closures_2025.json,key_lower@account,T1,0,-,"spec 4 conventions",20
account_closures_2025.json,key_nbsp@account,T10,0,-,"spec 4 conventions",21
account_closures_2025.json,key_space@account,T1,0,-,"spec 4 conventions",22
account_closures_2025.json,key_zero_pad@account,T1,0,-,"spec 4 conventions",22
account_closures_2025.json,key_zwsp@account,T10,0,-,"spec 4 conventions",20
account_closures_2025.json,records_under_named_key,T8,0,-,"specification catalogue",1
account_closures_2026h1.csv,closure_window,T11,0,-,"bad definition standard 4",633
account_closures_2026h1.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
account_closures_2026h1.csv,csv_quoted_delimiter,T9,0,-,"spec 4 conventions",13
account_closures_2026h1.csv,csv_reemitted_header,T8,0,-,"spec 2.2 and 4",1
account_closures_2026h1.csv,csv_utf8_bom,T10,0,-,"spec 2.2 and 4",1
account_closures_2026h1.csv,date_compact@closed_on,T3,0,-,"catalogue date and month notations",21
account_closures_2026h1.csv,date_dmy_dot@closed_on,T3,0,-,"catalogue date and month notations",20
account_closures_2026h1.csv,date_dmy_slash@closed_on,T3,0,-,"catalogue date and month notations",20
account_closures_2026h1.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
account_closures_2026h1.csv,key_homoglyph@account,T1,0,-,"spec 4 conventions",18
account_closures_2026h1.csv,key_hyphen@account,T1,0,-,"spec 4 conventions",21
account_closures_2026h1.csv,key_lower@account,T1,0,-,"spec 4 conventions",21
account_closures_2026h1.csv,key_nbsp@account,T10,0,-,"spec 4 conventions",20
account_closures_2026h1.csv,key_space@account,T1,0,-,"spec 4 conventions",19
account_closures_2026h1.csv,key_zero_pad@account,T1,0,-,"spec 4 conventions",21
account_closures_2026h1.csv,key_zwsp@account,T10,0,-,"spec 4 conventions",20
application_withdrawals.json,control_object_last,T9,0,-,"specification catalogue",1
application_withdrawals.json,date_compact@withdrawn_on,T3,0,-,"catalogue date and month notations",21
application_withdrawals.json,date_dmy_dot@withdrawn_on,T3,0,-,"catalogue date and month notations",22
application_withdrawals.json,date_dmy_slash@withdrawn_on,T3,0,-,"catalogue date and month notations",22
application_withdrawals.json,json_null_field,T5,0,-,"spec 4 conventions",17
application_withdrawals.json,json_unicode_escapes,T10,0,-,"spec 4 conventions",16
application_withdrawals.json,key_homoglyph@account,T1,0,-,"spec 4 conventions",21
application_withdrawals.json,key_hyphen@account,T1,0,-,"spec 4 conventions",23
application_withdrawals.json,key_lower@account,T1,0,-,"spec 4 conventions",22
application_withdrawals.json,key_nbsp@account,T10,0,-,"spec 4 conventions",22
application_withdrawals.json,key_space@account,T1,0,-,"spec 4 conventions",22
application_withdrawals.json,key_zero_pad@account,T1,0,-,"spec 4 conventions",22
application_withdrawals.json,key_zwsp@account,T10,0,-,"spec 4 conventions",27
application_withdrawals.json,records_under_named_key,T8,0,-,"specification catalogue",1
application_withdrawals.json,withdrawal_day_boundary,T11,0,-,"spec 3.5",140
application_withdrawals.json,withdrawal_later_reversed,T6,0,-,"governance 3.6",82
application_withdrawals.json,withdrawal_window,T11,0,-,"spec 3.5",471
applications_2025_01.csv,branch_code_reused,T13,0,-,"spec 3.3",238
applications_2025_01.csv,cohort_window_boundary,T11,0,-,"spec 3.3 cohort window",25
applications_2025_01.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
applications_2025_01.csv,cust_homoglyph,T1,0,-,"spec 4 conventions",23
applications_2025_01.csv,cust_lower,T1,0,-,"spec 4 conventions",24
applications_2025_01.csv,cust_space,T1,0,-,"spec 4 conventions",25
applications_2025_01.csv,cust_zero_pad,T1,0,-,"spec 4 conventions",23
applications_2025_01.csv,cust_zwsp,T10,0,-,"spec 4 conventions",23
applications_2025_01.csv,duplicate_application_person,T6,0,-,"spec 3.6",52
applications_2025_01.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
applications_2025_01.csv,header_reemitted_reordered,T8,0,-,"spec 4.2 re-emitted headers",1
applications_2025_01.csv,id_lower,T1,0,-,"spec 4 conventions",23
applications_2025_01.csv,id_padded,T9,0,-,"spec 4 conventions",25
applications_2025_01.csv,large_limit_valid,T15,0,-,"limit policy",556
applications_2025_01.csv,note_embedded_newline,T9,0,-,"RFC 4180 quoting",25
applications_2025_01.csv,quarantined_record,T6,0,-,"dq log",7
applications_2025_01.csv,resend_later_receipt,T7,0,-,"spec 3.2",5692
applications_2025_01.csv,superseded_revision,T7,0,-,"spec 3.2 highest revision wins",59
applications_2025_01.csv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
applications_2025_01.csv,withdrawal_reversed_elsewhere,T6,0,-,"governance 3.6",12
applications_2025_02.tsv,branch_code_reused,T13,0,-,"spec 3.3",254
applications_2025_02.tsv,code_lower,T1,0,-,"spec 4 conventions",24
applications_2025_02.tsv,code_padded,T9,0,-,"spec 4 conventions",26
applications_2025_02.tsv,cohort_window_boundary,T11,0,-,"spec 3.3 cohort window",25
applications_2025_02.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
applications_2025_02.tsv,cust_homoglyph,T1,0,-,"spec 4 conventions",24
applications_2025_02.tsv,cust_lower,T1,0,-,"spec 4 conventions",23
applications_2025_02.tsv,cust_space,T1,0,-,"spec 4 conventions",27
applications_2025_02.tsv,cust_zero_pad,T1,0,-,"spec 4 conventions",24
applications_2025_02.tsv,cust_zwsp,T10,0,-,"spec 4 conventions",24
applications_2025_02.tsv,duplicate_application_person,T6,0,-,"spec 3.6",224
applications_2025_02.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
applications_2025_02.tsv,id_lower,T1,0,-,"spec 4 conventions",22
applications_2025_02.tsv,id_padded,T9,0,-,"spec 4 conventions",23
applications_2025_02.tsv,large_limit_valid,T15,0,-,"limit policy",550
applications_2025_02.tsv,quarantined_record,T6,0,-,"dq log",6
applications_2025_02.tsv,resend_later_receipt,T7,0,-,"spec 3.2",5858
applications_2025_02.tsv,superseded_revision,T7,0,-,"spec 3.2 highest revision wins",66
applications_2025_02.tsv,trailing_empty_field,T9,0,-,"catalogue",30
applications_2025_02.tsv,withdrawal_reversed_elsewhere,T6,0,-,"governance 3.6",12
applications_2025_03.txt,branch_code_reused,T13,0,-,"spec 3.3",261
applications_2025_03.txt,code_lower,T1,0,-,"spec 4 conventions",22
applications_2025_03.txt,code_padded,T9,0,-,"spec 4 conventions",24
applications_2025_03.txt,cohort_window_boundary,T11,0,-,"spec 3.3 cohort window",25
applications_2025_03.txt,cust_lower,T1,0,-,"spec 4 conventions",22
applications_2025_03.txt,cust_zero_pad,T1,0,-,"spec 4 conventions",26
applications_2025_03.txt,dst_gap_local_time,T3,0,-,"spec 3.3 cohort window",12
applications_2025_03.txt,duplicate_application_person,T6,0,-,"spec 3.6",258
applications_2025_03.txt,id_lower,T1,0,-,"spec 4 conventions",22
applications_2025_03.txt,id_padded,T9,0,-,"spec 4 conventions",22
applications_2025_03.txt,large_limit_valid,T15,0,-,"limit policy",546
applications_2025_03.txt,latin1_encoding,T10,0,-,"specification catalogue",1
applications_2025_03.txt,latin1_names,T10,0,-,"catalogue fixed width",1
applications_2025_03.txt,limit_implied_decimals,T2,0,-,"catalogue",1
applications_2025_03.txt,money_three_decimals,T12,0,-,"spec 4 conventions",25
applications_2025_03.txt,quarantined_record,T6,0,-,"dq log",3
applications_2025_03.txt,record_type_codes,T8,0,-,"specification catalogue",1
applications_2025_03.txt,resend_later_receipt,T7,0,-,"spec 3.2",5909
applications_2025_03.txt,superseded_revision,T7,0,-,"spec 3.2 highest revision wins",72
applications_2025_03.txt,withdrawal_reversed_elsewhere,T6,0,-,"governance 3.6",19
applications_2025_04.csv,branch_code_reused,T13,0,-,"spec 3.3",255
applications_2025_04.csv,cohort_window_boundary,T11,0,-,"spec 3.3 cohort window",25
applications_2025_04.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
applications_2025_04.csv,cust_homoglyph,T1,0,-,"spec 4 conventions",21
applications_2025_04.csv,cust_lower,T1,0,-,"spec 4 conventions",23
applications_2025_04.csv,cust_space,T1,0,-,"spec 4 conventions",24
applications_2025_04.csv,cust_zero_pad,T1,0,-,"spec 4 conventions",22
applications_2025_04.csv,cust_zwsp,T10,0,-,"spec 4 conventions",21
applications_2025_04.csv,decimal_comma_limit,T4,0,-,"catalogue",1
applications_2025_04.csv,duplicate_application_person,T6,0,-,"spec 3.6",248
applications_2025_04.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
applications_2025_04.csv,id_lower,T1,0,-,"spec 4 conventions",26
applications_2025_04.csv,id_padded,T9,0,-,"spec 4 conventions",24
applications_2025_04.csv,iso_with_offset,T3,0,-,"catalogue",1
applications_2025_04.csv,large_limit_valid,T15,0,-,"limit policy",518
applications_2025_04.csv,quarantined_record,T6,0,-,"dq log",2
applications_2025_04.csv,resend_later_receipt,T7,0,-,"spec 3.2",5886
applications_2025_04.csv,superseded_revision,T7,0,-,"spec 3.2 highest revision wins",67
applications_2025_04.csv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
applications_2025_04.csv,withdrawal_reversed_elsewhere,T6,0,-,"governance 3.6",12
applications_2025_04_reextract.csv,application_id_crosswalk_only_source,T13,1,push,"governance policy",1
applications_2025_04_reextract.csv,cleansed_values_claim,T16,1,pull,"governance policy",1
applications_2025_04_reextract.csv,code_lower@branch,T1,1,-,"spec 4 conventions",25
applications_2025_04_reextract.csv,code_lower@product_code,T1,1,-,"spec 4 conventions",26
applications_2025_04_reextract.csv,code_padded@branch,T9,1,-,"spec 4 conventions",24
applications_2025_04_reextract.csv,code_padded@product_code,T9,1,-,"spec 4 conventions",23
applications_2025_04_reextract.csv,comment_lines_hash,T9,1,-,"specification catalogue",1
applications_2025_04_reextract.csv,csv_quoted_delimiter,T9,1,-,"spec 4 conventions",16
applications_2025_04_reextract.csv,csv_reemitted_header,T8,1,-,"spec 2.2 and 4",1
applications_2025_04_reextract.csv,csv_utf8_bom,T10,1,-,"spec 2.2 and 4",1
applications_2025_04_reextract.csv,decision_utc_only,T3,1,-,"governance policy",1
applications_2025_04_reextract.csv,header_names_differ_by_file,T8,1,-,"specification catalogue",1
applications_2025_04_reextract.csv,id_lower@app_id,T1,1,-,"spec 4 conventions",24
applications_2025_04_reextract.csv,id_padded@app_id,T9,1,-,"spec 4 conventions",22
applications_2025_04_reextract.csv,iso_fraction@decision_utc,T3,1,-,"spec 4 conventions",20
applications_2025_04_reextract.csv,iso_offset@decision_utc,T3,1,-,"spec 4 conventions",20
applications_2025_04_reextract.csv,key_homoglyph@account,T1,1,-,"spec 4 conventions",25
applications_2025_04_reextract.csv,key_hyphen@account,T1,1,-,"spec 4 conventions",23
applications_2025_04_reextract.csv,key_lower@account,T1,1,-,"spec 4 conventions",28
applications_2025_04_reextract.csv,key_nbsp@account,T10,1,-,"spec 4 conventions",23
applications_2025_04_reextract.csv,key_space@account,T1,1,-,"spec 4 conventions",23
applications_2025_04_reextract.csv,key_zero_pad@account,T1,1,-,"spec 4 conventions",26
applications_2025_04_reextract.csv,key_zwsp@account,T10,1,-,"spec 4 conventions",24
applications_2025_04_reextract.csv,money_thousands@limit,T4,1,-,"spec 4 conventions",21
applications_2025_04_reextract.csv,money_three_decimals@limit,T12,1,-,"spec 4 conventions",24
applications_2025_04_reextract.csv,no_revision_column,T7,1,-,"governance policy",1
applications_2025_04_reextract.csv,reextract_branch_cleansed,T16,1,pull,"",125
applications_2025_04_reextract.csv,reextract_limit_drift,T16,1,pull,"",231
applications_2025_04_reextract.csv,unofficial_label_header,T14,1,push,"governance policy",1
applications_2025_04_reextract.csv,withdrawn_accounts_still_listed,T6,1,-,"governance policy",1
applications_2025_05.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
applications_2025_05.xlsx,branch_code_reused,T13,0,-,"spec 3.3",266
applications_2025_05.xlsx,code_lower,T1,0,-,"spec 4 conventions",22
applications_2025_05.xlsx,cohort_window_boundary,T11,0,-,"spec 3.3 cohort window",25
applications_2025_05.xlsx,current_basis_product_code,T13,0,-,"catalogue product basis + migrations workbook",1
applications_2025_05.xlsx,cust_homoglyph,T1,0,-,"spec 4 conventions",24
applications_2025_05.xlsx,cust_lower,T1,0,-,"spec 4 conventions",24
applications_2025_05.xlsx,cust_space,T1,0,-,"spec 4 conventions",25
applications_2025_05.xlsx,cust_zero_pad,T1,0,-,"spec 4 conventions",25
applications_2025_05.xlsx,cust_zwsp,T10,0,-,"spec 4 conventions",22
applications_2025_05.xlsx,duplicate_application_person,T6,0,-,"spec 3.6",248
applications_2025_05.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
applications_2025_05.xlsx,id_lower,T1,0,-,"spec 4 conventions",25
applications_2025_05.xlsx,id_padded,T9,0,-,"spec 4 conventions",23
applications_2025_05.xlsx,large_limit_valid,T15,0,-,"limit policy",589
applications_2025_05.xlsx,quarantined_record,T6,0,-,"dq log",2
applications_2025_05.xlsx,resend_later_receipt,T7,0,-,"spec 3.2",5888
applications_2025_05.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
applications_2025_05.xlsx,superseded_revision,T7,0,-,"spec 3.2 highest revision wins",64
applications_2025_05.xlsx,withdrawal_reversed_elsewhere,T6,0,-,"governance 3.6",21
applications_2025_06.jsonl,branch_code_2026_scheme,T13,0,-,"catalogue",1
applications_2025_06.jsonl,branch_code_reused,T13,0,-,"spec 3.3",256
applications_2025_06.jsonl,code_lower,T1,0,-,"spec 4 conventions",24
applications_2025_06.jsonl,cohort_window_boundary,T11,0,-,"spec 3.3 cohort window",40
applications_2025_06.jsonl,control_line_last,T9,0,-,"specification catalogue",1
applications_2025_06.jsonl,cust_homoglyph,T1,0,-,"spec 4 conventions",26
applications_2025_06.jsonl,cust_lower,T1,0,-,"spec 4 conventions",25
applications_2025_06.jsonl,cust_space,T1,0,-,"spec 4 conventions",24
applications_2025_06.jsonl,cust_zero_pad,T1,0,-,"spec 4 conventions",26
applications_2025_06.jsonl,cust_zwsp,T10,0,-,"spec 4 conventions",24
applications_2025_06.jsonl,duplicate_application_person,T6,0,-,"spec 3.6",290
applications_2025_06.jsonl,id_lower,T1,0,-,"spec 4 conventions",23
applications_2025_06.jsonl,id_padded,T9,0,-,"spec 4 conventions",23
applications_2025_06.jsonl,large_limit_valid,T15,0,-,"limit policy",570
applications_2025_06.jsonl,limit_as_string,T4,0,-,"catalogue",66
applications_2025_06.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
applications_2025_06.jsonl,quarantined_record,T6,0,-,"dq log",5
applications_2025_06.jsonl,resend_later_receipt,T7,0,-,"spec 3.2",5935
applications_2025_06.jsonl,superseded_revision,T7,0,-,"spec 3.2 highest revision wins",52
applications_2025_06.jsonl,withdrawal_reversed_elsewhere,T6,0,-,"governance 3.6",10
applications_master_2025h1.parquet,code_lower@branch,T1,1,-,"spec 4 conventions",139
applications_master_2025h1.parquet,code_lower@product_code,T1,1,-,"spec 4 conventions",141
applications_master_2025h1.parquet,code_padded@branch,T9,1,-,"spec 4 conventions",135
applications_master_2025h1.parquet,code_padded@product_code,T9,1,-,"spec 4 conventions",136
applications_master_2025h1.parquet,cust_homoglyph@customer,T1,1,-,"spec 4 conventions",139
applications_master_2025h1.parquet,cust_lower@customer,T1,1,-,"spec 4 conventions",143
applications_master_2025h1.parquet,cust_space@customer,T1,1,-,"spec 4 conventions",146
applications_master_2025h1.parquet,cust_zero_pad@customer,T1,1,-,"spec 4 conventions",134
applications_master_2025h1.parquet,cust_zwsp@customer,T10,1,-,"spec 4 conventions",144
applications_master_2025h1.parquet,decision_epoch_seconds,T3,1,-,"governance 3.6",1
applications_master_2025h1.parquet,description_metadata,T14,1,pull,"governance 3.6",1
applications_master_2025h1.parquet,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",104
applications_master_2025h1.parquet,key_hyphen,T1,1,-,"spec 3.1 key normalisation",112
applications_master_2025h1.parquet,key_lower,T1,1,-,"spec 3.1 key normalisation",112
applications_master_2025h1.parquet,key_nbsp,T10,1,-,"spec 3.1 key normalisation",108
applications_master_2025h1.parquet,key_space,T1,1,-,"spec 3.1 key normalisation",109
applications_master_2025h1.parquet,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",106
applications_master_2025h1.parquet,key_zwsp,T10,1,-,"spec 3.1 key normalisation",104
applications_master_2025h1.parquet,master_branch_drift,T16,1,pull,"",1348
applications_master_2025h1.parquet,master_cleansed_values,T16,1,pull,"governance 3.6",1
applications_master_2025h1.parquet,master_is_latest_snapshot,T7,1,pull,"governance 3.6",1
applications_master_2025h1.parquet,master_lacks_application_id,T13,1,-,"governance 3.6",1
applications_master_2025h1.parquet,money_comma@limit,T4,1,-,"spec 4 conventions",139
applications_master_2025h1.parquet,money_thousands@limit,T4,1,-,"spec 4 conventions",140
applications_master_2025h1.parquet,money_three_decimals@limit,T12,1,-,"spec 4 conventions",138
applications_master_2025h1.parquet,nullable_columns,T5,1,-,"specification catalogue",1
applications_master_2025h1.parquet,row_groups_split,T9,1,-,"specification catalogue",1
applications_master_2025h1.parquet,typed_integer_columns,T4,1,-,"specification catalogue",1
applications_master_2025h1.parquet,withdrawal_reversed_flag,T6,1,-,"governance 3.6",82
applications_master_2025h1.parquet,withdrawal_reversed_flag_only_here,T6,1,push,"governance 3.6",1
audit_label_confirmations.pdf,audit_override,T14,0,-,"bad definition standard 5",734
audit_label_confirmations.pdf,key_hyphen@account,T1,0,-,"spec 4 conventions",23
audit_label_confirmations.pdf,key_lower@account,T1,0,-,"spec 4 conventions",20
audit_label_confirmations.pdf,key_nbsp@account,T10,0,-,"spec 4 conventions",19
audit_label_confirmations.pdf,key_space@account,T1,0,-,"spec 4 conventions",21
audit_label_confirmations.pdf,key_zero_pad@account,T1,0,-,"spec 4 conventions",22
audit_label_confirmations.pdf,page_footer_lines,T8,0,-,"specification catalogue",1
audit_label_confirmations.pdf,pdf_page_header_repeats,T8,0,-,"spec 2.2 and 4",1
audit_label_confirmations.pdf,pdf_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
audit_label_confirmations.pdf,status_lowercase@audited_label,T1,0,-,"spec 4 conventions",21
audit_label_confirmations.pdf,status_padded@audited_label,T9,0,-,"spec 4 conventions",20
audit_label_confirmations.pdf,status_title@audited_label,T1,0,-,"spec 4 conventions",25
audit_label_confirmations.pdf,text_layer_pipe_separated,T9,0,-,"specification catalogue",1
bad_definition_standard.docx,appendix_table_only_records,T8,0,-,"specification catalogue",1
bad_definition_standard.docx,custom_properties_control,T9,0,-,"specification catalogue",1
bad_definition_standard.docx,docx_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
bad_definition_standard.docx,docx_table_split_repeated_header,T8,0,-,"spec 2.2 and 4",1
bad_definition_standard.docx,grant_months_inclusive,T11,0,-,"bad definition standard 3",1183
bad_definition_standard.docx,id_lower,T1,0,-,"spec 4 conventions",21
bad_definition_standard.docx,id_padded,T9,0,-,"spec 4 conventions",20
bad_definition_standard.docx,key_homoglyph,T1,0,-,"spec 4 conventions",21
bad_definition_standard.docx,key_hyphen,T1,0,-,"spec 4 conventions",19
bad_definition_standard.docx,key_lower,T1,0,-,"spec 4 conventions",19
bad_definition_standard.docx,key_nbsp,T10,0,-,"spec 4 conventions",22
bad_definition_standard.docx,key_space,T1,0,-,"spec 4 conventions",22
bad_definition_standard.docx,key_zero_pad,T1,0,-,"spec 4 conventions",23
bad_definition_standard.docx,key_zwsp,T10,0,-,"spec 4 conventions",18
bad_definition_standard.docx,month_compact,T3,0,-,"catalogue date and month notations",18
bad_definition_standard.docx,month_slash,T3,0,-,"catalogue date and month notations",18
bad_definition_standard_v5.docx,appendix_table_only_records,T8,1,-,"specification catalogue",1
bad_definition_standard_v5.docx,custom_properties_control,T9,1,-,"specification catalogue",1
bad_definition_standard_v5.docx,date_compact@revoked_on,T3,1,-,"catalogue date and month notations",21
bad_definition_standard_v5.docx,date_dmy_dot@revoked_on,T3,1,-,"catalogue date and month notations",20
bad_definition_standard_v5.docx,date_dmy_slash@revoked_on,T3,1,-,"catalogue date and month notations",19
bad_definition_standard_v5.docx,docx_rule_in_prose,T14,1,-,"spec 2.2 and 4",1
bad_definition_standard_v5.docx,docx_table_split_repeated_header,T8,1,-,"spec 2.2 and 4",1
bad_definition_standard_v5.docx,draft_status_in_footnote,T14,1,push,"governance policy",1
bad_definition_standard_v5.docx,grant_revoked,T6,1,push,"governance 3.5",212
bad_definition_standard_v5.docx,id_lower@grant,T1,1,-,"spec 4 conventions",21
bad_definition_standard_v5.docx,id_padded@grant,T9,1,-,"spec 4 conventions",19
bad_definition_standard_v5.docx,key_homoglyph@account,T1,1,-,"spec 4 conventions",22
bad_definition_standard_v5.docx,key_hyphen@account,T1,1,-,"spec 4 conventions",21
bad_definition_standard_v5.docx,key_lower@account,T1,1,-,"spec 4 conventions",21
bad_definition_standard_v5.docx,key_nbsp@account,T10,1,-,"spec 4 conventions",22
bad_definition_standard_v5.docx,key_space@account,T1,1,-,"spec 4 conventions",22
bad_definition_standard_v5.docx,key_zero_pad@account,T1,1,-,"spec 4 conventions",24
bad_definition_standard_v5.docx,key_zwsp@account,T10,1,-,"spec 4 conventions",20
bad_definition_standard_v5.docx,revocation_applies_regardless,T13,1,push,"governance policy",1
bad_definition_standard_v5.docx,revocation_of_unknown_grant,T13,1,-,"governance policy",1
bad_definition_standard_v5.docx,revocation_supersedes_grant,T7,1,push,"governance policy",1
bad_definition_standard_v5.docx,status_lowercase@status,T1,1,-,"spec 4 conventions",22
bad_definition_standard_v5.docx,status_padded@status,T9,1,-,"spec 4 conventions",21
bad_definition_standard_v5.docx,status_title@status,T1,1,-,"spec 4 conventions",18
bad_definition_standard_v5.docx,v5_committee_label,T16,1,pull,"governance policy",1
bad_definition_standard_v5.docx,v5_effective_2026,T11,1,-,"governance policy",1
bad_definition_standard_v5.docx,v5_threshold_bnpl_30,T16,1,pull,"governance policy",1
bad_definition_standard_v5.docx,v5_threshold_ovdr_60,T16,1,pull,"governance policy",1
branch_directory.html,date_compact,T3,0,-,"catalogue date and month notations",22
branch_directory.html,date_dmy_dot,T3,0,-,"catalogue date and month notations",19
branch_directory.html,date_dmy_slash,T3,0,-,"catalogue date and month notations",21
branch_directory.html,html_entities_nbsp,T10,0,-,"spec 4 conventions",16
branch_directory.html,html_repeated_header_rows,T8,0,-,"spec 2.2 and 4",1
branch_directory.html,html_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
branch_directory.html,id_lower,T1,0,-,"spec 4 conventions",22
branch_directory.html,id_padded,T9,0,-,"spec 4 conventions",21
branch_directory.html,meta_control,T9,0,-,"specification catalogue",1
branch_directory.html,open_end_9999,T5,0,-,"spec 4.5",61
branch_directory.html,open_end_word,T5,0,-,"spec 4.5",60
branch_directory.html,status_lowercase,T1,0,-,"spec 4 conventions",20
branch_directory.html,status_padded,T9,0,-,"spec 4 conventions",21
branch_directory.html,status_title,T1,0,-,"spec 4 conventions",20
branch_directory.html,th_rows_not_records,T8,0,-,"specification catalogue",1
branch_directory_2026.html,booking_market_nordic,T16,1,pull,"governance policy",1
branch_directory_2026.html,branch_names_diacritics,T10,1,-,"governance policy",1
branch_directory_2026.html,date_compact@opened_2026,T3,1,-,"catalogue date and month notations",19
branch_directory_2026.html,date_dmy_dot@opened_2026,T3,1,-,"catalogue date and month notations",24
branch_directory_2026.html,date_dmy_slash@opened_2026,T3,1,-,"catalogue date and month notations",22
branch_directory_2026.html,html_entities_nbsp,T10,1,-,"spec 4 conventions",16
branch_directory_2026.html,html_repeated_header_rows,T8,1,-,"spec 2.2 and 4",1
branch_directory_2026.html,html_rule_in_prose,T14,1,-,"spec 2.2 and 4",1
branch_directory_2026.html,id_lower@branch_2025,T1,1,-,"spec 4 conventions",20
branch_directory_2026.html,id_lower@branch_2026,T1,1,-,"spec 4 conventions",21
branch_directory_2026.html,id_padded@branch_2025,T9,1,-,"spec 4 conventions",20
branch_directory_2026.html,id_padded@branch_2026,T9,1,-,"spec 4 conventions",21
branch_directory_2026.html,market_column_post_2025,T11,1,-,"governance policy",1
branch_directory_2026.html,merged_branch_status,T7,1,-,"governance policy",1
branch_directory_2026.html,merged_branches_still_listed,T6,1,-,"governance policy",1
branch_directory_2026.html,meta_control,T9,1,-,"specification catalogue",1
branch_directory_2026.html,new_codes_used_by_june_partition,T13,1,push,"governance policy",1
branch_directory_2026.html,nordic_hub_prose,T14,1,pull,"governance policy",1
branch_directory_2026.html,opened_dates_2026,T11,1,-,"governance policy",1
branch_directory_2026.html,recode_only_role,T13,1,push,"governance policy",1
branch_directory_2026.html,status_2026_values,T5,1,-,"governance policy",1
branch_directory_2026.html,status_lowercase@booking_market,T1,1,-,"spec 4 conventions",21
branch_directory_2026.html,status_lowercase@status_2026,T1,1,-,"spec 4 conventions",23
branch_directory_2026.html,status_padded@booking_market,T9,1,-,"spec 4 conventions",23
branch_directory_2026.html,status_padded@status_2026,T9,1,-,"spec 4 conventions",24
branch_directory_2026.html,status_title@booking_market,T1,1,-,"spec 4 conventions",19
branch_directory_2026.html,status_title@status_2026,T1,1,-,"spec 4 conventions",20
branch_directory_2026.html,th_rows_not_records,T8,1,-,"specification catalogue",1
calibration_reissue_2026.pdf,appendix_b_retrospective,T14,1,push,"governance 3.15",1
calibration_reissue_2026.pdf,approved_change_request_label,T13,1,pull,"governance 3.15",1
calibration_reissue_2026.pdf,approved_cr_prose,T14,1,pull,"governance policy",1
calibration_reissue_2026.pdf,duplicate_retro_row_later_wins,T7,1,-,"governance policy",1
calibration_reissue_2026.pdf,int_zero_pad@score,T9,1,-,"spec 4 conventions",21
calibration_reissue_2026.pdf,latin1_title,T10,1,-,"governance policy",1
calibration_reissue_2026.pdf,nbsp_in_pd,T10,1,-,"governance policy",1
calibration_reissue_2026.pdf,page_footer_lines,T8,1,-,"specification catalogue",1
calibration_reissue_2026.pdf,pd_comma@pd,T4,1,-,"spec 4 conventions",24
calibration_reissue_2026.pdf,pd_dash_missing,T5,1,-,"governance policy",1
calibration_reissue_2026.pdf,pd_padded@pd,T9,1,-,"spec 4 conventions",23
calibration_reissue_2026.pdf,pd_trailing_zeros@pd,T4,1,-,"spec 4 conventions",20
calibration_reissue_2026.pdf,pdf_page_header_repeats,T8,1,-,"governance 3.15",1
calibration_reissue_2026.pdf,pdf_rule_in_prose,T14,1,-,"governance 3.15",1
calibration_reissue_2026.pdf,placeholder_retro_row_overridden,T6,1,-,"governance policy",1
calibration_reissue_2026.pdf,reissue_effective_2026,T11,1,-,"governance 3.15",1
calibration_reissue_2026.pdf,reissue_grid_newer,T16,1,pull,"governance 3.15",1
calibration_reissue_2026.pdf,retro_pd_above_grid,T15,1,-,"governance 3.15",1
calibration_reissue_2026.pdf,retro_row_unknown_score,T13,1,-,"governance policy",1
calibration_reissue_2026.pdf,retro_rows_few,T15,1,push,"governance policy",1
calibration_reissue_2026.pdf,retro_rows_unsorted,T7,1,-,"governance 3.15",1
calibration_reissue_2026.pdf,rows_for_extra_segment,T13,1,-,"governance policy",1
calibration_reissue_2026.pdf,score_gap_rows,T15,1,-,"governance policy",1
calibration_reissue_2026.pdf,status_lowercase@segment,T1,1,-,"spec 4 conventions",23
calibration_reissue_2026.pdf,status_padded@segment,T9,1,-,"spec 4 conventions",22
calibration_reissue_2026.pdf,status_title@segment,T1,1,-,"spec 4 conventions",23
calibration_reissue_2026.pdf,text_layer_pipe_separated,T9,1,-,"specification catalogue",1
calibration_reissue_2026.pdf,two_tables_same_header,T8,1,-,"governance 3.15",1
chargeoff_events_2026.parquet,amount_minor_units,T2,0,-,"catalogue",1
chargeoff_events_2026.parquet,chargeoff_in_window,T11,0,-,"bad definition standard 2.4",419
chargeoff_events_2026.parquet,chargeoff_reversed_elsewhere,T6,0,-,"bad definition standard 2.4",45
chargeoff_events_2026.parquet,date32_column,T3,0,-,"catalogue",1
chargeoff_events_2026.parquet,id_lower,T1,0,-,"spec 4 conventions",20
chargeoff_events_2026.parquet,id_padded,T9,0,-,"spec 4 conventions",21
chargeoff_events_2026.parquet,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",13
chargeoff_events_2026.parquet,key_hyphen,T1,0,-,"spec 3.1 key normalisation",14
chargeoff_events_2026.parquet,key_lower,T1,0,-,"spec 3.1 key normalisation",17
chargeoff_events_2026.parquet,key_space,T1,0,-,"spec 3.1 key normalisation",17
chargeoff_events_2026.parquet,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",19
chargeoff_events_2026.parquet,nullable_columns,T5,0,-,"specification catalogue",1
chargeoff_events_2026.parquet,row_groups_split,T9,0,-,"specification catalogue",1
chargeoff_events_2026.parquet,typed_integer_columns,T4,0,-,"specification catalogue",1
consumer_redress_programme.pdf,code_lower@programme,T1,0,-,"spec 4 conventions",21
consumer_redress_programme.pdf,code_padded@programme,T9,0,-,"spec 4 conventions",23
consumer_redress_programme.pdf,historical_programmes,T15,0,-,"specification and catalogue",1
consumer_redress_programme.pdf,key_hyphen@account,T1,0,-,"spec 4 conventions",21
consumer_redress_programme.pdf,key_lower@account,T1,0,-,"spec 4 conventions",24
consumer_redress_programme.pdf,key_nbsp@account,T10,0,-,"spec 4 conventions",23
consumer_redress_programme.pdf,key_space@account,T1,0,-,"spec 4 conventions",21
consumer_redress_programme.pdf,key_zero_pad@account,T1,0,-,"spec 4 conventions",19
consumer_redress_programme.pdf,page_footer_lines,T8,0,-,"specification catalogue",1
consumer_redress_programme.pdf,pdf_page_header_repeats,T8,0,-,"spec 2.2 and 4",1
consumer_redress_programme.pdf,pdf_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
consumer_redress_programme.pdf,text_layer_pipe_separated,T9,0,-,"specification catalogue",1
currency_redenomination.ini,currency_differs_from_market,T2,0,-,"limit policy 4.2",1035
currency_redenomination.ini,ini_colon_delimiter_file,T9,0,-,"governance 3.8",1
currency_redenomination.ini,ini_inline_comment,T9,0,-,"catalogue ini rules",24
currency_redenomination.ini,interpolation_disabled,T9,0,-,"specification catalogue",1
currency_redenomination.ini,iso_numeric_currency,T13,0,-,"governance 3.8",1
currency_redenomination.ini,iso_numeric_zero_padded,T13,0,-,"governance 3.8",28
currency_redenomination.ini,key_homoglyph,T1,0,-,"spec 4 conventions",20
currency_redenomination.ini,key_hyphen,T1,0,-,"spec 4 conventions",21
currency_redenomination.ini,key_lower,T1,0,-,"spec 4 conventions",22
currency_redenomination.ini,key_nbsp,T10,0,-,"spec 4 conventions",18
currency_redenomination.ini,key_zero_pad,T1,0,-,"spec 4 conventions",22
currency_redenomination.ini,key_zwsp,T10,0,-,"spec 4 conventions",19
currency_redenomination.ini,non_market_currency_codes,T15,0,-,"governance 3.8",1
customer_master.db,alias_targets_merged_customer,T13,0,-,"spec 3.6",1
customer_master.db,control_in_view,T9,0,-,"specification catalogue",1
customer_master.db,cust_homoglyph@alias,T1,0,-,"spec 4 conventions",188
customer_master.db,cust_homoglyph@customer,T1,0,-,"spec 4 conventions",183
customer_master.db,cust_homoglyph@master,T1,0,-,"spec 4 conventions",181
customer_master.db,cust_lower@alias,T1,0,-,"spec 4 conventions",189
customer_master.db,cust_lower@customer,T1,0,-,"spec 4 conventions",181
customer_master.db,cust_lower@master,T1,0,-,"spec 4 conventions",187
customer_master.db,cust_space@alias,T1,0,-,"spec 4 conventions",188
customer_master.db,cust_space@customer,T1,0,-,"spec 4 conventions",204
customer_master.db,cust_space@master,T1,0,-,"spec 4 conventions",184
customer_master.db,cust_zero_pad@alias,T1,0,-,"spec 4 conventions",180
customer_master.db,cust_zero_pad@customer,T1,0,-,"spec 4 conventions",189
customer_master.db,cust_zero_pad@master,T1,0,-,"spec 4 conventions",184
customer_master.db,cust_zwsp@alias,T10,0,-,"spec 4 conventions",178
customer_master.db,cust_zwsp@customer,T10,0,-,"spec 4 conventions",180
customer_master.db,cust_zwsp@master,T10,0,-,"spec 4 conventions",192
customer_master.db,date_dmy_dot@customer_since,T3,0,-,"catalogue date and month notations",179
customer_master.db,tables_in_name_order,T8,0,-,"specification catalogue",1
customer_master.db,two_tables_one_delivery,T8,0,-,"spec 2.2",1
customer_merge_decisions.docx,appendix_table_only_records,T8,0,-,"specification catalogue",1
customer_merge_decisions.docx,cust_homoglyph,T1,0,-,"spec 4 conventions",23
customer_merge_decisions.docx,cust_lower,T1,0,-,"spec 4 conventions",21
customer_merge_decisions.docx,cust_space,T1,0,-,"spec 4 conventions",23
customer_merge_decisions.docx,cust_zero_pad,T1,0,-,"spec 4 conventions",25
customer_merge_decisions.docx,cust_zwsp,T10,0,-,"spec 4 conventions",22
customer_merge_decisions.docx,custom_properties_control,T9,0,-,"specification catalogue",1
customer_merge_decisions.docx,date_compact,T3,0,-,"catalogue date and month notations",23
customer_merge_decisions.docx,date_dmy_dot,T3,0,-,"catalogue date and month notations",22
customer_merge_decisions.docx,date_dmy_slash,T3,0,-,"catalogue date and month notations",23
customer_merge_decisions.docx,docx_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
customer_merge_decisions.docx,docx_table_split_repeated_header,T8,0,-,"spec 2.2 and 4",1
customer_merge_decisions.docx,merge_not_approved,T6,0,-,"merge decisions",1122
customer_merge_decisions.docx,status_lowercase,T1,0,-,"spec 4 conventions",21
customer_merge_decisions.docx,status_padded,T9,0,-,"spec 4 conventions",24
customer_merge_decisions.docx,status_title,T1,0,-,"spec 4 conventions",23
customer_merges_2026.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
customer_merges_2026.tsv,cust_homoglyph,T1,0,-,"spec 4 conventions",22
customer_merges_2026.tsv,cust_lower,T1,0,-,"spec 4 conventions",22
customer_merges_2026.tsv,cust_space,T1,0,-,"spec 4 conventions",23
customer_merges_2026.tsv,cust_zero_pad,T1,0,-,"spec 4 conventions",21
customer_merges_2026.tsv,cust_zwsp,T10,0,-,"spec 4 conventions",20
customer_merges_2026.tsv,date_compact,T3,0,-,"catalogue date and month notations",23
customer_merges_2026.tsv,date_dmy_dot,T3,0,-,"catalogue date and month notations",23
customer_merges_2026.tsv,date_dmy_slash,T3,0,-,"catalogue date and month notations",21
customer_merges_2026.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
customer_merges_2026.tsv,legacy_customer_id,T13,0,-,"governance 3.10",1326
customer_merges_2026.tsv,merge_not_approved,T6,0,-,"merge decisions",1070
customer_merges_2026.tsv,status_lowercase,T1,0,-,"spec 4 conventions",23
customer_merges_2026.tsv,status_padded,T9,0,-,"spec 4 conventions",26
customer_merges_2026.tsv,status_title,T1,0,-,"spec 4 conventions",22
customer_merges_2026.tsv,tsv_reemitted_header,T8,0,-,"spec 2.2 and 4",1
customer_merges_2026.tsv,tsv_trailing_empty_field,T9,0,-,"spec 4 conventions",19
customer_merges_2026.tsv,tsv_utf8_bom,T10,0,-,"spec 2.2 and 4",1
data_quality_issue_log.md,accepted_issue_no_action,T6,0,-,"dq log preamble",4694
data_quality_issue_log.md,delivery_name_case,T1,0,-,"dq log preamble",27
data_quality_issue_log.md,escaped_pipes,T9,0,-,"specification catalogue",1
data_quality_issue_log.md,historical_delivery_names,T13,0,-,"dq log preamble",1
data_quality_issue_log.md,id_lower,T1,0,-,"spec 4 conventions",19
data_quality_issue_log.md,id_padded,T9,0,-,"spec 4 conventions",18
data_quality_issue_log.md,note_with_escaped_pipe,T9,0,-,"dq log preamble",1
data_quality_issue_log.md,quarantined_records,T6,0,-,"dq log preamble",1
data_quality_issue_log.md,record_number_zero_padded,T9,0,-,"dq log preamble",25
data_quality_issue_log.md,status_lowercase,T1,0,-,"spec 4 conventions",21
data_quality_issue_log.md,status_padded,T9,0,-,"spec 4 conventions",20
data_quality_issue_log.md,status_title,T1,0,-,"spec 4 conventions",21
deceased_notifications_feed.xml,attributes_and_child_elements,T9,0,-,"specification catalogue",1
deceased_notifications_feed.xml,control_element,T9,0,-,"specification catalogue",1
deceased_notifications_feed.xml,cust_homoglyph@customer,T1,0,-,"spec 4 conventions",21
deceased_notifications_feed.xml,cust_lower@customer,T1,0,-,"spec 4 conventions",22
deceased_notifications_feed.xml,cust_space@customer,T1,0,-,"spec 4 conventions",23
deceased_notifications_feed.xml,cust_zero_pad@customer,T1,0,-,"spec 4 conventions",22
deceased_notifications_feed.xml,cust_zwsp@customer,T10,0,-,"spec 4 conventions",22
deceased_notifications_feed.xml,date_compact@notified,T3,0,-,"catalogue date and month notations",20
deceased_notifications_feed.xml,date_dmy_dot@notified,T3,0,-,"catalogue date and month notations",21
deceased_notifications_feed.xml,date_dmy_slash@notified,T3,0,-,"catalogue date and month notations",21
deceased_notifications_feed.xml,deceased_vs_window_end,T11,0,-,"exclusion policy 2.5",146
deceased_notifications_feed.xml,xml_entities,T9,0,-,"spec 4 conventions",18
deceased_notifications_feed.xml,xml_whitespace_text,T9,0,-,"spec 4 conventions",12
deceased_notifications_register.pdf,cust_lower@customer,T1,0,-,"spec 4 conventions",22
deceased_notifications_register.pdf,cust_space@customer,T1,0,-,"spec 4 conventions",22
deceased_notifications_register.pdf,cust_zero_pad@customer,T1,0,-,"spec 4 conventions",20
deceased_notifications_register.pdf,date_compact@notified,T3,0,-,"catalogue date and month notations",22
deceased_notifications_register.pdf,date_dmy_dot@notified,T3,0,-,"catalogue date and month notations",22
deceased_notifications_register.pdf,date_dmy_slash@notified,T3,0,-,"catalogue date and month notations",23
deceased_notifications_register.pdf,deceased_vs_window_end,T11,0,-,"exclusion policy 2.5",59
deceased_notifications_register.pdf,page_footer_lines,T8,0,-,"specification catalogue",1
deceased_notifications_register.pdf,pdf_page_header_repeats,T8,0,-,"spec 2.2 and 4",1
deceased_notifications_register.pdf,pdf_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
deceased_notifications_register.pdf,register_names_aliases,T13,0,-,"specification and catalogue",1
deceased_notifications_register.pdf,text_layer_pipe_separated,T9,0,-,"specification catalogue",1
delivery_manifest.json,certified_partition_scope,T13,0,-,"specification and catalogue",1
delivery_manifest.json,control_object_last,T9,0,-,"specification catalogue",1
delivery_manifest.json,delivered_at_order,T11,0,-,"specification and catalogue",1
delivery_manifest.json,id_lower,T1,0,-,"spec 4 conventions",19
delivery_manifest.json,id_padded,T9,0,-,"spec 4 conventions",19
delivery_manifest.json,iso_fraction,T3,0,-,"spec 4 conventions",21
delivery_manifest.json,iso_offset,T3,0,-,"spec 4 conventions",20
delivery_manifest.json,json_null_field,T5,0,-,"spec 4 conventions",16
delivery_manifest.json,json_unicode_escapes,T10,0,-,"spec 4 conventions",16
delivery_manifest.json,records_under_named_key,T8,0,-,"specification catalogue",1
delivery_manifest.json,status_lowercase,T1,0,-,"spec 4 conventions",23
delivery_manifest.json,status_padded,T9,0,-,"spec 4 conventions",19
delivery_manifest.json,status_title,T1,0,-,"spec 4 conventions",22
delivery_manifest.json,withdrawn_history_deliveries,T6,0,-,"specification and catalogue",1
employee_leavers.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
employee_leavers.tsv,date_compact@leave_date,T3,0,-,"catalogue date and month notations",21
employee_leavers.tsv,date_dmy_dot@leave_date,T3,0,-,"catalogue date and month notations",23
employee_leavers.tsv,date_dmy_slash@leave_date,T3,0,-,"catalogue date and month notations",18
employee_leavers.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
employee_leavers.tsv,id_lower@employee_id,T1,0,-,"spec 4 conventions",20
employee_leavers.tsv,id_padded@employee_id,T9,0,-,"spec 4 conventions",20
employee_leavers.tsv,leave_relative_to_decision,T11,0,-,"exclusion policy 2.1",629
employee_leavers.tsv,rehire_pairing,T7,0,-,"specification and catalogue",1
employee_leavers.tsv,tsv_reemitted_header,T8,0,-,"spec 2.2 and 4",1
employee_leavers.tsv,tsv_trailing_empty_field,T9,0,-,"spec 4 conventions",13
employee_leavers.tsv,tsv_utf8_bom,T10,0,-,"spec 2.2 and 4",1
employee_leavers.tsv,utf8_bom_register,T10,0,-,"specification and catalogue",1
errata_register.md,date_compact,T3,0,-,"catalogue date and month notations",22
errata_register.md,date_dmy_dot,T3,0,-,"catalogue date and month notations",20
errata_register.md,escaped_pipes,T9,0,-,"specification catalogue",1
errata_register.md,int_padded,T9,0,-,"spec 4 conventions",22
errata_register.md,key_homoglyph,T1,0,-,"spec 4 conventions",20
errata_register.md,key_hyphen,T1,0,-,"spec 4 conventions",20
errata_register.md,key_lower,T1,0,-,"spec 4 conventions",21
errata_register.md,key_nbsp,T10,0,-,"spec 4 conventions",22
errata_register.md,key_space,T1,0,-,"spec 4 conventions",21
errata_register.md,key_zero_pad,T1,0,-,"spec 4 conventions",21
errata_register.md,key_zwsp,T10,0,-,"spec 4 conventions",23
errata_register.md,later_erratum_wins,T7,0,-,"errata preamble",1
errata_register.md,month_compact,T3,0,-,"catalogue date and month notations",20
errata_register.md,month_slash,T3,0,-,"catalogue date and month notations",20
errata_register.md,rejected_erratum_cohort,T6,0,-,"errata preamble",120
errata_register.md,rejected_row_errata,T6,0,-,"errata preamble",1
errata_register.md,rule_errata_need_cr_status,T14,0,-,"governance 3.3",1
errata_register.md,status_lowercase,T1,0,-,"spec 4 conventions",21
errata_register.md,status_padded,T9,0,-,"spec 4 conventions",20
errata_register.md,status_title,T1,0,-,"spec 4 conventions",21
exclusion_policy.docx,appendix_table_only_records,T8,0,-,"specification catalogue",1
exclusion_policy.docx,cust_homoglyph@customer,T1,0,-,"spec 4 conventions",19
exclusion_policy.docx,cust_lower@customer,T1,0,-,"spec 4 conventions",23
exclusion_policy.docx,cust_space@customer,T1,0,-,"spec 4 conventions",20
exclusion_policy.docx,cust_zero_pad@customer,T1,0,-,"spec 4 conventions",19
exclusion_policy.docx,cust_zwsp@customer,T10,0,-,"spec 4 conventions",21
exclusion_policy.docx,custom_properties_control,T9,0,-,"specification catalogue",1
exclusion_policy.docx,date_compact@start_date,T3,0,-,"catalogue date and month notations",22
exclusion_policy.docx,date_dmy_dot@start_date,T3,0,-,"catalogue date and month notations",22
exclusion_policy.docx,date_dmy_slash@start_date,T3,0,-,"catalogue date and month notations",21
exclusion_policy.docx,docx_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
exclusion_policy.docx,docx_table_split_repeated_header,T8,0,-,"spec 2.2 and 4",1
exclusion_policy.docx,employee_customer_alias,T13,0,-,"exclusion policy 2.1",117
exclusion_policy.docx,employee_is_customer,T13,0,-,"exclusion policy 2.1",706
exclusion_policy.docx,id_lower@employee,T1,0,-,"spec 4 conventions",19
exclusion_policy.docx,id_padded@employee,T9,0,-,"spec 4 conventions",19
forbearance_extensions_register.pdf,extension_moves_end,T7,0,-,"bad definition standard 3",1428
forbearance_extensions_register.pdf,extension_of_revoked_grant,T6,0,-,"specification and catalogue",1
forbearance_extensions_register.pdf,extensions_for_other_portfolios,T13,0,-,"specification and catalogue",1
forbearance_extensions_register.pdf,id_lower@grant,T1,0,-,"spec 4 conventions",24
forbearance_extensions_register.pdf,id_padded@grant,T9,0,-,"spec 4 conventions",20
forbearance_extensions_register.pdf,month_compact@new_to_month,T3,0,-,"catalogue date and month notations",23
forbearance_extensions_register.pdf,month_slash@new_to_month,T3,0,-,"catalogue date and month notations",18
forbearance_extensions_register.pdf,multiple_extensions_latest_wins,T7,0,-,"specification and catalogue",1
forbearance_extensions_register.pdf,page_footer_lines,T8,0,-,"specification catalogue",1
forbearance_extensions_register.pdf,pdf_page_header_repeats,T8,0,-,"spec 2.2 and 4",1
forbearance_extensions_register.pdf,pdf_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
forbearance_extensions_register.pdf,text_layer_pipe_separated,T9,0,-,"specification catalogue",1
fraud_alerts_2025.jsonl,alert_not_confirmed,T6,0,-,"exclusion policy 2.6",630
fraud_alerts_2025.jsonl,confirmed_alert_vs_window,T11,0,-,"exclusion policy 2.6",270
fraud_alerts_2025.jsonl,control_line_last,T9,0,-,"specification catalogue",1
fraud_alerts_2025.jsonl,date_compact@alert_date,T3,0,-,"catalogue date and month notations",20
fraud_alerts_2025.jsonl,date_dmy_dot@alert_date,T3,0,-,"catalogue date and month notations",22
fraud_alerts_2025.jsonl,date_dmy_slash@alert_date,T3,0,-,"catalogue date and month notations",21
fraud_alerts_2025.jsonl,id_lower@case,T1,0,-,"spec 4 conventions",21
fraud_alerts_2025.jsonl,id_padded@case,T9,0,-,"spec 4 conventions",21
fraud_alerts_2025.jsonl,jsonl_unicode_escapes,T10,0,-,"spec 4 conventions",17
fraud_alerts_2025.jsonl,key_homoglyph@account,T1,0,-,"spec 4 conventions",23
fraud_alerts_2025.jsonl,key_hyphen@account,T1,0,-,"spec 4 conventions",21
fraud_alerts_2025.jsonl,key_lower@account,T1,0,-,"spec 4 conventions",18
fraud_alerts_2025.jsonl,key_nbsp@account,T10,0,-,"spec 4 conventions",20
fraud_alerts_2025.jsonl,key_space@account,T1,0,-,"spec 4 conventions",21
fraud_alerts_2025.jsonl,key_zero_pad@account,T1,0,-,"spec 4 conventions",19
fraud_alerts_2025.jsonl,key_zwsp@account,T10,0,-,"spec 4 conventions",21
fraud_alerts_2025.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
fraud_alerts_2026.xml,alert_not_confirmed,T6,0,-,"exclusion policy 2.6",83
fraud_alerts_2026.xml,attributes_and_child_elements,T9,0,-,"specification catalogue",1
fraud_alerts_2026.xml,confirmed_alert_vs_window,T11,0,-,"exclusion policy 2.6",172
fraud_alerts_2026.xml,control_element,T9,0,-,"specification catalogue",1
fraud_alerts_2026.xml,date_compact@raised,T3,0,-,"catalogue date and month notations",21
fraud_alerts_2026.xml,date_dmy_dot@raised,T3,0,-,"catalogue date and month notations",21
fraud_alerts_2026.xml,date_dmy_slash@raised,T3,0,-,"catalogue date and month notations",20
fraud_alerts_2026.xml,id_lower@case,T1,0,-,"spec 4 conventions",20
fraud_alerts_2026.xml,id_padded@case,T9,0,-,"spec 4 conventions",23
fraud_alerts_2026.xml,key_homoglyph@account,T1,0,-,"spec 4 conventions",20
fraud_alerts_2026.xml,key_hyphen@account,T1,0,-,"spec 4 conventions",19
fraud_alerts_2026.xml,key_lower@account,T1,0,-,"spec 4 conventions",19
fraud_alerts_2026.xml,key_nbsp@account,T10,0,-,"spec 4 conventions",23
fraud_alerts_2026.xml,key_space@account,T1,0,-,"spec 4 conventions",21
fraud_alerts_2026.xml,key_zero_pad@account,T1,0,-,"spec 4 conventions",21
fraud_alerts_2026.xml,key_zwsp@account,T10,0,-,"spec 4 conventions",21
fraud_alerts_2026.xml,xml_entities,T9,0,-,"spec 4 conventions",16
fraud_alerts_2026.xml,xml_whitespace_text,T9,0,-,"spec 4 conventions",15
fraud_case_dispositions.json,cases_array_key,T8,0,-,"specification and catalogue",1
fraud_case_dispositions.json,cleared_and_open_cases,T6,0,-,"specification and catalogue",1
fraud_case_dispositions.json,control_object_last,T9,0,-,"specification catalogue",1
fraud_case_dispositions.json,id_lower@case_id,T1,0,-,"spec 4 conventions",43
fraud_case_dispositions.json,id_padded@case_id,T9,0,-,"spec 4 conventions",43
fraud_case_dispositions.json,json_null_field,T5,0,-,"spec 4 conventions",28
fraud_case_dispositions.json,json_unicode_escapes,T10,0,-,"spec 4 conventions",29
fraud_case_dispositions.json,records_under_named_key,T8,0,-,"specification catalogue",1
fraud_case_dispositions.json,status_lowercase@disposition,T1,0,-,"spec 4 conventions",39
fraud_case_dispositions.json,status_padded@disposition,T9,0,-,"spec 4 conventions",39
fraud_case_dispositions.json,status_title@disposition,T1,0,-,"spec 4 conventions",41
fx_rates_ecb_mirror.xml,attributes_and_child_elements,T9,1,-,"specification catalogue",1
fx_rates_ecb_mirror.xml,ccy_lowercase,T1,1,push,"governance 3.8 (values not used)",30
fx_rates_ecb_mirror.xml,ccy_padded,T9,1,push,"governance 3.8 (values not used)",25
fx_rates_ecb_mirror.xml,complete_coverage_label,T16,1,pull,"governance 3.8",1
fx_rates_ecb_mirror.xml,control_element,T9,1,-,"specification catalogue",1
fx_rates_ecb_mirror.xml,coverage_beyond_cycle,T11,1,pull,"governance policy",1
fx_rates_ecb_mirror.xml,currency_names_diacritics,T10,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,eur_rate_is_one,T15,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,inverted_quotation,T2,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,iso_numeric_crosswalk_only_here,T13,1,push,"governance 3.8",1
fx_rates_ecb_mirror.xml,iso_numeric_with_leading_zero,T13,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,rate_cdata,T9,1,push,"governance 3.8 (values not used)",29
fx_rates_ecb_mirror.xml,rate_char_reference,T9,1,push,"governance 3.8 (values not used)",28
fx_rates_ecb_mirror.xml,rate_decimal_comma,T4,1,push,"governance 3.8 (values not used)",29
fx_rates_ecb_mirror.xml,rate_extra_decimals,T12,1,push,"governance 3.8 (values not used)",31
fx_rates_ecb_mirror.xml,rate_not_available,T5,1,push,"governance 3.8 (values not used)",28
fx_rates_ecb_mirror.xml,rate_padded,T9,1,push,"governance 3.8 (values not used)",30
fx_rates_ecb_mirror.xml,rate_scientific,T4,1,push,"governance 3.8 (values not used)",29
fx_rates_ecb_mirror.xml,rates_forward_filled_weekends,T16,1,pull,"governance 3.8",1
fx_rates_ecb_mirror.xml,rates_on_market_holidays,T16,1,pull,"governance 3.8",1
fx_rates_ecb_mirror.xml,reference_only_declared,T14,1,push,"governance 3.8",1
fx_rates_ecb_mirror.xml,sections_unsorted,T7,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,two_element_types,T8,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,utf8_bom,T10,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,withdrawn_currency_codes,T6,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,xml_comments,T9,1,-,"governance 3.8",1
fx_rates_ecb_mirror.xml,xml_default_namespace,T9,1,-,"governance 3.8",1
governance_precedence_policy.docx,appendix_table_only_records,T8,0,-,"specification catalogue",1
governance_precedence_policy.docx,custom_properties_control,T9,0,-,"specification catalogue",1
governance_precedence_policy.docx,date_compact,T3,0,-,"catalogue date and month notations",20
governance_precedence_policy.docx,date_dmy_dot,T3,0,-,"catalogue date and month notations",20
governance_precedence_policy.docx,date_dmy_slash,T3,0,-,"catalogue date and month notations",19
governance_precedence_policy.docx,docx_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
governance_precedence_policy.docx,docx_table_split_repeated_header,T8,0,-,"spec 2.2 and 4",1
governance_precedence_policy.docx,id_lower,T1,0,-,"spec 4 conventions",22
governance_precedence_policy.docx,id_padded,T9,0,-,"spec 4 conventions",21
governance_precedence_policy.docx,status_lowercase,T1,0,-,"spec 4 conventions",20
governance_precedence_policy.docx,status_padded,T9,0,-,"spec 4 conventions",21
governance_precedence_policy.docx,status_title,T1,0,-,"spec 4 conventions",19
legacy_account_map.ini,default_key_looks_like_legacy_number,T13,0,-,"catalogue ini rules",1
legacy_account_map.ini,id_lower,T1,0,-,"spec 4 conventions",22
legacy_account_map.ini,id_padded,T9,0,-,"spec 4 conventions",22
legacy_account_map.ini,ini_inline_comment,T9,0,-,"catalogue ini rules",28
legacy_account_map.ini,ini_percent_interpolation,T9,0,-,"catalogue ini rules",1
legacy_account_map.ini,interpolation_disabled,T9,0,-,"specification catalogue",1
legacy_account_map.ini,key_homoglyph,T1,0,-,"spec 4 conventions",23
legacy_account_map.ini,key_hyphen,T1,0,-,"spec 4 conventions",21
legacy_account_map.ini,key_lower,T1,0,-,"spec 4 conventions",20
legacy_account_map.ini,key_nbsp,T10,0,-,"spec 4 conventions",22
legacy_account_map.ini,key_space,T1,0,-,"spec 4 conventions",19
legacy_account_map.ini,key_zero_pad,T1,0,-,"spec 4 conventions",20
legacy_account_map.ini,key_zwsp,T10,0,-,"spec 4 conventions",22
limit_amendments_2025.xlsx,amendment_after_month_end,T11,0,-,"limit policy 4.1",1702
limit_amendments_2025.xlsx,amendment_in_month,T11,0,-,"limit policy 4.1",1142
limit_amendments_2025.xlsx,amendment_on_month_end,T11,0,-,"limit policy 4.1",548
limit_amendments_2025.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
limit_amendments_2025.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
limit_amendments_2025.xlsx,id_lower,T1,0,-,"spec 4 conventions",42
limit_amendments_2025.xlsx,id_padded,T9,0,-,"spec 4 conventions",40
limit_amendments_2025.xlsx,key_homoglyph,T1,0,-,"spec 4 conventions",37
limit_amendments_2025.xlsx,key_hyphen,T1,0,-,"spec 4 conventions",41
limit_amendments_2025.xlsx,key_lower,T1,0,-,"spec 4 conventions",42
limit_amendments_2025.xlsx,key_nbsp,T10,0,-,"spec 4 conventions",45
limit_amendments_2025.xlsx,key_space,T1,0,-,"spec 4 conventions",37
limit_amendments_2025.xlsx,key_zero_pad,T1,0,-,"spec 4 conventions",42
limit_amendments_2025.xlsx,key_zwsp,T10,0,-,"spec 4 conventions",40
limit_amendments_2025.xlsx,money_comma,T4,0,-,"spec 4 conventions",42
limit_amendments_2025.xlsx,money_thousands,T4,0,-,"spec 4 conventions",42
limit_amendments_2025.xlsx,money_three_decimals,T12,0,-,"spec 4 conventions",39
limit_amendments_2025.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
limit_amendments_2025.xlsx,xlsx_numeric_text_cells,T4,0,-,"spec 4 conventions",34
limit_management_policy.docx,amendment_after_month_end,T11,0,-,"limit policy 4.1",1094
limit_management_policy.docx,amendment_before_decision,T11,0,-,"limit policy 4.1",353
limit_management_policy.docx,amendment_in_month,T11,0,-,"limit policy 4.1",618
limit_management_policy.docx,amendment_on_month_end,T11,0,-,"limit policy 4.1",105
limit_management_policy.docx,appendix_table_only_records,T8,0,-,"specification catalogue",1
limit_management_policy.docx,custom_properties_control,T9,0,-,"specification catalogue",1
limit_management_policy.docx,date_compact,T3,0,-,"catalogue date and month notations",20
limit_management_policy.docx,date_dmy_dot,T3,0,-,"catalogue date and month notations",19
limit_management_policy.docx,date_dmy_slash,T3,0,-,"catalogue date and month notations",24
limit_management_policy.docx,docx_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
limit_management_policy.docx,docx_table_split_repeated_header,T8,0,-,"spec 2.2 and 4",1
limit_management_policy.docx,id_lower,T1,0,-,"spec 4 conventions",19
limit_management_policy.docx,id_padded,T9,0,-,"spec 4 conventions",19
limit_management_policy.docx,key_homoglyph,T1,0,-,"spec 4 conventions",20
limit_management_policy.docx,key_hyphen,T1,0,-,"spec 4 conventions",25
limit_management_policy.docx,key_lower,T1,0,-,"spec 4 conventions",23
limit_management_policy.docx,key_nbsp,T10,0,-,"spec 4 conventions",22
limit_management_policy.docx,key_space,T1,0,-,"spec 4 conventions",20
limit_management_policy.docx,key_zero_pad,T1,0,-,"spec 4 conventions",19
limit_management_policy.docx,key_zwsp,T10,0,-,"spec 4 conventions",21
litigation_hold_register.html,date_compact,T3,0,-,"catalogue date and month notations",20
litigation_hold_register.html,date_dmy_dot,T3,0,-,"catalogue date and month notations",24
litigation_hold_register.html,date_dmy_slash,T3,0,-,"catalogue date and month notations",21
litigation_hold_register.html,hold_ends_on_decision_date,T11,0,-,"erratum E-011",66
litigation_hold_register.html,hold_starts_after_decision,T11,0,-,"exclusion policy 2.2",94
litigation_hold_register.html,html_entities_nbsp,T10,0,-,"spec 4 conventions",16
litigation_hold_register.html,html_repeated_header_rows,T8,0,-,"spec 2.2 and 4",1
litigation_hold_register.html,html_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
litigation_hold_register.html,id_lower,T1,0,-,"spec 4 conventions",21
litigation_hold_register.html,id_padded,T9,0,-,"spec 4 conventions",20
litigation_hold_register.html,key_homoglyph,T1,0,-,"spec 4 conventions",20
litigation_hold_register.html,key_hyphen,T1,0,-,"spec 4 conventions",23
litigation_hold_register.html,key_lower,T1,0,-,"spec 4 conventions",21
litigation_hold_register.html,key_nbsp,T10,0,-,"spec 4 conventions",20
litigation_hold_register.html,key_space,T1,0,-,"spec 4 conventions",21
litigation_hold_register.html,key_zero_pad,T1,0,-,"spec 4 conventions",19
litigation_hold_register.html,key_zwsp,T10,0,-,"spec 4 conventions",21
litigation_hold_register.html,meta_control,T9,0,-,"specification catalogue",1
litigation_hold_register.html,open_end_word,T5,0,-,"spec 4.5",55
litigation_hold_register.html,th_rows_not_records,T8,0,-,"specification catalogue",1
market_holidays.ics,category_case,T1,0,-,"specification and catalogue",1
market_holidays.ics,closure_in_cohort_period,T11,0,-,"limit policy 4.3",56
market_holidays.ics,dtend_exclusive,T11,0,-,"RFC 5545",1
market_holidays.ics,dtstart_without_value_param,T3,0,-,"specification and catalogue",1
market_holidays.ics,ics_line_folding,T9,0,-,"RFC 5545",1
market_holidays.ics,market_case,T1,0,-,"specification and catalogue",1
market_holidays.ics,observance_in_cohort_period,T15,0,-,"limit policy 4.3",3
market_holidays.ics,observance_not_closure,T15,0,-,"limit policy 4.3",1
market_holidays.ics,summary_escaped_commas,T9,0,-,"specification and catalogue",1
market_holidays.ics,timed_cutoff_events,T3,0,-,"specification and catalogue",1
market_holidays.ics,utf8_bom_calendar,T10,0,-,"specification and catalogue",1
market_holidays.ics,vevent_blocks,T9,0,-,"specification catalogue",1
merge_candidates_ml.xlsx,auto_merge_label,T16,1,pull,"governance 3.10",1
merge_candidates_ml.xlsx,blank_cells_omitted,T5,1,-,"specification catalogue",1
merge_candidates_ml.xlsx,cust_homoglyph@customer,T1,1,-,"spec 4 conventions",47
merge_candidates_ml.xlsx,cust_homoglyph@customer_a,T1,1,-,"spec 4 conventions",49
merge_candidates_ml.xlsx,cust_homoglyph@customer_b,T1,1,-,"spec 4 conventions",51
merge_candidates_ml.xlsx,cust_lower@customer,T1,1,-,"spec 4 conventions",47
merge_candidates_ml.xlsx,cust_lower@customer_a,T1,1,-,"spec 4 conventions",47
merge_candidates_ml.xlsx,cust_lower@customer_b,T1,1,-,"spec 4 conventions",51
merge_candidates_ml.xlsx,cust_space@customer,T1,1,-,"spec 4 conventions",48
merge_candidates_ml.xlsx,cust_space@customer_a,T1,1,-,"spec 4 conventions",47
merge_candidates_ml.xlsx,cust_space@customer_b,T1,1,-,"spec 4 conventions",48
merge_candidates_ml.xlsx,cust_zero_pad@customer,T1,1,-,"spec 4 conventions",47
merge_candidates_ml.xlsx,cust_zero_pad@customer_a,T1,1,-,"spec 4 conventions",45
merge_candidates_ml.xlsx,cust_zero_pad@customer_b,T1,1,-,"spec 4 conventions",45
merge_candidates_ml.xlsx,cust_zwsp@customer,T10,1,-,"spec 4 conventions",47
merge_candidates_ml.xlsx,cust_zwsp@customer_a,T10,1,-,"spec 4 conventions",45
merge_candidates_ml.xlsx,cust_zwsp@customer_b,T10,1,-,"spec 4 conventions",49
merge_candidates_ml.xlsx,excel_1900_date_system,T3,1,-,"specification catalogue",1
merge_candidates_ml.xlsx,id_lower@candidate_id,T1,1,-,"spec 4 conventions",46
merge_candidates_ml.xlsx,id_lower@legacy_customer,T1,1,-,"spec 4 conventions",51
merge_candidates_ml.xlsx,id_padded@candidate_id,T9,1,-,"spec 4 conventions",46
merge_candidates_ml.xlsx,id_padded@legacy_customer,T9,1,-,"spec 4 conventions",45
merge_candidates_ml.xlsx,legacy_ids_superseded,T7,1,push,"governance policy",1
merge_candidates_ml.xlsx,legacy_sheet_authoritative,T13,1,push,"governance 3.10",1
merge_candidates_ml.xlsx,ml_candidate_not_decision,T16,1,pull,"",80
merge_candidates_ml.xlsx,probability_as_text_or_percent,T4,1,-,"governance 3.10",1
merge_candidates_ml.xlsx,probability_near_one,T15,1,pull,"governance 3.10",1
merge_candidates_ml.xlsx,review_candidates_never_decided,T6,1,pull,"governance policy",1
merge_candidates_ml.xlsx,shared_strings_table,T8,1,-,"specification catalogue",1
merge_candidates_ml.xlsx,status_lowercase@suggestion,T1,1,-,"spec 4 conventions",48
merge_candidates_ml.xlsx,status_padded@suggestion,T9,1,-,"spec 4 conventions",46
merge_candidates_ml.xlsx,status_title@suggestion,T1,1,-,"spec 4 conventions",48
merge_candidates_ml.xlsx,two_sheets_one_delivery,T8,1,-,"governance 3.10",1
model_documentation_v4.pdf,approvals_in_prose,T14,0,-,"spec 8.1",1
model_documentation_v4.pdf,cut_points_amended_by_errata,T14,0,-,"spec 8.1",1
model_documentation_v4.pdf,cut_table_before_grid,T13,0,-,"spec 8.1",1
model_documentation_v4.pdf,int_zero_pad@score,T9,0,-,"spec 4 conventions",19
model_documentation_v4.pdf,page_footer_lines,T8,0,-,"specification catalogue",1
model_documentation_v4.pdf,pd_comma@pd,T4,0,-,"spec 4 conventions",21
model_documentation_v4.pdf,pd_padded@pd,T9,0,-,"spec 4 conventions",23
model_documentation_v4.pdf,pd_trailing_zeros@pd,T4,0,-,"spec 4 conventions",23
model_documentation_v4.pdf,pdf_page_header_repeats,T8,0,-,"spec 8.1",1
model_documentation_v4.pdf,status_lowercase@segment,T1,0,-,"spec 4 conventions",22
model_documentation_v4.pdf,status_padded@segment,T9,0,-,"spec 4 conventions",21
model_documentation_v4.pdf,status_title@segment,T1,0,-,"spec 4 conventions",20
model_documentation_v4.pdf,text_layer_pipe_separated,T9,0,-,"specification catalogue",1
model_registry_v4.toml,aborted_run,T6,0,-,"spec 6.2",167
model_registry_v4.toml,approval_date_as_string,T3,0,-,"catalogue",1
model_registry_v4.toml,approval_segments_lowercase,T1,0,-,"spec 3.1",1
model_registry_v4.toml,dr_replay_host_runs,T13,0,-,"spec 6.2",1
model_registry_v4.toml,id_lower,T1,0,-,"spec 4 conventions",53
model_registry_v4.toml,id_padded,T9,0,-,"spec 4 conventions",52
model_registry_v4.toml,native_datetime_types,T9,0,-,"specification catalogue",1
model_registry_v4.toml,node_int_vs_string,T5,0,-,"catalogue",1
model_registry_v4.toml,run_without_events,T15,0,-,"spec 6.1",1
model_registry_v4.toml,shadow_version_runs,T13,0,-,"spec 6.3",1
model_registry_v4.toml,started_string_or_datetime,T3,0,-,"catalogue",1
model_registry_v4.toml,status_lowercase,T1,0,-,"spec 4 conventions",57
model_registry_v4.toml,status_padded,T9,0,-,"spec 4 conventions",56
model_registry_v4.toml,status_title,T1,0,-,"spec 4 conventions",51
model_registry_v4_1.toml,approval_all_segments,T15,1,pull,"governance policy",1
model_registry_v4_1.toml,approval_from_june,T11,1,pull,"governance 3.3",1
model_registry_v4_1.toml,approved_comment,T14,1,pull,"governance policy",1
model_registry_v4_1.toml,approved_label_in_title,T14,1,pull,"governance 3.3",1
model_registry_v4_1.toml,calibration_points_superseded,T7,1,pull,"governance 3.3",1
model_registry_v4_1.toml,cr_id_lower_case,T1,1,-,"governance 3.3",1
model_registry_v4_1.toml,dotted_keys,T8,1,-,"governance policy",1
model_registry_v4_1.toml,draft_change_request,T13,1,push,"governance 3.3",1
model_registry_v4_1.toml,duplicate_calibration_points,T7,1,-,"governance policy",1
model_registry_v4_1.toml,inline_table_owner,T9,1,-,"governance policy",1
model_registry_v4_1.toml,int_zero_pad@score,T9,1,-,"spec 4 conventions",22
model_registry_v4_1.toml,multiline_basic_string,T9,1,-,"governance 3.3",1
model_registry_v4_1.toml,native_datetime_types,T9,1,-,"specification catalogue",1
model_registry_v4_1.toml,newer_registry_version,T16,1,pull,"governance 3.3",1
model_registry_v4_1.toml,pd_comma@pd,T4,1,-,"spec 4 conventions",20
model_registry_v4_1.toml,pd_padded@pd,T9,1,-,"spec 4 conventions",22
model_registry_v4_1.toml,pd_trailing_zeros@pd,T4,1,-,"spec 4 conventions",26
model_registry_v4_1.toml,points_cover_scale_bounds,T15,1,-,"governance 3.3",1
model_registry_v4_1.toml,registry_version_4_1,T7,1,pull,"governance policy",1
model_registry_v4_1.toml,status_lowercase@segment,T1,1,-,"spec 4 conventions",24
model_registry_v4_1.toml,status_padded@segment,T9,1,-,"spec 4 conventions",18
model_registry_v4_1.toml,status_title@segment,T1,1,-,"spec 4 conventions",22
model_registry_v4_1.toml,unicode_escape_in_title,T10,1,-,"governance policy",1
model_registry_v4_1.toml,withdrawal_authoritative,T6,1,push,"governance 3.3",1
model_registry_v4_1.toml,withdrawal_cr_approved,T13,1,push,"governance policy",1
model_registry_v4_1.toml,withdrawal_local_date,T3,1,-,"governance 3.3",1
monitoring_spec_v4.md,appendix_table_split_repeated_header,T8,0,-,"spec 2.2",2
monitoring_spec_v4.md,catalogue_cells_with_semicolons,T9,0,-,"spec 2.2",1
monitoring_spec_v4.md,catalogue_names_every_file,T13,0,-,"specification and catalogue",1
monitoring_spec_v4.md,count_padded,T9,0,-,"spec 4 conventions",21
monitoring_spec_v4.md,count_thousands,T4,0,-,"spec 4 conventions",24
monitoring_spec_v4.md,dst_rule_in_prose,T3,0,-,"specification and catalogue",1
monitoring_spec_v4.md,escaped_pipes,T9,0,-,"specification catalogue",1
monitoring_spec_v4.md,int_zero_pad@score,T9,0,-,"spec 4 conventions",26
monitoring_spec_v4.md,rounding_half_even_rule,T12,0,-,"specification and catalogue",1
monitoring_spec_v4.md,rules_in_prose,T14,0,-,"spec 2.2",1
monitoring_spec_v4.md,status_lowercase@segment,T1,0,-,"spec 4 conventions",20
monitoring_spec_v4.md,status_padded@segment,T9,0,-,"spec 4 conventions",23
monitoring_spec_v4.md,status_title@segment,T1,0,-,"spec 4 conventions",24
ops_corrections.mbox,date_header_offsets,T3,0,-,"governance 2.4",1
ops_corrections.mbox,from_line_escaping,T9,0,-,"mbox format",1
ops_corrections.mbox,int_padded,T9,0,-,"spec 4 conventions",18
ops_corrections.mbox,key_homoglyph,T1,0,-,"spec 4 conventions",20
ops_corrections.mbox,key_hyphen,T1,0,-,"spec 4 conventions",21
ops_corrections.mbox,key_lower,T1,0,-,"spec 4 conventions",23
ops_corrections.mbox,key_nbsp,T10,0,-,"spec 4 conventions",20
ops_corrections.mbox,key_zero_pad,T1,0,-,"spec 4 conventions",22
ops_corrections.mbox,key_zwsp,T10,0,-,"spec 4 conventions",20
ops_corrections.mbox,later_correction_wins,T7,0,-,"specification and catalogue",1
ops_corrections.mbox,mboxo_from_lines,T9,0,-,"specification catalogue",1
ops_corrections.mbox,month_compact,T3,0,-,"catalogue date and month notations",19
ops_corrections.mbox,month_slash,T3,0,-,"catalogue date and month notations",22
ops_corrections.mbox,quoted_printable_bodies,T10,0,-,"mbox format",1
ops_corrections.mbox,retraction,T6,0,-,"governance 2.3",400
ops_corrections.mbox,retraction_after_correction,T11,0,-,"specification and catalogue",1
ops_corrections.mbox,subject_case_variants,T1,0,-,"specification and catalogue",1
product_code_crosswalk.ini,code_lower,T1,0,-,"spec 4 conventions",23
product_code_crosswalk.ini,code_padded,T9,0,-,"spec 4 conventions",24
product_code_crosswalk.ini,comment_lines_hash,T9,0,-,"catalogue ini rules",1
product_code_crosswalk.ini,current_codes_from_migrations,T13,0,-,"catalogue ini rules",1
product_code_crosswalk.ini,ini_colon_delimiter,T9,0,-,"catalogue ini rules",28
product_code_crosswalk.ini,ini_default_section_propagates,T9,0,-,"catalogue ini rules",1
product_code_crosswalk.ini,ini_inline_comment,T9,0,-,"catalogue ini rules",24
product_code_crosswalk.ini,interpolation_disabled,T9,0,-,"specification catalogue",1
product_code_crosswalk.ini,keys_with_surrounding_spaces,T9,0,-,"specification and catalogue",1
product_code_crosswalk.ini,one_section_per_segment,T8,0,-,"specification and catalogue",1
product_code_crosswalk.ini,section_names_case,T1,0,-,"catalogue ini rules",1
product_migrations_2025.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
product_migrations_2025.xlsx,code_lower,T1,0,-,"spec 4 conventions",27
product_migrations_2025.xlsx,code_padded,T9,0,-,"spec 4 conventions",25
product_migrations_2025.xlsx,date_compact,T3,0,-,"catalogue date and month notations",23
product_migrations_2025.xlsx,date_dmy_dot,T3,0,-,"catalogue date and month notations",23
product_migrations_2025.xlsx,date_dmy_slash,T3,0,-,"catalogue date and month notations",24
product_migrations_2025.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
product_migrations_2025.xlsx,id_lower,T1,0,-,"spec 4 conventions",25
product_migrations_2025.xlsx,id_padded,T9,0,-,"spec 4 conventions",24
product_migrations_2025.xlsx,key_homoglyph,T1,0,-,"spec 4 conventions",23
product_migrations_2025.xlsx,key_hyphen,T1,0,-,"spec 4 conventions",25
product_migrations_2025.xlsx,key_lower,T1,0,-,"spec 4 conventions",23
product_migrations_2025.xlsx,key_nbsp,T10,0,-,"spec 4 conventions",24
product_migrations_2025.xlsx,key_space,T1,0,-,"spec 4 conventions",22
product_migrations_2025.xlsx,key_zero_pad,T1,0,-,"spec 4 conventions",22
product_migrations_2025.xlsx,key_zwsp,T10,0,-,"spec 4 conventions",22
product_migrations_2025.xlsx,migration_after_decision,T7,0,-,"spec 3.4",2699
product_migrations_2025.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
product_migrations_2025.xlsx,xlsx_numeric_text_cells,T4,0,-,"spec 4 conventions",19
regulatory_exclusion_letter_2026.pdf,date_compact@notice_date,T3,0,-,"catalogue date and month notations",22
regulatory_exclusion_letter_2026.pdf,date_dmy_dot@notice_date,T3,0,-,"catalogue date and month notations",22
regulatory_exclusion_letter_2026.pdf,date_dmy_slash@notice_date,T3,0,-,"catalogue date and month notations",21
regulatory_exclusion_letter_2026.pdf,key_hyphen@account,T1,0,-,"spec 4 conventions",19
regulatory_exclusion_letter_2026.pdf,key_lower@account,T1,0,-,"spec 4 conventions",19
regulatory_exclusion_letter_2026.pdf,key_nbsp@account,T10,0,-,"spec 4 conventions",22
regulatory_exclusion_letter_2026.pdf,key_space@account,T1,0,-,"spec 4 conventions",23
regulatory_exclusion_letter_2026.pdf,key_zero_pad@account,T1,0,-,"spec 4 conventions",21
regulatory_exclusion_letter_2026.pdf,notice_vs_window_end,T11,0,-,"exclusion policy 2",265
regulatory_exclusion_letter_2026.pdf,page_footer_lines,T8,0,-,"specification catalogue",1
regulatory_exclusion_letter_2026.pdf,pdf_page_header_repeats,T8,0,-,"spec 2.2 and 4",1
regulatory_exclusion_letter_2026.pdf,pdf_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
regulatory_exclusion_letter_2026.pdf,text_layer_pipe_separated,T9,0,-,"specification catalogue",1
sampling_design_v2.yaml,future_cohort_entries_void,T6,1,-,"governance policy",1
sampling_design_v2.yaml,id_lower@entry,T1,1,-,"spec 4 conventions",31
sampling_design_v2.yaml,id_padded@entry,T9,1,-,"spec 4 conventions",30
sampling_design_v2.yaml,june_entries_authoritative,T13,1,push,"sampling methodology 2.1 / governance 3.14",1
sampling_design_v2.yaml,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",21
sampling_design_v2.yaml,key_hyphen,T1,1,-,"spec 3.1 key normalisation",25
sampling_design_v2.yaml,key_lower,T1,1,-,"spec 3.1 key normalisation",23
sampling_design_v2.yaml,key_nbsp,T10,1,-,"spec 3.1 key normalisation",25
sampling_design_v2.yaml,key_space,T1,1,-,"spec 3.1 key normalisation",26
sampling_design_v2.yaml,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",20
sampling_design_v2.yaml,key_zwsp,T10,1,-,"spec 3.1 key normalisation",27
sampling_design_v2.yaml,month_compact@entry,T3,1,-,"catalogue date and month notations",31
sampling_design_v2.yaml,month_slash@entry,T3,1,-,"catalogue date and month notations",31
sampling_design_v2.yaml,pi_comma@entry,T4,1,-,"spec 4 conventions",32
sampling_design_v2.yaml,pi_percent@entry,T4,1,-,"spec 4 conventions",31
sampling_design_v2.yaml,pi_ratio@entry,T4,1,-,"spec 4 conventions",33
sampling_design_v2.yaml,scalars_as_strings,T9,1,-,"specification catalogue",1
sampling_design_v2.yaml,v2_backtest_values_for_earlier_cohorts,T16,1,pull,"sampling methodology 2.1 / governance 3.14",1
sampling_design_v2.yaml,v2_design_newer_label,T16,1,pull,"sampling methodology 2.1 / governance 3.14",1
sampling_design_v2.yaml,v2_effective_cohorts_header,T14,1,push,"sampling methodology 2.1 / governance 3.14",1
sampling_design_v2.yaml,v2_future_cohort_entries,T11,1,push,"sampling methodology 2.1 / governance 3.14",1
sampling_design_v2.yaml,v2_pi_differs_for_bait,T16,1,pull,"governance policy",1
sampling_design_v2.yaml,v2_supersedes_v1_for_june_only,T7,1,push,"governance policy",1
sampling_design_v2.yaml,yaml_document_separator,T8,1,push,"sampling methodology 2.1 / governance 3.14",1
sampling_design_v2.yaml,yaml_flow_mapping@entry,T8,1,-,"spec 4 conventions",32
sampling_design_v2.yaml,yaml_norway_bool,T5,1,-,"spec 4.4",1
sampling_design_v2.yaml,yaml_quoted_scalar@entry,T9,1,-,"spec 4 conventions",31
sampling_design_v2.yaml,yaml_trailing_comment@entry,T9,1,-,"spec 4 conventions",30
sampling_inclusion_cz_hu_ch.yaml,id_lower,T1,0,-,"spec 4 conventions",36
sampling_inclusion_cz_hu_ch.yaml,id_padded,T9,0,-,"spec 4 conventions",32
sampling_inclusion_cz_hu_ch.yaml,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",26
sampling_inclusion_cz_hu_ch.yaml,key_lower,T1,0,-,"spec 3.1 key normalisation",25
sampling_inclusion_cz_hu_ch.yaml,key_space,T1,0,-,"spec 3.1 key normalisation",25
sampling_inclusion_cz_hu_ch.yaml,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",24
sampling_inclusion_cz_hu_ch.yaml,keyed_by_application_id,T13,0,-,"sampling 2.1",1
sampling_inclusion_cz_hu_ch.yaml,month_compact,T3,0,-,"catalogue date and month notations",33
sampling_inclusion_cz_hu_ch.yaml,month_slash,T3,0,-,"catalogue date and month notations",37
sampling_inclusion_cz_hu_ch.yaml,pi_comma,T4,0,-,"spec 4 conventions",36
sampling_inclusion_cz_hu_ch.yaml,pi_percent,T4,0,-,"spec 4 conventions",35
sampling_inclusion_cz_hu_ch.yaml,pi_ratio,T4,0,-,"spec 4 conventions",33
sampling_inclusion_cz_hu_ch.yaml,scalars_as_strings,T9,0,-,"specification catalogue",1
sampling_inclusion_cz_hu_ch.yaml,weight_eight,T15,0,-,"sampling 1",1
sampling_inclusion_cz_hu_ch.yaml,yaml_flow_mapping,T8,0,-,"spec 4 conventions",37
sampling_inclusion_cz_hu_ch.yaml,yaml_norway_bool,T5,0,-,"spec 4.4",1
sampling_inclusion_cz_hu_ch.yaml,yaml_quoted_scalar,T9,0,-,"spec 4 conventions",32
sampling_inclusion_cz_hu_ch.yaml,yaml_trailing_comment,T9,0,-,"spec 4 conventions",36
sampling_inclusion_dk_no.yaml,id_lower,T1,0,-,"spec 4 conventions",26
sampling_inclusion_dk_no.yaml,id_padded,T9,0,-,"spec 4 conventions",27
sampling_inclusion_dk_no.yaml,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",21
sampling_inclusion_dk_no.yaml,key_lower,T1,0,-,"spec 3.1 key normalisation",23
sampling_inclusion_dk_no.yaml,key_space,T1,0,-,"spec 3.1 key normalisation",21
sampling_inclusion_dk_no.yaml,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",20
sampling_inclusion_dk_no.yaml,keyed_by_application_id,T13,0,-,"sampling 2.1",1
sampling_inclusion_dk_no.yaml,month_compact,T3,0,-,"catalogue date and month notations",25
sampling_inclusion_dk_no.yaml,month_slash,T3,0,-,"catalogue date and month notations",28
sampling_inclusion_dk_no.yaml,pi_comma,T4,0,-,"spec 4 conventions",29
sampling_inclusion_dk_no.yaml,pi_percent,T4,0,-,"spec 4 conventions",29
sampling_inclusion_dk_no.yaml,pi_ratio,T4,0,-,"spec 4 conventions",29
sampling_inclusion_dk_no.yaml,scalars_as_strings,T9,0,-,"specification catalogue",1
sampling_inclusion_dk_no.yaml,weight_eight,T15,0,-,"sampling 1",1
sampling_inclusion_dk_no.yaml,yaml_flow_mapping,T8,0,-,"spec 4 conventions",28
sampling_inclusion_dk_no.yaml,yaml_norway_bool,T5,0,-,"spec 4.4",1
sampling_inclusion_dk_no.yaml,yaml_quoted_scalar,T9,0,-,"spec 4 conventions",26
sampling_inclusion_dk_no.yaml,yaml_trailing_comment,T9,0,-,"spec 4 conventions",30
sampling_inclusion_gb_pl_se.yaml,id_lower,T1,0,-,"spec 4 conventions",61
sampling_inclusion_gb_pl_se.yaml,id_padded,T9,0,-,"spec 4 conventions",54
sampling_inclusion_gb_pl_se.yaml,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",47
sampling_inclusion_gb_pl_se.yaml,key_lower,T1,0,-,"spec 3.1 key normalisation",44
sampling_inclusion_gb_pl_se.yaml,key_space,T1,0,-,"spec 3.1 key normalisation",42
sampling_inclusion_gb_pl_se.yaml,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",45
sampling_inclusion_gb_pl_se.yaml,keyed_by_application_id,T13,0,-,"sampling 2.1",1
sampling_inclusion_gb_pl_se.yaml,month_compact,T3,0,-,"catalogue date and month notations",57
sampling_inclusion_gb_pl_se.yaml,month_slash,T3,0,-,"catalogue date and month notations",51
sampling_inclusion_gb_pl_se.yaml,pi_comma,T4,0,-,"spec 4 conventions",56
sampling_inclusion_gb_pl_se.yaml,pi_percent,T4,0,-,"spec 4 conventions",60
sampling_inclusion_gb_pl_se.yaml,pi_ratio,T4,0,-,"spec 4 conventions",57
sampling_inclusion_gb_pl_se.yaml,scalars_as_strings,T9,0,-,"specification catalogue",1
sampling_inclusion_gb_pl_se.yaml,weight_eight,T15,0,-,"sampling 1",1
sampling_inclusion_gb_pl_se.yaml,yaml_flow_mapping,T8,0,-,"spec 4 conventions",60
sampling_inclusion_gb_pl_se.yaml,yaml_norway_bool,T5,0,-,"spec 4.4",1
sampling_inclusion_gb_pl_se.yaml,yaml_quoted_scalar,T9,0,-,"spec 4 conventions",57
sampling_inclusion_gb_pl_se.yaml,yaml_trailing_comment,T9,0,-,"spec 4 conventions",52
sampling_methodology.docx,appendix_table_only_records,T8,0,-,"specification catalogue",1
sampling_methodology.docx,custom_properties_control,T9,0,-,"specification catalogue",1
sampling_methodology.docx,docx_rule_in_prose,T14,0,-,"spec 2.2 and 4",1
sampling_methodology.docx,docx_table_split_repeated_header,T8,0,-,"spec 2.2 and 4",1
sampling_methodology.docx,key_homoglyph@account,T1,0,-,"spec 4 conventions",24
sampling_methodology.docx,key_hyphen@account,T1,0,-,"spec 4 conventions",20
sampling_methodology.docx,key_lower@account,T1,0,-,"spec 4 conventions",21
sampling_methodology.docx,key_nbsp@account,T10,0,-,"spec 4 conventions",21
sampling_methodology.docx,key_space@account,T1,0,-,"spec 4 conventions",21
sampling_methodology.docx,key_zero_pad@account,T1,0,-,"spec 4 conventions",20
sampling_methodology.docx,key_zwsp@account,T10,0,-,"spec 4 conventions",18
sampling_methodology.docx,override_rejected,T6,0,-,"sampling 2.3",173
sampling_methodology.docx,pi_comma@inclusion_probability,T4,0,-,"spec 4 conventions",22
sampling_methodology.docx,pi_percent@inclusion_probability,T4,0,-,"spec 4 conventions",20
sampling_methodology.docx,pi_ratio@inclusion_probability,T4,0,-,"spec 4 conventions",19
sampling_methodology.docx,status_lowercase@status,T1,0,-,"spec 4 conventions",20
sampling_methodology.docx,status_padded@status,T9,0,-,"spec 4 conventions",21
sampling_methodology.docx,status_title@status,T1,0,-,"spec 4 conventions",19
sampling_methodology.docx,weight_eight_valid,T15,0,-,"sampling 1",88
score_batches_2025_q1.jsonl,control_line_last,T9,0,-,"specification catalogue",1
score_batches_2025_q1.jsonl,epoch_milliseconds,T2,0,-,"catalogue",1
score_batches_2025_q1.jsonl,event_in_aborted_run,T6,0,-,"spec 6.2",63
score_batches_2025_q1.jsonl,event_in_void_run,T6,0,-,"governance 3.4",79
score_batches_2025_q1.jsonl,id_lower,T1,0,-,"spec 4 conventions",22
score_batches_2025_q1.jsonl,id_padded,T9,0,-,"spec 4 conventions",22
score_batches_2025_q1.jsonl,int_padded,T9,0,-,"spec 4 conventions",17
score_batches_2025_q1.jsonl,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",16
score_batches_2025_q1.jsonl,key_lower,T1,0,-,"spec 3.1 key normalisation",15
score_batches_2025_q1.jsonl,key_space,T1,0,-,"spec 3.1 key normalisation",15
score_batches_2025_q1.jsonl,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",17
score_batches_2025_q1.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
score_batches_2025_q1.jsonl,post_decision_rescore,T11,0,-,"spec 6.4 point in time",259
score_batches_2025_q1.jsonl,quarantined_record,T6,0,-,"dq log",10
score_batches_2025_q1.jsonl,version_not_approved_for_segment,T13,0,-,"spec 6.3",18
score_batches_2025_q2_a.jsonl,control_line_last,T9,0,-,"specification catalogue",1
score_batches_2025_q2_a.jsonl,epoch_milliseconds,T2,0,-,"catalogue",1
score_batches_2025_q2_a.jsonl,event_in_aborted_run,T6,0,-,"spec 6.2",57
score_batches_2025_q2_a.jsonl,event_in_void_run,T6,0,-,"governance 3.4",59
score_batches_2025_q2_a.jsonl,id_lower,T1,0,-,"spec 4 conventions",19
score_batches_2025_q2_a.jsonl,id_padded,T9,0,-,"spec 4 conventions",20
score_batches_2025_q2_a.jsonl,int_padded,T9,0,-,"spec 4 conventions",21
score_batches_2025_q2_a.jsonl,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",17
score_batches_2025_q2_a.jsonl,key_lower,T1,0,-,"spec 3.1 key normalisation",18
score_batches_2025_q2_a.jsonl,key_space,T1,0,-,"spec 3.1 key normalisation",16
score_batches_2025_q2_a.jsonl,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",18
score_batches_2025_q2_a.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
score_batches_2025_q2_a.jsonl,post_decision_rescore,T11,0,-,"spec 6.4 point in time",507
score_batches_2025_q2_a.jsonl,quarantined_record,T6,0,-,"dq log",4
score_batches_2025_q2_a.jsonl,version_not_approved_for_segment,T13,0,-,"spec 6.3",6
score_batches_2025_q2_a.jsonl,withdrawn_version_event,T13,0,-,"governance 3.3",157
score_batches_2025_q2_b.jsonl,control_line_last,T9,0,-,"specification catalogue",1
score_batches_2025_q2_b.jsonl,epoch_milliseconds,T2,0,-,"catalogue",1
score_batches_2025_q2_b.jsonl,event_in_aborted_run,T6,0,-,"spec 6.2",69
score_batches_2025_q2_b.jsonl,event_in_void_run,T6,0,-,"governance 3.4",66
score_batches_2025_q2_b.jsonl,id_lower,T1,0,-,"spec 4 conventions",22
score_batches_2025_q2_b.jsonl,id_padded,T9,0,-,"spec 4 conventions",21
score_batches_2025_q2_b.jsonl,int_padded,T9,0,-,"spec 4 conventions",21
score_batches_2025_q2_b.jsonl,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",15
score_batches_2025_q2_b.jsonl,key_lower,T1,0,-,"spec 3.1 key normalisation",18
score_batches_2025_q2_b.jsonl,key_space,T1,0,-,"spec 3.1 key normalisation",15
score_batches_2025_q2_b.jsonl,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",15
score_batches_2025_q2_b.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
score_batches_2025_q2_b.jsonl,post_decision_rescore,T11,0,-,"spec 6.4 point in time",506
score_batches_2025_q2_b.jsonl,quarantined_record,T6,0,-,"dq log",5
score_batches_2025_q2_b.jsonl,version_not_approved_for_segment,T13,0,-,"spec 6.3",7
score_batches_2025_q2_b.jsonl,withdrawn_version_event,T13,0,-,"governance 3.3",168
score_batches_2025_q2_c.jsonl,account_null,T5,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,approved_rows_authoritative,T13,1,push,"governance policy",1
score_batches_2025_q2_c.jsonl,control_line_last,T9,1,-,"specification catalogue",1
score_batches_2025_q2_c.jsonl,engine_build_label,T14,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,epoch_milliseconds,T2,1,-,"catalogue",1
score_batches_2025_q2_c.jsonl,event_in_aborted_run,T6,1,-,"spec 6.2",142
score_batches_2025_q2_c.jsonl,event_in_void_run,T6,1,-,"governance 3.4",185
score_batches_2025_q2_c.jsonl,id_lower,T1,1,-,"spec 4 conventions",57
score_batches_2025_q2_c.jsonl,id_padded,T9,1,-,"spec 4 conventions",53
score_batches_2025_q2_c.jsonl,int_padded,T9,1,-,"spec 4 conventions",53
score_batches_2025_q2_c.jsonl,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",42
score_batches_2025_q2_c.jsonl,key_hyphen,T1,1,-,"spec 3.1 key normalisation",39
score_batches_2025_q2_c.jsonl,key_lower,T1,1,-,"spec 3.1 key normalisation",40
score_batches_2025_q2_c.jsonl,key_nbsp,T10,1,-,"spec 3.1 key normalisation",39
score_batches_2025_q2_c.jsonl,key_space,T1,1,-,"spec 3.1 key normalisation",39
score_batches_2025_q2_c.jsonl,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",39
score_batches_2025_q2_c.jsonl,key_zwsp,T10,1,-,"spec 3.1 key normalisation",42
score_batches_2025_q2_c.jsonl,model_field_disagrees_with_register,T16,1,pull,"governance policy",1
score_batches_2025_q2_c.jsonl,newest_build_header,T16,1,pull,"governance policy",1
score_batches_2025_q2_c.jsonl,numbers_or_strings,T4,1,-,"specification catalogue",1
score_batches_2025_q2_c.jsonl,post_decision_rescore,T11,1,-,"spec 6.4 point in time",1562
score_batches_2025_q2_c.jsonl,rescore_supersedes_bait,T7,1,pull,"governance policy",1
score_batches_2025_q2_c.jsonl,rescores_after_decision,T11,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,run_not_registered,T13,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,score_as_string,T4,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,shadow_version_rows,T13,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,ts_ms_as_string,T4,1,-,"governance policy",1
score_batches_2025_q2_c.jsonl,ts_ms_float,T2,1,-,"governance policy",1
score_clock_skew_corrections.json,control_object_last,T9,0,-,"specification catalogue",1
score_clock_skew_corrections.json,id_lower@run,T1,0,-,"spec 4 conventions",173
score_clock_skew_corrections.json,id_padded@run,T9,0,-,"spec 4 conventions",166
score_clock_skew_corrections.json,int_padded@offset_seconds,T9,0,-,"spec 4 conventions",180
score_clock_skew_corrections.json,int_signed_string@offset_seconds,T4,0,-,"spec 4 conventions",181
score_clock_skew_corrections.json,json_null_field,T5,0,-,"spec 4 conventions",134
score_clock_skew_corrections.json,json_unicode_escapes,T10,0,-,"spec 4 conventions",132
score_clock_skew_corrections.json,nonzero_offset_skew_nodes,T3,0,-,"specification and catalogue",1
score_clock_skew_corrections.json,offsets_for_replay_runs,T13,0,-,"specification and catalogue",1
score_clock_skew_corrections.json,records_under_named_key,T8,0,-,"specification catalogue",1
score_clock_skew_corrections.json,zero_offset_rows,T15,0,-,"specification and catalogue",1
score_events_backfill.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
score_events_backfill.csv,event_in_aborted_run,T6,0,-,"spec 6.2",81
score_events_backfill.csv,event_in_void_run,T6,0,-,"governance 3.4",72
score_events_backfill.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
score_events_backfill.csv,id_lower,T1,0,-,"spec 4 conventions",22
score_events_backfill.csv,id_padded,T9,0,-,"spec 4 conventions",24
score_events_backfill.csv,int_padded,T9,0,-,"spec 4 conventions",19
score_events_backfill.csv,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",17
score_events_backfill.csv,key_space,T1,0,-,"spec 3.1 key normalisation",16
score_events_backfill.csv,key_zwsp,T10,0,-,"spec 3.1 key normalisation",14
score_events_backfill.csv,post_decision_rescore,T11,0,-,"spec 6.4 point in time",299
score_events_backfill.csv,quarantined_record,T6,0,-,"dq log",10
score_events_backfill.csv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
score_events_backfill.csv,version_not_approved_for_segment,T13,0,-,"spec 6.3",10
score_events_backfill.csv,withdrawn_version_event,T13,0,-,"governance 3.3",131
score_events_node5.parquet,epoch_seconds,T2,0,-,"catalogue",1
score_events_node5.parquet,event_in_aborted_run,T6,0,-,"spec 6.2",76
score_events_node5.parquet,event_in_void_run,T6,0,-,"governance 3.4",111
score_events_node5.parquet,id_lower,T1,0,-,"spec 4 conventions",30
score_events_node5.parquet,id_padded,T9,0,-,"spec 4 conventions",30
score_events_node5.parquet,int_padded,T9,0,-,"spec 4 conventions",28
score_events_node5.parquet,key_space,T1,0,-,"spec 3.1 key normalisation",25
score_events_node5.parquet,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",26
score_events_node5.parquet,nullable_columns,T5,0,-,"specification catalogue",1
score_events_node5.parquet,post_decision_rescore,T11,0,-,"spec 6.4 point in time",192
score_events_node5.parquet,quarantined_record,T6,0,-,"dq log",24
score_events_node5.parquet,row_groups_split,T9,0,-,"specification catalogue",1
score_events_node5.parquet,typed_integer_columns,T4,0,-,"specification catalogue",1
score_events_node5.parquet,version_not_approved_for_segment,T13,0,-,"spec 6.3",26
score_events_node5.parquet,withdrawn_version_event,T13,0,-,"governance 3.3",279
score_events_node6.xml,attributes_and_child_elements,T9,0,-,"specification catalogue",1
score_events_node6.xml,clock_skew_near_decision,T3,0,-,"spec 6.4",3418
score_events_node6.xml,control_element,T9,0,-,"specification catalogue",1
score_events_node6.xml,event_in_aborted_run,T6,0,-,"spec 6.2",113
score_events_node6.xml,event_in_void_run,T6,0,-,"governance 3.4",85
score_events_node6.xml,id_lower,T1,0,-,"spec 4 conventions",27
score_events_node6.xml,id_padded,T9,0,-,"spec 4 conventions",28
score_events_node6.xml,int_padded,T9,0,-,"spec 4 conventions",24
score_events_node6.xml,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",21
score_events_node6.xml,key_lower,T1,0,-,"spec 3.1 key normalisation",22
score_events_node6.xml,local_time_with_offset,T3,0,-,"catalogue",1
score_events_node6.xml,post_decision_rescore,T11,0,-,"spec 6.4 point in time",320
score_events_node6.xml,quarantined_record,T6,0,-,"dq log",23
score_events_node6.xml,version_not_approved_for_segment,T13,0,-,"spec 6.3",18
score_events_node6.xml,withdrawn_version_event,T13,0,-,"governance 3.3",265
score_events_node7.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
score_events_node7.tsv,event_in_aborted_run,T6,0,-,"spec 6.2",69
score_events_node7.tsv,event_in_void_run,T6,0,-,"governance 3.4",104
score_events_node7.tsv,excel_serial_utc,T3,0,-,"catalogue",1
score_events_node7.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
score_events_node7.tsv,id_lower,T1,0,-,"spec 4 conventions",25
score_events_node7.tsv,id_padded,T9,0,-,"spec 4 conventions",23
score_events_node7.tsv,int_padded,T9,0,-,"spec 4 conventions",21
score_events_node7.tsv,key_lower,T1,0,-,"spec 3.1 key normalisation",19
score_events_node7.tsv,key_nbsp,T10,0,-,"spec 3.1 key normalisation",23
score_events_node7.tsv,key_space,T1,0,-,"spec 3.1 key normalisation",19
score_events_node7.tsv,post_decision_rescore,T11,0,-,"spec 6.4 point in time",175
score_events_node7.tsv,quarantined_record,T6,0,-,"dq log",16
score_events_node7.tsv,version_not_approved_for_segment,T13,0,-,"spec 6.3",21
score_events_node7.tsv,withdrawn_version_event,T13,0,-,"governance 3.3",240
scoring_engine_node1.log,event_in_aborted_run,T6,0,-,"spec 6.2",103
scoring_engine_node1.log,event_in_void_run,T6,0,-,"governance 3.4",91
scoring_engine_node1.log,heartbeat_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node1.log,id_lower,T1,0,-,"spec 4 conventions",28
scoring_engine_node1.log,int_zero_pad,T9,0,-,"spec 4 conventions",27
scoring_engine_node1.log,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",22
scoring_engine_node1.log,key_hyphen,T1,0,-,"spec 3.1 key normalisation",20
scoring_engine_node1.log,key_lower,T1,0,-,"spec 3.1 key normalisation",25
scoring_engine_node1.log,post_decision_rescore,T11,0,-,"spec 6.4 point in time",173
scoring_engine_node1.log,quarantined_record,T6,0,-,"dq log",17
scoring_engine_node1.log,stack_trace_continuation,T9,0,-,"catalogue log records",30
scoring_engine_node1.log,utc_z_timestamps,T3,0,-,"specification catalogue",1
scoring_engine_node1.log,version_not_approved_for_segment,T13,0,-,"spec 6.3",25
scoring_engine_node1.log,warn_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node1.log,withdrawn_version_event,T13,0,-,"governance 3.3",274
scoring_engine_node2.log,event_in_aborted_run,T6,0,-,"spec 6.2",83
scoring_engine_node2.log,event_in_void_run,T6,0,-,"governance 3.4",116
scoring_engine_node2.log,heartbeat_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node2.log,id_lower,T1,0,-,"spec 4 conventions",29
scoring_engine_node2.log,int_zero_pad,T9,0,-,"spec 4 conventions",31
scoring_engine_node2.log,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",23
scoring_engine_node2.log,key_hyphen,T1,0,-,"spec 3.1 key normalisation",25
scoring_engine_node2.log,key_lower,T1,0,-,"spec 3.1 key normalisation",21
scoring_engine_node2.log,post_decision_rescore,T11,0,-,"spec 6.4 point in time",193
scoring_engine_node2.log,quarantined_record,T6,0,-,"dq log",16
scoring_engine_node2.log,stack_trace_continuation,T9,0,-,"catalogue log records",28
scoring_engine_node2.log,utc_z_timestamps,T3,0,-,"specification catalogue",1
scoring_engine_node2.log,version_not_approved_for_segment,T13,0,-,"spec 6.3",35
scoring_engine_node2.log,warn_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node2.log,withdrawn_version_event,T13,0,-,"governance 3.3",267
scoring_engine_node3.log,clock_skew_near_decision,T3,0,-,"spec 6.4",3769
scoring_engine_node3.log,event_in_aborted_run,T6,0,-,"spec 6.2",73
scoring_engine_node3.log,event_in_void_run,T6,0,-,"governance 3.4",117
scoring_engine_node3.log,heartbeat_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node3.log,id_lower,T1,0,-,"spec 4 conventions",31
scoring_engine_node3.log,int_zero_pad,T9,0,-,"spec 4 conventions",29
scoring_engine_node3.log,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",21
scoring_engine_node3.log,key_hyphen,T1,0,-,"spec 3.1 key normalisation",22
scoring_engine_node3.log,key_lower,T1,0,-,"spec 3.1 key normalisation",22
scoring_engine_node3.log,post_decision_rescore,T11,0,-,"spec 6.4 point in time",358
scoring_engine_node3.log,quarantined_record,T6,0,-,"dq log",16
scoring_engine_node3.log,stack_trace_continuation,T9,0,-,"catalogue log records",29
scoring_engine_node3.log,utc_z_timestamps,T3,0,-,"specification catalogue",1
scoring_engine_node3.log,version_not_approved_for_segment,T13,0,-,"spec 6.3",27
scoring_engine_node3.log,warn_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node3.log,withdrawn_version_event,T13,0,-,"governance 3.3",263
scoring_engine_node4.log,event_in_aborted_run,T6,0,-,"spec 6.2",98
scoring_engine_node4.log,event_in_void_run,T6,0,-,"governance 3.4",172
scoring_engine_node4.log,heartbeat_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node4.log,id_lower,T1,0,-,"spec 4 conventions",30
scoring_engine_node4.log,int_zero_pad,T9,0,-,"spec 4 conventions",32
scoring_engine_node4.log,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",24
scoring_engine_node4.log,key_hyphen,T1,0,-,"spec 3.1 key normalisation",24
scoring_engine_node4.log,key_lower,T1,0,-,"spec 3.1 key normalisation",23
scoring_engine_node4.log,post_decision_rescore,T11,0,-,"spec 6.4 point in time",223
scoring_engine_node4.log,quarantined_record,T6,0,-,"dq log",19
scoring_engine_node4.log,stack_trace_continuation,T9,0,-,"catalogue log records",33
scoring_engine_node4.log,utc_z_timestamps,T3,0,-,"specification catalogue",1
scoring_engine_node4.log,version_not_approved_for_segment,T13,0,-,"spec 6.3",24
scoring_engine_node4.log,warn_lines_not_records,T8,0,-,"specification catalogue",1
scoring_engine_node4.log,withdrawn_version_event,T13,0,-,"governance 3.3",277
scoring_engine_node9.log,acct_variants_in_replays,T1,1,-,"governance policy",1
scoring_engine_node9.log,ctrl_level_token,T8,1,-,"governance policy",1
scoring_engine_node9.log,dr_host_header_comment,T14,1,push,"governance policy",1
scoring_engine_node9.log,heartbeat_lines_not_records,T8,1,-,"specification catalogue",1
scoring_engine_node9.log,id_lower,T1,1,-,"spec 4 conventions",35
scoring_engine_node9.log,int_zero_pad,T9,1,-,"spec 4 conventions",31
scoring_engine_node9.log,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",26
scoring_engine_node9.log,key_hyphen,T1,1,-,"spec 3.1 key normalisation",26
scoring_engine_node9.log,key_lower,T1,1,-,"spec 3.1 key normalisation",27
scoring_engine_node9.log,key_nbsp,T10,1,-,"spec 3.1 key normalisation",23
scoring_engine_node9.log,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",23
scoring_engine_node9.log,key_zwsp,T10,1,-,"spec 3.1 key normalisation",24
scoring_engine_node9.log,logged_in_2026,T11,1,-,"governance policy",1
scoring_engine_node9.log,post_decision_rescore,T11,1,-,"spec 6.4 point in time",206
scoring_engine_node9.log,replay_orig_ts_field,T3,1,-,"governance policy",1
scoring_engine_node9.log,replay_runs_registered_node9,T13,1,push,"governance policy",1
scoring_engine_node9.log,replay_same_event_id,T16,1,pull,"governance policy",10
scoring_engine_node9.log,replay_score_drift,T16,1,pull,"governance policy",1
scoring_engine_node9.log,replays_cover_most_events,T16,1,pull,"governance policy",1
scoring_engine_node9.log,replays_logged_later,T7,1,-,"governance policy",1
scoring_engine_node9.log,replays_of_2024_scores,T11,1,-,"governance policy",1
scoring_engine_node9.log,replays_of_void_run_events,T6,1,-,"governance policy",1
scoring_engine_node9.log,utc_z_timestamps,T3,1,-,"specification catalogue",1
scoring_engine_node9.log,void_directive,T6,1,push,"governance policy",1
scoring_engine_node9.log,void_lines_without_events,T8,1,-,"governance policy",1
scoring_engine_node9.log,void_run_directive,T6,1,-,"governance 3.4 void directives",590
scoring_engine_node9.log,void_runs_in_other_files,T13,1,push,"governance policy",1
scoring_engine_node9.log,warn_lines_not_records,T8,1,-,"specification catalogue",1
scoring_runs_2025q2.toml,aborted_run,T6,0,-,"spec 6.2",374
scoring_runs_2025q2.toml,dr_replay_host_runs,T13,0,-,"spec 6.2",1
scoring_runs_2025q2.toml,id_lower,T1,0,-,"spec 4 conventions",120
scoring_runs_2025q2.toml,id_padded,T9,0,-,"spec 4 conventions",124
scoring_runs_2025q2.toml,native_datetime_types,T9,0,-,"specification catalogue",1
scoring_runs_2025q2.toml,node_int_vs_string,T5,0,-,"catalogue",1
scoring_runs_2025q2.toml,run_without_events,T15,0,-,"spec 6.1",1
scoring_runs_2025q2.toml,shadow_version_runs,T13,0,-,"spec 6.3",1
scoring_runs_2025q2.toml,started_string_or_datetime,T3,0,-,"catalogue",1
scoring_runs_2025q2.toml,status_lowercase,T1,0,-,"spec 4 conventions",122
scoring_runs_2025q2.toml,status_padded,T9,0,-,"spec 4 conventions",114
scoring_runs_2025q2.toml,status_title,T1,0,-,"spec 4 conventions",121
servicing_snapshots_2025q3.db,control_in_view,T9,0,-,"specification catalogue",1
servicing_snapshots_2025q3.db,corrected_by_errata,T7,0,-,"governance 2.1",35
servicing_snapshots_2025q3.db,corrected_by_feed,T7,0,-,"governance 2.1",42
servicing_snapshots_2025q3.db,corrected_by_mail,T7,0,-,"governance 2.1",30
servicing_snapshots_2025q3.db,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",179
servicing_snapshots_2025q3.db,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",49
servicing_snapshots_2025q3.db,forborne_month,T14,0,-,"bad definition standard 3",286
servicing_snapshots_2025q3.db,int_signed_string,T4,0,-,"spec 4 conventions",150
servicing_snapshots_2025q3.db,key_hyphen,T1,0,-,"spec 3.1 key normalisation",115
servicing_snapshots_2025q3.db,key_lower,T1,0,-,"spec 3.1 key normalisation",121
servicing_snapshots_2025q3.db,key_space,T1,0,-,"spec 3.1 key normalisation",113
servicing_snapshots_2025q3.db,month_compact,T3,0,-,"catalogue date and month notations",145
servicing_snapshots_2025q3.db,month_slash,T3,0,-,"catalogue date and month notations",144
servicing_snapshots_2025q3.db,quarantined_record,T6,0,-,"dq log",12
servicing_snapshots_2025q3.db,sqlite_balance_decimal_comma,T4,0,-,"catalogue",1
servicing_snapshots_2025q3.db,status_lowercase,T1,0,-,"spec 4 conventions",148
servicing_snapshots_2025q3.db,status_padded,T9,0,-,"spec 4 conventions",148
servicing_snapshots_2025q3.db,status_title,T1,0,-,"spec 4 conventions",146
servicing_snapshots_2025q3.db,tables_in_name_order,T8,0,-,"specification catalogue",1
servicing_snapshots_2025q3.db,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",151
servicing_snapshots_2026q1.db,control_in_view,T9,0,-,"specification catalogue",1
servicing_snapshots_2026q1.db,corrected_by_errata,T7,0,-,"governance 2.1",39
servicing_snapshots_2026q1.db,corrected_by_feed,T7,0,-,"governance 2.1",53
servicing_snapshots_2026q1.db,corrected_by_mail,T7,0,-,"governance 2.1",39
servicing_snapshots_2026q1.db,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",162
servicing_snapshots_2026q1.db,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",55
servicing_snapshots_2026q1.db,forborne_month,T14,0,-,"bad definition standard 3",302
servicing_snapshots_2026q1.db,int_padded,T9,0,-,"spec 4 conventions",139
servicing_snapshots_2026q1.db,int_signed_string,T4,0,-,"spec 4 conventions",148
servicing_snapshots_2026q1.db,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",102
servicing_snapshots_2026q1.db,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",106
servicing_snapshots_2026q1.db,month_compact,T3,0,-,"catalogue date and month notations",141
servicing_snapshots_2026q1.db,month_slash,T3,0,-,"catalogue date and month notations",138
servicing_snapshots_2026q1.db,quarantined_record,T6,0,-,"dq log",21
servicing_snapshots_2026q1.db,sqlite_balance_decimal_comma,T4,0,-,"catalogue",1
servicing_snapshots_2026q1.db,status_lowercase,T1,0,-,"spec 4 conventions",142
servicing_snapshots_2026q1.db,status_padded,T9,0,-,"spec 4 conventions",148
servicing_snapshots_2026q1.db,status_title,T1,0,-,"spec 4 conventions",147
servicing_snapshots_2026q1.db,tables_in_name_order,T8,0,-,"specification catalogue",1
servicing_snapshots_2026q1.db,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",160
snapshot_corrections_feed.xml,attributes_and_child_elements,T9,0,-,"specification catalogue",1
snapshot_corrections_feed.xml,control_element,T9,0,-,"specification catalogue",1
snapshot_corrections_feed.xml,int_padded,T9,0,-,"spec 4 conventions",20
snapshot_corrections_feed.xml,int_signed_string,T4,0,-,"spec 4 conventions",20
snapshot_corrections_feed.xml,key_homoglyph,T1,0,-,"spec 4 conventions",23
snapshot_corrections_feed.xml,key_hyphen,T1,0,-,"spec 4 conventions",21
snapshot_corrections_feed.xml,key_lower,T1,0,-,"spec 4 conventions",22
snapshot_corrections_feed.xml,key_nbsp,T10,0,-,"spec 4 conventions",22
snapshot_corrections_feed.xml,key_space,T1,0,-,"spec 4 conventions",20
snapshot_corrections_feed.xml,key_zero_pad,T1,0,-,"spec 4 conventions",18
snapshot_corrections_feed.xml,key_zwsp,T10,0,-,"spec 4 conventions",23
snapshot_corrections_feed.xml,month_compact,T3,0,-,"catalogue date and month notations",25
snapshot_corrections_feed.xml,month_slash,T3,0,-,"catalogue date and month notations",20
snapshot_corrections_feed.xml,seq_supersedes,T7,0,-,"governance 2.2",600
snapshot_corrections_feed.xml,xml_entities,T9,0,-,"spec 4 conventions",18
snapshot_corrections_feed.xml,xml_whitespace_text,T9,0,-,"spec 4 conventions",14
snapshots_2025_02.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_02.csv,corrected_by_errata,T7,0,-,"governance 2.1",7
snapshots_2025_02.csv,corrected_by_feed,T7,0,-,"governance 2.1",1
snapshots_2025_02.csv,corrected_by_mail,T7,0,-,"governance 2.1",1
snapshots_2025_02.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",158
snapshots_2025_02.csv,forborne_month,T14,0,-,"bad definition standard 3",34
snapshots_2025_02.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_02.csv,int_padded,T9,0,-,"spec 4 conventions",31
snapshots_2025_02.csv,int_signed_string,T4,0,-,"spec 4 conventions",33
snapshots_2025_02.csv,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",25
snapshots_2025_02.csv,key_lower,T1,0,-,"spec 3.1 key normalisation",23
snapshots_2025_02.csv,key_space,T1,0,-,"spec 3.1 key normalisation",22
snapshots_2025_02.csv,money_three_decimals,T12,0,-,"spec 4 conventions",28
snapshots_2025_02.csv,month_compact,T3,0,-,"catalogue date and month notations",29
snapshots_2025_02.csv,month_slash,T3,0,-,"catalogue date and month notations",34
snapshots_2025_02.csv,quarantined_record,T6,0,-,"dq log",7
snapshots_2025_02.csv,status_lowercase,T1,0,-,"spec 4 conventions",33
snapshots_2025_02.csv,status_padded,T9,0,-,"spec 4 conventions",36
snapshots_2025_02.csv,status_title,T1,0,-,"spec 4 conventions",33
snapshots_2025_02.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",93
snapshots_2025_03.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_03.tsv,corrected_by_errata,T7,0,-,"governance 2.1",1
snapshots_2025_03.tsv,corrected_by_feed,T7,0,-,"governance 2.1",5
snapshots_2025_03.tsv,corrected_by_mail,T7,0,-,"governance 2.1",5
snapshots_2025_03.tsv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",172
snapshots_2025_03.tsv,forborne_month,T14,0,-,"bad definition standard 3",75
snapshots_2025_03.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_03.tsv,int_signed_string,T4,0,-,"spec 4 conventions",52
snapshots_2025_03.tsv,key_hyphen,T1,0,-,"spec 3.1 key normalisation",45
snapshots_2025_03.tsv,key_nbsp,T10,0,-,"spec 3.1 key normalisation",44
snapshots_2025_03.tsv,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",40
snapshots_2025_03.tsv,month_compact,T3,0,-,"catalogue date and month notations",60
snapshots_2025_03.tsv,month_slash,T3,0,-,"catalogue date and month notations",56
snapshots_2025_03.tsv,period_compact_yyyymm,T3,0,-,"catalogue",1
snapshots_2025_03.tsv,quarantined_record,T6,0,-,"dq log",9
snapshots_2025_03.tsv,status_lowercase,T1,0,-,"spec 4 conventions",54
snapshots_2025_03.tsv,status_padded,T9,0,-,"spec 4 conventions",53
snapshots_2025_03.tsv,status_title,T1,0,-,"spec 4 conventions",54
snapshots_2025_03.tsv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
snapshots_2025_03.tsv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",121
snapshots_2025_04.parquet,balance_minor_units,T2,0,-,"catalogue",1
snapshots_2025_04.parquet,corrected_by_errata,T7,0,-,"governance 2.1",13
snapshots_2025_04.parquet,corrected_by_feed,T7,0,-,"governance 2.1",12
snapshots_2025_04.parquet,corrected_by_mail,T7,0,-,"governance 2.1",14
snapshots_2025_04.parquet,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",149
snapshots_2025_04.parquet,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",5
snapshots_2025_04.parquet,forborne_month,T14,0,-,"bad definition standard 3",136
snapshots_2025_04.parquet,key_lower,T1,0,-,"spec 3.1 key normalisation",63
snapshots_2025_04.parquet,key_space,T1,0,-,"spec 3.1 key normalisation",59
snapshots_2025_04.parquet,nullable_columns,T5,0,-,"specification catalogue",1
snapshots_2025_04.parquet,quarantined_record,T6,0,-,"dq log",7
snapshots_2025_04.parquet,row_groups_split,T9,0,-,"specification catalogue",1
snapshots_2025_04.parquet,status_lowercase,T1,0,-,"spec 4 conventions",79
snapshots_2025_04.parquet,status_padded,T9,0,-,"spec 4 conventions",80
snapshots_2025_04.parquet,status_title,T1,0,-,"spec 4 conventions",81
snapshots_2025_04.parquet,typed_integer_columns,T4,0,-,"specification catalogue",1
snapshots_2025_04.parquet,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",113
snapshots_2025_05.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
snapshots_2025_05.xlsx,corrected_by_errata,T7,0,-,"governance 2.1",18
snapshots_2025_05.xlsx,corrected_by_feed,T7,0,-,"governance 2.1",29
snapshots_2025_05.xlsx,corrected_by_mail,T7,0,-,"governance 2.1",35
snapshots_2025_05.xlsx,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",170
snapshots_2025_05.xlsx,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",20
snapshots_2025_05.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
snapshots_2025_05.xlsx,forborne_month,T14,0,-,"bad definition standard 3",176
snapshots_2025_05.xlsx,key_lower,T1,0,-,"spec 3.1 key normalisation",73
snapshots_2025_05.xlsx,key_space,T1,0,-,"spec 3.1 key normalisation",75
snapshots_2025_05.xlsx,period_excel_serial,T3,0,-,"catalogue",1
snapshots_2025_05.xlsx,quarantined_record,T6,0,-,"dq log",11
snapshots_2025_05.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
snapshots_2025_05.xlsx,sheet_column_order_differs,T8,0,-,"catalogue workbook layouts",1
snapshots_2025_05.xlsx,status_lowercase,T1,0,-,"spec 4 conventions",103
snapshots_2025_05.xlsx,status_padded,T9,0,-,"spec 4 conventions",105
snapshots_2025_05.xlsx,status_title,T1,0,-,"spec 4 conventions",101
snapshots_2025_05.xlsx,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",124
snapshots_2025_06_a.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_06_a.csv,corrected_by_errata,T7,0,-,"governance 2.1",23
snapshots_2025_06_a.csv,corrected_by_feed,T7,0,-,"governance 2.1",20
snapshots_2025_06_a.csv,corrected_by_mail,T7,0,-,"governance 2.1",23
snapshots_2025_06_a.csv,decimal_comma_balance,T4,0,-,"catalogue numeric conventions",1
snapshots_2025_06_a.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",154
snapshots_2025_06_a.csv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",16
snapshots_2025_06_a.csv,forborne_month,T14,0,-,"bad definition standard 3",150
snapshots_2025_06_a.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_06_a.csv,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",63
snapshots_2025_06_a.csv,key_space,T1,0,-,"spec 3.1 key normalisation",63
snapshots_2025_06_a.csv,key_zwsp,T10,0,-,"spec 3.1 key normalisation",61
snapshots_2025_06_a.csv,month_compact,T3,0,-,"catalogue date and month notations",78
snapshots_2025_06_a.csv,month_slash,T3,0,-,"catalogue date and month notations",82
snapshots_2025_06_a.csv,quarantined_record,T6,0,-,"dq log",12
snapshots_2025_06_a.csv,status_lowercase,T1,0,-,"spec 4 conventions",78
snapshots_2025_06_a.csv,status_padded,T9,0,-,"spec 4 conventions",82
snapshots_2025_06_a.csv,status_title,T1,0,-,"spec 4 conventions",76
snapshots_2025_06_a.csv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
snapshots_2025_06_a.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",122
snapshots_2025_06_b.jsonl,control_line_last,T9,0,-,"specification catalogue",1
snapshots_2025_06_b.jsonl,corrected_by_errata,T7,0,-,"governance 2.1",15
snapshots_2025_06_b.jsonl,corrected_by_feed,T7,0,-,"governance 2.1",20
snapshots_2025_06_b.jsonl,corrected_by_mail,T7,0,-,"governance 2.1",11
snapshots_2025_06_b.jsonl,dpd_as_string,T5,0,-,"catalogue",15
snapshots_2025_06_b.jsonl,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",154
snapshots_2025_06_b.jsonl,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",13
snapshots_2025_06_b.jsonl,forborne_month,T14,0,-,"bad definition standard 3",92
snapshots_2025_06_b.jsonl,int_signed_string,T4,0,-,"spec 4 conventions",62
snapshots_2025_06_b.jsonl,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",41
snapshots_2025_06_b.jsonl,key_lower,T1,0,-,"spec 3.1 key normalisation",44
snapshots_2025_06_b.jsonl,key_space,T1,0,-,"spec 3.1 key normalisation",48
snapshots_2025_06_b.jsonl,month_compact,T3,0,-,"catalogue date and month notations",59
snapshots_2025_06_b.jsonl,month_slash,T3,0,-,"catalogue date and month notations",58
snapshots_2025_06_b.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
snapshots_2025_06_b.jsonl,quarantined_record,T6,0,-,"dq log",13
snapshots_2025_06_b.jsonl,status_lowercase,T1,0,-,"spec 4 conventions",58
snapshots_2025_06_b.jsonl,status_padded,T9,0,-,"spec 4 conventions",61
snapshots_2025_06_b.jsonl,status_title,T1,0,-,"spec 4 conventions",63
snapshots_2025_06_b.jsonl,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",111
snapshots_2025_08_a.csv,balance_thousands_quoted,T4,0,-,"catalogue numeric conventions",22
snapshots_2025_08_a.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_08_a.csv,corrected_by_errata,T7,0,-,"governance 2.1",19
snapshots_2025_08_a.csv,corrected_by_feed,T7,0,-,"governance 2.1",32
snapshots_2025_08_a.csv,corrected_by_mail,T7,0,-,"governance 2.1",22
snapshots_2025_08_a.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",152
snapshots_2025_08_a.csv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",32
snapshots_2025_08_a.csv,forborne_month,T14,0,-,"bad definition standard 3",188
snapshots_2025_08_a.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_08_a.csv,header_reemitted_reordered,T8,0,-,"spec 4.2 re-emitted headers",1
snapshots_2025_08_a.csv,key_hyphen,T1,0,-,"spec 3.1 key normalisation",60
snapshots_2025_08_a.csv,key_lower,T1,0,-,"spec 3.1 key normalisation",72
snapshots_2025_08_a.csv,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",66
snapshots_2025_08_a.csv,month_compact,T3,0,-,"catalogue date and month notations",92
snapshots_2025_08_a.csv,quarantined_record,T6,0,-,"dq log",13
snapshots_2025_08_a.csv,status_lowercase,T1,0,-,"spec 4 conventions",93
snapshots_2025_08_a.csv,status_padded,T9,0,-,"spec 4 conventions",92
snapshots_2025_08_a.csv,status_title,T1,0,-,"spec 4 conventions",83
snapshots_2025_08_a.csv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
snapshots_2025_08_a.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",146
snapshots_2025_08_b.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_08_b.tsv,corrected_by_errata,T7,0,-,"governance 2.1",21
snapshots_2025_08_b.tsv,corrected_by_feed,T7,0,-,"governance 2.1",29
snapshots_2025_08_b.tsv,corrected_by_mail,T7,0,-,"governance 2.1",20
snapshots_2025_08_b.tsv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",167
snapshots_2025_08_b.tsv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",28
snapshots_2025_08_b.tsv,forborne_month,T14,0,-,"bad definition standard 3",125
snapshots_2025_08_b.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_08_b.tsv,header_reemitted_reordered,T8,0,-,"spec 4.2 re-emitted headers",1
snapshots_2025_08_b.tsv,int_signed_string,T4,0,-,"spec 4 conventions",69
snapshots_2025_08_b.tsv,key_nbsp,T10,0,-,"spec 3.1 key normalisation",50
snapshots_2025_08_b.tsv,key_space,T1,0,-,"spec 3.1 key normalisation",51
snapshots_2025_08_b.tsv,month_compact,T3,0,-,"catalogue date and month notations",74
snapshots_2025_08_b.tsv,month_slash,T3,0,-,"catalogue date and month notations",66
snapshots_2025_08_b.tsv,period_compact_yyyymm,T3,0,-,"catalogue",1
snapshots_2025_08_b.tsv,quarantined_record,T6,0,-,"dq log",6
snapshots_2025_08_b.tsv,status_lowercase,T1,0,-,"spec 4 conventions",71
snapshots_2025_08_b.tsv,status_padded,T9,0,-,"spec 4 conventions",72
snapshots_2025_08_b.tsv,status_title,T1,0,-,"spec 4 conventions",74
snapshots_2025_08_b.tsv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",122
snapshots_2025_09.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
snapshots_2025_09.xlsx,corrected_by_errata,T7,0,-,"governance 2.1",50
snapshots_2025_09.xlsx,corrected_by_feed,T7,0,-,"governance 2.1",60
snapshots_2025_09.xlsx,corrected_by_mail,T7,0,-,"governance 2.1",46
snapshots_2025_09.xlsx,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",189
snapshots_2025_09.xlsx,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",61
snapshots_2025_09.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
snapshots_2025_09.xlsx,forborne_month,T14,0,-,"bad definition standard 3",343
snapshots_2025_09.xlsx,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",118
snapshots_2025_09.xlsx,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",110
snapshots_2025_09.xlsx,period_excel_serial,T3,0,-,"catalogue",1
snapshots_2025_09.xlsx,quarantined_record,T6,0,-,"dq log",16
snapshots_2025_09.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
snapshots_2025_09.xlsx,sheet_column_order_differs,T8,0,-,"catalogue workbook layouts",1
snapshots_2025_09.xlsx,status_lowercase,T1,0,-,"spec 4 conventions",147
snapshots_2025_09.xlsx,status_padded,T9,0,-,"spec 4 conventions",148
snapshots_2025_09.xlsx,status_title,T1,0,-,"spec 4 conventions",147
snapshots_2025_09.xlsx,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",160
snapshots_2025_10_a.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_10_a.csv,corrected_by_errata,T7,0,-,"governance 2.1",27
snapshots_2025_10_a.csv,corrected_by_feed,T7,0,-,"governance 2.1",23
snapshots_2025_10_a.csv,corrected_by_mail,T7,0,-,"governance 2.1",22
snapshots_2025_10_a.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",142
snapshots_2025_10_a.csv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",41
snapshots_2025_10_a.csv,forborne_month,T14,0,-,"bad definition standard 3",220
snapshots_2025_10_a.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_10_a.csv,header_reemitted_reordered,T8,0,-,"spec 4.2 re-emitted headers",1
snapshots_2025_10_a.csv,int_signed_string,T4,0,-,"spec 4 conventions",87
snapshots_2025_10_a.csv,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",64
snapshots_2025_10_a.csv,key_lower,T1,0,-,"spec 3.1 key normalisation",67
snapshots_2025_10_a.csv,key_zwsp,T10,0,-,"spec 3.1 key normalisation",63
snapshots_2025_10_a.csv,month_compact,T3,0,-,"catalogue date and month notations",81
snapshots_2025_10_a.csv,month_slash,T3,0,-,"catalogue date and month notations",84
snapshots_2025_10_a.csv,quarantined_record,T6,0,-,"dq log",2
snapshots_2025_10_a.csv,status_lowercase,T1,0,-,"spec 4 conventions",88
snapshots_2025_10_a.csv,status_padded,T9,0,-,"spec 4 conventions",90
snapshots_2025_10_a.csv,status_title,T1,0,-,"spec 4 conventions",87
snapshots_2025_10_a.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",125
snapshots_2025_10_b.tsv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_10_b.tsv,corrected_by_errata,T7,0,-,"governance 2.1",25
snapshots_2025_10_b.tsv,corrected_by_feed,T7,0,-,"governance 2.1",28
snapshots_2025_10_b.tsv,corrected_by_mail,T7,0,-,"governance 2.1",16
snapshots_2025_10_b.tsv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",148
snapshots_2025_10_b.tsv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",29
snapshots_2025_10_b.tsv,forborne_month,T14,0,-,"bad definition standard 3",151
snapshots_2025_10_b.tsv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_10_b.tsv,key_space,T1,0,-,"spec 3.1 key normalisation",50
snapshots_2025_10_b.tsv,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",49
snapshots_2025_10_b.tsv,month_compact,T3,0,-,"catalogue date and month notations",66
snapshots_2025_10_b.tsv,month_slash,T3,0,-,"catalogue date and month notations",72
snapshots_2025_10_b.tsv,period_compact_yyyymm,T3,0,-,"catalogue",1
snapshots_2025_10_b.tsv,quarantined_record,T6,0,-,"dq log",6
snapshots_2025_10_b.tsv,status_lowercase,T1,0,-,"spec 4 conventions",61
snapshots_2025_10_b.tsv,status_padded,T9,0,-,"spec 4 conventions",75
snapshots_2025_10_b.tsv,status_title,T1,0,-,"spec 4 conventions",66
snapshots_2025_10_b.tsv,system_error_voided,T6,0,-,"governance 3.12",314
snapshots_2025_10_b.tsv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
snapshots_2025_10_b.tsv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",117
snapshots_2025_10_b_restated.tsv,comment_lines_hash,T9,1,-,"specification catalogue",1
snapshots_2025_10_b_restated.tsv,copy_value_drift,T16,1,pull,"",703
snapshots_2025_10_b_restated.tsv,dpd_not_reported_sentinel,T5,1,-,"catalogue sentinel table",148
snapshots_2025_10_b_restated.tsv,dpd_written_off_sentinel,T5,1,-,"bad definition standard 2.3",29
snapshots_2025_10_b_restated.tsv,header_names_differ_by_file,T8,1,-,"specification catalogue",1
snapshots_2025_10_b_restated.tsv,header_references_certified_delivery,T13,1,push,"governance policy",1
snapshots_2025_10_b_restated.tsv,int_padded,T9,1,-,"spec 4 conventions",68
snapshots_2025_10_b_restated.tsv,int_signed_string,T4,1,-,"spec 4 conventions",70
snapshots_2025_10_b_restated.tsv,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",49
snapshots_2025_10_b_restated.tsv,key_hyphen,T1,1,-,"spec 3.1 key normalisation",53
snapshots_2025_10_b_restated.tsv,key_lower,T1,1,-,"spec 3.1 key normalisation",54
snapshots_2025_10_b_restated.tsv,key_nbsp,T10,1,-,"spec 3.1 key normalisation",50
snapshots_2025_10_b_restated.tsv,key_space,T1,1,-,"spec 3.1 key normalisation",51
snapshots_2025_10_b_restated.tsv,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",50
snapshots_2025_10_b_restated.tsv,key_zwsp,T10,1,-,"spec 3.1 key normalisation",52
snapshots_2025_10_b_restated.tsv,money_comma,T4,1,-,"spec 4 conventions",72
snapshots_2025_10_b_restated.tsv,money_thousands,T4,1,-,"spec 4 conventions",71
snapshots_2025_10_b_restated.tsv,money_three_decimals,T12,1,-,"spec 4 conventions",75
snapshots_2025_10_b_restated.tsv,month_compact,T3,1,-,"catalogue date and month notations",69
snapshots_2025_10_b_restated.tsv,month_slash,T3,1,-,"catalogue date and month notations",66
snapshots_2025_10_b_restated.tsv,period_compact_yyyymm,T3,1,-,"catalogue",1
snapshots_2025_10_b_restated.tsv,quarantined_record,T6,1,-,"dq log",2
snapshots_2025_10_b_restated.tsv,restated_values_newer,T16,1,pull,"governance policy",1
snapshots_2025_10_b_restated.tsv,restatement_header_comment,T14,1,push,"governance policy",1
snapshots_2025_10_b_restated.tsv,restatement_supersedes_claim,T7,1,pull,"governance policy",1
snapshots_2025_10_b_restated.tsv,status_lowercase,T1,1,-,"spec 4 conventions",67
snapshots_2025_10_b_restated.tsv,status_padded,T9,1,-,"spec 4 conventions",68
snapshots_2025_10_b_restated.tsv,status_title,T1,1,-,"spec 4 conventions",72
snapshots_2025_10_b_restated.tsv,system_error_only_evidence,T6,1,push,"governance policy",1
snapshots_2025_10_b_restated.tsv,within_file_duplicate_later_wins,T7,1,-,"spec 5.2 later record wins",117
snapshots_2025_11_a.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2025_11_a.csv,corrected_by_errata,T7,0,-,"governance 2.1",26
snapshots_2025_11_a.csv,corrected_by_feed,T7,0,-,"governance 2.1",30
snapshots_2025_11_a.csv,corrected_by_mail,T7,0,-,"governance 2.1",38
snapshots_2025_11_a.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",189
snapshots_2025_11_a.csv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",33
snapshots_2025_11_a.csv,forborne_month,T14,0,-,"bad definition standard 3",167
snapshots_2025_11_a.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2025_11_a.csv,int_padded,T9,0,-,"spec 4 conventions",71
snapshots_2025_11_a.csv,int_signed_string,T4,0,-,"spec 4 conventions",74
snapshots_2025_11_a.csv,key_nbsp,T10,0,-,"spec 3.1 key normalisation",56
snapshots_2025_11_a.csv,key_space,T1,0,-,"spec 3.1 key normalisation",53
snapshots_2025_11_a.csv,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",58
snapshots_2025_11_a.csv,month_compact,T3,0,-,"catalogue date and month notations",74
snapshots_2025_11_a.csv,month_slash,T3,0,-,"catalogue date and month notations",76
snapshots_2025_11_a.csv,quarantined_record,T6,0,-,"dq log",8
snapshots_2025_11_a.csv,status_lowercase,T1,0,-,"spec 4 conventions",77
snapshots_2025_11_a.csv,status_padded,T9,0,-,"spec 4 conventions",74
snapshots_2025_11_a.csv,status_title,T1,0,-,"spec 4 conventions",67
snapshots_2025_11_a.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",97
snapshots_2025_11_a_rev2.csv,certified_only_for_cz,T13,1,push,"spec 5.1",3262
snapshots_2025_11_a_rev2.csv,comment_lines_hash,T9,1,-,"specification catalogue",1
snapshots_2025_11_a_rev2.csv,copy_value_drift,T16,1,pull,"",586
snapshots_2025_11_a_rev2.csv,corrected_by_errata,T7,1,-,"governance 2.1",4
snapshots_2025_11_a_rev2.csv,corrected_by_feed,T7,1,-,"governance 2.1",7
snapshots_2025_11_a_rev2.csv,corrected_by_mail,T7,1,-,"governance 2.1",1
snapshots_2025_11_a_rev2.csv,dpd_not_reported_sentinel,T5,1,-,"catalogue sentinel table",7
snapshots_2025_11_a_rev2.csv,dpd_written_off_sentinel,T5,1,-,"bad definition standard 2.3",33
snapshots_2025_11_a_rev2.csv,final_label_header,T16,1,pull,"governance policy",1
snapshots_2025_11_a_rev2.csv,forborne_month,T14,1,-,"bad definition standard 3",31
snapshots_2025_11_a_rev2.csv,header_names_differ_by_file,T8,1,-,"specification catalogue",1
snapshots_2025_11_a_rev2.csv,int_padded,T9,1,-,"spec 4 conventions",83
snapshots_2025_11_a_rev2.csv,int_signed_string,T4,1,-,"spec 4 conventions",82
snapshots_2025_11_a_rev2.csv,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",61
snapshots_2025_11_a_rev2.csv,key_hyphen,T1,1,-,"spec 3.1 key normalisation",57
snapshots_2025_11_a_rev2.csv,key_lower,T1,1,-,"spec 3.1 key normalisation",57
snapshots_2025_11_a_rev2.csv,key_nbsp,T10,1,-,"spec 3.1 key normalisation",59
snapshots_2025_11_a_rev2.csv,key_space,T1,1,-,"spec 3.1 key normalisation",61
snapshots_2025_11_a_rev2.csv,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",52
snapshots_2025_11_a_rev2.csv,key_zwsp,T10,1,-,"spec 3.1 key normalisation",65
snapshots_2025_11_a_rev2.csv,money_thousands,T4,1,-,"spec 4 conventions",79
snapshots_2025_11_a_rev2.csv,money_three_decimals,T12,1,-,"spec 4 conventions",78
snapshots_2025_11_a_rev2.csv,month_compact,T3,1,-,"catalogue date and month notations",75
snapshots_2025_11_a_rev2.csv,month_slash,T3,1,-,"catalogue date and month notations",77
snapshots_2025_11_a_rev2.csv,quarantined_record,T6,1,-,"dq log",2
snapshots_2025_11_a_rev2.csv,revision_number_newer,T7,1,pull,"governance policy",1
snapshots_2025_11_a_rev2.csv,scope_set_by_manifest_comment,T14,1,push,"governance policy",1
snapshots_2025_11_a_rev2.csv,status_lowercase,T1,1,-,"spec 4 conventions",80
snapshots_2025_11_a_rev2.csv,status_padded,T9,1,-,"spec 4 conventions",81
snapshots_2025_11_a_rev2.csv,status_title,T1,1,-,"spec 4 conventions",71
snapshots_2025_11_b.parquet,balance_minor_units,T2,0,-,"catalogue",1
snapshots_2025_11_b.parquet,corrected_by_errata,T7,0,-,"governance 2.1",18
snapshots_2025_11_b.parquet,corrected_by_feed,T7,0,-,"governance 2.1",25
snapshots_2025_11_b.parquet,corrected_by_mail,T7,0,-,"governance 2.1",24
snapshots_2025_11_b.parquet,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",163
snapshots_2025_11_b.parquet,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",30
snapshots_2025_11_b.parquet,forborne_month,T14,0,-,"bad definition standard 3",152
snapshots_2025_11_b.parquet,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",59
snapshots_2025_11_b.parquet,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",54
snapshots_2025_11_b.parquet,nullable_columns,T5,0,-,"specification catalogue",1
snapshots_2025_11_b.parquet,quarantined_record,T6,0,-,"dq log",10
snapshots_2025_11_b.parquet,row_groups_split,T9,0,-,"specification catalogue",1
snapshots_2025_11_b.parquet,status_lowercase,T1,0,-,"spec 4 conventions",67
snapshots_2025_11_b.parquet,status_padded,T9,0,-,"spec 4 conventions",69
snapshots_2025_11_b.parquet,status_title,T1,0,-,"spec 4 conventions",71
snapshots_2025_11_b.parquet,typed_integer_columns,T4,0,-,"specification catalogue",1
snapshots_2025_11_b.parquet,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",89
snapshots_2025_12.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
snapshots_2025_12.xlsx,corrected_by_errata,T7,0,-,"governance 2.1",45
snapshots_2025_12.xlsx,corrected_by_feed,T7,0,-,"governance 2.1",66
snapshots_2025_12.xlsx,corrected_by_mail,T7,0,-,"governance 2.1",60
snapshots_2025_12.xlsx,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",138
snapshots_2025_12.xlsx,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",70
snapshots_2025_12.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
snapshots_2025_12.xlsx,forborne_month,T14,0,-,"bad definition standard 3",328
snapshots_2025_12.xlsx,key_hyphen,T1,0,-,"spec 3.1 key normalisation",109
snapshots_2025_12.xlsx,key_zwsp,T10,0,-,"spec 3.1 key normalisation",110
snapshots_2025_12.xlsx,period_excel_serial,T3,0,-,"catalogue",1
snapshots_2025_12.xlsx,quarantined_record,T6,0,-,"dq log",16
snapshots_2025_12.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
snapshots_2025_12.xlsx,sheet_column_order_differs,T8,0,-,"catalogue workbook layouts",1
snapshots_2025_12.xlsx,status_lowercase,T1,0,-,"spec 4 conventions",152
snapshots_2025_12.xlsx,status_padded,T9,0,-,"spec 4 conventions",146
snapshots_2025_12.xlsx,status_title,T1,0,-,"spec 4 conventions",141
snapshots_2025_12.xlsx,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",176
snapshots_2026_02_a.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2026_02_a.csv,corrected_by_errata,T7,0,-,"governance 2.1",18
snapshots_2026_02_a.csv,corrected_by_feed,T7,0,-,"governance 2.1",23
snapshots_2026_02_a.csv,corrected_by_mail,T7,0,-,"governance 2.1",20
snapshots_2026_02_a.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",156
snapshots_2026_02_a.csv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",30
snapshots_2026_02_a.csv,forborne_month,T14,0,-,"bad definition standard 3",132
snapshots_2026_02_a.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2026_02_a.csv,header_reemitted_reordered,T8,0,-,"spec 4.2 re-emitted headers",1
snapshots_2026_02_a.csv,key_homoglyph,T1,0,-,"spec 3.1 key normalisation",55
snapshots_2026_02_a.csv,key_lower,T1,0,-,"spec 3.1 key normalisation",57
snapshots_2026_02_a.csv,key_space,T1,0,-,"spec 3.1 key normalisation",52
snapshots_2026_02_a.csv,month_compact,T3,0,-,"catalogue date and month notations",70
snapshots_2026_02_a.csv,month_slash,T3,0,-,"catalogue date and month notations",76
snapshots_2026_02_a.csv,negative_in_parentheses,T4,0,-,"catalogue numeric conventions",1
snapshots_2026_02_a.csv,quarantined_record,T6,0,-,"dq log",5
snapshots_2026_02_a.csv,status_lowercase,T1,0,-,"spec 4 conventions",72
snapshots_2026_02_a.csv,status_padded,T9,0,-,"spec 4 conventions",76
snapshots_2026_02_a.csv,status_title,T1,0,-,"spec 4 conventions",72
snapshots_2026_02_a.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",114
snapshots_2026_02_b.jsonl,control_line_last,T9,0,-,"specification catalogue",1
snapshots_2026_02_b.jsonl,corrected_by_errata,T7,0,-,"governance 2.1",19
snapshots_2026_02_b.jsonl,corrected_by_feed,T7,0,-,"governance 2.1",17
snapshots_2026_02_b.jsonl,corrected_by_mail,T7,0,-,"governance 2.1",13
snapshots_2026_02_b.jsonl,dpd_as_string,T5,0,-,"catalogue",8
snapshots_2026_02_b.jsonl,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",176
snapshots_2026_02_b.jsonl,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",25
snapshots_2026_02_b.jsonl,forborne_month,T14,0,-,"bad definition standard 3",111
snapshots_2026_02_b.jsonl,int_signed_string,T4,0,-,"spec 4 conventions",60
snapshots_2026_02_b.jsonl,key_hyphen,T1,0,-,"spec 3.1 key normalisation",44
snapshots_2026_02_b.jsonl,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",44
snapshots_2026_02_b.jsonl,key_zwsp,T10,0,-,"spec 3.1 key normalisation",46
snapshots_2026_02_b.jsonl,month_compact,T3,0,-,"catalogue date and month notations",57
snapshots_2026_02_b.jsonl,month_slash,T3,0,-,"catalogue date and month notations",53
snapshots_2026_02_b.jsonl,numbers_or_strings,T4,0,-,"specification catalogue",1
snapshots_2026_02_b.jsonl,quarantined_record,T6,0,-,"dq log",6
snapshots_2026_02_b.jsonl,status_lowercase,T1,0,-,"spec 4 conventions",57
snapshots_2026_02_b.jsonl,status_padded,T9,0,-,"spec 4 conventions",55
snapshots_2026_02_b.jsonl,status_title,T1,0,-,"spec 4 conventions",57
snapshots_2026_02_b.jsonl,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",89
snapshots_2026_03.xlsx,blank_cells_omitted,T5,0,-,"specification catalogue",1
snapshots_2026_03.xlsx,corrected_by_errata,T7,0,-,"governance 2.1",24
snapshots_2026_03.xlsx,corrected_by_feed,T7,0,-,"governance 2.1",33
snapshots_2026_03.xlsx,corrected_by_mail,T7,0,-,"governance 2.1",39
snapshots_2026_03.xlsx,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",154
snapshots_2026_03.xlsx,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",41
snapshots_2026_03.xlsx,excel_1900_date_system,T3,0,-,"specification catalogue",1
snapshots_2026_03.xlsx,forborne_month,T14,0,-,"bad definition standard 3",172
snapshots_2026_03.xlsx,key_lower,T1,0,-,"spec 3.1 key normalisation",72
snapshots_2026_03.xlsx,key_nbsp,T10,0,-,"spec 3.1 key normalisation",75
snapshots_2026_03.xlsx,key_space,T1,0,-,"spec 3.1 key normalisation",80
snapshots_2026_03.xlsx,period_excel_serial,T3,0,-,"catalogue",1
snapshots_2026_03.xlsx,quarantined_record,T6,0,-,"dq log",8
snapshots_2026_03.xlsx,shared_strings_table,T8,0,-,"specification catalogue",1
snapshots_2026_03.xlsx,sheet_column_order_differs,T8,0,-,"catalogue workbook layouts",1
snapshots_2026_03.xlsx,status_lowercase,T1,0,-,"spec 4 conventions",99
snapshots_2026_03.xlsx,status_padded,T9,0,-,"spec 4 conventions",94
snapshots_2026_03.xlsx,status_title,T1,0,-,"spec 4 conventions",99
snapshots_2026_03.xlsx,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",133
snapshots_2026_04.txt,corrected_by_errata,T7,0,-,"governance 2.1",26
snapshots_2026_04.txt,corrected_by_feed,T7,0,-,"governance 2.1",18
snapshots_2026_04.txt,corrected_by_mail,T7,0,-,"governance 2.1",28
snapshots_2026_04.txt,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",167
snapshots_2026_04.txt,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",45
snapshots_2026_04.txt,forborne_month,T14,0,-,"bad definition standard 3",118
snapshots_2026_04.txt,fw_balance_signed_minor,T2,0,-,"catalogue fixed width",1
snapshots_2026_04.txt,fw_dpd_9999_not_reported,T5,0,-,"catalogue fixed width",1
snapshots_2026_04.txt,key_hyphen,T1,0,-,"spec 3.1 key normalisation",55
snapshots_2026_04.txt,key_lower,T1,0,-,"spec 3.1 key normalisation",60
snapshots_2026_04.txt,key_zero_pad,T1,0,-,"spec 3.1 key normalisation",57
snapshots_2026_04.txt,latin1_encoding,T10,0,-,"specification catalogue",1
snapshots_2026_04.txt,quarantined_record,T6,0,-,"dq log",7
snapshots_2026_04.txt,record_type_codes,T8,0,-,"specification catalogue",1
snapshots_2026_04.txt,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",113
snapshots_2026_05_a.parquet,balance_minor_units,T2,0,-,"catalogue",1
snapshots_2026_05_a.parquet,corrected_by_errata,T7,0,-,"governance 2.1",10
snapshots_2026_05_a.parquet,corrected_by_feed,T7,0,-,"governance 2.1",9
snapshots_2026_05_a.parquet,corrected_by_mail,T7,0,-,"governance 2.1",10
snapshots_2026_05_a.parquet,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",147
snapshots_2026_05_a.parquet,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",13
snapshots_2026_05_a.parquet,forborne_month,T14,0,-,"bad definition standard 3",42
snapshots_2026_05_a.parquet,key_hyphen,T1,0,-,"spec 3.1 key normalisation",27
snapshots_2026_05_a.parquet,key_nbsp,T10,0,-,"spec 3.1 key normalisation",28
snapshots_2026_05_a.parquet,nullable_columns,T5,0,-,"specification catalogue",1
snapshots_2026_05_a.parquet,quarantined_record,T6,0,-,"dq log",9
snapshots_2026_05_a.parquet,row_groups_split,T9,0,-,"specification catalogue",1
snapshots_2026_05_a.parquet,status_lowercase,T1,0,-,"spec 4 conventions",36
snapshots_2026_05_a.parquet,status_padded,T9,0,-,"spec 4 conventions",35
snapshots_2026_05_a.parquet,status_title,T1,0,-,"spec 4 conventions",33
snapshots_2026_05_a.parquet,typed_integer_columns,T4,0,-,"specification catalogue",1
snapshots_2026_05_a.parquet,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",88
snapshots_2026_05_b.txt,corrected_by_errata,T7,0,-,"governance 2.1",6
snapshots_2026_05_b.txt,corrected_by_feed,T7,0,-,"governance 2.1",10
snapshots_2026_05_b.txt,corrected_by_mail,T7,0,-,"governance 2.1",7
snapshots_2026_05_b.txt,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",154
snapshots_2026_05_b.txt,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",11
snapshots_2026_05_b.txt,forborne_month,T14,0,-,"bad definition standard 3",21
snapshots_2026_05_b.txt,fw_balance_signed_minor,T2,0,-,"catalogue fixed width",1
snapshots_2026_05_b.txt,fw_dpd_9999_not_reported,T5,0,-,"catalogue fixed width",1
snapshots_2026_05_b.txt,key_hyphen,T1,0,-,"spec 3.1 key normalisation",23
snapshots_2026_05_b.txt,key_lower,T1,0,-,"spec 3.1 key normalisation",23
snapshots_2026_05_b.txt,latin1_encoding,T10,0,-,"specification catalogue",1
snapshots_2026_05_b.txt,quarantined_record,T6,0,-,"dq log",7
snapshots_2026_05_b.txt,record_type_codes,T8,0,-,"specification catalogue",1
snapshots_2026_05_b.txt,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",78
snapshots_2026_06.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
snapshots_2026_06.csv,corrected_by_errata,T7,0,-,"governance 2.1",11
snapshots_2026_06.csv,corrected_by_feed,T7,0,-,"governance 2.1",8
snapshots_2026_06.csv,corrected_by_mail,T7,0,-,"governance 2.1",15
snapshots_2026_06.csv,dpd_not_reported_sentinel,T5,0,-,"catalogue sentinel table",168
snapshots_2026_06.csv,dpd_written_off_sentinel,T5,0,-,"bad definition standard 2.3",17
snapshots_2026_06.csv,forborne_month,T14,0,-,"bad definition standard 3",34
snapshots_2026_06.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
snapshots_2026_06.csv,int_signed_string,T4,0,-,"spec 4 conventions",29
snapshots_2026_06.csv,key_hyphen,T1,0,-,"spec 3.1 key normalisation",23
snapshots_2026_06.csv,key_nbsp,T10,0,-,"spec 3.1 key normalisation",24
snapshots_2026_06.csv,key_zwsp,T10,0,-,"spec 3.1 key normalisation",29
snapshots_2026_06.csv,month_compact,T3,0,-,"catalogue date and month notations",31
snapshots_2026_06.csv,month_slash,T3,0,-,"catalogue date and month notations",33
snapshots_2026_06.csv,quarantined_record,T6,0,-,"dq log",6
snapshots_2026_06.csv,status_lowercase,T1,0,-,"spec 4 conventions",32
snapshots_2026_06.csv,status_padded,T9,0,-,"spec 4 conventions",34
snapshots_2026_06.csv,status_title,T1,0,-,"spec 4 conventions",32
snapshots_2026_06.csv,utf8_bom,T10,0,-,"spec 4.2 encodings",1
snapshots_2026_06.csv,within_file_duplicate_later_wins,T7,0,-,"spec 5.2 later record wins",86
snapshots_servicing_replica.db,balance_text_point,T4,1,-,"governance 1.3",1
snapshots_servicing_replica.db,control_in_view,T9,1,-,"specification catalogue",1
snapshots_servicing_replica.db,control_value_text,T4,1,-,"governance 1.3",1
snapshots_servicing_replica.db,copy_value_drift,T16,1,pull,"",4654
snapshots_servicing_replica.db,cycle_controls_history,T7,1,-,"governance 1.3",1
snapshots_servicing_replica.db,cycle_controls_only_copy,T13,1,push,"governance 1.3",1
snapshots_servicing_replica.db,cycle_controls_segment_all,T15,1,-,"governance policy",1
snapshots_servicing_replica.db,dpd_minus_one,T5,1,-,"governance 1.3",1
snapshots_servicing_replica.db,excluded_accounts_hash,T13,1,push,"governance policy",1
snapshots_servicing_replica.db,key_homoglyph,T1,1,-,"spec 3.1 key normalisation",364
snapshots_servicing_replica.db,key_hyphen,T1,1,-,"spec 3.1 key normalisation",352
snapshots_servicing_replica.db,key_lower,T1,1,-,"spec 3.1 key normalisation",364
snapshots_servicing_replica.db,key_nbsp,T10,1,-,"spec 3.1 key normalisation",360
snapshots_servicing_replica.db,key_space,T1,1,-,"spec 3.1 key normalisation",371
snapshots_servicing_replica.db,key_zero_pad,T1,1,-,"spec 3.1 key normalisation",362
snapshots_servicing_replica.db,key_zwsp,T10,1,-,"spec 3.1 key normalisation",368
snapshots_servicing_replica.db,metric_names_suffixed,T8,1,-,"governance 1.3",1
snapshots_servicing_replica.db,month_compact@period,T3,1,-,"catalogue date and month notations",473
snapshots_servicing_replica.db,month_slash@period,T3,1,-,"catalogue date and month notations",485
snapshots_servicing_replica.db,replica_balance_differs,T16,1,pull,"governance policy",1
snapshots_servicing_replica.db,replica_complete_months,T16,1,pull,"governance 1.3",1
snapshots_servicing_replica.db,replica_months_outside_certification,T11,1,-,"governance 1.3",1
snapshots_servicing_replica.db,replica_not_value_source,T14,1,push,"governance 1.3",1
snapshots_servicing_replica.db,replica_rows_of_closed_accounts,T6,1,-,"governance policy",1
snapshots_servicing_replica.db,status_lowercase@status,T1,1,-,"spec 4 conventions",477
snapshots_servicing_replica.db,status_padded@status,T9,1,-,"spec 4 conventions",490
snapshots_servicing_replica.db,status_title@status,T1,1,-,"spec 4 conventions",493
snapshots_servicing_replica.db,tables_in_name_order,T8,1,-,"specification catalogue",1
status_events_chargeoff_2025.csv,chargeoff_in_window,T11,0,-,"bad definition standard 2.4",784
status_events_chargeoff_2025.csv,chargeoff_reversed_elsewhere,T6,0,-,"bad definition standard 2.4",109
status_events_chargeoff_2025.csv,comment_lines_hash,T9,0,-,"specification catalogue",1
status_events_chargeoff_2025.csv,csv_quoted_delimiter,T9,0,-,"spec 4 conventions",15
status_events_chargeoff_2025.csv,csv_reemitted_header,T8,0,-,"spec 2.2 and 4",1
status_events_chargeoff_2025.csv,csv_utf8_bom,T10,0,-,"spec 2.2 and 4",1
status_events_chargeoff_2025.csv,date_compact,T3,0,-,"catalogue date and month notations",19
status_events_chargeoff_2025.csv,date_dmy_dot,T3,0,-,"catalogue date and month notations",20
status_events_chargeoff_2025.csv,date_dmy_slash,T3,0,-,"catalogue date and month notations",20
status_events_chargeoff_2025.csv,header_names_differ_by_file,T8,0,-,"specification catalogue",1
status_events_chargeoff_2025.csv,id_lower,T1,0,-,"spec 4 conventions",18
status_events_chargeoff_2025.csv,id_padded,T9,0,-,"spec 4 conventions",22
status_events_chargeoff_2025.csv,key_homoglyph,T1,0,-,"spec 4 conventions",19
status_events_chargeoff_2025.csv,key_lower,T1,0,-,"spec 4 conventions",22
status_events_chargeoff_2025.csv,key_space,T1,0,-,"spec 4 conventions",21
status_events_chargeoff_2025.csv,money_thousands,T4,0,-,"spec 4 conventions",20
status_events_chargeoff_2025.csv,money_three_decimals,T12,0,-,"spec 4 conventions",23
status_events_consolidated.json,branch_notice_deceased_not_authoritative,T6,1,-,"governance policy",1
status_events_consolidated.json,chargeoff_copies_agree,T16,1,pull,"governance policy",1
status_events_consolidated.json,chargeoff_reversed,T6,1,push,"bad definition standard 2.4",215
status_events_consolidated.json,civil_registry_authoritative,T13,1,push,"governance 3.11",29
status_events_consolidated.json,control_object_last,T9,1,-,"specification catalogue",1
status_events_consolidated.json,cust_homoglyph@subject,T1,1,-,"spec 4 conventions",110
status_events_consolidated.json,cust_lower@subject,T1,1,-,"spec 4 conventions",111
status_events_consolidated.json,cust_space@subject,T1,1,-,"spec 4 conventions",105
status_events_consolidated.json,cust_zero_pad@subject,T1,1,-,"spec 4 conventions",119
status_events_consolidated.json,cust_zwsp@subject,T10,1,-,"spec 4 conventions",102
status_events_consolidated.json,date_compact@date,T3,1,-,"catalogue date and month notations",108
status_events_consolidated.json,date_dmy_dot@date,T3,1,-,"catalogue date and month notations",113
status_events_consolidated.json,date_dmy_slash@date,T3,1,-,"catalogue date and month notations",105
status_events_consolidated.json,fraud_alert_without_disposition,T16,1,pull,"exclusion policy 2.6",1155
status_events_consolidated.json,generated_timestamp_newest,T16,1,pull,"governance policy",1
status_events_consolidated.json,id_lower@ref,T1,1,-,"spec 4 conventions",107
status_events_consolidated.json,id_padded@ref,T9,1,-,"spec 4 conventions",107
status_events_consolidated.json,json_null_field,T5,1,-,"spec 4 conventions",82
status_events_consolidated.json,json_unicode_escapes,T10,1,-,"spec 4 conventions",84
status_events_consolidated.json,records_under_named_key,T8,1,-,"specification catalogue",1
status_events_consolidated.json,reversal_supersedes_chargeoff,T7,1,push,"governance policy",1
status_events_consolidated.json,scope_declared_in_metadata,T14,1,push,"governance policy",1
status_events_consolidated.json,status_lowercase@source,T1,1,-,"spec 4 conventions",112
status_events_consolidated.json,status_lowercase@type,T1,1,-,"spec 4 conventions",110
status_events_consolidated.json,status_padded@source,T9,1,-,"spec 4 conventions",103
status_events_consolidated.json,status_padded@type,T9,1,-,"spec 4 conventions",109
status_events_consolidated.json,status_title@source,T1,1,-,"spec 4 conventions",104
status_events_consolidated.json,status_title@type,T1,1,-,"spec 4 conventions",104
treasury_fixings_2024_2026.xml,attributes_and_child_elements,T9,0,-,"specification catalogue",1
treasury_fixings_2024_2026.xml,ccy_lowercase,T1,0,-,"limit policy 4.4",26
treasury_fixings_2024_2026.xml,cdata_value,T9,0,-,"catalogue",1
treasury_fixings_2024_2026.xml,control_element,T9,0,-,"specification catalogue",1
treasury_fixings_2024_2026.xml,fixing_revision,T7,0,-,"limit policy 4.4",33
treasury_fixings_2024_2026.xml,huf_per_100,T2,0,-,"limit policy 4.4",1
treasury_fixings_2024_2026.xml,month_end_fixing,T11,0,-,"limit policy 4.3",148
treasury_fixings_2024_2026.xml,per_omitted,T5,0,-,"limit policy 4.4",27
treasury_fixings_2024_2026.xml,publication_gap,T15,0,-,"limit policy 4.4 as-of",5
treasury_fixings_2024_2026.xml,rev_omitted,T5,0,-,"limit policy 4.4",26
treasury_fixings_2024_2026.xml,value_decimal_comma,T4,0,-,"limit policy 4.4",28
treasury_fixings_2024_2026.xml,value_padded,T9,0,-,"limit policy 4.4",25
treasury_fixings_2024_2026.xml,xml_comments,T9,0,-,"catalogue",1
```

## Provenance

```yaml
uuid: dad47963-3ef5-569b-9c83-dcf0fa4ffb57
instance_id: dad47963-3ef5-569b-9c83-dcf0fa4ffb57
task_name: terminal-bench/dad47963-3ef5-569b-9c83-dcf0fa4ffb57
fix_patch_sha256: d0b37eea6aa136303dbea6cca77bf2a14016499c0bd7d5926a93d3154eeb92f2  # sha256 of solution/solve.sh
solve_py_sha256: 8c6206abc4daaf86b3244d0710619875d8bfdc92819f5f1b1c75dae4cd64ce89  # informational; solve.py is 1903 lines
language: python
golden_score_measured: null
golden_score_runs: 0
golden_score_note: >
  Oracle, nop and stub scores are recorded only from the Step 10 runs on the
  tests-only copy and cover the test channel in tests/test_output.py only; the
  judged channel has no oracle score.
caveat: >
  The test channel carries 27 positive checks worth 93 weight and 4 negative
  checks worth -18 weight, so on its own it ranges -18/93 = -0.194 to +1.000.
  The judged channel carries 10 criteria worth 19 positive and -13 negative
  points, -13/19 = -0.684 to +1.000 on its own. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward runs from -0.439 to +1.000 with no clamp.
```
