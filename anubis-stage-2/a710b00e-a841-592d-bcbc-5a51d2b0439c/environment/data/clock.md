# Clock evidence and event replay

sources.csv names each source and its signed integer unit_numerator. For each
epoch named in epochs.csv, every source has an unknown integer offset in the
inclusive range zero through 38. An offset may differ between epochs. The offset
for a record is selected under the applicability definition in dictionary.md.

clock_residues.csv contains epoch,equation,residue. clock_terms.csv contains
epoch,equation,source,coefficient,power,shift. For each term, first add shift to
that source's offset and reduce modulo 41, then raise it to power modulo 41.
Multiply the result by coefficient. The sum of those term values has remainder
residue on division by 41. For one epoch and source, every term has the same
power and shift. Powers are positive and relatively prime to 40. Terms with the
same source add. A missing term has coefficient zero. Remainders are zero through
40, including for negative sums. All rows of evidence apply together. The
admissible offsets satisfy every equation and the stated range.
An assignment is unique only if exactly one vector in that range satisfies it.

events.csv contains event,source,captured,stamp,alias,quantity. event is an integer
identifier. Event instant is stamp minus the applicable offset. Unit quantity
is quantity times that source's unit_numerator. The identity is the identity
from aliases.csv whose alias matches and whose half-open start,end interval
contains the event instant. A row with zero or multiple matching identities is
an error. Identity intervals use event instant; epoch intervals use captured,
as defined in dictionary.md. These operands must remain distinct.

Order events by ascending event instant, breaking ties by integer event
identifier. The North running state starts at zero. For each event it becomes
the remainder of previous state times clock_multiplier plus unit quantity plus
event instant times event identifier, divided by clock_modulus. The state after
this event belongs to that event. The final state of an empty lane is zero.
