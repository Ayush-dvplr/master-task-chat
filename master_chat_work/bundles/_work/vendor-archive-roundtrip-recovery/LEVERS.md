# LEVERS.md - vendor-archive-roundtrip-recovery

One row per test_output.py check, its lever, weight, and the single observable it
reads. Positive total 145, negative total -23 (sum|neg| <= sum pos). 48 checks.

| Check | Lever | Weight | Observable |
|---|---|---|---|
| decoder_exists | existence | 1 | decode.py file present |
| encoder_exists | existence | 1 | encode.py file present |
| format_report_present | existence | 1 | format_report.json parses |
| roundtrip_report_present | existence | 1 | roundtrip_report.json parses |
| error_analysis_present | existence | 1 | error_analysis.json parses |
| decoded_examples_present | existence | 1 | decoded_examples.jsonl >=4 lines |
| basic_raw_wide | basic-decode | 3 | wide raw value doc |
| basic_raw_narrow | basic-decode | 3 | narrow raw value doc |
| basic_delta | basic-decode | 3 | delta value doc |
| basic_dict | basic-decode | 3 | dict value doc |
| basic_reset | basic-decode | 3 | reset doc |
| basic_longkey | basic-decode | 3 | long-key field doc |
| va1_cross_dict | LV-VA-1 | 5 | seg B dict value from seg A |
| va1_cross_delta | LV-VA-1 | 5 | seg B delta cumulator from seg A |
| va1_three_seg | LV-VA-1 | 3 | seg C dict value from seg A |
| va2_modified_bytes | LV-VA-2 | 5 | modified-record encoded bytes |
| va2_extensions_kept | LV-VA-2 | 5 | extensions after modify re-encode |
| va2_untouched_preserved | LV-VA-2 x LV-VA-4 | 3 | untouched overlong field bytes |
| va3_boundary_value | LV-VA-3 | 5 | decoded values (boundary escape) |
| va3_ext_escaped | LV-VA-3 | 5 | extension hex (escaped sync) |
| va3_reencode | LV-VA-3 | 3 | re-encoded escaped-frame bytes |
| va4_overlong_bytes | LV-VA-4 | 5 | unmodified overlong encoded bytes |
| va4_len_reported | LV-VA-4 | 3 | decoded delta_raw_len |
| va4_modified_shortest | LV-VA-4 | 5 | modified-delta encoded bytes |
| va5_magic_over_version | LV-VA-5 | 3 | error object (magic vs version) |
| va5_version_over_reserved | LV-VA-5 | 3 | error object (version vs reserved) |
| va5_reserved_over_overflow | LV-VA-5 | 3 | error object (reserved vs overflow) |
| va5_overflow_over_crc | LV-VA-5 | 3 | error object (overflow vs crc) |
| va5_version_field | LV-VA-5 | 3 | unsupported_version version field |
| heavy_decode_rejects | LV-VA-5 x LV-VA-6 | 5 | decode error on header defect + damage |
| heavy_salvage_recovers | LV-VA-5 x LV-VA-6 | 5 | salvage records + header_defect |
| va6_single_records | LV-VA-6 | 5 | salvage recovered records |
| va6_single_damage | LV-VA-6 | 3 | salvage damaged offsets |
| va6_two_spans | LV-VA-6 | 5 | salvage two spans + records |
| va6_no_false_resync | LV-VA-6 | 3 | salvage resync offset (stray sync) |
| compA_value | LV-VA-1 x remap | 5 | cross-seg dict value + field |
| compA_len | LV-VA-4 x remap | 3 | overlong len + remapped field |
| compA_ext | LV-VA-2 x LV-VA-3 | 5 | modified escaped-ext bytes |
| compA_all | composition (all) | 3 | whole-frame byte-exact re-encode |
| report_format | reports | 3 | format_report.json equals expected |
| report_error_analysis | reports | 3 | error_analysis precedence/counts |
| report_roundtrip | reports | 3 | roundtrip_report equality |
| report_decoded_examples | reports | 3 | decoded_examples self-consistency |
| negative_hardcoded_sample_answers | anti-cheat | -5 | visible-only reproduction |
| negative_filename_dependent_behaviour | anti-cheat | -5 | filename-keyed divergence |
| negative_reads_training_corpus_at_runtime | anti-cheat | -5 | /app/data literal in source |
| negative_rebinds_verifier_dependencies | anti-cheat | -5 | rebinding open/zlib/struct |
| negative_nondeterministic_output | anti-cheat | -3 | cross-run divergence |

