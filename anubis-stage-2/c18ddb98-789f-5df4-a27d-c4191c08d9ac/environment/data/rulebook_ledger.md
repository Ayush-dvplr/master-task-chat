# Rulebook: ledger

Filed under L in the platform reference set, near the end. The ledger is the
record by record account of a settled window. Each rule stands on its own.

## L1 What reaches the ledger

Every landing record that took part in the settlement reaches the ledger,
whatever became of it. Curated records, withdrawn records and quarantined
records are all there. Records that took no part at all, which is to say records
outside the window boundary and records on suspended feeds, do not reach the
ledger and are accounted for only in the quality register.

The count of records that reached the ledger is the count of records that were
in the window and eligible to be settled. It equals the curated count plus the
withdrawn count plus the quarantined count exactly, with nothing left over.

## L2 Ledger order

The ledger is ordered by the emission instant of the record, earliest first.
Where two records share an emission instant they are ordered by their record
identifier compared as text, smallest first. Every record in the ledger carries
its position in that order as a sequence number, counting from one, with no gaps
and no repeats.

This order is a property of the ledger. It is not the order the landing register
happens to be filed in, and it is not the order records were judged in.

## L3 The running total

Every row of the ledger carries the total charge settled by that row and by
every row before it in ledger order. Because a row that is not curated carries
no charge, the running total never falls as the ledger is walked, and it never
rises except at a curated row.

The running total on the last row of the ledger is the charge the window
settled. That figure has to agree exactly with the settled charge reported in
the window summary. If the two disagree the settlement is wrong, however
plausible each artifact looks on its own.

## L4 Conservation of records

The records that reached the ledger are conserved. The count of records in the
window and eligible to be settled, less the curated count, less the withdrawn
count, less the quarantined count, is zero. The settled window reports that
residual as a figure of its own so it can be read rather than recomputed.

## L5 Conservation of charge

Charge is conserved at every level. The charge settled by the window equals the
total of the charge settled by every settled domain. It also equals the total of
the charge settled by every settled channel. Within a channel report, the charges
attributed to the settled member domains total the charge the channel settled.
Each of those identities is reported as a residual, and every residual is zero
in a correct settlement.

## L6 Conservation of units

Payload units are conserved the same way. The curated payload units of the
window equal the total of the curated payload units of every settled domain, and
that residual is reported too.

## L7 What the audit carries

Beyond the ledger, the audit artifact carries the identity resolution of every
distinct producer reference seen in the window, the canonical entities a
tombstone reached, and the records that carried an upheld agreed rate into the
settled output.
