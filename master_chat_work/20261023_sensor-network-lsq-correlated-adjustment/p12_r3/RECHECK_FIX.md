# RECHECK_FIX: sensor-network-lsq-correlated-adjustment (P12 r3, board 078d40a)

QC report: `QC/reports/sensor-network-lsq-correlated-adjustment/v2.md` (copy c3824bc). Live kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e. Session rename printed `codex: no match` / `opencode: ['ses_e97678fedffebkYgpG4gOqjPZg']`; carried on as told.

Lever columns cover all 16 levers in WORK/LEVERS.md (V0-1 to V0-12, H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN). Every lever is "none" for every row, so the cell says "all 16 none".

| ID | Label | Rule quote | Evidence quote | Decision | Playbook row | Effect per lever | Files changed |
|---|---|---|---|---|---|---|---|
| IN-8 (JD-15, JD-18, AL-1, AL-4) ❌ | REAL | `01_Instruction_QC.md:38`: "a test or an outcome criterion demands something (a key name, an exact string, an error shape, ...) that the agent could not have learned"; `04_Judge_QC.md:99` JD-18: "At least one criterion judges the quality of the code the agent writes ... functions a reader can follow ... a criterion demanding one specific formatter, line length or idiom is a bare preference and fails JD-15". | v2.md:37 and pre-fix `tests/judge.toml:65-66`: "The agent writes derive_report.py so that a missing or unparsable input file stops the run with an error message naming that file." No line of instruction.md or schema.md states that error shape, and no other criterion judges code quality. `solution/TRUTH.md:10` "every graded rule is written there" and `:114` "one code-quality criterion" were both untrue. | FIX. R5 is now `r5_derive_report_py_uses_named_stage_functions`: "The agent writes derive_report.py as separate named functions, one per stage: reading the inputs, computing the adjustment, writing the reports." Id R5, weight 3, `type = "agent behavior"`, binary, evaluation_target trajectory kept. This is the 04:99 shape "functions a reader can follow", not a formatter or idiom. The program is large: oracle 548 lines, v0 reflex 1014 lines, the emberforge v5:198 size case. JD-2: no banned token. JD-5: I used "one per stage:" with a list in place of the master's "and" chain, so the criterion reads as one observable. JD-7, oracle `solution/solve.py`: reading `load_observations` (:148), `workbook_controls` (:204), `iteration_policy` (:225), `correlated_sessions` (:234); computing `adjust_extract` (:358), `class Network` (:281), `gauss_solve` (:257); writing `write_reports` (:391), `dump_json` (:387). solve.py is unchanged (sha 19e506cd...054c0). TRUTH.md:10 now reads "every rule behind a graded figure is written there". TRUTH.md:114-116 now names the conduct criterion. No sentence was added to instruction.md or schema.md. | JD-18 (named shape J4, conduct label, w1-3, oracle meets it, no idiom) | all 16 none | tests/judge.toml, solution/TRUTH.md |
| DS-27 ❌ | REAL | `02_Data_Solution_QC.md:80`: "TRUTH.md describes the task, not how the task was made ... What does not belong is any narrative of the production process ... Fail on process narration". | v2.md:38; pre-fix `solution/TRUTH.md:15-16` "(focal: the rules the earlier run broke and the round's levers; ...)". | FIX. The text now reads "the rules the earlier run broke and that change every graded figure". I grepped solution/, tests/, environment/Dockerfile, environment/data/schema.md, instruction.md and task.toml for `round`, `lever`, `harden`, `earlier version`, `v[0-9]` and lever codes (H1-4, V0-n). After the fix the only hits are maths (`ROUND_HALF_EVEN`, `round_places`, rounding) and the word "trap" in test_output.py comments, which is off limits (see Lessons). "The earlier run" as task story is kept. | DS-22 / DS-27 (rewrite TRUTH to the shipped task) | all 16 none | solution/TRUTH.md |
| TS-13 🟡 | REAL (minor) | `03_Tests_QC.md:44`: "One property per test. A test asserting two unrelated properties hides which one failed and skews the weight; flag it." Severity at `03:135`: minor. | v2.md:41; `tests/test_output.py:2654-2657` asserts `trace_decimal` inside `_check_reports`, registered 3 times at w3. | KEEP as minor, per master. The r2 split attempt failed (p12_r2/RECHECK_FIX.md:13, :19). Live W2 allows only weights 1/3/5. The legal 1+3+1+1 redistribution let no_centring, centring_angles and ignore_mount pass the observation-set half, which weakens H4-CHAIN. CL-4 shows one trace slip still scores 53/62 = 0.855 (v2.md:230). The defence is in WORK/QC_DEFENCE.md item 14. | TS-13 (NEVER drop or weaken the harder half) | all 16 none | none in bundle |
| X1 ⚠️ | FALSE_POSITIVE (script WARN) | structure_qc.py X1: "5 file(s) skipped as binary, re-check any that are text". | v2.md:44, :80: xlsx, db, sqlite, pdf, docx are real binary containers; QC re-checked their text by hand under DS-7 and found it clean. | KEEP. No change. | none (script WARN) | all 16 none | none |

## Deviations from master directions

