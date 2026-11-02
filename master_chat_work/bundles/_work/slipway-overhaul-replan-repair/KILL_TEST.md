# KILL_TEST e2bfbf0 slipway-overhaul-replan-repair (Docker, 8g / 4 cpus, python:3.12-slim)

Bar for a lever: a3 program WRONG on a doc-backed behaviour through an existing generator family.
Reference cost per corpus is 0.05-0.12 s and `_corpus` 1.2-10.4 s, so no hidden-scale lever exists
(and no runtime sentence is stated for the engine: v3.5 condition 2 fails).

## Try 1: held-out seeds through write_corpus / _corpus / _reference (diag.py)
| program | corpus | seconds (corpus/ref/prog) | result | lever pts kept by a3 |
|---|---|---|---|---|
| a3 | SAMPLE | 3.82/0.06/0.23 | WRONG 02,19,23,24,25 (Q1) | n/a (disputed) |
| a3 | EVAL | 3.79/0.06/0.22 | WRONG 02,18,19,23,24,25 (Q1,Q2) | n/a |
| a3 | CHALLENGE | 5.59/0.05/0.22 | WRONG 02,11,18,19,23,24,25 (Q1,Q2) | n/a |
| a3 | PROBE | 1.15/0.08/0.24 | WRONG 02,11,18,19,23,24,25 (Q1,Q2) | n/a |
| a3 | 20 fresh seeds | 1.8-10.4/0.05-0.12/0.3-0.7 | 13 seeds abort in write_corpus (SystemExit level charge); 7 build: WRONG only Q1 (7/7) and Q2 (11 on 4, 18 on 3) | all non-disputed docs EXACT |

Q1 = cycle lodgements: p02:20-23 says they are rejected under EDG-UNKNOWNJOB; the reference drops them.
Q2 = top-level `weighted_resource` of 11/18: reference sums the rounded precinct strings, a3 rounds the
exact sum; no document says which (output_schema_reference.md:68 names the key only).
Non-disputed WRONG on a3: 0 of every document on every buildable seed. EXACT otherwise.

## Try 2: stated invocation variants (variants.py), SAMPLE and seed 3048880505978245378, uid 1000
relative paths, spaces in both paths, read-only papers, out dir holding a stale document, cwd inside
the papers, trailing slashes: a3 rc 0 on all 14 runs, documents identical to its plain run (only the
Q1 set differs from the reference). Non-disputed WRONG: 0. TIMEOUT 0. CRASH 0.

## Verdict
No reachable instance from the existing families separates a3 from the reference except Q1/Q2,
which are reference/document disputes (QC_RISKS.md), not a3 errors. Generic first-write and
all-but-one programs were not run: the a3 program already keeps every lever point, so condition
4 (a3 program <= 60 on new tests) cannot be met by any reweighting. NO CORE.
