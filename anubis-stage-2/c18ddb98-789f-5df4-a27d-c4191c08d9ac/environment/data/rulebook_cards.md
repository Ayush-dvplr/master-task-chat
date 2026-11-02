# Rulebook: cards

Filed under C in the platform reference set. A rate card is one edition of the
platform charging material. This rulebook says which edition governs a landing
record. It says nothing about what is then done with the numbers on that
edition.

## C1 Effective intervals

A card carries an instant from which it is effective and, optionally, an instant
at which it was superseded. A card is live at an instant when the instant is at
or after the card effective instant and, if the card carries a supersession
instant, strictly before it. A card with no supersession instant recorded stays
live indefinitely once it becomes effective.

Editions are filed as they are issued, so the register is not sorted by
effective instant and intervals overlap freely. More than one card can be live
at the same instant, and a card can become effective while an older card is
still live.

## C2 Which live card governs

Among the cards live at the emission instant of a landing record, the one with
the latest effective instant governs that record. Where two live cards share the
same latest effective instant, the one whose card identifier is greatest when
compared as text governs.

A card that is never the governing card for any record in the window still
belongs in the register. Its presence is not an error and it must not be
removed.

## C3 What a card carries

A card carries one rate in micros for each tier class a landing record can
declare, and one multiplier in basis points for each form class a landing record
can declare. The rate that speaks for a record is the one matching the tier
class the record declares. The multiplier that speaks for a record is the one
matching the form class the record declares.

## C4 Windows are not required to be covered

Nothing obliges the card register to cover every instant of a window. Where no
card is live at the emission instant of a record, no card governs it. The
consequence of that is stated under admission.

## C5 The governing card is reported

The ledger names the governing card for every record that reached it. Where no
card governed, the ledger carries an empty card identifier for that record
rather than omitting the field.
