# Campaign contract

The animal health service runs a dose campaign over a fixed set of fortnightly rounds. Doses
are scarce. This contract and the rule documents it names are the single source of truth for
every quantity the campaign reports.

## Defined terms

A **block** is a herd holding under one registration. A block belongs to one region and one
holder segment for a round, taken from the master version in force at the start of that round.

A **block identity** is a block reference together with its restock epoch, written in the form
`BLK-0042#2`. Identity is the unit of account. Every running quantity belongs to an identity,
never to a bare block reference.

A **claim** is the settled request of one block identity for one round. A round carries at
most one claim per identity.

The **entitlement** of a claim is the dose quantity the block may draw for that round before
any carried quantity is added. `entitlement_rules.md` fixes how it is derived.

The **carried claim** of a claim is the quantity carried into the round by the same identity
under `carry_rules.md`.

The **claimable quantity** of a claim is its entitlement plus its carried claim.

The **award** of a claim is the quantity the ration ladder grants it under `ration_rules.md`.

## Order of determination

The campaign is settled in one pass over the rounds in calendar order. Within a round the
regions are settled independently of each other. Admission comes before identity, identity
before the governing head count, the governing head count before the entitlement, the
entitlement before the claimable quantity, the claimable quantity before the award, and the
award before the carried claim of the next round. No later step revises an earlier one.

## Precedence

Where two documents could both decide the same question, the document named later in this
list decides it: `legacy_runbook.md`, a reference table, a primary source, a correction stream,
a rule document in the contract tier, `errata_notice.md`.

Where two rules inside one document could both apply to one record, the rule stated first in
that document applies and the other does not.

Nothing in this corpus records how many records disagree with each other, and no file states
how many defects an export carries.
