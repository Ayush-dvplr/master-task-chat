# TRUTH.md - speculative-decode-arbiter

Author side record. Not shipped to the agent.

## Defect

Nothing in this bundle is broken. The task is a deterministic replay, and what
makes it hard is the number of documented rules that have to be simultaneously
right before any deliverable is. The list below names the difficulty carriers
rather than faults, classified so a reviewer can see the budget at a glance.

1. **(focal) The acceptance algebra runs over classes, never identifiers.** The
   shipped alias table collapses 60 token pairs onto a shared class, so two
   positions agree without carrying the same token. A replay comparing
   identifiers reports a shorter prefix on roughly a third of windows. Fixture:
   any window whose verdict carries the paired member rather than the drafted
   one.

2. **(focal) The seed of the draft width schedule is a fixed point.** The
   policy K of each window follows a moving average of acceptance, and the seed
   that schedule starts from is recalibrated from the pooled ratio the schedule
   itself produces. A single forward pass is wrong for 105 of the 241 streams, 116
   take more than one pass, and 16 streams never settle and must be stopped at the documented cap of 6 and
   reported. Fixture: every stream whose `passes` column exceeds 1.

3. **(focal) The agreed prefix and the lease span do not commute.** The prefix
   is resolved over the policy truncated vectors and only then does the span
   bound how many of those tokens were accepted. Applying the span first is
   self consistent and wrong. Fixture: the 456 windows whose accepted count
   comes out below their agreed prefix.

4. **(drift) Repairing a malformed record looks like rejecting it.** Six
   documented malformations each carry a repair and none is a rejection, so no
   window is ever dropped. The experienced instinct is to filter the corpus
   clean first. Fixture: 70 windows at `R01`, 79 at `R02`, 149 at `R03`, 120 at
   `R04`, 83 at `R05` and 98 at `R06`.

5. **(drift) A position the target never answered looks like a disagreement.**
   Repair `R04` extends a short verdict with the void token, and those extended
   positions are voided rather than rejected. Treating them as ordinary
   disagreements still sums to the drafted count and is still wrong. Fixture:
   the 120 windows carrying `R04`.

6. **(trap) A tier two field reaches forward to a tier four one.** The window
   index carries the band its stream ends the period in, which is only known
   once that stream's schedule has settled. A single forward pipeline produces
   a plausible wrong column and every reader of it inherits the error.

7. **(trap) Equal ranks do not preempt.** A revocation takes effect only when
   the issuing rank is strictly greater. Equal ranks invert. Fixture: the
   233 ignored revocations across 15 distinct slots, 86 of them at equal rank,
   and the 92 windows carrying two revocations, where only the earlier one that
   takes effect moves the expiry.

8. **(trap) Cancellation splits two ways that never overlap.** A window granted
   at or after the cancellation tick is reclaimed whole; one granted before it
   merely has its lease shortened. Fixture: 15 straddling windows against 16
   cancelled streams that reclaimed nothing.

9. **(trap) An empty group still emits its row.** Tenant `T10` owns no stream
   and slot `S15` was never leased, and both still appear carrying zeros, as
   does every repair code with no instances. Fixture: the `T10` and `S15` rows.

10. **(trap) The allowance binds after aggregation.** A tenant cap is the sum
    of its streams' allocations and is applied to the tenant total, never to a
    stream. Fixture: the 7 tenants whose gross cost exceeds their cap.

11. **(trap) Two files record a tenant and only one is authoritative.** The
    master record carries an advisory tenant that disagrees for 23 of the 240
    streams. Fixture: those 23 streams.

12. **(trap) Canonical form, fixed width sequence, and one artifact sorted
    differently.** Identifiers are emitted upper case with hyphens although
    they arrive lower case with underscores, sequence numbers keep four digits
    of leading zeros, and `lease_grants.psv` is ordered by slot rather than by
    window identifier like everything else.

13. **(trap) Only one message identifier cancels anything.** The journal also
    carries `STREAM_ADMIT` and `LANE_HEARTBEAT` records at the same shape.
    Fixture: 241 admission records and 81 heartbeats against 39 cancellations.

The corpus emitter and the grader share one model text so the shipped bytes
and the bytes the grader regenerates cannot drift. The oracle is deliberately
NOT part of that: solution/solve.py was written separately from the shipped
specification, with its own parsers, its own data shapes and its own rounding
implementation. Run against the shipped corpus the two agree on 19 of the 20
content artifacts byte for byte, and the twentieth, the manifest, differs only
in the digest of the driver file itself, which is correct because the two
drivers are different files. Two independent implementations agreeing is the
evidence that the specification is unambiguous; an oracle lifted out of the
grader would have proved nothing.

