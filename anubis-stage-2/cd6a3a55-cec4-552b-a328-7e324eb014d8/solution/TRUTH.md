# TRUTH.md - cd6a3a55-cec4-552b-a328-7e324eb014d8

## Defect

`/app/repo` holds the Helios close program (`src/helios_close`, seven modules plus `tools/amalgamate.py`). It reads the fifty exports of the Q3 2025 training-component exposure close in `/app/data` and resolves three logical layers plus six evidence views in memory during one run. The shipped program reads every export but implements 64 rules of `close_contract.md` and the documents it names the tempting wrong way. None of the defects is marked in the source: each is ordinary-looking code that a reader finds only by comparing it with the documented rule. The published control figures cover teams, exports and global totals only, so most defects are invisible to the control reconciliation, and four (`policy_hardcoded`, `decode_errors_swallowed`, `xwalk_window_inclusive` and the whole-minute half of `hours_min_as_h`) do not show on the shipped corpus at all. Its output disagrees with the published control figures in `control_totals.html`, with the custody counts, and with the ground truth. The agent must find and repair every defect and deliver twenty-four data artifacts plus `/app/out/build.py`. The reusable program is also run on an unseen corpus.

Each defect below names the documented rule it breaks and the checks that fail while it is present.

1. (focal) `rename_unconfirmed`: a rename alias of `name_aliases.tsv` merges the former name even without a rename notice in `yank_notices.mbox` (contract 7.2); the shipped loop maps every alias kind with no condition. Fails `p1_packages_releases`, `p1_pins_resolution`, `eval_p1_packages`, `eval_p1_pins`.
2. (focal) `typo_alias_merge`: typo and vendor aliases are merged into the target package by the same unconditional mapping (contract 7.2). Fails `p1_packages_releases`, `p1_packages_latest`.
3. (focal) `quarantine_ignored`: the mirror's quarantine flag is compared with the string `'true'` although the cell decodes to a boolean, so withdrawn releases stay candidates (contract 2). Fails `p1_packages_releases`, `p1_pins_resolution`.
4. (focal) `exact_no_yanked`: an exact pin may not select a yanked release (contract 8.1, the yanked exact-pin rule). Fails `p1_pins_resolution`, `p1_exposures_rows`.
5. (focal) `snapshot_ignored`: archived services take declarations from their home manifest instead of the snapshot (contract 2). Fails `p1_pins_rows`, `p1_pins_resolution`.
6. (focal) `final_lifecycle_inverted`: the `legacy_lifecycle` sheet of the preview export is read for services that already have a lifecycle and skipped for migrated ones (contract 2). Fails `p1_services_catalog`.
7. (focal) `replay_ignored`: OSV rows whose events point at the replay feed lose their affected ranges (contract 2). Fails `p1_exposures_rows`.
8. (focal) `errata_unapproved`: errata apply without an approving review decision (contract 4). Fails `p1_ledger_custody` and many record values.
9. (focal) `minutes_first_decision`: the earliest review decision decides instead of the latest before the cut (contract 4). Fails `p1_exposures_status`, `p1_pins_resolution`.
10. (focal) `postcut_applies`: revisions recorded at or after the cut are applied instead of deferred (contract 4, 8.6). Fails `p1_ledger_deferred` and most stage 1 values.
11. (focal) `waiver_unapproved`: waivers apply without approval (contract 8.3). Fails `p1_exposures_status`.
12. (focal) `reversal_self_only`: a journal reversal cancels itself but not the reversed entry (contract 8.5). Fails `p1_ledger_entries`, `p1_ledger_closing`.
13. (focal) `policy_hardcoded`: SLA targets, holidays, base hours and tier weights are constants that match only the shipped corpus's `sla_policy.pdf` and `scoring_methodology.pdf`; another corpus states other figures (contract 8.3, instruction item 86). Invisible on the shipped corpus. Fails `eval_p1_exposures`, `eval_p1_services_teams_ledger`.
14. (focal) `decode_errors_swallowed`: a cell that does not follow its registered convention is read as an absent value instead of making the input invalid (contract 5.1 and 13, instruction item 85). Invisible on the shipped corpus. Fails `invalid_cell_is_reported`, `fractional_minutes_are_invalid`.
15. (drift) `cvss_halfup`: CVSS 3.1 scores are rounded half up instead of with the specification's Roundup (scoring_methodology.pdf). Fails `p1_exposures_cvss`.
16. (drift) `prerelease_lexical`: prerelease numbers compare as text, so rc.10 precedes rc.9 (contract 8.1). Fails `p1_pins_resolution`.
17. (drift) `caret_zero`: a caret range on 0.m.p with m above 0 admits everything below the next major (contract 8.1). Fails `p1_pins_resolution`.
18. (drift) `prerelease_ranges`: prereleases satisfy ordinary ranges whose lower bound is not a prerelease (contract 8.1). Fails `p1_pins_resolution`.
19. (drift) `last_affected_exclusive`: an OSV last_affected bound is treated as exclusive like fixed (contract 8.3). Fails `p1_exposures_rows`.
20. (drift) `nvd_any_source`: the latest NVD record wins regardless of its NVD or CNA source (contract 8.3). Fails `p1_exposures_cvss`.
21. (drift) `pub_date_utc`: the publication date is the UTC date instead of the local date of the service's region (sla_policy.pdf). Fails `p1_exposures_clock`.
22. (drift) `capacity_rounded`: capacity is rounded half to even instead of floored (contract 8.5). Fails `p1_teams`.
23. (drift) `latest_includes_yanked`: the latest release of a package may be a release yanked at the cut (contract 10.1). Fails `p1_packages_latest`, `eval_p1_packages`.
24. (drift) `fixed_ignores_yank`: the fixed version may be a release yanked at the cut (contract 8.3). Fails `p1_exposures_estimate`, `eval_p1_exposures`.
25. (drift) `team_on_end_inclusive`: a timesheet entry belongs to an allocation whose end date equals its worked date (contract 8.5, [start, end)). Fails `p1_ledger_entries`, `p1_ledger_closing`, `eval_p1_services_teams_ledger`.
26. (drift) `fx_strictly_before`: a fixing recorded at the instant of an entry is skipped instead of applying at or before the instant (contract 8.5). Fails `p1_ledger_entries`, `p1_ledger_closing`.
27. (drift) `lock_window_inclusive`: a lock override whose valid_to is 2025-09-30 still forces its version (contract 8.1, [valid_from, valid_to)). Fails `p1_pins_resolution`.
28. (drift) `exception_revoked_boundary`: a licence exception revoked on 2025-09-30 still grants its class (contract 8.4). Fails `p1_pins_license`, `eval_p1_pins`.
29. (drift) `sla_override_effective_strict`: an SLA override effective on 2025-09-30 is ignored (sla_policy.pdf, on or before). Fails `p1_exposures_sla`.
30. (drift) `xwalk_window_inclusive`: a legacy service identifier resolves through a crosswalk row whose valid_to equals the row's date (contract 5.2, [valid_from, valid_to)). Invisible on the shipped corpus. Fails `eval_p1_pins`, `eval_p1_services_teams_ledger`.
31. (trap) `xl_base_1900`: Excel serial timestamps are counted from 1899-12-31 (contract 5.2). Fails `p1_ledger_custody` and values in xlsx batches.
32. (trap) `xl4_as_xl`: 1904-based serials are read as 1900-based (contract 5.2). Fails `p1_ledger_custody`.
33. (trap) `ts_dmy_as_mdy`: day-first timestamps are read month-first (contract 5.2). Fails `p1_ledger_custody`.
34. (trap) `de_decimal`: German-locale decimals drop the comma decimal point (contract 5.2). Fails `p1_teams`, `p1_ledger_entries`.
35. (trap) `hours_min_as_h`: minute durations are read as hours, and a minute cell is not required to be a whole number (contract 5.2). Fails `p1_ledger_entries`, `fractional_minutes_are_invalid`.
36. (trap) `jpy_two_decimals`: JPY amounts are read with two minor decimals (contract 5.2). Fails `p1_ledger_entries`.
37. (trap) `bool_neg_ignored`: negated boolean columns (listed, cleared, unreviewed) are read without inversion (contract 5.2). Fails `p1_packages_releases`.
38. (trap) `cve_nopad_kept`: unpadded CVE sequence numbers stay unpadded, so aliases split (contract 7.3). Fails `p1_exposures_rows`.
39. (trap) `maven_lowercase`: maven coordinates are lower-cased, merging case-distinct artifacts (contract 7.2). Fails `p1_packages_releases`.
40. (trap) `legacy_aliases_all`: every row of the retired crosswalk is applied (contract 2). Fails `p1_packages_releases`.
41. (trap) `legacy_log_no_migration`: the retired deploy collector counts for us-central services without the 2025-08-04 limit (contract 2). Fails `p1_services_weight`.
42. (trap) `clock_offset_added`: collector clock offsets are added instead of subtracted (contract 8.2). Fails `p1_services_weight`.
43. (trap) `deploy_per_collector`: a deploy event repeated by two collectors is counted once per collector instead of once per rid (contract 8.2). Fails `p1_services_weight`, `eval_p1_services_teams_ledger`.
44. (trap) `authority_ignored`: per-vulnerability authority rows of `precedence.yaml` are ignored (contract 8.3). Fails `p1_exposures_cvss`, `p1_exposures_clock`.
45. (trap) `unknown_fallthrough`: an unknown publication falls through to the next source (contract 8.3). Fails `p1_exposures_clock`.
46. (trap) `vex_any_non_affected`: statements of status fixed and under_investigation mark an exposure not affected (contract 8.3). Fails `p1_exposures_status`.
47. (trap) `freeze_end_inclusive`: change-freeze windows include their end date (sla_policy.pdf). Fails `p1_exposures_clock`.
48. (trap) `days_from_publication_day`: days_open counts the publication date itself instead of starting the day after (sla_policy.pdf). Fails `p1_exposures_clock`, `eval_p1_exposures`.
49. (trap) `owner_any_role`: the owning team of a package may come from a maintainer row (contract 10.1, owner role only). Fails `p1_packages_latest`, `eval_p1_packages`.
50. (trap) `rate_after_september_july`: a post-cut timesheet amendment is costed at the July rate instead of the September rate (contract 8.5). Fails `p1_ledger_deferred`, `eval_p1_services_teams_ledger`.
51. (trap) `pct_rank_n`: the percent rank divides by the row count instead of the row count minus one (contract 11). Fails `p2_package_risk_ranks`.
52. (trap) `plan_slots_off_by_one`: only the first five open exposures of a service are eligible instead of six (contract 11.3). Fails `p2_plan_allocation`.
53. (trap) `plan_null_capacity_zero`: a written null capacity is treated as zero hours (contract 9, 11.3). Fails `p2_plan_allocation`.
54. (trap) `fold_hold_overdrawn`: the ledger fold holds an entry only once the balance is already negative, not when the entry would take it below zero (contract 11.4). Fails `p2_team_rollup_fold`.
55. (trap) `sla_nulls_as_zero`: null days open are counted as zero (contract 11.6). Fails `p2_sla_counts`, `p2_sla_statistics`.
56. (trap) `nearest_rank_rounding`: the nearest-rank position rounds half to even instead of up (contract 11.6). Fails `p2_sla_statistics`.
57. (trap) `license_all_scopes`: the licence summary counts dev and test pins (contract 11.5). Fails `p2_license_classes`.
58. (trap) `rollup_services_all`: the team rollup counts decommissioned services (contract 11.4, active services). Fails `p2_team_rollup_risk`.
59. (trap) `top_risk_floor`: the top-risk rank limit is floored instead of rounded up (contract 12.1). Fails `p3_gate_verdicts`.
60. (trap) `unsat_any_scope`: an unsatisfiable dev or test pin raises unsatisfiable_pin (contract 12.1, runtime pins only). Fails `p3_gate_reasons`, `p3_gate_verdicts`.
61. (trap) `impact_all_status`: deferred rescore impact sums over every exposure instead of the open ones (contract 12.3). Fails `p3_deferred_impact`.
62. (trap) `deferred_after_balance`: the after value of a cents amendment starts from the rollup balance instead of the closing row (contract 12.3). Fails `p3_deferred_impact`.
63. (trap) `util_zero_capacity`: a zero capacity yields utilisation 0 instead of null (contract 12.4). Fails `p3_scorecard_allocation`.
64. (trap) `score_open_denominator`: the team score divides breaches by open instead of open + 1 (contract 12.4). Fails `p3_scorecard_score`.

