# TRIP e2bfbf0 slipway-overhaul-replan-repair, run a3 on tree 62dbcde0c809

Run a3: tests 72.06 (49/68), rubric 82.98 (78/94), final 77.52, 96 agent steps, 23 min.
Method: a3 patched_engine.zip unzipped to WORK/a3_program; WORK/proto/diag.py (Docker, python:3.12-slim,
8g/4 cpus) builds `_corpus(seed)` and `_reference(seed)` from tests/test_output.py and runs the a3 engine
the way `_drive` does. Diffs in WORK/proto/diag_a3/*.diff. The repaired oracle engine (solve.py) was
built the same way into WORK/oracle_program and diffed against the a3 sources.

## 1. Why a3 lost each of the 5 tests (all WRONG, 19 pts)

| test (w) | documents that differ | cause | doc line | verdict |
|---|---|---|---|---|
| shipped_graph_layer_exact (3) | SAMPLE 02, 19 | a3 lists EDG-4261, EDG-4268, EDG-4275 (journal rows naming JOB-1305/1306/1307, the JOB-CYCLE jobs) as `rejected EDG-UNKNOWNJOB` in 02 and as `edge,...,EDG-UNKNOWNJOB` rows in 19; the reference drops the three rows from both documents | spec_stage_p02_precedence_graph.md:20-23 "the lodgements that named it are then rejected under `EDG-UNKNOWNJOB` by the test above"; p02:5-6 a rejected row appears once in the rejection register | a3 follows the doc; the reference contradicts it (QC risk Q1) |
| shipped_audit_documents_exact (3) | SAMPLE 23, 24, 25 | knock-on of Q1: `edges rejected 181` vs 178 in 23, `edges_rejected` 181 vs 178 in 25, manifest digests of 02/19/23/25 in 24 | same | follows from Q1 |
| package_eval_state_exact (5) | EVAL 18 (and 02,19,23,24,25 from Q1) | top-level `weighted_resource` of 18_final_selection.json: reference 4331.283333333334 (sum of the per-precinct 12 dp strings, test_output.py `_selection_body` l3035-3060), a3 4331.283333333333 (exact rational sum, then rounded) | output_schema_reference.md:6 "Every ratio carries exactly twelve decimal places"; spec_stage_p10_objective.md:24-26 exact rational published to 12 dp; p11:15 "the round is their sum"; no doc says the round figure is a sum of rounded figures | doc silent / favours a3 (QC risk Q2) |
| package_challenge_state_exact (5) | CHALLENGE 11, 18 | Q2 on 11_baseline_selection.json (3225.650793650793 vs ...794) and 18 | same | Q2 |
| package_probe_publication_exact (3) | PROBE 02, 19, 23, 24, 25 | Q1 | p02:20-23 | Q1 |

Timings (Docker, per corpus): corpus build 1.2-5.6 s, reference 0.05-0.08 s, a3 engine 0.22-0.24 s.
If Q1 and Q2 are settled in the doc's favour, a3 scores 68/68 = tests 100.

## 2. Where a3 deviates from the oracle engine (diff -r oracle_program/src a3_program/src)
All deviations generalise the shipped engine; none is reached by the generator except Q1/Q2:
cells.py cycle lodgements re-sifted (Q1); publish.py exact top-level sum (Q2); mutate.py restatement
classified by implied kind, reversal stores the exact inverse of edge_lodged/edge_withdrawn, SELF tested
before UNKNOWNJOB on lodged edges (p02 order), carryover on an unknown precinct rejected, NOTARGET for
unknown job/group/rule/capacity/class, `inert` whenever the seed set is empty; normalise.py memo sitting
must say IN FORCE FOR ROUND <index>, class list from priority_class_vocabulary.csv rows in force,
`aliases_active` = active crosswalk row count (output_schema_reference.md:12).

## 3. Judge: why a3 earned each criterion (trajectory step numbers)

| crit (w) | earned | how a3 showed it | cheap or real |
|---|---|---|---|
| R1 repaired in place (5) | 1 | step 16 unzip project.zip into /app/work, 47-66 str_replace edits, 94 zip | cheap: every repair run does this |
| R2 package_expectations (3) | 1 | step 7 cat package_expectations.toml | cheap: one read |
| R3 quiet branch (3) | 1 | steps 83-88 reversal/restatement edits, final message | cheap: read of code |
| R4 determinism (3) | 1 | step 75 rerun + diff -r IDENTICAL, 89 SAME | real act, but Opus default habit |
| R5 path independence (3) | 1 | step 75 cp -r /app/data /tmp/papers_other, diff PORTABLE; 96 deep out dir | real act, Opus default habit |
| R6-R9, R11, R13-R19 fault repairs (5,5,5,5,5,3,3,3,3,3,3,3) | 1 each | edits steps 47-66, 83-88; judge read the diffs | cheap: restate the defects the tests and 11 negative detectors already grade (JD-8 overlap) |
| R10 live pool weights + tie shown (5) | 0 | weights read (step 42-46) but no equal-charge tie exhibited | the extra act was missed |
| R12 register in force + drafting adds (5) | 0 | populations compared (step 25-28), jobs not named | missed reporting act |
| R20 stdlib binaries (3) | 1 | steps 9-15 zipfile/ElementTree/zlib | cheap: only way to read them |
| R21 set aside by reason (3) | 1 | final message step 98 | cheap: program output |
| R22 live sheet + key cell (3) | 1 | step 98 `Schedule R`, `R40-PEN` | cheap: printed figure |
| R23 amendments reaching no cell (3) | 0 | AMD-101 named, no contrast with AMD-104 | missed |
| R24 pool to last unit (3) | 1 | step 97 grep 20_resource_usage, step 98 PCT-ELS 995/995 | cheap: program output |
| R25 faults beside stage (3) | 1 | step 98 staged list | cheap |
| R26 counters vs withdrawn (3) | 0 | opened withdrawn_counter_publication.csv (step 33), no comparison published | missed |
| R27, R28 negatives (-3,-3) | 0 | not fired; data checksum verified steps 75, 96 | - |

Earned 78 of 94: 61 of the 78 are cheap (fault restatements 47, delivery/read/report 14); the real acts
earned were determinism (R4) and relocation (R5). Acts a3 did on its own that a probe band must not pay
for again: ran the shipped engine before its first edit (step 36 vs first edit 47), an independent
recompute of every precinct selection (/tmp/check.py steps 78-80), rerun + diff (75, 89), relocated
copy (75), deep output dir (96), data checksums (75, 96), suite run (81, 89, 95).
Acts a3 never did: ran the engine on an altered copy of the papers (no quiet branch was ever fired),
on a missing or malformed paper, or exhibited a tie or a uniqueness witness.
FALSE_CLAIM step 98: "all 16 tests still pass" refers to the shipped suite; true for that suite.

## 4. Levers that exist today
Held-out corpora run on the delivered engine: package_eval_state (5), package_eval_cascade (5),
package_challenge_state (5), package_challenge_cascade (3), package_probe_publication (3, data-first
argument order) = 21 of 68 = 31%. a3 passed both cascade checks and lost the other three only by Q1/Q2.
The generator (mint l823, `_amendments` l1398) is fixed-structure: 6 precinct shapes, fixed edges,
groups, rules and the same 19 amendments on every seed; seeds move only numbers. Hidden rounds therefore
fire no branch the shipped round does not fire, and a3 matches the reference on every one of them apart
from Q1/Q2. Measured: 20 fresh seeds, 13 abort inside write_corpus (SystemExit "no precinct was seated
on a level charge"), 7 build; on all 7 a3 differs only in 02/19/23/24/25 (Q1, every seed) and in the
top-level `weighted_resource` of 11 (4 seeds) or 18 (3 seeds) (Q2). Log WORK/proto/diag_a3_seeds.log.
