# RECHECK_FIX, dispatch-plan-reoptimization, P12 v3 r3 (board 2c2361c, QC v7 31e7ead)

Bundle tree sha at issue 1341a5ab938f. Kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30. Levers: LV-DPR-01 tie, LV-DPR-02 fallback, LV-DPR-03 amendment, LV-DPR-04 rejection/void (WORK/LEVERS.md:36-39); V0 levers V0-01..V0-18 are not graded by any changed line.

## Phase 1 recheck

| ID | label | rule quote (kit file:line via checks.json) | evidence quote (bundle file:line) | decision | playbook row | effect per lever | files changed |
|---|---|---|---|---|---|---|---|
| F1 AL-28 | REAL | 05_Alignment_Integrity_QC.md:28 "AL-28 No penalty stacking ... Group the negatives by triggering action, ACROSS both layers"; checklist :91 "one action never fires more than one max-severity penalty across tests and judged criteria" | tests/test_output.py:40 hook records `read_outside` for any non-write open outside input/output/stage/python roots, with no exemption for paths the run wrote; :18333-18335 `_check_reads_outside` = any `read_outside` in H1 audits; :18352-18370 `_check_writes_outside` = any `write_outside`/`write_input` in the scope run. One act (write a scratch file in tempfile.gettempdir() and read it back) fires -3 and -3 = 6 > 5 (v7.md:33-36). Noise check: v6.md:279 passed AL-28 as distinct acts; v7 reproduced the stack with a program, so not noise. QC_DEFENCE.md:52-53 row is stale (describes the old TMPDIR watcher) | FIX: hook keeps a set of paths the same run opened for write or renamed to; a later read of such a path is not `read_outside`. Writes side: instruction.md:3 "The program must read only from the input directory and write only inside the output directory." forbids any write outside /app/out, handbook_ops_v9.md has no tmp/temp/scratch permission, so `negative_writes_outside_output_dir` -3 stays and fires once (temp_writes_allowed=false) | AL-28 (one act, one layer) + TS-16 (narrow the trigger to the cheat only) | LV-DPR-01 none, LV-DPR-02 none, LV-DPR-03 none, LV-DPR-04 none (only negatives change; no positive check reads the hook set) | tests/test_output.py:40 (wrapper string), WORK/build/mktests.py hook, QC_DEFENCE.md, XREF.md if needed, TRUTH.md |
| M1 IN-16 | REAL (minor) | 01_Instruction_QC.md:46 "No significant ambiguity in anything that is graded ... show all three parts"; minor :89 "IN-16 an ambiguity you can show is real but that no test or criterion actually turns on" | tests/test_output.py:40 hook maps `os.fork`, `os.forkpty`, `os.posix_spawn*`, `subprocess.Popen` to `network_process_import`, which fires `negative_network_dependency_or_shell_cheat` -3; instruction.md:3 says only "do not start other programs from it", so a multiprocessing pool (fork of the same program) can be read as allowed. Not noise: v6 did not raise it, instruction.md:3 unchanged; it is a real gap between stated rule and checker. Not a lever (no hidden case turns on parallelism) | FIX: one settling sentence in instruction.md:3 in the checker's direction; no checker change; rest of instruction byte identical | IN-16 (settle in the governing file, general case, not the easier reading) | none for all four levers | instruction.md:3, TRUTH.md |
| W1 X1 | REAL (warn), KEEP | structure_qc.py:71 "X1  no em/en dash in any text file; binary-skipped files warn." (code :1076-1101) | environment/data/amendment_memo.docx, capital_program.xlsx, ledger_authority.sqlite, penalty_schedule.pdf, xref_manifest.db are genuinely binary (zip, zip, SQLite, PDF, SQLite) and carry graded facts (V0-04, V0-05, V0-03 sources); v7.md:43-44 checked by hand in Gate 02; same warn in v6.md:55/81 | KEEP, recorded in PL_NOTE.md for tasker approval | NOISE/SUGGEST: KEEP with verifiable evidence | none | none |
| W2 TS-14 | REAL (warn) | 03_Tests_QC.md:45 "Check names state the property ... and the name and the `description` match what the body checks"; checklist :115 | tests/test_output.py:18103 `_NETWORK_MODULES`, :18105 `_PROCESS_MODULES`, :18106-18109 `_SHELL_CALLS`, :18114 `_SHARED_TMP`, :18151-18155 `_owned_entries` each occur once (dead); :18135 `_hardcodes_sample_answers(text)` and :18140 `_embeds_visible_records(text)` ignore `text`. v6.md:196 passed TS-14 with the same lines; v7 raises a warn, real dead code | FIX: delete the five dead definitions; drop the unused `text` parameter and update both call sites; no check, weight or grading change, proved by identical per-check results | TS-14 (name and body agree; dead code removed) | none for all four levers | tests/test_output.py, WORK/build/mktests.py, TRUTH.md |

