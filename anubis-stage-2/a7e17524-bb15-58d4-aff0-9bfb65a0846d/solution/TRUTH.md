# TRUTH.md - a7e17524-bb15-58d4-aff0-9bfb65a0846d

## Defect

The Hollowbrand package relay has to close cycle RC-2411. The evidence under `/app/data` carries
fifty three independent sources that disagree with each other in documented ways, and the relay
service under `/app/service` accepts promotions only in an order its own reducer admits. Nothing in
the shipped material tells an operator which rule wins where. The work is to settle the whole
roster, drive the service, and write the seven cycle artifacts.

1. **(focal)** Every promotion request has to be reduced to one governing row. Requests live in
   `promotion_requests.jsonl` with 2131 rows, of which 1864 fall outside the half open horizon and
   90 are superseded duplicates in 45 groups of three. The governing row of a duplicate group is the one with the greatest
   `recorded_at`, broken by the greatest `priority_hint`, broken by last position in file order; it
   sits first in 8 groups, in the middle in 10 and last in 27. Getting this wrong defeats
   `decision_roster_is_the_governing_request_set` and trips
   `negative_duplicate_request_rows_were_counted`.
2. **(focal)** Each of the 177 governing candidates has to receive exactly one reason code from the
   seventeen code registry, selected by the registry `order` field from every gate that fires. The
   codes settled before capacity are graded by `pre_capacity_reason_codes_are_exact` and the codes
   capacity settles by
   `capacity_family_reason_codes_are_exact`, so a mis-ordered gate and a mis-settled pool are
   visible on separate axes.
3. **(focal)** Revisions are written `E:MAJ.MIN.PAT-BLD` and have to be compared as the integer
   tuple named by `revision_grammar.json`. Text comparison inverts the order of `0:9.2.0-7` against
   `0:10.0.0-1`, which flips regression tests, quarantine floors and dependency minimums at once.
   Defeats every weight five check.
4. **(drift)** Membership is seated from `channel_membership_snapshot.csv` at the greatest
   `snapshot_seq`, then raised by the four `mirror_index_*.tsv` files, counting only rows in the
   published state whose `published_at` reaches the decision instant. 9187 mirror rows sit in another
   state and 466 published rows are later than the cut. The registry in `platform_suffixes.json`
   lists `_ARM64` ahead of `_LINUX_ARM64`, so a label ending in the longer form leaves a body with
   two underscores and names no unit at all; six planted published rows exploit that. Mis-seating
   moves the adjacency head and defeats `promoted_seating_matches_the_cycle`.
5. **(focal)** Channel capacity is a reserved pool per risk tier plus a general pool that is
   `max(0, budget - reserved_tier1 - reserved_tier2)`, and the tier two reserve falls as the offers
   proceed. Two requests in one channel bound by a requirement the channel did not already seat form
   a pair, and the pair holds a rollback slot against the tier two reserve the moment its second
   member takes capacity. A request is offered a seat only where the channel can cover it both ways,
   one slot plus the hold on every pair its admission completes, and otherwise it carries the
   capacity code consuming nothing while later ranks are still offered what is left. Eight pairs
   hold eleven slots, six requests are refused for want of cover while their pools are still open,
   and three channels end with an empty reserve. The settlement is therefore a fixpoint: the reserve
   decides who is offered a seat and who is offered a seat decides the reserve. No file states a
   settled pool figure. Defeats `capacity_family_reason_codes_are_exact`,
   `rollback_cover_and_closure_depth_are_exact`, `admitted_sequence_matches_the_cycle` and
   `seat_sequence_numbers_match_the_draw`.
6. **(trap)** `site_freeze_windows.csv` holds `hold_len` in hours while `recurring_holds.csv` holds
   the same column name in minutes, and both windows are expressed in site local wall time. The site
   offsets in `site_clock_offsets.csv` change inside the horizon for frankfurt, reston and dublin.
   Defeats `pre_capacity_reason_codes_are_exact`.
