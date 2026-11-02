# DESIGN - vendor-archive-roundtrip-recovery

Harbor 0.24 input bundle, archetype `format-recovery`, category `data-processing`, seed `284611`.
Goal: a careful frontier agent scores ~0.10-0.20 on the tests channel; every graded rule is written
down; hardness comes only from composition (A), chaining (B), and the six VARC levers, never from
secrecy, volume, arithmetic or ambiguity.

Fixed archetype artifacts (VB 1.12, do not change): `/app/decode.py`, `/app/encode.py`,
`/app/out/decoded_examples.jsonl`, `/app/out/format_report.json`, `/app/out/roundtrip_report.json`,
`/app/out/error_analysis.json`. Structural musts kept from the scaffold: `solution/{solve.sh,solve.py,
TRUTH.md}`; `tests/test_output.py` defines `SAMPLE_SEED`, `CHALLENGE_SEED`, `EVAL_SEED`, `_write_corpus`,
a `__main__` block, and `@criterion` checks (validator §7.2); negative `negative_hardcoded_sample_answers`
required plus the four recommended negatives (§11).

================================================================================
## 1. The format: VARC1 (vendor archive container)

A `.varc` SEGMENT file is one chunk of one STREAM. A stream is an ordered list of segment files that
share a `stream_id` and carry dictionary + delta (cumulator) + sequence state ACROSS files.

### 1.1 Segment header (16 bytes, fixed)
| off | size | field | notes |
|----|----|----|----|
| 0  | 5 | magic | ASCII "VARC1" = 56 41 52 43 31 |
| 5  | 1 | version | supported value = 2 |
| 6  | 1 | flags | bit0 stream_continues (1 = more segments follow in this stream); bits1-7 = 0 |
| 7  | 2 | stream_id | u16 LE |
| 9  | 2 | seq_no | u16 LE, 0-based segment index within the stream |
| 11 | 2 | rec_count | u16 LE, number of frames |
| 13 | 1 | revision | field-id revision in force for this segment (see 1.4) |
| 14 | 2 | reserved | = 00 00 |

### 1.2 Frame (variable)
| part | encoding |
|----|----|
| SYNC | 1 byte 0xAA (the documented resync marker) |
| selector | 1 byte: bits0-1 mode (0 raw,1 delta,2 dict,3 reset); bit2 wide; bit3 long_key; bit4 has_ext; bits5-7 = 0 |
| key | short: 1 byte u8. long: uvarint(len) + len UTF-8 bytes |
| fchk | 1 byte = (sum of RAW unescaped body bytes) & 0xFF |
| body_len | uvarint: number of ESCAPED body bytes that follow |
| body | body_len bytes, escape-encoded (1.3). After unescaping -> value-bytes ++ extensions |

RAW body = value-bytes then (if has_ext) extension TLVs filling the remainder.
- raw mode: value-bytes = i32 LE (wide=1) or i16 LE (wide=0). `value` = that signed int.
- delta mode: value-bytes = signed LEB128 (may be non-shortest, see LV-VA-4). `value` = stream cumulator + delta; cumulator := value.
- dict mode: value-bytes = 1 byte u8 index. `value` = stream_resolved[len-1-index] (backward). cumulator := value.
- reset mode: value-bytes empty. Clears the stream's resolved list, cumulator:=0. Produces no resolved value.
- extensions: each TLV = type uvarint, len uvarint, value[len]. Types the schema does not define are OPAQUE: kept verbatim, in position (LV-VA-2).
After each non-reset frame, append `value` to the stream resolved list (dict source = resolved values).

### 1.3 Framing-aware escaping (LV-VA-3)
ESC = 0x1B. Inside a body, the two bytes 0xAA (SYNC) and 0x1B (ESC) are written as `1B (b XOR 0x20)`.
Unescaping is bounded to the `body_len` window: the decoder consumes exactly body_len escaped bytes and
unescapes within them only. A trailing ESC-like byte at the body boundary is still inside the window and
must not consume the following frame's SYNC. (Reflex bug: scan-until-SYNC or unescape past the window,
merging two frames.)

### 1.4 Revision remap (spine stage 5, part of A chain)
Short integer keys are field ids under the segment `revision`. `revision_map.ini` maps
`(revision, raw_key) -> canonical_field_id`; `field_layouts.csv` describes canonical fields
(id, name, type). Decode output carries both `raw_key` and the normalised `field` name. Long (UTF-8)
keys are already canonical names and skip remap. Reflex: identity map (field = raw_key).

