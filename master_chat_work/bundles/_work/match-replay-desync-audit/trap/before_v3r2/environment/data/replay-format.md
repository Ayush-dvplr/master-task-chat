# RPL1 capture container

Ninefold Marches writes one capture file per match. A capture is ASCII text with line feed endings
and carries the entries the simulation recorded while the match ran.

## Header

The first line of a capture is the header. It begins with `#RPL1` and then carries space separated
`key=value` fields.

- `capture` is the capture stem.
- `number` is the capture ordinal. Captures form a ring and the ordinal is that ring position.
- `flags` is a four digit hexadecimal word. Each bit of it names one space saving transform that the
  shipping serializer applied to this capture. A bit that is clear means the transform was skipped.
  The twelve transforms are described below, one per bit, in bit order from the least significant.
- `blocks` is the number of block lines the capture carries.
- `frames` is the entry count the serializer declared.
- `words` is a comma separated list of unit words. It is always plaintext and it is always this
  capture's own list.
- `seal` is a digest over the capture ordinal and the number of entries the capture truly carries.

## Blocks and entries

After the header the capture alternates block lines and entry lines. A block line begins with `B`
and carries the block ordinal, a declared width and a block check word. The declared width is the
number of entry lines that follow before the next block line or the end of the file. Block ordinals
count from zero.

An entry line begins with `R` and carries one hexadecimal payload.

The block check word is a digest over the capture ordinal, the block ordinal and the declared width.
It reads nothing from the payloads, so a transform that rewrites a payload or restates a count leaves
every block check word untouched.

## Entry payload

An entry payload that has had every transform undone is twelve bytes:

| offset | width | field |
|---|---|---|
| 0 | 2 | tick |
| 2 | 2 | unit index |
| 4 | 1 | kind |
| 5 | 4 | amount |
| 9 | 1 | mark |
| 10 | 2 | check |

Multi byte fields are big endian unless a transform says otherwise. The check field is a digest over
the ten bytes that precede it.

`kind` is zero, one or two for an ordinary entry and three for a reversal. `mark` is scenery on an
ordinary entry and names the kind being reversed on a reversal.

A payload whose kind byte reads two hundred and twenty four is not an ordinary entry. It is an echo,
and its unit index, amount and mark fields are written as zero.

`unit index` selects a unit word. Which list it indexes into is settled by the transforms below.

## The twelve transforms

Bit zero, **sealed**. Every payload of the capture is masked by a keystream. The keystream is drawn
from one of the twelve published label words together with the capture ordinal and the entry ordinal.

Bit one, **chained**. Every payload of the capture is masked a second time, and that mask is drawn
from the capture ordinal together with the tick and the amount of the entry that settled immediately
before it. The first entry of a capture uses zero for both.

Bit two, **stepped**. The tick field does not hold the tick. It holds the second difference of the
tick series across the capture. The first entry holds its tick, the second holds the difference
against the first, and every later entry holds the difference of differences. The field wraps at two
to the sixteen.

Bit three, **drifted**. Every payload of a block is masked by a block key. The block key is drawn
from the capture ordinal together with a counter, and the counter is the block ordinal advanced by
one and advanced again by five for every step of the capture ordinal, wrapped at the drift modulus.

Bit four, **woven**. The entry lines inside each block are restated in a permuted order. The
permutation is a Fisher and Yates shuffle whose seed is fixed by the weave seed offset, the capture
ordinal and the block ordinal, and it runs over the declared width of that block.

The shuffle reads from a counter. The counter is seeded with the weave seed offset advanced by 97
for every step of the capture ordinal and by 7 for every step of the block ordinal. That seed is
multiplied by 2654435761, advanced by 1013904223 and held to thirty two bits, and a seed that lands
on zero is replaced by 2654435769. Every draw folds the counter three times, exclusive or against
itself shifted left by 13, then against itself shifted right by 17, then against itself shifted left
by 5, holding to thirty two bits after each fold, and hands back the folded counter. The shuffle
starts an order that lists the block positions in their natural sequence, walks the positions from
the last down to the second, and at each position swaps the entry of the order there with the entry
of the order at the draw taken against that position advanced by one. The line standing in a given
position of the restated block is the line that stood in the position the finished order records for
it.

Bit five, **echoed**. Some entries are echoes. An echo reaches a distance back into the entries
already settled in this capture and takes the unit, the kind, the amount and the mark of the entry
that distance earlier, while keeping its own tick. The distance is the entry ordinal taken against
one less than the echo window span and then advanced by one, so it is at least one and never reaches
the echo window span.

Bit six, **flipped**. Inside exactly one block of the capture the multi byte fields are little endian
rather than big endian. That block is the one whose ordinal equals the capture ordinal taken against
the block count.

Bit seven, **padded**. The declared frame count overstates the number of entry lines the capture
carries. The overstatement is three times the capture ordinal plus one, taken against the frame bias
limit.

Bit eight, **shadowed**. The opening block of the capture declares a width larger than its true
width, and the surplus entry lines at the end of that block are filler. Their count is three fewer
than the shadow pad base. Filler payloads are drawn from the capture ordinal and the filler ordinal
and are shaped exactly like real payloads.

Bit nine, **spun**. Every payload of the capture is restated with its twelve bytes rotated left. The
rotation amount is the entry ordinal advanced by one, multiplied by the spin modulus, and taken
against twelve.

Bit ten, **aliased**. The unit index does not index this capture's own word list. It indexes the word
list published in the header of the donor capture, which is the capture whose ring ordinal sits the
alias donor shift ahead of this one, counted around the ring of six, and that list is read after it
has been rotated left by the alias donor shift. A capture that is not aliased indexes the twenty four
unit words published in the charter notes.

Bit eleven, **warded**. One reserved byte value is escaped inside every payload of the capture by
writing it twice. The reserved value is the sentinel code value, and the escape marker is that same
value.

## Tiers

Two captures in the shipped set carry a flag word of zero. Nothing was done to them, so their
payloads are already the twelve byte form above and they can be read directly. They are there so the
base layout can be confirmed before anything harder is attempted. They reveal nothing about which
label word, which seed, which span or which reserved value the transformed captures use.

Entry ordinals count true entries of the capture from zero and ignore filler.