## Weight totals per lever (positive)
| Lever | Checks | Weight |
|---|---|---|
| existence | 6 | 6 |
| basic-decode | 6 | 18 |
| LV-VA-1 | 3 (+compA_value) | 13 (+5) |
| LV-VA-2 | 3 (+compA_ext) | 13 (+5) |
| LV-VA-3 | 3 (+compA_ext shared) | 13 |
| LV-VA-4 | 3 (+compA_len, +va2_untouched shared) | 13 (+3) |
| LV-VA-5 | 5 (+heavy 2) | 15 (+10) |
| LV-VA-6 | 4 (+heavy shared) | 16 |
| composition compA_all | 1 | 3 |
| reports | 4 | 12 |
| Positive total | 42 | 145 |
| Negatives | 6 | -23 |

Hidden-weight share (LV-VA-1..6 + composition + heavy + reports, excludes
existence+basic): (13+13+13+13+15+16+10+5+5+3+3+12)/145 = 121/145 = 0.83.
Each counted lever is HIDDEN-ONLY (visible catalog + alpha/beta do not separate
right from reflex) and loses points under its wrong reading (see wrong/README.md).

## Round 1 (22 Oct 2026): current check bank (supersedes the v0 list above)

24 positive checks (total 100) and 2 negatives. Composed = whole documents from hidden
multi-segment streams or hidden segments where several rules meet; isolated = one rule.

| Lever | Checks (weight) | Positive weight | Share |
|---|---|---|---|
| RUN: state per stream run (`stream_continues` of the previous segment, split contract/appendix) | stream_interleaved 5, stream_new_run 5, stream_eval_mix 5, stream_challenge_mix 5 | 20 | 20% |
| REV: revision per segment, REV0 decoy in loader_notes.md | stream_revision_change 5 | 5 | 5% |
| REMAP: remap before alias, unlisted bytes identity (MAP-OMIT) | stream_remap_alias 5, single_remapped_modes 5 | 10 | 10% |
| STATE: cumulator by mode (DICT-CUM omission), reset | stream_reset_mid_run 5, reset_clears_state 3 | 8 | 8% |
| ESC/EXT: bounded escaping, opaque extensions out of type order | single_escapes_ext 5 | 5 | 5% |
| SALV: salvage state across damage, resync | salvage_state 5, salvage_mix 5 | 10 | 10% |
| ENC: representation memory, delta_raw_len null, new records | encode_unmodified 5, encode_edited 5, encode_new_record 5 | 15 | 15% |
| REJ: rejection order and fields | reject_magic_over_version 3, reject_version_over_reserved 3, reject_reserved_offset15 3, reject_count_bound 3, reject_crc_fields 3 | 15 | 15% |
| Reports | report_decoded_examples 3, report_roundtrip 3, report_error_analysis 3, report_format 3 | 12 | 12% |

Composed 70% (14 checks x 5), isolated 18% (6 x 3), reports 12% of which shipped-data-only
(report_format) 3%. Negatives: negative_hardcoded_sample_answers -5, negative_nondeterministic_output -3 (same path x3), negative_filename_dependent_behaviour -3 (same bytes, three names), negative_reads_training_corpus_at_runtime -5 (planted poisoned /app/data, behavioural, replaces the v0 source grep), negative_rebinds_verifier_dependencies -3 (.pth or stdlib/grader-named module in the workspace, replaces the v0 AST grep). The last three stay because validate_bundle.py (strict default) FAILs without them, against recheck rows 11, 12, 15.
Value rules (raw sets cumulator, dict does not) run through every value-bearing composed check.