Every rule the replay applies is written out in full in
`environment/data/SPEC-SDA.md` and its three appendices, and the difficulty is
the breadth and interaction of those documented rules rather than anything
withheld. No graded value depends on a seed, a constant or a file the agent
cannot read.

## Load-bearing work

Twenty one declared artifacts across five tiers. The tier is the number of
upstream deliverables whose correctness the artifact needs.

Tier 1, corpus only: `stream_registry.csv`, `token_classes.json`.

Tier 2, one parent: `lease_grants.psv`, `cancel_timeline.jsonl`. Note that
`window_index.tsv` is emitted at this tier but is not graded at it: its
terminal_band column reaches forward to the settled schedule, so its
correctness sits behind three or more upstream deliverables.

Tier 3, two parents: `k_schedule.tsv`, `acceptance_ledger.csv`,
`lease_conflicts.tsv`, `reclaim_ledger.csv`, `malformed_repairs.jsonl`.

Tier 4, three or more parents: `window_disposition.csv`,
`token_accounting.tsv`, `stream_metrics.json`, `tenant_cost.csv`,
`inversion_report.tsv`, `nonconvergence_report.jsonl`, `slot_occupancy.tsv`.

Tier 5, closure: `conservation_ledger.json`, `reconciliation.tsv`,
`arbiter_driver.py`, `run_manifest.json`.

The content contract for each is `environment/data/sda-output-formats.md`,
which the instruction names and which is binding on columns, order, delimiter,
header rule and row order.

`reconciliation.tsv` is the closure check. It states the same six figures from
two independent aggregations, one over the per window ledger and one over the
per stream accounting, and neither may be copied from the other.

## Verification

The reward combines two channels with `tests/reward.toml`, each worth half:

- test channel `tests/test_output.py`: 30 rewardkit checks, positive total 94, negative total -24; weight `0.005319148936170213` (0.5 divided by the positive total).
- judged channel `tests/judge.toml`: 24 criteria, positive total 78, negative total -16; weight `0.00641025641025641`.

Every positive passing and no negative firing scores 1.0, an empty run scores 0.0, and the floor is -1.0. rewardkit runs the checks concurrently, so every check that runs the delivered program works in private directories, runs it as `nobody` with a minimal environment in its own session, and kills everything it started before returning.

Positive checks:

| check | weight | grades |
|---|---|---|
| `declared_artifacts_exist_and_parse` | 1 | every declared artifact is present and the structured ones parse. |
| `stream_registry_matches_reference` | 3 | the canonical stream registry, whole file. |
| `token_classes_matches_reference` | 1 | the token to class map, in token ordinal order. |
| `window_index_matches_reference` | 3 | the window index including the band each stream ends in. |
| `lease_grants_matches_reference` | 3 | lease grants with effective expiry and span, in slot order. |
| `cancel_timeline_matches_reference` | 3 | the cancellation timeline with after and straddling counts. |
| `k_schedule_matches_reference` | 5 | the settled policy K schedule per stream. |
| `acceptance_ledger_matches_reference` | 5 | per window acceptance under the settled schedule. |
| `lease_conflicts_matches_reference` | 3 | every recorded revocation and its disposition. |
| `reclaim_ledger_matches_reference` | 3 | reclaim totals for each cancelled stream. |
| `malformed_repairs_matches_reference` | 1 | the six repair codes with their instance counts. |
| `window_disposition_first_section_matches_reference` | 5 | window disposition, first third, graded whole. |
| `window_disposition_second_section_matches_reference` | 5 | window disposition, second third, graded whole. |
| `window_disposition_third_section_matches_reference` | 5 | window disposition, final third, graded whole. |
| `token_accounting_matches_reference` | 5 | per stream five class accounting with its residual. |
| `stream_metrics_matches_reference` | 5 | per stream pooled ratio, band, moving average and pass count. |
| `tenant_cost_matches_reference` | 5 | tenant service units with the cap applied after aggregation. |
| `inversion_report_matches_reference` | 5 | every priority inversion and the tokens it preserved. |
| `nonconvergence_report_matches_reference` | 5 | the streams that stopped at the recalibration cap. |
| `slot_occupancy_matches_reference` | 5 | per slot occupancy including peak concurrency. |
| `conservation_ledger_matches_reference` | 5 | the run wide conservation identity. |
| `reconciliation_matches_reference` | 5 | the two independent derivations agree line for line. |
| `run_manifest_matches_delivered_files` | 3 | the manifest digests the files actually delivered. Recomputed against the delivered bytes rather than against the reference, so a manifest is correct exactly when it describes what was shipped. |
| `driver_reproduces_unseen_corpus` | 5 | the delivered driver replays a corpus the run never saw. |

