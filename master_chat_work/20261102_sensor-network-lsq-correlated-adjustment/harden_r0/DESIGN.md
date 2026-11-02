# DESIGN 868afdf: sensor-network-lsq-correlated-adjustment, R0 lever

Bundle tree 376ab407134e (= Tasks_INPUT), kit HEAD 5574d77e. No BUNDLE edits in Phase 1.
Measurement harness: WORK/r0_lever/measure.py (imports tests/test_output.py, patches its
CSV writer `write_csv` test_output.py:606-617, emits challenge/eval/audit with the real seeds,
runs the real hidden test functions). Runs (Docker, --memory 4g --cpus 2, dockfree START=yes):
_runs/20261102/sensor-network-lsq-correlated-adjustment/r0-1844, r0-1852, r0-1856, r0-1858 (all ALL_DONE).

## 1. Measured against the master-note-1 go bar

Literal carrier (sigma_kind quoted as `"stddev"` in every third data row, CSV only, note 2):
paid 53/76 hidden, loses 23/86 = 26.7% -> misses the 35/86 bar. Reason (generator,
test_output.py:979-987, 1011-1016): in challenge and eval the CSV shard (north) stores
`variance`, so a quoted `"variance"` still falls into the paid program's else branch and is
right; only audit's CSV holds `stddev`. The stddev TSV shard would need a TSV quoting rule
(sk_csv_tsv: loses 69/86), which note 2 rules out unless a doc names one.

Redesign (the one allowed): same kind 1(a), same shard, same RFC 4180 form, two graded text
fields: `sigma_kind` and `dir` written as quoted fields holding the same value in some rows of
the hidden CSV shard, unquoted rows kept (variant `skdir_csv`).

| bar | measured (skdir_csv) | verdict |
|---|---|---|
| reference documents byte-identical plain vs quoted | verifier ref digest identical on challenge 1468f572e0fc, eval 204d4dbb91eb, audit ca86804a08da; solve.py output tree identical (209857db2c92, 9c9be5e879a5, d88be5170829) | GO |
| paid WRONG on whole-document families of both extracts, >= 40% positive | paid 7/76 hidden: all 18 families (challenge, eval, audit x6, w3) + 3 hard rows (w5) WRONG, exit 0 (silent); keeps control 3, superseded 3, canonical 1. Lost 69/86 = 80.2% | GO |
| reference <= 30 s per extract (stated 120 s, instruction.md:3) | verifier reference 0.93-1.43 s; solve.py 1.07-2.22 s | GO |

Other measured variants (recorded): sk_csv_swap (generator swaps north/south sigma kinds, then
quote) loses 76/86 but changes hidden data, so old checks would not stay byte-identical;
rng_csv (any cell, p=0.2) and rngtext_csv (text cells, p=0.2) loses 76/86 by CRASH
(paid.py:315 KeyError ('ft_us','angle') when a quoted `"length"` falls to angle); ref and
oracle digests identical for both. Chosen: skdir_csv (silent WRONG, data values unchanged,
no crash that a log could reveal).

## 2. New fact and its doc

