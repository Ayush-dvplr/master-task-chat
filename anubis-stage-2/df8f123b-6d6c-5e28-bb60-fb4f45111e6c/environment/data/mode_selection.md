# Mode selection

The governing mode is either strict or tempered. Three layers settle it and a
higher layer overrides a lower one.

| layer | source | reading |
| --- | --- | --- |
| 1 | desk_policy.ini | the desk default mode |
| 2 | window_directives.jsonl | the mode directive of the governing revision |
| 3 | principal_standing_orders.csv | a live standing order scoped to settlement_mode |

Layer two applies when the governing revision names a mode directive. When that
revision also carries a countersignature requirement of true, the directive holds
only while layer three supplies a live standing order that names the same mode.

A standing order is live when its issue instant and its logging instant both fall
at or before the settlement cutoff, its scope is settlement_mode, a
countersignature in countersignature_register.csv names it with both instants at
or before the settlement cutoff, and no live retraction notice names the order or
that countersignature. Among live standing orders scoped to settlement_mode the
one with the latest issue instant is the authority, and the artifact reports its
order identifier.

When layer two carries a countersignature requirement of true and layer three
supplies no live standing order naming that mode, the desk falls back to the
layer one default.
