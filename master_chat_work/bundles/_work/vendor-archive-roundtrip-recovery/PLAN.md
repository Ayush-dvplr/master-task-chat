# PLAN - vendor-archive-roundtrip-recovery

## Rebuild round 1 (22 Oct)

Prompt: master_chat_tasks/prompts/issued/vendor-archive-roundtrip-recovery/P4_rebuild_r1.md. Round notes 20261022 (incl. 16:00 update: QC HEAD f3765e67, judge mode "batched") bind.

### One line per fix
- F1 permissions (notes C, recheck 1, 27): `_run_agent` copies decode.py/encode.py into a fresh 0755 mkdtemp as 0644 copies and runs the copy; every temp input 0644 in 0755 folders; encode output folder 0o1777; leftovers killed by process group and by uid (scan /proc).
- F2a raw frames set the cumulator (contract, verifier parse_frame, solve.py all agree).
- F2b encode fixtures = reference decode of a real hidden segment, then one field edited and re-decoded; edited delta gets delta_raw_len null as the appendix says; appendix states which keys the encoder reads and which keys a new record carries.
- F3 recheck REAL rows: report_roundtrip runs agent encode.py on every example; startswith(("cap","rej","eval","sample","field")); drop negative_filename_dependent_behaviour, negative_reads_training_corpus_at_runtime, negative_rebinds_verifier_dependencies (validator 11.2/11.3/11.5 WARN only); fixtures for offset 15 alone, rec_count*5 bound, full crc object, reset clearing state; unknown long key rule in format_contract.md; TRUTH counts and seed wording; _run timeout 20 s against verifier 2700 s; strict typed compare; split multi-property checks; judge R10 split per program; R12 dropped; escape_rules window-end sentence; instruction wording; JD-13 left as is.
- F3 conflict: recheck row 26 (delete seeds, _write_corpus, __main__) conflicts with validator 7.2 (FAIL without them). Keep them and make them real: SAMPLE_SEED drives the visible catalog, EVAL_SEED and CHALLENGE_SEED drive the hidden composed corpus, `_write_corpus` writes that corpus for audit, `__main__` calls it.
- F4a instruction: no rule count, no trap list; final reply asks for four computed figures; names only format_contract.md as authority.
- F4b composition: hidden multi-segment manifests regenerated from EVAL_SEED/CHALLENGE_SEED, graded as whole documents; rule-isolating checks <= 30% of positive weight; shipped-data-only checks <= 5%.
- F4c no confirming shipped answers: no expected decodes anywhere; shipped captures only show that each boundary occurs.
- F4d split/omission rule RUN: flags bit 0 named in format_contract.md, its effect on state defined only in decoder_appendix.md (--stream): state carries from the previous segment of the same stream only when that segment set stream_continues; every other segment starts fresh. Also DICT-CUM by omission ("raw and delta set the cumulator; every other frame leaves it, reset zeroes it") and MAP-OMIT ("every other key byte under that revision is its own canonical id").
- F4e decoy REV0: new environment/data/loader_notes.md (historical, mostly true) says a revision 0 continuation segment inherits the revision it continues; format_contract.md (authority) says each segment resolves short keys under its own revision byte and 0 to 3 are identity everywhere. Shipped capture_alpha (rev 5, continues) then capture_beta (rev 0 continuation) shows the boundary.
- F4f judge: R1 to R12 replaced by four figure criteria (one figure each, full chain, in no file), decode.py and encode.py quality (one each), honesty negative, /tests-or-/logs negative; mode "batched".
- F5 tests/Dockerfile pip line gains litellm==1.105.0; test.sh unchanged (already chown + chmod 755).

### What wrong reading each new check fails
- stream_interleaved: one state per manifest, or fresh state per file (cross-file delta/dict refs in two interleaved streams).
- stream_new_run: always carrying state per stream id (new run starts with delta frames).
- stream_revision_change: caching the first header's revision; the REV0 decoy (rev 0 continuation after rev 5).
- stream_remap_alias: alias looked up on the raw key; unlisted key bytes treated as unknown; unknown long key not kept as text.
- stream_eval_mix / stream_challenge_mix: any of the above plus dict moving the cumulator, raw not setting it.
- single_remapped_modes: the four modes under revisions 4 to 7 with DICT-CUM and raw cumulator.
- single_escapes_ext: whole-region unescape, escaped bytes in ext payloads, extensions reordered by type.
- salvage_state: state reset or advanced by frames in a damaged span.
- salvage_mix: false resync inside a damaged frame, damage reaching the trailer.
- encode_unmodified: dropping overlong delta memory, reordering two opaque extensions, re-escaping wrongly.
- encode_edited: edited delta kept padded (null not honoured) or other records losing memory.
- encode_new_record: record_count/CRC not recomputed, new delta not shortest, missing keys crash.
- chain_decode_encode: agent decode output not accepted by agent encoder for the original bytes.
- isolated rejection set: wrong precedence pair, offset 15 missed, count bound off by one, crc fields swapped.
