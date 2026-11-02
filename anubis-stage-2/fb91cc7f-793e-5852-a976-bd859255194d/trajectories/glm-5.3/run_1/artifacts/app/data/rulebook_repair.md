# Rulebook: repair

Restoration nodes work defects. A node submits a repair claiming a number of
frames against one defect. This rulebook says which claims stand and how much
of a standing claim the lab accepts.

## What a repair names

A repair names the defect it works, the pass it belongs to, the class of the
node that ran it, the frames it claims, and the cycle it was submitted in.

## Passes

Repairs are worked in passes. A pass is a sweep of the whole cycle's defect
list, so a defect may be worked in several passes by several nodes. Repairs in
an earlier pass are worked before repairs in a later one. Within a pass,
repairs are worked in ascending repair identifier.

That working order runs across every repair raised against a programme, not
only across the repairs raised against one of its defects. A programme's
repairs are laid out in a single sequence, earlier pass first and ascending
repair identifier inside a pass, and the lab works that sequence from the
front.

## The repair window

Every programme carries a window close cycle. A repair submitted after the
window closed on the programme its defect belongs to does not stand: the
customer had already taken delivery. Such a repair recovers nothing, and it
stays in the record marked as having been submitted outside the repair window.

A repair submitted in or before the window close cycle is within the window,
however early. The greenlit cycle on a programme records when the work was
commissioned; it does not bound repair submission.

## Node class

A restoration node's class is the worst defect severity it is competent to
work. A node may work a defect whose severity is at or below its class. A
repair by a node whose class is below the severity of the defect it claims
does not stand: it recovers nothing, and it stays in the record marked as
having been worked by a node whose class is below the defect's severity.

One repair can fail both tests at once. The record carries one mark for a
repair, and for a repair that was submitted after the window closed and was
also worked by a node below the defect's severity, that mark is the window
one: the customer had taken delivery before the class of the node that
worked it mattered to anybody. The lab tests the window first and reaches
the node class only for a repair that was submitted in time.

## The pass ceiling

Take the repairs recorded against one defect in the working order set out
above. The first of them may recover as much as that defect covers. Every one
after it is working ground that has already been gone over, and the lab allows
it to recover only a fraction of what the repair before it in that order could
have recovered. The fraction is a standing house convention, is the same for
every defect in every cycle, and is not written down here. It is recoverable
from the published calibration cycle.

The ceiling falls at every step along that order whether or not the previous
repair recovered anything, and whether or not the previous repair stood. A
repair that recovers nothing still consumed its place in the order.

## What a standing repair recovers

A repair that stands recovers the frames it claims, but never more than the
pass ceiling that applies to it, never more than the defect has left to give,
and never more than the programme has left to give.

A defect has left to give whatever it covers after clipping, less whatever
earlier repairs have already recovered against it. A programme has left to
give the frames it was impaired by, less whatever earlier repairs in its
working order have already recovered against any of its defects.

A standing repair that is held below its claim by the ceiling, by what the
defect has left or by what the programme has left is *clamped*, and it stays
in the record marked as clamped. A standing repair that recovers exactly what
it claimed is marked as accepted.

## Recovery and the programme bound

Recovery accrues to the defect. A programme's recovered frames are the sum of
the frames recovered against that programme's defects.

The two bounds are not one bound. A defect is held to what it covers after
clipping, and two defects on one programme may cover the same picture, so the
frames a programme's defects cover between them can come to more than the
frames the programme is impaired by. The programme bound is what holds the two
in step, and because it is spent along the working order set out above, which
repairs it clamps depends on where they sit in that order.

Repairs against a defect belonging to a voided programme recover nothing.