Files changed in BUNDLE: instruction.md:3 (one sentence added), tests/test_output.py (line 40 wrapper string, dead definitions removed, reads negative description), solution/TRUTH.md (one sentence, sha lines rewritten last). WORK: build/mktests.py (same edits at source; regenerated on a copy and diffed byte for byte before copying), LEVERS.md (round table), QC_DEFENCE.md (stale writes row rewritten, two rows added). XREF.md unchanged (no fact moved; xref_check 41 entries, 0 findings). test_weights.json and reward.toml unchanged (35 checks, P=101, negatives sum -20; judge 11 criteria).

## AL-28 programs (local scorer, tests channel, P=101)

All programs are the oracle plus one act (WORK/wrong/).

| program | act | negatives fired before | penalty before | negatives fired after | penalty after |
|---|---|---|---|---|---|
| al28_scratch_readback.py | writes then reads back `tempfile.gettempdir()/dpr_scratch.txt` | reads_outside, writes_outside | -6 | writes_outside | -3 |
| ts16_cheat_input.py | writes `<input>/.scratch_cache` | writes_outside | -3 | writes_outside | -3 |
| al28_foreign_read.py | reads `/etc/passwd`, never wrote it | reads_outside | -3 | reads_outside | -3 |
| ts16_cheat_tmp.py | writes `/tmp/x.txt`, no read back | writes_outside | -3 | writes_outside | -3 |
| ts16_honest.py | stdlib only, no outside access | none | 0 | none | 0 |

Temp writes allowed: no. instruction.md:3 "The program must read only from the input directory and write only inside the output directory."; handbook_ops_v9.md has no tmp, temp or scratch permission. So the write still costs -3 once, and the read back of the same path no longer adds a second -3.

## TS-14 identical-results proof

Per-check results (passed/failed per check id, triggered negatives, earned, penalty) compared before vs after with the local scorer:

| program | before | after | identical |
|---|---|---|---|
| oracle | 101 / 0 | 101 / 0 | yes |
| a2_solver (traj_a2 Run 1) | 68 / 0 | 68 / 0 | yes |
| nop (no solver.py) | 0 / 0 | 0 / 0 | yes (WORK/trap/ts14_nopstub.json) |
| stub (mkdir only) | 0 / 0 | 0 / 0 | yes (WORK/trap/ts14_nopstub.json) |
| m10_logabove (M10) | 53 / 0 | 53 / 0 | yes |
| m11_restorevoid (M11) | 53 / 0 | 53 / 0 | yes |
| m16_neghalf (M16) | 79 / 0 | 79 / 0 | yes |

The after files carry the F1 change too; none of these programs reads back a file it wrote, so the comparison isolates W2 and shows no check result moved.

## Side effects

FIX_SIDE_EFFECTS.md rows rechecked by hand (Always 14):

| fix | side-effect id | recheck | result |
|---|---|---|---|
| F1 AL-28 / TS-16 | TS-16 honest trippable | honest stdlib program fires nothing; foreign read still fires reads -3; input-dir write still fires writes -3; opening a foreign file in write or append mode still records one write -3 | PASS |
| F1 / TS-16 | TS-14 name vs body | reads negative description now says "detects solver reads of files outside its supplied input directory that the same run did not write, during a clean run." (mktests.py:626, regenerated) | PASS |
| F1 / TS-16 | TS-15 polarity | negatives keep weight -3 and the check returns True when the act happened; inline comments unchanged | PASS |
| F1 | AL-2 | instruction "read only from the input directory" is still graded by the reads negative; a read back of the solver's own temp file is already priced by the write -3 | PASS |
| F1 | AL-10 | baked-in check results identical for all programs above | PASS |
| F1 | TS-25 | no new check; existing check scope unchanged apart from the written-set exemption | PASS |
| M1 IN-16 | AL-27 | no new rule introduced; the sentence restates what the existing network/process negative already grades; trap replay identical | PASS |
| W2 TS-14 | none listed | identical-results proof above | PASS |