### 1.5 Trailer
4 bytes CRC32 LE. `crc_coverage = "header"`: it covers ONLY header bytes offset 5..15 inclusive
(the 11 header bytes after the magic: version through the two reserved bytes). Frame bytes are NOT under the trailer CRC; in-band frame damage is
caught by `fchk` and the resync path, not by the trailer. (This is what lets rejection (whole-file,
header) and resync (in-band, per-frame) coexist without contradiction.)

================================================================================
## 2. Entry points (documented in instruction + format_contract.md)

- `python3 /app/decode.py <file.varc>` : decode one segment, fresh stream state. Prints one JSON object
  (shape 3.1) to stdout, exit 0; on a rejectable file prints one error object (4.1) and still exits 0.
- `python3 /app/decode.py --stream <manifest.json>` : decode an ordered multi-file stream, carrying
  per-stream state across files (LV-VA-1). manifest = `{"segments":[{"path":...},...]}` in processing
  order. Prints `{"segments":[<decode doc per file in order>]}`.
- `python3 /app/decode.py --salvage <file.varc>` : resync mode (LV-VA-6). Walks frames; on a frame that
  fails to parse or whose fchk is wrong, emits one damage record and scans forward to the next SYNC
  (0xAA at a frame boundary), then resumes. Prints `{"records":[...],"damaged":[{"from_offset":O,
  "resync_offset":S,"reason":R}]}`. Each damaged span reported once; frames inside it are neither
  silently skipped nor decoded.
- `python3 /app/encode.py <doc.json> <out.varc>` : encode a decode doc back to bytes. Byte-exact for an
  unmodified doc; canonical (shortest varint) for new records and for a field whose preserved token was
  dropped (modification); extensions re-emitted verbatim in position; header + trailer CRC recomputed.

Downstream isolation (lever B): the tests feed VERIFIER-BUILT correct intermediates to `--stream`,
`--salvage` and `encode.py`, so a bug in single-file decode does not zero the stream/salvage/encode
checks. Each stage's entry point and input shape are stated in the instruction.

================================================================================
## 3. Output shapes (all keys listed in format_contract.md for DS-25)

### 3.1 decode doc
```
{"magic_ok":true,"version":2,"stream_id":7,"seq_no":0,"revision":3,
 "flags":{"stream_continues":false},"record_count":N,
 "records":[
   {"raw_key":12,"field":"temp_c","mode":"delta","wide":null,"long_key":false,
    "delta_raw":5,"delta_raw_len":1,"value":105,"ext_present":false,"extensions":[]},
   {"raw_key":0,"field":null,"mode":"reset","wide":null,"long_key":false,"value":null,
    "ext_present":false,"extensions":[]},
   {"raw_key":3,"field":"flow","mode":"dict","wide":null,"long_key":false,
    "dict_index":2,"value":40,"ext_present":true,
    "extensions":[{"type":9,"hex":"ab12"}]}
 ]}
```
Per mode the pre-resolution payload token: raw -> `raw_value`+`wide`; delta -> `delta_raw`+`delta_raw_len`;
dict -> `dict_index`. `field` = normalised name (null for reset / unknown canonical id). `extensions`
hex is lowercase. These tokens are what make `encode(decode(x))==x` possible.

### 3.2 format_report.json (report on the VISIBLE catalog)
keys: `format_tag`,`magic_hex`,`version`,`header_size`,`trailer_size`,`crc_coverage`,`sync_byte_hex`,
`esc_byte_hex`,`selector_layout` (dict of bit meanings),`mode_ids`,`catalog_count`,`catalog_ok_count`,
`catalog_mode_counts` ({raw,delta,dict,reset}),`catalog_field_count` (distinct canonical fields seen),
`stream_count` (distinct stream_ids in catalog). Values computed from the shipped catalog + layouts.

### 3.3 roundtrip_report.json
`{"all_roundtrips_equal":true,"examples":[{"name":..,"input_sha256":..,"rebuilt_sha256":..,
"byte_length":..,"roundtrip_equal":true}, ...]}` over the agent's own self-built examples only.

### 3.4 error_analysis.json
`precedence` = `["bad_magic","unsupported_version","reserved_not_zero","record_count_overflow",
"trailer_crc_mismatch"]`; `cases` = decoder output for the first example's bytes damaged each of five
documented ways plus `all_defects` (all at once -> highest precedence wins); `catalog_errors` = map from
error string to how many catalog captures produced it.

### 3.5 decoded_examples.jsonl
>=4 lines, keys `name`,`hex`,`decoded`; together the lines use all four modes and at least one opaque
extension and one long key; no `name` starts with a reserved corpus prefix.

