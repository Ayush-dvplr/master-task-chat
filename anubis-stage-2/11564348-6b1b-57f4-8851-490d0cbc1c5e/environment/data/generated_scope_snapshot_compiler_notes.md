# Export snapshot compiler notes

The export snapshot is produced by the release train compiler after every
merge into the release branch. Before it walks the ledger the compiler loads the
ledger shards, the active sheet of the restricted scope workbook, the policy
addenda in force, and the release operations journal and builds the same journal view the builder
runtime uses: every journal operation that the release desk has not rejected
is honoured, so pending lineage anchors are settled, rolled back records are
dropped and records whose admission was refused are skipped.

The compiler then opens the change ledger, walks the records in ascending
record sequence, and applies each record to an in-memory surface as it goes.
The walk is single pass and the compiler holds no lookahead buffer, so a
record is applied at the moment it is read.

Scope values that carry a restricted reference domain are resolved through
the restricted scope map before they are applied. Deprecation and restore
records are tracked per scope so that a restore can cancel the deprecation
that precedes it. Withdrawn scopes are moved to the retired list and are
never returned to the active surface. At the end of the walk, scopes whose
open deprecation has outlived the deprecation window are appended to the
retired list in scope name order.

The compiler stamps the surface digest and the household version onto the
snapshot at the end of the walk.

The compiler writes the snapshot with two space indentation and a trailing
newline so that successive snapshots diff cleanly.
