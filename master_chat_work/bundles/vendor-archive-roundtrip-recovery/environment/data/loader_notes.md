# Sluicegate loader notes

These are the operators' notes on how the retired Sluicegate batch loader
behaved while it was in service. They are kept for history. The format itself
is described by `format_contract.md`.

## Flushing

- The loader wrote one segment file per flush of a stream's buffer.
- A stream's segments were numbered from zero. When the loader restarted, the
  stream began a new run and numbering started again at zero.
- Every segment of a run except the last was written with `stream_continues`
  set. The last segment of a run was written with the bit clear.
- Segments of different streams were flushed in whatever order the buffers
  filled, so a batch of files usually interleaves several streams.

## Keys and revisions

- Sites on the older layouts wrote revisions 0 to 3. Sites moved to the newer
  layouts wrote revisions 4 to 7.
- Fields added after a layout freeze had no key byte, so the loader wrote them
  with a long key carrying the field name.
- A continuation segment written with revision byte 0 meant "no change": the
  loader resolved its short keys under the revision of the segment it
  continued.

## Frame buffers

- Frame buffers were reused between flushes, so a delta value was sometimes
  written in more bytes than it needed.
- Extension types the loader did not know were copied through untouched.
