# TODO schema-migration-plan-repair

- [x] P0.1 fingerprints GEN + QC checked (match 9b8229f6, 0 changed / 0 missing; untracked extras predate fingerprint)
- [x] P0.2 DESIGN.md written
- [x] P0.3 DESIGN_SUMMARY.md written
- [x] P0.4 "go" received 13:16; 8 master changes applied in DESIGN.md v2
- [x] P1 scaffold (generate_bundle.py, copy to scaffold_orig/)
- [x] P2 datagen.py, data, repository_contract.md, repo.zip
- [x] P3 solve.py / solve.sh, check_exact.py
- [x] P4 test_output.py, wrong implementations, LEVERS.md, embed, reward.toml
- [x] P5 judge.toml
- [x] P6 instruction.md
- [x] P7 TRUTH.md
- [x] P8 QC x4, validate_bundle, playground --skip-docker, oracle via rewardkit, C6
- [x] P9 BUILD_REPORT.md, fingerprints re-check

## Rebuild round 1 (22 Oct)
- [x] R1.1 PLAN.md section written
- [x] R1.2 make_shipped.py: decoy default + tokens_for `or` + README line; regenerate repo_shipped
- [x] R1.3 datagen.py: new layout, contract text (K1, K2, K19, N7), visible-data constraints, decoy boundary; regenerate
- [x] R1.4 verify visible data: shipped vs fixed vs reflex variants agree except decoy boundary, REPORT, CLI, fingerprint formula
- [x] R1.5 test_output.src.py rewrite (worlds, rebuilt checks, TS-17, TS-24, claims, embedding)
- [x] R1.6 embed + reward.toml + judge.toml + instruction.md + task.toml + Dockerfiles
- [x] R1.7 solve.py/solve.sh new layout + TRUTH.md
- [x] R1.8 local runs: oracle, shipped, variants, forgery, shares
- [x] R1.9 LEVERS.md, DESIGN.md Round 1 changes, README_STALE.md, LOG.md
- [x] R1.10 gates D1 to D5
- [x] R1.11 REBUILD_REPORT.md

## P12 r1 (22 Oct 21:42, board e5411d0)
- [x] P12.0 session renamed, rules + round notes read, harness HEAD 3fb1650b recorded
- [x] P12.1 WORK/QC_DEFENCE.md
- [x] P12.2 WORK/XREF.md + xref_check.py 0 findings
- [x] P12.3 Phase 1 recheck DS-27, TS-13, JD-5, TS-23, TS-14 -> OUT/RECHECK_FIX.md
- [x] P12.4 Phase 2 apply fixes, keep reward.toml/LEVERS/TRUTH/QC_DEFENCE/XREF in step
- [x] P12.5 QC scripts x4 + manual checks 0 FAIL, xref 0
- [x] P12.6 Docker block (oracle x3, owner x1, nop x1) if tests changed
- [x] P12.7 PL_NOTE.md, result_e5411d0.json

## P12 r2 (22 Oct 22:55, board e4d972f; QC v3 F/M/W 5/1/3)
- [x] R2.0 session renamed e4d972f, rules + round notes C/E/F/G read, harness HEAD 3fb1650b (same as v3 kit)
- [x] R2.1 Phase 0: QC_DEFENCE.md + XREF.md exist; xref_check 0 findings
- [x] R2.2 Phase 1 recheck IN-16, TS-25, JD-2/15, AL-2, AL-27, JD-5, DS-15 note, TS-23, CL-5/AL-4 -> OUT/RECHECK_FIX.md
- [x] R2.3 Phase 2 apply fixes (keep reward.toml/LEVERS/TRUTH/QC_DEFENCE/XREF in step; rule 6 if data edited)
- [x] R2.4 xref 0, QC scripts x4 0 FAIL, manual checks behind fixed IDs, local stub oracle
- [x] R2.5 warm verifier image, Docker chain oracle x3 / owner x1 / nop x1
- [x] R2.6 PL_NOTE.md, result_e4d972f.json

