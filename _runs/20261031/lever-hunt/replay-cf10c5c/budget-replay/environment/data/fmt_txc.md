# tx_c.bin layout

tx_c.bin is a binary file: a header, then the records one after another, then a trailer. Every multi-byte integer of fixed width is big-endian.

## Header

| offset | width | field |
|---|---|---|
| 0 | 4 | the ASCII bytes `TXC1` |
| 4 | 1 | filler: any value, carrying no meaning |
| 5 | 2 | record count, unsigned |

## Number encodings

A varint is an unsigned integer written seven bits per byte, least significant group first; every byte but the last of a varint has its high bit set, and the low seven bits of each byte carry the group. A signed varint is a varint holding the zigzag form of a signed integer: a value v of zero or more is held as 2v, a negative value v as -2v-1.

A day number counts days after 2026-08-31: 2026-09-01 is day 1, 2026-08-31 is day 0, 2026-08-30 is day -1, and 2026-10-01 is day 31.

## Records

Each record begins with a selector byte. Bits 0 and 1 (the two lowest bits, read as a number from 0 to 3) give the record's mode: 0 literal, 1 follow-on, 2 back-reference. Bit 2 set marks a malformed record, which has no amount field. Bits 3 to 7 are zero. No record has mode 3.

After the selector, every record holds its transaction number as a varint. The record's transaction id is the letter T followed by its transaction number written as five decimal digits.

The rest of the record depends on its mode, in this order:

| mode | fields after the transaction number |
|---|---|
| literal | code length (one byte, unsigned), the envelope code in that many ASCII bytes, day number as a signed varint |
| follow-on | day number less the day number of the record before it, as a signed varint |
| back-reference | dictionary position (one byte, unsigned), day number as a signed varint |

A record that is not malformed ends with its amount: the signed cents of the row as a signed varint, positive adding to the envelope and negative taking from it.

A follow-on record names the same envelope as the record before it.

## Running state and dictionary

"The record before it" is the record immediately preceding in the file, whatever its mode and whether or not it is malformed; every record, malformed records included, sets the day number and envelope that the next record reads.

The dictionary starts empty. A literal record whose envelope code matches no dictionary entry, compared without regard to letter case, adds its code to the dictionary as the newest entry; a literal record whose code matches an entry adds nothing. A back-reference record names the envelope of the dictionary entry at its dictionary position, counted from the newest entry: position 0 is the newest entry, position 1 the one added before it, and so on.

## Trailer

The last four bytes are an unsigned 32-bit checksum: the CRC-32 (the polynomial and conventions of zlib's crc32, initial value 0) of every byte of the file before the trailer. A file whose trailer differs from that checksum breaks a rule of the inputs.
