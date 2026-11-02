# Stall journal wire rules

The stall reporter writes one journal file per capture. A line whose first
character is a number sign is a comment. A line that begins with an at sign
followed by a vertical bar opens a segment; every line after it, up to the next
such line or the end of the file, is a body line of that segment.

## Header line

The header is a vertical bar separated line. After the opening at sign its
fields stand in this order: the segment identifier, the worker column, the
declared body line count, the origin numeral written in hexadecimal, the flag
word written in hexadecimal, the segment key written in decimal, and the
segment check total written in hexadecimal.

## Body line

A body line is a vertical bar separated line of ten fields, in this order: the
slot, the wait span, the hold span, the spin count, the depth, the blocked lock
class, the owner column, the symbol column, the wait for token, and the line
check total.

The wait span, the hold span and the depth are decimal integers. The wait span
and the hold span are nanosecond counts. The wait for token is sixteen
hexadecimal characters.

## Check totals

A line check total is the low sixteen bits of the sum of the character codes of
that line up to but not including the separator before the check field itself,
written as four hexadecimal digits.

A segment check total is the low sixteen bits of the sum of the line check
totals of every body line the segment carries, written as four hexadecimal
digits.

## Flag word

The flag word of a segment is a bit set. Each bit below is stated on its own
and holds for the whole segment. A bit that is clear says nothing at all.

`0x001` The wait column carries differences. The first body line of the segment
carries its wait span outright. Every later line carries the signed difference
between its own wait span and the wait span of the line before it, in the zig
zag mapping that sends a whole number n to twice n and a negative number n to
twice the magnitude of n less one.

`0x002` The hold column is combined by exclusive or with the low bits of the
wait span of the line before it in the segment. The count of low bits taken is
a withheld constant. The first body line of the segment uses a wait span of
zero for this purpose.

`0x004` The body lines of the segment stand in a stride order rather than in
logical order. The writing positions are taken in logical order: begin at the
first position of the segment, and after taking a position advance by the
stride, wrapping at the end of the segment and stepping forward one position at
a time over any position already taken. The stride is a withheld constant.

`0x008` The declared body line count is raised above the true event count by
the segment key taken modulo a withheld window. The body lines past the true
event count are padding and carry no event, although they are ordinary body
lines in every other respect and are covered by the segment check total.

`0x010` The origin numeral is written with its byte pairs in the opposite
order.

`0x020` The origin numeral holds the distance from the origin of the segment
before it in the same file rather than the origin itself. The first segment of
a file carries its own origin.

`0x040` A symbol column that opens with an exclamation mark marks the body line
that follows it in logical order. That following line carries the bitwise
complement of its depth within a withheld width. The exclamation mark is not
part of the symbol.

`0x080` An owner column that opens with a circumflex names a slot of the
rolling owner window rather than an owner. The window has a withheld width and
holds one owner per slot. Every body line of the file, in logical order, writes
its own owner into the window slot that its position in the file reaches, the
slots being filled in turn and wrapping at the width. A line reads its slot
before it writes its own.

`0x100` A spin column that opens with a tilde carries the spin count divided by
a withheld coarse unit.

`0x200` The wait for token is rotated to the left before its line check total
is taken, by the slot of that line plus a withheld offset, taken modulo the
sixteen character token width.

`0x400` The worker column of the header carries a tag the thread registry maps
rather than a worker that stands in its own right.

`0x800` The slot column is a placeholder. The authoritative slot of the line is
the number that stands after the colon of its symbol column, and that number and
the colon are not part of the symbol.

## Reach of the carried state

The rolling owner window and the origin distance run across the whole file. The
wait difference chain and the hold mask run inside one segment and start again
at the first body line of the next.
