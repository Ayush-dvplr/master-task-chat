# TRUTH.md - slipway-overhaul-replan-repair

Author-side golden trajectory for `slipway-overhaul-replan-repair`. Not shipped
to the agent.

## Defect

The `slwopt` engine inside `/app/data/project.zip` runs to completion, passes
the suite it carries exactly as it shipped, and writes a full and plausible set
of twenty five documents that are wrong in two different ways at once: the plan
it publishes disagrees with the papers that govern it, and the ledger of work it
publishes beside the plan claims effort the round never owed. Fifteen edits
across six modules carry the faults.

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

The reference authoring holds the repaired engine once, inside
`tests/test_output.py` as `PACKAGE_FILES`, and derives the shipped broken tree
from it by applying every pair in reverse, so the two can never drift apart.
`solution/solve.py` carries the same fifteen pairs the other way round and
asserts each matches its module exactly once before applying it.

Out of bounds: the agent is never asked to invent a rule. Every one of the
fifteen is stated in a shipped paper, most of them twice, once in the stage
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

`tests/test.sh` asserts the bijection between `test_weights.json` and the
`test_*` symbols, runs all thirty five, and writes `reward.json`, `reward.txt`
and `ctrf.json` under the verifier log root. The reward is the signed weight
sum over the positive total, clamped.

Channel A: 35 tests, 18 positive weighing 68, 17 negative weighing -63, so the
floor is -0.926. The positive side splits into two structural checks weighing 1
each, eleven exact document families over the shipped round weighing 45, and
five families over three rounds minted from seeds the delivered engine has never
seen, weighing 21.

Negative detectors: eleven rebuild the whole publication under one named wrong
reading and fire only when the delivered bytes match that reconstruction on
every document the reading moves; five are the standard cheat detectors for a
baked answer, an engine that ignores its input, a non-deterministic engine, an
engine that reads its own directory name, and an engine that reaches for a
corpus beside its working directory. One more fires on an archive that shadows a
standard library module.

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
- `test_negative_weight_package_ignores_its_input` (-3)
- `test_negative_weight_nondeterministic_output` (-3)
- `test_negative_weight_filename_dependent_behaviour` (-3)
- `test_negative_weight_reads_training_corpus_at_runtime` (-3)

Positive assertions and their weights:

- `test_delivered_documents_present_and_parse` (1)
- `test_delivered_package_shape` (1)
- `test_shipped_identifier_layer_exact` (3)
- `test_shipped_graph_layer_exact` (3)
- `test_shipped_closure_and_demand_exact` (5)
- `test_shipped_rule_and_charge_exact` (5)
- `test_shipped_baseline_optimum_exact` (5)
- `test_shipped_amendment_classification_exact` (3)
- `test_shipped_invalidation_sets_exact` (5)
- `test_shipped_work_ledger_exact` (5)
- `test_shipped_store_summary_exact` (3)
- `test_shipped_final_optimum_exact` (5)
- `test_shipped_audit_documents_exact` (3)
- `test_package_eval_state_exact` (5)
- `test_package_eval_cascade_exact` (5)
- `test_package_challenge_state_exact` (5)
- `test_package_challenge_cascade_exact` (3)
- `test_package_probe_publication_exact` (3)

Channel B: 31 rubric criteria, 103 positive points of which 79 sit on
`critically_important`, and two negative criteria. Five are instruction
following and they lead the file. No criterion grades a published value; each
names the paper, field, cell or reason code the trajectory has to show. Where a
rule shows up only in the command history, such as what was installed into the
container, the rubric owns it, because an assertion may not read the history.

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

**The objective is lexicographic and the papers say so.** Two accepted sets of
one charge are settled by the weighted resource, then the count of optional
jobs, then the canonical job order. Two precincts of the round are engineered
onto that ladder: one where the weighted resource settles two sets of one
charge, and one where three sets are level on charge and on weighted resource
so the count of optional jobs and then the canonical order have to settle it.

## Solution shape