## P12 r3 (23 Oct 00:34, board a2407ba; QC v4 F/M/W 1/2/2)
- [x] R3.0 session renamed a2407ba, rules + round notes C/E/F/G read, harness HEAD 71a653b2 (diff vs 3fb1650b: structure_qc.py only)
- [x] R3.1 Phase 0: QC_DEFENCE.md + XREF.md exist; xref_check 0 findings
- [x] R3.2 Phase 1 recheck AL-27, TS-13, TS-16/19, DS-18, TS-23 -> OUT/RECHECK_FIX.md
- [x] R3.3 Phase 2 AL-27: five triggers inside an existing w5 world; one-rule-broken variants lose points
- [x] R3.4 Phase 2 minors/warns (TS-13 split, K7 contract line, DS-18 idempotent solve)
- [x] R3.5 embed, reward.toml, TRUTH, LEVERS, QC_DEFENCE, XREF in step; xref 0; QC scripts x4 0 FAIL; stub oracle
- [x] R3.6 warm verifier image, Docker chain oracle x3 / owner x1 / nop x1
- [x] R3.7 PL_NOTE.md, result_a2407ba.json

## P12 r4 (23 Oct, board 922c9f2; QC v5)
- [x] R4.0 rename, read rules and prior work, record live HEAD/fingerprint delta
- [x] R4.1 Phase 0 xref/defence review and pre-fix trap scores
- [x] R4.2 Phase 1 recheck all four findings and write rows
- [x] R4.3 lock and apply scoped fixes; sync XREF/TRUTH/LEVERS/defence
- [x] R4.4 xref, QC scripts, manual checks, stacking, trap survival
- [x] R4.5 warm image and Docker chain oracle x3, owner x1, nop x1
- [x] R4.6 complete reports, result JSON, release lock, rename

## P9 v2 harden r1 (23 Oct 16:34, board f681ef6; levers L1+L2+L5+L6)
- [x] H0 rename f681ef6, kit HEAD 71a653b2, fingerprints 0 diff; rules read (COMMON, notes C/E/F/G, LEVER_RULES, LEAK, RULINGS, PLAYBOOK, LEVERS, QC_DEFENCE)
- [x] H1 read DESIGN.md, XREF.md, baselines.json; blind_r1 SCORE/log/details/work; bundle ci docs + tests layout
- [x] H2 Phase 1: Phase A, 4 causes, lever table, autopsy; copy agent_program; OUT/DIAGNOSIS.md
- [x] H3 Phase 2 design: L1/L2/L5/L6 fitted; LEVERS.md + QC_DEFENCE.md entries before QC
- [x] H4a repo_fixed receipt+tokens, make_shipped F16/F17, datagen K13/K18/manifest/padding, env regenerated, solve.py rendered [x done 17:10]
- [x] H4b tests: receipt in reference, late gadgets REJECT/SCOPE/PAD/DAMAGE in all worlds, worlds 20-28, 3 isolated, 2 mutation; check_worlds 0 failures; oracle stub 201/201, nop 0; reflex 0.194; judge J2x4 + J3; instruction G5, figures paragraph removed; solve.py probes [x 17:14]
- [x] H4 Phase 2 implement: ci docs, datagen hidden worlds, tests, solution, embed, reward.toml, TRUTH, XREF; xref 0
- [x] H4c G7 [check] stdout lines; LEVERS/QC_DEFENCE/DESIGN sections; xref 0 [x done 17:22]
- [x] H5 Phase 3: stacking_check + STACKING_CHECK.md; reflex gate <=0.20; QC x4 + validator + playground static
- [x] H6 Docker block: oracle x3, owner, nop, stub, forgery
- [x] H7 HARDEN_REPORT.md, result_f681ef6.json, final rename [x done 17:40]

