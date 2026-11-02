# TODO sentinel-policy-recompute P12 r2 (47d0997)
Prompt: master_chat_tasks/prompts/issued/sentinel-policy-recompute/P12_r2.md. OUT: master_chat_work/20261023_sentinel-policy-recompute/p12_r2
(P12 r1 aa5e389 TODO all done; history in LOG.md)
- [x] rename session (21:14, opencode ses_e96904e81ffe1Fz20DSQRqGV6y), tree e478f82d9b72 OK, kit HEAD 71a653b2 (= report kit), lock taken 21:16
- [x] Phase 0: xref_check 20 entries 0 findings
- [x] Phase 0: copy tests/ environment/ solve.py test_body.py to WORK/trap/before_r2 (read-only)
- [x] Phase 0: score BEFORE -> WORK/trap/before_r2_scores.txt (oracle 1, nop 0, stub 0, reflex build 0.1290 swap 0.0968). Local python: PATH=/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode/venv/bin (py3.12 pyarrow rewardkit); chmod -R u+w temp roots
- [x] Phase 1: read rules in live kit + bundle evidence for 13 findings; RECHECK_FIX rows (all 13 REAL; KEEP M1 M2 W7 W13)
- [x] Phase 2 F1: confirm reference_documents + solve.py row-version; HIDDEN_HEADS row v099 fixture in one hidden corpus; window-version-only variant in single_lever.py
- [x] Phase 2 F2: rerun check rewrite (test_body.py) + docstring
- [x] Phase 2 W11: resolution_order relative-order assert in hidden_dependency_trace
- [x] Phase 2 M3/W10: instruction.md:7 split, :5 reword (check README options)
- [x] Phase 2 M4/W8/W9: judge.toml R5, R10 negative -1, R7 w3; reward.toml judge denominator
- [x] Phase 2 W12: TRUTH.md:17
- [x] Phase 2: build_tests.py regenerate, diff vs bundle; TRUTH counts/shas/lines; QC_DEFENCE; XREF; LEVERS
- [x] Phase 2: oracle local 1.0 shipped+hidden; nop; stub; xref 0; 4 QC scripts; manual checks; stacking_check -> OUT/STACKING_CHECK.md
- [x] Phase 2: trap survival AFTER (+ window-version-only variant)
- [x] Phase 2: warm verifier image; Docker block (oracle x3, owner x1, nop x1, stub x1)
- [x] Deliverables: RECHECK_FIX.md, PL_NOTE.md, result_47d0997.json, tree sha, rename, lock removed

# TODO sentinel-policy-recompute P12 v3 r3 (7e07424)
OUT: master_chat_work/20261023_sentinel-policy-recompute/p12_v3_r3. QC v3 board f06feb3.
- [x] rename (opencode ses_e91cad2ceffeIMn7gP4hgPE6mb), tree 88d1009c6a4c OK, kit HEAD 976c1666 OK, lock taken 19:30, rules read
- [x] Phase 0: xref_check 0 findings (25 entries)
- [x] Phase 0: copy tests/ solution/ environment/ to WORK/trap/before_v3r3 (read-only); venv (py3.14)
- [x] Phase 0: BEFORE scores (oracle, nop, stub, reflex v0, m1-m7, single-lever) -> trap/before_v3r3_scores.txt
- [x] Phase 1: read v3.md findings + kit rules + evidence; RECHECK_FIX rows (F1 M1 M2 W1 W2 W3 P1 P2 P3)
- [x] Phase 2 F1 rebuild_config with reference values; weight decision; m2 proof
- [x] Phase 2 M1 split shipped check; W1 descriptions
- [x] Phase 2 M2 solve.sh echo paths
- [x] Phase 2 W2 W3 P1 judge.toml + JUDGE_MAP.md; reward.toml
- [x] Phase 2 P2 rename decoy_alias_table.jsonc; regen corpus
- [x] Phase 2 P3 RULE_COVERAGE.md
- [x] Phase 2 regenerate tests, diff, oracle local 1.0, nop, stub
- [x] Phase 2 trap AFTER + COST_TABLE.md
- [x] Phase 2 TRUTH/QC_DEFENCE/XREF/LEVERS; xref 0; precheck CLEAN; structure_qc; stacking
- [x] Phase 2 Docker block (oracle x3, owner, nop, stub)
- [x] Deliverables, tree sha, rename, lock removed, cleanup