1. Extract `/app/data/project.zip` into a working tree.
2. Read the programme contract, the fourteen stage papers, the policy papers and
   `readings_not_in_force.md`.
3. Open the workbook, the memo and the directive with the standard library and
   take the shift lengths, the pool weights, the deferral rates, the retention,
   the ceiling, the classification table, the reader table and the order of
   application out of them.
4. Apply the fifteen repairs to the shipped modules.
5. Zip the repaired tree, with deterministic member order and timestamps, to
   `/app/out/patched_engine.zip`.
6. Run `python3 -m slwopt --data /app/data --out /app/out`.

## Ordered plan

1. Read `00_open_this_first.txt`, then the programme contract, then the lineage
   paper, then the readings paper. Covers R1 and R2.
2. Open the three papers that are not plain text and print what each gives.
   Covers R23 and R25.
3. Run the shipped engine once, keep its output, and compare it against
   `withdrawn_plan_publication.tsv` and `withdrawn_counter_publication.csv` to
   confirm the withdrawn publication is what this engine produces. Covers R29.
4. Work the parameter layer first: register, workbook, memo. Covers R12, R13,
   R14 and R15.
5. Work the objective next: capacity boundary, ranking keys, penalties, rebate
   order. Covers R16 through R19.
6. Work the cascade last: reader table, cut-off, seed sets. Covers R9, R10,
   R11, R20, R21 and R22.
7. Deliver, run twice at one path and once under another name, on the standard
   library alone, with the branches the stage papers state but this round
   leaves quiet carried through. Covers R3, R4, R5, R6, R7 and R8.
8. Report the live sheet, the register in force and what it set aside, the
   precinct on a pool boundary, the amendments that reached no cell, and every
   fault repaired beside its stage. Covers R24 through R28.

## Pitfalls

- Rewriting the engine from scratch rather than repairing it. The delivered
  archive still has to carry the module list and the suite byte for byte, which
  `test_delivered_package_shape` checks.
- Taking the shift lengths or the pool weights from `legacy_scale_table.csv`.
  Fires `test_negative_weight_shift_length_taken_flat` and
  `test_negative_weight_pool_weights_taken_flat`.
- Taking the deferral rates from the rescinded sitting. Fires
  `test_negative_weight_deferral_rate_from_the_rescinded_sitting`.
- Repairing the plan and leaving the ledger. `test_shipped_work_ledger_exact`
  and `test_shipped_store_summary_exact` carry eight of the sixty eight positive
  points and turn only on the cascade.
- Over-invalidating to be safe. The plan comes out right and
  `test_shipped_invalidation_sets_exact`, `test_shipped_work_ledger_exact` and
  the eval tier all fail.
- Treating a withdrawal as harmless. Fires
  `test_negative_weight_withdrawal_treated_as_inert`.
- Publishing a ratio in binary floating point. The twelve place strings stop
  matching and every document carrying one fails.

## Provenance

`fix_patch_sha256` is sha256 over `json.dumps(DEFECTS, sort_keys=True)`
as `tests/test_output.py` holds it, which is the fifteen fault pairs and
therefore the whole fix patch. `solve_py_sha256` is sha256 over the bytes
of `solution/solve.py`. Both are reproducible from the shipped bundle.

```yaml
uuid: 5707c4a9-6bcd-5f14-87c0-0a2cdb0d0023
instance_id: slipway-overhaul-replan-repair
task_name: terminal-bench/slipway-overhaul-replan-repair
fix_patch_sha256: c80b4688354a4cf9f7e99525addac66c46f2d34acd1be2bfaff834fd072002cd
solve_py_sha256: 81a05370de5702c1acb47592c8d16c765f5a4bbc3a906e3af951b19e27de1f14
language: python
category: Optimization
data_file_count: 59
artifact_count: 26
channel_a_positive_total: 68
channel_a_negative_total: -63
channel_b_positive_total: 103
channel_b_negative_total: -6
measured_oracle: 1.000
measured_nop: 0.000
```
