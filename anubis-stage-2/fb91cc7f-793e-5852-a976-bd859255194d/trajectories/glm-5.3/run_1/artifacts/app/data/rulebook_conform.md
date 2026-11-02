# Rulebook: conform

Conform assembles a programme's timeline from shots cut out of scanned
elements. It runs after identity resolution and before anything is measured.

## Usable span of an element

A scanned element carries a frame count and, for photochemical carriers, a
head leader and a tail leader. Leader is laced onto the carrier to thread the
scanner; it is not picture and it is never conformed.

Negative, interpositive and print elements are photochemical. Their usable
span begins after the head leader and ends before the tail leader.

Tape elements are not photochemical. A tape carries no leader, and the head
leader and tail leader columns on a tape row are an artefact of a shared
scanning form. They are not picture boundaries and they do not reduce a tape
element's usable span. A tape element's usable span is the whole of it.

Usable spans are expressed in the coordinates of the element that carries
them. When identity resolution folds one element into another, the folded
element's usable span moves with it under the registration shift the identity
rulebook defines, and the surviving element's usable span is everything either
element could supply.

## Shots

A shot names a source element, an in frame, an out frame and a transition. The
in frame is the first frame of the shot; the out frame is the first frame past
it, so a shot's length is the difference between them. A shot with an out
frame at or before its in frame carries no picture.

Shot coordinates are written against the element as it was registered when the
shot was cut. When identity resolution has since folded that element into
another, the shot's coordinates move with it under the same registration
shift.

Every shot in a programme must lie wholly inside the usable span of the
element it is cut from, after any shift.

## Tiling

A programme's shots carry ordinals. The ordinals of a programme's shots must
run from one upwards with no gap and no repetition. Nothing else about the
ordinals is required: a shot's ordinal position in the programme has no
relation to which element it is cut from or where in that element it sits.

Shots are laid onto the programme timeline in ascending ordinal, each starting
where the previous one ended, beginning at zero. A programme's conformed frame
count is the length of that timeline.

## Voids

A programme is *voided* when it cannot be conformed. A voided programme is
carried in the cycle's records with the reason it voided, and it is settled
for nothing: it earns no frame count, it enters no draw, and it is seated
nowhere.

A programme voids when any of the following is true of it:

  - a shot names an element that no identity in the cycle resolves to
  - a shot names an element that has been retired
  - a shot carries no picture
  - a shot does not lie wholly inside the usable span of its element
  - the programme's shot ordinals do not tile
  - the programme has no shots at all

A void is a property of a programme, not of a shot. One bad shot voids the
whole programme.

## The governing element

A conformed programme converts from the cadence of its governing element.

The governing element is the element that supplies the programme with the
greatest number of frames. Where two elements supply the same number of
frames, the governing element is the one whose resolved identity sorts first.

Print elements are viewing copies. A print is duplicated from something else
and does not carry the cadence of record, so a print element does not govern a
programme while any element of another class supplies that programme, however
many frames the print supplies. Where every element a programme draws on is a
print, there is nothing else of record to govern by and the ranking above
stands unmodified.