## Harden round 2 (0074a64, 24 Oct 21:07 prompt)
- [x] Rename session, read rules + WORK docs, kit HEAD 976c1666 (matches)
- [x] P1.1 Phase A genuine check
- [x] P1.2 Root cause 4 causes (files changed since baseline, cause 3 7e07424 + instruction edit)
- [x] P1.3 Lever table from reward-details + trajectory
- [x] P1.4 Trajectory autopsy (Cause 4 per lever with step numbers)
- [x] P1.5 Save agent program -> OUT/agent_program/
- [x] P1.6 LEAK_LIBRARY rows
- [x] P1.7 Write OUT/DIAGNOSIS.md (+ lever plan, R11 review, trips table, scattered rules) then STOP
- [x] P2.0 Ayush go + master rulings 1-9 received (21:2x)
- [x] P2.1 gen_data.py N1/N2/N3 data + conventions; regenerated
- [x] P2.2 solve.py N1/N2/N3 + self_check_ledger; oracle_local run
- [x] P2.3 test_body.py families (n1/n2/n3 _hard w5, coupling a-d, mutations, merged shipped w1); build_tests; oracle 1.0 local
- [x] P2.4 judge.toml R11-R14, solve.sh check lines, JUDGE_MAP.md
- [x] P2.5 single_lever COST_TABLE (alone, all-but-one, one-fact-wrong) + reflex gate
- [x] P2.6 RULE_COVERAGE, LEVERS, DESIGN, QC_DEFENCE, XREF, TRUTH by script, xref 0
- [x] P3 stacking, QC scripts, precheck CLEAN, Docker block
- [x] P4 HARDEN_REPORT.md + result_0074a64.json

## Harden round 3 (9aaa7c6, 24 Oct 23:17 prompt; STOP after Phase 1 for master review)
- [x] Rename session (opencode ses_e90f5f047ffeEcV0gUm5bLIxkU), date 23:21, rules read
- [x] Kit HEAD + fingerprint check; OUT harden_r3 created
- [x] Read TEST_DEPTH.md 21-67 + result.json; QC_DEFENCE, XREF
- [x] P1.1 Phase A genuine check (job folder, diff -rq, result.json, verifier stdout)
- [x] P1.2 Root cause 4 causes
- [x] P1.3 Lever table from reward-details + trajectory
- [x] P1.4 Trajectory autopsy (step numbers per lever)
- [x] P1.5 Save agent program -> OUT/agent_program/
- [x] P1.5b Fuzz: copy kit fz -> OUT/fuzz, adapt W/image, run >=300 corpora on probe-2 program, differing share per lever
- [x] P1.5c Scratch prototype of proposed new lever (H7 re-entry / defined term), shrunk corpus where agent differs
- [x] P1.6 LEAK_LIBRARY rows
- [x] P1.7 Write OUT/DIAGNOSIS.md, STOP "DIAGNOSIS READY"
- [x] P2 awaiting master review of DIAGNOSIS.md (N4 timeout_pool H7 proposal)
- [x] P2.0 master GO 25 Oct: N4 wording explicit, caldermoor truth (no fits re-check), N4 only counted lever (PL note), R16 w3
- [x] P2.1 proto v2 re-run 300 corpora (agent differs 111/300; pool-a 2771, pool-b 2741)
- [x] P2.2 data + oracle + tests + judge R16 + regen (Always 6)
- [x] P2.3 COST_TABLE, RULE_COVERAGE, reflex score, WORK docs, xref 0
- [x] P3.1 stacking, QC scripts, validator, precheck (STACKING PASS w/ exceptions; QC 0 fail; validator 3 pre-existing TRUTH yaml; PRECHECK CLEAN)
- [x] P3.2 Docker chain (ALL_DONE 01:03:51 oracle 1.0x3 owner 1.0 nop 0 stub 0 forgery 0.2308)
- [x] P3.3 HARDEN_REPORT + result json

## Judge rebuild v3 (d0f1870, 26 Oct 18:00 prompt master_chat_tasks/prompts/issued/sentinel-policy-recompute/20261026T1800_rebuild.md)
OUT: master_chat_work/20261026_sentinel-policy-recompute/judge_rebuild
- [x] rename session d0f1870 (opencode ses_e87c656afffe6jciUrZ3B85o4T listed; d0f1870 not shown in list), date 18:10
- [x] read COMMON_RULES_v4, LEVER_RULES_v3, QC_RULINGS, g3 GROUP_SUMMARY
- [x] A1 OUT/JUDGE_BEFORE.md (16 criteria, probe 4 verdicts)
- [x] A2 trajectory acts list (step numbers) -> JUDGE_BEFORE.md section
- [x] B JUDGE_MAP.md "v3 rebuild 26 Oct" + new tests/judge.toml + reward.toml judge denominator check
- [x] C solve.sh self-check stage (check <id> ok + witness), graded outputs unchanged
- [x] D1 Docker oracle x3 + nop (QL procedure), quote check lines
- [x] D2 criterion vs oracle line by line
- [x] D3 4 QC scripts 0 FAIL + precheck CLEAN
- [x] D4 TRUTH.md sha by script; rm tests/__pycache__
- [x] E OUT/JUDGE_REBUILD.md + result_d0f1870.json

