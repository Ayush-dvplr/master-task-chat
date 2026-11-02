# TODO - vendor-archive-roundtrip-recovery

## Phase 0 design (STOP after)
- [x] Read _COMMON_RULES, KNOWLEDGE, qc_authoring_checklist
- [x] Check GEN + QC fingerprints (match; only pre-existing untracked memory/ and "ayush sah tasks/")
- [x] Study format-recovery archetype: scaffold, validator RULES, playground A4/A5, 5 QC gates
- [x] Write DESIGN.md
- [x] Write DESIGN_SUMMARY.md
- [ ] STOP: say DESIGN READY, wait for "go" (+ master findings from district-heat/emberforge harden)

## Phase 1 scaffold (after go)
- [x] generate_bundle.py with env vars, no --force; copy scaffold_orig
## Phase 2 data + spec
- [x] datagen.py -> environment/data (12 files, 7 formats, chains, A5 22950 lines)
- [x] spec files hold every graded rule/key/error string (DS-25, CL-6)
## Phase 3 reference solution
- [x] solve.py (independent) + solve.sh; ref_codec/check via wrong-impls
## Phase 4 tests
- [x] test_output.py: hidden eval corpus, separating cases per lever, wrong-impls confirmed; LEVERS.md; reward.toml
## Phase 5 judge
- [x] judge.toml 12 concrete-fact criteria + 1 code-quality
## Phase 6 instruction.md (rewrite, 3821 chars)
- [x]
## Phase 7 TRUTH.md (8 sections; Q18 provenance kept)
- [x]
## Phase 8 self-check
- [x] 4 QC scripts 0 FAIL; validator GATE PASS; playground static 0 FAIL; oracle 1.0 (rewardkit 0.2.1), nop 0.0; C6 clear
## Phase 9 report
- [x] OUT/BUILD_REPORT.md

## Rebuild round 1 (22 Oct)
- [x] R1.0 read prompt, rules, round notes (incl 16:00 update), inputs; PLAN.md written
- [x] R1.1 docs: format_contract.md, decoder_appendix.md, escape_rules.md, revision_notes.md, new loader_notes.md
- [x] R1.2 tests/test_output.py: reference codec fixes, generators (catalog unchanged bytes, MAP-OMIT revision map, alpha/beta/gamma), composed hidden fixtures, permission-safe runner, checks + registrations
- [x] R1.3 regenerate environment/data from test_output.py (_write_corpus / build script in scratch), confirm catalog bytes unchanged
- [x] R1.4 solution/solve.py rewrite from the contract; solve.sh; local oracle run vs verifier (no Docker) = all checks pass
- [x] R1.5 judge.toml (batched, figure criteria), instruction.md, task.toml, tests/Dockerfile, reward.toml
- [x] R1.6 TRUTH.md, LEVERS.md, DESIGN.md "Round 1 changes", README_STALE.md
- [x] R1.7 D1 QC scripts (local c9e3454a + f3765e67 snapshot)
- [x] R1.8 D2 validator
- [x] R1.9 D3 Docker: oracle x2, nop, oracle-0600, owner-only
- [x] R1.10 D4 forgery
- [x] R1.11 D5 judge-by-reading; OUT/REBUILD_REPORT.md

## P12 r1 (22 Oct 21:42, QC v2 fixes)
- [x] P0.1 session rename 671afdb; read rules, round notes C/E/F/G, QC report v2, live kit HEAD 3fb1650b
- [x] P0.2 WORK/XREF.md + xref_check 0 findings
- [x] P0.3 WORK/QC_DEFENCE.md
- [x] P1 OUT/RECHECK_FIX.md rows (8 findings)
- [x] P2.1 judge.toml R5/R6 -> code quality R5 + method line R6 (8 criteria); reward.toml judge 0.5/24
- [x] P2.2 instruction.md L13 clause kept and graded by R6 (deleting it gave judge_qc G3 FAIL, 7 criteria)
- [x] P2.3 test_output.py both_reserved fixture + inversion comments
- [x] P2.4 TRUTH.md verification section; LEVERS.md; XREF update + xref_check 0
- [x] P2.5 4 QC scripts 0 FAIL + local verifier run
- [x] P2.6 Docker block oracle x3 / owner-only / nop (ALL_DONE)
- [x] P2.7 OUT/RECHECK_FIX.md gates, PL_NOTE.md, result_671afdb.json