================================================================================
## 4. Rejection paths (LV-VA-5, STANDARD F)

Offsets are 0-based from file start (stated). Precedence order, first match wins:
1. `{"error":"bad_magic"}` - bytes 0..4 != "VARC1".
2. `{"error":"unsupported_version","version":V}` - version byte != 2.
3. `{"error":"reserved_not_zero","offset":O}` - a reserved byte (offset 14 or 15) nonzero; O = first such offset.
4. `{"error":"record_count_overflow","record_count":N}` - rec_count frames cannot fit in the bytes present.
5. `{"error":"trailer_crc_mismatch","expected":E,"found":F}` - header CRC mismatch.

AL-27: hidden fixtures construct every ADJACENT precedence pair with both faults present and assert the
earlier wins, plus an `all_defects` case. Reflex bugs: wrong order (e.g. CRC before version), or crashing
instead of returning an error object.

================================================================================
## 5. Levers: rule text, location, reflex, hidden cases, why visible cannot confirm, independence

Every rule lives in `format_contract.md` (+ `revision_map.ini`, `field_layouts.csv`, `escape_rules.md`,
`revision_notes.md`). The instruction says the contract has N rules to apply and points at these files.

### Harden lessons applied (district-heat + emberforge, 21 Oct)
- Hidden-only is necessary but NOT sufficient. district-heat: every lever was hidden-only yet a solver
  right on each documented rule in its own one-rule case scored 1.0. So each lever below names the
  NATURAL CODE STRUCTURE that produces the reflex (emberforge's only surviving lever was a composition
  the agent's own if/elif-early-return structure missed), and EVERY hidden separating case combines the
  lever with at least one other rule whose text lives in a DIFFERENT spec file (so no single-file read
  settles it). Rules stay stated plainly (IN-15, DS-21, DS-25); nothing is hidden.
- Spec-file map (for the cross-file pairing requirement): byte layout + modes + rejection precedence ->
  `format_contract.md`; escaping + resync -> `escape_rules.md`; revision remap table -> `revision_map.ini`;
  canonical field id/name/type -> `field_layouts.csv`; per-stream field labels/scope -> `symbol_table.tsv`;
  extension types (which are opaque) -> `schema_registry.json`; CRC algo/coverage/byte-order ->
  `crc_profiles.json`; report shapes -> `decoder_appendix.md`.

### LV-VA-1 stream-local state across files  (STANDARD, independent)
- Rule: dictionary + cumulator + seq belong to a stream; continue across segments in `--stream` order;
  cleared only by a reset frame.
- Reflex: reset state at each file (per-file decode), so a dict/delta ref to a value from an earlier
  segment of the same stream resolves wrong or errors.
- Natural reflex code structure: one decoder object (fresh resolved-list + cumulator=0) constructed per
  file inside the `--stream` loop, instead of one decoder threaded through all segments.
- Hidden cases (verifier --stream manifests), each crosses a spec-file boundary: seg B dict ref to a
  value defined only in seg A, where that field's canonical name needs `field_layouts.csv`+`revision_map.ini`
  (layout spec, not format_contract); a delta in seg B continuing seg A's cumulator where the resolved
  `value` also drives a `symbol_table.tsv` scope label; a reset in seg A clears before seg B. 3+ cases.
- Why visible cannot confirm: the shipped multi-file example (capture_alpha.varc + capture_beta.varc) and
  every catalog capture keep all dict/delta refs WITHIN one segment, so per-file and per-stream agree.
- Independence: graded only through `--stream`; single-file decode unaffected.

### LV-VA-2 opaque extensions kept in position on modified records  (STANDARD E)
- Rule: unknown-type extension TLVs are kept as raw bytes in their original slot. When a known field is
  modified, the encoder re-emits the frame with extensions in their original positions, recomputes fchk,
  body_len and trailer CRC, and keeps preserved reps of untouched fields.
- Reflex: drop/reorder unknown extensions, or regenerate them, on re-encode of a modified record; or
  only handle extensions on the untouched round-trip.
- Natural reflex code structure: encoder rebuilt from the decoded value dict alone (serialise value by
  mode, append nothing), so extensions that were not folded back into the dict vanish; or extensions
  re-sorted by type. Which types are opaque is stated in `schema_registry.json`, a different file from
  the encode rules in `format_contract.md`.
- Hidden cases (verifier modified docs fed to encode.py): take a correct decode doc, change ONE field's
  `value` and drop that field's preserved token, keep every other field + all extensions; assert bytes
  equal the verifier's canonical modified bytes. Pairs LV-VA-2 with LV-VA-4 (an untouched overlong delta
  elsewhere must stay overlong) so one case needs rules from format_contract + schema_registry together.