## P12 r1 (22 Oct 2026): QC v2 fixes
- REJ: reject_reserved_offset15 (3) now also requires the `both_reserved` fixture (bytes 14 and 15 non zero) to be rejected at offset 14 (AL-27 precedence pair). Weight unchanged; a decoder that checks 15 before 14 now loses these 3.
- Negatives: each carries an inline `# inverted:` comment (TS-15). Weights unchanged.
- Judge: R5/R6 structure criteria replaced by one code-quality criterion R5 r5_code_quality (weight 3, task completion, state_change) and a new R6 r6_method_lines (weight 1, instruction following, final_answer) grading the one line method note after each figure (AL-2; keeps 8 criteria for JD-12). R7 (-3) and R8 (-5) unchanged. Judge positive total 24; reward.toml judge = 0.5/24 = 0.020833333333333332. Score labels stay tests-only.

## P12 r2 (22 Oct 2026): QC v3 fixes
- negative_filename_dependent_behaviour (-3, weight unchanged) now runs each of its three names twice and stands down when a name's repeats differ, so a decoder that only varies run to run pays negative_nondeterministic_output alone (TS-26, AL-28). A filename-keyed decoder that is stable per name still pays -3.
- Oracle only: solve.py --build now writes role-specific /app/decode.py and /app/encode.py holding only the definitions each role uses (JD-7 vs judge R5). Decode, salvage, stream, encode and all four reports byte-identical to the previous oracle. No test, weight or data change from this.
- negative_rebinds_verifier_dependencies kept (-3), trigger replaced in P12 r3: besides the workspace scan it now runs decode.py and encode.py once and fires if the run writes a .pth or shadow-named module into the run folder, staged folder, temp dir or site-packages, so it can fire in separate mode (TS-16-1 fixed). P12 r3 also made every catalog capture_id cap-NNNNN in file order (DS-4-1): harder, no count is readable from names.

## Harden lp1 r1 (23 Oct 2026, board 52dbb3c): LEVER_PLAN_v1 levers L2 + L3 + L5 + L6 (supersedes the tables above)

Bank: 13 whole-document checks on hidden reseeded inputs (w5, 65 = 60.7%), 8 isolated rule checks and 2 mutation checks (w3, 30 = 28.0%), 4 report checks (w3, 12; report_format is the only shipped-only check, 3 = 2.8%). Positive total 107. Negatives: cheating only, -19, one act each. Line numbers refer to `environment/data/`.

### L2 make-it-match repair: count fields read unsigned, behind the catalog control
- Rule:
  - format_contract.md L152-155: "A raw record whose unit is `count` is read unsigned, in place of the signed reading under Value by mode".
  - Global default at L90: "raw: the value bytes are a signed little endian integer".
  - Control at L9-12: `value_sum` is "the sum of the resolved values of its records".
  - Encoder side, decoder_appendix.md L69-70: raw_value is written as its low 16/32 bits.
- Reflex: signed everywhere (the Value by mode bullet). On the shipped catalog this fails the control on 1157 of 15200 clean captures. The tempting repair is to read every raw value unsigned. It passes the control on all 15200, because every non-count raw in the shipped catalog is non-negative. A second reflex packs raw_value with signed=True, which crashes on unsigned values.
- Hidden cases:
  - every _Gen raw draws by unit: count fields mostly get the top bit set, all other fields are signed over the full range;
  - fx_rule_count_raw (10 raws, count and plain alternating, all with the top bit set);
  - fx_mutation_count (one raw moved from a plain key byte to a count key byte; the dict copy and the count delta after it move with it);
  - _single and fx_encode_new_record carry count raws above 32767.
- Wrong reading fails:
  - signed: every whole doc holding a count raw (all 6 stream docs, decode_doc_remapped/escapes, salvage docs), rule_count_raw_values, mutation_count_field;
  - all-unsigned: every whole doc with a negative plain raw, rule_count_raw_values;
  - signed packing in the encoder: encode_doc_unmodified/edited/new_records crash.

### L6 scope carried by a definition: one cumulator per field name
- Rule:
  - format_contract.md L188-190 (Terms): "cumulator: an integer the stream state keeps for each field name. The cumulator of a record is the one kept for the record's field name (its `field` ...). A field name whose cumulator has not been set reads zero."
  - Formula use at L92-93 "The resolved value is the cumulator plus the delta"; L86-88 points to Terms; L101-102 covers raw/delta setting and reset.
