# Invariants of a cleared epoch

Every statement here holds of a cleared epoch. They are not goals to aim at:
a clearance that breaks one of them has not cleared the epoch, and the
account is expected to prove them rather than assert them.

## The rulebooks are filed, not ordered

The rulebooks in this reference set are shelved by subsystem under their own
initials. That is how a reference set is filed and it is not the order in
which the rules bear on a tap. Each rulebook opens by naming what it consumes
and what it produces, and those dependencies are what settle the order.

Three orderings are not forced by any dependency, so they are stated plainly
rather than left to be worked out:

1. A reversal record's reach is resolved before the suspension rulebook runs.
2. Upheld exceptions are applied after the suspension fixpoint and before the
   capping rulebook runs.
3. Capping is the last rule that can withdraw a tap.

## Conservation

1. Every tap in the register appears in the ledger exactly once, and its
   disposition is one of `priced`, `withdrawn` or `out_of_epoch`.
2. The priced count plus the withdrawn count is the admitted count, and the
   admitted count plus the out of epoch count is the register count.
3. The same holds of distance units: priced distance plus withdrawn distance
   is admitted distance.
4. The epoch charge equals the sum of the zone charges, equals the sum of the
   operator charges, and equals the running charge of the last ledger row.
5. Every micro lent between zones is a micro borrowed, so the total lent
   equals the total by which the effective caps exceed the published caps.
6. The operators' net positions sum to zero.
7. The residual obligations plus everything the cancellations removed equal
   the gross obligations.
8. The apportioned shares sum exactly to the retained distance units.
9. The retained margins sum exactly to the pool.

## Bounds

1. No zone's priced total exceeds its effective cap unless that zone is cap
   infeasible, and a cap infeasible zone reports the residual by which it
   does.
2. No operator lends more than its float ceiling across the whole epoch.
3. No payer's funded total exceeds its funding ceiling.
4. A unit fare is never below the floor fare of its own gate.
5. The running charge down the ledger never decreases.

## Consistency

1. A partition report exists exactly when that partition is in scope, and the
   epoch summary's in scope lists name exactly the reports on disk.
2. A held back tap appears in neither the pool, the apportionment weights nor
   the assurance digest order.
3. A tap that is not priced raises no obligation and carries no margin.
4. The suspended gate set in the epoch summary is the set the suspension
   register marks suspended.
5. Every withdrawal reason in the ledger is one of the ten the ledger rulebook
   lists, and every priced row carries an empty reason.
6. An upheld exception never changes a withdrawn tap, and never changes a
   tap's disposition.

## Determinacy

The cleared account is a function of what the registers say and of nothing
else. In particular it does not depend on:

1. the order the rows of any register happen to be stated in,
2. the order the files happen to be read in,
3. anything about the epoch that this particular register set published,
4. the wall clock at the time of the run.

A clearance run twice over the same registers produces the same account byte
for byte, and a clearance run over a register directory with the same content
in a different row order produces the same account as well.
