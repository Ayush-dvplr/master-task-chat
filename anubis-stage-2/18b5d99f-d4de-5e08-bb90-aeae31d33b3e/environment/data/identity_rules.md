# Identity rules

This file defines the governing identity record of an account, which account a row is
booked to, when a row's account is unregistered, and the billing region and sponsor of
an account. Billing accounts change over time: they are merged into others, merged
accounts are later reactivated, and the identity records are kept in two places. The
rules file names the three identity files through `registry_file`, `export_file` and
`merges_file`.

## Governing record

The registry file is the system of
record. It has the columns `account`, `home_region`, `sponsor` and `updated`; `sponsor`
may be empty, and `updated` is a timestamp written in one fixed-width form, so two
`updated` values compare correctly as text. An account may appear on more than one
line. The governing record of an account the registry lists is its line with the
greatest `updated`; when two of its lines carry the same `updated`, the one written
later in the file governs.

The export file is a nightly snapshot of
the same records under `accounts`, each with `account`, `home_region`, `sponsor` and
`updated`. It is marked FINAL and its stamps are later than the registry's, but for an
account the registry lists, every field of the export is ignored, its home region and
its sponsor included. For an account the registry does not list, the export's record is
the governing record. The export's `updated` field plays no part.

An account that neither file lists is unregistered.

## Booking

The merges file holds merge records with
the columns `account`, `merged_into` and `effective_ts`. A record with a non-empty
`merged_into` says that rows of `account` belong to `merged_into` once the record is in
force. A record with an empty `merged_into` reactivates `account`: once it is in force,
the rows of `account` belong to it again. No account has two records with the same
`effective_ts`, and the records never form a cycle.

A merge record is in force at every stamp strictly later than its `effective_ts`, and
not at its `effective_ts` itself.

To resolve an account at a stamp, take that account's record with the greatest
`effective_ts` among the records in force at the stamp. If there is none, or its
`merged_into` is empty, the account resolves to itself. Otherwise it resolves to
whatever `merged_into` resolves to at the same stamp, so merges chain.

A row is booked to the account its written `account` resolves to at the row's own
`ts`. A booking never moves afterwards: a merge that comes into force later does not
rebook earlier rows.

A row is unregistered when its booked account is unregistered, whatever account is
written on it.

## Billing region

The billing region of an account is the `home_region` of its governing record. The
billing region of a row is the billing region of its booked account. Every billing
region of a registered account has an entry in the rules file's `region_offsets`.

## Sponsor

The sponsor of an account is the account named in the `sponsor` field of its governing
record, followed through the merge records as at a stamp later than every
`effective_ts` (every record in force): if the named account resolves to another
account there, the sponsor is that other account. An account whose governing record
has an empty `sponsor` has no sponsor. The use of the sponsor is defined in
scoring_rules.md.