## P12 r5 (23 Oct 18:22, board 3b74d43; QC v6 F/M/W 1/2/2) prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/P12_r5.md
- [x] R5.0 rename (opencode/codex no match, noted), rules read (COMMON v2, notes C/E/F/G, LEVER_RULES, RULINGS, PLAYBOOK)
- [x] R5.1 record harness HEAD; read QC v6 + result json, LEVERS, QC_DEFENCE, STACKING_CHECK
- [x] R5.2 Phase 0: xref_check 0; copy tests/ environment/ to trap/before_r5; score replay + 31 variants (before)
- [x] R5.3 Phase 1 recheck DS-22/AL-18, TS-13, JD-5, A3/TS-23, TS-15 -> OUT/RECHECK_FIX.md rows
- [x] R5.4 lock; apply DS-22 (TRUTH + TRUTH.src/make_truth), TS-13 (test + src + embed), JD-5 (judge + make_judge + TRUTH/LEVERS/STACKING)
- [x] R5.5 xref (xref 0, 4 QC 0 FAIL, stacking same AL-28/TS-26 by-hand as harden_r1; manual checks + OUT STACKING_CHECK pending) 0; 4 QC scripts 0 FAIL; manual checks (negatives sum, TS-13, JD-5); stacking_check
- [x] R5.6 (PASS 31/31, replay 39/201 both; TS-13 reverted earlier) trap survival after (31 variants + replay); revert TS-13 if FAIL
- [x] R5.7 warm verifier image; Docker chain oracle x3 / owner x1 / nop x1
- [x] R5.8 RECHECK_FIX gates, Trap survival table, PL_NOTE, result_3b74d43.json, STACKING_CHECK; release lock; rename

## Wave 1 harden (27 Oct 11:10, board e3e74e6; P-2 long stateful replay + P-4) prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261027T1110_harden.md
- [x] W0 rename (opencode listed ses_e841e838..., codex no match), rules read, kit HEAD 5574d77e
- [x] W1 Phase A diff run staged tests/env vs BUNDLE (empty; Tasks_INPUT empty too)
- [x] W2 diagnosis table from trajectory + loss.py (all fixes first write 5.4 min; planner perf only hard part)
- [x] W3 collect generic solvers: proto/blind (cee149a), proto/opus (a4), proto/run_solver.py variants name_keyed/end_resolve/file_order/greedy; proto/core.py astar/greedy/schema_only/exhaustive/dijkstra; proto/p4.py
- [x] W4 prototype long hidden corpora in WORK/proto; run all solvers vs reference in Docker; KILL_TEST.md
  - [x] W4a Design 1 (P-2 history.py) local: blind + opus exact on 4 corpora -> FAIL
  - [x] W4b Design 2 (P-3 planner core.py) local: blind/opus TIMEOUT, astar exact
  - [x] W4c Docker block proto/kill.sh (log /tmp/opencode-logs/smpr_w1_kill.log, ALL_DONE) once <2 heavy jobs
  - [x] W4d WORK/KILL_TEST.md from the Docker log
- [x] W5 OUT/DESIGN.md; stop with DESIGN READY / NO CORE
- [x] W6 wait for master 'go' (Phase 2 build per OUT/DESIGN.md: 8 core worlds, bounded reference + oracle planner)
## Wave 1 Phase 2 (go 27 Oct, Design 2 P-3, P-4 dropped, judge unchanged)
- [x] B1 read tests src (WORLDS, _world, _world_holds, _child, registration, _reference_plan), embed/check_exact/make_solve, repo_fixed planner, task.toml memory, docs cost range
- [x] B2 digest of all expectations before (28 worlds + isolated + mutation)
- [x] B3 _g_core gadget (own RNG) + worlds 29-36 in src; bounded reference planner; digest after = before
- [x] B4 oracle planner (repo_fixed + solve.py via make_solve.py) bounded
- [x] B5 extra solvers a-d (fast dijkstra, dominance, incumbent, bidirectional) in proto; retune gadget so plain/opus/blind/a-d >60 s in Docker; 300-seed generator assert
- [x] B6 Docker kill test on final generator output (KILL_TEST.md, COST_TABLE)
- [x] B7 memory/timeout proof: full test run with Opus a4 deliverable in Docker, quote score (SCORE 0.8340 201/241; 8 core worlds TimeoutExpired at 60 s, rest pass)
- [x] B8 registration weights, embed, reward.toml, docs check (no new sentence), LEVERS/COST_TABLE/QC_DEFENCE/DESIGN/XREF, TRUTH last
- [x] B9 gates: stacking_check, precheck, QC scripts + validator, Docker oracle x3/owner/nop/stub/forgery
- [x] B10 Tasks_INPUT sync, HARDEN_REPORT, result_e3e74e6.json
- B8 partial: QC_DEFENCE, TRUTH text, XREF done; LEVERS/COST_TABLE/DESIGN pending measurements; TRUTH sha last

