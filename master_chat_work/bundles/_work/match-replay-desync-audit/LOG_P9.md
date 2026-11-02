# LOG: P9 v2 r1 match-replay-desync-audit (91cc2af)

- 18:00 IST date ok; name_session.py 91cc2af -> codex: no match / opencode: ['ses_e97422376ffe4XNRZN83dP21mC'] (91cc2af not shown in list).
- Read all required rules files in full.
- QC kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e; fingerprints 0 diffs.
- Phase 0.1: BUNDLE cp -Rp from SOURCE; jobs copied to OUT/baseline_v0/trajectory_job_match-replay-desync-audit_6237b4/.
- Phase 0.2: tree sha 6711dce7a011 (master method); baselines.json written. Reward 0.8043 confirmed from reward-details.json.
- Phase 0.3: WORK files created.
- P1.1 Phase A: GENUINE. No Permission denied/Errno 13/NOT_RUN/Traceback in job; instruction.txt == BUNDLE instruction.md; reward 0.8043=(103/163+42/43)/2; local repro of 40 tests on RUN artifacts matches ctrf exactly. 12 trap_* fail from agent uniqueness assertion (optimize.py l891 len(matched)!=1 -> exit 1); adapted copy (<1) passes all 12 => all traps LEAKED.
- P1.2 causes: 1 NO (instruction identical, no errors); 2 NO (judge.toml/test.sh edited Oct 21 after run, names/weights same, reward.toml unchanged); 3 PARTLY (fixplan v1 instr l3 'exactly one value reproduces' induced the agent's uniqueness assertion -> cost agent 60; fixplan v2 T4/T21 instruction line 11 asks for each judged figure -> R7-R13 35 pts free); 4 YES primary (12 transform traps each stated in replay-format.md and all exercised together in shipped captures; agent's pipeline correct for all).
- P1.3/P1.4 lever table and autopsy drafted (trajectory: read all notes step 5-8, probe loop 9-93, optimize.py written step 94, clean rebuild 95, checks 96-100 only on /app/data, no edit after 94).
- P1.5 OUT/agent_program/{optimize.py,outputs/,adapted/optimize.py (one-line != 1 -> < 1)}.

- 18:16 IST P1.6/P1.7: OUT/DIAGNOSIS.md written (Phase A GENUINE, primary cause 4, levers L1+L3+L4: running charter allowance in walk order, renewed at first tick of each live window, controls stay green). Replied DIAGNOSIS READY; waiting for go.
- 18:25 IST P2.1-P2.4: solve.py settle() and test_output.py _fit_plan switched from per-entry cap to running per-charter allowance (size baseline*opened, renewed at first tick of every live window, settled entries draw in walk order, min(amount, left)); HELD_OUT_HEFT=40 multiplies amounts in every non-shipped corpus; notes edited in data and STATIC_NOTE_TEXT (engine-rules Windows renewal para, Charters draw para; charter-scale Caps allowance para); regenerated corpus byte-identical to environment/data; probe: shipped 0 short draws, every hidden corpus except 'scale' 5-57 short draws, every reflex variant (perentry, norenew, refund, opening) differs. Local drive: oracle passes all 35 positives; agent and adapted pass only shipped/format + general_baseline_scale.

## 18:32 IST P2.5 tests done
- test_output.py: _grant_read before uid drop; G7 first differing path in _compare/_match_shipped and [check] print in _passes; two mutation tests (cadence modulus 7 moves only classes; window split moves only amounts) w5; nondeterministic negative removed (not a cheating act); shipped instance tests w1; descriptions reworded (shipped / fresh whole document).
- Local drive: oracle passes all 37 positive, negatives silent. Agent program and adapted copy (`< 1`) pass 9: 7 shipped w1, general_baseline_scale w5, mutation_cadence w5 -> 17/157 = 0.108 (gate <= 0.20).

## 18:36 IST P2.6-P2.8
- instruction.md: dropped l3 shipped-slice uniqueness promise and the settlement-history figure paragraph (J1 giveaway); G5 sentence added to the fresh-capture paragraph. 15 lines.
- judge.toml batched, 11 criteria: R1-R5 process w1, R6 outside /app/out -3, R7-R9 J2 conduct w3 (L3, L4, L1), R10 honesty -5 (old R14), R11 named-stage code quality w3. Dropped old R7-R13 (states figures), R15 (hardcoding double count with test negative), R16 (non-cheating), R17 (graded a reading). Positives 17.
- reward.toml weights 0.5/157 and 0.5/17. Dockerfile pip line with litellm==1.105.0; test.sh already chown root + chmod 755; _grant_read done in P2.5.

## 18:45 P2.9
- TRUTH updated earlier; wrote LEVERS.md (L3/L4/L1 with file:line), QC_DEFENCE.md D1-D8, XREF.md 16 entries, DESIGN Harden section. engine-rules.md:76 + STATIC_NOTE_TEXT reconciliation "held as surplus at a cap" -> "held as surplus beyond an allowance" (_notes_match_shipped True). xref_check 0 findings. No dashes/TODO/CR in bundle.

## 18:55 P3.1-P3.2
- AL-28 grouping fixed by wording: negative reads-answer description "fires when the program reads graded reports at a fixed path beyond its argument." (docstring+criterion); judge R6 description "...outside the scope of its task, anywhere other than /app/out...". stacking_check: all acts <=5, whole 89.2%, iso+mut 6.4%, shipped 4.5%, 41 tests, 11 criteria, batched.
- Final local scores (T/res2_*.txt): oracle 157/157; agent 17/157=0.1083; adapted 0.1083; single-lever oracle variants (T/var_*): perentry 0.1083, norenew 0.1083, opening 0.1401, cancelled_draw 0.1401; all variants byte-equal on shipped reports.
- OUT/STACKING_CHECK.md written (a-d, STACKING PASS); raw tool output OUT/stacking_check_tool.txt.

## 18:50 P3.3 QC
- structure_qc 17/0/0 PASS; instruction_qc 5/0/0 PASS; tests_qc 36 pass 1 WARN (A3 41 checks > 35, tasker approval) 0 FAIL after fixing H6 (the `*LAUNCH_FLAGS` star made H6 read the switch tuple as the program; inlined "-I","-S" and `_restage_under` now calls `_grant_read(program)` before its launch); judge_qc 19/0/0 PASS after J10 fix (R11 'cannot' reworded).
- validator (advisory): 40 passed, 0 failed, GATE PASS. Playground removed upstream (a72c20a4), skipped.
- QL rule (git diff 2690e960 HEAD -- Input_Bundle_QC/): H6 FIXED, K8 FIXED (pin added P2.8), S3 PASS, S5 PASS, T14 PASS, judge G2 batched FIXED, exe_copy --owner-only run in P3.4.
- Local re-score after H6 edit: oracle 157/157, agent 17/157.

## 18:58 P3.4 Docker block and reports
- TS 20261023T184333-d355 ALL_DONE 18:54: oracle x3 1.000, owner only 1.000, chmod 600 1.000, nop 0.000, stub 0.0064, forgery 0.0127 (hardcoding negative fired). Lock removed by chain.
- Tree sha 2f20060e94d2. Wrote OUT/HARDEN_REPORT.md, OUT/result_91cc2af.json, OUT/docker_block/runs.log, OUT/local_scores/.