Negative checks (each returns true only when its cheat is present):

| check | weight | fires when |
|---|---|---|
| `negative_hardcoded_sample_answers` | -5 | fires when the driver replays the shipped figures whatever corpus it is given. |
| `negative_filename_dependent_behaviour` | -5 | fires when the same corpus under a different directory name grades differently. |
| `negative_nondeterministic_output` | -3 | fires when two replays of one corpus disagree. |
| `negative_degenerate_at_scale` | -3 | fires when a corpus larger than anything shipped yields a truncated replay. |
| `negative_order_dependent_output` | -3 | fires when reordering the recorded rows changes the replay. |
| `negative_wrote_outside_declared_paths` | -5 | fires when the replay litters its output directory. The harness ferries only the declared artifacts into this container, so an extra file beside them is invisible here. What is observable is the driver itself: run it into a clean directory and see what it leaves behind. |

Judged criteria:

| id | weight | kind | criterion |
|---|---|---|---|
| R1 | 3 | conduct | The agent starts the shipped service and drives it through its command line channel and through its HTTP interface, making at least one state change on each. |
| R2 | 1 | outcome | The response names the service channel that carried each state change the run made. |
| R3 | 5 | outcome | The response states the closing figure named windows_at_k8 as the whole number 745. |
| R4 | 5 | outcome | The response states the closing figure named mean_pooled_ratio as the value 0.5668. |
| R5 | 5 | outcome | The response states the closing figure named high_band_streams as the whole number 47. |
| R6 | 5 | outcome | The response states the closing figure named low_band_windows as the whole number 642. |
| R7 | 5 | outcome | The response states the closing figure named lease_limited_windows as the whole number 456. |
| R8 | 5 | outcome | The response states the closing figure named recalibrated_streams as the whole number 105. |
| R9 | 5 | outcome | The response states the closing figure named max_schedule_stream as the identifier SDA-T01-0002. |
| R10 | 5 | outcome | The response states the closing figure named distinct_schedules as the whole number 80. |
| R11 | 5 | outcome | The response states the closing figure named total_billed_units as the whole number 72974. |
| R12 | 5 | outcome | The response states the closing figure named over_cap_tenants as the whole number 7. |
| R13 | 3 | outcome | The response states the closing figure named multi_repair_windows as the whole number 25. |
| R14 | 3 | outcome | The response states the closing figure named max_peak_concurrent as the whole number 21. |
| R15 | 3 | outcome | The response states the closing figure named nonconverged_drafted as the whole number 1032. |
| R16 | 3 | outcome | The response states the closing figure named capped_tenant_drafted as the whole number 7904. |
| R17 | 3 | outcome | The response states the closing figure named high_band_drafted as the whole number 2909. |
| R18 | 3 | outcome | The response states the closing figure named empty_reclaim_streams as the whole number 16. |
| R19 | 3 | outcome | The response states the closing figure named void_disposition_windows as the whole number 113. |
| R20 | 3 | conduct | The agent writes arbiter_driver.py as code a reviewer would accept, with meaningful names, handled errors, no dead or duplicated blocks and no debug residue. |
| R21 | -5 | conduct | The agent reports that the two independent derivations were compared while the transcript shows no command that compared them. |
| R22 | -5 | constraint | The agent edits a file inside the shipped corpus directory. |
| R23 | -3 | conduct | The response reports a closing figure that disagrees with the artifact the run delivered. |
| R24 | -3 | conduct | The agent reissues one identical failing command five or more times during the run. |

Every driver run uses its own corpus copy and output directory; the unseen corpus is built once under a lock. Earlier versions shared fixed paths under /tmp and raced when rewardkit ran checks concurrently, which is why the oracle once scored between 0.89 and 0.97. `negative_degenerate_at_scale` first requires the ordinary unseen corpus to replay exactly, so a driver that writes nothing is not charged for it. The cancellation journal negative was withdrawn: ignoring the journal is a misreading the cancel timeline and reclaim ledger positives already price.

Scores quoted for this bundle are TESTS-ONLY.

## Root cause

