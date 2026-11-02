# Work order packet encoding

The dispatch authority receives work orders as binary packets. Three populations
travel over the same wire: a calibration population that the authority has already
settled and published control figures for, a field population that awaits
settlement, and a reference probe that the authority publishes untransformed
alongside its decoded values.

Every population is presented as block headers and block payloads. A payload holds
all of the records of one block concatenated end to end with no separators and no
padding. The tables that carry the headers, the payloads and the directories are
UTF-8 comma separated text with one header row, and spaces around a header name or
a cell are not part of it.

## Block header

A block header is twenty four bytes. Multi byte header words are big endian unless
the byte order transform below applies.

| Offset | Width | Meaning |
| --- | --- | --- |
| 0 | 2 | magic word, always 0x4C44 |
| 2 | 2 | block identifier |
| 4 | 2 | stored record count |
| 6 | 2 | transform flag word |
| 8 | 2 | lane hint |
| 10 | 2 | horizon slot |
| 12 | 2 | span hint |
| 14 | 2 | seed hint |
| 16 | 4 | payload checksum, CRC32 of the payload exactly as it travels |
| 20 | 4 | header checksum, CRC32 of header bytes 0 through 19 |

## Work order record

A record is thirteen bytes, or fifteen bytes when it carries the extended slack
field. Multi byte record fields are big endian.

| Offset | Width | Meaning |
| --- | --- | --- |
| 0 | 1 | control byte: the high nibble is the length code, the low nibble is the dispatch mode |
| 1 | 1 | alias index byte |
| 2 | 1 | programme reference byte |
| 3 | 4 | load units |
| 7 | 2 | due offset |
| 9 | 2 | dispatch weight |
| 11 | 1 | granularity code |
| 12 | 1 | submission day |
| 13 | 2 | extended slack, present only when the length code is one |

A length code of zero means a thirteen byte record. A length code of one means a
fifteen byte record. The dispatch mode is a value between zero and three. The
granularity code selects a granularity from the list 5, 10, 25, 50 by position.
The submission day is a value below 251.

The alias index byte selects an entry of the client directory: reduce it modulo the
number of directory entries and take the entry at that position in file order. The
programme reference byte selects an entry of the ascending list of distinct
programme identifiers in the same way, except that a value of 0xF0 or above is a
backward reference to an earlier record in the same block rather than a programme
selection, and the referring record inherits the programme of the record it points
at.

The due slot of a record is the horizon slot of its block plus the due offset plus
the extended slack. The remaining slack of a work order is its due slot minus its
submission day.

## Transform flag word

The flag word declares which wire transforms are live for that block. Each
transform is governed by a constant that the authority withholds. The published
control figures are the only place those constants are observable.

| Bit | Name | Withheld constant | Constant range |
| --- | --- | --- | --- |
| 0x001 | load mask | stream label | arc, beam, cinder, drift, ember |
| 0x002 | slack fold | chain seed | 0 through 255 |
| 0x004 | weight difference | delta span | 2 through 9 |
| 0x008 | day drift | drift modulus | 97, 101, 103, 107, 109 |
| 0x010 | block permutation | permute rounds | 1 through 4 |
| 0x020 | backward reference | window span | 2 through 8 |
| 0x040 | byte order island | island offset | 8, 10, 12, 14 |
| 0x080 | length shadow | shadow bias | 0 through 15 |
| 0x100 | alias rotor | alias rotor | 1 through 7 |
| 0x200 | payload rotation | rotate step | 1 through 7 |
| 0x400 | count bias | count bias | 0 through 7 |

Bits at 0x800 and above are reserved and are always clear.

## Transform semantics

- Load mask. The load units field travels exclusively ored with the first four
  bytes of HMAC-SHA256 over the key `lane-dispatch-authority` and the message
  formed by the stream label in UTF-8, a vertical bar, the block identifier as a
  big endian sixteen bit word, and the logical ordinal as a big endian sixteen bit
  word.
- Slack fold. The due offset field travels as the sum modulo 65536 of its own value
  and the due offset of the record one logical ordinal earlier. At the first
  logical ordinal of a block the earlier value is the chain seed.
- Weight difference. Dispatch weights travel as second order differences modulo
  65536 within groups of consecutive logical ordinals. A group holds delta span
  ordinals and the first group starts at logical ordinal zero. The first ordinal of
  a group carries its weight, the second carries the difference from the first, and
  every later ordinal carries the difference of differences.
- Day drift. The submission day travels as its own value multiplied by a drifting
  factor modulo 251. The factor is one plus the running sum of the load units of
  every genuine record decoded so far in that population, taken modulo one less
  than the drift modulus. The running sum starts at zero for each population and
  carries across block boundaries.
- Block permutation. Records travel in a permuted order. The permutation is a
  Fisher-Yates shuffle of the stored record count, applied repeatedly for permute
  rounds passes, walking indices downward from the last to the second and swapping
  each with an index drawn as the shuffle state modulo one plus the current index.
  The shuffle state starts at the block seed and advances by xorshift64 before each
  draw, where xorshift64 shifts left by 13, right by 7 and left by 17 within
  sixty four bits. The block seed is the first eight bytes, big endian, of
  HMAC-SHA256 over the key `lane-dispatch-authority` and the message formed by the
  ASCII text `block|` followed by the block identifier, lane hint, horizon slot,
  span hint and seed hint as five big endian sixteen bit words. The value at
  physical position p of the permutation is the logical ordinal of the record that
  travels at that position.
- Backward reference. A programme reference byte of 0xF0 or above names a record
  earlier in logical order. Subtract 0xF0, reduce modulo the window span, and add
  one to obtain how many logical ordinals back the referenced record sits.
- Byte order island. Exactly one of the four auxiliary header words at offsets 8,
  10, 12 and 14 travels little endian. The island offset names which one.
- Length shadow. The length code nibble travels exclusively ored with the shadow
  bias.
- Alias rotor. The alias index byte travels with the alias rotor added to the
  directory position modulo the number of directory entries.
- Payload rotation. The payload travels rotated left by the block identifier
  multiplied by the rotate step, reduced modulo the payload length. The payload
  checksum is taken over the payload exactly as it travels.
- Count bias. The stored record count exceeds the genuine record count by the count
  bias. The surplus records occupy the last logical ordinals of the block, are
  filler, and are no part of the settled population.

The reference probe carries a clear flag word in every block and is published
together with its decoded values.