- Why visible cannot confirm: no visible capture is ever modified; the agent only round-trips originals,
  where extensions are reproduced by a plain copy whether or not the modify path is correct.
- Independence: graded via encode.py on supplied docs; decode correctness not required.

### LV-VA-3 framing-aware escaping  (STANDARD, independent)
- Rule: unescape only within the body_len window; a boundary ESC-like byte must not merge frames.
- Reflex: unescape by scanning to the next SYNC, or run unescape past body_len.
- Natural reflex code structure: unescape the whole buffer first, then split on SYNC (so a boundary
  escaped byte or an escaped SYNC inside a body swallows the next frame). body_len + escaping live in
  `escape_rules.md`; the extension TLV layout the escaped bytes resolve to lives in `format_contract.md`.
- Hidden cases: a frame whose last body byte is an escaped 0xAA/0x1B immediately before the next frame's
  SYNC (pairs LV-VA-3 with the frame-layout rule, different file); a frame whose OPAQUE extension payload
  (schema_registry defines it opaque) contains escaped SYNCs. Assert resolved value + extension hex +
  byte re-encode as SEPARATE observables.
- Why visible cannot confirm: visible bodies never place an escapable byte at the body boundary and never
  put SYNC/ESC bytes inside extension payloads, so bounded and greedy unescape give identical output.
- Independence: pure decode-side; graded on single-file hidden captures.

### LV-VA-4 representation memory (non-shortest varints)  (STANDARD E)
- Rule: a delta captured in a longer-than-shortest LEB128 must be reproduced in that byte length when
  re-encoding the UNMODIFIED frame; shortest form for new records and for a modified delta field.
- Reflex: always re-encode shortest, so overlong captures do not round-trip.
- Natural reflex code structure: encoder calls `write_sleb128(value)` which by construction emits the
  shortest form, discarding the captured length; the decoder never stores `delta_raw_len`. The varint
  rule is in `format_contract.md`; the case pairs it with a revision remap (`revision_map.ini`) so the
  frame's field name also depends on a second file.
- Hidden cases: unmodified docs whose `delta_raw_len` exceeds the shortest length (assert byte-exact and,
  separately, assert the reported `delta_raw_len`); modified docs where the changed delta must become
  shortest (assert byte-exact). Each observable (bytes vs reported length) is its own check.
- Why visible cannot confirm: every visible capture uses shortest LEB128, so preserved length == shortest
  length and a decoder that drops `delta_raw_len` still round-trips the visible set.
- Independence: graded via encode.py byte-exactness + the reported length on supplied docs.

### LV-VA-5 validation precedence and offsets  (STANDARD F) -> section 4.
- Natural reflex code structure: validation written as a straight if/elif chain in the spec's listed
  order (which IS correct for single-defect files), so a careful agent gets single-defect cases right.
- The ordered list lives in one file (`format_contract.md`), so a careful agent implements it directly.
  Therefore weight the pure-precedence checks LIGHT (3s, section 7). The HEAVY cases are where precedence
  meets LV-VA-6 (section 4 + LV-VA-6): a file with a header defect AND damaged frames, where the contract
  says the header rejection wins for `decode.py <file>` but `--salvage` still recovers the clean frames
  and reports the header defect as the stop reason. That pairing spans format_contract + escape_rules.
- Independent as a decode rejection path for the single-defect 3s; the heavy pairing is shared with LV-VA-6.

### LV-VA-6 resynchronisation after damage  (STANDARD, independent)
- Rule: on a frame that fails to parse or whose fchk is wrong, emit one damage record and resume at the
  next SYNC; each damaged span reported once; inside frames neither skipped silently nor decoded.
- Reflex: abort the whole file on first bad frame; or silently skip bytes without a damage record; or
  resync to the wrong offset (not a SYNC).
- Natural reflex code structure: the decode loop does `for _ in range(rec_count): frame = parse(cur)`
  with the first parse failure raising out of the loop (abort), or a `while cur.find(0xAA)` that resyncs
  to the first 0xAA byte without re-validating it is a real frame boundary. Resync + fchk live in
  `escape_rules.md`; the frame structure a candidate must satisfy lives in `format_contract.md`.
- Hidden cases (--salvage on verifier-built segments): one corrupted frame mid-segment then clean frames;
  two separate damaged spans; damage whose bytes contain a 0xAA that is NOT a frame boundary (must not
  false-resync there); and the LV-VA-5 pairing (header defect + in-band damage). Assert the damaged list
  offsets/reasons and the recovered clean records as SEPARATE observables.
