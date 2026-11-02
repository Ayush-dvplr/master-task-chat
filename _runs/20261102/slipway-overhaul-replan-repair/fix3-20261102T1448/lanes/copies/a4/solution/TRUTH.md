# TRUTH.md - slipway-overhaul-replan-repair

Author-side golden trajectory for `slipway-overhaul-replan-repair`. Not shipped
to the agent.

## Defect

The `slwopt` engine inside `/app/data/project.zip` runs to completion, passes
the suite it carries exactly as it shipped, and writes a full and plausible set
of twenty five documents that are wrong in two different ways at once: the plan
it publishes disagrees with the papers that govern it, and the ledger of work it
publishes beside the plan claims effort the round never owed. Twenty seven
repairs across nine modules (`cells`, `charge`, `graph`, `mutate`, `normalise`,
`objective`, `publish`, `reading`, `search`) carry the fix: the fifteen
catalogued faults `DFC-01` to `DFC-15` below, and `DFC-16` to `DFC-27`, which
`solution/solve.py` applies after them.

1. `DFC-01` (focal) `cells.readers_of` reaches only the job's own demand cell
   when a norm cell moves, so the closed demand of every job whose closure holds
   that job stands at the figure it held before.
2. `DFC-02` (focal) `search.solve_inputs` leaves the rule digests out of the
   solve key, so a charge rule revision reaches the solve cell, finds the key
   unmoved, and reads a stale optimum back out of the store.
3. `DFC-03` (focal) `cells.visit` passes the cascade on from a cell that came
   back with the digest it already held, so the round visits cells no amendment
   touched.
4. `DFC-04` (trap) `charge.norm_inputs` folds the presentation fields into the
   norm key, which only bites once a title revision and a later reversal of a
   governed field meet on one job.
5. `DFC-05` (trap) `mutate.seeds_for` seeds the norm cell for a
   `job_note_revision`, which the classification table gives an empty seed set.
6. `DFC-06` (trap) `mutate.seeds_for` seeds every closure cell of a precinct on
   a capacity revision as well as the solve cell.
7. `DFC-07` (drift) `mutate.seeds_for` seeds nothing for an `edge_withdrawn`, on
   the experienced instinct that removing an edge can only take work away.
8. `DFC-08` (drift) `objective.ranking` returns the charge alone, dropping the
   three keys the objective paper puts behind it.
9. `DFC-09` (trap) `objective.within_capacity` turns down a usage equal to the
   available quantity.
10. `DFC-10` (focal) `normalise.workbook` converts crew shifts at a flat four
    hundred and eighty minutes, which is the retired scale table.
11. `DFC-11` (focal) `normalise.workbook` weights the three pools alike, which
    is the retired scale table.
12. `DFC-12` (drift) `search.sweep` takes the closure rebate of the scaled
    charges alone rather than of the scaled charges and the surcharges.
13. `DFC-13` (trap) `search.sweep` charges a deferral penalty for every job
    outside the closed set.
14. `DFC-14` (focal) `normalise.memo` reads the sitting the board memo marks as
    rescinded in full.
15. `DFC-15` (focal) `normalise.register` reads the drafting copy of the job
    register.

`solution/solve.py` holds all twenty seven repairs in `REPAIRS`
(solve.py:31-266) and asserts each anchor matches its module exactly once
before applying it, in order. `DFC-16` to `DFC-27` are faults the stage papers show
beside the catalogued fifteen. Left unrepaired, `DFC-16` moves the shipped
round's documents 02, 19, 23, 24 and 25: lodgements naming a job of a cycle
are rejected under `EDG-UNKNOWNJOB` (p02). The shipped round leaves the other
eleven quiet or coincident: every job identifier in a group membership, a charge
rule subject or an amendment payload goes through the crosswalk (p01), a lodged
amendment is tested for `EDG-SELF` before `EDG-UNKNOWNJOB` (p02), the reversal
of a lodgement or a withdrawal is its exact inverse (p13), an amendment that
seeds no cell is classified inert (output_schema_reference.md), the round's weighted
resource is the exact sum published once at twelve places (p10, p11),
`aliases_active` counts active crosswalk rows (the schema reference), and every
declared input is read through `reading._declared`, whose handlers raise on the
error they catch (judge R2).

Out of bounds: the agent is never asked to invent a rule. Every one of the
catalogued fifteen is stated in a shipped paper, most of them twice, once in the stage
paper and once in `readings_not_in_force.md`. The three values that stand in no
plain text paper stand in the workbook and the memo, and the tables that fix
the seed sets, the readers and the order of application stand in the directive.
The instruction points at all three.

## Load-bearing work

Twenty six artifacts. `/app/out/patched_engine.zip` carries the repaired engine,
and the twenty five numbered documents carry the round it publishes.