7. **(trap)** A row in `qa_verdicts_site.csv` displaces the central report only when a governing
   grant in `delegation_grants.json` names the owning site and family and the site row is strictly
   later than the central row. Four later site rows have no grant. Defeats
   `pre_capacity_reason_codes_are_exact` and `mode_comparison_matches_the_cycle`.
8. **(trap)** After the capacity pass the held set is revalidated for dependency closure until a
   pass evicts nobody, under a published bound of four. A planted chain four deep loses its head to
   the cover refusal, so the first pass evicts six holders, the second evicts three and the third
   evicts one, ten over the cycle, and the fourth pass evicts nobody. The vacated
   slots are left empty. Stopping after one pass or reallocating a vacated slot defeats
   `admitted_sequence_matches_the_cycle`, `rollback_cover_and_closure_depth_are_exact` and
   `capacity_family_reason_codes_are_exact`.
9. **(trap)** Three candidates have no alias binding at all and resolve through a trusted builder
   attestation; five others resolve to nothing and carry `alias_unresolved`. Each fallback reference
   carries two trusted attestations sharing one `signed_at`, the decoy filed under the lower
   identifier, so the published rank of greatest `signed_at` then builder precedence is the only
   route to the right unit. Skipping the fallback or ranking by identifier defeats
   `decision_roster_is_the_governing_request_set`.
10. **(trap)** Carry forward escalation rewrites a deferral into `carry_forward_exhausted` only when
    the row for cycle RC-2411 shows `carry_count` at or above three and `reset_flag` is other than
    `Y`, and never when the blocking code is `budget_exhausted`. Defeats
    `unresolved_and_escalations_are_exact`.

### Trap record incidence

| Trap | Source file | Firing records | Graded value that changes |
| --- | --- | --- | --- |
| Duplicate request groups | promotion_requests.jsonl | 45 groups, 90 losing rows | roster identity, audit_count |
| Out of horizon rows | promotion_requests.jsonl | 1864 | audit_count, every total |
| Boundary rows | promotion_requests.jsonl | 6 at the four edges | audit_count |
| Catalog generation drift | unit_catalog.csv | 480 future rows, 2 wrong tier patterns | risk_tier field, tier pools |
| Alias absent | alias_bindings.csv | 3 refs with no row | unit_key, alias_unresolved |
| Alias retired at the cut | alias_bindings.csv | 2 rows retired at D | alias_unresolved count |
| Builder fallback | builder_attestations.jsonl | 3 references, 5 trusted rows, 98 untrusted | unit_key resolution |
| Competing attestation rank | builder_attestations.jsonl | equal signed_at pairs, decoy filed first | unit_key resolution |
| Mirror state filter | mirror_index_*.tsv | 9187 non published rows | seated revision, adjacency |
| Mirror publication cut | mirror_index_*.tsv | 466 late rows | seated revision |
| Suffix registry order | platform_suffixes.json, mirror_index_*.tsv | 6 planted long suffix rows | seated revision, regression |
| Snapshot sequence | channel_membership_snapshot.csv | 1920 stale rows | boot seating |
| Withdrawal governing row | withdrawal_notices.jsonl | 5 active, 7 revoked later | withdrawn_revision, rate |
| Embargo horizon split | embargo_records.jsonl | 6 beyond, 7 pending | embargo_active, embargo_pending |
| Supersession void | supersession_chains.csv | 2 chain rows naming a replacement with no record | embargo release instant, settled on balance |
| Blank central verdict | integrity_reports_central.jsonl | 2 empty verdict rows | attestation_failed |
| Site override authority | qa_verdicts_site.csv | 3 with grant, 4 without | attestation_failed |
| Freeze length unit | site_freeze_windows.csv | 1468 active, 962 revoked | freeze_window |
| Hold length unit | recurring_holds.csv | 2427 rows, 4 signal holds | recurring_hold |
| Hold exceptions | hold_exceptions.csv | 1002 cancel, 1102 shift | recurring_hold |
| Clock offset change | site_clock_offsets.csv | 3 sites change inside horizon | freeze_window, recurring_hold |
| Seal history filter | relay_audit.log | 47 seals, 1 aborted, 2 rolled back | channel_cooldown |
| Requirement scope | unit_revision_requires.csv | 718 rows out of scope | missing_dependency |
| Legacy fallback | dependency_declarations_legacy.tsv | 4 candidates sourced | missing_dependency |
| Prior cycle scope | prior_cycle_decisions.csv | 990 RC-2410 rows of 2932 | repeat_deferral_count |
| Carry cycle scope | carry_forward_state.csv | RC-2411 rows only | carry_forward_exhausted |
| Waiver business days | waiver_records.jsonl | 3 live, 3 expired | freeze_window |
| Quarantine floor | quarantine_directives.json | 3 in force, 1 expired | quarantine_floor |
| Bulletin action filter | release_bulletins.json | 5 rows with another action | risk_tier_blocked |
| Reserved pool clamp | channel_budgets.ini | 4 channels, edge clamps to 0 | budget_exhausted |
| Rollback cover per pair | channel_budgets.ini, relay_policy_baseline.json | 8 bound pairs, 11 slots held | budget_exhausted, admitted set, rollback_holds |
| Hold size fallback | channel_budgets.ini | staging publishes no charge, hold is 2 | staging admitted set |
| Cover refusal before a slot | unit_revision_requires.csv | 6 refusals with pools still open | budget_exhausted |
| Eviction cascade | unit_revision_requires.csv | 6 then 3 then 1 over three passes | missing_dependency, closure_passes |
| Requirement rings | unit_revision_requires.csv | rings of 2, 3 and 4, 11 members | cycle_unresolved |
| Derived batch limit | channel_budgets.ini | advisory cap 40 over 4 channels | calls, batch_limit |
| Share apportionment | metrics_definitions_spec.md | 3 non zero channels, naive sum also 100.00 | coverage_share_pct |
| Draw accounting in the digest | metrics_definitions_spec.md | every admitted draw | dependency_digest |
| Declared boundaries | boundary_semantics.json | 15 comparisons, 5 census scopes, 3 used by the message | every instant comparison |