**Agreement is an equivalence, not an equality.** The draft service and the
target engine emit tokens from the same vocabulary but from different sampling
paths, so the arbiter compares what a token means rather than which token it
is. Every downstream figure inherits that choice.

**A width policy that reads its own output is a fixed point, not a pipeline.**
Raising the draft width pulls more speculative tokens into each window, which
lowers the acceptance ratio, which lowers the width. The recalibration and the
schedule are therefore solved together and a stream that oscillates is a
documented outcome rather than a bug.

**A buffer lease is a resource bound and acceptance is a correctness question.**
They answer different questions, so they compose in one order only. Bounding
before deciding conflates a token that was wrong with a token that was right
and late, and those two carry different terminal classes and different costs.

**Conservation is what makes a partial pipeline visible.** Every drafted token
lands in exactly one of five classes, so an error anywhere shows up as a non
zero residual at the closure tier even when each artifact looks locally
plausible.

## Solution shape

1. Read the specification and its three appendices, then inventory the corpus
   and work out which of the 50 files carry the five window families.
2. Canonicalise every stream reference and build the registry, taking the
   tenant from the authoritative table.
3. Join the five window families on the canonical stream and the sequence.
4. Apply the six repairs in code order, recording which applied and how many
   verdict positions the target actually answered.
5. Resolve revocations against the rank table, producing an effective expiry
   and a list of inversions.
6. Solve each stream's schedule to its fixed point, capping at 6 passes.
7. Score every window into the five terminal classes at its policy K.
8. Aggregate upward into the per stream, per tenant and per slot views,
   applying the tenant allowance after aggregation.
9. Emit the twenty one artifacts, close the conservation identity, digest the
   files into the manifest, and drive the control plane over both channels.

## Ordered plan

1. Read `SPEC-SDA.md`, `sda-output-formats.md`, `sda-glossary.md`,
   `sda-acceptance-appendix.md`, `sda-lease-appendix.md` and
   `api_contract.md` in full before writing code.
2. Inventory `/app/data` and identify the shard families.
3. Build the parser for all twelve formats.
4. Implement the repairs, the equivalence lookup and the scoring.
5. Implement the schedule fixed point and confirm some streams take more than
   one pass and some reach the cap.
6. Emit the artifacts in the documented shapes and orders.
7. Confirm the residual is 0 and the reconciliation deltas are all 0.
8. Start the service, enact the decisions over both channels. Judged by R1.
9. Write the closing summary naming all seventeen figures and the channel each
   state change used. Judged by R3 to R19 and R2.

## Pitfalls

- Comparing token identifiers rather than classes. Fails
  `acceptance_ledger_matches_reference` and everything downstream.
- Running one forward pass and treating the schedule as settled. Fails
  `k_schedule_matches_reference` and `stream_metrics_matches_reference`.
- Bounding by the lease span before resolving the agreed prefix. Fails
  `window_disposition_first_section_matches_reference` and the conservation ledger.
- Filtering malformed windows out instead of repairing them. Fails
  `malformed_repairs_matches_reference`.
- Counting an unanswered position as a rejection. Fails
  `token_accounting_matches_reference`.
- Filling the band column in one pass. Fails `window_index_matches_reference`.
- Letting an equal rank preempt. Fails `lease_conflicts_matches_reference`
  and `inversion_report_matches_reference`.
- Dropping the empty tenant, the unused slot or a zero count repair code. Fails
  `tenant_cost_matches_reference` and `slot_occupancy_matches_reference`.
- Applying the tenant allowance per stream. Fails `tenant_cost_matches_reference`.
- Sorting `lease_grants.psv` by window identifier. Fails
  `lease_grants_matches_reference`.
- Stripping the leading zeros from the sequence column. Fails
  `window_index_matches_reference`.
- Delivering a driver that carries this corpus's figures. Fails
  `driver_reproduces_unseen_corpus` and fires
  `negative_hardcoded_sample_answers`.

## Provenance

```
solve_py_sha256: c5f2c397702d2f4296e518c9c2efbd522b6873809cdbe9ba93b16c8d14e0053e
test_output_py_sha256: 67211a565f799e84d3a88e6f28001dbd6c631706a046ddcd2e7653b591b658a8
judge_toml_sha256: 8a0948ddcaaa6087ac1145a7f21050016ff6d9e1672c6db20d2018ec52402d0d
instruction_md_sha256: 1fbca9bfb487bba8338e78760f148ea8bcd854918efae0565d52093a8b822dfe
language: python
```
