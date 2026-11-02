# The probe wire format

The probes of a shift are not shipped as text. Each shift carries its probes in
one binary file, `probes.bin` (and the worked example in `example_probes.bin`),
written in the format below. Decode it to recover the probe records, then feed
them to the gate. The format is fixed and fully described here; there is nothing
to guess about the bytes themselves. Every integer is little-endian.

## Layout

```
+--------+------------------+-----------------------------------------+
| magic  |   record_count   |            record_count records         |
| 4 bytes|     u32 LE       |                                         |
+--------+------------------+-----------------------------------------+
```

- `magic`: the four ASCII bytes `50 52 42 45` (`PRBE`). Any other value is not a
  probe file.
- `record_count`: an unsigned 32-bit little-endian count of the records that
  follow.

The records are stored in an arbitrary order. The gate, not this format, decides
the order probes resolve in (see `gate.md`).

## One record

Each record is these ten fields back to back, in this exact order:

| order | field | encoding |
|---|---|---|
| 1 | `seq` | i32 LE, signed |
| 2 | `meter` | i32 LE, signed (it may be negative) |
| 3 | `rows` | i32 LE, signed |
| 4 | `spans` | i32 LE, signed |
| 5 | `replays` | i32 LE, signed |
| 6 | `endpoint` | 1-byte unsigned length, then that many UTF-8 bytes |
| 7 | `tag` | 1-byte unsigned length, then that many UTF-8 bytes |
| 8 | `caller` | 1-byte unsigned length, then that many UTF-8 bytes |
| 9 | `mode` | 1-byte unsigned length, then that many UTF-8 bytes |
| 10 | `phase` | 1-byte unsigned length, then that many UTF-8 bytes |

The five integers come first as a fixed 20-byte block (`seq`, `meter`, `rows`,
`spans`, `replays` in that order), then the five strings, each a single length
byte followed by its UTF-8 bytes. A record carries no padding and no trailing
field, so the next record begins at the byte after the last string.

What each field means, how the `meter` value has to be read back, and how the
gate turns these records into the four reports are all in `gate.md` and
`reports.md`.