- R5 wording: the master's draft joined three stages with "and". I wrote "one per stage: reading the inputs, computing the adjustment, writing the reports" to stay clear of a JD-5 compound reading. The shape, name, id, weight and type are the master's.
- XREF: the old R5 name was not in XREF.md. I added an "R5 name" entry with the old name under `retired`. xref_check: 16 entries, 0 findings.

## Gate results

- xref_check before changes: 15 entries, 0 findings. After: 16 entries, 0 findings.
- structure_qc exit 0 (0 FAIL, X1 WARN only); instruction_qc exit 0; tests_qc exit 0; judge_qc exit 0 (8 criteria; J1-J13 pass). Logs in this folder.
- Manual checks:
  - IN-8: R1-R4 quote the four figures the instruction asks for in the final reply; R5 is a conduct criterion; R6-R8 are negatives as before.
  - JD-18: R5 judges code quality through one named shape, and the oracle meets it (functions quoted above).
  - JD-2: no banned token in the new R5.
  - JD-5: one observable.
  - DS-27: grep clean except for maths and the off-limits test comments.
- Stacking: stacking_check.py output is byte-identical to r2 (`diff` exit 0). After the same body reading as r2, the verdict is PASS. See STACKING_CHECK.md.
- Counts: 24 tests, 8 criteria, positive tests 62, positive judge 15 (R1-R5 at 3 each).
- Docker (tests-only, live kit exe_copy plain / `--owner-only` / `--stub`): oracle x5 1.0, owner 1.0, nop 0.0, stub 0.0161; see "Docker block" below.
- Tree sha (sha256 over sorted bundle paths and contents, 67 files, first 12): 5823ca803559. Result: result_078d40a.json.

## Docker block

One nohup chain, copies built by the live kit `exe_copy.py` at /tmp/snlsq-p12r3-20261023T172415-ab1e/{plain,owner,stub}. Logs: /tmp/opencode-logs/sensor-network-lsq-correlated-adjustment-p12r3-20261023T172415-ab1e (runs.log ends `ALL_DONE` at 17:29:49 IST). Warm image warm-sensor-network-lsq-correlated-adjustment was under 1 hour old, so the warm build was skipped.

| Run | Copy | Agent | Reward | Exception |
|---|---|---|---:|---|
| oracle-1 | plain | oracle | 1.0 | none |
| oracle-2 | plain | oracle | 1.0 | none |
| oracle-3 | plain | oracle | 1.0 | none |
| oracle-4 | plain | oracle | 1.0 | none |
| oracle-5 | plain | oracle | 1.0 | none |
| owner-1 | owner (`--owner-only`) | oracle | 1.0 | none |
| nop-1 | plain | nop | 0.0 | none |
| stub-1 | stub (QC stub) | oracle | 0.0161 | none |

All four gates met (oracle 1.000 x5, owner 1.000, nop 0.000, stub 0.0161, which matches QC result_c3824bc.json).

## Trap survival

I recorded sha256 for 62 files: everything under tests/ except judge.toml, everything under environment/, and solution/solve.py. I took the hashes before the lock and the edits (`trap_shas_before.txt`) and again after every edit (`trap_shas_after.txt`). `diff` exit 0: SHAS_MATCH. Key hashes:

- tests/test_output.py 9d57e8eeed4ba5c35d01dd8debb63c0e0b3323bbb631b6d586a92f150db7a031
- tests/reward.toml 59e70c4da4cb2ff4dd94302e53f6390b7c0d415c6fa6a496acffeff573f4f83b
- tests/Dockerfile d12c9b206abd00fd7b823e141ad8ce396e0674aaaadc9adf86b47e9e597485d0
- environment/Dockerfile eca4cb2c21520148ed2678013eaa5280bcef1100110917e5a5ec6950f594b930
- solution/solve.py 19e506cd7f6d43ca4bc6f2b4826c4402c2466184df8b1581dc814a8d67f054c0

Trap survival is PASS by construction, with no re-score. The tests-only reflex stays at the r2 value, 0/62. Lever loss, copied from r2: H1-CENTRING 54 to 54, H2-ANGLE-REDUCE 54 to 54, H3-REVISION 57 to 57, H4-CHAIN 54 to 54, V0-11 0 to 10.

## QC_RULINGS rows

- IN-8/JD-18 | rule 01:38 + 04:99 | our design: R5 graded an error message the contract never stated | QC ❌ | REAL | replaced with conduct shape "separate named functions per stage" (size case like emberforge v5:198)
- DS-27 | rule 02:80 | our design: TRUTH used "the round's levers" | QC ❌ | REAL | process word replaced with a task phrase
- TS-13 | rule 03:44 | our design: trace assert bundled in summary_reports | QC 🟡 | REAL minor | kept: a split with legal weights weakens H4-CHAIN (r2 evidence)
- X1 | rule structure_qc X1 | our design: five genuine binary inputs | QC ⚠️ | FALSE_POSITIVE | script warn; QC re-read the text by hand (DS-7)

## Lessons for the master

- A conduct R5 should come from the 04:99 list from the start. Error-message wording keeps turning into a hidden contract rule (IN-8).
- test_output.py comments still say "trap" for data conventions. No QC flag, and the file is off limits this round. Watch for a future DS-27 reading.
- Recording the trap shas before the lock made trap survival a one-line proof. It is worth keeping for every judge-only or TRUTH-only round.
