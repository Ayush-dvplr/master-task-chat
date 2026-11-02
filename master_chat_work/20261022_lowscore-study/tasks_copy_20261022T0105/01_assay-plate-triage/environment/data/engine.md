# The plate triage engine

This directory holds bench runs from a microplate reader and what the plate
triage engine made of them. The engine was lost when the bench controller was
rebuilt. Its file shapes and its stage order are written down here. Its numbers
are not, and neither is the meaning of its mode word.

## What ships here

A run is six files under one prefix. The graded run carries no prefix at all, and a second graded run ships under the prefix `trial_`.

| File | One row per | Columns |
|---|---|---|
| `manifest.json` | the run | see below |
| `instruments.csv` | plate reader | `instrument`, `model`, `baseline` |
| `panels.csv` | assay panel | `panel`, `family`, `replicates` |
| `operators.csv` | bench operator | `operator`, `role` |
| `plates.csv` | plate | `plate`, `instrument`, `panel`, `matrix`, `tier` |
| `reads.jsonl` | well read | `seq`, `plate`, `well`, `operator`, `action`, `raw`, `exposure` |

`reads.jsonl` is stored in an arbitrary line order.

`matrix` is one of `buffer`, `serum`, `plasma`, `lysate`, `saliva`, `urine`,
`media`, in that order. `family` is one of `elisa`, `pcr`, `turbidity`, `fluor`.
`role` is one of `technician`, `scientist`, `trainee`, `service`. `tier` is 1, 2
or 3. `action` is one of `measure`, `blank`, `recal`, `mask`.

`manifest.json` carries `run`, `mode`, `declared_reads`, `plate_digests` and
`run_digest`. `declared_reads` is the number of lines in `reads.jsonl`. The two
digest fields are defined in `reports.md`.

## The mode word

`mode` is a twelve bit word, from `0x001` to `0x800`. Every bit is defined, and
each one switches on a single alteration somewhere in the chain below: to what a
stage reads, to what it carries, to which reads it walks, or to how a rollup is
totalled. Each bit acts independently of the others, and setting one never turns
another off.

What any individual bit does was recorded only in the controller firmware, and
that firmware is gone. Nothing in this directory says which bit is which.

The graded run in this directory has every bit set. A second run under the prefix
`trial_` also has every bit set: like the graded run it ships no worked output,
only its own `trial_manifest.json` with a digest per plate and one for the whole
run. It holds a different set of instruments and a different number of operators
and plates from the graded run, so a reading of the mode word can be checked
against two independent runs rather than one. Two worked runs ship under
the prefixes `example_a_` and `example_b_`, and both have `mode` of zero: they
carry no alteration at all and are there to pin down the chain below. Each of
them ships with the three files the engine wrote for it, named
`example_a_out_readings.jsonl`, `example_a_out_plates.json` and
`example_a_out_bench.json`, and the same three under `example_b_`.

## Carried plate state

Each plate carries three values while its reads are resolved.

- `blank level`: at mode zero it starts at the `baseline` of the plate's instrument.
- `drift`: starts at zero.
- `strike count`: starts at zero.

## The chain at mode zero

At mode zero the engine resolves reads in ascending `seq`, a single run wide
ordering across every plate, and passes each read through these stages in this
order. No stage reports a figure below zero: each one clamps its result at zero
before the next stage runs.

1. **Baseline.** The plate's current blank level is taken off the read's `raw`.
2. **Exposure normalisation.** The figure is rescaled against the read's
   `exposure` with one fixed gain, and the division truncates towards zero.
3. **Matrix adjustment.** One adjustment keyed on the plate's `matrix`. Six of
   the seven matrix values carry an adjustment; the seventh leaves the figure
   alone.
4. **Panel adjustment.** One adjustment keyed on the panel's `family`. Three of
   the four families carry an adjustment; the fourth leaves the figure alone.
5. **Drift correction.** The plate's drift at the moment the read is resolved is
   taken off the figure. That drift is reported as `drift_before` and the result
   is reported as `value`.
6. **Grading.** `value` falls into one of four bands, reported as `grade`:
   `high`, `mid`, `low` or `trace`, from the widest figure down.
7. **Status.** An ordered ladder decides `status`. The first condition that holds
   wins and the rest are never consulted.
   - a setup action resolves to `setup`;
   - a masked well resolves to `masked`;
   - a bottom band read resolves to `reject`;
   - a read whose `drift_before` sits above the tolerance of the operator's
     `role` resolves to `review`, and each of the four roles has its own
     tolerance;
   - anything left resolves to `ok`.
8. **Carry update.** After the reading is emitted the plate state moves on. A
   `blank` read replaces the blank level. A `recal` read clears the drift. A
   `measure` read adds a drift charge derived from its `exposure`, and one of the
   three `tier` values changes the size of that charge. Drift has a ceiling it
   never passes. A `reject` adds one strike.

## What is missing

The gain, the six matrix adjustments, the three panel adjustments, the three band
edges, the four role tolerances, the drift charge, the tier that changes it, the
drift ceiling, the strike count that quarantines a plate, the drift figure that
holds a plate back, which statuses count into a plate total, and both of the tie
breaks in `reports.md` are firmware constants. The two mode zero runs and their
outputs are the evidence for those.

The twelve mode bits have no worked run at all. The digests in `manifest.json`
and in `trial_manifest.json` are the only thing that says whether a reading of
them is right.
