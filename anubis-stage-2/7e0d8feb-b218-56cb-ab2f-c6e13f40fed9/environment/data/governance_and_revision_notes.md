# Governance and revision notes

## Control sets

Contract terms are published as control sets. Three sets sit in the workbook
at any time and `channel_config.json` names the one that is settled. The
sheet names carry a revision label but the label is not the selector: a
sheet named with a higher revision is not necessarily the settled one,
because a revision can be raised and then withdrawn. The two superseded
sheets carry terms of their own, so reaching for either of them gives a snap
tolerance and a commission that look plausible and are wrong.

## The memorandum

The compliance memorandum is issued per transmission date and it is the only
publication of the separation minimum, the billing grain and the regulatory
minutes per clock hour. Those three constants are not repeated anywhere else
in this directory, by design, so that a change to them cannot be missed.
The memorandum also lists permitted minutes per market and clock hour in its
Section 2. Where that list departs from the standing figure for a market
hour, the list governs that hour (V13, R37).

## The rate register

Rate codes are added but never changed. `df_allowed` is a property of the
rate and is not negotiable per asset. Attempts that claim drop frame on a
rate that does not permit it are a known defect of one ingest station and
are corrected at V2 rather than in the register.

## The draft overlay

`blackout_overlay_drafts.xml` was prepared for a legal review that did not
complete. Its root element carries the status `draft-superseded`. It is kept
for audit and it is not read.

## The legacy commission table

Commission moved from a percentage of gross to an exact fraction when the
minor unit rounding was written down. `legacy_commission_table.csv` is the
old schedule and is kept for audit.
