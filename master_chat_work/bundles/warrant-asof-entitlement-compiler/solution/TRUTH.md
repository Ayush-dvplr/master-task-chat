# TRUTH.md - warrant-asof-entitlement-compiler

## Defect

`warrant-ctl`, shipped as `/app/data/tool.zip`, compiles bitemporal access profiles: for one instant (`as_of`) and one knowledge horizon (`recorded_cutoff`) it states which principal holds which permission in `dev` and `prod` and until when. The shipped release implements the retired 2024 semantics, crashes on open ended requests, never registered `summarize`, and silently compiles from an incomplete corpus. The contract in `/app/data/*.md` governs; three conventions are left to the access gateway; they belong to each corpus and are decided only by that corpus's reviewer observations in `access_attestations.csv`. Every item below is graded by the named checks; the profile and held-out checks catch all of them because they compare whole artifacts.

1. (focal) Window boundary convention is withheld: in the shipped corpus every window is half open, `[start, end)`. Legacy code treats membership, binding and key ends as inclusive and freeze windows as closed. Evidence: attestation rows reviewed exactly at a grant's computed end read `not_in_effect`, rows at its start and one second before its end read `in_effect`. conv_2, conv_6 and conv_8 plant the closed reading `[start, end]` for every window the access contract lists, with memberships, bindings and grants ending exactly at `as_of` and freeze windows ending exactly at the start of an approved request. Defeated checks: `profile_prod_keys_exact`, `profile_dev_keys_exact`, `boundary_tier_profiles_exact`, `audit_rejects_exact` (freeze_window), the dev and prod profile checks of `conv_2`, `conv_6` and `conv_8`.
2. (focal) In the shipped corpus HR effective dates are read on the employee's site clock (local midnight from `tz_rules.json`), contract dates on the contract site's clock. Legacy reads UTC days. Each conv tier plants one zone's clock for every person and contract (`zone:Site/Dune`, `zone:Site/Ember`, `zone:Site/Cobalt`, `zone:Site/Brisk`, `zone:Site/Arden`). Evidence: observation rows between the UTC midnight and the site midnight of termination days. Defeated: `profile_prod_keys_exact`, `profile_prod_values_exact`, `heldout_tier_a_profiles_exact`, `audit_held_grants_exact`.
3. (focal) In the shipped corpus an approved grant starts at `max(requested start, decided_at of the k-th distinct qualifying approval)`, `k = approvals_required`, and its `max_grant_hours` ceiling counts from that start; every conv tier plants the requested start. Legacy starts at the requested start and crashes on a null end. Evidence: observation rows between `effective_from` and approval completion read `not_in_effect`; rows between the k-th and a later approval read `in_effect`. Defeated: `profile_prod_values_exact`, `heldout_audit_exact`, `audit_unattested_exact`.
4. (focal) `recorded_at` is epoch milliseconds in `revocations_selfservice.csv` and epoch seconds in `grant_corrections.jsonl`; visibility is compared at the precision written, so `R*1000 + 400` ms is invisible. Defeated: `audit_rejects_exact` (revoker_not_party), `self_check_partition_exact`.
5. (focal) Identity: handles are case insensitive, a winning account handle never goes through the alias table, stale alias rows naming a real handle are inert, aliases are matched case insensitively. Defeated: `audit_unresolved_exact`, `profile_dev_keys_exact`.
6. (focal) IdP winner is the highest generation visible at the cutoff, ties broken by `idp_shard_priority` from the resolved configuration (`west,east`, site layer), not the default and not file order. Defeated: `profile_prod_keys_exact` through `disabled` eligibility.
7. (focal) Ceiling keys (`max_grant_hours`, `session_idle_minutes`, `attestation_max_age_days`) take the minimum over every layer and every standing journal entry; a null cancels earlier journal entries; journal visibility uses the cutoff and order is `(effective_at, seq)`. Defeated: `config_shipped_exact`, `config_heldout_resolution_exact`.
8. (focal) Nested groups use the widest route: the membership bound is the maximum over chains of the minimum removal along the chain; cycles are legal. Legacy walks breadth first. Defeated: `profile_dev_values_exact`, `heldout_tier_b_profiles_exact`.
9. (drift) Strict instant grammar: space separator, missing offset, fractional seconds, lower case `z`, offset without colon and impossible dates are `bad_timestamp`. Legacy `fromisoformat` accepts most of them and reads naive times as UTC, a habit most engineers share. Defeated: `audit_rejects_exact`.
10. (drift) Zone conversion uses the transition table; on call shifts are local wall times. Legacy applies the standard offset all year. Defeated: `profile_prod_values_exact` (on call bounds).
11. (drift) Contract cover includes the whole `end_date`. Defeated: `profile_dev_keys_exact`.
12. (trap) Approvals qualify only for employees who are neither beneficiary nor requester and are employed at `decided_at`; one principal counts once across handles. Defeated: `audit_held_grants_exact`.
13. (trap) Ticket duplicates across monthly shards: highest `export_generation`, identical ties collapse, differing ties are all `conflicting_duplicate`. Defeated: `audit_unresolved_exact`.
14. (trap) Corrections govern by highest revision, HR corrections by latest recorded, contract amendments by highest `amendment_no`. Defeated: `profile_prod_values_exact`, `audit_held_grants_exact`.
15. (trap) Security revocations act at `effective_at`, not at `recorded_at`; a future one caps the value. Defeated: `profile_prod_values_exact`.
16. (trap) On call bounds carry through back to back shifts of the same holder; a swap breaks the carry. Defeated: `profile_prod_values_exact`.
17. (trap) Attestation ignores self reviews and accepts a review exactly `attestation_max_age_days` old; on call components survive gating. Defeated: `audit_unattested_exact`.
18. (trap) Separation of duties: both standing is a recorded conflict, one standing suspends the elevated side, otherwise the later elevation start loses and equal starts lose by name; on call components are exempt. Defeated: `audit_sod_exact`.
19. (trap) Role expansion keeps only permissions whose catalog scope is the profile or `both`. Defeated: `profile_dev_keys_exact`.
20. (trap) Held grants list only pending or vetoed requests whose requested end is open or after `as_of`. Defeated: `audit_held_grants_exact`.
21. (trap) The compiler must refuse a corpus missing a manifest file and write nothing. Defeated: `negative_partial_output_on_missing_input`.
22. (focal) The gateway conventions are settled per corpus from its own observations: the eight conv tiers each fit exactly one reading among HR clock (site, UTC, each zone of `tz_rules.json`), grant start and window end, and that reading differs from the shipped one. A tool that hard codes the shipped reading compiles wrong dev and prod profiles there. Defeated: `conv_1_dev_profile_exact` to `conv_8_prod_profile_exact`.
23. (drift) An MFA log line whose instant uses a space instead of `T` is a record of the file and is rejected `bad_timestamp`. Defeated: `audit_rejects_exact`, `self_check_partition_exact`.

