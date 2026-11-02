# Governance and revision notes

## The register

The node register is revised whenever a site changes what realises its clock or
restates its declared uncertainty. Every revision is kept. A publication
interval works at one revision, named in the interval header as
frozen_register_revision, and it does not move to a later one part way through.

Revisions REG-R15 and REG-R16 move the reference oscillator at two sites. This
interval is frozen at REG-R14 and both sites keep the oscillator REG-R14 names.
A recompute at the current revision would publish a different series for every
oscillator at those two sites and a different budget for every site.

node_register_current.csv is a snapshot of the latest revision, kept for the
audit trail. It is not the register this interval works at.

## Calibration revisions

A delay calibration report is registered under the next free revision number
of its link. When the register receives a restatement of a report that is
already on it, the restatement carries the same effective epoch and the next
revision number, and the register keeps both. The reading of that link at that
effective epoch stays the one the register took first, which is the smaller
revision. That is why two reports can share an effective epoch and why the
smaller revision is the one that governs.

The status of a report is a review state, not a selection key. A report on the
register governs the readings its effective epoch reaches whether its review
has finished or not.

The date a report reached the desk is recorded because the audit needs it. It
does not order anything. A report that reached the desk last can take effect
before every other report of its link, or after the interval closes.

## The workbook

The workbook holds a live sheet and a draft. The draft is a working copy of the
next revision and its numbers are not adopted. The interval header carries the
key of the live sheet and the live sheet carries that key in its own header
cell, so the live sheet is identified by matching, not by its name and not by
its position in the workbook.

## The retired weighting scheme

Before REG-R09 the network weighted by a fixed number per oscillator class.
legacy_weight_table.csv is what that scheme published. It is retired. Weights
come from the residual dispersion of the previous interval.