Out of bounds: nothing here is recovery of damaged bytes, decoding, cryptography or reverse
engineering of an opaque format. Every file is plain text and well formed, every
rule that decides a graded value is stated in one of the twelve specification documents, the
operator notes or a configuration file that the specifications name, with one exception: no file
says what a supersession row naming a replacement embargo with no record does. The solution follows
the chain as written, so the two requests behind those rows carry no embargo, and it reports that
reading as settled on balance in the closing message. The difficulty is the volume of interacting
rules rather than any puzzle. No shipped file carries a worked answer, and the service never reports
whether a decision was right.

## Load-bearing work

Twelve specification documents carry a `## Normative parameters` block, and the operator notes
carry one more fenced block; their `key: value` lines are read by the solution: the request table name and the evidence file count, the duplicate
rank fields and the request priority field, the ladder and the two state words, the three
separators, the two length units and the weekday base, the closure pass bound and the ready
tiebreak, the channel blocked for an indeterminate verdict, the general pool floor, the reserve
floor, the hold scope and source and fallback, the rank
fields, the rounding places and digest width, the replay count and the seal sequence, the JSON
indent, the mode and scenario names, and the reseal cooldown hours. Deleting any one of the fifty three files stops the solution from producing a complete artifact
set.

The service is a pure reducer in `relay_core.py` behind a threaded HTTP front end in
`relay_service.py`, with a small CLI in `relay_client.py`. It boots from the snapshot and the mirror
indexes, admits a promotion only when the target channel is the seated head or one rung above it,
refuses a revision at or below the seated one, refuses an operation whose requirement is unseated,
refuses anything on a sealed channel, fails a whole call carrying more than the derived limit of operations, aborts a whole call on the first refused operation,
and replays a stored answer for a repeated idempotency key. The runbook fixes the call pattern:
fill each call to the limit, then close with one final call carrying only the four seal operations
in ladder order, and the runbook then repeats the first promote call once so the transcript carries
exactly one replay. `tests/test_output.py` embeds a zlib and base64 copy of `relay_core.py`, byte
for byte the shipped module, and imports it to replay probe operations against the delivered
`final_state.json`; it never runs anything the agent wrote.