- Why visible cannot confirm: all visible captures are clean (transport_errors.log annotates only a few
  WHOLE-file rejections, never in-band frame damage), so the salvage path is never exercised visibly.
- Independence: separate `--salvage` entry point.

### STANDARD A composition (hidden frames combine rules; graded on SEPARATE observables, CL-4)
Compositions are NOT graded all-or-nothing. Each hidden composition frame is graded by several checks,
each tied to ONE lever and reading ONE observable: the decoded `value` (LV-VA-1 cross-file dict), the
extension hex (LV-VA-2/3), the reported varint length (LV-VA-4), the normalised `field` (remap), the
byte-exact re-encode, the damage record (LV-VA-6). Each composition check pairs AT MOST 2 levers. There
is AT MOST ONE all-levers check (one frame carrying escaped-SYNC extension + cross-file dict + non-identity
revision + overlong delta), weighted 3, that asserts the whole-frame byte-exact re-encode; the per-lever
observables above carry the real weight so one gap costs about one fact, not the whole frame.

### STANDARD B chain (section 2 entry points) - stages graded on supplied correct intermediates.

================================================================================
## 6. Input files (environment/data/, flat; >=10 files, >=5 formats; chains)

Record files (A5: csv/tsv/jsonl/txt/log, each >=2000 lines, load-bearing):
1. `capture_catalog.jsonl` (~8000) - visible captures: {capture_id, stream_id, seq_no, hex}. All clean,
   single-segment-resolvable, canonical varints, identity-safe revisions, no boundary escapes. Feeds
   format_report tallies + roundtrip self-check. The reflex-confirming trap surface.
2. `frame_index.jsonl` (~5000) - per frame of the catalog: {capture_id, ordinal, offset, body_len, mode,
   raw_key}. Feeds format_report frame/mode counts; cross-checks the catalog.
3. `field_layouts.csv` (~2500) - canonical field id,name,type,width. Feeds remap/normalisation + report.
4. `symbol_table.tsv` (~2500) - per stream: stream_id, canonical_field_id, label/scope. Feeds field names.
5. `transport_errors.log` (~2500) - damage annotations for the few rejectable catalog captures:
   capture_id, error_string, offset. Feeds error_analysis catalog_errors tally.

Spec / small files (md exempt from A5; json/ini count to total not per-file):
6. `format_contract.md` - normative: byte layout, modes, state, escaping, revision remap, trailer/CRC,
   rejection catalogue + precedence + offset convention, entry points, every output key + error string.
7. `escape_rules.md` - the escaping + resync (salvage) rules in full.
8. `revision_notes.md` - revision remap narrative + the identity vs non-identity revisions.
9. `decoder_appendix.md` - the four /app/out report shapes, key by key.
10. `revision_map.ini` - (revision, raw_key) -> canonical_field_id table.
11. `schema_registry.json` - defined extension types (so the agent knows which are opaque) + canonical
    field catalogue mirror.
12. `crc_profiles.json` - CRC algorithm (crc32), coverage ("header", offsets 5..15 = 11 bytes), byte order (LE).
Binary visible example: `capture_alpha.varc`, `capture_beta.varc` - one multi-segment stream with NO
cross-file refs (so per-file == per-stream). Do not count toward A5.

### Data volume rule (harden change 6)
No padding rows. Each record file is read by a graded stage, and every row must be able to change a
graded output when edited: the catalog/frame_index rows drive the format_report tallies and the roundtrip
self-check; field_layouts + symbol_table rows drive the normalised `field` names and catalog_field_count;
transport_errors rows drive error_analysis catalog_errors. A5 sizes are met by shipping MORE real
captures/frames (more streams, more frames per capture), never filler lines. The format_report tallies
are computed over the whole catalog, so adding or editing any row moves a graded number.

### Chains (>=3 of length >=4)
- C1 remap: capture hex (capture_catalog) -> revision (header) -> revision_map.ini -> field_layouts.csv ->
  normalised `field` in decode doc + format_report catalog_field_count. (5)
- C2 dict value: frame dict_index (frame_index/body) -> stream resolved list (prior frames) ->
  symbol_table scope -> resolved `value` -> roundtrip_report byte match. (5)
- C3 rejection: capture hex -> magic/version/reserved/rec_count/trailer (format_contract precedence) ->
  crc_profiles.json coverage -> transport_errors.log annotation -> error_analysis catalog_errors. (5)