## Gate v3.6 harden (27 Oct 22:30, board f0331ad) prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261027T2228_harden.md
- [x] G0 rename (opencode ses_e81a91572ffeBBsfOI0AB2Bx5i, codex no match); common/lever/knowledge/leak/rulings/playbook read
- [x] G1 read task list: harden_w1 HARDEN_REPORT, score_caa031b SCORE_REPORT, QC v8 Findings+Carry-over; WORK DESIGN/LEVERS/QC_DEFENCE/JUDGE_MAP/XREF/COST_TABLE/KILL_TEST; kit HEAD
- [x] G2 trajectory_readout -> OUT/TRIP.md (written 22:44), complete TRIP table
- [x] G3 Phase A diff run staged vs BUNDLE (tests/ env/ identical; task.toml allowed_hosts only)
- [x] G4 arithmetic + lever design
- [x] G5 Docker kill test on proto hidden instances -> KILL_TEST.md
  - [x] G5a proto/core3.py (variant of _g_core: base 7000, zone degree 5, edges<=6000 guard); gen worlds 37-46 in proto/g36_d5 (1145-1196 schemas, 5683-5944 edges, ref <=0.011 s)
  - [x] G5b Docker kill3.sh gen + prog started 22:48 (logs proto/kill3_gen.log, proto/kill3_prog.log; ALL_DONE)
  - [x] G5c 300-seed shape run + KILL_TEST.md section