## Verification

The test channel registers thirty one checks. Eight carry weight five, nine carry weight three, three
carry weight one, and eleven are negative: five plus three plus three plus three plus three plus three
plus one plus one plus one plus one plus one. Positive weight totals seventy and negative magnitude
totals twenty five, so the registered positives equal the seventy used for the test fraction.

The negative checks are `negative_requests_outside_the_horizon_were_adjudicated`,
`negative_duplicate_request_rows_were_counted`, `negative_reason_codes_outside_the_registry`,
`negative_state_was_never_moved_by_the_service`, `negative_batch_limit_was_ignored`,
`negative_scenarios_repeat_the_baseline_counts`, `negative_mode_delta_disagrees_with_its_own_modes`,
`negative_artifacts_carry_dynamic_fields`, `negative_extra_files_sit_in_the_output_directory`,
`negative_final_state_seats_a_rejected_unit` and `negative_hardcoded_sample_answers`. Each returns
False when the artifact it reads is absent.

The judge channel registers thirty three criteria, R1 through R33, with seventy seven positive weight
and twenty two negative magnitude. R1 through R10 grade the ten counterfactual figure groups in the
closing message, R11 through R17 grade the capacity derivations in the trajectory, R18 and R19 grade
the service exchange and the hold length unit, R20 grades the one
ordering rule the instruction states, R21 and R22 grade honest reporting, R23 grades code shape, and
R24 through R33 are the negatives. R1 through R17 all turn on the settled capacity, so the positive
weight that survives a wrong settlement is the six carried by R18 through R23. The judge reads the
trajectory and the closing message, and the workspace for R23, R27 and R33; the tests read only
artifact bytes.

| Requirement | Artifact or channel | Graded by |
| --- | --- | --- |
| Governing request roster | report.json decisions | decision_roster_is_the_governing_request_set |
| Reason code settled before capacity | report.json decisions | pre_capacity_reason_codes_are_exact |
| Reason code for a capacity block | report.json decisions | capacity_family_reason_codes_are_exact |
| Cover held and revalidation depth | summary.json | rollback_cover_and_closure_depth_are_exact |
| Seat sequence follows the draw | final_state.json channels | seat_sequence_numbers_match_the_draw |
| Admission order | report.json admission_order | admitted_sequence_matches_the_cycle |
| Seating after the cycle | final_state.json channels | promoted_seating_matches_the_cycle |
| Untouched seats answer probes | final_state.json channels | inherited_seating_answers_unseen_probes |
| Strict against delegated | scenario_mode.json | mode_comparison_matches_the_cycle |
| Seals close every channel | final_state.json sealed | every_channel_refuses_a_probe_after_the_close |
| Totals reconcile | summary.json | summary_totals_reconcile_with_the_report |
| Admission rate places | summary.json | admission_rate_is_exact |
| Coverage shares sum to 100 | summary.json | coverage_shares_follow_the_largest_remainder |
| Repeat deferral and digest | summary.json | repeat_deferral_and_digest_are_exact |
| Shifted decision instant | scenario_alpha.json | alpha_scenario_matches_the_shifted_instant |
| Withdrawn evidence layers | scenario_beta.json | beta_scenario_matches_the_withdrawn_layers |
| Unresolved and escalations | report.json | unresolved_and_escalations_are_exact |
| Call accounting | transcript_summary.json | transcript_accounting_reconciles_with_the_state |
| Contract key sets | all seven artifacts | artifacts_carry_the_contract_keys |
| Artifacts are plain files | all seven artifacts | artifacts_are_bounded_regular_files |
| Horizon filter respected | report.json decisions | negative_requests_outside_the_horizon_were_adjudicated |
| Duplicates discarded | report.json decisions | negative_duplicate_request_rows_were_counted |
| Codes inside the registry | report.json | negative_reason_codes_outside_the_registry |
| Service actually moved | final_state.json | negative_state_was_never_moved_by_the_service |
| Batch limit honoured | transcript_summary.json | negative_batch_limit_was_ignored |
| Scenarios differ from baseline | scenario_alpha.json, scenario_beta.json | negative_scenarios_repeat_the_baseline_counts |
| Mode delta self consistent | scenario_mode.json | negative_mode_delta_disagrees_with_its_own_modes |
| No clock or host fields | all seven artifacts | negative_artifacts_carry_dynamic_fields |
| No stray output files | /app/out | negative_extra_files_sit_in_the_output_directory |
| Seats agree with the decisions | final_state.json and report.json | negative_final_state_seats_a_rejected_unit |
| Totals are settled rather than copied from the budget file | summary.json | negative_hardcoded_sample_answers |
| Counterfactual figures | closing message | R1 through R10 |
| Capacity derivation evidence | trajectory | R11 through R17 |
| Service exchange and hold units | trajectory | R18, R19 |
| Decisions before calls | trajectory | R20 |
| Honest reporting | closing message | R21, R22 |
| Program shape | trajectory and workspace | R23 |
| Evidence left alone | /app/data | R33 |