- C4 escaping: body_len (frame) -> escape_rules.md -> unescape window -> value-bytes + extensions ->
  decode `value`/`extensions` -> encode byte-exact. (5)

================================================================================
## 7. Test plan (tests/test_output.py; 40-70 checks; weights 5 core / 3 sub / 1 existence)

Hidden corpora built verifier-side from `EVAL_SEED` (lives only in tests/). `SAMPLE_SEED`/`CHALLENGE_SEED`
regenerate the visible catalog deterministically (datagen mirrors them) for the report-tally checks.
Agent programs run from a foreign cwd (/tmp) as an unprivileged user, output+rc consumed, process group
killed (TS-24). Every check guards reads and returns bool (TS-29). Separating cases CONSTRUCTED, never
sampled. For each lever a wrong-impl is confirmed to lose that lever's weight (Phase 4).

Positive groups (lever -> checks, indicative weights; LEVERS.md will be the source of truth):
- Existence (1 each): decode.py present, encode.py present, decoded_examples.jsonl shape, each of the 3
  report jsons present/parse. (~6 x 1). Weight 1 is used ONLY for these true existence/shape checks.
- Basic decode on clean HIDDEN captures (not visible): raw/delta/dict/reset single-file decode (3 each).
  These read the hidden eval corpus, so they are not re-graded visible value checks. Per harden change 5
  (TS-20), NO core-deliverable value check is weighted 1, and any visible-only value check that a hidden
  case already grades is DROPPED rather than kept at weight 1.
- LV-VA-1 (5,5,3): cross-file dict ref value; cross-file delta cumulator value; reset-clears-across-files,
  via --stream. Each reads the decoded `value`, a distinct observable per check.
- LV-VA-2 (5,5,3): modified-record byte-exact with extensions in place (bytes); untouched preserved reps
  kept (bytes of a second untouched field); extension order/position preserved (extension hex list).
- LV-VA-3 (5,5,3): boundary-escape decode value; escaped SYNC inside extension -> extension hex; byte-exact
  re-encode of the escaped frame.
- LV-VA-4 (5,3): overlong-delta unmodified byte-exact (bytes) + reported `delta_raw_len` (separate check);
  modified-delta-becomes-shortest byte-exact.
- LV-VA-5 (3,3,3,3): each adjacent precedence pair + exact error object (offset/version/expected/found).
  Pure precedence is LIGHT (all 3s), since the ordered list is in one file (harden change 4).
- LV-VA-6 (5,5,3,3): single in-band damage span recovered records; its damage record (from_offset/
  resync_offset/reason) as a separate check; two spans; no false-resync on a non-boundary 0xAA.
- LV-VA-5 x LV-VA-6 heavy pairing (5,5): a file with a header defect AND in-band damaged frames ->
  `decode.py <file>` returns the header error (one check), `--salvage` recovers the clean frames and
  reports the header defect as the stop reason (second check). This is where precedence carries weight.
- STANDARD A per-observable (change 2): three composition frames, each graded by per-lever observables
  pairing at most 2 levers: value (LV-VA-1 x remap), extension hex (LV-VA-2 x LV-VA-3), varint length
  (LV-VA-4 x remap). Weights 5/5/3 each frame on its observables. Plus ONE all-levers whole-frame
  byte-exact check, weight 3 only.
- Reports (3 each): format_report equals verifier-computed; error_analysis equals; roundtrip_report shape
  + internal consistency (agent's own examples, recomputed by the verifier's encoder).
Target positive total ~ 150-180 over ~48-58 positive checks, with >=0.8 of weight on hidden
(composition + new-lever + modified/overlong + resync + cross-file) checks.

Negatives (sum|neg| <= sum pos; one action -> one penalty, AL-28):
- `negative_hardcoded_sample_answers` (-5): passes catalog, 0 on hidden eval.
- `negative_filename_dependent_behaviour` (-5): rename -> same bytes required.
- `negative_reads_training_corpus_at_runtime` (-5): /app/data literal in decode/encode source.
- `negative_rebinds_verifier_dependencies` (-5): rebinds open/zlib.crc32/struct.unpack.
- `negative_nondeterministic_output` (-3): two runs differ.

No positive passes on an absence (TS-25). No two checks read the same observable (TS-26). Downstream
isolation: --stream, --salvage, encode checks fed verifier-built correct inputs.

### Wrong-implementation confirmations (Phase 4; harden change 3)
One wrong-impl per lever, each confirmed to lose exactly that lever's weight. Two must be SELF-CONSISTENT
(decode(encode(x))==x for every record the wrong encoder itself produces), because the agent self-tests
that way and such a bug passes the visible round-trip:
- W-VA2: encoder rebuilds bytes from the decoded value dict only (drops/moves opaque extensions). Its own
  decode(encode(x)) round-trips (it never emits extensions), but hidden modified-record byte checks fail.
