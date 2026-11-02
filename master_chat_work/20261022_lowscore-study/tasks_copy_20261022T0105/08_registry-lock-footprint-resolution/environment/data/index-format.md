# Registry index shard format

An index shard is one binary file. Every integer is unsigned and little endian unless a transform
below says otherwise. A version travels as a version code: the major number times 65536, plus the
minor number times 256, plus the patch number. CRC-32 means the standard zlib CRC-32.

## Shard header, 20 bytes

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | magic `PIDX` |
| 4 | 1 | format version, always 2 |
| 5 | 1 | tier marker: 0 rehearsal, 1 calibration, 2 field |
| 6 | 2 | flag word |
| 8 | 4 | shard nonce |
| 12 | 4 | block area length: the number of bytes after the header |
| 16 | 2 | stored block count |
| 18 | 2 | header check: the low 16 bits of the CRC-32 of bytes 0 to 17 |

## Block

A block carries the versions that one registry name published. It is a 10 byte block header, the
version records of the block, and a 4 byte block trailer.

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | package key |
| 4 | 2 | record count |
| 6 | 4 | block nonce |

The block trailer is the CRC-32 of every byte from the start of the block header to the end of the
last record of the block, exactly as those bytes sit in the file. Records inside a block appear in
ascending version code, and the ordinal of a record is its zero based position inside its block.

## Version record

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | version code |
| 4 | 4 | artifact bytes |
| 8 | 2 | publish day |
| 10 | 2 | status word: the status byte in the high byte, the dependency entry count in the low byte |

The dependency entries of the record follow its status word. Status bit 0 marks a yanked version and
status bit 1 marks a deprecated version.

## Dependency entry, 14 bytes

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | target package key |
| 4 | 4 | lowest version code, inclusive |
| 8 | 4 | version code bound, exclusive |
| 12 | 1 | requested feature mask |
| 13 | 1 | gate: 255 means the entry always applies; any other value names the feature bit of the declaring package that switches the entry on |

## Optional transforms

Each set bit of the flag word switches on one transform. Five transforms use withheld registry
constants: the salt word, the window span, the bias limit, the rotation base and the shuffle
multiplier. Blocks are numbered from zero in logical order, which is the order in which the shard
writer produced them.

| bit | name | effect on the bytes |
| --- | --- | --- |
| 0x0001 | MASK_BYTES | the artifact bytes field holds the true value combined by exclusive or with a keystream word: the CRC-32 of the salt word in ASCII followed by the shard nonce (4 bytes), the block key (4 bytes) and the record ordinal (2 bytes), all little endian. The block key is the block nonce unless DRIFT_KEY is set |
| 0x0002 | CHAIN_VERSION | every record after the first in a block holds its version code minus the version code of the record before it, modulo 2^32 |
| 0x0004 | DELTA2_DAY | the publish day field of the record at ordinal k holds day(k) minus twice day(k-1) plus day(k-2), modulo 65536, where a day before the first record of the block counts as zero |
| 0x0008 | DRIFT_KEY | the block key is the block nonce combined by exclusive or with the sum, modulo 2^32, of the true artifact bytes of every record of every logically earlier block of the same shard |
| 0x0010 | BLOCK_PERMUTE | blocks sit in the file in a shuffled order. Start from the list 0 to count-1 and a state equal to the shard nonce; for i from count-1 down to 1, set the state to (state times multiplier plus 0x9E3779B9) modulo 2^32, let j be the state modulo (i+1) and swap list positions i and j. Position k of the final list names the logical block written k-th in the file |
| 0x0020 | BACKREF_DEPS | every dependency entry is preceded by a tag byte. Tag 0 means the 14 entry bytes follow. A tag t above 0 means no entry bytes follow and the entry equals slot span-t of the ring. The ring is a list of span entries, newest first, that begins every block filled with all zero entries; each entry of the block, once known, is placed at the front of the ring and the last slot is dropped. The writer uses a tag above 0 whenever the entry already sits in the ring |
| 0x0040 | ENDIAN_ISLAND | the shard nonce and every block record count are big endian |
| 0x0080 | BIASED_COUNT | the stored block count is the true count plus a bias: the low byte of the CRC-32 of the salt word in ASCII followed by the shard nonce (4 bytes, little endian), modulo the bias limit |
| 0x0100 | ROT_STATUS | the status word of the record at ordinal k is rotated left within 16 bits by (rotation base plus (k modulo 8)) modulo 16 bits, and the block trailer covers the rotated word |
| 0x0200 | XREF_KEY | the package key of every block is combined by exclusive or with the shard nonce of the companion shard, which is the shard of the same tier whose nonce is the next smaller one; the shard with the smallest nonce takes the shard with the largest nonce as its companion |
| 0x0400 | SPLIT_TAIL | every block trailer is followed by (block nonce modulo 7) zero bytes that no trailer covers |

A rehearsal shard carries a flag word of zero.