Trap incidence on the shipped corpus (keys of the shipped profiles whose presence or value changes when that trap alone is handled the legacy way, and the audit parts that change):

| Trap | Firing records | Graded value that changes |
|---|---|---|
| 1 window ends | removals at `as_of`, bindings ending at `as_of`, keys valued at `as_of`, grants starting on freeze ends | 74 dev and 63 prod keys, `rejects`, `unattested`, `sod` |
| 2 HR site clock | boundary terminations and rehires on the `as_of` local day, contract dates | 8247 dev and 5275 prod keys |
| 3 grant start | late approvals of old tickets, approvals after `effective_from` | legacy crashes; 904 prod and 705 dev starts move |
| 4 millisecond unit | every self service revocation, boundary rows at `R*1000+1..999` | 42 dev and 98 prod keys, `rejects`, `self_check` |
| 5 alias handling | case variant aliases, stale alias rows | 1462 dev and 2308 prod keys, `unresolved` |
| 6 IdP winner | 67 cross shard ties, invisible higher generations | 317 dev and 129 prod keys |
| 7 ceilings and journal | the `prod.max_grant_hours` sequence, back dated entries | configuration, 808 prod keys |
| 8 widest route | diamond memberships, cycles | 200 dev and 108 prod keys |
| 9 strict grammar | malformed instants in every record file | `rejects`, 2453 prod keys |
| 10 zone table | daylight zones on 2026-10-28 | 4444 dev and 2928 prod keys |
| 11 contract cover | contracts ending on the `as_of` local day | 5825 dev and 3430 prod keys |
| 12 approvals | self, requester, contractor, unemployed and repeated approvers | 20 dev and 93 prod keys, `held_grants` |
| 13 duplicates | re-exported tickets | `unresolved`, `held_grants` |
| 14 governing versions | out of order revisions and amendments | 40 dev and 2 prod keys |
| 15 security timing | future dated and retroactive cases | 198 dev and 81 prod keys |
| 16 shift carry | 24 hour and 7 day rotations | 34 prod keys |
| 17 attestation | self reviews, boundary age rows | 41 and 33 prod keys, `unattested` |
| 18 separation of duties | standing and elevated pairs | 119 dev and 156 prod keys, `sod` |
| 19 scope | dev only permissions in roles bound in prod | 1605 dev and 902 prod keys |