## Test-hardening t1 (b7e15f9, 26 Oct prompt master_chat_tasks/prompts/issued/sentinel-policy-recompute/20261026T1926_harden.md)
OUT: master_chat_work/20261026_sentinel-policy-recompute/harden_t1
- [x] rename session b7e15f9 (opencode ses_e87300d24ffe0mEYurecnYSop9 listed; b7e15f9 not shown), date 20:54
- [x] read COMMON_RULES_v4, round notes C/E/F/G, LEVER_RULES_v3, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2, DESIGN, LEVERS, baselines
- [x] read QC_DEFENCE, XREF, COST_TABLE, RULE_COVERAGE; kit HEAD
- [x] P1.1 diff -rq run tests vs BUNDLE tests
- [x] P1.2 positive-test table (read, step, what made it easy)
- [x] P1.3 arithmetic; rules with no hidden-only behaviour
- [x] P1.4 OUT/DIAGNOSIS.md, STOP "DIAGNOSIS READY"
- [ ] P2 (after go) T1 quiet rules data/contract/oracle/tests; T4 rare fixtures; docs
- [ ] P3 stacking, cost table, precheck, Docker block, Tasks_INPUT sync, report, result json

## t1 Phase 2 (go 26 Oct, master: Q1,Q2,Q3,Q5 accepted; Q4 retry cap weak -> unguessable point or dependency-order rule; shipped shows no new key/field/value line; EVIDENCE_MAP Q2,Q5 (IN-16); no IN-17 words; sentences apart; measured costs first-write<=70 all-but-one<=91; stop at BUILD READY, no harness probe)
- [x] P2.1 read solve.py/test_body/gen_data
- [x] P2.2 Q4 choice + floor value
- [x] P2.3 data sentences (+gen_data)
- [x] P2.4 oracle solve.py
- [x] P2.5 test_body + build tests + reward.toml
- [x] P2.6 local oracle 75/75, BRANCH_FIRE
- [x] P2.7 measured COST_TABLE, RULE_COVERAGE
- [x] P2.8 WORK docs + xref 0
- [x] P3.1 stacking, precheck, QC, validator, TRUTH
- [x] P3.2 Docker block
- [x] P3.3 sync + report + result json

## Test-hardening t2 (4a82a12, 26 Oct 23:28 prompt master_chat_tasks/prompts/issued/sentinel-policy-recompute/20261026T2328_harden.md)
OUT: master_chat_work/20261026_sentinel-policy-recompute/harden_t2
- [x] rename session 4a82a12 (opencode ses_e8613349fffesQ5WqXW4tVOMlN listed; 4a82a12 not shown), date 02:05 27 Oct
- [x] read COMMON_RULES_v4, round notes C/E/F/G, LEVER_RULES_v3, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2; DESIGN, LEVERS, QC_DEFENCE, XREF, baselines; kit HEAD
- [x] P1.1 diff -rq run tests vs BUNDLE tests (staged = probe-4 era pre-t1: judge/reward/test_output differ, expected)
- [x] P1.2 copy blind r1 (done) program -> WORK/blind_r1; table Q1-Q5 + hard rules (read, step, why easy)
- [x] P1.3 arithmetic
- [x] P1.4 OUT/DIAGNOSIS.md (unique-fit + derived-state plan), STOP "DIAGNOSIS READY"
- [x] P2 (go 02:25)
  - [x] P2.1 backups *_before_t2 + snapshot old corpora bytes/docs
  - [x] P2.2 data text edits (select, conventions, convergence_spec, reconciliation comment, output_field_spec nulls) + gen_data.py
  - [x] P2.3 solve.py oracle (resolve + recompute_outside): reinstated, reports/reset, divisor fit, null verdict
  - [x] P2.4 test_body: evaluate + planters u/d1/d2/combo2 + tests + weights P=98
  - [x] P2.5 build_tests, oracle local 1.0, old corpora byte-identical
  - [x] P2.6 measured costs (levers alone, all-but-one, first-write, blind r1)
  - [x] P2.7 WORK docs (LEVERS, BRANCH_FIRE, RULE_TRACE, COST_TABLE, RULE_COVERAGE, QC_DEFENCE, UNIQUENESS, EVIDENCE_MAP, DESIGN), TRUTH, XREF 0
- [x] P3 gates (Docker NOT RUN), Docker, sync, report, result json
  - [x] P3.1 stacking_check -> OUT/STACKING_CHECK.md
  - [x] P3.2 precheck CLEAN + 4 QC scripts + validator
  - [x] P3.3 Docker block: NOT RUN (harness command denied by permission rule)
  - [x] P3.4 Tasks_INPUT sync, HARDEN_REPORT, result json, cleanup