- W-VA4: encoder always emits shortest LEB128 (canonicalises an unmodified overlong varint). Self-
  consistent, but the overlong-unmodified byte + `delta_raw_len` checks fail.
Also: W-VA1 per-file decoder (cross-file checks fail), W-VA3 whole-buffer-unescape-then-split (boundary
checks fail), W-VA5 CRC-before-version order (precedence-pair checks fail), W-VA6 abort-on-first-bad-frame
(salvage checks fail). Each recorded in WORK/wrong/README.md with its one-line edit and the points lost.

================================================================================
## 8. Judge plan (tests/judge.toml; 12-30 criteria; concrete facts, no overlap with tests JD-8)

Harden change 7: every criterion is a CONCRETE FACT the instruction asks the agent to state in its final
reply, in plain words, with no mention of a reviewer/grader/judge/test. Each names a value or a direction
so a run that misread the rule fails it, and every correct run states it (JD-7, JD-15). No criterion reads
a value a test reads (JD-8). No effort criteria. The instruction will ask the agent to end its reply with
a short account of the format it recovered covering exactly these facts. Criteria (positive grammar,
counts, start "The agent"/"The response"):
- The response states that the trailer CRC covers header offsets 5 to 15 only and uses crc32 little-endian.
- The response states that the resync marker byte is 0xAA and that unescaping is bounded by body_len.
- The response states that dictionary and cumulator state continues across the segment files of one stream
  and is cleared only by a reset frame.
- The response states that an opaque extension keeps its original byte position when a record is modified.
- The response states the rejection precedence as bad_magic, then unsupported_version, then
  reserved_not_zero, then record_count_overflow, then trailer_crc_mismatch.
- The response states the number of catalog captures that were rejected and the error string for each.
- The response states that a delta captured in a non-shortest LEB128 is re-emitted at its original byte
  length for an unmodified frame and in shortest form for a modified or new record.
- The response states that a short integer key is remapped to a canonical field through the segment
  revision before it is named.
- The response states the count of distinct record modes it implemented (four: raw, delta, dict, reset).
- (code quality, JD-18) The agent writes decode.py and encode.py with named helper functions, no bare
  except, and returns the documented error objects rather than swallowing errors.
Negatives on THIS task's cheats (hardcoding catalog answers; reading tests/). ~14-16 criteria.
These read the agent's REPLY/trajectory; the tests read artifacts, so no observable is shared (JD-8/F0d).
reward.toml: weights = {test_output = repr(0.5/Ptests), judge = repr(0.5/Pjudge)}.

================================================================================
## 9. Expected baselines (to confirm in P3, not asserted now)
- S0 nop 0.0 ; S5 oracle 1.0.
- S1 stub (empty artifacts): only existence (~6/pos total) minus negatives -> <=~0.04.
- S2 reflex-everywhere: existence + maybe basic single-file decode; fails all composition/new-lever/
  modified/overlong/resync/cross-file -> target <=0.10.