Only one new fact: the CSV shard is RFC 4180, so a field may be quoted. Today schema.md has no
quoting sentence (schema.md:28-38 names the shard and its fields; sigma rule schema.md:70-76;
dir rule schema.md:83-86). Doc sentence to add after schema.md:38 ("...none of the other files
is a source of observation values.") and in the generator copy SCHEMA_MD
(test_output.py:3312, after line 3348) so schema.md stays byte-identical to generator output:

> The CSV shard is written to RFC 4180, so any of its fields may be enclosed in double quotes; the quotes are not part of the value.

No TSV/PSV/JSONL quoting. No field or row named. Shipped extract unchanged (stays unquoted);
quoting only in hidden extracts, per-seed flag in CORPUS_VARIANTS, own RNG (random.Random(seed
^ const)) choosing rows, so sample/hidden values and all old reference digests are unchanged.

instruction.md (R0 3, R0 7) lacks both sentences; add:
- "Each output document is graded whole, and only an exact match counts." (G1/G5)
- "Leave enough of that time to finish and write your final reply." (after "You have 7200 seconds.")

## 3. Named difference (R0 4)

Witness WORK/r0_lever/witness/data_sk/: shipped data with only obs_source_district_north.csv
line 7 (OB00001) `,stddev,` -> `,"stddev",`. solve.py plain vs witness: diff -rq empty. Paid:
residuals.csv, unknowns.csv, rollups, status.txt differ; residuals.csv OB00001 oracle
`OB00001,length,-16912,0` vs paid `OB00001,length,-17025,0` (witness_run.log).
- Oracle: solve.py:76-80 (csv.DictReader strips quotes) -> solve.py:262 (`== "stddev"`), dir solve.py:250.
- Paid: P:86 `line.split(delim)` keeps quotes -> P:328-332 takes variance branch; dir P:320 (`"R"` != R).
- Verifier: test_output.py:2162-2176 (csv.DictReader, row["sigma_kind"], row["dir"] at 2174).

## 4. Kill table (hidden points of 76; shipped 10 unaffected; plain / skdir_csv)

| program | plain | skdir_csv | lever points kept (of 69) | state | seconds |
|---|---|---|---|---|---|
| paid (run_1 artifact, sha 68c82e495ad5) | 76 | 7 | 0 | WRONG x21 | 0.9-2.3 |
| paid first write (trajectory step 23) | 76 | 7 | 0 | WRONG x21 | ~1-2 |
| oracle all-but-one (solve.py:80 naive split) | 76 | 7 | 0 | WRONG x21 | ~1-2 |
| a2_r2 (blind, 25 Oct) | 7 | 7 | 0 | WRONG (pre-existing) | 1.2-1.9 |
| wrong_centring_angles / ignore_mount / no_centring / no_reduce | 7 | 7 | 0 | WRONG (pre-existing) | 1.2-2.1 |
| wrong_last_occurrence | 6 | 6 | 0 | WRONG (pre-existing) | 1.5-2.3 |
| wrong_first_seen | 4 | 4 | 0 | WRONG (pre-existing) | 1.3-1.7 |
| lever-aware (paid + csv.reader) (recorded only) | 76 | 76 | 69 | EXACT | 1.0-1.4 |
| oracle solve.py | 76 | 76 | 69 | EXACT | 1.07-2.22 |

No program on file keeps >= 60% of lever points except the lever-aware row: core holds.

## 5. Judge (tests/judge.toml; master note 5)

Today: R1-R4 final-reply figures, R5 code quality, R9-R11 recompute probes (w3 each, positive
24), negatives R6 -5, R7 -5, R8 -3. Paid run_1 got 18/24 = 75 (R10, R11 failed). The lever does
not touch shipped data, so paid keeps R1-R4: rubric would stay above 40. Add five probes the
paid trajectory never did (44 steps listed with python; one act each, w3, type process,
trajectory; solve.sh prints `check R12 ok` ... `check R16 ok` from a real act):
- R12 runs derive_report.py on a copy of the shipped extract in which at least one field of a
  CSV source is written as a quoted field, and compares with the unmodified outputs.
- R13 parses a CSV source shard with Python's csv module (or another RFC 4180 reader) and
  compares the rows with those derive_report.py reads.
- R14 runs derive_report.py on a copy of the shipped extract with observation rows removed or
  values changed, and inspects the result.
- R15 times derive_report.py on an extract larger than the shipped one.
- R16 runs a command listing the modules derive_report.py imports (stdlib check).
Plus R17 grader-read negative -5: reads files under /tests/ or /logs/verifier (anchored).
Probes R9-R16 = 8 (band 8-16); positive 39; probe share 24/39 = 61.5% (band 55-70%).
JD-7: each probe names one act checkable in the trajectory; no figures added (J1).

Paid trajectory grade on new judge (R1-R4 kept, R9 pass, R10/R11/R12-R16 not done):
low 15/39 = 38.5 (R5 lost), mid 18/39 = 46.2, high 24/39 = 61.5 (R10/R11 credited).

## 6. Prediction

| | tests | judge | final |
|---|---|---|---|
| paid program, new tests | 17/86 = 19.8 | | |
| low / mid / high | 19.8 | 38.5 / 46.2 / 61.5 | 29.1 / 33.0 / 40.7 |
Gate tests<85, rubric<85, final<40: met at low and mid; R5 bar (mid final <= 35): 33.0.
Lever share 69/86 = 80.2% (>= 40%).

## 7. QC rows

- IN-15 (rule stated): the RFC 4180 sentence is in schema.md section 2, the doc that governs the
  shards; the variance and dir rules are already stated (schema.md:70-76, 83-86).
- IN-16 (no graded ambiguity): "the quotes are not part of the value" fixes the reading; RFC
  4180 is one standard and the Python csv module (stdlib, allowed) implements it.
- IN-17 (no pre-announced discovery): sentence says "may"; names no field or row; shipped
  sample unquoted; hidden-extract rerun already promised (instruction.md "other extracts in the
  same format").
- DS-21 (solvable): oracle and verifier reader both use csv.DictReader; 76/76 on all variants.
- TS-11 (deterministic): rows chosen by own RNG seeded per extract; reference digest fixed;
  generator will assert quoted-row count > 0 and plain-row count > 0 over 300 seeds.
- TS-19 (promise graded): the doc sentence is graded by 21 hidden checks; no ungraded promise.
- TS-26 (no double payment): no new test added; the 18 family checks and 3 hard rows were
  already per-extract whole documents; R0 requires the lever to cost >= 40%. R12/R13 are acts,
  not results.
- AL-27: add one RULE_COVERAGE row (CSV RFC 4180 -> schema.md new line -> solve.py:76-80 ->
  test_output.py:2162-2176 -> hidden families).
- CL-4: whole-document grading defended by the G1/G5 sentence (to add) and
  Final_checklist.md:491.

## 8. Live kit today (master note 4) on current bundle

instruction_qc PASS 5/0/0; tests_qc PASS 37; judge_qc PASS 19; structure_qc WARN X1 (5 binary
decoys skipped, tasker approval; unchanged). precheck.sh PRECHECK CLEAN with NOTEs to fix in
build: DS-22 TRUTH.md:173 fix_patch_sha256 names no file; EVIDENCE-MAP missing
WORK/EVIDENCE_MAP.md; SELF-CHECKS missing WORK/SELF_CHECKS.md; AL-27 33 rows (add 1); J1 4
figure criteria (R1-R4 final-reply figures, kept). No FAIL.

## 9. Build plan after go

tests/test_output.py: CORPUS_VARIANTS flag `csv_quote` for challenge/eval/audit, write_csv
quotes sigma_kind/dir in RNG-chosen rows when set; SCHEMA_MD sentence; schema.md copy;
digest of old hidden references before/after (must match); 300-seed shape assert.
judge.toml R12-R17; solve.sh probe witnesses; instruction.md two sentences; WORK LEVERS,
QC_DEFENCE, EVIDENCE_MAP, SELF_CHECKS, RULE_COVERAGE; TRUTH.md last; xref 0; gates per Phase 3.

DESIGN READY: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_sensor-network-lsq-correlated-adjustment/harden_r0/DESIGN.md
