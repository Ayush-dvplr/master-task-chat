# BUILD REPORT - vendor-archive-roundtrip-recovery

Archetype format-recovery, category data-processing, seed 284611. Built 21 Oct 2026.
GEN and QC fingerprints re-checked before and after: unchanged (9b8229f6). Nothing
was written inside GEN or QC.

## Tree and file counts (23 files)

```
instruction.md  task.toml
environment/Dockerfile
environment/data/  (12 files)
  capture_catalog.jsonl  field_layouts.csv  symbol_table.tsv  revision_map.ini
  schema_registry.json   crc_profiles.json  capture_alpha.varc  capture_beta.varc
  format_contract.md  escape_rules.md  revision_notes.md  decoder_appendix.md
solution/  solve.sh  solve.py  TRUTH.md
tests/  Dockerfile  test.sh  test_output.py  judge.toml  reward.toml
```

## Data formats, line counts, chains

Formats: jsonl, csv, tsv, ini, json, md, and binary .varc (7 formats). Record files
(A5): capture_catalog.jsonl 17700, field_layouts.csv 2101, symbol_table.tsv 2101
(each >= 2000). Non-record: revision_map.ini 1028, schema_registry.json, crc_profiles.json.
Binary: capture_alpha.varc + capture_beta.varc (one two-segment stream, no cross-file refs).
Total non-md non-binary input lines 22950 (minimum 20000). Specs (.md) hold the contract.

Every record file is load-bearing: capture_catalog feeds the format_report tallies and the
roundtrip self-check; field_layouts and symbol_table feed the field names and the
field_name_sha256 / field_unit_sha256 digests in format_report; revision_map feeds the
remap used in the hidden eval. No padding rows.

Chains (length 4 or more): C1 capture hex -> header revision -> revision_map.ini ->
field_layouts.csv -> normalised field name. C2 frame dict_index -> stream resolved list ->
symbol_table alias -> resolved value -> roundtrip byte match. C3 capture hex -> magic/version/
reserved/overflow/trailer precedence -> crc_profiles.json -> error_analysis catalog_errors.
C4 body_len -> escape_rules.md -> bounded unescape -> value + extensions -> encode byte-exact.

## Lever table (from LEVERS.md)

Positive total 145 over 42 positive checks; negatives -23 over 6 checks; 48 checks total.
Hidden-weight share 0.83. Every counted lever is HIDDEN-ONLY (visible catalog + alpha/beta
do not separate the right reading from the reflex) and loses points under its wrong reading.

| Lever | Checks | Positive weight |
|---|---|---|
| existence | 6 | 6 |
| basic-decode (hidden eval) | 6 | 18 |
| LV-VA-1 stream state across files | 3 (+compA_value 5) | 13 (+5) |
| LV-VA-2 opaque extensions on modified records | 3 (+compA_ext 5) | 13 (+5) |
| LV-VA-3 framing-aware escaping | 3 | 13 |
| LV-VA-4 representation memory | 3 (+compA_len 3, +va2_untouched 3) | 13 (+3) |
| LV-VA-5 rejection precedence | 5 (+heavy 5) | 15 (+5) |
| LV-VA-6 resync | 4 (+heavy 5) | 16 (+5) |
| composition all-levers | 1 | 3 |
| reports | 4 | 12 |

Negatives: negative_hardcoded_sample_answers (-5), negative_filename_dependent_behaviour (-5),
negative_reads_training_corpus_at_runtime (-5), negative_rebinds_verifier_dependencies (-5),
negative_nondeterministic_output (-3). Full per-check table in
`_work/vendor-archive-roundtrip-recovery/LEVERS.md`.

## Wrong-implementation confirmation (lever discrimination)

Each lever's wrong reading loses exactly its checks (measured locally with the real checks):
W-VA4 always-shortest (self-consistent) 0.9241; W-VA2 drop-extensions (self-consistent) 0.8345;
W-VA3 no-unescape 0.8759; W-VA1 per-file-state 0.9103; W-VA6 abort-on-damage 0.8552;
W-VA5 wrong-precedence 0.9586. The two self-consistent wrong encoders are both caught.
Detail in `_work/.../wrong/README.md`.

## Script, validator and playground results

- structure_qc.py: 0 FAIL, 1 WARN (X1 two .varc binaries, expected).
- instruction_qc.py: 0 FAIL, 0 WARN (no C6 grader-wording).
- tests_qc.py: 0 FAIL, 5 WARN (A3 48 checks over the 35 cap; A5 four checks read agent
  output through the shared `_holds` try/except wrapper, so bad output returns False and
  no check raises, TS-29 satisfied).
- judge_qc.py: 0 FAIL, 0 WARN.
- validate_bundle.py --archetype format-recovery: GATE PASS, 48 passed, 0 failed.
- playground.py --skip-docker: 0 FAIL, 1 WARN. A1 pass, A3 pass, A4 pass (every non-md
  data file named in a spec), A5 pass (22950 lines). A2 WARN lists only test-internal
  fixture and schema dict keys (cross_dict, mod_bytes, id_to_name, transit_note, ...), not
  agent output conventions; confirmed test-internal (CL-5).

## Oracle score

Oracle on the tests channel: reward 1.0, measured with the real harbor-rewardkit 0.2.1
(`uvx --from harbor-rewardkit==0.2.1 rewardkit tests --workspace <abs>/app`, tests-only
reward.toml normalised to the test positive total). nop: reward 0.0 (same tool). A local
run of all 48 checks against the built programs also scores 145/145. The judged channel has
no oracle score (no OPENAI key; tests-only, per convention).

## Open conflicts

OPEN CONFLICT Q18: TRUTH.md provenance keeps the generator-written `authored_by: harbor-generator`
and `status: generated_reference`. validate_bundle 15.5 requires authored_by/status (passes),
while QC DS-27 fails authoring/tooling attribution. Kept as the generator wrote it per the
build prompt; no third option invented.

## Not run

- Full Step 10 under Docker (oracle x5 via `harbor run`, stub, D4 ablation): not run here.
  The oracle 1.0 and nop 0.0 were measured with the real rewardkit on the tests channel
  rather than through a Docker harbor run. Docker-based playground checks (D1-D4) were
  skipped (`--skip-docker`); for this archetype D4 ablation is expected high because most
  weight is on the verifier's hidden corpus (ablation_max 0.95).
- Measured difficulty baselines (S2 reflex, S4 careful, S4b single-lever-correct): these are
  the P3 hardness run's job. P3 must also score S4b (correct on every single-lever hidden
  case, wrong only where two rules meet); if S4b is near 1.0 the compositions need strengthening.