- S4 careful (every rule right in isolation + on visible, reflex where rules combine and on each new
  lever's reflex) -> target 0.10-0.20.
- S4b (harden change 8): right on every rule in isolation AND on each SINGLE-LEVER hidden case, wrong only
  where two rules meet (the composition observables). P3 must score S4b; if it is near 1.0 the
  compositions are too weak and the build rebuilds with more two-lever observables. S4b is the real test
  of whether the levers depend on composition rather than on any single hidden case.
- Every counted lever HIDDEN-ONLY (right vs reflex identical on the shipped catalog + alpha/beta).

================================================================================
## 10. Open items / risks
- Q18 provenance: keep scaffold's `authored_by`/`status` (VB 15.5 needs them, QC DS-27 fails them). Will
  write OPEN CONFLICT Q18 and not invent a third option.
- Oracle must reach exactly 1.0: the verifier's encoder (ground truth) and solve.py are independent
  implementations of one spec; keep shared lines < 20% (TS-S13) by not importing either into the other.
- Resync false-positive on a non-boundary 0xAA: the SYNC scan must re-validate that the candidate frame
  parses (selector/body_len sane + fchk ok) before accepting it as the resume point; documented.
- A5 total: 5 record files sized to ~20500 lines total; md excluded, binary excluded. Will verify.
- C6 WARN: instruction must avoid grader/checker/verifier wording.

## Round 1 changes (22 Oct 2026)

- Verifier runner: agent programs copied into a verifier-made 0755 folder as 0644 copies and run
  with `python3 -I` under setpriv as nobody; inputs 0644 in 0755 folders; encode output folder
  1777; leftovers killed by process group and by uid; 20 s per run, 2100 s run budget.
- Value rule: raw and delta set the cumulator, reset zeroes it, nothing else moves it (tests,
  solve.py and format_contract.md agree).
- New rules: RUN (stream_continues named in the contract header table, its effect defined in the
  appendix `--stream` section), MAP-OMIT (revision_map.ini lists only moved key bytes), unknown
  long key keeps its text as field name. Decoy: loader_notes.md says a revision 0 continuation
  inherits the previous revision; the contract says each segment uses its own revision byte.
  Shipped stream 3: capture_alpha (rev 5, continues), capture_beta (rev 0, ends run),
  capture_gamma (new run, starts with deltas).
- Grading: 14 composed checks (70%) on hidden streams from EVAL_SEED; 6 isolated (18%); reports 12%.
  Encode fixtures are decoded real segments with one edit and re-decoded values.
- Error analysis reduced to the six cases; precedence and catalog_errors keys dropped.
- Judge: four computed figures (absent from every shipped file), structure of each program,
  an unbacked-validation negative and a grader-path negative; mode batched.
- Validator 7.2 requires SAMPLE_SEED, CHALLENGE_SEED, EVAL_SEED, `_write_corpus` and a main block,
  so they stay (recheck row 26 asked to delete them) and now drive the visible data and the
  hidden fixtures.
- Negatives: validator 11.2, 11.3, 11.5 FAIL (strict default) without the filename, runtime-corpus and
  rebinding negatives, so they stay against recheck rows 11, 12, 15, rebuilt as behavioural checks distinct
  from the determinism check (same path vs different names; planted poisoned tables; shadow modules).

## Harden lp1 r1 (23 Oct 2026, board 52dbb3c, LEVER_PLAN_v1)

- Cause (OUT/DIAGNOSIS.md): the a2 run scored 100/100/100 genuinely. Every r1 rule was one plain sentence beside its use (two of them explained the trap), the shipped stream 3 separated the run rule, and the judge figures came from shipped files. The agent wrote its program once at step 12.
- Levers are L2 + L3 + L5 + L6 (no L1/L4; cohort uses L1+L2+L3+L4/L5). The details, with file:line, are in LEVERS.md "Harden lp1 r1".
  - L2: count unit read unsigned, behind the catalog `value_sum` control. The all-unsigned repair also satisfies the shipped control.
  - L6: Terms defines the cumulator per field name.
  - L3: the Runs ledger with resends.
  - L5: a JSON boolean `stream_continues` in the manifest beside "every text value is trimmed", and a JSON integer `delta_raw_len` beside "hex read case-insensitively after trimming".
- Writing:
  - W1: two trap explanations removed from escape_rules.md (the "must not swallow that sync byte" sentence and "a 0xAA inside damaged bytes is not a resume point").
  - The instruction no longer asks for figures or lists traps, and it states "Each output document is graded whole on fresh inputs" (G5).
  - Each rule sits in the file that governs its data: the field table rule under Field names, the cumulator under Terms, manifest rules in the appendix Manifest/Runs, encoder rules in "What the encoder reads".
- Data: the catalog is regenerated from tests/test_output.py.
  - It gains `value_sum`.
  - Count raws may have the top bit set, and non-count raws are non-negative.
  - A delta comes only first or after a same-key setter.
  - Stream 3 is rebuilt to the same pattern.
  - `stream3_manifest.json` is added.
  - The tables are byte-identical.
- Grading:
  - 13 whole documents on hidden inputs (w5), 8 isolated rule checks and 2 mutation checks (w3), 4 reports (w3); positive total 107; negatives for cheating only, -19.
  - Failure reasons are printed to the verifier stdout (test-stdout.txt). ctrf cannot hold them: rewardkit 0.2.1 has no message field, harness normalize_ctrf.py strips `message`, and tests_qc B4 forbids writing under /logs/verifier from tests.
- Judge: 8 criteria, batched.
  - Four w3 conduct criteria, one per lever (self-built case + check).
  - A w3 named-shape code-quality criterion (no bare except / except Exception).
  - A w1 catalog round trip check.
  - An honesty negative (-3) and a grader-path negative (-5).
  - reward.toml judge 0.5/16, tests 0.5/107.
- The a2 reflex program scores 0.1682 tests-only locally.