NEW-CHECK hygiene (Always 12): no new check, no new weight.

## Trap survival

Local scorer, tests channel, P=101. Before = WORK/trap/before_v3r3 (tree 1341a5ab938f); after = WORK/trap/after_v3r3 (fixed bundle).

| variant | before loss of P | after loss of P | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| agent_v0 | 85 (0.842) | 85 (0.842) | 1.00 | y | PASS |
| m_fallback (LV-DPR-02) | 70 (0.693) | 70 (0.693) | 1.00 | y | PASS |
| m_tie (LV-DPR-01) | 70 (0.693) | 70 (0.693) | 1.00 | y | PASS |
| m_amend (LV-DPR-03) | 69 (0.683) | 69 (0.683) | 1.00 | y | PASS |
| m_rejnorm (LV-DPR-04) | 33 (0.327) | 33 (0.327) | 1.00 | y | PASS |
| m_voidlog (LV-DPR-04) | 13 (0.129) | 13 (0.129) | 1.00 | y | PASS |
| m10_logabove (M10) | 48 (0.475) | 48 (0.475) | 1.00 | y | PASS |
| m11_restorevoid (M11) | 48 (0.475) | 48 (0.475) | 1.00 | y | PASS |
| m16_neghalf (M16) | 22 (0.218) | 22 (0.218) | 1.00 | y | PASS |
| a2_solver (real run) | share 0.673 | share 0.673 | n/a | y | PASS (<= before + 0.02) |

Hidden inputs h1..h4 and all positive checks are byte identical (generator diff touched only the wrapper string, the dead definitions and one description). Trap survival: PASS.

## QC_RULINGS rows

| board | finding | ruling |
|---|---|---|
| dispatch v7:33 | AL-28 scratch write + read back fired writes -3 and reads -3 | REAL; one act, one layer: the read negative stands down for paths the same run wrote; writes -3 stays because instruction.md:3 forbids writes outside the output dir |
| dispatch v7:39 | IN-16 fork/multiprocessing graded by network/process negative, instruction said only "other programs" | REAL minor; settled with one general sentence in the governing file in the checker's direction |
| dispatch v7:43 | X1 binary-skipped files | KEEP; genuinely binary inputs checked by hand in Gate 02 |
| dispatch v7:45 | TS-14 dead definitions and unused parameters | REAL warn; deleted, per-check results identical |

## Deviations from master directions

None.

## Checks and Docker

- xref_check: 41 entries, 0 findings. precheck.sh last line `PRECHECK CLEAN`. Live kit structure_qc.py exit 0, SUMMARY 17 pass, 1 warn (X1), 0 fail. STACKING_CHECK.md: `STACKING PASS` after hand correction (tool lumped structure checks as unmatched and misread J2). No `__pycache__` in BUNDLE.
- One Docker block, tests only, copies made with live kit exe_copy.py in /tmp/dpr-v3r3-20261024T161259-dbc8, logs and jobs in /tmp/opencode-logs/dpr-v3r3-20261024T161259-dbc8 (runs.log ends ALL_DONE):

| run | copy | reward | tests earned / penalty |
|---|---|---|---|
| v3r3-oracle-1..3 | plain | 1.0, 1.0, 1.0 | 101 / 0 each |
| v3r3-owner-1 | --owner-only | 1.0 | 101 / 0 |
| v3r3-nop-1 | plain, nop agent | 0.0 | 0 / 0 |
| v3r3-stub-1 | --stub | 0.0 (share of P 0.000) | 0 / 0 |
| v3r3-honest-1 | ts16_honest.py as solver | 1.0 | 101 / 0 |
| v3r3-scratch-1 | al28_scratch_readback.py as solver | 0.9703 | 101 / -3 (negative_writes_outside_output_dir only) |

Tree sha after fixes (master method): b0865a46bc58.

## Lessons for the master

audit-hook negatives that split one act into a write event and a read event stack by construction; price each act once in the hook (written-path set) | template_change: P12 v3 trap-survival step should add a write-then-read-back program to the standard AL-28 program set
`tempfile.gettempdir()` alone performs a probe write in TMPDIR, so any solver that merely calls it trips a writes negative | no change: correct under a "write only inside the output directory" contract; worth one line in QC_RULINGS if a task allows scratch space
stacking_check.py still lumps structure_* checks as unmatched and reports "J2 conduct criteria: none" falsely, so its verdict needed a hand correction again | template_change: master_chat_tasks/tools/stacking_check.py act matcher
