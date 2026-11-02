# Rulebook: cadence

A programme is conformed from film or tape elements that were scanned at
whatever cadence their carrier ran at. It is delivered at the cadence its
contract names. The two are rarely the same, and the difference is the whole
of this subsystem.

## Where the lab measures

**The lab settles a programme at its delivery cadence, not at the cadence of
the element it was conformed from.**

This is the house position and it is not the industry default. Most facilities
bill the scan: a frame that existed on the carrier is a frame that was worked,
and pulldown or decimation performed downstream is treated as a delivery
formality that changes nothing billable. This lab takes the opposite view. The
deliverable is what the customer receives, so the deliverable is what is
measured. Frames that pulldown introduces on the way to a faster delivery
cadence are billable frames, because they exist in the thing delivered. Frames
that decimation removes on the way to a slower delivery cadence are not
billable, because they do not exist in the thing delivered.

A programme conformed from a 24000 element and delivered at 29970 therefore
settles for materially more than the frames its element carried. A programme
conformed from a 29970 element and delivered at 24000 settles for materially
less. Neither is an error and neither is corrected anywhere downstream.

The conversion is proportional: a count of frames measured at one cadence
becomes, at another cadence, that count in the same ratio as the two cadences.
Because frames are whole things, the converted count is quantised to a whole
frame under the lab's standing quantisation convention. That convention is not
written down here; it is the same convention everywhere in the lab, and the
published calibration cycle exists so that it can be recovered.

## The governing element

A programme may be conformed from more than one element, and those elements
may have been scanned at different cadences. The programme converts from the
cadence of its governing element, which the conform rulebook defines.

## Condition bands

A settled programme carries a condition grade. The grade describes how much of
the programme survived impairment, measured against the programme's frame
count at its delivery cadence before any impairment or credit is applied:

  - grade A: the settled count is at least 95 per cent of that figure
  - grade B: at least 85 per cent
  - grade C: at least 70 per cent
  - grade D: below 70 per cent

## Restoration credit

Frames recovered by the repair subsystem earn restoration credit, and the
credit a recovered frame earns depends on the grade the programme settles at:

  - at grade A a recovered frame earns one frame of credit
  - at grade B, three quarters of a frame
  - at grade C, one half of a frame
  - at grade D, one quarter of a frame

Credit is quantised to whole frames under the same standing convention.

## The settled count

Three things act on a programme's frame count on the way to its settled
figure: the cadence conversion described above, the deduction of the frames
lost to impairment that repair did not recover, and the addition of
restoration credit. Each is defined in isolation; the order in which the lab
composes them is a standing house convention, is the same for every programme
in every cycle, and is not written down here. Different orders give different
figures, because quantisation does not commute, so the order is recoverable
from the published calibration cycle and from nothing else.

## Stability of the grade

The grade determines the credit, the credit contributes to the settled count,
and the settled count determines the grade. A programme's grade is settled
when it is the grade the programme's own settled count falls into. Where more
than one grade holds that way, the lab settles the highest of them, A ahead of
B ahead of C ahead of D.