## Root cause

Four independent axes make the cycle hard rather than long. Bi-temporal resolution: ten tables
carry both `effective_at` and `recorded_at`, and the governing row is the greatest `recorded_at`
among rows whose `effective_at` reaches the decision instant, with the row identifier as the
tiebreak, so a row recorded later about an earlier effect still wins. Authority layering: a central
verdict yields to a site verdict only under a governing grant, a baseline risk tier yields to a site
denial and then to a bulletin allowance, and a quarantine floor outranks every bulletin. Temporal
geography: freeze windows and recurring holds are written in site local wall time with different
length units, over offsets that change inside the horizon, and waiver expiry counts business days
against a per site calendar. Dependency and capacity coupling: requirements are met by existing
seating or by co-candidates in the same channel, a cycle between two co-candidates refuses both,
capacity ranks by tier, release instant and unit key, and the held set
is revalidated until stable with no reallocation. The coupling runs both ways and this is the crux.
A channel's tier two reserve is drawn down as the offers proceed, because every pair of co-admitted
requests bound by a requirement holds a rollback slot against that reserve, and the hold lands when
the second member of the pair takes capacity. So the reserve that decides whether a request can be
offered a seat depends on which earlier requests were offered seats, and no file states a settled
pool figure. A solver that reads capacity forward out of the configuration layer admits requests the
channel could never cover both ways, which keeps a provider alive that the cycle actually refuses,
which keeps its dependents alive through the revalidation, and the three pass eviction cascade never
happens. Every count in the artifacts stays well formed and internally consistent while the
admitted set, the shares, the digest and the revalidation depth are all wrong. The admission order
tiebreak closes the loop by counting the requirement rows each candidate satisfies for its own
channel.

**Red lines.** Do not reallocate a slot vacated by the closure pass. Do not count a withdrawn
request in the admission rate denominator while leaving it in the audit count. Do not compare
revisions as text. Do not let a bulletin lift a quarantine floor. Do not let a site verdict displace
a central verdict without a governing grant. Do not read the freeze length in minutes or the hold
length in hours. Do not seal a channel before its promotions are applied. Do not read a pool figure
forward out of the configuration layer. Do not charge rollback cover per member where the channel
publishes no charge of its own. Do not offer a seat the channel lacks the reserve to cover both
ways. Do not stop the revalidation after one pass.
Do not treat a requirement ring of three or four members as if only pairs closed. Do not read the
batch limit as a literal. Do not round the channel shares independently. Do not probe the relay with
speculative operations: one refusal costs the whole call and the aborted call is counted.

## Solution shape

`solve.py` loads every table and every normative block into one `Evidence` object, reduces the
request table to 177 governing candidates, resolves each content reference through alias bindings
and then through trusted builder attestations, reads the governing catalog row for risk tier and
owning site, and gathers requirements from the primary table or, when that table holds no row for
the pair at all, from the legacy declarations. It then runs every gate, selects the lowest `order`
code that fired, refuses requirement cycles, applies the dependency pass, ranks for capacity and
offers each seat only where the reserve covers it both ways,
revalidates the held set until a pass evicts nobody, rewrites eligible deferrals into the escalated code, orders the
admitted set topologically with the ready tiebreak, drives the live service through batches of
the derived batch limit plus one replayed call and one seal call, and writes the seven artifacts. The same
adjudication runs three more times under option flags for the shifted instant, the withdrawn
evidence layers and the strict verdict mode.

