# FIX_REPORT - sensor-network-lsq-correlated-adjustment - 3302dbb

## Outcome

DONE for this scoped fix. Added S11.2-S11.5 behavioral negatives, each -1. The validator is 48 PASS / 1 FAIL, with only the approved S1.12 manifest exception retained. X1 remains the pre-existing binary-input structure WARN. This is not a zero-failure generic-validator result, a full QC verdict, or authorization to ship. Next: master issues full QC, then freeze and one paid model run.

Untouched bundle tree: `70e94464a151`. Final BUNDLE and synced Tasks_INPUT tree: `380f417a8efd`. Exactly three bundle files changed: tests/test_output.py, tests/reward.toml, solution/TRUTH.md. All 172 fingerprinted upstream files matched before work. First session rename matched OpenCode `ses_e62bac0aaffe2wm6uvhI4GdPqD`; Codex had no match. No alternate ID was tried.

## Cause and disposition

The validator's `detect_archetype`, `validate_bundle.py:51-68`, says "The template whose declared artifacts equal the bundle's task.toml artifacts" and requires `sorted(declared) == sorted(artifacts)`. None matches Sensor's 32 outputs. At :86-87 it returns `detect_archetype(self.bundle) or "format-recovery"`; :837-840 then returns `fail("task.toml artifacts do not match the declared archetype manifest")`. The fallback also enables corpus-only checks S11.2-S11.5; strict-default validation promotes their missing-test recommendations to FAIL.

S11.2-S11.5 were fixed inside the permitted verifier files. S1.12 is KEPT, not suppressed: clearing it requires changing the output contract or harness templates, both forbidden. Authority: Ayush 2 Nov '1. b', as carried by the issued prompt. Precedent: `master_chat_work/20261102_slipway-overhaul-replan-repair/fix_ql1/FIX_REPORT.md:44`, "validator build-repair: 38 passed, 1 FAIL S1.12 pre-existing archetype manifest (noted since fix1)." See KEPT.md for both retained rows.

Untouched validator FAILs, reproduced in validator_before.txt:

```text
FAIL[§1.12] declared archetype matches its trusted manifest: task.toml artifacts do not match the declared archetype manifest
FAIL[§11.2] Filename-dependent behaviour cheat test is recommended: recommended negative-weight cheat test missing: negative_filename_dependent_behaviour
FAIL[§11.3] Runtime training-data access cheat test is recommended: recommended negative-weight cheat test missing: negative_reads_training_corpus_at_runtime
FAIL[§11.4] Nondeterministic output cheat test is recommended: recommended negative-weight cheat test missing: negative_nondeterministic_output
FAIL[§11.5] Verifier-dependency rebinding cheat test is recommended: recommended negative-weight cheat test missing: negative_rebinds_verifier_dependencies
```

## Behavioral negatives

The following references are to BUNDLE/tests/test_output.py. Weights register at :4007-4010; wrappers are :3958, :3963, :3968, :3973. Each witness is a standalone planted program under WORK/fix_val1_witnesses, run in a real capped Docker container. Full evidence: witnesses.json and scratch logs/witness.log.

| Criterion | Weight | Observed act and implementation | QC_DEFENCE anchor | Witness result |
|---|---:|---|---|---|
| negative_filename_dependent_behaviour | -1 | :3453, shared probes :3396. Same input bytes under another directory and cwd produce different complete documents after same-path repeat stability. | WORK/QC_DEFENCE.md:52 quotes instruction.md:3, "It will also be run on other extracts in the same format" and "taking every reported figure from the data". | filename_dependent_behaviour.py: only this owner fired, 2.722 s. |
| negative_reads_training_corpus_at_runtime | -1 | :3457; permission intervention :2815. Complete held-out documents change when /app/data and shipped /app/out answers are unreadable to nobody. Modes restore under the run lock after child cleanup. | WORK/QC_DEFENCE.md:53 quotes instruction.md:3, "read only from DATA_DIR and write only to OUT_DIR". | reads_training_corpus_at_runtime.py: only this owner fired, 3.264 s. |
| negative_nondeterministic_output | -1 | :3461. Complete documents change on the same input/output/cwd paths with PYTHONHASHSEED 1 versus 2. | WORK/QC_DEFENCE.md:54 quotes instruction.md:3, "taking every reported figure from the data", and :5, "only an exact match counts". | nondeterministic_output.py: only this owner fired, 2.969 s. |
| negative_rebinds_verifier_dependencies | -1 | :3465, physical tree inspection :3380. Delivered import locations carry actual stdlib-shadow modules/packages or startup hooks. No source-token, request-id or filename-literal scan. | WORK/QC_DEFENCE.md:55 quotes instruction.md:3, "It must use only the Python standard library". | rebinds_verifier_dependencies.py plus delivered sitecustomize.py: only this owner fired, 3.030 s. |

