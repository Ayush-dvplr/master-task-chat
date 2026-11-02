# TODO baafa14 sensor-network-lsq-correlated-adjustment harden r1
- [x] Phase 0 setup (HEAD 3fb1650b, copy, baseline_v0, baselines.json)
- [x] Phase 1 diagnosis: LEVERS.md, DIAGNOSIS.md
- [x] Phase 2.1 format fixes (K8, _grant_read, judge batched)
- [x] Phase 2.2 v2.md FAIL/WARN recheck (only G2 open at HEAD; X1 binary warn accepted DS-7)
- [x] Phase 2.3 hardness redesign
- [x] Phase 2.4 judge
- [x] Phase 2.5 DESIGN/LEVERS/TRUTH (generator-embedded data; re-emitted, TRUTH sha)
- [x] QC_DEFENCE.md, XREF.md, xref_check 0
- [x] Phase 3 Docker gates (chain running), HARDEN_REPORT.md, result_baafa14.json, scratch cleanup, lock release

# P12 r2 6a3cd4a
- [x] Rename session, read common rules and required round notes, lever rules, rulings, playbook, prompt
- [x] Re-hash generator and QC against fingerprints
- [x] Prior pause cleared: reconciled generator and QC fingerprints match current listed files
- [x] Phase 0: baseline copy, variants, reflex and trap scores
- [x] Phase 1: seven finding rechecks and rows (pending baseline completion before bundle edits)
- [x] Phase 2: fixes, QC, stacking, trap survival, Docker gates, reports

# P12 r3 078d40a
- [x] Rename session, read common rules, round notes C/E/F/G, lever rules, rulings, playbook
- [x] Phase 0: xref_check 0 findings; trap shas before recorded (OUT/trap_shas_before.txt)
- [x] Phase 1: recheck IN-8, DS-27, TS-13, X1 rows in OUT/RECHECK_FIX.md
- [x] Phase 2: lock, fix R5 + TRUTH L10/L114 + DS-27, QC_DEFENCE, LEVERS, XREF, QC scripts, stacking
- [x] Phase 2: trap shas after, Docker gates (oracle x5, owner, nop, stub)
- [x] Reports: RECHECK_FIX.md, PL_NOTE.md, STACKING_CHECK.md, result_078d40a.json, lock release, rename

# Redesign r2 4d6dfe8 (prompt master_chat_tasks/prompts/issued/sensor-network-lsq-correlated-adjustment/20261025T0051_rebuild.md)
- [x] Rename session (opencode matched ses_e90a3881effeekr4lU9Ua6qzuV)
- [x] Read common rules, round notes C/E/F/G, LEVER_RULES, LEAK_LIBRARY, QC_RULINGS, playbook, DESIGN, LEVERS, baselines, P14 summary
- [x] P1.1 read QC_DEFENCE, XREF, instruction, schema, solve.py, tests; tree_sha vs last QC tree; QC kit HEAD
- [x] P1.2 save agent program to OUT/agent_program/
- [x] P1.3 reflex pre-mortem (DESIGN_PROPOSAL.md section 1)
- [x] P1.4 (proto oracle_r2.py+fuzz.py built, smoke 3 seeds OK; 200-seed run started 01:16) prototype levers in OUT/proto/ (flags on oracle copy), >=200 corpora, differing share + points lost + one-fact-wrong + shrunk corpus
- [x] P1.5 OUT/DESIGN_PROPOSAL.md; STOP "DESIGN READY" (01:42, waiting for go)
- [x] go received 01:45 (night master; conditions 1-6 in LOG)
- [x] P2.1 test_output.py: generator (region align, marks+set_out_from, closures, variants), reader (district, recursive centring, closure), SCHEMA_MD, 6 new tests + weights (P=86)
- [x] P2.2 regen shipped data into environment/data (generator byte-for-byte), schema.md copy
- [x] P2.3 (01:58; local real-test score oracle 86/86, a2 8/86=0.093; selfcheck R9-R11 ok on 4 corpora) solution/solve.py mirrors rules + check R9-R11 ok lines; oracle local run == reference
- [x] P2.4 (02:00) judge.toml R1-R4 recompute + R9-R11; reward.toml 0.5/86
- [x] P2.5 (02:20; xref 0 findings) WORK docs: LEVERS, COST_TABLE, RULE_COVERAGE, JUDGE_MAP, QC_DEFENCE, XREF, DESIGN; TRUTH.md (sha last)
- [x] P3.1 (02:25; fuzz 300x3 reflex 300/300 each; variants 63/40/17; a2 8/86) fuzz gate >=300 on final generator; reflex gate a2 + one-lever + two-lever variants on real tests; STACKING_CHECK.md
- [x] P3.2 (02:28; xref 0, precheck CLEAN, kit 4 scripts 0 FAIL, validator 44/5 advisory same as r1, playground n/a) xref_check 0; 4 QC scripts + validator + playground static; precheck CLEAN; no __pycache__
- [x] P3.3 (docker emulation of the verifier, harness CLI denied by permission rule; oracle 1.0x3, owner 1.0, nop 0, stub 0.0116, forgery 0.0698; ALL_DONE; lock released) Docker chain oracle x3, owner, nop, stub, forgery (ALL_DONE)
- [x] P3.4 REDESIGN_REPORT.md + result_4d6dfe8.json

