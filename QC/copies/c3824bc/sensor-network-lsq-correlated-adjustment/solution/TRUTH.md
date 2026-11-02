# TRUTH.md - sensor-network-lsq-correlated-adjustment

## Defect

There is no broken program to repair. `/app/data` holds a 56-file adjustment
extract whose earlier run formed weights from shard-unit sigmas
(`observation_weight_manifest.csv:naive_weight`). The agent writes
`/app/out/derive_report.py`, which reads any extract in this format and writes
the 31 reports listed in the instruction, and runs it on the shipped extract.
`schema.md` is the single authority; every graded rule is written there, and
the per-file facts it refers to (shard declaration tokens, station mounts,
workbook control values, acceptance rows, frame and campaign maps) sit in the
files it names.

Rules that decide the figures, in reading order (focal: the rules the
earlier run broke and the round's levers; trap: per-file conventions; drift:
control values that move between extracts):

1. (trap) Shard declarations: `revision`, `length_unit`, `angle_unit`,
   `sigma_stored_as`, `sign_flip_rev`, `azimuth_wrap`, `transpose_ids` from each
   shard's header (the first line of the JSON-lines shard).
2. (focal) Duplicate records (schema section 2): an observation can be carried by two
   shards. Ids are compared after the epoch-2 un-transposition of section 7. The
   record from the shard with the higher `revision` is the observation; the
   other is superseded, not counted, and listed in
   `provenance_summary.json:superseded_records`. The shipped extract carries six
   such pairs; the first-listed shard is the right one for some and wrong for
   others, so neither "first seen" nor "last seen" reproduces the set.
3. (trap) Units from authoritative `reference_unit_registry.csv` rows only.
4. (focal) Variance (schema section 4): sigma kind per shard, base-unit variance; for a
   length observation, every station with a non-zero partial whose
   `station_registry.csv` row (first active row) has `mount=tripod` adds
   `(centring_mm/1000)^2` m^2. Angles add nothing (the rule names length
   observations only). Pillar rows and abandoned rows add nothing. The resulting
   `variance_base` feeds the base weight, the session covariance block and the
   blunder test.
5. (trap) Sign (`dir=R`), azimuth wrap, epoch-2 id transposition.
6. (focal) Misclosure (schema section 8): observed minus computed; for angles the
   difference is reduced modulo 400 into `(-200, 200]` gon. Plain subtraction
   agrees on every angle except the rows whose observed and computed values sit
   on opposite sides of the 0/400 boundary (shipped OB00213, OB00500).
7. (drift) Control values `u`, `k`, `blunder_crit`, origin from the workbook `datum`
   sheet; IRLS passes and quantization from `iteration_policy.yaml`;
   authoritative correlated sessions from `session_correlation.csv`.
8. (focal) Exact WLS in ascending obs_id, IRLS from base weights each pass (session
   members exempt), stage-1 blunder removal by `v^2 * p_base > blunder_crit^2`,
   stage-2 re-solve, datum shift to the origin station, global model test with
   the acceptance row of `dof = n - u` (centres are per row, not a formula).

## Load-bearing work

- Rules 2, 4 and 6 each change vTPv, every unknown and every residual on the
  shipped extract and on all three hidden extracts; rule 6 also changes the
  blunder set. Missing any one fails all 18 chain checks.
- The chain dedupe -> variance -> IRLS -> blunders -> n -> dof -> acceptance
  row -> verdict is graded as whole documents on three regenerated extracts.

## Final state (shipped extract)

`verdict=REJECT_LOW dof=1019 u=3 n=1022 blunders_removed=18 datum_origin=CIVET sigma0_sq=0.9979587276 downweighted=3`

- vTPv 1016.9199434352; acceptance row 1019 is [1065.010807, 1066.010807].
- Removed blunders OB00065, OB00130, OB00195, OB00260, OB00325, OB00390,
  OB00455, OB00520, OB00546, OB00585, OB00650, OB00715, OB00780, OB00845,
  OB00910, OB00975, OB01001, OB01040. Downweighted OB00637, OB00728, OB00819.
- Superseded records OB00095, OB00239, OB00265, OB00380, OB00509, OB00653.
- `residual_summary.json`: n 1022, sum_signed_micrometres -413109,
  max_abs_residual_micrometres 59094 at OB00728.
- Normal-matrix trace 14548610.757228.
- Unknowns (micrometres, datum-shifted): ALPHA 4336 / -3102, BRAVO 6103 /
  -6275, CIVET 0 / 0, DELTA 7340 / -7407, EAGLE 3619 / 2462, FICUS 5012 /
  -9313.