The reference implementation is Python (145 lines of repair driver: 73 repair hunks applied in place to the shipped modules of `/app/repo`, including a reader for the policy figures of `sla_policy.pdf` and `scoring_methodology.pdf`, a strict cell decoder and the removal of the policy constants and the revision-register flag the repairs leave unused, then the repository's unit tests and the amalgamation). Grading has two channels: the deterministic test channel and the judged channel.

Out of bounds: embedding answers of the shipped corpus in the program (`negative_hardcoded_sample_answers`); behaviour tied to directory names (`negative_filename_dependent_behaviour`); reading `/app/data` instead of the supplied directory (`negative_reads_training_corpus_at_runtime`); nondeterminism (`negative_nondeterministic_output`); reading back an artifact (`negative_reads_back_own_output_as_input`); parent rollups without children (`negative_rollup_written_without_children`); and printing data on a successful run (`negative_prints_data_on_success`). The directory, read-back and planted-corpus negatives fire only for a program whose repeat runs are byte-identical, so a nondeterministic program pays the nondeterminism penalty once.

Not a defect: the shipped publish step already keeps entries of the output directory that are not artifacts, so `/app/out/build.py` survives `build.py /app/data /app/out` (contract section 13, instruction item 62, graded by `keeps_foreign_entries`).

## Load-bearing work

25 artifacts are collected and every one is graded:

- `/app/out/build.py`
- `/app/out/packages.jsonl`
- `/app/out/pins.jsonl`
- `/app/out/exposures.jsonl`
- `/app/out/services.jsonl`
- `/app/out/teams.csv`
- `/app/out/ledger.jsonl`
- `/app/out/package_risk.json`
- `/app/out/service_risk.json`
- `/app/out/remediation_plan.json`
- `/app/out/team_rollup.json`
- `/app/out/license_summary.json`
- `/app/out/sla_metrics.json`
- `/app/out/release_gates.json`
- `/app/out/control_reconciliation.json`
- `/app/out/deferred_amendments.json`
- `/app/out/team_scorecard.json`
- `/app/out/certification.json`
- `/app/out/chain_audit.json`
- `/app/out/authority-trace.xml`
- `/app/out/rollup-ledger.tsv`
- `/app/out/reconciliation-map.yaml`
- `/app/out/dependency-matrix.ini`
- `/app/out/freeze-register.log`
- `/app/out/training-closure.md`

The input corpus (62 files including the repository):

- `/app/repo/README.md`
- `/app/repo/pyproject.toml`
- `/app/repo/src/helios_close/__init__.py`
- `/app/repo/src/helios_close/cascade.py`
- `/app/repo/src/helios_close/cli.py`
- `/app/repo/src/helios_close/domain.py`
- `/app/repo/src/helios_close/formats.py`
- `/app/repo/src/helios_close/ledger.py`
- `/app/repo/src/helios_close/records.py`
- `/app/repo/src/helios_close/rules.py`
- `/app/repo/tests/test_visible.py`
- `/app/repo/tools/amalgamate.py`
- `/app/data/advisories_feed_cache.json`
- `/app/data/advisories_ghsa.json`
- `/app/data/advisories_nvd.xml`
- `/app/data/advisories_osv.jsonl`
- `/app/data/advisories_osv_replay.jsonl`
- `/app/data/advisory_aliases.csv`
- `/app/data/advisory_rescores.parquet`
- `/app/data/change_freeze.ics`
- `/app/data/clock_offsets.txt`
- `/app/data/close_contract.md`
- `/app/data/control_totals.html`
- `/app/data/deploy_events_central.log`
- `/app/data/deploy_events_east.log`
- `/app/data/deploy_events_legacy.log`
- `/app/data/deploy_events_west.log`
- `/app/data/engineer_rates.xlsx`
- `/app/data/engineer_roster.ini`
- `/app/data/errata_register.docx`
- `/app/data/fx_fixings.tsv`
- `/app/data/ledger_journal.db`
- `/app/data/license_overrides.csv`
- `/app/data/license_policy.md`
- `/app/data/license_scan.parquet`
- `/app/data/lock_overrides.toml`
- `/app/data/manifests_core.csv`
- `/app/data/manifests_data.yaml`
- `/app/data/manifests_edge.jsonl`
- `/app/data/manifests_legacy.txt`
- `/app/data/manifests_snapshot.csv`
- `/app/data/name_aliases.tsv`
- `/app/data/name_aliases_legacy.tsv`
- `/app/data/package_owners.json`
- `/app/data/precedence.yaml`
- `/app/data/registry_cargo.tsv`
- `/app/data/registry_maven.xml`
- `/app/data/registry_mirror.parquet`
- `/app/data/registry_npm.csv`
- `/app/data/registry_pypi.jsonl`
- `/app/data/remediation_estimates.xlsx`
- `/app/data/remediation_timesheets.csv`
- `/app/data/review_minutes.docx`
- `/app/data/scanner_findings.jsonl`
- `/app/data/scoring_methodology.pdf`
- `/app/data/service_catalog.xlsx`
- `/app/data/service_catalog_final.xlsx`
- `/app/data/sla_policy.pdf`
- `/app/data/source_conventions.html`
- `/app/data/vex_statements.xml`
- `/app/data/waivers.db`
- `/app/data/yank_notices.mbox`

The source layer is the record-level resolution layer; the risk layer is the population derivation; the close layer is the certification fold. The boundaries are lossy by design: source values use scores at one decimal, weights at four, estimates at two, capacities floored to whole hours and money in whole cents. Later values are computed from those in-memory rounded forms. The deferred register carries amendments recorded after the cut that the risk values ignore and the close values report. Six format-distinct evidence artifacts serialise the same resolved identities, and every source, risk and close file ends with the audit rows of contract section 12.7, each bound to the digest of that file's data part.

The dependency matrix below has rows as dependent artifacts and columns as prerequisites. The numbered order is: 1 packages, 2 pins, 3 exposures, 4 services, 5 teams, 6 ledger, 7 package_risk, 8 service_risk, 9 remediation_plan, 10 team_rollup, 11 license_summary, 12 sla_metrics, 13 release_gates, 14 control_reconciliation, 15 deferred_amendments, 16 team_scorecard, 17 certification, 18 chain_audit, 19 authority_trace, 20 rollup_ledger, 21 reconciliation_map, 22 dependency_matrix, 23 freeze_register, 24 training_closure. It contains exactly 216 filled cells, has an empty diagonal, and is the in-memory resolution order.

| dependent | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 packages |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2 pins | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 3 exposures | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 4 services | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 5 teams | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 6 ledger | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 7 package_risk | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 8 service_risk | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 9 remediation_plan | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 10 team_rollup | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 11 license_summary | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 12 sla_metrics | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 13 release_gates | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |  |
| 14 control_reconciliation | X | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |  |
| 15 deferred_amendments |  | X | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |  |
| 16 team_scorecard |  |  | X | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |  |
| 17 certification |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |  |
| 18 chain_audit |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |  |
| 19 authority_trace |  |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |  |
| 20 rollup_ledger |  |  |  |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |  |
| 21 reconciliation_map |  |  |  |  |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |  |
| 22 dependency_matrix |  |  |  |  |  |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X |  |  |  |
| 23 freeze_register |  |  |  |  |  |  |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X |  |  |
| 24 training_closure |  |  |  |  |  |  |  |  |  |  |  | X | X | X | X | X | X | X | X | X | X | X | X |  |

By design the verifier never reads the agent's `/app/data` or `/app/repo`: it rebuilds the reference from the seeded world model (which regenerates the fifty shipped exports: byte for byte, except that the two SQLite databases match row for row, since their file headers record the SQLite library version that wrote them) and runs the delivered program on unseen corpora. The only use of `/app/data` inside the verifier container is `negative_reads_training_corpus_at_runtime`, which plants a decoy corpus there for one probe run and removes it again. The risk-layer and close-layer reference is written from contract sections 11 and 12 independently of the repository code.

## Verification

The test channel declares 78 positive and 7 negative tests, positive weight total 262 and negative weight total -27, so its range is -27/262 = -0.103 to +1.000. The rule combining the two channels belongs to the runner harness (tests/reward.toml) and is not restated here. Oracle and empty-run scores quoted anywhere for this task are test-channel scores; no judged-channel oracle score exists.

Positive tests (78):

- `p1_packages_releases` (weight 5)
- `p1_packages_latest` (weight 5)
- `p1_pins_rows` (weight 1)
- `p1_pins_resolution` (weight 5)
- `p1_pins_license` (weight 5)
- `p1_exposures_rows` (weight 5)
- `p1_exposures_cvss` (weight 5)
- `p1_exposures_status` (weight 5)
- `p1_exposures_clock` (weight 5)
- `p1_exposures_sla` (weight 5)
- `p1_exposures_estimate` (weight 5)
- `p1_services_catalog` (weight 5)
- `p1_services_weight` (weight 5)
- `p1_teams` (weight 5)
- `p1_ledger_entries` (weight 5)
- `p1_ledger_closing` (weight 1)
- `p1_ledger_controls` (weight 1)
- `p1_ledger_custody` (weight 5)
- `p1_ledger_deferred` (weight 5)
- `p1_written_form` (weight 1)
- `p2_package_risk_values` (weight 5)
- `p2_package_risk_ranks` (weight 5)
- `p2_package_risk_totals` (weight 1)
- `p2_service_risk_values` (weight 5)
- `p2_service_risk_ranks` (weight 5)
- `p2_service_risk_totals` (weight 1)
- `p2_plan_allocation` (weight 5)
- `p2_plan_balances` (weight 5)
- `p2_plan_totals` (weight 5)
- `p2_team_rollup_risk` (weight 5)
- `p2_team_rollup_fold` (weight 5)
- `p2_license_classes` (weight 5)
- `p2_license_teams` (weight 3)
- `p2_sla_counts` (weight 5)
- `p2_sla_statistics` (weight 3)
- `p2_propagation` (weight 3)
- `p2_upstream_binding` (weight 1)
- `p3_gate_verdicts` (weight 5)
- `p3_gate_totals` (weight 1)
- `p3_gate_reasons` (weight 5)
- `p3_reconciliation_stages` (weight 5)
- `p3_reconciliation_agreement` (weight 3)
- `p3_deferred_impact` (weight 5)
- `p3_deferred_totals` (weight 3)
- `p3_scorecard_allocation` (weight 5)
- `p3_scorecard_score` (weight 5)
- `p3_certification_risk` (weight 5)
- `p3_certification_verdict` (weight 3)
- `certification_verdict_chain` (weight 3)
- `p3_chain_audit_files` (weight 3)
- `p3_chain_audit_checks` (weight 3)
- `p3_propagation` (weight 3)
- `p3_upstream_binding` (weight 1)
- `eval_p1_packages` (weight 3)
- `eval_p1_pins` (weight 3)
- `eval_p1_exposures` (weight 5)
- `eval_p1_services_teams_ledger` (weight 5)
- `stage_errors_are_reported` (weight 3)
- `invalid_cell_is_reported` (weight 3)
- `fractional_minutes_are_invalid` (weight 1)
- `rerun_replaces_complete_set` (weight 1)
- `keeps_foreign_entries` (weight 3)
- `writes_only_into_output` (weight 1)
- `wrong_argument_count_is_reported` (weight 1)
- `single_invocation_interface` (weight 3)
- `complete_output_set` (weight 1)
- `artifact_volume_contract` (weight 1)
- `authority_trace_layout` (weight 1)
- `rollup_ledger_layout` (weight 1)
- `reconciliation_map_layout` (weight 1)
- `dependency_matrix_layout` (weight 1)
- `freeze_register_layout` (weight 1)
- `closure_notes_layout` (weight 1)
- `nested_json_evidence` (weight 1)
- `evidence_text_form` (weight 1)
- `evidence_values_bound` (weight 5)
- `evidence_formats_agree` (weight 3)
- `audit_rows_bound` (weight 3)

Negative tests (7) hold only when the cheat happened (inverted polarity), so an honest run leaves them false:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_reads_back_own_output_as_input` (weight -5)
- `negative_rollup_written_without_children` (weight -3)
- `negative_prints_data_on_success` (weight -1)

The judged channel is 19 criteria (15 positive / 4 negative), positive total 43, negative total -18:

- **R1** (+3, trajectory): The agent reads /app/data/close_contract.md and opens the documents it names before its first edit of the program in /app/repo, as the instruction asks: "Read the contract and the documents it names before you change the program."
- **R2** (+5, trajectory): The agent checks each suspected defect against a published control figure, a custody count or a documented rule before changing the code for it, as the instruction asks: "Check each suspected defect against the published control figures, the custody counts or the documented rules before you change the code for it."
- **R3** (+5, trajectory): The agent settles each disagreement between two exports by the contract's authority rule for that source, as the instruction asks: "Decide every conflict between sources by the authority rules of the contract"
- **R4** (+3, user_facing_message): The response names each rule whose two plausible readings each broke a different control figure together with the documented rule the agent applied, or states that the agent met no such conflict, as the instruction asks: "name each rule whose two plausible readings each broke a different control figure, with the documented rule you applied, or say that you met none"
- **R5** (+3, trajectory): The agent produces the delivered twenty-four artifacts in one run of /app/out/build.py with a data directory and an output directory, as the instruction asks: "The invocation is the entire production run."
- **R6** (+1, trajectory): The agent runs the repository's validation command, its unit tests, while repairing the program, as the instruction asks: "Use the repository's own validation command and its amalgamation tool while you work."
- **R7** (+1, trajectory): The agent builds /app/out/build.py with the repository's tools/amalgamate.py, as the instruction asks: "Use the repository's own validation command and its amalgamation tool while you work."
- **R8** (-5, trajectory): The agent fetches code, data, answers or hints for this task from the network or from any source outside the image, against the instruction: "Work offline, using only what the image provides; fetching code, data or answers from anywhere else is forbidden."
- **R9** (-5, trajectory): The agent edits, creates or deletes a file under /app/data, against the instruction: "Leave the files in /app/data unmodified"
- **R10** (-5, trajectory): The agent writes any of the twenty-four data artifacts under /app/out by hand or with a script other than /app/out/build.py, against the instruction: "produce every deliverable by running the program rather than writing values by hand"
- **R11** (+3, user_facing_message): The response lists each repair made to the program with the module it changed and the contract section or named document rule that the repair restores, as the instruction asks: "In your final message, list every repair you made with the module you changed, the contract section or named document rule that the repair restores"
- **R12** (+1, user_facing_message): The response names /app/out as the output directory, as the instruction asks: "name the output directory."
- **R13** (+3, user_facing_message): The response reports the agreeing and total control counts that the final control_reconciliation.json of the agent's last build carries, as the instruction asks: "give the agreeing and total control counts of your final build"
- **R14** (+3, trajectory): The agent recomputes each relied-on precomputed total from its detail rows and compares the two values before use.
- **R15** (+3, trajectory): The agent inspects the exit status and the listing of the twenty-four artifacts of its final build before concluding.
- **R16** (+3, trajectory): The agent's code changes to the close program meet ordinary Python code review standards: each exception handler the agent adds names the exceptions it expects, and the repairs leave no definition they made unused and no leftover debug output in /app/out/build.py.
- **R17** (+3, user_facing_message): The response names, for each repair it lists, the control figure, custody count or documented rule that confirmed the repair, as the instruction asks: "and the control figure, custody count or documented rule that confirmed it."
- **R18** (+3, trajectory): The agent runs the repaired program on at least one input directory whose export contents differ from /app/data, such as a copy with edited cells, records or policy figures, and checks that the outputs follow the documented rules for that directory before concluding.
- **R19** (-3, trajectory): The agent creates a notes file, scratch program or trial output inside /app/repo, against the instruction: "Keep notes, scratch programs and trial outputs out of `/app/repo`"

## Root cause

**One contract, many readers.** Every export is batched; a batch's column layout, value conventions and sentinel tokens are registered in `source_conventions.html`. A program that reads cells at face value gets plausible but wrong values on most rows, and the custody checksums of the stage 1 ledger expose every misread cell.

**Revisions, errata and the cut.** The in-force revision is the highest non-draft revision recorded before the cut; errata apply only with an approving review decision; amendments recorded after the cut go to the deferred register and are never applied by any stage.

**Authority is per field and per source.** The mirror, snapshot, replay feed, cache, preview catalogue, retired crosswalk, retired collector and scanner each look authoritative and each is authoritative for exactly one documented slice.

**Expert variants.** Semantic-version precedence with numeric prerelease numbers, caret on 0.x, the yanked exact-pin rule, OSV last_affected, CVSS Roundup, NVD-over-CNA precedence and local publication dates are the variants a generalist gets wrong.

**Thin control coverage.** `control_totals.html` publishes 191 in-force figures for teams, exports (record counts only) and global totals. No figure exists per package, pin, exposure or service, so the record-level rules (owners, latest and fixed releases, licence boundaries, override windows, SLA overrides, day counting, deploy identity) and every risk and close formula have to be checked against the documented rule itself.

**Another corpus.** The program is graded on an unseen corpus whose policy documents state other SLA targets, holidays and base hours, and on copies of that corpus that carry one malformed cell. A program tuned to the shipped quarter (constants copied from the shipped PDFs, malformed cells read as absent) reproduces every shipped figure and still fails there.

**The cascade.** Risk and close values consume the earlier in-memory values in the documented order. Serialisers bind the exact bytes to be published by SHA-256 without reading those files back.

**Red lines.** No online lookup, no edits to `/app/data`, no hand-written output values, no artifact read-back, and no answers embedded in the program.

## Solution shape

1. Confirm that `/app/repo` holds the shipped modules (or their repaired form, which is left as it is) and apply the repair hunks in place to `src/helios_close/*.py`, each verified against the digest of the lines it replaces.
2. Run the repository's unit tests on the repaired package without writing bytecode into the repository.
3. Amalgamate the package into `/app/out/build.py` with `tools/amalgamate.py`.
4. Run `build.py /app/data /app/out` once; the publish step stages the set beside `/app/out` and keeps `build.py` in place.
5. Confirm that `/app/out` holds `build.py` and the twenty-four data artifacts (solve.sh exits 4 otherwise).

## Ordered plan

1. Read `close_contract.md` end to end, then the documents it names (R1).
2. Run the shipped program and the repository tests; list the failing tests and the control figures the dry run misses (R6).
3. Resolve the conventions register and the crosswalk first: they are written canonically and decode everything else. Make every cell decode strictly: a cell outside its convention is invalid input (exit 3), never an absent value.
3a. Replace every policy constant with the figure the input directory's `sla_policy.pdf` and `scoring_methodology.pdf` state, then run the program on a copy of the corpus with edited policy figures and cells (R18).
4. For each suspected defect, compute the affected control or custody figure before and after the change (R2, R14).
5. Settle every source conflict by the authority section of the contract, never by recency or completeness (R3).
6. Where two fixes each break a different control, find the third documented rule and report it (R4).
7. Resolve source, risk and close values in order inside one run, passing shared values in memory, and build the program with the amalgamation tool (R5, R7).
8. Run the complete build, inspect its exit status and the twenty-four-file listing, and re-run it over renamed directories to confirm determinism and independence from paths (R15).
9. List every repair with its module, the rule it restores and the evidence that confirmed it, then the agreeing and total control counts and the output directory (R11, R17, R12, R13). Keep notes and scratch files out of `/app/repo` (R19).

## Pitfalls

- Reading naive or serial timestamps as UTC: custody checksums and boundary deploy counts fail (`p1_ledger_custody`, `p1_services_weight`).
- Trusting the preview catalogue, the snapshot, the mirror or the scanner beyond their slice: `p1_services_catalog`, `p1_pins_resolution`.
- Recomputing each artifact independently at full precision: `p2_package_risk_values`, `p2_plan_allocation` and the close checks fail.
- Applying the post-cut rescore amendments: `p1_exposures_cvss`, `p1_ledger_deferred`.
- Treating a written null capacity as zero: `p2_plan_allocation`, `p3_scorecard_allocation`.
- Folding allocations or the ledger in raw export order: `p2_plan_allocation`, `p2_team_rollup_fold`.
- Reading a just-written artifact back as the next layer's input: `negative_reads_back_own_output_as_input`.
- Replacing the whole output directory on publish and so deleting `/app/out/build.py`: `keeps_foreign_entries` and every check that runs the program.
- Copying the policy figures of the shipped PDFs into the program: every shipped figure agrees, while `eval_p1_exposures` and `eval_p1_services_teams_ledger` fail on the unseen corpus.
- Leaving the decoder's broad exception handler in place: a malformed cell becomes an absent value and the run succeeds (`invalid_cell_is_reported`).
- Following the shipped evidence writer without the audit-row and evidence formulas of contract section 12.7: `audit_rows_bound`, `evidence_values_bound`, `evidence_formats_agree`.

Hallucination map:

| bait | fluent wrong answer | agent-visible refutation | catching check |
|---|---|---|---|
| registry mirror release rows | the mirror is the newest release authority | `close_contract.md` section 2 limits it to quarantine | `p1_packages_releases` |
| preview service catalogue | the file named final replaces the catalogue | contract section 2 grants only legacy lifecycle authority | `p1_services_catalog` |
| core manifest snapshot | the snapshot is the cleanest core source | contract section 2 limits it to archived services | `p1_pins_rows` |
| replayed OSV feed | replay is globally newer | contract section 2 uses only the elsewhere events cell | `p1_exposures_rows` |
| advisory feed cache score | copy the supplied score | contract section 2 allows only a missing vector lookup | `p1_exposures_cvss` |
| retired alias crosswalk | all historical aliases merge | contract sections 2 and 7.2 restrict old renames | `p1_packages_releases` |
| retired deploy collector | legacy telemetry fills every gap | contract section 2 limits region and corrected time | `p1_services_weight` |
| first review decision | the first approval is final | contract section 4 selects the latest pre-cut decision | `p1_pins_resolution` |
| post-cut higher revision | highest revision always wins | contract section 4 excludes revisions at or after cut | `p1_ledger_deferred` |
| unapproved erratum | a formal errata row always applies | contract section 4 requires an approving minute | `p1_ledger_custody` |
| precomputed control total | published means derived truth | contract requires reconciliation to detail and reports disagreement | `p3_reconciliation_stages` |
| rounded risk source | reuse the displayed package total for every view | contract sections 11 and 12 specify separate population folds | `p3_certification_risk` |
| null capacity | blank means zero capacity | contract section 11.3 defines null as unlimited | `p2_plan_allocation` |
| null elapsed days | unknown publication means zero days | SLA policy keeps unknown as null | `p2_sla_counts` |
| exact yanked pin | yanked releases can never resolve | contract section 8.1 permits an exact yanked pin | `p1_pins_resolution` |
| caret on zero major | caret always advances the major | contract section 8.1 narrows zero-major bounds | `p1_pins_resolution` |
| prerelease range | ordinary ranges admit prereleases | contract section 8.1 requires an exact or matching prerelease lower bound | `p1_pins_resolution` |
| OSV last affected | last affected is exclusive | contract section 8.3 makes it inclusive | `p1_exposures_rows` |
| NVD modified time | newest record wins regardless of source | contract section 8.3 gives NVD source priority | `p1_exposures_cvss` |
| CVSS decimal | ordinary half-up rounding is safe | `scoring_methodology.pdf` states the version-specific Roundup | `p1_exposures_cvss` |
| UTC publication date | every date is the UTC date | `sla_policy.pdf` requires the service-region local date | `p1_exposures_clock` |
| freeze boundary | the end date is included | `sla_policy.pdf` defines a half-open window | `p1_exposures_clock` |
| German decimal text | punctuation can be stripped | contract section 5.2 assigns decimal and grouping roles | `p1_teams` |
| minute duration | a numeric cell is hours | conventions register and contract section 5.2 label minutes | `p1_ledger_entries` |
| JPY amount | every currency has two minor decimals | contract section 5.2 gives JPY exponent zero | `p1_ledger_entries` |
| negative boolean convention | the written token is the value | conventions register says the boolean is inverted | `p1_packages_releases` |
| unpadded CVE | preserve source spelling as identity | contract section 7.3 pads the canonical sequence | `p1_exposures_rows` |
| Maven coordinate case | package names are always lower case | contract section 7.2 preserves Maven case | `p1_packages_releases` |
| service allocation order | sort by severity before capping | contract section 11.3 uses source-layer sequence | `p2_plan_allocation` |
| ledger negative balance | apply every entry then report negative | contract section 11.4 holds an entry that crosses zero | `p2_team_rollup_fold` |
| policy figures in the PDFs | the shipped figures are fixed constants | contract section 8.3 and instruction item 86 make them facts of the corpus | `eval_p1_exposures` |
| malformed cell | an unreadable cell is simply missing | contract sections 5.1 and 13 make it invalid input | `invalid_cell_is_reported` |
| minute durations | any decimal is a valid minute count | contract section 5.2 writes min as a whole number of minutes | `fractional_minutes_are_invalid` |
| maintainer row | any package team row is the owner | contract section 10.1 takes the latest owner-role row | `p1_packages_latest` |
| yanked newer release | the newest stable release is latest or fixed | contracts 8.3 and 10.1 exclude releases yanked at the cut | `p1_exposures_estimate` |
| half-open windows | an end date is inclusive | contract sections 5.2, 8.1 and 8.5 use [start, end) | `p1_pins_resolution` |

## Provenance

```yaml
uuid: cd6a3a55-cec4-552b-a328-7e324eb014d8
instance_id: cd6a3a55-cec4-552b-a328-7e324eb014d8
task_name: terminal-bench/cd6a3a55-cec4-552b-a328-7e324eb014d8
fix_patch_sha256: ec2766b5824557603a8b0250bbbbd359aa379c0a56a4ac4aaf5e3c1f64c35f3c  # sha256 of solution/solve.sh
solve_py_sha256: 6607a3ad01a496ca9603cca5d407572b0781ee3b652e36d043ea08fa9e1e9bcc  # informational; solve.py is 145 lines
language: python
golden_score_measured: 1.0  # test channel only
golden_score_channel_a_pct: 100.0  # test channel
golden_score_channel_b_pct: null  # judged channel has no oracle score
golden_score_runs: 1
golden_score_trial_id: null
golden_score_verified_by: >
  One grading of the test channel over the oracle's output read 1.000 (262
  of 262, no negative fired); an empty-artifact stub read 0.0038
  (complete_output_set only). The judged channel has no oracle score.
caveat: >
  The test channel carries 78 positive checks worth 262 weight and 7
  negative checks worth -27 weight, so on its own it ranges -27/262 = -0.103
  to +1.000. The judged channel carries 19 criteria worth 43 positive and
  -18 negative points. tests/reward.toml divides each channel's weighted sum
  by its positive total and gives each half of the reward, so the combined
  reward runs from about -0.261 to +1.000 with no clamp.
```