# R0 lever 868afdf (prompt master_chat_tasks/prompts/issued/sensor-network-lsq-correlated-adjustment/20261102T1445_harden.md)
- [x] Rename session (opencode ses_e63a0c69fffeZQhOSx2TQ1Rp2p)
- [x] Read rule files; card; instruction, reward, task.toml; test_output.py layout
- [x] Phase 0: WORK/r0_lever + witness created; tree sha 376ab407134e
- [x] Phase 0: confirm P reader/core lines (P:77-94, 240-265, 328-332), O solve.py:76-80, T 2162-2176; kit HEAD; OUT/TRIP.md
- [x] Phase 1: build measurement harness (quote sigma_kind in CSV/TSV rows of challenge+eval extracts) in r0_lever/
- [x] Phase 1: Docker run: paid, solve.py, verifier reference on plain+quoted; ref byte-identical; per-check EXACT/WRONG
- [x] Phase 1: kill table (paid, wrong/*.py, a2/owner programs on file, lever-aware row)
- [x] Phase 1: witness (smallest input) + line cites
- [x] Phase 1: live kit scripts + precheck on current bundle (list fails)
- [x] Phase 1: judge analysis, paid trajectory grade low/mid/high (low 38.5 mid 46.2 high 61.5 with R12-R17)
- [x] Phase 1: OUT/DESIGN.md; STOP "DESIGN READY"/"NO CORE" (19:05 DESIGN READY, skdir_csv; waiting for go)
- [x] go received (skdir_csv, DESIGN 2,5,9)
- [x] P2.1 tests: csv_quote flag + write_csv quoting + SCHEMA_MD + shape assert
- [x] P2.2 schema.md sentence; instruction.md 2 sentences
- [x] P2.3 judge.toml R12-R17; solve.sh R12-R16 witnesses
- [x] P2.4 Docker: digests before/after, oracle/paid on new tests, 300 seeds, solve.sh
- [x] P2.5 (20:20; xref 25 entries 0 findings; SELF_CHECKS after gates) WORK docs; TRUTH.md last; xref 0
- [x] P3.1 run stacking_check; precheck; 4 QC + validator (precheck CLEAN; validator 44 PASS, 5 pre-existing FAIL)
- [x] P3.1 disposition received in 3302dbb: add four behavioral negatives; KEEP legacy manifest S1.12; no freeze or paid model run
- [x] P3.2 exe_copy lanes oracle x3, owner, nop/stub/forgery (ALL_DONE; 1/1/1, 1, 0, 1/86, 10/86)
- [x] P3.3 paid rescore (valid corrected lane 17/86); rsync Tasks_INPUT; diff empty; both trees 70e94464a151
- [x] P3.4 HARDEN_REPORT and parsed result json (PAUSED); final rename queued as the last action before reply

# Fix-val1 3302dbb
- [x] Rename session; read route/common/playbook; verify 172 upstream fingerprints; record untouched tree and digests; validator before 44 PASS/5 FAIL
- [x] Add isolated behavioral probes and four negatives; register weights without changing positive scores
- [x] Write witnesses and defence/recheck rows; refresh TRUTH by script last
- [x] Run xref, stacking, precheck, four live QC scripts and validator (48 PASS/1 approved KEPT FAIL S1.12; PRECHECK CLEAN)
- [x] Docker witnesses: each planted act fires only its owner; oracle silent (WITNESSES_PASS, ALL_DONE exit=0)
- [x] Fresh exe_copy tests-only lanes: oracle x3, owner, nop, stub, forgery, paid-fixed; logs ALL_DONE exit=0
- [x] Verify paid 17/86, all new negatives silent, positive checks and lever unchanged (exact points and AST/digest audit)
- [x] Sync Tasks_INPUT, empty diff, no bytecode, both tree shas 380f417a8efd
- [x] Write FIX_REPORT, KEPT, parsed result; process cleanup verified; final session rename queued as last action before reply