- [x] G6 judge band design
- [x] G7 OUT/DESIGN.md; DESIGN READY stop
- [ ] G8 wait for master go (Phase 2 per OUT/DESIGN.md)
- [x] G8 go received (master: J4 vacuity probe first; P1-P8 shown by oracle; old worlds byte-identical; Docker only; PRECHECK CLEAN)
## Gate v3.6 Phase 2
- [x] H1 digest before (proto/digest.py) + J4 vacuity probe on shipped src
- [x] H2 test_output.src.py: _g_core params, world_37..46, checks, registrations; embed.py; digest after = before
- [x] H3 solve self_checks P1-P8 (make_solve.py/solve_template), oracle local run in Docker
- [x] H4 judge.toml rebuild + JUDGE_MAP.md
- [x] H5 LEVERS/COST_TABLE/QC_DEFENCE/DESIGN/XREF/TRUTH; xref 0
- [x] H6 Phase 3: stacking, cost table Docker, precheck, QC scripts+validator, Docker gates, Tasks_INPUT sync
- [x] H7 HARDEN_REPORT + result json [done 03:47]
## P12 fix QC v9 (28 Oct, board c9ea299) prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261028T1205_fix.md
- [x] P0 rename (opencode ses_e7eb93acdffeTcus06yfhSQSKl, codex no match); rules read; kit HEAD 5574d77; OUT created; xref 0 findings before change
- [x] P1 recheck F1 (REAL) and F2 (REAL); noise check: both criteria new since v8; TS-23 KEEP
- [x] P1a R14 design scans (dead.py, unp.py, unimp.py) on shipped/oracle/a5/3 blinds
- [x] P2a make_judge_g36.py R14 + R20 text; save tests/ before; regenerate judge.toml; tests/ diff only judge.toml R14/R20
- [x] P2b TRUTH.md: drop error-message lines, R14/R20 text; JUDGE_MAP, QC_DEFENCE, LEVERS mentions
- [x] P2c judge_qc / validate / stacking / xref; truth_sha.py last; precheck CLEAN
- [x] P2d Docker: warm, exe_copy plain + owner, oracle x3 owner nop (nohup ALL_DONE)
- [x] P2e Tasks_INPUT cp -Rp + diff -rq empty
- [x] P3 OUT deliverables: RECHECK_FIX, PL_NOTE, KEPT, result_c9ea299.json
## Gate v3.6 harden a6 (28 Oct 15:53, board a4f790c) prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261028T1553_harden.md
- [x] A0 rename (opencode ses_e7df60dfeffehDUSJLE0asRGaV, codex no match); rules read; kit HEAD 5574d77e; OUT created
- [x] A1 trajectory_readout -> OUT/TRIP.md (written) + TRIP table (fill by hand at A6)
- [x] A1a unzip a6 repo -> WORK/a6_repo; audit: non-planner == oracle, planner == reference A* schema bound (old solvers on 29..46 already measured in KILL_TEST.md; a6 29..46 timing pending in kill4? no: run small block)
- [x] A2 Phase A diff -rq: staged tests/ environment/ solution/ instruction.md identical; task.toml only allowed_hosts lines 25,32
- [x] A3 arithmetic (L=140: a6 291/431=67.52, share 32.5%)
- [x] A4 design: gated core worlds (proto/gate.py g_gate stream 9000, strong_plan = max(schema rest, per-prereq-field projection)); same: 987 reference calls diff 0 digest b0f465e55d9b6d1a; ref 0.20-0.26 s; a6 >62 s on 47-49
- [x] A5a kill4.sh ALL_DONE 16:59 (container a4f790c_kill4, log proto/kill4.log, ALL_DONE)
- [x] A5 kill test Docker -> KILL_TEST.md (section a4f790c)
- [x] A6 OUT/DESIGN.md; DESIGN READY stop (17:10)
- [x] B0 master go 17:0x with change: 34 gated worlds world_47..80 (L=170, 291/461=63.1, final 46.0); Docker rule: only metered container besides mine, else echo wait-N; sleep 200
- [x] B1 DESIGN.md numbers -> 34 worlds (checks 81->115, positive 291->461, verifier worst 2,220 s)
- [x] B2 copies saved (/tmp/smpr-a4f790c/bundle_before, test_output.src.before_a4f790c.py); digest46 before/after pending Docker
- [x] B3 (src edited, ast ok; embed + digest + G7 pending) test_output.src.py: _reference_plan projection remainder; _g_gate; WORLDS 47..80; _world dispatch; _world_holds; 34 fns + regs; embed.py; digest after == before; G7 diff
- [x] B4 (repo_fixed planner + make_shipped patch + make_solve rendered solve.py; Docker check pending) oracle planner upgrade solve.py / repo_fixed / solve_template; oracle Docker run
- [ ] B5 records LEVERS/COST_TABLE/QC_DEFENCE/DESIGN/XREF; xref 0; TRUTH by script last
- [ ] B6 Phase 3: stacking, cost table Docker, precheck, QC+validator, gate Docker block, Tasks_INPUT sync
- [ ] B7 HARDEN_REPORT + result json
## Gate v3.7 redesign a6 (29 Oct 09:11, board 9111ecc) prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261029T0855_harden.md
- [x] Z0 rename (opencode ses_e7a40682dffeCVs57SfRcaIqc1, codex no match); rules read; kit HEAD 5574d77e; OUT created
- [x] Z1 Phase 0: halfbuild copied to WORK/halfbuild_a4f790c (fe32d3435385); BUNDLE rsync from Tasks_INPUT, diff empty, tree 308399b4016e
- [x] Z2 arithmetic: N=52 gated worlds w5 (L=260), cap 20 s (TIME_LIMIT_SEC+10), a6-like 291/551=52.8, share 47.2%, worst 1,080+52x21+120=2,292 s; judge 16 probes a6-graded 7/49=14.3; final 33.5
- [x] Z3 design: 52 gated worlds world_47..98 (_g_gate stream 9000+n), GATE child cap TIME_LIMIT_SEC+10=20 s; judge drop R5,R13, add N1-N5 probes (P-h missing file, P-h empty feed, P-h malformed edge line, P-d policy altered copy, P-d INI altered copy); cites K2 :18-23, K14 :88-93, K15 :95-99, M2-M8 migration_semantics.md:10-44
- [x] Z4a kill5 ALL_DONE (52 worlds 47-98, 20 s) + kill6 ALL_DONE (99-106, 15 s)
- [x] Z4 kill table in KILL_TEST.md section 9111ecc: a6 0/60, all repos/blinds 0/6, generics 0/4 (3 WRONG, 7 TIMEOUT), strong/repo_fixed 60/60 max 0.68 s; design moved to N=60, cap 15 s
- [x] Z5 a6 reply+trajectory: earned R1,R2,R14 only; N1-N5 skipped (no missing/malformed file, empty feed, altered policy/INI copy in a6_cmds grep); mid 7/49=14.3 (peer-25% formula 26.5)
- [x] Z6 OUT/DESIGN.md written (60 worlds, cap 15 s, judge R5/R13 out, R21-R25 in; pred final 31.8); DESIGN READY, waiting for master go
- [x] G0 master go 29 Oct 10:05: 60 gated worlds, cap 15 s, R21-R25; bundle-only CRASH+TIMEOUT cap 60% of positive test weight
- [x] G1 WORK/before_g37: preserve frozen BUNDLE before build; guard old 81 checks and immutable environment/instruction
- [x] G2 test_output.src.py: extend gated worlds to 106 and child cap 15 s; rendered embedded tests, 141 checks / 591 positive points; old 81 check bodies unchanged
- [x] G3 judge.toml: removed logical R5/R13, added R21-R25; 23 criteria / 49 positive points; sequential live IDs required by kit, logical names/witnesses stable
- [x] G4 solve_template.py: R21-R25 witnesses passed in Docker; generated solve.py; direct final checks 591/591 (g37_solve.log ALL_DONE)
- [x] G5 Docker build audit: 987 old reference calls identical (b0f465e55d9b6d1a); old worlds unchanged; 300 seeds passed; maximum reference 0.267 s
- [ ] G6 [blocked] remaining final-cost matrix: a5 cumulative TIMEOUT 390/591 = 65.9898% exceeds approved 60%; no third design authorized
- [x] G6a a6 full final-test cost ALL_DONE: 291/591 = 49.2386%, 982 s; all 60 new worlds TIMEOUT, every old check outcome unchanged
- [x] G6b a5 final-test cost ALL_DONE: 201/591 = 34.0102%, 2060 s; old 90 plus new 300 TIMEOUT points = 65.9898%; cap failed
- [x] G7 records: per-check LEVERS/QC_DEFENCE/COST_TABLE/DESIGN/JUDGE_MAP, TRUTH scripted last, XREF 0; unrun measurements explicitly blocked
- [x] G7a LEVERS/QC_DEFENCE list all 60 new checks; JUDGE_MAP logical/live ID map; TRUTH scripted, xref 50 entries 0 findings; PRECHECK CLEAN; validator 40/0/0
- [x] Phase 2 build (approved): built and invariant-checked, retained as PAUSED candidate
- [ ] Phase 3 [blocked] remaining costs and Harbor gates: cumulative timeout cap failed; Tasks_INPUT not synchronized
- [x] Deliverables: TRIP, DESIGN, STACKING_CHECK, HARDEN_REPORT and parseable PAUSED result JSON; final arithmetic/AST/report checks passed, tree ebf080b7b781; blocked gates and unsynced Tasks_INPUT explicitly recorded