Oracle witness: no new negative fired, 8.209 s. All witness assertions passed; log ends `WITNESSES_PASS` and `ALL_DONE exit=0`. Missing or incomplete reruns are not evidence for the three byte-comparison negatives. Rebinding uses the actual delivered tree, not program text.

Ownership at :3427: existing hardcoded_sample_answers (-5) or external_dependency (-3) takes precedence; all four new checks stand down if either fires. Otherwise at most one new owner is selected: rebinding > nondeterminism > runtime dependence > filename/cwd dependence. R17 alone owns grader-file reads: no intervention reads or hides /tests or /logs/verifier, and mentioning those names cannot trigger a new negative. An outside-directory shipped-tree read may independently meet unchanged judge R8 (-3); combined with the narrower runtime -1 this is at most -4, below AL-28's -5 cap. No judge changes were authorized or made.

Reward schema caveat: the live R4 check and rewardkit model permit only `aggregation` in [scoring.test_output]. Actual -1 weights therefore register through criteria in test_output.py, the same mechanism as every existing weight; reward.toml explicitly documents all four names and weights as comments. Parsed aggregation and channel multipliers are unchanged. No unsupported config keys were introduced.

## Gates and preservation

| Gate | Measured result |
|---|---|
| xref_check | 25 entries, 0 findings, exit 0; xref.txt |
| stacking_check | exit 0; TS-26 duplicate candidates none; manual AL-28 disposition below |
| PRECHECK | exit 0; last line `PRECHECK CLEAN`; precheck.txt |
| Live structure_qc | 17 pass / 1 X1 warn / 0 fail |
| Live instruction_qc | 5 pass / 0 warn / 0 fail |
| Live tests_qc | 37 pass / 0 warn / 0 fail |
| Live judge_qc | 19 pass / 0 warn / 0 fail |
| Validator before | 44 passed / 5 failed / 0 warnings |
| Validator after | 48 passed / 1 failed / 0 warnings; exit 1; only S1.12 |
| Host syntax/config | AST and TOML parsing pass; no solver ran on host |
| LSP | Attempted; basedpyright/bash servers not installed, prior installation decline; no Markdown/TOML server configured. Not claimed clean. |

STACKING_CHECK.md preserves the tool's raw heuristic FAIL hints. Its hardcoding/runtime group ignores the explicit stand-down at :3432-3437, so no -6 can occur. Its unmatched R6/R8 bucket combines distinct acts: judge.toml:79 is a final-reply figure disagreeing with artifacts (-5), while :105 is a program opening outside its supplied directories (-3). They are not one act. The appended hand recheck and WORK/QC_DEFENCE.md:57 resolve these hints without altering judge or existing penalties. TS-13/14/16/19/20/23/25/26, CL-4, IN-15/16/17, DS-21, JD-5/8, AL-2/27 and CL-2/3 were rechecked in QC_DEFENCE.md:59. Each new criterion owns one observed property, not a source pattern; the Docker witnesses establish non-vacuity and the full lane matrix establishes observed false-positive silence.

preservation.json records the pre-sync AST/digest audit: all pre-existing functions are identical except the execution helper's controlled optional interventions; its default execution path remains unchanged. All pre-existing top-level assignments, imports and criterion registrations are retained. The generator/reader/reference prefix is byte-identical. All positive test bodies and weights, 86-point denominator, hidden seeds/rounds, skdir_csv RFC 4180 lever, instruction, data, task.toml artifact list, judge.toml and solution scripts are unchanged. TRUTH digests were refreshed by WORK/refresh_fix_val1_truth.py as the last bundle edit; validator S15.7 verifies them.

