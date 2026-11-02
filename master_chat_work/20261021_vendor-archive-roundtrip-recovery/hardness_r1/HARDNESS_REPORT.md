# HARDNESS REPORT r1: vendor-archive-roundtrip-recovery

Auditor run 21 Oct 2026, 17:35 to 18:10 IST (12:05 to 12:40 UTC). Bundle read-only, sha256 tree unchanged (see end).
All scores are tests-only, method (b): the real `tests/test_output.py` run by `uvx --python 3.12 --from
harbor-rewardkit==0.2.1 rewardkit <tests> --workspace <ws>` with `judge.toml` removed and
`reward.toml` = `{test_output = 1/145}` (0.006896551724137931). Gate: oracle 1.0 (145/145), nop 0.0, measured before any other solver.
Agent programs ran as my user (no `setpriv`), so permission-based isolation was not exercised.

**Verdict: REBUILD.** S4 = 0.648 (target 0.10 to 0.20), S4b = 0.966, S2 = 0.276, best shortcut = 0.221,
and the primary reflexes of 3 of the 7 levers (LV2, LV3, LV5) are DERIVABLE. Also found two validity defects
(V1, V2 below) that must be fixed before any further hardness work.

## 1. Solver table (tests-only, method b)

| id | solver | score | pts /145 | expectation | ok? |
|---|---|---|---|---|---|
| S0 | nop | 0.0000 | 0 | 0.0 | yes |
| S1 | stub (empty/default shapes) | 0.0414 | 6 | <= 0.25 | yes |
| S2 | every primary reflex + CR1 | 0.2759 | 40 | <= 0.10 | **no** |
| S3_LV1 | per-file stream state | 0.9103 | 132 (-13) | loses | yes |
| S3_LV2 | encoder drops extensions | 0.8138 | 118 (-27) | loses | yes |
| S3_LV3 | whole-region unescape then walk | 0.8345 | 121 (-24) | loses | yes |
| S3_LV4 | always shortest + shortest length reported | 0.8828 | 128 (-17) | loses | yes |
| S3_LV5 | CRC checked after magic | 0.8069 | 117 (-28) | loses | yes |
| S3_LV6 | abort on first bad frame | 0.8552 | 124 (-21) | loses | yes |
| S3_REMAP | identity remap | 0.9448 | 137 (-8) | loses | yes |
| S4 | careful self-tester (see def.) | 0.6483 | 94 | 0.10 to 0.20 | **no** |
| S4b | right on every rule and single-lever case; wrong only at CR1 | 0.9655 | 140 | <= 0.30 | **no** |
| S5 | oracle | 1.0000 | 145 | 1.0 | yes |

Variants (second natural reading per lever): LV2b re-sorted extensions 1.0000 (loses 0), LV3b no escaping 0.8207 (-26),
LV5b overflow before reserved 0.9793 (-3), LV6b first 0xAA accepted 0.9793 (-3).

S1 paid: decoder_exists, encoder_exists, format_report_present, roundtrip_report_present, error_analysis_present,
decoded_examples_present (6 x 1).

S2 paid (40): the 6 existence checks; basic_raw_wide, basic_raw_narrow, basic_delta, basic_dict, basic_reset,
basic_longkey (18); **va1_cross_delta (5), va4_modified_shortest (5), va5_magic_over_version (3), report_roundtrip (3)**.
The last four are named after levers but are paid by every reflex measured (see section 5).

Definitions. S4 = master note 5 read with the self-test allowance: right on every rule the visible data can confirm,
and the natural reflex code structure from DESIGN.md wherever visible data cannot confirm it (HIDDEN-ONLY primaries LV1,
LV4, LV6, REMAP) plus the composition reflex CR1. In round 1 no lever is new, so "each NEW lever's reflex" applies to none.
S4 loses va1_cross_dict, va1_three_seg, va2_untouched_preserved, va4_overlong_bytes, va4_len_reported,
heavy_salvage_recovers, va6_* (4), compA_value, compA_len, compA_all. This S4 assumes a careful agent ignores four rules
that are each stated in plain words, so it is a generous lower estimate. S4b (0.966) is the upper estimate for an agent
that reads every rule. A real careful run probably lands between 0.65 and 0.97. Either way it is far above 0.20.