- Reflex: one running total per stream state (the a2 program's State.cumulator; the old contract wording). Variants:
  - keyed by raw_key, which goes wrong under remap and when a long and a short key name the same field;
  - dict frames moving the cumulator.
- Shipped data never separates it. In the catalog a delta opens its capture or follows a raw/delta of the same key; stream3 is built the same way. Probe: per-stream equals per-field on all 15200 clean captures and on stream3.
- Hidden cases:
  - _Gen key pool (fields recur, interleaved);
  - fx_stream_remap_runs (a short key under revision 4-7 and the long key of its target share one field name);
  - fx_rule_field_cumulator (3 plain fields taking turns);
  - fx_salvage_* (lost frames move no cumulator).
- Wrong reading fails: all 6 stream docs, decode_doc_remapped, decode_doc_escapes, salvage_doc_state, salvage_doc_mix, rule_field_cumulator.

### L3 stateful stream: the run ledger
- Rule: decoder_appendix.md L92-105 (Runs). Each stream has at most one current run (state + last seq_no). A segment whose seq_no is not larger than the run's last is a resend: "decoded from the run's stream state as it stands, and the run, its stream state and its last seq_no are left exactly as they were". L109: every printed doc reports its own header flags.
- Reflex: every listed segment updates its stream's state (the a2 program). Variants:
  - a resend starts a fresh run;
  - a resend moves last_seq.
- Hidden cases:
  - _manifest resends (copies of earlier taken segments of the open run, about 1 in 4-6 entries) in fx_stream_interleaved, new_runs, reset_runs, mix_a, mix_b;
  - fx_rule_resend (one field, two resends inside one run).
- Wrong reading fails: stream_doc_interleaved, new_runs, reset_runs, mix_a, mix_b, rule_resend_keeps_run.

### L5 strict type beside a normalising rule
- Rule (manifest site):
  - decoder_appendix.md L106-108: "When its manifest entry carries `stream_continues` as a JSON boolean (`true` or `false`), that value decides in place of the header bit."
  - Normaliser in another section, L86-88: "every text value in a manifest is trimmed of surrounding whitespace before it is used".
- Rule (encoder site):
  - L72-74: "When `delta_raw_len` is a JSON integer, the delta is written in exactly that many bytes. Otherwise (null, or any other value) ... the shortest form".
  - Normaliser at L79-80: hex is read case-insensitively after trimming.
- Shipped separating row: environment/data/stream3_manifest.json (beta has `"stream_continues": "true"`, a string over a clear header bit, and a padded path; gamma has a JSON false).
- Reflex:
  - Python truthiness or coercion: `"false"` and `" TRUE "` trimmed then read as booleans, `1`/`0` as booleans;
  - `int(" 2 ")` for delta_raw_len;
  - ignoring the override entirely (the a2 program).
- Hidden cases:
  - _manifest override roll: JSON booleans that flip or agree with the header; ignored values "true", "false", " TRUE ", "False", 1, 0, null;
  - padded paths in fx_stream_new_runs;
  - fx_rule_boolean_override;
  - fx_mutation_override (one JSON boolean flipped);
  - _hand_edit in fx_encode_edited (text lengths, upper-case padded hex);
  - fx_rule_length_integer.
- Wrong reading fails: stream docs with overrides (interleaved, new_runs, reset_runs, mix_a, mix_b, remap_runs whenever an override draw lands), rule_boolean_override, mutation_override_flip, encode_doc_edited, rule_length_integer.

### Other checks (rules kept from r1, unchanged in substance)
reject_precedence (merges the old magic/version, version/reserved and offset15/both_reserved checks), reject_count_bound, reject_crc_fields, report_*. The gate segment `_base` now uses one plain field under an identity revision, so the rejection checks read the rejection rules alone.

### Reflex program (a2 agent, OUT/agent_program)
Tests-only local score 18/107 = 0.1682 (its own reports regenerated on the new data; 15/107 = 0.1402 with its stale /app/out). It passes reject_precedence, reject_count_bound, reject_crc_fields, report_roundtrip, report_error_analysis and report_format, and fails every lever-bearing check.