## P12 r2 (22 Oct 22:55, QC v3 fixes, board 8ea6d8d)
- [x] P0.1 session rename 8ea6d8d; read rules, round notes C/E/F/G
- [x] P0.2 QC_DEFENCE/XREF present; xref_check 0 findings
- [x] P1 recheck v3 findings -> OUT/RECHECK_FIX.md
- [x] P2.1 apply fixes
- [x] P2.2 xref 0 + 4 QC scripts 0 FAIL
- [x] P2.3 Docker (if tests/solution/env changed): warm, oracle x3, owner-only, nop
- [x] P2.4 OUT RECHECK_FIX gates, PL_NOTE, result_8ea6d8d.json

## P9 harden lp1 r1 (23 Oct 08:45, board 52dbb3c, LEVER_PLAN_v1; levers L2+L3+L5+L6)
- [x] P0 session rename 52dbb3c (list shows it)
- [x] P0 read rules (COMMON, round notes C/E/F/G, LEVER_PLAN_v1, cohort DIAGNOSIS s0, DESIGN/LEVERS/QC_DEFENCE/XREF); record kit HEAD
- [x] P1.1 Phase A genuineness check
- [x] P1.2 lever table from reward-details + trajectory
- [x] P1.3 OUT/agent_program/
- [x] P1.4 OUT/DIAGNOSIS.md
- [x] P2.1 design L2/L3/L5/L6 in docs+data+generators
- [x] P2.2 instruction W1-W7 rewrite
- [x] P2.3 tests G1-G7 rewrite + reward.toml
- [x] P2.4 judge J1-J5
- [x] P2.5 solve.py update; local oracle 1.0, nop 0
- [x] P2.6 rule 6 (embed, reward, TRUTH sha); DESIGN/LEVERS/TRUTH/QC_DEFENCE/XREF; xref 0
- [x] P3.1 OUT/STACKING_CHECK.md incl agent program score <= 0.20
- [x] P3.2 4 QC + validator + playground static 0 FAIL; QL diff list
- [x] P3.3 Docker block (warm, oracle x3, owner, nop, stub, forgery) ALL_DONE
- [x] P3.4 HARDEN_REPORT.md, result_52dbb3c.json

## P12 r3 (23 Oct 10:45, QC v5 bddf20b fixes, board b2da4ee; scope Q51: FIX DS-4-1, JD-15-1, TS-16-1; KEEP DS-20-1, DS-6-1, X1)
- [x] P0.1 session rename b2da4ee (list shows it); kit HEAD 71a653b2
- [x] P0.2 read rules, QC v5, QC_DEFENCE/XREF present; xref_check 0
- [x] P0.3 reflex baseline (agent_program) on current tests
- [x] P1 recheck 6 findings -> OUT/RECHECK_FIX.md
- [x] P2.1 DS-4-1 neutral capture_id (generator, data, oracle, tests, TRUTH, XREF, rule 6)
- [x] P2.2 JD-15-1 judge.toml type
- [x] P2.3 TS-16-1 negative trigger replaced (runtime plant scan, name/weight kept; reward.toml unchanged, positive totals same)
- [x] P2.4 xref 0 (54 entries, capture_id added, rej- retired), 4 QC scripts 0 FAIL, validate_bundle PASS, stacking_check PASS, reflex 0.1682
- [x] P2.5 Docker: warm, oracle x3, owner-only, nop (ALL_DONE)
- [x] P2.6 OUT RECHECK_FIX gates, PL_NOTE, result_b2da4ee.json

## P12 r3 trap survival (23 Oct 11:19, P12_r3_trap.md, board b2da4ee)
- [x] T1 rebuild 8 variants (L2s L2u L2e L6 L3 L5c L5i L5n) from solve.py into WORK/trap/
- [x] T2 before: run variants + a2 on pre-P12 tests/data (QC_2026-10-23_lp1 copy, read-only, copied)
- [x] T3 after: run variants + a2 on current tests/data; separating cases; rebinds fired
- [x] T4 verdict PASS, no compensation
- [x] T5 OUT RECHECK_FIX ## Trap survival, result_b2da4ee.json keys, parse check