## Test-hardening t3 (3022cae)
- [x] P1.1 diff -rq staged vs BUNDLE tests; BUNDLE vs Tasks_INPUT empty
- [x] P1.2 blind r2 copied to WORK/blind_r2; rule table
- [x] P1.3 arithmetic
- [x] P1.4 OUT/harden_t3/DIAGNOSIS.md written; STOP for "go"
- [x] P2.0 go received 03:41; R measured in Docker (dp/mitm/naive TIMEOUT, ref <=0.07 s) -> build variant C
- [x] P2 lever R (ledger_repair.json) data+docs+tests+WORK records
  - [x] P2.1 data: controls t-atlas, conventions[14], output_field_spec, instruction 60 s
  - [x] P2.2 solve.py CORRECT_CLI writes ledger_repair.json; self-check
  - [x] P2.3 test_body.py: repair_document, R planters/corpora, 5 tests, weights
  - [x] P2.4 build_tests, reward.toml, local oracle 1.0, accepted() readings (+ hidden_fresh_state_corpora_hard w4, P=137)
  - [x] P2.5 cost table measured (local + Docker), WORK records, TRUTH, XREF (P=131 after W2 reweight + rall family)
- [x] P3 gates, Docker, sync, report, result json
  - [x] P3.1 truth_sha, xref_check 0, precheck CLEAN, stacking_check, validator 37/3 pre-existing
  - [x] P3.2 rule_mutants t3 (27/27 caught) -> WORK/rule_mutants_t3.log
  - [x] P3.3 Docker chain (manual, CLI blocked; oracle 1/1/1 owner 1 nop 0 stub 0 forge 0.0153) (oracle x3, owner, nop, stub, forge) ALL_DONE
  - [x] P3.4 Tasks_INPUT sync, HARDEN_REPORT, result json, cleanup

## Gate v3.6 harden (217875e) prompt master_chat_tasks/prompts/issued/sentinel-policy-recompute/20261027T2229_harden.md
- [x] P0.1 name_session 217875e (not shown in list; note in report)
- [x] P0.2 read rules (_COMMON_RULES_v5, LEVER_RULES_v3, KNOWLEDGE T, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v3)
- [x] P0.3 read WORK docs + QC v7 + 1328 fix prompt + bundle judge/instruction
- [x] P1.1 trajectory_readout -> OUT/TRIP.md + table
- [x] P1.2 Phase A diff staged vs BUNDLE
- [x] P1.3 arithmetic
- [x] P1.4-6 design, kill line, judge band
- [x] P1.7 OUT/DESIGN.md; STOP "DESIGN READY"
- [x] P2 build (F1 F2 F3 F5 F6 + judge band + R12 code quality), WORK records, TRUTH, XREF 0
- [x] P3 gates (stacking, cost, precheck/QC, Docker block, sync), report, result json
  - [x] P3.1 STACKING PASS, PRECHECK CLEAN, QC 0 fail, validator 10 pre-existing, xref 0
  - [x] P3.2 Docker chain ALL_DONE (oracle 1x3 owner 1 nop 0 stub 0 forge 0.1164; F3 isolation ok) + rescore ALL_DONE
  - [x] P3.3 Tasks_INPUT sync (diff empty, tree f5e0d873e6c6), HARDEN_REPORT, result json, cleanup

## P12 fix QC v8 (3157183) prompt master_chat_tasks/prompts/issued/sentinel-policy-recompute/20261028T0325_fix.md
OUT: master_chat_work/20261026_sentinel-policy-recompute/p12_fix_v8_3157183 ; kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271
- [x] P0.1 name_session 3157183 (not shown in list; note in report)
- [x] P0.2 read rules
- [x] P0.3 xref_check 0 before changes; trap baseline
- [x] P1 read v8 report, classify every finding -> RECHECK_FIX rows
- [x] P2.1 CL-1 restore check shipped_config_produced_by_repaired_tool (test_body, build_tests, G7 diff, reward 0.5/147)
- [x] P2.2 JD-5 judge.toml:157 drop "a maintainable"
- [x] P2.3 WORK records (XREF, COST_TABLE, QC_DEFENCE, LEVERS, OUT KEPT.md, STACKING_CHECK)
- [x] P2.4 TRUTH regen last (line count, probe list, garbled sentence) + sha
- [x] P3.1 touched rules, vacuity, xref 0, precheck CLEAN, stacking, trap survival
- [x] P3.2 Docker block oracle x3 owner nop ALL_DONE
- [x] P3.3 Tasks_INPUT sync, deliverables, result json
