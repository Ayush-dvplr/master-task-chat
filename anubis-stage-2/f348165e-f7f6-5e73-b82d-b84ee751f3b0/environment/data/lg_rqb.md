# Request log container (RQB1)

Every request log of an extract is a binary file in the RQB1 container. This document gives its grammar. st_demand.md gives what the requests mean.

## Header

The file opens with a header of 21 bytes. Its fields, in this order:

| bytes | field | form |
|---|---|---|
| 0 to 3 | magic | the four ASCII characters RQB1 |
| 4 | version | the number 1 |
| 5 | class code | the position of the traffic class of the log in the class order visible, peak, steady, burst, latency, counted from 0 |
| 6 to 7 | request prefix | two ASCII characters |
| 8 to 11 | base instant | unsigned 32-bit big-endian count of seconds since 2026-01-01T00:00:00Z |
| 12 to 15 | record count | unsigned 32-bit big-endian count of the records in the file; filler bytes are not records |
| 16 | pad | one byte that carries no value |
| 17 to 20 | checksum | unsigned 32-bit big-endian CRC-32 (the CRC-32 of zlib and of ISO-HDLC: reflected polynomial 0xEDB88320, initial value and final exclusive-or 0xFFFFFFFF) of the pad byte followed by every byte from byte 21 to the end of the file |

The checksum region is byte 16 and bytes 21 to the end; the four checksum bytes themselves are outside it.

## Number and text forms

An unsigned number is written in groups of seven bits, lowest group first, one group per byte in the low seven bits; bit 7 of a byte is set when another byte of the same number follows and clear on its last byte. A number may carry more groups than it needs (high groups of zero bits); it reads the same.

A signed number is an unsigned number n read in zigzag form: n/2 when n is even, and -(n+1)/2 when n is odd.

A text is one byte giving its length in bytes, followed by that many ASCII bytes.

## Records

Bytes 21 to the end of the file are records and filler bytes, one after another. Each starts with a selector byte:

| bits | value | meaning |
|---|---|---|
| 0 to 1 | selector AND 3 | mode: 0 literal, 1 delta, 2 repeat, 3 filler |
| 2 to 3 | (selector shifted right by 2) AND 3 | status: 0 ok, 1 cut, 2 rejected, 3 a status outside the contract |
| 4 | 16 | the key is written as a back-reference |
| 5 | 32 | a class byte follows the selector |
| 6 | 64 | the model is written as an index |
| 7 | 128 | never set in a well formed log |

A filler is the single byte 3 (mode 3, every other bit clear). Nothing follows it, it is not a record, and it changes no state.

After the selector, a literal record and a delta record hold, in this order: the class byte when bit 5 is set (a class code as in the header); the request number (unsigned); the key (an unsigned back-reference when bit 4 is set, otherwise a text); the model (an unsigned index when bit 6 is set, otherwise a text); the prompt token count (unsigned); the completion token count (unsigned); the instant field (signed).

A repeat record holds, in this order: the class byte when bit 5 is set; the request number; the prompt token count; the completion token count; the instant field. Bits 4 and 6 of its selector are clear. Its key and its model are the key and the model of the record immediately before it in the file, whatever that record's mode and status. A repeat record is never the first record of a file.

## Tables and running state

Key table: empty at the start of the file. A key written as text is appended at the end of the table unless the table already holds it, in which case the table is unchanged. A back-reference r names the entry r places before the last entry of the table: 0 names the last entry, 1 the entry before it, and so on.

Model table: empty at the start of the file. A model written as text is appended at the end unless the table already holds it. An index i names the entry at position i counted from the first entry, which is position 0.

Running instant: before the first record it is the base instant of the header. The instant of a literal record is the base instant plus its instant field. The instant of a delta record or a repeat record is the running instant plus its instant field. After every record, of any mode, the running instant becomes the instant of that record.

## The request of a record

Every record is one request of the log:

| request field | value |
|---|---|
| req_id | rq- followed by the request prefix and the request number written with five digits, leading zeros kept |
| api_key | the key of the record |
| model | the model of the record |
| prompt_tok | the prompt token count |
| completion_tok | the completion token count |
| done_at | the instant of the record, as seconds since 2026-01-01T00:00:00Z, written YYYY-MM-DDTHH:MM:SSZ |
| status | the status of the selector |
| traffic_class | the class of the class byte when the record has one, otherwise the class of the header |

## Well formed logs

A request log is well formed when its magic and version are as above, its checksum matches its checksum region, no selector has bit 7 set, no record has status 3, every back-reference and index names an entry of its table, every record is complete, and the number of records equals the record count of the header. ct_svc.md treats a log that is not well formed as a broken invariant.

Bytes: no request log holds a carriage return byte immediately followed by a line feed byte, nor two left braces or two right braces in a row. A writer keeps to this by writing a number with one more group than it needs or by placing a filler byte between two records; neither changes what the log means. A reader takes every byte as it stands; it never translates line ends.
