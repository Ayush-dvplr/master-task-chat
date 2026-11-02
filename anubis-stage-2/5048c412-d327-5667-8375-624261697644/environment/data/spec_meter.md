# Meter file grammar

`ob_s3.bin` holds the season's meter records as a binary container. This document states its whole grammar. Every multi-byte integer is unsigned and big-endian (most significant byte first). Offsets count bytes from the start of the file, the first byte being offset 0.

## Layout

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | Magic: the ASCII bytes `OBS3`. |
| 4 | 1 | Version: 1. |
| 5 | 7 | Season label, ASCII. |
| 12 | 2 | Record count: the number of records that follow. |
| 14 | varies | The records, one after another, exactly as many as the record count says. |
| last 4 bytes | 4 | Checksum: the CRC-32 (the polynomial and conventions of `zlib.crc32`) of every byte from offset 4 up to and including the last byte of the last record. |

Nothing lies between the last record and the checksum. A file whose magic or version differs, whose checksum does not match, whose records end before or after the checksum, or that holds a record this grammar does not allow, breaks the meter rules: the extract cannot be balanced.

## Selector byte

Every record starts with one selector byte. Its bits, numbered from 7 (the most significant) to 0:

| Bits | Meaning |
|---|---|
| 7 and 6 | Record kind, read as a two-bit number: 0 a reading, 1 a correction, 2 a replacement. Kind 3 is not allowed. |
| 5 | Form of the record's first gauge number: 0 literal, 1 dictionary reference. |
| 4 | Form of the value of a reading or correction: 0 absolute, 1 delta. A replacement carries no value, so in a replacement this bit carries no meaning and is ignored, as the filler is. |
| 3 | Form of the second gauge number of a replacement, as bit 5. It is 0 in readings and corrections; a reading or correction with bit 3 set is not allowed. |
| 2 to 0 | Filler: carries no meaning and is ignored. |

## Fields after the selector

| Kind | Fields, in order |
|---|---|
| Reading | gauge number; value |
| Correction | gauge number; value; day (1 byte) |
| Replacement | retired gauge number; current gauge number |

A gauge number in literal form is 2 bytes: the digits of the gauge number after its `G`, read as an integer. A gauge number in reference form is 1 byte: a position in the gauge dictionary, counted from 0. A reference to a position the dictionary does not yet hold is not allowed.

A value is one signed integer written as a variable-length integer: the bytes carry 7 bits each, least significant group first; the high bit (value 128) of a byte is set when another byte of the same integer follows and clear on its last byte. The unsigned integer u so read stands for the signed integer u / 2 when u is even and -(u + 1) / 2 when u is odd.

The day of a correction is the day of the season, day 1 being 2026-07-01 and day 92 being 2026-09-30.

## Gauge dictionary

The gauge dictionary is a list that starts empty at the first record. Each gauge number written in literal form, in any kind of record and in either position of a replacement, is appended to the end of the list when the list does not already hold it; a gauge number the list already holds is not appended again. Numbers read through a reference are not appended.

## Running value

The running value starts at 0 at the first record. The value of a reading or a correction in absolute form is the integer written. In delta form it is the running value plus the integer written. After each reading and each correction, the running value becomes that record's value. Replacements leave it unchanged.

## Meaning of the records

A reading gives a gauge's meter reading at the start of the season, in megalitres. A correction gives a corrected reading for a gauge and the day the correction was filed. A replacement records that the meter numbered by the retired gauge number was replaced by the meter numbered by the current gauge number; the current number is the one `xw_codes.csv` gives. How readings, corrections and replacements combine is stated in `dict_register.md`.
