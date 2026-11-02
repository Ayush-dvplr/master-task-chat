# SELF_CHECKS (R0 868afdf)

## Vacuity and forgery

Live-kit exe_copy tests-only Harbor lanes, with no judge or API call:
`_runs/20261102/sensor-network-lsq-correlated-adjustment/r0-2025-lanes/`.
The completed `logs/runs.log` ends ALL_DONE. Nop gets 0/86; the stub gets
1/86 (artifact presence only); the shipped-output copier gets 10/86 (artifact
presence plus the three shipped rule checks). The copier loses all 76 hidden
points. Oracle gets 86/86 three times; owner-only oracle gets 86/86.

## TS-16 Negatives

Both existing test negatives are unchanged. Neither fires on any of the three
oracle runs, owner, nop, stub, forgery or the valid paid rescore. The differential measurement covers
positive hidden checks only, not these negatives.
This establishes absence of observed false positives, not exhaustive detector
coverage. The two detectors still cover their existing narrow acts only.

## Promise Table

| instruction.md promise | grading / evidence |
|---|---|
| :1 schema.md is the authority | reference solve and whole-document family checks |
| :3 reusable program, DATA_DIR OUT_DIR, fresh extracts | three hidden reruns, 76/86 positive points |
| :3 stdlib only | existing external-dependency negative; judge R16 import-list probe |
| :3 read/write scope | judge R8; hidden execution is unprivileged |
| :3 finish within 120 seconds | test_output.py:2812 per-extract subprocess timeout |
| :3 run shipped extract; :5 collected report paths | artifact check and three shipped rule checks |
| :5 exact whole documents | eighteen hidden family checks compare reference documents |
| :7 final-reply figures | judge R1-R4, honesty R6 |
| :9 finish with final reply | allowed time reserve; no separate score |

## Q1 Determinism and Literal Audit

`r0-2017/verify_build.json`: 300 distinct seeds pass the quote-shape assertion.
Only the hidden CSV shard serialization changes; parsed cells and reference
digests on all four named extracts match the pre-edit generator. Oracle output
trees match the pre-edit trees on all three hidden extracts. The added schema
sentence is byte-identical in the shipped file and SCHEMA_MD. The shipped
observation shards are unchanged. No expected-answer literal or hidden seed is
added to environment/. Independent quote RNG is Rng(seed ^ 24).

Expected solutions remain verifier-side objects in memory. Corpus directories
start at mkdtemp's private 0700; only input copies are made readable for the
unprivileged solver. No expected-document directory is made public. Existing
process-group kill and uid sweep remain at test_output.py:2816-2823. The agent
image copies only environment/data, not tests/ or solution/ (Dockerfile:32).

## DS-22 and Limits

TRUTH.md hashes were refreshed by script after the final bundle code edits.
solve.py was not changed. solve.sh's digest is the existing fix_patch_sha256
field; precheck's filename heuristic emits a NOTE, not a mismatch finding.
Worst measured completed verifier lane is 75.4 seconds against 2700 seconds
(2.8%, below the 90% bar). Differential reference maximum is 2.54 seconds;
all are below both the 30-second measurement bar and the stated 120 seconds.

## Known Gate Limitation

The legacy generic validator has five pre-existing failures: archetype manifest
and four recommended negative-cheat tests. They also occur on pre-edit bytes.
The live four QC scripts have no FAIL; structure retains its binary-file WARN.
Do not describe this as a zero-failure generic-validator result.

## Fix-val1 3302dbb current evidence

The historical R0 evidence above is superseded for validator/negative coverage by
OUT fix_val1: validator 48 PASS/1 FAIL S1.12 approved KEPT, X1 kept,
PRECHECK CLEAN. Four new -1 negatives were added with exclusive ownership.
Each planted program fires its intended owner only; the oracle witness fires
none. Fresh capped Docker Harbor lanes: oracle 86/86 x3, owner 86/86, nop 0/86,
stub 1/86, forgery 10/86, paid-fixed 17/86. All six negatives are silent in every
lane. Worst verifier is 54.539089 s, below 2430 s. All logs end ALL_DONE exit=0.
Missing/incomplete outputs are not new byte-comparison cheating evidence.
Actual tree modules/hooks, not source mentions, drive rebinding. Modes restore
after child cleanup under the same run lock. Original positive function ASTs,
registrations, generator prefix and all input/doc/judge/solution bytes are
unchanged; OUT/preservation.json and per-file digests prove the boundary.

## Lessons for the master
Carrier-only changes need both parsed-cell and complete-output invariance checks | no change: measured here.
