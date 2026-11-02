# Rate card and kind weights

The base value of a row (scoring_rules.md) multiplies its metered quantity by the
weight of its kind. No rules file carries the weights.

## Kind weights

The rules file lists the kinds of its extract under `kinds`. Every listed kind has a
weight, a whole number from 2 to 40, whether or not the kind appears on the rate card.
The weights belong to the extract: every workload of the extract is rated with them,
the published figures of its batches were computed with them, and the legacy engine
rated the periods of the extract's two closing journals with them (legacy_notes.md).

## Metered charges

The metered charge of a row, or of a rate card line, is amount * units * the weight of
its kind. For a workload row, amount and units are its cells after amendments
(amendments.md).

## The rate card and the figures

The rate card file (`rate_card_file`) has the columns `batch`, `kind`, `amount` and
`units`: each line is one metered line of a calibration batch. The figures file
(`rate_figures_file`) holds `figures`, an object that maps each batch to its published
metered charge.

The metered charge of a batch is the sum of the metered charges of its lines. Nothing
else enters it: no region offset, latency, carry, penalty or waiver.

The rate card lines are not workload rows: they are never processed, never counted and
never part of any result.
