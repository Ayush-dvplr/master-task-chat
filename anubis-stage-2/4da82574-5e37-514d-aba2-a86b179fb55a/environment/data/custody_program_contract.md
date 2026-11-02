# Custody replay contract

The engine reconstructs the credit state of one observation epoch
from an append only event journal, a sealed checkpoint and the
registers that govern them. Every quantity it publishes is an exact
integer in credit units, written `cu`. Every ratio it publishes
carries exactly twelve decimal places.

## Stages

| stage | subject | paper |
| --- | --- | --- |
| r01 | Unit normalisation and parameter layers | `spec_stage_r01_unit_normalisation.md` |
| r02 | Identifier resolution and registers | `spec_stage_r02_identifier_resolution.md` |
| r03 | Canonical event order | `spec_stage_r03_canonical_order.md` |
| r04 | Checkpoint selection | `spec_stage_r04_checkpoint_selection.md` |
| r05 | Checkpoint restoration | `spec_stage_r05_checkpoint_restoration.md` |
| r06 | Replay window construction | `spec_stage_r06_replay_window.md` |
| r07 | Dependency closure | `spec_stage_r07_dependency_closure.md` |
| r08 | Ordinary state transitions | `spec_stage_r08_state_transitions.md` |
| r09 | Compensating event targets | `spec_stage_r09_compensation_targets.md` |
| r10 | Compensation effects | `spec_stage_r10_compensation_effects.md` |
| r11 | Carry settlement | `spec_stage_r11_carry_settlement.md` |
| r12 | State dependent eligibility | `spec_stage_r12_eligibility_rounds.md` |
| r13 | Materialisation and the derived index | `spec_stage_r13_materialisation.md` |
| r14 | Publication, serialisation and digests | `spec_stage_r14_publication.md` |

## Entry points

The same replay machinery serves every published document. A replay
runs over a half open range of canonical positions, optionally on
top of a restored checkpoint. The epoch header names four ranges:
the publication range, the bounded range, the probe position and
the from scratch comparison range, which always opens at position
one.

## Invariants

A replay that starts from a restored checkpoint and a replay that
starts from scratch over the same end boundary reach the same state,
byte for byte, because the checkpoint body carries the whole state,
the pending queue and the applied and reversed ledgers included.

Replaying the same directory twice produces the same bytes. Running
the engine over the same epoch under another directory name produces
them again. The paper directory is never written to.

No published quantity comes from binary floating point. Rounding
happens where a stage paper places it and nowhere else, and it is
always half away from zero on an exact rational.
