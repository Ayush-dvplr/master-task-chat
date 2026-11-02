# LEVERS: sensor-network-lsq-correlated-adjustment

Board baafa14, harden round 1. Steps are `step_id` values in
`OUT/baseline_v0/.../Run 1/artifacts/logs/agent/trajectory.json` (claude-opus-5, tests 1.0).

## v0 levers (reconstructed, all INFERRED from TRUTH.md, schema.md and test_output.py)

| id | rule (schema.md v0) | reflex reading | graded by (v0 checks) | family | read at | self-check | result | what made it derivable |
|---|---|---|---|---|---|---|---|---|
| V0-1 | unit factors from authoritative rows of reference_unit_registry.csv | use first row / decoy rounded factor | solved_unknowns, final_weights, residual_* | A | step 3 (schema sec 3), 5, 11 | step 32 compares converted sigma with manifest `apriori_sigma_base` | LEAKED | schema sec 3 printed the true factors 79200/3937, 1200/3937; every header `TRAP 2 ... inverse: use the authoritative chain 79200/3937`; manifest column confirms the conversion |
| V0-2 | sigma_stored_as variance vs stddev | square every sigma | final_weights, downweighted_set | A | step 3, 11 | step 32 manifest cross-check | LEAKED | `TRAP 3: apply each shard's sigma_stored_as: square base sigma if stddev...` in every file; manifest `apriori_sigma_base` column (step 17: `OB00001,0.017000000000000000,...`) |
| V0-3 | dir=R negates observed and computed | ignore dir | solved_unknowns, residual_* | A | step 11 | none needed | LEAKED | `TRAP 4: negate observed_value AND computed_nominal for rows with dir=R` |
| V0-4 | azimuth_wrap mod 400 | no reduction | residual_* | A | step 11 | none | LEAKED | `TRAP 5` with inverse |
| V0-5 | transpose epoch-2 ids | keep raw ids | removed_blunder_set, order | A | step 11 | none | LEAKED | `TRAP 6 ... inverse: move the last 3 characters to the front` |
| V0-6 | u, k, crit, origin only from workbook | yaml decoy_tuning_k / json spec | constrained_component_count, tuning_constant, blunder_critical_value, datum_origin | A (isolated) | step 5, 7 | none | LEAKED | schema sec 9/11 and `TRAP 8/9` (step 5: `reject the decoy_tuning_k in iteration_policy.yaml`) |
| V0-7 | IRLS from base weights, quantized, sessions exempt | cumulative reweighting | downweighted_set, final_weights | A | step 3 | step 23 PASS verdict | LEAKED | rule written beside its use in schema sec 11; PASS band confirms |
| V0-8 | correlated session blocks, dissolve on blunder | diagonal weights | final_weights, holdout_eval | A | step 3, 13 | step 23 PASS | LEAKED | schema sec 11b explicit; PASS band confirms |
| V0-9 | stage-1 blunder removal with base weight | use final IRLS weight | removed_blunder_set, global_model_test | B | step 3 | step 23 PASS | LEAKED | schema sec 12 explicit; PASS band confirms |
| V0-10 | chi-square row at stage-2 dof | wrong dof | global_model_test | B | step 15 | step 23 `verdict=PASS` | LEAKED | table header `center = dof * chi_center` and the shipped band brackets the correct vTPv: a full-answer confirmation |
| V0-11 | derived rollup by lowest-index station frame | first partial / any station | derived_key_rollups | A | step 15 (`FICUS,FrameA,boundary_crosser`) | none | LEAKED | map row labels the boundary case |
| V0-12 | max-abs tie lowest obs_id | first seen | residual_summary, holdout_eval | E | step 3 | none | LEAKED | stated in sec 16 |

Shared cause: every shipped file carried `Documented traps ... exact inverse is what a solver must apply` (step 11), and the acceptance table made the shipped run print `verdict=PASS` (step 23), which confirms the whole chain at once.

## Harden round 1 levers