- `01_identifier_canon.json`, `04_normalised_jobs.csv`, `06_feasibility_map.csv`
  carry the register in force, the unit conversions and the admissibility tests.
- `02_precedence_edges.tsv`, `03_reverse_index.json`,
  `19_rejected_register.csv` carry the graph and everything the papers turn
  down.
- `05_normalised_rules.csv`, `07_closure_map.jsonl`, `08_demand_vectors.csv`,
  `10_charge_contributions.csv` carry the per job layers.
- `09_conflict_groups.json`, `11_baseline_selection.json`,
  `12_baseline_trace.jsonl` carry the round before any amendment.
- `13_amendment_classification.csv`, `14_invalidation_sets.jsonl`,
  `15_reuse_ledger.csv`, `16_work_counters.csv`, `17_cache_summary.json`,
  `21_amendment_optima.csv` carry the cascade.
- `18_final_selection.json`, `20_resource_usage.tsv` carry the round after it.
- `22_defect_register.md`, `23_verification_notes.md`, `24_run_manifest.txt`,
  `25_summary.json` carry the audit.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app`, which grades the
criteria registered in `tests/test_output.py` and the rubric in
`tests/judge.toml` and writes `reward.json` under the verifier log root. Each
channel is the signed weight sum over its positive total, weighted 0.5.

Channel A: 50 checks, 32 positive weighing 112, 18 negative weighing -66. The
positive side splits into four structural checks weighing 1 each (documents
present, package layout, shipped suite unedited, the sample round published by
the engine started with only the standard library importable), eleven exact
document families over the shipped round weighing 33, five families over three
rounds minted from seeds the delivered engine has never seen weighing 15, and
twelve families over eleven held-out rounds that write job identifiers under the
legacy identifier their active crosswalk row carries, in group memberships,
charge rule subjects, amendment payloads, both ends of precedence rows, the
frozen register and supplement-completed payload fields, weighing 60. Every
engine run starts in its own session as the run user, and its process group
and any process of that user left behind are killed once it exits. The
expected documents of every round are built beforehand from a private copy, in
a directory only root can open, held in memory and removed before any engine
run; the engine reads a sealed copy it cannot write, and its output is read
back before the next run starts.

Negative detectors: eleven rebuild the whole publication under one named wrong
reading and fire only when the delivered bytes match that reconstruction on
every document the reading moves; five are the standard cheat detectors for a
baked answer (the shipped round's final selection written on a minted or
held-out round whose own selection differs, or the shipped documents right
while no minted round runs), an engine that ignores its input, a non-deterministic engine, an
engine that reads its own directory name, and an engine that reaches for a
corpus beside its working directory. One more fires on an archive that shadows a
standard library module, and one on a delivered module that imports something
outside the standard library and the package, standing down where the
shadowing charge already fires.

Negative assertions and their weights:

- `test_negative_weight_shift_length_taken_flat` (-5)
- `test_negative_weight_pool_weights_taken_flat` (-5)
- `test_negative_weight_deferral_rate_from_the_rescinded_sitting` (-5)
- `test_negative_weight_set_ranked_on_charge_alone` (-5)
- `test_negative_weight_cascade_stopped_at_the_first_hop` (-5)
- `test_negative_weight_hardcoded_sample_answers` (-5)
- `test_negative_weight_drafting_register_read` (-3)
- `test_negative_weight_capacity_boundary_read_as_strict` (-3)
- `test_negative_weight_rebate_taken_before_the_surcharges` (-3)
- `test_negative_weight_penalty_charged_on_every_job` (-3)
- `test_negative_weight_cascade_never_stopped` (-3)
- `test_negative_weight_withdrawal_treated_as_inert` (-3)
- `test_negative_weight_rebinds_verifier_dependencies` (-3)
- `test_negative_weight_imports_outside_the_standard_library` (-3)
- `test_negative_weight_package_ignores_its_input` (-3)
- `test_negative_weight_nondeterministic_output` (-3)
- `test_negative_weight_filename_dependent_behaviour` (-3)
- `test_negative_weight_reads_training_corpus_at_runtime` (-3)

Each is registered in `tests/test_output.py` as a criterion of the same stem:
`negative_shift_length_taken_flat`,
`negative_pool_weights_taken_flat`,
`negative_deferral_rate_from_the_rescinded_sitting`,
`negative_set_ranked_on_charge_alone`,
`negative_cascade_stopped_at_the_first_hop`,
`negative_hardcoded_sample_answers`,
`negative_drafting_register_read`,
`negative_capacity_boundary_read_as_strict`,
`negative_rebate_taken_before_the_surcharges`,
`negative_penalty_charged_on_every_job`,
`negative_cascade_never_stopped`,
`negative_withdrawal_treated_as_inert`,
`negative_rebinds_verifier_dependencies`,
`negative_imports_outside_the_standard_library`,
`negative_package_ignores_its_input`,
`negative_nondeterministic_output`,
`negative_filename_dependent_behaviour`,
`negative_reads_training_corpus_at_runtime`.

Positive assertions and their weights:

- `test_delivered_documents_present_and_parse` (1)
- `test_delivered_package_layout` (1)
- `test_delivered_shipped_suite_unedited` (1)
- `test_delivered_engine_stdlib_only` (1)
- `test_shipped_identifier_layer_exact` (3)
- `test_shipped_graph_layer_exact` (3)
- `test_shipped_closure_and_demand_exact` (3)
- `test_shipped_rule_and_charge_exact` (3)
- `test_shipped_baseline_optimum_exact` (3)
- `test_shipped_amendment_classification_exact` (3)
- `test_shipped_invalidation_sets_exact` (3)
- `test_shipped_work_ledger_exact` (3)
- `test_shipped_store_summary_exact` (3)
- `test_shipped_final_optimum_exact` (3)
- `test_shipped_audit_documents_exact` (3)
- `test_package_eval_state_exact` (3)
- `test_package_eval_cascade_exact` (3)
- `test_package_challenge_state_exact` (3)
- `test_package_challenge_cascade_exact` (3)
- `test_package_probe_publication_exact` (3)
- `test_package_crosswalk_groups_state_exact` (5)
- `test_package_crosswalk_groups_cascade_exact` (5)
- `test_package_crosswalk_groups_publication_exact` (5)
- `test_package_crosswalk_rules_state_exact` (5)
- `test_package_crosswalk_rules_cascade_exact` (5)
- `test_package_crosswalk_rules_publication_exact` (5)
- `test_package_crosswalk_amendments_cascade_exact` (5)
- `test_package_crosswalk_amendments_state_exact` (5)
- `test_package_crosswalk_amendments_publication_exact` (5)
- `test_package_crosswalk_every_state_exact` (5)
- `test_package_crosswalk_every_cascade_exact` (5)
- `test_package_crosswalk_every_publication_exact` (5)

Channel B: 16 rubric criteria, 36 positive points and four negative criteria
weighing -14. Nine are probes of weight 3 on acts the trajectory has to show:
a tie the weights settle, the jobs the drafting copy adds beside the rejection
register, the counters beside the withdrawn ledger, a rerun on an altered copy,
a reversal of a kind no shipped reversal names, a run on a copy where one job
identifier is written as its active legacy identifier, a count of the sets
level on the winning charge, a rerun on reordered rows, and a run on an empty
amendment journal. The self-check block of
`solution/solve.sh` performs each and prints `check <id> ok` with its witness. No criterion grades a
published value.

## Root cause

**One register is in force and the other is the desk's.** `round_header.json`
names it. The drafting copy holds rows the frozen copy sets aside, so reading it
puts three jobs into the round that should never have been in it.

**A control value that stands in one paper only.** The shift lengths and the
pool weights stand on one sheet of the workbook, picked by matching its key cell
against the round header; the deferral rates, the store retention and the charge
ceiling stand in the sitting of the memo that is in force. `legacy_scale_table.csv`
carries the retired figures and reads like a convenience. Every one of those
values is minted per round, so they differ between the shipped round and the
three rounds the delivered engine is driven over, and an engine that carries
this round's figures inside itself is wrong on every round it has not seen.
That is what the contract means by holding nothing about this round inside it.

**A key holds what its cell reads and nothing else.** A key that holds a
presentation field makes the round derive work it did not owe; a key that leaves
out the charge rules leaves a stale optimum standing. Both are visible, in
different documents.

**A cascade stops where a value stands.** The equivalence test on the digest is
what separates a restatement that moves nothing from a revision that moves
everything behind it, and it is what separates withdrawing a duplicate lodgement
from withdrawing a live one.

**An amendment the round turns down moves nothing.** Nineteen amendments reach
the round and four of them are rejected: one names a commitment the round does
not carry, one names an amendment no earlier row applied, one names a job that
is not in force, and one would close a precedence cycle. Each is published with
its reason, an empty seed set and a stage that reached no cell, so a round that
applies them anyway is visible in the classification, the invalidation sets and
the work ledger together.

**A payload field is completed only where both gates agree.** Two lodgements
leave their kind empty on the journal row and the supplement offers `advisory`
for each. The first is refused because `row_provenance_ledger.csv` sends that
field back to the journal; the second because the supplement row carrying it is
withdrawn. Either gate alone would refuse one of the two and admit the other,
so a round that implements one and drops the other lodges an advisory edge,
creates no prerequisite, and publishes a closure that moves.

**An identifier is read after the crosswalk, wherever it stands.** The
shipped round writes legacy identifiers only in the crosswalk itself, so an
engine that maps the register and the precedence journal and nothing else is
right on it. The held-out rounds write group members, charge rule subjects,
amendment payload jobs, precedence row ends, frozen register rows and
supplement-completed payload jobs under their active legacy identifiers, and
such an engine drops the member, never fires the rule and turns the amendment
down.

**The objective is lexicographic and the papers say so.** Two accepted sets of
one charge are settled by the weighted resource, then the count of optional
jobs, then the canonical job order. Two precincts of the round are engineered
onto that ladder: one where the weighted resource settles two sets of one
charge, and one where three sets are level on charge and on weighted resource
so the count of optional jobs and then the canonical order have to settle it.

## Solution shape

1. Print the head of `/app/data/00_open_this_first.txt` and then of
   `/app/data/replan_programme_contract.md`, before any other working paper.
2. Extract `/app/data/project.zip` into a working tree, then read the fourteen
   stage papers, the policy papers and `readings_not_in_force.md`.
3. Open the workbook, the memo and the directive with the standard library and
   take the shift lengths, the pool weights, the deferral rates, the retention,
   the ceiling, the classification table, the reader table and the order of
   application out of them.
4. Apply the twenty seven repairs `DFC-01` to `DFC-27` to the shipped modules.
5. Zip the repaired tree, with deterministic member order and timestamps, to
   `/app/out/patched_engine.zip`.
6. Run `python3 -m slwopt --data /app/data --out /app/out`.

## Ordered plan

1. Read `00_open_this_first.txt`, then the programme contract, then the lineage
   paper, then the readings paper. Covers R3.
2. Open the three papers that are not plain text and print what each gives.
3. Run the shipped engine once, keep its output, and compare it against
   `withdrawn_plan_publication.tsv` and `withdrawn_counter_publication.csv`.
4. Work the parameter layer first: register, workbook, memo, crosswalk.
5. Work the objective next: capacity boundary, ranking keys, penalties, rebate
   order.
6. Work the cascade last: reader table, cut-off, seed sets, reversals. Covers
   R1 and R2.
7. Deliver, then run the probes against the delivered engine: the tie with the
   members and weighted resource of both tied sets and the set kept, the
   drafting adds beside `19_rejected_register.csv`, the three counters of every
   stage beside the matching withdrawn row with every differing stage named, an
   altered copy, a reversal of another kind, a legacy identifier written into a
   copy of a paper, the count of subsets of selectable jobs that pass the group
   and capacity tests at the winning charge, reordered rows, an empty journal.
   Covers R4 to R12.

## Pitfalls

- Rewriting the engine from scratch rather than repairing it. The delivered
  archive still has to carry the module list and the suite byte for byte, which
  `test_delivered_package_layout` and `test_delivered_shipped_suite_unedited`
  check.
- Taking the shift lengths or the pool weights from `legacy_scale_table.csv`.
  Fires `test_negative_weight_shift_length_taken_flat` and
  `test_negative_weight_pool_weights_taken_flat`.
- Taking the deferral rates from the rescinded sitting. Fires
  `test_negative_weight_deferral_rate_from_the_rescinded_sitting`.
- Repairing the plan and leaving the ledger. `test_shipped_work_ledger_exact`
  and `test_shipped_store_summary_exact` carry six of the one hundred and twelve
  positive points and turn only on the cascade.
- Over-invalidating to be safe. The plan comes out right and
  `test_shipped_invalidation_sets_exact`, `test_shipped_work_ledger_exact` and
  the eval tier all fail.
- Treating a withdrawal as harmless. Fires
  `test_negative_weight_withdrawal_treated_as_inert`.
- Publishing a ratio in binary floating point. The twelve place strings stop
  matching and every document carrying one fails.

## Provenance

`fix_patch_sha256` is sha256 over the bytes of `solution/solve.sh`, the
entry point that applies the whole fix patch. `solve_py_sha256` is sha256
over the bytes of `solution/solve.py`, which holds the repair pairs. Both are
reproducible from the shipped bundle.

```yaml
uuid: 5707c4a9-6bcd-5f14-87c0-0a2cdb0d0023
instance_id: slipway-overhaul-replan-repair
task_name: terminal-bench/slipway-overhaul-replan-repair
fix_patch_sha256: 5b410df6f80049b68b95f4ebbad79cc34ae33eb2854621f92a1705772619a8e7
solve_py_sha256: 101a83ecdd44e54b7bd92c7962a1fd653c06bcc7005e0e15bc813916bbe59359
language: python
category: Debugging
data_file_count: 58
artifact_count: 26
channel_a_positive_total: 112
channel_a_negative_total: -66
channel_b_positive_total: 36
channel_b_negative_total: -14
measured_oracle_test_channel: 1.000
measured_nop_test_channel: 0.000
```