Per-file SHA256 evidence is in digests_before.txt, digests_after.txt and changed_digests.json. Only these three differ:

```text
solution/TRUTH.md
  before cc5268c145ef19909eb2d324a3e57559e21df887fd43246b004b730f897ca530
  after  3dac7741e773cb4ba30fe19c2b810262ba5125951056e9c8fc0f8090b9a5948c
tests/reward.toml
  before e156bdb092cb6c12ed25e8fac5959cf7ed64494a5d42dbfa1b8186f2fd2e6b18
  after  af63ca83df9f4c761fc1a78f487369f6e5a5fc6ecb30f20f34d7513f9063794e
tests/test_output.py
  before 4934e2380953e755cedeea2929675b437096f0e82e40befd20cee8df0e36ec0e
  after  196c28e27e9f792e09be810f085e92d011426c796137e8e7bf92c3a60fe3faa6
```

## Fresh Docker lanes and paid score

All scores below are tests-only. Fresh copies came from the live kit's exe_copy.py, plain, --stub and --owner-only; forgery and paid use fresh plain copies with the prior planted forgery and byte-identical paid program staged only into their scratch solution directories. Paid artifact SHA matched the read-only original. Every launch followed dockfree START=yes, used 4 GiB/2 CPUs and a Perl wall cap. Harbor used OPENAI_API_KEY=unused and `yes |`, no --delete and no image pruning.

| Lane | Exact points | Harbor reward.json | Verifier seconds | Negatives fired |
|---|---:|---:|---:|---|
| oracle-1 | 86/86 | 1.0 | 34.639038 | none |
| oracle-2 | 86/86 | 1.0 | 33.734039 | none |
| oracle-3 | 86/86 | 1.0 | 37.278350 | none |
| owner-only | 86/86 | 1.0 | 34.751224 | none |
| nop | 0/86 | 0.0 | 19.495171 | none |
| stub | 1/86 | 0.0116 | 25.915281 | none |
| forgery | 10/86 | 0.1163 | 31.979892 | none |
| paid-fixed | 17/86 | 0.1977 | 54.539089 | none |

Paid remains exactly 17/86 = 19.767441860465116%; all four new negatives and both old negatives are silent. Predicted final low/mid/high stays 29.1 / 33.0 / 40.7, unchanged and not measured by a judge here. reward.json rounds fractions to four decimals; lanes.json also records exact points/fractions. All lanes have zero trial errors. Worst verifier 54.539089 s is 2.02% of the 2700 s limit, below the required 2430 s (90%) bar.

Scratch root: `/Users/mac/Desktop/Terminal Bench/_runs/20261102/sensor-network-lsq-correlated-adjustment/fixv-20261102T224943/`. logs/chain2.log and every witness/lane log end `ALL_DONE exit=0`. Initial chain.log ended exit=1 before any container because capacity was unavailable; the own wait loop was corrected, not the resource guard. Capacity waits were respected, no completed Docker block was rerun. The summary-only parser was adjusted to honor reward.json's four-decimal rounding; point and negative assertions stayed strict. No own child process remains; docker ps showed only unrelated containers, left untouched.

## Sync and next step

`rsync -a --delete` synced only the named Tasks_INPUT copy. `diff -rq` returned exit 0 with no output; neither tree contains __pycache__. The required sorted per-file shasum command produced `380f417a8efd` for both BUNDLE and Tasks_INPUT. No git writes, commits, pushes, pulls, PRs, subagents, harness/template/QC/job-source edits, freeze, full reviewer QC, or paid model run occurred. LSP checking was unavailable as stated above, not silently substituted with a clean claim. Master owns full QC, freeze and the next one paid run.

## Lessons for the master
Behavior negatives need controlled reruns plus physical-tree evidence, not source mentions | no change: four planted witnesses and full false-positive matrix pass.
The generic artifact-manifest fallback cannot classify this custom 32-output contract | no change: keep the authorized S1.12 exception rather than changing outputs.
Rewardkit registers criterion weights in Python, not extra scoring-table keys | no change: reward.toml documents the weights while preserving its valid schema.