| id | family | rule (where written) | reflex reading | hidden cases | checks the wrong reading fails |
|---|---|---|---|---|---|
| H1-CENTRING | A (split across files, scope by omission) | schema.md sec 4: length observations add (centring_mm/1000)^2 per station with non-zero partial whose station_registry.csv row has mount=tripod; mount/centring_mm columns live only in station_registry.csv | ignore the register columns, or add centring to every station / to angles too | mounts and centring change on challenge, eval, audit | all 18 chain checks (model_test, unknowns, residual, sets, rollups, summary reports x3) |
| H2-ANGLE-REDUCE | decoy default contradicted on a rare shipped boundary | schema.md sec 8: angle misclosure reduced modulo 400 into (-200, 200] | plain observed minus computed (right on every angle but the boundary rows) | shipped 2 rows (OB00213, OB00500), challenge 3, eval 2, audit 1 | all 18 chain checks (boundary row becomes a ~400 gon misclosure and an extra blunder) |
| H3-REVISION | F (rejection path, interacts with id transposition) | schema.md sec 2 + sec 7: duplicate records matched by un-transposed id, higher shard `revision` wins, loser listed in superseded_records | keep the first-seen (or last-seen) copy; compare raw ids | revisions reorder on each hidden extract; one epoch-2 duplicate crosses a transposing and a non-transposing shard | superseded_records_on_hidden_extracts + all 18 chain checks |
| H4-CHAIN | B (dependent chain) | schema.md secs 12-14: dedupe -> variance -> IRLS -> blunders -> n -> dof -> acceptance row (per-row centres) -> verdict | read the verdict from a formula or the shipped band | three regenerated extracts with different control values and acceptance centres | model_test_document and summary_reports x3 |

Removed confirmations: per-file trap blocks with exact inverses, schema "(Trap: ...)" labels and printed factors, the acceptance band that bracketed the shipped answer (shipped verdict is now REJECT_LOW and no wrong reading lands in the band), the base-unit sigma column of observation_weight_manifest.csv, the base-unit restatements in the workbook network sheet.

Local mutant scores (tests channel, positive 62): oracle 62/62; no centring 8/62; no angle reduction 8/62; centring on angles 8/62; centring regardless of mount 8/62; first-seen duplicate 5/62.

Check-to-lever map: artifact_set_exists_and_parses (none, shipped-only); {challenge,eval,audit}_* (H1, H2, H3, H4); control_values_on_hidden_extracts (V0-6, isolated); superseded_records_on_hidden_extracts (H3, isolated); canonical_serialization_on_hidden_extracts (format, isolated); negatives (cheat detectors).

## P12 r2 QC fix effects (board 6a3cd4a)

Each cell is the effect of the corresponding finding's decision on that lever. TS-13 is measured after the split; the hidden document cascade remains.

| lever | JD-15 | AL-27 | DS-22 | TS-13 | JD-5 | DS-6 KEEP | X1 KEEP |
|---|---|---|---|---|---|---|---|
| V0-1 | none | none | none | none | none | none | none |
| V0-2 | none | none | none | none | none | none | none |
| V0-3 | none | none | none | none | none | none | none |
| V0-4 | none | none | none | none | none | none | none |
| V0-5 | none | none | none | none | none | none | none |
| V0-6 | none | none | none | none | none | none | none |
| V0-7 | none | none | none | none | none | none | none |
| V0-8 | none | none | none | none | none | none | none |
| V0-9 | none | none | none | none | none | none | none |
| V0-10 | none | none | none | none | none | none | none |
| V0-11 | none | harder | none | none | none | none | none |
| V0-12 | none | none | none | none | none | none | none |
| H1-CENTRING | none | none | none | none | none | none | none |
| H2-ANGLE-REDUCE | none | none | none | none | none | none | none |
| H3-REVISION | none | none | none | none | none | none | none |
| H4-CHAIN | none | none | none | none | none | none | none |

No compensation was needed. The hidden map restatements preserve first-occurrence reference semantics and make V0-11 harder. The allowed-weight TS-13 redistribution keeps total P=62; measured single-reading losses are in the fix report.

## P12 r3 QC fix effects (board 078d40a)

| lever | IN-8/JD-18 R5 | DS-27 TRUTH | TS-13 KEEP | X1 KEEP |
|---|---|---|---|---|
| V0-1 | none | none | none | none |
| V0-2 | none | none | none | none |
| V0-3 | none | none | none | none |
| V0-4 | none | none | none | none |
| V0-5 | none | none | none | none |
| V0-6 | none | none | none | none |
| V0-7 | none | none | none | none |
| V0-8 | none | none | none | none |
| V0-9 | none | none | none | none |
| V0-10 | none | none | none | none |
| V0-11 | none | none | none | none |
| V0-12 | none | none | none | none |
| H1-CENTRING | none | none | none | none |
| H2-ANGLE-REDUCE | none | none | none | none |
| H3-REVISION | none | none | none | none |
| H4-CHAIN | none | none | none | none |

No compensation needed. Only tests/judge.toml (R5 text) and solution/TRUTH.md changed; every file under tests/ except judge.toml, environment/ and solution/solve.py is sha-identical before and after, so test-channel lever losses are the r2 numbers.

## Redesign r2 levers (board 4d6dfe8, 25 Oct)

Why: P14 e30c85c found NO NATURAL TRAP (a2 wrote one program at minute 7; every H-lever named its own exception and shipped rows separated the readings). The r1 levers stay as graded noise; three new single-reading rules carry the score. Separating cases are in one hidden extract each; the shipped extract gives identical figures under every wrong reading (measured, `OUT/proto/variants.json`).

