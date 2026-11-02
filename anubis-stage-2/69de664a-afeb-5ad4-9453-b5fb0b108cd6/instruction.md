The flat and office-format files in `/app/data` are a detector-array flux
reconciliation extract from a four-instrument imaging array observed over three
epochs. The extract ships a written reconciliation contract, a set of reference
tables spread across many files, and a pre-computed pipeline output that is
known to be faulty. Deciding which inputs feed which figure is part of the task.
Read the contract, diagnose why the pre-computed flux values are wrong, and
produce a corrected reconciliation report by recomputing every figure from the
data rather than trusting the shipped output.

`/app/data/reconciliation_contract.md` governs how every figure is computed, and
`/app/data/report_schema.md` governs what the output looks like: the keys of
every artifact, the fixed strings, the key formats and the order of every list.
Follow both exactly. Where a reference table appears in more than one file,
`/app/data/file_role_index.md` names the authoritative source for each role.

Deliver a single reusable program at `/app/out/derive_report.py`, runnable as
`python3 /app/out/derive_report.py DATA_DIR OUT_DIR`, that reads an extract in
this schema from `DATA_DIR` and writes the full report set into `OUT_DIR`. Run
it on the shipped extract so the deliverables land at the exact paths named
here.

Write the whole-corpus report to `/app/out/summary.json`, the per-observation
reconciled flux to `/app/out/reconciled_flux.json`, the applied-calibration
audit to `/app/out/calibration_audit.json`, and the input-integrity report to
`/app/out/data_quality.json`. Write the four per-instrument rollups to
`/app/out/instrument_G1.json`, `/app/out/instrument_G2.json`,
`/app/out/instrument_G3.json` and `/app/out/instrument_G4.json`, the per-epoch
totals to `/app/out/epoch_totals.json`, and the dead-pixel redistribution
closure to `/app/out/deadpixel_closure.json`. Write the band rollup to
`/app/out/band_rollup.csv`, the epoch rollup to `/app/out/epoch_rollup.tsv`, and
the instrument rollup to `/app/out/instrument_rollup.psv`. Write the
flagged-observation list to `/app/out/flagged_observations.xml`, the objective
summary to `/app/out/objective_summary.yaml`, the human-readable report to
`/app/out/reconciliation_report.md`, and the run status to
`/app/out/run_status.txt`. Write the provenance manifest to
`/app/out/provenance_manifest.json`, the anomaly ledger to
`/app/out/anomaly_ledger.json`, the ordered flux index to
`/app/out/ordered_flux_index.json`, and the dropped-observation list to
`/app/out/dropped_observations.json`. Write the exposure attribution of the
reconciled total to `/app/out/flux_attribution.json` and the hop-by-hop
dead-pixel relay audit to `/app/out/relay_audit.json`.

The contract also carries a settlement layer that runs on top of the reconciled
flux, turning each reading into a rate over the integration time its frame
received, discarding the frames that measured nothing and the hits that are not
sky, and settling the result into a pool, an attribution and a digest. Write the
settlement account to `/app/out/settlement_summary.json`, the per-observation
settled rates to `/app/out/settled_rates.json`, the frames whose shutter aborted
to `/app/out/zero_exposure.json`, the rejected cosmic ray hits to
`/app/out/cosmic_ray_rejects.json`, the near-saturated observations to
`/app/out/near_saturation.json`, the settled attribution to
`/app/out/settled_attribution.json`, the per-band settlement rendering to
`/app/out/band_settlement.csv`, and the ranked order the digest is taken over to
`/app/out/settlement_order.json`.

The reconciled figures are also cut along three pairs of dimensions, as
sections D1, D2 and D3 of the report schema set out. Each family carries its
own serialisation and its own row order, and the schema states both for each
one. Every file named below is written even where the pair it names has no live
observation.

Write the twenty instrument-and-band cells to `/app/out/cell_G1_u.json`,
`/app/out/cell_G1_g.json`, `/app/out/cell_G1_r.json`,
`/app/out/cell_G1_i.json`, `/app/out/cell_G1_z.json`,
`/app/out/cell_G2_u.json`, `/app/out/cell_G2_g.json`,
`/app/out/cell_G2_r.json`, `/app/out/cell_G2_i.json`,
`/app/out/cell_G2_z.json`, `/app/out/cell_G3_u.json`,
`/app/out/cell_G3_g.json`, `/app/out/cell_G3_r.json`,
`/app/out/cell_G3_i.json`, `/app/out/cell_G3_z.json`,
`/app/out/cell_G4_u.json`, `/app/out/cell_G4_g.json`,
`/app/out/cell_G4_r.json`, `/app/out/cell_G4_i.json` and
`/app/out/cell_G4_z.json`.

Write the fifteen epoch-and-band grids to `/app/out/grid_E1_u.psv`,
`/app/out/grid_E1_g.psv`, `/app/out/grid_E1_r.psv`, `/app/out/grid_E1_i.psv`,
`/app/out/grid_E1_z.psv`, `/app/out/grid_E2_u.psv`, `/app/out/grid_E2_g.psv`,
`/app/out/grid_E2_r.psv`, `/app/out/grid_E2_i.psv`, `/app/out/grid_E2_z.psv`,
`/app/out/grid_E3_u.psv`, `/app/out/grid_E3_g.psv`, `/app/out/grid_E3_r.psv`,
`/app/out/grid_E3_i.psv` and `/app/out/grid_E3_z.psv`.

Write the twelve instrument-and-epoch spans to `/app/out/span_G1_E1.tsv`,
`/app/out/span_G1_E2.tsv`, `/app/out/span_G1_E3.tsv`,
`/app/out/span_G2_E1.tsv`, `/app/out/span_G2_E2.tsv`,
`/app/out/span_G2_E3.tsv`, `/app/out/span_G3_E1.tsv`,
`/app/out/span_G3_E2.tsv`, `/app/out/span_G3_E3.tsv`,
`/app/out/span_G4_E1.tsv`, `/app/out/span_G4_E2.tsv` and
`/app/out/span_G4_E3.tsv`.

The settlement layer does not reuse the conventions of the layer beneath it. Its
normalisation rounds one way and only one way, its rejection rule names the
estimator it uses and the two samples it never rejects from, its medians settle
an even sample differently from the band median above, and the order it puts
bands in is not alphabetical. The contract states each of those; take none of
them from the layer above.

Every calibrated flux is an integer in micro-jansky, and no flux figure is a
floating-point value. The contract fixes the application order of the correction
stages, the sign of each correction, where a reading meets the detector's full
well and what that does to it, how a gain label resolves to the channel that
applies, how an epoch follows from a date, how the dead-pixel redistribution
closes and how its hops are audited, which observations a band median is allowed
to be taken over, how the reconciled total is apportioned across the instruments
so the parts sum to it exactly, which source wins when two disagree, and the
rounding mode. Work each of those out from the contract and the reference tables
rather than from the order the files happen to appear in. Serialize all JSON
deterministically with sorted keys and a trailing newline, keep the output
byte-identical across reruns, and keep the output identical when the input
observation rows are reordered.

The reusable program is graded on extracts you have not seen, in this same
schema, including extracts whose reference tables hold different values from the
shipped ones. Implement the contract in general rather than memorizing the
shipped numbers. Only the artifact paths named above are collected. Use only the
Python standard library, make no network access of any kind, and read nothing
outside `DATA_DIR` and write nothing outside `OUT_DIR`.

You have 7200 seconds to complete this task. Do not cheat by using online
solutions or hints specific to this task.
