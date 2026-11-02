# Replan programme contract

The yard settles one round at a time. A round opens against the register in
force, derives the state of every job, solves each precinct exactly, and then
folds in the amendments the desk lodged during the round, one at a time, in
sequence.

The fourteen stages and the paper that specifies each one:

| stage | subject | paper |
| --- | --- | --- |
| p01 | identifiers, the register in force, the parameter layer | spec_stage_p01_identifier_and_revision.md |
| p02 | the precedence graph and its indexes | spec_stage_p02_precedence_graph.md |
| p03 | units, amounts and the normalised records | spec_stage_p03_normalisation.md |
| p04 | admissibility of one job | spec_stage_p04_admissibility.md |
| p05 | the closure of a job | spec_stage_p05_closure.md |
| p06 | what a job draws | spec_stage_p06_demand.md |
| p07 | the charge a job carries | spec_stage_p07_charges.md |
| p08 | the exclusive slot groups | spec_stage_p08_slot_groups.md |
| p09 | the pools and what is left of them | spec_stage_p09_capacity.md |
| p10 | the objective | spec_stage_p10_objective.md |
| p11 | the exact optimum of one precinct | spec_stage_p11_search.md |
| p12 | what the optimum was derived from | spec_stage_p12_provenance.md |
| p13 | the amendments and the cascade | spec_stage_p13_amendments.md |
| p14 | the publication | spec_stage_p14_publication.md |

The derived state of the round is held in seven layers of cells: `norm` and
`rule` at the bottom, then `closure`, `demand` and `charge`, then `group`, and
`solve` at the top. Each cell carries a key over the inputs it reads and a
value. A key that holds an input the cell does not read makes the round derive
work it did not need; a key that leaves out an input the cell does read leaves
a stale value standing. Both are defects and both are visible in the
publication.

The work ledger is published beside the selection. See
work_ledger_counter_contract.md for what each counter means.
