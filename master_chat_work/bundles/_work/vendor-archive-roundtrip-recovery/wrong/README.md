# Wrong implementations and the points each loses (measured locally via the real tests)

Baseline oracle tests score: 1.0 (145/145). Each variant is a one-line edit of the
built decode.py/encode.py; it confirms the lever's checks discriminate. Two are
self-consistent encoders (decode(encode(x))==x for what they emit), the trap the
agent self-test would miss.

| Variant | Edit | Tests score | Checks lost |
|---|---|---|---|
| W-VA4 always-shortest (self-consistent encoder) | encoder ignores delta_raw_len, always shortest LEB128 | 0.9241 | va4_overlong_bytes, va2_untouched_preserved, compA_all |
| W-VA2 drop-extensions (self-consistent encoder) | encoder emits no extensions | 0.8345 | va2_modified_bytes, va2_extensions_kept, va2_untouched_preserved, va3_reencode, compA_ext, compA_all |
| W-VA3 no-unescape | decoder treats the body window as raw (no unescaping) | 0.8759 | va3_boundary_value, va3_ext_escaped, va3_reencode, compA_value |
| W-VA1 per-file-state | --stream resets dictionary/cumulator per file | 0.9103 | va1_cross_dict, va1_three_seg, compA_value |
| W-VA6 abort-on-damage | salvage stops at the first bad frame instead of resyncing | 0.8552 | heavy_salvage_recovers, va6_single_records, va6_single_damage, va6_two_spans, va6_no_false_resync |
| W-VA5 wrong-precedence | decoder skips the version check (checks reserved/overflow first) | 0.9586 | va5_version_over_reserved, va5_version_field |

Every lever loses points under its wrong reading; no check is immune. The
self-consistent W-VA2 and W-VA4 are both caught (they pass their own round-trip
on the visible captures but fail the hidden modified/overlong byte checks).