| id | rule (file:line) | reflex reading (from a2 program) | hidden cases | checks the wrong reading fails | interaction |
|---|---|---|---|---|---|
| A-H7 traverse closure | schema.md:112-129 (8b); second pass L125-126 "every micrometre of the closure magnitude is shared again, in proportion to basis by largest remainder, ties settled as above, across only the lengths whose share was the floor or more" | second pass written as a call of the whole rule, so survivors whose summed basis is at or below the closure absorb only their basis (re-enters the fits branch) | every extract plants zero, fits, prop, none_held and drop groups (drop groups chosen so both readings agree); eval alone plants one survivors_within group (South/1); generator asserts every branch (test_output.py `emit_traverse_closures`) | the 6 eval families (18) + `eval_traverse_closure_rows_hard` (5) = 23/86 | grouped by district (C), so C feeds A |
| B-H6 set-out chain | schema.md:20-26 (centring variance of a station or control mark, plus the variance of the mark it names) and :78 | own term plus the named mark's own term (a2 read one registry row, derive_report.py:313-318) | every extract: BRAVO->CM03, CIVET->CM05 (depth 1) plus unreferenced chains among CM22-CM40; challenge alone: DELTA or EAGLE->CM07->CM08, FICUS->CM10->CM11->CM12 | the 6 challenge families + `challenge_centring_chain_rows_hard` = 23/86 | independent of A and C |
| C-H3 district | schema.md:54-57 (district of the shard that holds the kept record) and :245 (district rollups) | district = line `region` (a2 derive_report.py:757-767) | shipped, challenge, eval: region equals shard district on every record; audit alone: 24 lengths + 6 angles relabelled, generator asserts >= 3 relabelled lengths in prop/drop groups with a different share | the 6 audit families + `audit_district_rows_hard` = 23/86 | moves lengths between closure groups (A) |

Measured (real tests, local): oracle 86/86; A, B, C alone 63/86 each; any two 40/86; all three 17/86; a2 program 8/86. Differential fuzz on the prototype (200 corpora each): each reflex differed on 200/200. Final-generator fuzz: STACKING_CHECK.md.

## R0 868afdf (2 Nov): primary lever Q1, carrier variation inside a named standard (kind a)

| field | value |
|---|---|
| rule | schema.md:38-39 "The CSV shard is written to RFC 4180, so any of its fields may be enclosed in double quotes; the quotes are not part of the value." (same sentence in SCHEMA_MD, tests/test_output.py:3405) |
| carrier | `sigma_kind` and `dir` cells of the hidden CSV shard (`obs_source_district_north.csv`) written as RFC 4180 quoted fields holding the same value, about one row in three each (Rng(seed ^ 24)); unquoted rows kept; shipped extract, TSV, PSV and JSONL shards unchanged |
| generator | tests/test_output.py:606-657 (`_rfc4180_quoted`, `write_csv(quote_rng=)`, `_assert_csv_quote_shape`), :1229-1236 (emit_source_shards csv branch), flags :1024, :1055, :1079 |
| oracle branch | solution/solve.py:76-80 (csv.DictReader after `#` lines), :250 (`dir`), :262 (`sigma_kind`) |
| program branch (paid) | run_1 artifacts derive_report.py:86 (`line.split(delim)`, quotes kept), :320-322 (`dir` "R" test), :328-332 (`sigma_kind` "stddev" test) |
| verifier reader | tests/test_output.py csv.DictReader in `read_delimited` (reference solve, unchanged) |
| witness | WORK/r0_lever/witness/data_sk (shipped extract, north.csv line 7 OB00001 `"stddev"`): oracle outputs identical to plain; paid residuals.csv OB00001 -17025 vs oracle -16912 |
| tests graded | 18 whole-document families (6 x challenge/eval/audit, w3) + 3 hard row checks (w5) = 69 of 86 positive |
| paid program | 7/76 hidden + 10 shipped = 17/86 (exit 0, silent WRONG), r0-2017/m/plain.json |
| lever share | 69/86 = 80.2% (go bar 40%) |
| reference | verifier reference digests old == new on all four seeds (r0-2017/verify_build.json); seconds 1.29-2.06 per extract |

Kill table on the built bundle (hidden points of 76; shipped 10 unaffected): paid 7, paid first write 7, oracle all-but-one 7, a2_r2 7, wrong_centring_angles 7, wrong_first_seen 4, wrong_ignore_mount 7, wrong_last_occurrence 6, wrong_no_centring 7, wrong_no_reduce 7; lever-aware paid (csv.reader) 76 (recorded only); oracle 76.
