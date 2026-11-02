# Stale build scripts (round 1, 22 Oct 2026)

datagen.py, ref_codec.py, checks_addendum.py, specs/, scaffold_orig/ and wrong/ describe the v0
bundle. Do not run them. Round 1 edits the bundle directly: `tests/test_output.py` is the single
source of the generated data (`python3 tests/test_output.py <bundle>/environment` writes the
catalog, tables, revision map and the three stream 3 files into environment/data) and of the
hidden fixtures.

Harden lp1 r1 (23 Oct 2026): still true. `tests/test_output.py` is the single source of the
generated data (catalog with `value_sum`, stream 3 files, `stream3_manifest.json`); the tables are
byte-identical to r1. Do not run datagen.py, ref_codec.py, checks_addendum.py or wrong/.