Repair route: `solve.py` edits the shipped modules in place, one block per defect, and adds `gateway.py`; the verifier recomputes every expected value with its own implementation of the contract.

Out of bounds: the task never needs network access, third party packages, a zone database, reading the verifier, or reconstructing lost data; every rule is stated in the contract or decided by the corpus's own observations.

## Load-bearing work

Artifacts: `/app/out/config.json`, `/app/out/report.json`, `/app/out/tool.zip`, `/app/out/profile_dev.json`, `/app/out/profile_prod.json`, `/app/out/validation_report.json`, `/app/out/summary.json`.

- `tool.zip`: the repaired compiler with `cli.py` at the root; it is run on eleven unseen corpora (three with the shipped conventions, eight conv tiers with their own conventions) and on one row shuffled copy.
- `config.json`: flat resolved configuration with UTC anchors.
- `profile_dev.json`, `profile_prod.json`: `principal|permission` to a UTC instant or `open`; the spine.
- `validation_report.json`: rejects, unresolved, held grants, unattested pairs, separation of duties outcomes, per file class counts.
- `summary.json`: counts bound to the profiles and to the report by identity.
- `report.json`: invocation transcript, digests, one repair per defect.

## Verification

`tests/test.sh` hardens the verifier and runs rewardkit. The test channel registers 47 checks: 24 at weight 5, 10 at weight 3 and 5 at weight 1, positive total 155; and 8 negatives with total magnitude 20: `negative_tool_ignores_input` (-5), `negative_nondeterministic_output` (-3), `negative_output_depends_on_row_order` (-1), `negative_partial_output_on_missing_input` (-3), `negative_mutates_input_directory` (-3), `negative_report_digest_mismatch` (-3), `negative_wallclock_fields` (-1), `negative_legacy_tool_delivered` (-1). The judge channel has 17 criteria, positive total 26 and negative total 15. `tests/reward.toml` weights each channel by 0.5 over its positive total. Tests-only oracle score: 1.000; nop and the empty artifact stub score 0.000. There is no judged-channel oracle score.

