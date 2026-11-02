# pipeline contract overview

The settlement is one chain. Each stage freezes a value that the next
stage consumes, and no stage may be reordered against the edges in
ordering_dependencies.yaml.

| stage | name | owns |
| --- | --- | --- |
| S01 | identity resolution | spec_stage_s01_identity_resolution.md |
| S02 | availability construction | spec_stage_s02_availability_construction.md |
| S03 | pass admission | spec_stage_s03_pass_admission.md |
| S04 | interval clipping | spec_stage_s04_interval_clipping.md |
| S05 | capacity derivation | spec_stage_s05_capacity_derivation.md |
| S06 | precedence and commit | spec_stage_s06_precedence_and_commit.md |
| S07 | contention resolution | spec_stage_s07_contention_resolution.md |
| S08 | entitlement merge | spec_stage_s08_entitlement_merge.md |
| S09 | deliverable volume | spec_stage_s09_deliverable_volume.md |
| S10 | transmission accounting | spec_stage_s10_transmission_accounting.md |
| S11 | utilisation basis | spec_stage_s11_utilisation_basis.md |
| S12 | settlement aggregation | spec_stage_s12_settlement_aggregation.md |
| S13 | credit and debit | spec_stage_s13_credit_and_debit.md |
| S14 | reconciliation emission | spec_stage_s14_reconciliation_emission.md |

## the spine

The canonical contact ledger is the spine. It carries one row per pass
per settlement period, and every artifact after S05 is a projection of
it. A pass that is read wrong at S03 or S04 is wrong in the station
statement, the mission statement, the compliance ledger and the credit
ledger at the same time.

## the two scarcities

Antenna time is scarce twice over and the two scarcities are settled by
different rules. S07 settles the clash of two passes that want the same
aperture at the same instant, and it settles it by displacement: one
pass keeps its whole eligible interval and the other keeps none of it.
S09 settles the case where the passes that survived S07 want more volume
in one accounting period than the aperture is contracted to carry, and it
settles that by rationing the budget across them. A solution that folds
the two together produces plausible totals and disagrees with every
ledger below S07.

## the two accountings

Operational accounting and contractual accounting are separate and stay
separate. An outage exemption at S13 changes what a mission is charged
and never changes what an aperture was occupied for. S11 reads the
resolved ledger and nothing else.

## what a settlement run consumes

A run reads /app/data and writes /app/out. It reads
nothing else, it reaches no network, and it produces the same bytes
every time it is given the same directory.
