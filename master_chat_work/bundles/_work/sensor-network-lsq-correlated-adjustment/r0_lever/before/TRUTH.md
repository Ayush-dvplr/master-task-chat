# TRUTH.md - sensor-network-lsq-correlated-adjustment

## Defect

There is no broken program to repair. `/app/data` holds a 58-file adjustment
extract whose earlier run formed weights from shard-unit sigmas
(`observation_weight_manifest.csv:naive_weight`). The agent writes
`/app/out/derive_report.py`, which reads any extract in this format and writes
the 31 reports listed in the instruction, and runs it on the shipped extract.
`schema.md` is the single authority; every rule behind a graded figure is
written there, and the per-file facts it refers to (shard declaration tokens,
station mounts and set-out links, control marks, traverse closures, workbook
control values, acceptance rows, frame and campaign maps) sit in the files it
names.

Rules that decide the figures, in reading order (focal: rules that change every graded figure; trap: per-file conventions; drift: control values that move between extracts):

1. (trap) Shard declarations: `revision`, `length_unit`, `angle_unit`,
   `sigma_stored_as`, `sign_flip_rev`, `azimuth_wrap`, `transpose_ids` from each
   shard's header (the first line of the JSON-lines shard).
2. (focal) Duplicate records (schema section 2): ids are compared after the epoch-2
   un-transposition of section 7; the record from the shard with the higher
   `revision` is the observation, the other is superseded and listed in
   `provenance_summary.json:superseded_records`.
3. (focal) District (schema section 2): the district of an observation is the district
   of the shard holding its kept record. It keys the district rollups and the
   traverse closure groups. The shipped extract, challenge and eval carry a
   line `region` equal to that district on every record; audit carries 24
   lengths and 6 angles whose line `region` names another district.
4. (trap) Units from authoritative `reference_unit_registry.csv` rows only; sigma kind
   per shard; base-unit variance.
5. (focal) Centring variance (schema sections 1 and 4): a station's own tripod term
   `(centring_mm/1000)^2` (pillar adds nothing), plus, when `set_out_from` is
   filled, the centring variance of the named control mark, which itself
   follows its own `set_out_from`. Added for every station with a non-zero
   partial of a length observation. Shipped, eval and audit links are one mark
   deep (BRAVO -> CM03, CIVET -> CM05); challenge adds DELTA or EAGLE -> CM07
   -> CM08 and FICUS -> CM10 -> CM11 -> CM12.
6. (trap) Sign (`dir=R`), azimuth wrap, misclosure reduced into `(-200, 200]` gon.
7. (focal) Traverse closure (schema section 8b): per district and epoch, the closure
   magnitude is absorbed by the group's lengths in proportion to basis (whole
   metres of `computed_nominal`) by largest remainder, ties to the lower
   `obs_id`; when the summed basis fits, each takes its basis; lengths whose
   share falls below the floor take nothing and the whole closure magnitude is
   shared again over the lengths that held the floor, with no fits test on that
   second sharing. The absorbed amount, with the closure's sign, is subtracted
   from `l` before the solve. The shipped extract, challenge and audit plant
   the zero, fits, proportional, none-held and drop branches; only eval has a
   group whose surviving lengths hold no more basis than the closure.
8. (drift) Control values `u`, `k`, `blunder_crit`, origin from the workbook `datum`
   sheet; IRLS passes and quantization from `iteration_policy.yaml`;
   authoritative correlated sessions from `session_correlation.csv`.
9. (focal) Exact WLS in ascending obs_id, IRLS from base weights each pass (session
   members exempt), stage-1 blunder removal by `v^2 * p_base > blunder_crit^2`,
   stage-2 re-solve, datum shift to the origin station, global model test with
   the acceptance row of `dof = n - u`.

## Load-bearing work

- Rules 3, 5 and 7 each change every residual, unknown and summary figure of
  the hidden extract that plants their separating case; the shipped extract
  gives the same figures under either reading of each of them.
- The chain dedupe -> district -> variance -> closure -> IRLS -> blunders ->
  n -> dof -> acceptance row -> verdict is graded as whole documents on three
  regenerated extracts, plus owned-row checks per rule.

## Final state (shipped extract)

`verdict=REJECT_LOW dof=1019 u=3 n=1022 blunders_removed=18 datum_origin=CIVET sigma0_sq=0.9812789020 downweighted=3`

- vTPv 999.9232011672; acceptance row 1019 is [1065.010807, 1066.010807].
- Removed blunders OB00065, OB00130, OB00195, OB00260, OB00325, OB00390,
  OB00455, OB00520, OB00546, OB00585, OB00650, OB00715, OB00780, OB00845,
  OB00910, OB00975, OB01001, OB01040. Downweighted OB00637, OB00728, OB00819.
- Superseded records OB00095, OB00239, OB00265, OB00380, OB00509, OB00653.
- `residual_summary.json`: n 1022, sum_signed_micrometres -444581,
  max_abs_residual_micrometres 59361 at OB00728.