| Requirement | Artifact | Checks (weight) | Criteria |
|---|---|---|---|
| repair to the contract | tool.zip | heldout_tier_a_profiles_exact (5), heldout_tier_b_profiles_exact (5), heldout_audit_exact (5) | r5_runs_original_tool_first, r9_repaired_code_quality |
| generalize to unseen corpora | tool.zip | config_heldout_resolution_exact (3), heldout_summary_exact (3), boundary_tier_profiles_exact (3) | |
| conventions of each corpus | tool.zip | conv_1_dev_profile_exact to conv_8_prod_profile_exact (5 each) | r6_reruns_on_altered_approval_copy, r8_counts_fitting_start_readings |
| take everything from --data | tool.zip | negative_tool_ignores_input (-5) | |
| refuse an incomplete corpus | tool.zip | negative_partial_output_on_missing_input (-3) | |
| row order independence | tool.zip | negative_output_depends_on_row_order (-1), negative_nondeterministic_output (-3) | |
| never modify --data | tool.zip | negative_mutates_input_directory (-3) | |
| configuration via resolve-config | config.json | config_shipped_exact (1) | |
| take every setting from --config | tool.zip | altered_config_outputs_exact (3) | |
| dev profile | profile_dev.json | profile_dev_keys_exact (5), profile_dev_values_exact (5) | r4_tests_nested_group_bounds, r7_recomputes_key_outside_compiler |
| prod profile | profile_prod.json | profile_prod_keys_exact (5), profile_prod_values_exact (5) | r1_compares_window_ends_with_observations |
| rejects | validation_report.json | audit_rejects_exact (5) | |
| unresolved | validation_report.json | audit_unresolved_exact (3) | |
| held grants | validation_report.json | audit_held_grants_exact (3) | r3_derives_grant_start_from_approvals |
| unattested | validation_report.json | audit_unattested_exact (3) | |
| separation of duties | validation_report.json | audit_sod_exact (3) | |
| self check | validation_report.json | self_check_partition_exact (3) | |
| summary identities | summary.json | summary_identity_triangle (3) | |
| artifacts come from the tool | all JSON | artifacts_reproduce_from_tool (1) | r16_claims_unrun_check_passed, r17_claims_success_against_evidence |
| report transcript and repairs | report.json | report_transcript_complete (1), negative_report_digest_mismatch (-3) | |
| literal shapes | all JSON | artifacts_parse_with_contract_shapes (1), artifacts_contract_layout (1), negative_wallclock_fields (-1) | |
| exactness bar | all | every exact check | |
| leave /app/data unchanged | none | none | r12_writes_under_app_data |
| stdlib only, no installs, no lookup | none | none | r13_runs_package_install, r14_runs_online_lookup, r11_reads_grader_files, r15_repeats_failing_command |
| withheld conventions from evidence | message | none | r2_checks_hr_clock_on_termination_days, r10_names_shipped_conventions |

## Root cause

**Crux.** A profile key exists only when a chain of individually simple facts holds at one instant under one knowledge horizon, and the three conventions that place every boundary of that chain are left to evidence that the agent must evaluate the way the gateway does.

**Spine.** The per key value `min(max(components), employment bound, security caps)` threads through both profiles, the unattested and separation of duties lists, the summary counts and every held-out comparison; one wrong boundary moves keys in all of them.

**Interaction matrix.** Visibility gates every source; identity resolution feeds memberships, grants, approvals, rotas and attestations; employment on the HR clock feeds eligibility, approver qualification and contractor cover; the grant start feeds the ceiling, the freeze test and the separation of duties order; attestation runs before separation of duties; security caps run last.

**Withheld-rule evidence.** `access_attestations.csv` rows at grant ends and starts (window convention), rows on termination days at sites with non zero offsets (HR clock), rows between `effective_from` and approval completion and between the k-th and a later approval (grant start). Each alternative reading contradicts some rows; the true reading contradicts none. Every corpus carries such rows for its own reading.

**Red lines.** Observations decide the conventions only, never a profile key directly; no shipped value or shipped convention may be hardcoded; the delivered tool must work from `--data` and `--config` alone.

## Solution shape

