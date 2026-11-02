# Hardness r1 solvers (auditor-written, independent of the builder's wrong/)

Every `.py` here is `solution/solve.py` with exact-string edits applied by `make_solvers.py`
(each edit asserted to match once). Run as solve.py: `--build <data> <decode> <encode>` then
`--emit-reports <data> <out>`. `S1_stub/`, `SC_fabricated/`, `SC_header_only/` are prebuilt
workspaces. Scores: tests-only, method (b), see `../../../../20261021_vendor-archive-roundtrip-recovery/hardness_r1/`.

| id | edit (one line) | tests-only |
|---|---|---|
| S1_stub | decode prints `{}`, encode writes 0 bytes, 3 reports `{}`, 4 lines `{}` | 0.0414 |
| S2 | all seven primary reflexes below + CR1 | 0.2759 |
| S3_LV1 | `--stream`: fresh `{"cum":0,"res":[]}` per file | 0.9103 |
| S3_LV2 | encoder `exts = []` (frame rebuilt from value fields only) | 0.8138 |
| S3v_LV2b | encoder re-sorts extensions by type | 1.0000 |
| S3_LV3 | decoder unescapes the whole frame region, then walks frames on the unescaped bytes | 0.8345 |
| S3v_LV3b | no escaping at all (decoder never unescapes, encoder never escapes) | 0.8207 |
| S3_LV4 | encoder always shortest LEB128; decoder reports the shortest length | 0.8828 |
| S3_LV5 | trailer CRC checked right after the magic | 0.8069 |
| S3v_LV5b | record_count_overflow checked before the reserved bytes | 0.9793 |
| S3_LV6 | salvage: no resync, one damage entry to the trailer, stop | 0.8552 |
| S3v_LV6b | salvage: resume at the first 0xAA without re-validating | 0.9793 |
| S3_REMAP | short key canonical id = raw key under every revision | 0.9448 |
| S4 | reflex on the HIDDEN-ONLY primaries (LV1, LV4, LV6, REMAP) + CR1; right on LV2/LV3/LV5 (their reflexes fail visible self-tests) | 0.6483 |
| S4b | CR1 only: salvage returns the header error object (early-return gate shared with decode) | 0.9655 |
| PAIR_LV1_REMAP | LV1 + REMAP | 0.8897 |
| PAIR_LV3_LV4 | LV3 + LV4 | 0.7172 |
| DS | stage-1 wrong: every record's field/unit/canonical_id = null | 0.7793 |
| S_CUM | contract-literal: a raw frame also sets the cumulator (format_contract.md line 96) | 0.9241 |
| SC_fabricated | S1_stub + fabricated roundtrip_report + hardcoded error_analysis | 0.0828 |
| SC_header_only | 15-line header validator in precedence order, no frame decoding, fabricated reports | 0.2207 |
