# Identity rules

## 1. Reference spellings

The order book writes a customer as a site letter, a hyphen and six digits,
for example `W-004862`, where the letter is the first letter of the site. The
contract registry writes `CUS-` and the number with no padding, for example
`CUS-4862`. The legacy intake writes either the canonical spelling or an alias
code beginning `LGC-`, `VND-` or `OLD-`. The canonical customer id is `CUS-`
followed by the number padded with leading zeros to four digits. Two
references name the same customer when their canonical ids agree.

## 2. Aliases

`customer_alias_map.csv` maps an alias code to another code over a half open
window. A mapping is used only when it is admitted and when the effective
instant of the record being resolved lies in the window. A target can itself
be an alias, so resolution follows at most three hops. The same alias can
point at different customers in different windows. A reference with no live
mapping, and an id with no row in `customer_master.csv`, put the request out
of scope with the reason `UNKNOWN_CUSTOMER`.

## 3. Epochs

A customer id is reissued. `customer_master.csv` carries one row set per
`epoch_seq`, each with a half open window `epoch_from_utc` to `epoch_to_utc`.
The epoch of a request is the one whose window contains the governing
effective instant of the request. The canonical identity of a request is the
canonical id, the character `#`, and the epoch sequence, for example
`CUS-0412#2`. Every artifact names a customer in that form. Two requests of
the same id in different epochs are different customers: they do not share a
ceiling, a committed minimum, a deficit lot or a segment.

## 4. Segment and status

The segment of a request is the one on its epoch rows and is `commercial` or
`public`. One id can be commercial in one epoch and public in the next.

Status is effective dated. The governing status of a request is the one on the
admitted master row for its id and epoch with the greatest `effective_utc` at
or before the start of its cycle, ties broken by the greater `revision_seq`. A
governing status of `suspended` keeps the request in the ledger with the
reason `CUSTOMER_SUSPENDED` and no claim.