## Ordered plan

1. Read the twelve specification documents and the operator notes and collect their normative
   parameter blocks.
2. Load the configuration layer and the reason code registry with its `order` field.
3. Reduce the request table to governing in horizon rows.
4. Resolve content references to unit keys, alias first and trusted attestation second.
5. Seat membership from the snapshot and raise it with the published mirror rows.
6. Evaluate adjacency, regression, withdrawal, quarantine, embargo, attestation, risk tier,
   cooldown, freeze and hold for every candidate.
7. Select the lowest ordered firing code per candidate.
8. Refuse requirement cycles among surviving co-candidates.
9. Apply the dependency pass against seating plus same channel co-candidates.
10. Rank for capacity by tier, release instant and unit key, consume reserved pools before the general pool, and
    hold rollback cover against the tier two reserve as each bound pair completes.
11. Revalidate the held set until a pass evicts nobody and leave vacated slots empty.
12. Rewrite eligible deferrals into the escalated code and record the original code.
13. Order the admitted set topologically with the tier, requirement rows served and unit key
    tiebreak.
14. Start the service, apply full batches, seal in ladder order in one call, then replay the first
    call once.
15. Compute the metrics and write the seven artifacts.
16. Re-run the adjudication for the two scenarios and the two verdict modes.
17. Close with the ten counts the instruction asks for, the source of each, and the supersession
    reading kept apart as settled on balance.

## Pitfalls

| Rank | Mis-handling | Test fraction retained |
| --- | --- | --- |
| 1 | Rollback cover never charged against the reserve | 0.0857 |
| 2 | Cover charged but no request refused for want of it | 0.0857 |
| 3 | Revalidation stopped after one pass | 0.0857 |
| 4 | Hold length read in hours | 0.1143 |
| 5 | Cover charged per member where no charge is published | 0.2000 |
| 6 | Freeze window matched in UTC | 0.4714 |
| 7 | Service count dropped from the order tiebreak | 0.7286 |
| 8 | Pool and draw position dropped from the digest | 0.8714 |
| 9 | Repeat deferral counted against any prior cycle | 0.9571 |
| 10 | Withdrawn request left in the rate denominator | 0.9571 |

The top three rows are the same defect seen from three sides, and each is the whole of what a
forward reading of the configuration layer produces, so a solver that never settles the capacity
fixpoint keeps only the weight three check on the codes decided before capacity, the weight one
check that every channel closed, and the two weight one shape checks. That is six of seventy, the
floor behind the instruction's warning that a single wrong figure costs its artifact: a complete, well formed, internally
consistent artifact set that is wrong in the admitted roster, the shares, the digest, the seat
sequence and the revalidation depth at once. At the other end one wrong metric fact costs about one
fact, 0.9571 of the test half. Two rules carry no cost on this cycle and neither is hidden. Running
the revalidation to the published bound rather than to stability gives the same answer here, because
three passes settle it and the bound is four, and the dependency document says the bound has never
been reached in a closed cycle. Rounding the three non zero channel shares independently also gives
the same answer here, a naive sum of 100.00, because nine, twenty four and thirteen of forty six happen to round to a sum
of exactly one hundred, so the largest remainder rule is correct and stated but not load bearing on
this cycle.

## Provenance

```yaml
uuid: a7e17524-bb15-58d4-aff0-9bfb65a0846d
instance_id: a7e17524-bb15-58d4-aff0-9bfb65a0846d
task_name: terminal-bench/a7e17524-bb15-58d4-aff0-9bfb65a0846d
fix_patch_sha256: f11944d4b73bb64247d161c432fd21e1e2d36dc7064c95492b8626d692197191
solve_py_sha256: c10c1bcd120c171598add768db5810d5c007d12e4fef7f1181da055df4ba8d4b
language: python
```
