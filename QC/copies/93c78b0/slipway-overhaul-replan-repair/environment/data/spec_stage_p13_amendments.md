# Stage p13  the amendments and the cascade

The lodged rows of `amendment_journal.jsonl`, in ascending sequence, are the
amendments of the round. A row that is not lodged is not an amendment. Where a
payload field is empty on the journal row, the field is completed from
`amendment_supplement.ndjson`, but only for the amendment and field that
`row_provenance_ledger.csv` records against the supplement with the state
`in_force`.

Each amendment is classified by its kind and seeds the cells the precedence
directive names for that kind, and no others. A `job_note_revision` moves only
presentation fields and seeds nothing at all. A `restatement` seeds what its
own kind would seed. A `reversal` names an earlier amendment and applies the
exact inverse of what that amendment did, and is classified by the kind of the
amendment it names. An amendment that names nothing the round holds, or that
would close a precedence cycle, is rejected and moves nothing.

A seeded cell is derived again. When the value it comes back with carries the
digest it already held, it is revalidated and the cascade stops there: the
cells that read it keep their values and are never visited. When the digest
moves, every cell that reads it is reached in turn, prerequisites before the
jobs that name them, and the same test is applied at each of them.

The cells one cell is read by are fixed by the precedence directive. A
mistake in either direction is a defect. Reaching too few cells leaves a stale
value standing in the publication. Reaching too many leaves the publication
right and the work ledger wrong, and the work ledger is published.