Single wrong readings on the shipped extract (none lands in its acceptance
band, so the shipped verdict confirms nothing):

| wrong reading | vTPv | sigma0^2 | sum signed | trace |
|---|---|---|---|---|
| no centring term | 1097.7210980823 | 1.0772532857 | -404777 | 17315630.343532 |
| centring regardless of mount | 1013.7925564320 | 0.9948896530 | -411485 | 14429707.315878 |
| centring on angles too | 900.5200317614 | 0.8828627762 | -417141 | 14524626.565722 |
| plain angle subtraction | 1014.4536731538 | 0.9974962371 | -412082 | 14548215.597096 |
| first-seen duplicate | 1026.9930417450 | 1.0078440056 | -426700 | 14533081.207813 |

## Verification

Tests channel, `tests/test_output.py` (positive weight 62):

- `artifact_set_exists_and_parses` (1): the shipped `/app/out` reports exist
  and parse. Only shipped-data check (1.6%).
- For each hidden extract (challenge, eval, audit) the grader regenerates the
  extract, runs the delivered program on it as `nobody` from a 0644 copy, and
  compares whole documents with the reference solve: `model_test_document` (3),
  `unknowns_documents` (3), `residual_documents` (3), `observation_sets` (3),
  `rollup_documents` (3), `summary_reports` (3). 54 of 62.
- Isolated checks across the hidden extracts: `control_values_on_hidden_extracts`
  (3), `superseded_records_on_hidden_extracts` (3),
  `canonical_serialization_on_hidden_extracts` (1). 7 of 62 (11.3%).
- Negatives: `negative_hardcoded_sample_answers` (-5),
  `negative_external_dependency` (-3); both stand down unless the program ran
  cleanly on a hidden extract.

Hidden extracts (reference): challenge n 1021, dof 1017, 19 removed, 4
downweighted, REJECT_HIGH, 8 superseded, straddles OB00189, OB00465, OB00713;
eval n 1022, dof 1019, 18 removed, 10 downweighted, REJECT_LOW, 7 superseded,
straddles OB00281, OB00628; audit n 1024, dof 1021, 16 removed, 8
downweighted, REJECT_HIGH, 9 superseded, straddle OB00373. They also vary the
control values, datum components, shard declarations and revisions, station
mounts, IRLS policy, acceptance centres and frame and campaign maps.

Judge channel (`tests/judge.toml`, positive weight 15): the four shipped
figures the instruction asks for in the final reply (vTPv, variance of unit
weight, signed residual sum, normal-matrix trace), each needing the full chain;
one code-quality criterion; negatives for figures disagreeing with the written
artifacts, for claiming an unrun check, and for a program that opens paths
outside its two directories.

## Root cause

The earlier run weighted observations by `1/sigma^2` in shard units. A correct
derivation must also merge duplicate shard records by revision, add the
tripod centring variance to length observations, and reduce angle misclosures
across the 0/400 boundary before the robust two-stage adjustment.

## Solution shape

1. Read every shard's declarations; un-transpose ids; keep the higher-revision
   record per observation and list the superseded ones.
2. Convert units, signs, wraps; add centring variance to length observations
   from active tripod mounts; reduce angle misclosures into (-200, 200].
3. Read workbook controls, iteration policy, authoritative sessions.
4. Exact WLS with quantized diagonal and block weights, IRLS, stage-1 blunder
   removal, stage-2 re-solve, datum shift, model test from the acceptance row.
5. Write the 31 reports (sorted-key JSON, trailing newline, micrometre
   integers).

## Ordered plan

1. Read `schema.md` end to end; inspect shard headers, the station register and
   the workbook.
2. Implement readers, dedupe, conversions and the variance rule.
3. Implement the exact solve, IRLS, sessions, blunder removal and model test.
4. Write the reports and run on the shipped extract; test on an edited copy.

## Pitfalls

- Taking the first (or last) copy of a duplicated observation.
- Adding centring to angles, to pillar mounts, or ignoring it.
- Subtracting angles without reduction, which turns a boundary row into a
  ~400 gon misclosure and an extra blunder.
- Using `default_tuning_k` from `iteration_policy.yaml` instead of the workbook.
- Hard-coding the shipped conventions or control values.

## Provenance

```yaml
instance_id: sensor-network-lsq-correlated-adjustment
uuid: 43f71cb2-f550-59c1-b15b-b31fd7b91194
task_name: terminal-bench/sensor-network-lsq-correlated-adjustment
solve_py_sha256: 19e506cd7f6d43ca4bc6f2b4826c4402c2466184df8b1581dc814a8d67f054c0
language: python
```
