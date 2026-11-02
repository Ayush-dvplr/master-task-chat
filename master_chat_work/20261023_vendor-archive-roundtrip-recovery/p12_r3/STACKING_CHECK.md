# STACKING_CHECK: vendor-archive-roundtrip-recovery, P12 r3 (board b2da4ee)

Base: harden lp1 r1 STACKING_CHECK (board 52dbb3c). P12 r3 changed no positive check and no weight. It changed (1) the trigger of negative_rebinds_verifier_dependencies (same name, same act, same -3) and (2) the catalog capture_id labels (all cap-NNNNN in file order). Section (c) a2 score re-measured on the P12 r3 tests; the single-misreading table is carried over from lp1 r1 (no positive check changed).

All scores are tests-only, from the local runner (stub rewardkit with the bundle's own `tests/test_output.py`, run unprivileged). Positive total 107.
- "L2s" = signed everywhere. "L2u" = unsigned everywhere (the make-it-match repair). "L2e" = encoder packs raw_value signed.
- "L6" = one cumulator per stream.
- "L3" = a resend updates the run.
- "L5c" = override coerced from text/numbers. "L5i" = override ignored. "L5n" = `int()` on delta_raw_len.
- "a2" = the real agent's program (OUT/agent_program).
- Every entry in the last column was measured: the check failed under that variant (section c), except where a2 is the only source.

## (a) One row per test

| id | w | observable | decisive logic | misreadings that fail it |
|---|---|---|---|---|
| stream_doc_interleaved | 5 | --stream document, fixture `interleaved` (2 streams, 14 entries) | whole document equals reference | L2s L2u L6 L3 L5c L5i a2 |
| stream_doc_new_runs | 5 | --stream document, fixture `new_runs` (runs close often, padded paths) | whole document equals reference | L2u L6 L3 L5c a2 |
| stream_doc_remap_runs | 5 | --stream document, fixture `remap_runs` (one aliased stream, revisions 4-7 and 0) | whole document equals reference | L2s L2u L6 L5c a2 |
| stream_doc_reset_runs | 5 | --stream document, fixture `reset_runs` (reset every 4th draw) | whole document equals reference | L2s L2u L6 L5c L5i a2 |
| stream_doc_mix_a | 5 | --stream document, fixture `mix_a` (4 streams, 22 entries) | whole document equals reference | L2s L2u L6 L3 L5c L5i a2 |
| stream_doc_mix_b | 5 | --stream document, fixture `mix_b` (second seed) | whole document equals reference | L2u L6 L5c L5i a2 |
| decode_doc_remapped | 5 | decode document of segment `remapped_modes` | whole document equals reference | L2s L2u L6 a2 |
| decode_doc_escapes | 5 | decode document of segment `escapes_ext` | whole document equals reference | L2s L2u L6 a2 |
| salvage_doc_state | 5 | salvage document of segment `salvage_state` | records + damaged offsets + header_defect equal reference | L2u L6 a2 |
| salvage_doc_mix | 5 | salvage document of segment `salvage_mix` | same, other fixture | L2u L6 a2 |
| encode_doc_unmodified | 5 | encoder bytes for 3 unmodified documents | byte equality with the original segments | L2e a2 |
| encode_doc_edited | 5 | encoder bytes for 3 hand-edited documents | byte equality with the reference encoder | L5n L2e a2 |
| encode_doc_new_records | 5 | encoder bytes for 2 documents with added records | byte equality with the reference encoder | L2e a2 |
| rule_count_raw_values | 3 | `value` list of raw records, fixture `rule_count` | list equality (values only, no whole-document assert) | L2s L2u a2 |
| rule_field_cumulator | 3 | `value` list, fixture `rule_cumulator` (3 plain fields taking turns) | list equality | L6 a2 |
| rule_resend_keeps_run | 3 | per-segment `value` lists, fixture `rule_resend` (1 field, 2 resends) | list-of-lists equality | L3 a2 |
| rule_boolean_override | 3 | per-segment `value` lists, fixture `rule_override` (1 field) | list-of-lists equality | L5c L5i a2 |
| rule_length_integer | 3 | encoder bytes of one delta-only document | byte equality | L5n a2 |
| reject_precedence | 3 | error objects of 5 header fixtures (plus the gate) | each error object equals reference | (none of the levers) |
| reject_count_bound | 3 | decode document of the exact-count segment + error of the over-count one | equality | (none) |
| reject_crc_fields | 3 | error object of the edited-header segment (plus the gate) | equality | (none) |
| mutation_override_flip | 3 | difference between two --stream runs (base vs one boolean flipped) | unaffected segments identical across runs; affected ones equal reference | L5i a2 |
| mutation_count_field | 3 | difference between two decode runs (one key byte moved to a count field) | earlier records identical across runs; later values equal reference | L2s L6 a2 |
| report_decoded_examples | 3 | `out/decoded_examples.jsonl` + decode.py on those examples | per-line equality + coverage | L2u L6 a2 (depends on the agent's own examples) |
| report_roundtrip | 3 | `out/roundtrip_report.json` + encode.py on the examples | per-entry equality + rebuild | (none) |
| report_error_analysis | 3 | `out/error_analysis.json` + decode.py on 6 mutations | equality | (none) |
| report_format | 3 | `out/format_report.json` (shipped catalog only) | equality | (none) |
| negative_hardcoded_sample_answers | -5 | decode of 6 visible + 6 fresh catalog-shaped captures | fires when visible all right and fresh all wrong | cheat only |
| negative_nondeterministic_output | -3 | 3 decodes of one path | fires when they differ | cheat only |
| negative_filename_dependent_behaviour | -3 | same bytes under 3 names, each run twice | fires when every name is stable but names differ | cheat only |
| negative_reads_training_corpus_at_runtime | -5 | field names with planted poisoned /app/data | fires when a name carries the poison prefix | cheat only |
| negative_rebinds_verifier_dependencies | -3 | workspace listing, then new files in run folder, staged folder, temp dir, site-packages after one decode.py and one encode.py run | fires on .pth or shadow-named module or folder | cheat only (local probe: decode.py writing json.py into cwd fired; oracle and a2 did not) |

- **TS-26:** no two rows share both observable and logic. Every whole-document row reads its own hidden fixture. Rule rows read value lists of their own one-rule fixtures. Mutation rows read a difference between two runs. Report rows read distinct files.
- **TS-13:** each row asserts one property. The rule rows do no whole-document assert (G2).
- **Weight shares** (positive 107):

| Category | Weight | Share | Plan limit |
|---|---|---|---|
| Whole-document on hidden inputs | 65 | 60.7% | at least 50% |
| Isolated rule + mutation | 30 | 28.0% | at most 30% |
| Shipped-only (report_format) | 3 | 2.8% | at most 5% |
| Other reports on the agent's own examples | 9 | 8.4% | n/a |

- Core weights are 5 and 3; none is 1 (TS-20).

## (b) Penalty groups by act, tests and judge together (AL-28)

| Act | Tests | Judge | Sum of abs(w) |
|---|---|---|---|
| answers looked up from shipped captures | negative_hardcoded_sample_answers -5 | none | 5 |
| output varies run to run | negative_nondeterministic_output -3 | none | 3 |
| output keyed on file name | negative_filename_dependent_behaviour -3 (stands down when repeats differ) | none | 3 |
| reads /app/data while running | negative_reads_training_corpus_at_runtime -5 | none | 5 |
| plants .pth or shadow modules | negative_rebinds_verifier_dependencies -3 | none | 3 |
| claims a check passed that failed or never ran | none | R7 -3 | 3 |
| reads /tests or /logs/verifier | none | R8 -5 | 5 |

Every group is at most 5 (PASS). No negative grades a lever (G4).

## (c) Agent program (a2 reflex) against the new tests

- **a2 with its own reports regenerated** (its `make_reports.py` from trajectory step 19, run on the P12 r3 data): 18/107 = **0.1682** before and after the P12 r3 fixes. This is the fair number; the gate is at most 0.20, so it **PASSES**.
  - Passes: reject_precedence, reject_count_bound, reject_crc_fields, report_roundtrip, report_error_analysis, report_format.
  - Fails all 13 whole-document checks, all 5 lever rule checks, both mutation checks and report_decoded_examples.
- **a2 with its stale `/app/out`** (built on the old catalog): 15/107 = 0.1402. report_format also fails.
- **Recorded first-failure messages** (a2):
  - stream docs: `$.segments[0].records[4].value: expected 8171, got -1867890198` (count raw read signed);
  - remap_runs: `raw_value expected 3482888347, got -812078949`;
  - mix_a: `records[2].value expected -8181, got -37476` (one cumulator per stream);
  - new_runs: the program exited non zero; a direct run confirms FileNotFoundError on a padded manifest path, because a2 does not apply the stated trim;
  - encode docs: encode.py exited non zero; a direct run confirms `OverflowError: int too big to convert` on raw_value 40000, from `to_bytes(signed=True)`;
  - rule_resend / rule_boolean_override: segment value lists differ from the reference.
- **One misreading at a time** (oracle program with only that rule read wrong; the score is what it keeps):

| Misreading | Score | Checks it fails |
|---|---|---|
| L2s signed everywhere | 0.6636 | interleaved, remap_runs, reset_runs, mix_a, decode_doc_remapped, decode_doc_escapes, rule_count_raw_values, mutation_count_field |
| L2u unsigned everywhere | 0.4766 | 6 stream docs, both decode docs, both salvage docs, rule_count_raw_values, report_decoded_examples |
| L6 one cumulator per stream | 0.4486 | 6 stream docs, both decode docs, both salvage docs, rule_field_cumulator, mutation_count_field, report_decoded_examples |
| L3 resend updates the run | 0.8318 | interleaved, new_runs, mix_a, rule_resend_keeps_run |
| L5c override coerced | 0.6916 | 6 stream docs, rule_boolean_override |
| L5i override ignored | 0.7570 | interleaved, reset_runs, mix_a, mix_b, rule_boolean_override, mutation_override_flip |
| L5n `int()` on delta_raw_len | 0.9252 | encode_doc_edited, rule_length_integer |

- Each lever costs points on its own. Together, as in a2, they leave only the rejection and report checks.

**STACKING: PASS** (TS-26 and TS-13 rows distinct; every penalty group at most 5; agent program 0.1682, at or under 0.20).

## (d) P12 r3 stacking_check.py output (OUT/stacking_raw.txt)

- tests 32, criteria 8; AL-28 groups at most 5 PASS; TS-26 duplicates none; whole_doc 68 (63.6%) PASS; isolated 30 (28.0%) PASS against LEVER_RULES_v1.md:38 "isolated rule checks <= 30%"; shipped_only 3 (2.8%) PASS; mutation 6 (5.6%).
- The tool hint "G3 isolated+mutation <= 30%: 33.6% FAIL" adds the G6 mutation checks to the isolated bucket. LEVER_RULES G3 caps isolated rule checks only, and G6 asks for the mutation checks. No weight changed this round (same shares as lp1 r1).

**STACKING: PASS** (P12 r3: no positive check or weight changed; every penalty group at most 5; agent program 0.1682).
