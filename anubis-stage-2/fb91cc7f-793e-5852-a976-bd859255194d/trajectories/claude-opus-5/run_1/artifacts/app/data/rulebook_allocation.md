# Rulebook: allocation

The allocation subsystem decides which settled programmes the lab bills this
cycle and where each billed programme is stored. It runs on settled frame
counts. It never revisits a frame count.

## Rights holders and settlement groups

Every programme is held by exactly one rights holder. Every rights holder
belongs to exactly one settlement group. A holder carries a base quota
expressed in frames, and an account tier that has no effect on allocation
(the tier governs invoicing, which this lab does not settle here).

## Drawing holders

A holder is *drawing* in a cycle when at least one of its programmes is
admitted in that cycle. A holder with no admitted programme is not drawing,
and contributes nothing to any quota.

## Group quota

A settlement group's quota for the cycle is the sum of the base quotas of its
drawing holders, reduced by the charter's group draw factor once for each
drawing holder beyond the first. A group with a single drawing holder suffers
no reduction. A group with no drawing holder has a quota of zero.

The quota therefore depends on which holders are drawing, and whether a holder
is drawing depends on whether its programmes are admitted, which depends on
the quota. Exactly one drawing set is stable under this dependency: the set in
which every drawing holder does hold an admitted programme, and no holder
outside the set would gain one were it added. That stable set is the one the
cycle settles on.

## The draw

Within a settlement group the programmes of that group's holders draw against
the group quota in descending order of settled frames. Two programmes with the
same settled frame count draw in ascending programme identifier order.

A group's draw closes at the first programme that would take the group's
consumption past its quota. That programme is *held*, and so is every
programme behind it in the same group's draw order, whether or not a later
programme would have fitted in the frames that remain. Programmes that drew
before the close are *admitted*.

A programme whose conform was voided never enters the draw at all: it has no
settled frame count.

## Vaults

The vault charter lists the lab's vaults. Each vault carries a seat rank, a
capacity in frames, the set of deliverable classes it accepts, and the set of
settlement groups it accepts.

Every admitted programme is seated in exactly one vault. A vault may only seat
a programme whose deliverable class it accepts and whose settlement group it
accepts. The sum of the settled frames seated in a vault may not exceed that
vault's capacity.

Those conditions do not always pick out a single seating, so the lab fixes the
order in which it looks for one. The admitted programmes are taken in
descending order of settled frames, ties broken by ascending programme
identifier. Each programme in turn is offered to the vaults in ascending seat
rank, ties broken by ascending vault identifier, and it is placed in the first
vault that accepts its deliverable class and its settlement group and still has
room for its settled frames. When a programme cannot be placed, the lab takes
back the programme placed before it and moves that one on to its next vault,
and carries on that way. The seating the lab settles is the first complete
placement this search reaches. Where only one seating satisfies the conditions
at all, the search finds that one.

A vault's headroom is its capacity less its load.

## The residual pool and the lanes

The frames a cycle's vaults do not consume form the residual pool: the sum,
across every vault in the charter, of that vault's headroom.

The lane charter lists the lab's overflow lanes. Each lane carries a lane
rank, a residual share expressed as a numerator and a denominator, the
deliverable classes it accepts and the settlement groups it accepts.

Lanes draw on the residual pool in ascending lane rank. A lane's capacity is
its residual share of the pool as the pool stands when that lane draws,
rounded down to a whole frame. Held programmes are offered to a lane in
descending order of settled frames, ties broken by ascending programme
identifier, and a lane takes a programme when it accepts that programme's
deliverable class and settlement group and its remaining capacity is at least
the programme's settled frames. When a lane finishes, the pool is reduced by
the frames that lane took, and the next lane draws against what is left.

A held programme that no lane took is *shed*. Shed programmes are settled and
counted, but they are stored nowhere this cycle.