CR1 (LV5 x LV6) is the only natural two-rule failure I could find in this check bank: the salvage path reuses the
decode header gate and returns early with the error object. Every other composition check is a conjunction of
independent rules, so a solver right on each rule is right on the composition.

## 2. Underivability (right vs reflex on visible shipped data only)

Surfaces: single decode of all 17700 catalog lines + alpha + beta; salvage of the same; `--stream [alpha, beta]`;
encode(decode(x)) bytes for every ok capture. Counts are outputs that differ from the oracle.

| lever | reflex | decode | salvage | roundtrip | stream | verdict |
|---|---|---|---|---|---|---|
| LV1 | per-file state | 0 | 0 | 0 | 0 | HIDDEN-ONLY |
| LV2 | encoder drops extensions | 0 | 0 | 4688 (self-roundtrip fails) | 0 | **DERIVABLE** |
| LV2b | extensions re-sorted | 0 | 0 | 0 | 0 | HIDDEN-ONLY, but costs 0 points |
| LV3 | whole-region unescape | 202 (clean captures turn into errors) | 0 | 202 | 0 | **DERIVABLE** |
| LV3b | no escaping | 0 | 0 | 0 | 0 | HIDDEN-ONLY (-26) |
| LV4 | always shortest | 0 | 0 | 0 | 0 | HIDDEN-ONLY |
| LV5 | CRC after magic | 1488 (catalog rejects relabelled) | 1488 | 0 | 0 | **DERIVABLE** |
| LV5b | overflow before reserved | 0 | 0 | 0 | 0 | HIDDEN-ONLY (-3) |
| LV6 | abort | 0 | 0 | 0 | 0 | HIDDEN-ONLY |
| LV6b | first 0xAA | 0 | 0 | 0 | 0 | HIDDEN-ONLY (-3) |
| REMAP | identity | 0 | 0 | 0 | 0 | HIDDEN-ONLY |
| CR1 | salvage early return | 0 | 2500 (rejects) | 0 | 0 | DERIVABLE by the mechanical rule, but there is no visible ground truth for salvage of a reject |

The builder's claim that W-VA2 "passes its own round-trip on the visible captures" is false: 4688 visible captures carry
extensions (types 1, 2, 3, 7, 9), so dropping them fails the agent's own self-test. LV2's only hidden-only reading
(re-sorting) costs nothing, because no fixture has two extensions in one record.

## 3. Shortcut hunt (about 25 min, own scratch copy of instruction.md + environment/ only)

| attempt | result |
|---|---|
| SC_fabricated: stub programs + invented roundtrip_report (4 entries, equal fake digests) + error_analysis with constants and catalog_errors counted offline | **0.0828** (existence 6 + report_roundtrip 3 + report_error_analysis 3) |
| SC_header_only: about 15-line header validator in the listed order, no frame decoding, fabricated reports | **0.2207** (adds the five va5_* checks 15 + heavy_decode_rejects 5) |
| hardcoding visible outputs / keying on names or row counts | no gain: no check reads catalog-derived values except report_format (needs a real decoder); negative_hardcoded_sample_answers did not fire on any solver |
| self-consistent program that round-trips only what it decoded | no gain: decode checks require the exact key set, and encode checks get verifier-built docs with no room for replayed bytes |
| image / verifier paths | environment/ holds only the Dockerfile + data (no tests, solution or generator). Catalog rows carry no `transit_note` (grep: 0 hits). /tests is `chmod -R go-rwx` and programs run under `setpriv nobody`, so they cannot read the tests at grade time. Reasoned from test.sh and `_wrap`, **not run in Docker** |

Best shortcut: **0.2207** (> 0.10). report_roundtrip pays a fabricated report: it checks only internal consistency
(`input_sha256 == rebuilt_sha256`) and never decodes or re-encodes anything. The five precedence checks plus
heavy_decode_rejects (20 points, 0.138) are earned by one header function with no codec at all.

## 4. Extra measures