### g37 resume after master go 14:15 (cap 70%)
- [x] H1 full-test cost done 18:00 (9179/b686 skipped by master 16:50: identical to 4 measured blinds); exhaustive CT/pos 71.57% > 70% (old SCALE/ladder timeouts)
- [x] H2 Harbor gates ALL_DONE 18:45: oracle 1/1/1, owner 1, nop 0, stub 0.0017, forgery 0.0102 (forgery verifier 2118.9 s)
- [x] H3 judge low/mid/high 8.16/14.29/26.53 -> final 28.70/31.76/37.88
- [ ] H4 [blocked] Tasks_INPUT sync withheld: PAUSED (exhaustive CT 71.57% > 70%); bundle ebf080b7b781, Tasks_INPUT 308399b4016e
- [x] H5 reports + result json PAUSED; g37_final_check.py FINAL CHECK PASS

- [x] H1 running since 14:19: chainA (7 programs) + chainB (abo + 8 generics); smoke diff ok (proto/g37_smoke.py)
- [x] H2 prep done 14:25: copies in /tmp/smpr-g37-gate-20261029T142136, script proto/g37_gate.sh; launch when a cost chain ends
- [x] H2 gates chain launched 18:01 (pairs), D=/tmp/smpr-g37-gate-20261029T142136/chain.log; wait ALL_DONE