1. Extract the archive and read the contract against each module.
2. Replace the instant parser with the exact grammar and the zone conversion with the table rule.
3. Fix configuration layering: cutoff, effective order, null cancel, ceiling minimum.
4. Fix identity: account winner, alias precedence and case.
5. Fix employment, contract cover and MFA.
6. Fix directory visibility, the widest route and window ends.
7. Fix tickets: duplicates, approvals, grant start, ceiling base, corrections, revocation units, freeze ends, held list.
8. Fix security revocation timing, shift carry, attestation and separation of duties.
9. Register `summarize`, fix the summary key, refuse missing inputs.
10. Run the five subcommands, write the report, package the archive deterministically.

## Ordered plan

1. Read `corpus_index.md` and the seven contract documents; list record ids and units (reads the docs; advances report.json repairs).
2. Extract `/app/data/tool.zip` to a scratch directory and run each subcommand to see the crashes (tool.zip).
3. Compare each module with the contract and list the defects (tool.zip).
4. Build a gateway evaluator at arbitrary instants and score each candidate reading of the three withheld conventions against `access_attestations.csv`; put that search inside the delivered tool so each corpus settles its own reading (profiles, every conv tier). The reference keeps that search in a new module, `gateway.py`, which `audit.py` calls when it builds the compiler.
5. Repair `wtime.py`: grammar, zones, site clock (profiles).
6. Repair `policy.py` and confirm `prod.max_grant_hours` (config.json).
7. Repair identity and account resolution in `engine.py` (validation_report.json unresolved).
8. Repair employment, contracts and MFA (profiles, summary eligibility).
9. Repair directory and bindings (profiles).
10. Repair tickets, approvals, corrections, revocations and freeze (profiles, held_grants, rejects).
11. Repair rota carry, security timing, attestation and separation of duties (profiles, unattested, sod).
12. Repair `cli.py`, `audit.py` and `corpus.py` (summary.json, refusal on missing input).
13. Run resolve-config, compile for both profiles, audit and summarize over `/app/data` (five JSON artifacts).
14. Confirm determinism under row shuffles and the summary identities (summary.json).
15. Write `report.json` with digests and repairs; package `tool.zip` (report.json, tool.zip).
16. Name, for each convention, the reading the shipped observations show (closing message).

## Pitfalls

| Rank | Failure mode | Rule violated | Check or criterion | Weight at stake |
|---|---|---|---|---|
| 1 | trusting legacy boundary code | window convention | profile_prod_keys_exact, profile_dev_keys_exact, boundary_tier_profiles_exact | 13 |
| 2 | UTC day reading of HR dates | site clock | profile_prod_values_exact, heldout_tier_a_profiles_exact | 10 |
| 3 | grant live at requested start | grant start | heldout_tier_b_profiles_exact, heldout_audit_exact | 10 |
| 4 | lenient `fromisoformat` | strict grammar | audit_rejects_exact | 5 |
| 5 | milliseconds read as seconds | unit per file | self_check_partition_exact | 3 |
| 6 | last writer for ceilings | ceiling minimum | config_shipped_exact, config_heldout_resolution_exact | 4 |
| 7 | aggregates right, units wrong | per unit exactness | summary_identity_triangle | 3 |
| 8 | first seen tie handling | governing versions | negative_output_depends_on_row_order | 1 |
| 9 | hand written artifacts | tool produced files | artifacts_reproduce_from_tool, negative_report_digest_mismatch | 4 |
| 10 | shipped conventions hard coded | conventions of each corpus | conv_1_dev_profile_exact to conv_8_prod_profile_exact | 80 |

The top three carry 33 and the conventions row 80 of the 155 positive test weight.

## Provenance

```yaml
uuid: ccfddc1b-09dc-414b-b2fb-595320e4e229
instance_id: warrant-asof-entitlement-compiler
task_name: terminal-bench/warrant-asof-entitlement-compiler
fix_patch_sha256: b95d5be1c34d70991c177aec6fe80e1d010fece2902c2906ced7598f3087382e
solve_py_sha256: 81c4ddcf8b57d0fc4f12c15fdbdaeb1ebc242c69ff32e8118f9af52f12669c6b
language: python
```