- Independence: LV1+REMAP lost 16 against 13+8 = 21 additive (they share compA_value, 5). LV3+LV4 lost 41 = 24+17 (fully additive).
- Composition share: 33/145 = **0.228**. These are the checks lost by 2 or more distinct levers' solvers:
  va2_untouched_preserved, va3_reencode, heavy_salvage_recovers, compA_value, compA_len, compA_ext, compA_all,
  report_format, report_error_analysis. But S4b loses only 5 of those 33, so they are conjunctions, not interactions.
- Downstream isolation: DS (stage-1 naming wrong: every field, unit and canonical_id null) still earns every encode check
  (va2_*, va4_overlong_bytes, va4_modified_shortest, compA_ext, compA_all), every stream value (va1_*) and every salvage
  check (va6_*, heavy_*), for 0.7793. It lost only the checks that read `field` (basic_* 18, compA_value 5,
  compA_len 3) or the reports (6). Isolation holds. Only va3_reencode is chained (it feeds the agent's own decode doc to its encoder).
- Immune checks (paid by every reflex measured, 40 points): the 6 existence checks, 6 basic_*, va1_cross_delta,
  va4_modified_shortest, va5_magic_over_version, report_roundtrip.

## 5. Validity defects found (fix first)

- **V1: contract and verifier disagree on the cumulator.** format_contract.md lines 96 to 97 say "The cumulator is set to the
  resolved value for raw, delta and dict frames". The verifier's `parse_frame` and solve.py `_read_frame` do NOT set it
  on raw frames (the datagen `_make_capture` does). Measured: S_CUM, the oracle plus that one contract-literal line, scores
  0.9241. It loses basic_delta, va1_cross_delta and report_decoded_examples (11 points). The bug also explains why
  va1_cross_delta pays the per-file reflex: seg A holds only raw frames, so the cumulator stays 0 under either reading.
- **V2: the hidden encode inputs are not valid decode documents.** `_r_delta`/`_r_dict` set `value: null`, and they are fed
  straight to encode.py in fx_va2 `untouched`, fx_va4 `modified` and fx_compA `all`. That contradicts
  decoder_appendix.md ("value: the fully resolved signed integer"). An encoder that treats `value` as the source of
  truth (a natural way to read "a field whose value was changed") crashes there. Found by reading the code; this
  variant was not scored.
- Latent: the verifier's `decode_stream` threads ONE state through the whole manifest and ignores stream_id, while the
  appendix says "interleaved streams ... State is kept per stream_id". Current fixtures never interleave, so it is not
  triggered yet, but it blocks fix F4. Also: TRUTH.md and LEVERS.md say 6 negatives, but 5 are registered (-23).
  `EVAL_SEED`/`CHALLENGE_SEED` are defined but unused (the hidden cases are 12 hand-built fixtures).

## 6. Master's notes answered

1. Hidden-weight share 0.83 does not hold S2 down: S2 = 0.276. Visible checks pay 24 (existence 6 + basic 18). Lever-named
   checks that a reflex also passes pay 16: va1_cross_delta (V1), va4_modified_shortest (an always-shortest encoder writes the
   expected shortest bytes), va5_magic_over_version (any magic-first order passes) and report_roundtrip (self-reported).
2. tests_qc WARN, quoted: `WARN [A5] check decoded_examples_present (line 1221) reads agent output with no try/except; confirm bad
   output returns False instead of raising` (the same wording for report_decoded_examples line 1530,
   negative_reads_training_corpus_at_runtime line 1597 and negative_rebinds_verifier_dependencies line 1609). All four put
   their reads inside `fn` and pass it to `_holds`, which returns False on any exception. A missing file therefore
   scores False: no positive check pays on an absence (TS-25 holds; S0 = 0.0 and S1 paid only 6 existence points), and
   the two negatives do not fire on an empty workspace. The reflex is not paid by `_holds` either; the accidental payments come from
   fixture design (note 1). Residual risk: `_holds` also swallows exceptions raised by the verifier's own code, which
   would silently zero a check for every solver. Oracle 1.0 shows that does not happen today.
3. Builder vs auditor: W-VA1 and W-VA6 match mine exactly (0.9103, 0.8552). The builder's W-VA4 keeps the true length on
   decode (0.9241); mine also reports the shortest length (0.8828). W-VA3 is a decode-only no-unescape (0.8759); my LV3b
   also drops escaping in the encoder (0.8207). W-VA5 skips the version check (0.9586); mine checks the CRC early (0.8069,
   derivable). The builder's self-consistency claim for W-VA2 is false (section 2). The builder scored no S2, S4, S4b or
   REMAP, and its "no check is immune" misses the 4 immune lever checks.
4. S4b = 0.9655 (> 0.30): every composition except heavy_salvage_recovers is a conjunction. Weak ones: compA_value,
   compA_len, compA_ext, compA_all, va2_untouched_preserved, va3_reencode.
5. S4 written as natural one-sitting code: one state per file in the stream loop, a shortest-only `write_sleb128`, abort
   on the first bad frame, identity remap, and a shared early-return header gate.
6. Shortcut hunt done (section 3), including image and verifier paths and the self-consistent round-trip program.
7. Method (b); oracle 1.0 and nop 0.0 were proved first.

## 7. Fix list (smallest first; prefer new separating cases over weight changes)

- **F1 (V1, blocking):** make raw frames set the cumulator in the verifier `parse_frame` and in solve.py, matching the contract.
  Then re-run the oracle. va1_cross_delta becomes separating (seg A raw 333, seg B delta 7: 340 against 7 per-file).
- **F2 (V2):** build every encode input from `decode_segment(encode_segment(base))` and modify it consistently
  (change `value` and the token, drop `delta_raw_len`), so all inputs are valid decode documents.
- **F3 (immune checks, S2):** fold va4_modified_shortest into one doc that also carries an untouched overlong delta.
  Make report_roundtrip recompute: decode each example's hex with the verifier, run the agent's encode.py on it, compare
  bytes. Replace va5_magic_over_version with a reserved byte 15 only plus overflow case. Remove heavy_decode_rejects, which
  is single-lever LV5 despite its name, or pair it with a frame observable.
- **F4 (real interactions, S4b):** add two-rule cases that natural per-rule code gets wrong:
  (a) an interleaved manifest [A0, B0, A1, B1] with cross-file dict refs in both streams. It fails both "fresh per file" and
  "one state per manifest" (needs the latent decode_stream fix);
  (b) a stream whose seg B changes revision (rev 0 to rev 5) with a dict ref into seg A, so the field must come from seg B's
  revision (fails a stream object that caches the first header);
  (c) a short key under rev 4 to 7 in a stream 1 to 40 whose symbol_table aliases the REMAPPED id, while a different alias
  exists for the raw-key id (tests remap before alias, two files);
  (d) delta and dict frames right after a damaged span in salvage. This needs one added sentence in escape_rules.md on
  state across damage (DS-21).
- **F5 (S4, hidden-only weight):** run the base-decode fixtures under revisions 4 to 7 and in aliased streams, so the
  hidden-only REMAP rule and the alias rule carry the base weight instead of identity-revision cases that visible data
  already confirms.
- F6: give a lever whose primary reflex is DERIVABLE (LV2, LV3, LV5) no hardness credit, or add cases for its
  hidden-only variant (LV2: two opaque extensions out of type order in one record; LV3: more weight on the no-escape
  reading; LV5: more pairs among version, reserved and overflow).

Arithmetic warning: even after F3, S2 keeps 24 visible points. Reaching S2 <= 0.10 needs a positive total of at least 240,
or F5 moving the basic cases onto hidden-only rules.

## 8. Integrity

Bundle sha256 tree: 23 files, list hash `ceb7fffb360f9ea246a32592065bb6408bd5f7bed606f61b4276eed23083bed2` before
and after (`bundle_tree.sha256` beside this report). Upstream: GEN/QC no longer match `fingerprints/*.json` (9b8229f6). HEAD is bde868c4,
the push the master already migrated to (`20261021_qc-push-bde868c4/MIGRATION_REPORT.md`). No QC rule text was used
to score. Solvers: `_work/vendor-archive-roundtrip-recovery/wrong/hardness_r1/`. Raw data: `scores_tests_only.json`,
`underivability_raw.json` and `check_lever_map.json` beside this report.