### P12 fix v12 (board 08741c4, 29 Oct 20:20 IST) prompt master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261029T2010_fix.md
- [x] F0 session renamed (opencode ok, codex no match); rules read; kit HEAD 5574d77e; backup WORK/qc12_ebf080b7b781 (= bundle = QC copy a97202e = Tasks_INPUT, tree ebf080b7b781 via WORK/tree_sha.py)
- [x] F1 Phase 0: QC_DEFENCE/XREF exist; run xref_check 0 findings; trap baseline from HARDEN_REPORT/KILL_TEST
- [x] F2 Phase 1 recheck rows DS-20, DS-27, JD-15, TS-11, TS-23, DS-22/17 names -> OUT/RECHECK_FIX.md
- [x] F3 DS-20: rebuild QC graph WORK/p12v12/qc_graph.py; time old oracle in Docker; fix solve_template planner (joint-prereq pruning); new <= 2.5 s same plan
- [x] F4 DS-20 equivalence: 987 old reference calls + worlds 47..106 identical plans (Docker)
- [x] F5 DS-22/17: probe names descriptive in solve_template; regenerate solve.py (diff check)
- [x] F6 JD-15: remove R19/R21 from judge (generator), renumber per kit, reward.toml judge weight, JUDGE_MAP, solve check lines; judge prediction
- [x] F7 TS-11 (3600 applied; caldermoor task.toml:22 3600.0): check Output_RFP verifier timeouts; 3600 or KEEP
- [x] F8 DS-27: TRUTH src rewrite; regenerate TRUTH by script last + sha
- [x] F9 touched rules, vacuity probe, xref, precheck CLEAN, stacking, trap survival
- [x] F10 Docker: warm, oracle x3, owner, nop (stub) from exe_copy copies
- [x] F11 sync Tasks_INPUT; deliverables RECHECK_FIX, PL_NOTE, KEPT, result json

### P12 fix v13 (board 6ebf33a, 29 Oct 23:45 IST) prompt master_chat_tasks/prompts/issued/schema-migration-plan-repair/20261029T2345_fix.md
- [x] V0 session renamed (opencode ok, codex no match); rules read; kit HEAD 5574d77e; lock taken; backup WORK/qc13_589d2aa9c1e0 (tree 589d2aa9c1e0 = bundle = QC copy 68bec9e)
- [x] V1 Phase 0: xref_check 50 entries 0 findings; QC_DEFENCE/XREF exist; trap baseline = HARDEN_REPORT kill table :44-60 (every program loses 300 GATE points) + v12 RECHECK_FIX trap table
- [x] V2 Phase 1 recheck DS-20, DS-22, AL-17/TS-11, TS-23 -> OUT/RECHECK_FIX.md
- [x] V3 DS-20: WORK/p12v13/qc_graph13.py builds g2/g4 + stress family; time current oracle (Docker)
- [x] V4 DS-20: new planner (try7 backward bitset cost search + schema bound; installed repo_fixed, solve.py rendered) design in solve_template; g2/g4/stress <= 2.5 s and = slow exact
- [x] V5 DS-20 equivalence (2696 cases 0 diffs, p12v13/equiv.json): 987 ref + worlds 47..106 + 1109 calls identical (Docker)
- [x] V6 AL-17/TS-11: budget hunk in test_output.py _run (+ src generator?); arithmetic
- [x] V7 (02:07 p13_truth.py 5 replacements + truth_sha.py; xref 0) TRUTH by script last (DS-20 :18 :218-222, DS-22 :156-157) + sha
- [x] V8 touched rules, vacuity, xref, precheck, stacking, trap survival, side effects
- [x] V9 Docker: warm, oracle x3, owner, nop + ONE timed full verifier of unrepaired package
- [x] V10 sync Tasks_INPUT; deliverables RECHECK_FIX, PL_NOTE, KEPT, result json
