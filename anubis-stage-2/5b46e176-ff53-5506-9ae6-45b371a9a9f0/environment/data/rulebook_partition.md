# Rulebook: Partition

Filed under P. This rulebook consumes the cleared ledger and produces the set
of partition reports the epoch owes, and their names.

## P1. Scope is a result

A zone is **in scope** when it holds at least one priced tap once the
clearance has finished. An operator is **in scope** when it owns at least one
in scope zone.

Scope is therefore a consequence of how the epoch cleared, not a property of
the register. A zone that was suspended out of existence, or curtailed down
to nothing, or whose every tap lost its identity, is out of scope however
many rows name it in the zone register.

## P2. Report naming

A partition report is written into the output directory and named for what it
reports on:

```
operator_<operator_id>.json
zone_<zone_id>.json
```

with the identifier taken verbatim from the register.

## P3. Reports that must not exist

A partition that settles out of scope gets **no report**. A report that
should not exist is as wrong as one that is missing: both say the clearance
did not work out its own scope. The epoch summary lists the operators and the
zones that ended in scope, and the set of partition reports on disk is
exactly that list.

## P4. What a partition report says

Both kinds carry a `partition_kind` and a `partition_id` so a report can be
read on its own. Beyond that, the operator report accounts for the operator's
priced taps, its charge, its distance, the zones of its that are in scope,
the gates of its that were suspended, and its net position from the netting
layer. The zone report accounts for the zone's priced taps, its charge, its
distance, its operator, its cap and effective cap, the gates of its that
carry priced taps, and whether it ended cap infeasible.

The exact key names of both kinds are fixed by the artifact schema, and the
byte form of both kinds is fixed by the one shipped example report.
