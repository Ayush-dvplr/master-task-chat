# Rulebook: defect

Quality control raises a defect against a programme when a stretch of picture
is unfit to deliver. This rulebook says what a defect covers. What is done
about one is the repair subsystem's business.

## What a defect names

A defect names the programme it was raised against, the shot ordinal it was
seen in, a defect class, a severity, and the span of picture it covers. The
span is written in the coordinates of the programme's timeline: a start frame
and an end frame, where the end frame is the first frame past the defect.

A defect also carries the stage it was detected at. The stage records where in
the workflow the eye caught it and has no effect on how much picture the
defect covers.

Severity runs from one upwards. A higher number is a worse defect. Severity
does not change the extent of a defect; it constrains which repair nodes may
work on it.

## Clipping

A defect is only ever raised against picture that is actually in the
programme, so a defect covers only the part of its span that falls inside the
shot it was raised against. The part of a defect's span that falls outside
that shot covers nothing and is worth nothing.

A defect whose span, after clipping, has no length covers no picture at all.
It stays in the record and it earns nothing.

A defect raised against a programme that voided covers nothing, because that
programme has no timeline.

## Impairment

A programme's impaired frames are the frames of its timeline that at least one
of its defects covers.

Two defects raised against the same stretch of picture damage that stretch
once. A frame that three defects all cover is one impaired frame, not three.
The lab has been burned by suppliers who invoiced the same scratch three times
and it does not pay twice for the same frame.

Impairment is measured on the programme timeline, before any cadence
conversion.

## What impairment costs

Impaired frames that the repair subsystem does not recover are lost. Impaired
frames that repair recovers are not lost, and they earn restoration credit
under the cadence rulebook.

The frames a defect recovers can never exceed the frames that defect covers
after clipping.