- Normal-matrix trace 14059330.440663.
- Unknowns (micrometres, datum-shifted): ALPHA 4341 / -3180, BRAVO 6104 /
  -6361, CIVET 0 / 0, DELTA 7369 / -7506, EAGLE 3686 / 2304, FICUS 5012 /
  -9425.
- District observation counts North 256, South 257, West 254, East 255.

## Verification

Tests channel, `tests/test_output.py` (positive weight 86, 28 positive checks
and 2 negatives):

- `artifact_set_exists_and_parses` (1): the shipped `/app/out` reports exist
  and parse.
- For each hidden extract (challenge, eval, audit) the grader regenerates the
  extract, runs the delivered program on it as `nobody` from a 0644 copy, and
  compares whole documents with the reference solve: `model_test_document` (3),
  `unknowns_documents` (3), `residual_documents` (3), `observation_sets` (3),
  `rollup_documents` (3), `summary_reports` (3). 54 of 86.
- Isolated checks across the hidden extracts: `control_values_on_hidden_extracts`
  (3), `superseded_records_on_hidden_extracts` (3),
  `canonical_serialization_on_hidden_extracts` (1).
- Owned rows per rule, shipped run (3 each) and hidden extract (5 each):
  `traverse_closure_rows_shipped`, `eval_traverse_closure_rows_hard`;
  `centring_chain_rows_shipped`, `challenge_centring_chain_rows_hard`;
  `district_rollups_shipped`, `audit_district_rows_hard`.
- Negatives: `negative_hardcoded_sample_answers` (-5),
  `negative_external_dependency` (-3); both stand down unless the program ran
  cleanly on a hidden extract.
- Measured locally with these tests: reference 86/86; one rule read wrongly
  (closure second sharing re-entering the fits test, one-level set-out lookup,
  or line `region` as district) 63/86 each; two wrong 40/86; all three 17/86.

Hidden extracts (reference): challenge n 1022, dof 1018, 18 removed, 4
downweighted, REJECT_HIGH, 8 superseded; eval n 1022, dof 1019, 18 removed, 10
downweighted, REJECT_LOW, 7 superseded; audit n 1024, dof 1021, 16 removed, 7
downweighted, REJECT_HIGH, 9 superseded, 24 records whose line region is not
their district. They also vary the control values, datum components, shard
declarations and revisions, station mounts, IRLS policy, acceptance centres and
frame and campaign maps.

Judge channel (`tests/judge.toml`, positive weight 24): the four shipped
figures the instruction asks for in the final reply (vTPv, variance of unit
weight, signed residual sum, normal-matrix trace); one code-quality criterion
(a maintainable program judged on names, function structure and error handling); three conduct
criteria for recomputing, apart from the program, a closure absorption (R9), a
station centring variance (R10) and a district observation count (R11), which
`solve.sh` performs and prints as `check R9 ok`, `check R10 ok`, `check R11 ok`;
negatives for figures disagreeing with the written artifacts, for claiming an
unrun check, and for a program that opens paths outside its two directories.

## Root cause

The earlier run weighted observations by `1/sigma^2` in shard units. A correct
derivation must also merge duplicate shard records by revision, key districts
by the shard that holds the kept record, add the full set-out centring
variance to length observations, absorb each district and epoch's traverse
closure into its lengths, and reduce angle misclosures across the 0/400
boundary before the robust two-stage adjustment.

## Solution shape

1. Read every shard's declarations; un-transpose ids; keep the higher-revision
   record per observation, note its shard's district, list the superseded ones.
2. Convert units, signs, wraps; add centring variance through the set-out
   links; reduce angle misclosures; absorb traverse closures into `l`.
3. Read workbook controls, iteration policy, authoritative sessions.
4. Exact WLS with quantized diagonal and block weights, IRLS, stage-1 blunder
   removal, stage-2 re-solve, datum shift, model test from the acceptance row.
5. Write the 31 reports (sorted-key JSON, trailing newline, micrometre
   integers).

## Ordered plan

1. Read `schema.md` end to end; inspect shard headers, the station register,
   the control mark register, the closure register and the workbook.
2. Implement readers, dedupe, districts, conversions, centring and closures.
3. Implement the exact solve, IRLS, sessions, blunder removal and model test.
4. Write the reports and run on the shipped extract; test on an edited copy.

## Pitfalls

- Taking the first (or last) copy of a duplicated observation.
- Grouping districts or closures by the line `region` field.
- Following `set_out_from` only one mark deep.
- Re-applying the "summed basis fits" test on the second closure sharing.
- Subtracting angles without reduction.
- Using `default_tuning_k` from `iteration_policy.yaml` instead of the workbook.
- Hard-coding the shipped conventions or control values.

## Provenance

```yaml
instance_id: sensor-network-lsq-correlated-adjustment
uuid: 43f71cb2-f550-59c1-b15b-b31fd7b91194
task_name: terminal-bench/sensor-network-lsq-correlated-adjustment
fix_patch_sha256: 9c8436c2f15bfb10a688a067f91d80eedaeeba9459d02bd7b529f8aedc22aa7f
solve_py_sha256: 1b6e7e24e3afb79a853f6e8f76fb02c81cd2cf65a14401ab84e1459ebb5612cc
language: python
```
