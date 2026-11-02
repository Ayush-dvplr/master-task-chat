# DESIGN SUMMARY - vendor-archive-roundtrip-recovery (for master chat)

Archetype format-recovery, category data-processing, seed 284611. GEN+QC fingerprints match 9b8229f6.

WHAT: decode.py + encode.py for an invented stateful binary container VARC1 + the 4 fixed /app/out
reports. The full contract is in shipped spec files; the hard part is building it, not reading it.
FORMAT: 16-byte header (magic VARC1, version 2, flags, stream_id, seq_no, rec_count, revision, reserved).
Frames = SYNC 0xAA, selector (mode raw/delta/dict/reset + wide/long_key/has_ext), key (u8 or uvarint-len
utf8), 1-byte fchk, uvarint body_len, escaped body (ESC 0x1B, bounded by body_len) holding value + opaque
extension TLVs. Trailer CRC32 LE covers the header only (offsets 5..14), so in-band frame damage is caught
by fchk + resync, not the trailer. A stream = ordered segment files sharing dict/cumulator/seq state.
LEVERS (all HIDDEN-ONLY: visible data cannot separate right reading from reflex):
- LV-VA-1 stream state across files: dict/delta/reset continue across `--stream` segments; visible refs all
  stay in-file so per-file reflex matches; hidden manifests put a ref across segments.
- LV-VA-2 opaque extensions on MODIFIED records: encode keeps unknown TLVs in position, recomputes
  len+fchk+CRC; visible captures are never modified so round-trip never tests the modify path.
- LV-VA-3 framing-aware escaping: unescape bounded by body_len, boundary ESC must not merge frames; visible
  bodies never put an escapable byte at the boundary.
- LV-VA-4 representation memory: non-shortest LEB128 reproduced at original length for unmodified frames,
  shortest for new/modified; all visible varints are shortest.
- LV-VA-5 rejection precedence (F): bad_magic > unsupported_version > reserved_not_zero >
  record_count_overflow > trailer_crc_mismatch, exact error objects + 0-based offsets; hidden multi-defect
  files force the order (adjacent pairs + all_defects).
- LV-VA-6 resync (salvage): bad/failed-fchk frame -> one damage record, resume at next SYNC, no false
  resync on a non-boundary 0xAA; visible captures all clean.
- A composition: hidden frames combine escaped-SYNC extension + cross-file dict + non-identity revision
  remap + overlong delta, graded on value AND byte-exact (one rule right still fails).
- B chain: entry points decode.py <f>, --stream, --salvage, encode.py; stages graded on verifier-supplied
  correct intermediates so one early slip does not zero the score.
DATA (flat, >=5 formats): record files (A5 >=2000 lines each, ~20500 total, all load-bearing)
capture_catalog.jsonl (visible clean captures = reflex trap), frame_index.jsonl, field_layouts.csv,
symbol_table.tsv, transport_errors.log; specs format_contract.md, escape_rules.md, revision_notes.md,
decoder_appendix.md, revision_map.ini, schema_registry.json, crc_profiles.json; binary visible example
capture_alpha.varc + capture_beta.varc (one stream, NO cross-file refs). No answer keys shipped.
TESTS/JUDGE/BASELINES: ~45-55 positives (>=0.8 weight on composition + new-lever + modified/overlong/
cross-file/resync), 5 negatives (hardcode, filename-key, runtime data read, dep rebind, nondeterminism),
one wrong-impl per lever confirmed to lose its points; judge ~14-16 concrete-fact criteria + 1 code
quality. Targets: S2 reflex <=0.10, S4 careful 0.10-0.20, oracle 1.0. OPEN: Q18 provenance (keep generator
authored_by/status; VB15.5 vs DS-27); oracle needs solve.py <20% shared with verifier encoder; resync
re-validates a candidate SYNC. Full byte layout, key lists, rejection catalogue, 4 chains in DESIGN.md.
