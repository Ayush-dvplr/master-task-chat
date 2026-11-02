# TODO - district-heat-flex-procurement

Tick a line only when its exit check passed; one line of evidence after the tick.

## P0 Read and plan
- [x] Record generator checksums in LOG.md - 15 digests written 16:40 IST
- [x] Read Final_checklist.md sections named in Rule 2 - read lines 1-525 incl. CL-1..CL-10
- [x] Read 01..05 QC gate files - all five read; truncated JD-15 and AL-1 lines read with sed
- [x] Read every file in templates/domain-calculation/ - 13 files read
- [x] Read DESIGN.md - 305 lines read
- [x] Write PLAN.md (summaries, data table, graph, rule/check/judge tables, open questions) - written
- [x] STOP: show PLAN.md, wait for "go" and answers to the open questions - go given 16:58 IST, all recommendations accepted (PLAN.md section 10)

## P1 Scaffold
- [x] Run generate_bundle.py with the fixed arguments - exit 0, printed `archetype: domain-calculation`
- [x] Confirm bundle folder exists and list its tree - 22 files, template data (11 files) present

## P2 Data
- [x] Write _work/.../datagen.py (stdlib, seeded from 731904, uniqueness/neutrality asserts) - written; second run byte-identical (cmp on all 13 files)
- [x] Delete the template's own data files (keep only what datagen writes plus schema.md) - 10 template files removed
- [x] Generate into environment/data/ - 14 files
- [x] Exit check: line counts per file (record files >= 2,000, total >= 20,000) - smallest record file pools.txt 2,002; total 234,443 lines
- [x] Exit check: >= 5 formats, flat folder, >= 12 files - 8 formats (csv ini json jsonl md tsv txt xml), 0 subfolders, 14 files
- [x] Exit check: dash scan returns nothing - perl U+2013/U+2014 scan: 0 hits (macOS grep has no -P)
- [x] Exit check: datagen neutrality asserts pass - 7 rerolls to unique optima; pending+VALID+Y rows 0; base+uplift<=cap by construction; 18,201 pool rerolls to distinct remainders; Wh and rates multiples of 1000; adjacent component swaps change 463/180/89/20 event-regions
- [x] Dependency graph in PLAN.md matches the generated files - 13 data files + schema as in PLAN section 2 (events.json per Q2)

## P3 schema.md
- [x] Write schema.md (sections 1-9 per DESIGN section 5) - 16,153 chars, 0 dashes
- [x] Exit check: quote the schema.md line for every rule and every output key in PLAN tables - rule lines in PLAN section 11; output keys re-checked mechanically at P5 (every key the tests read grepped in schema.md)

## P4 Oracle
- [x] Write solution/solve.py (independent implementation) and solve.sh - solve.py rewritten (exhaustive search, Fraction-free integer half_up); template solve.sh kept
- [x] Exit check: solve.sh against a local copy of the data writes all 10 artifacts - path-substituted solve.sh run: 10 files in out/, 1.5 s

## P5 Tests
- [x] Write tests/test_output.py (own reference, hidden-case generator, trap cases, negatives) - 30 checks (26 positive = 98, 4 negative = -16); source in _work/test_output.src.py; tests_qc O1 overlap 2%
- [x] Re-embed _SHIPPED_DATA from environment/data - _work/embed.py: 14 files, zlib 9 + base64; test_output.py 2.28 MB
- [x] Exit check: oracle output passes every positive and fires no negative - grade.py (rewardkit stand-in): earned 98 of 98, all 4 negatives False; empty workspace 0.0; stub -1/98; reference == oracle on all 9 shipped reports

## P6 Judge
- [x] Write tests/judge.toml (pinned header, R1.. criteria) - 12 conduct criteria, positive 30, negative -10; header diff vs template: identical
- [x] Exit check: judge_qc.py no FAIL - SUMMARY: 19 pass, 0 warn, 0 fail

## P7 Instruction
- [x] Write instruction.md - 1,880 chars; each artifact path once (derive_report.py twice: path + run command)
- [x] Exit check: every contract_sentence in judge.toml is verbatim in instruction.md; length < 6,000 - 0 contract_sentence (no constraint criteria); 1,880 < 6,000; instruction_qc PASS 5/0/0

## P8 task.toml and reward.toml
- [x] Edit description, keywords, tags, time estimates only - description 92 words; estimates 5400 s / 240 min / 720 min; structure_qc PASS 17/0/0
- [x] Rewrite reward.toml with 0.5 / positive totals (repr floats) - test_output 0.00510204081632653, judge 0.016666666666666666; tests_qc PASS 35/0/0

## P9 TRUTH.md
- [x] Write TRUTH.md (8 sections, >= 4,000 chars, labels, fresh digests, provenance edits) - 16,579 chars; 3 focal/2 drift/3 trap; archetype, generator_seed, trailer_token removed; authored_by null; validator §15.1-15.8 PASS

## P10 Lazy baselines
- [x] Write one wrong implementation per hard rule plus all-lazy in _work/.../wrong/ - wrong/make.py builds 9 variants from solve.py by exact patches
- [x] Grade each with the real test_output.py and record the fraction table - PLAN.md section 12
- [x] Exit check: >= 1 realistic row in 0.40-0.60; no wrong implementation scores 1.0 - all five lazy 0.592; max wrong row 0.918

## P11 Validation
- [x] validate_bundle.py -> GATE: PASS, 0 FAIL, 0 WARN - 41 passed, 0 failed, 0 warnings
- [x] playground.py -> 0 FAIL (oracle 1.0, nop 0.0, stub near 0, every ablation <= 0.5) - 0 FAIL 0 WARN; oracle 1.0, nop 0.0, stub -0.0102, 13 ablations 0.4898
- [x] structure_qc.py, instruction_qc.py, tests_qc.py, judge_qc.py from the QC folder -> no FAIL - 17/5/35/19 pass, 0 warn, 0 fail
- [x] Re-check generator checksums against LOG.md - 15 of 15 match

## P12 Report
- [x] Report: path, data table, hard rules, baseline table, gate summaries, not-verified list - delivered in chat 18:20 IST

## v2 HARDEN

Plan: PLAN.md section 13. Same tick rule: one line of evidence after each tick.

### V0 Plan
- [x] Record generator checksums at v2 start in LOG.md - 15 digests, identical to the P0 list (18:26 IST)
- [x] Read LOG, TODO, PLAN, DESIGN, schema.md, solve.py, datagen.py, test_output.src.py, wrong/make.py - read
- [x] Write PLAN.md section 13 (schema edits, new field, cases, checks, runtime plan) - written
- [ ] STOP: wait for Ayush's approval and answers to PLAN 13.11

### V1 schema.md
- [ ] Fix the 4 ambiguities (tuple order example, per-offer credit rounding, blank lines, code->region mapping everywhere)
- [ ] Add L1 text (tied_portfolio_count definition), L2 text (funded pool, calculation order), L3 text (column-only fixed width, RFC 4180 quoting, XML child order and whitespace, orphan vs ineligible)
- [ ] Remove the now-false sentence "Grants depend only on pools and weights"
- [ ] Exit: each rule stated once (grep), 0 dashes, every output key the tests read appears in schema.md

### V2 datagen.py
- [ ] Add 10 large event-regions (18-22 sites, 3-4 modes, >= 2 per region), unique optimum asserted with datagen's own exact search
- [ ] Add L3 traps (10-char event ids, 10-digit slack ceilings, quoted comma mode labels, XML cap-first and whitespace, profile rows of orphan and ineligible offers, blank jsonl lines)
- [ ] Keep neutrality asserts (H1-H5, unique optima, funded-pool distinct remainders, funded pool > 0)
- [ ] Run seed 731904 twice: byte-identical; record line counts and sha256 per file in LOG.md
- [ ] Exit: A5 line counts (record files >= 2,000), dash scan 0

### V3 reference and solve.py
- [ ] solve.py: exact branch-and-bound with strict pruning, tie count, coupling, L3-safe parsing
- [ ] _work/check_exact.py: 200 random small groups vs plain enumeration; large groups vs the verifier's independent method; log result
- [ ] Measure oracle runtime in the agent image (docker, 2 CPUs, 3 runs); large groups < 60 s total; set N

### V4 tests
- [ ] test_output.src.py: independent exact reference, new fields, new hidden cases, separated() lazy flags, per-run timeout N
- [ ] Check list and weights per PLAN 13.7 (5/3/1, negatives -1/-3/-5), 10..35 checks
- [ ] Re-embed _SHIPPED_DATA with embed.py; rewrite reward.toml (0.5 / positive total)
- [ ] Exit: oracle 1.0 and empty 0 through grade.py; measured verifier time logged

### V5 wrong/ and baselines
- [ ] make.py variants: time-capped brute force/greedy, prune on >=, no coupling, str.split fixed width, H1..H5, all-lazy
- [ ] Grade every variant with grade.py; table in PLAN 13.12
- [ ] Exit: oracle 1.0, empty 0, >= 1 realistic row in 0.40-0.60, all-lazy < 0.50

### V6 instruction.md
- [ ] Runtime sentence and funded-pool line; instruction_qc.py no FAIL

### V7 judge.toml
- [ ] Replace R5, add optimiser process criteria; judge_qc.py no FAIL

### V8 TRUTH.md and DESIGN.md
- [ ] TRUTH: new defect labels, fresh digests, DS-27 clean; DESIGN.md `## v2` change list

### V9 Gates and report
- [ ] structure_qc, instruction_qc, tests_qc, judge_qc from _qc: no FAIL
- [ ] validate_bundle.py --archetype domain-calculation: GATE PASS
- [ ] playground.py: D1 oracle 1.0, D2 nop 0, D3 stub <= 0.25, D4 ablations <= 0.5
- [ ] Generator checksums at end match the v2 start list
- [ ] Final report: changes, baseline table, oracle and verifier runtimes, every QC result, not-verified list

## Harden r1 (21 Oct 2026, master-chat prompt; the v2 HARDEN section above is ideas only)

Working copy: master_chat_work/bundles/district-heat-flex-procurement. OUT: master_chat_work/20261021_district-heat-flex-procurement/harden_r1/

### Phase 0
- [x] GEN and QC fingerprints - 163 + 12 files match (12:09 IST)
- [x] Copy ORIGINAL bundle and _work, sha256 tree - 25 + 23 files, trees equal; OUT/original_tree.sha256
- [x] Stopped-session edit check - only _work TODO/PLAN/LOG after 18:20; TRUTH digests match solve.sh, solve.py

### Phase 1
- [x] LEVERS.md - 30 checks, lever-neutral 58/98
- [x] S0..S5 + shortcut, P3 method b - baselines.json round 0 (S2 0.5918, S4 1.0, oracle 1.0, nop 0.0)
- [x] Underivability - all 5 levers HIDDEN-ONLY
- [x] OUT/DIAGNOSIS.md - 66 lines
- [x] STOP: wait for Ayush "go" and answers on D1, D2, DH-3, N - go 12:46 IST with 9 answers

### Phase 2 (after go)
- [x] V4 schema sentence (region codes in every file) - schema.md section 1
- [x] New levers per approved list, each with rule text, cases, wrong solver - LV-DH-1..5, 21 small + 4 large extracts, make_r1.py 13 variants
- [x] Exactness - check_exact.py 300 extracts, 1,200 event-regions, 338 ties, 0 mismatches
- [x] N - oracle 3x on 4 large extracts, 2 CPUs, agent image: slowest 1.785 s, N = 30
- [x] Re-embed, reward.toml, TRUTH digests, DESIGN "Harden round 1", LEVERS.md - done; reward 0.5/139, 0.5/45

### Phase 3
- [x] 4 QC scripts, validate_bundle --archetype domain-calculation, playground static - QC 0 FAIL; VB 1 FAIL (15.5, Q18 kept); playground static 0 FAIL 1 WARN
- [x] Oracle 1.0, nop 0.0 (tests channel) - score_p3 r1
- [x] Re-score S0..S5, baselines.json round 1, OUT/HARDEN_REPORT.md - S2 0.0863, S4 0.1942; UPSTREAM CHANGED noted

# ROUND 2 (P9 harden r2, started 2026-10-22 16:50 IST). Prompt: master_chat_tasks/prompts/issued/district-heat-flex-procurement/P9_harden_r2.md
- [x] R2-0 fingerprints GEN 160 + QC 12 match f3765e67; read common rules, round notes, DESIGN, LEVERS, baselines; backup /tmp/dh-r2-20261022/{bundle_orig,work_orig}; original_tree.sha256 in OUT
- [x] R2-1 Phase 1 diagnosis -> OUT/DIAGNOSIS.md (helpers never started, cancelled; read by me; no conflict)
- [x] R2-2 fix1 timing: sizes 8x3 and 120 s in schema, oracle DFS rewritten; oracle times measured in Docker (/tmp/dh-r2-20261022/timing/oracle_times_docker.txt, redo after final tests)
- [x] R2-3 fix2 run_agent stages 0644 copy, reaps uid 65534, caches parsed JSON (code written; Docker proof pending in R2-8)
- [x] R2-4 fix3 REAL recheck rows (1-9, 11-15, 17(no edit), 18, 19, 21; leave 16 and 20)
- [x] R2-5 fix4 judge rewritten, 10 criteria, judge_build_r2.py (written 17:02)
- [x] R2-6 fix5 instruction, schema, program.ini decoy, waiver rows, composed extracts (17:02); LEVERS.md + DESIGN.md still to rewrite
- [x] R2-7 tests/Dockerfile litellm pin done; test.sh already chmod 755
- [x] R2-8 gates: 4 QC, validator, exe_copy oracle x2 / oracle-0600 / nop / forgery; QC diff since 2690e960
- [ ] R2-9 HARDEN_REPORT.md + final reply
- [x] R2-3b fix3 REAL recheck rows applied (see PLAN_R2.md list); UNSURE rows 16 and 20 untouched; row 10 false positive untouched
- [x] R2-8a QC scripts 4/4 0 FAIL 0 WARN, validator 41/0/0 (logs in /tmp/opencode-logs/district-heat-flex-procurement-r2-20261022T1702/); check_exact 300 extracts 0 mismatches; reaping test in Docker; forgery 0.04
- [x] R2-8b FINAL docker chain done: oracle 1.0, 1.0, nop 0.0, owner-only 1.0; QC 17/5/37/19 0 fail; validator 41/0/0 (dh2f-oracle-1, -2, nop-1, owner-only-1) -> logs final-*.log, final-chain.done; then re-run QC + validator + forgery + lever_table once more if test_output changes
- [x] R2-9 HARDEN_REPORT.md in OUT written; copy baselines/levers/lever_table.json/oracle_times into OUT; final reply (<= 12 lines)

# P12 r1 (QC v2 recheck + fix, started 2026-10-22 21:42 IST). Prompt: master_chat_tasks/prompts/issued/district-heat-flex-procurement/P12_r1.md
- [x] P12-0 rename session 6fa0bdf; read common rules + round notes C/E/F/G; live kit HEAD 3fb1650b, fingerprints match
- [x] P12-1 Phase 0 QC_DEFENCE.md + XREF.md, xref_check 0 findings
- [x] P12-2 Phase 1 recheck DS-27, TS-25, JD-18/JD-15 -> OUT/RECHECK_FIX.md
- [x] P12-3 Phase 2 apply fixes; xref 0; 4 QC scripts 0 FAIL
- [x] P12-4 Docker block (only if tests/solution/environment changed)
- [x] P12-5 OUT/PL_NOTE.md, OUT/result_6fa0bdf.json, final reply

# P9 harden lp1 r1 (LEVER_PLAN_v1, board 0154d63, started 2026-10-23 08:45 IST). Prompt: master_chat_tasks/prompts/issued/district-heat-flex-procurement/P9_harden_lp1_r1.md
OUT: master_chat_work/20261023_district-heat-flex-procurement/harden_lp1_r1
- [x] H0 session renamed 0154d63 (list shows it); read common rules, round notes C/E/F/G, LEVER_PLAN_v1, cohort DIAGNOSIS s0, DESIGN, LEVERS, QC_DEFENCE; kit HEAD 71a653b2
- [x] H1 Phase A genuine check + lever table + OUT/agent_program/ + OUT/DIAGNOSIS.md
- [x] H2 design L1 L2 L4 L7 + backup /tmp/dh-lp1-20261023T084650-d539 (LEVERS.md section written at H6)
- [x] H3 lp1_data.py (deterministic, 2 runs identical): program.ini adders, profiles multiplier col (5410 rows), rate_cards comment + 226 overrides, export_manifest.tsv; schema.md edits; solve.py
- [x] H4 test_output.src.py rebuilt (35 pos = 113, 3 neg); embed 15 files; grade.py oracle 113/113, a4 program 20/113 = 0.177 (reward.toml at H5)
- [x] H5 judge.toml (J1-J5) + instruction.md (G5 sentence, remove figure ask)
- [x] H6 TRUTH.md digests, DESIGN.md "Harden lp1 r1", QC_DEFENCE, XREF + xref_check 0
- [x] H7 STACKING_CHECK.md (a)(b)(c) agent program <= 0.20
- [x] H8 4 QC scripts + validator + playground static 0 FAIL; QL diff list
- [x] H9 Docker block oracle x3, owner-only, nop, stub, forgery
- [x] H10 HARDEN_REPORT.md, result_0154d63.json, final reply

# P12 r2 (QC v4 53c71e3 recheck + fix, board a3aeb84, started 2026-10-23 10:45 IST). Prompt: master_chat_tasks/prompts/issued/district-heat-flex-procurement/P12_r2.md
OUT: master_chat_work/20261023_district-heat-flex-procurement/p12_r2
- [x] Q0 session renamed a3aeb84 (list shows it); read common rules v2, round notes C/E/F/G, LEVER_RULES_v1, QC_RULINGS, v4.md
- [x] Q1 Phase 0: QC_DEFENCE/XREF exist (check current), xref_check 0; reflex baseline on current tests
- [x] Q2 Phase 1 recheck 8 findings -> OUT/RECHECK_FIX.md
- [x] Q3 Phase 2 apply fixes (judge.toml R1/R5/R6/R9, reward judge 0.5/16, TRUTH.md, test src DH4seen + embed, LEVERS/QC_DEFENCE/XREF/DESIGN) 10:53
- [x] Q4 xref 0, 4 QC scripts 0 FAIL, stacking_check, reflex re-run
- [x] Q5 Docker block (warm, oracle x3, owner, nop)
- [x] Q6 OUT/PL_NOTE.md, result_a3aeb84.json, final reply

# P9 harden lp1 r2 (leak fix after a5, board eb6f232, started 2026-10-23 13:03 IST). Prompt: master_chat_tasks/prompts/issued/district-heat-flex-procurement/P9_harden_lp1_r2.md
OUT: master_chat_work/20261023_district-heat-flex-procurement/harden_lp1_r2
- [x] K0 session renamed eb6f232 (list shows it); read common rules, round notes C/E/F/G, LEVER_PLAN_v1, cohort DIAGNOSIS s0, DESIGN, LEVERS, QC_DEFENCE, XREF
- [x] K1 Phase 1 genuine check (staged copy = BUNDLE + harness host inject; instruction identical; exception None; judge 10/16 read)
- [x] K2 Phase 1 per-lever leak table from a5 steps
- [x] K3 OUT/agent_program (a5 final program) + local score on current tests
- [x] K4 OUT/DIAGNOSIS.md
- [x] K5 Phase 2 design fixes + backup bundle (WORK/bundle_pre_r2; levers L1 receipt, L3 season allowance ledger NEW, L4 composition, L7 per-interval half-even)
- [x] K6 data/schema/rate_cards edits, solve.py, re-embed, reward (0.5/98); TRUTH pending in K9
- [x] K7 tests rebuilt; grade oracle full, a5 <= 0.20, r1 program (oracle 98/98, a5 11/98=0.112, reflex 16/98=0.163, r1 2/98=0.020)
- [x] K8 judge.toml (DONE via judge_build_lp2.py, 8 criteria +16/-5), instruction check (unchanged, OK)
- [x] K9 DESIGN/LEVERS/TRUTH/QC_DEFENCE/XREF + xref_check 0 (xref 0 findings, 43 entries; TRUTH solve_py sha updated; schema re-embedded)
- [x] K10 STACKING_CHECK.md (a5 0.112, reflex 0.163, r1 0.020; penalty groups <=5; PASS)
- [x] K11 4 QC + validator + playground static 0 FAIL; QL diff list (17/5/37/19 pass 0 fail, validate 41/0; FIXED J10 R2, J5 R5 w3, R3 judge 0.5/17, 15.4 trap label; playground absent)
- [x] K12 Docker block (oracle 1/1/1, owner 1.0, nop 0.0, stub 0.0102, forgery -0.0102; ALL_DONE)
- [x] K13 HARDEN_REPORT.md, result_eb6f232.json, final reply

# P9 harden lp1 r3 (board 8cd7597, 23 Oct 2026)
- [x] R3-0 session renamed 8cd7597; read common rules, round notes C/E/F/G, LEVER_PLAN, cohort diagnosis section 0, DESIGN, LEVERS, QC_DEFENCE, XREF; live HEAD 71a653b2.
- [x] R3-1 genuine BUNDLE hash c3c5b97731b5 matches blind run; blind score 98/98; inspected blind program and read order.
- [x] R3-2 per-lever leak diagnosis and copy of blind program written in OUT; NO NATURAL TRAP, PILOT_WEAK decision.
- [x] R3-3 OUT reports and result JSON written; unchanged BUNDLE XREF 43 entries, 0 findings.
- [x] R3-4 stop before Phase 2 and gates, as prompt directs on NO NATURAL TRAP; no Docker job started.

# Redesign r4 (board 7743264)
- [x] D0 session renamed (opencode match; codex no match); rules/knowledge read; tree sha c3c5b97731b5 matches last QC
- [x] D1 agent programs saved OUT/agent_program/{blind,harness}
- [x] D2 proto oracle with flags OUT/proto/proto_oracle.py
- [x] D3 generator OUT/proto/gen.py (grants keys, chains, overlap planting)
- [x] D4 fuzz >=200 corpora: differing share, points alone, one-fact-wrong, shrunk corpora
- [x] D5 reflex pre-mortem + OUT/DESIGN_PROPOSAL.md; STOP "DESIGN READY"

- [x] D6 master 'go' 01:50 (M1 weight, M2 as proposed, M3 hidden-only overlaps; STACKING one-lever + two-lever rows; fuzz >=300)
- [x] E1 backup WORK/bundle_pre_r4 + test_output_r2.src.py; data edits (program.ini [grants], site_allowances draws_from depth-1, rate_cards comment, schema 1/6/7, manifest)
- [x] E2 solve.py new rules + solve.sh self-check lines
- [x] E3 test_output.src.py: reference flags, write_extract grants/draws, generator planting H1/H2, family tests, mutations; embed; reward.toml
- [x] E4 local grade: oracle full, nop, one-lever + two-lever variants, blind + harness programs (gate <=0.20)
- [x] E5 fuzz >=300 corpora final generator
- [x] E6 judge.toml +3 conduct; JUDGE_MAP; TRUTH; DESIGN/LEVERS/QC_DEFENCE/XREF/COST_TABLE/RULE_COVERAGE; xref 0
- [x] E7 STACKING_CHECK.md; QC scripts + validator + precheck CLEAN
- [x] E8 Docker block (warm, oracle x3, owner, nop, stub, forgery)
- [x] E9 REDESIGN_REPORT.md, result_7743264.json, final reply

# Wave 1 harden (board 7d95b18, 27 Oct 2026). Prompt: master_chat_tasks/prompts/issued/district-heat-flex-procurement/20261027T1110_harden.md
OUT: master_chat_work/20261027_district-heat-flex-procurement/harden_w1_7d95b18
- [x] W0 rename (7d95b18 not in list; noted), read rules + reports, fingerprints match (GEN 976c166, QC 5574d77e)
- [x] W1 Phase A: staged tests/environment == BUNDLE == Tasks_INPUT (diff -rq empty)
- [x] W2 diagnosis (loss.py: tests 173/173; Opus wrote B&B DFS with shortfall/deficit bound at traj step 14)
- [x] W3 design P-3 (+P-4) and proto generator in WORK/proto (regime e6: 20-26 sites, twins 95%, maxl 2)
- [x] W4 kill test in Docker -> WORK/KILL_TEST.md (g20 regime, all generic LATE or 3/16, ref2 <= 12.2 s)
- [x] W5 OUT/DESIGN.md, then STOP "DESIGN READY" (waiting for go)
- [x] GO received 14:5x (master: P-4 only if probe9 or blind fails it, Docker-only runs 4g/2cpu with cap, final kill table on final generator incl ref + ref3, twins in shipped/hidden check, other-shape exact solver timing on guard sample, schema s3 only doc change for P-3, kit-clean checks)
- [x] B1 (DROPPED both: solve/opus/blind pass missing-file x15 and rerun-identical; KILL_P4.txt) P-4 pre-test in Docker: probe9 + blind on missing-file and rerun-identical; keep check only if one fails
- [x] B2 (shipped 0 twin lanes of 8794; H1 14 twin lanes in 12 ERs, 2 chosen; H2 3 in 3; noted DESIGN) twin check: shipped extract + existing hidden corpora hold >= 1 site with identical offers (DESIGN.md note)
- [x] B3 (Docker CMP_OLD_NEW.txt: 22 corpora byte-identical old vs new; wide g20 5.5/6.0 s) solve.py: replace choose_portfolio with reference shape (merge twins, best-first order, bound); oracle == old on shipped
- [x] B4 (s3 now 'A site has at most 3 candidate offers in an event. Each run ... 120 seconds.'; no P-4 sentences) schema.md section 3 sentence edit (only P-3 doc change); instruction.md P-4 sentences if kept
- [x] B5 (WIDE_SEEDS 75775/84071, 8 wide checks 32 pts, 205 positive; CHECK_REF.txt MISMATCH 0; embed done; reward 0.5/205) test_output.src.py: wide generator (own RNG, bump constants), reference update, new checks; embed; reward.toml
- [x] B6 (guard2.py 150k: wide0 max 130,838 nodes, wide1 max 106,027; solve 4.3/9.3 s ref 4.1/8.7 s Docker) final generator guard + other-shape exact solver timing on sample (Docker)
- [x] B7 final kill table on final corpora in Docker -> KILL_TEST.md
- [x] B8 WORK docs: LEVERS, COST_TABLE, QC_DEFENCE, DESIGN (Wave 1 hardening), XREF + xref_check 0, TRUTH last
- [x] Phase 3 G1 stacking_check -> OUT/STACKING_CHECK.md
- [x] Phase 3 G2 cost table in Docker (all solvers, blind, all-but-one, first-write)
- [x] Phase 3 G3 precheck CLEAN + 4 QC scripts + validator 0 FAIL
- [x] Phase 3 G4 Docker block oracle x3/owner/nop/stub/forgery
- [x] Phase 3 G5 Tasks_INPUT sync + diff -rq empty
- [x] Deliverables: HARDEN_REPORT.md, result_7d95b18.json, ps clean
- [x] B8 partial 15:27: TRUTH_w1_body.md + w1_truth.py, EVIDENCE_MAP.md, LEVERS/QC_DEFENCE/DESIGN wave-1 sections written; COST_TABLE, XREF, TRUTH regen pending cost run
- [x] B7 final kill table (KILLF.txt, KILL_TEST.md final section) 15:39
- [x] B8a COST_TABLE wave-1 section (COST_w1.txt) 16:59

## P12 fix QC v6 (board 9a85fdc), started 23:05 IST 2026-10-27
- [x] P0 date, name_session (opencode ses_e8191d5f2ffeuXwT5oN9qkhwFa), rules read, kit HEAD 5574d77e
- [x] P0 xref_check 0 findings (48 entries) before change; trap baseline queued (p12/dout/TRAP_before.txt)
- [x] P1 recheck rows DS-27, JD-7/AL-6, JD-15, TS-23, TS-25/CL-2 -> OUT/RECHECK_FIX.md
- [x] P2 F05 TS-25 wide_feasible non-empty (test_output.src.py + embed), G7 diff
- [x] P2 F03 JD-15 delete R5, renumber, reward.toml judge weight
- [x] P2 F02 JD-7 solve.sh self-check own-extract stage (Docker test: all 8 lines agree, 3.1 s)
- [x] P2 F01 DS-27 TRUTH body edits, regenerate TRUTH by script last
- [x] P2 LEVERS/QC_DEFENCE/XREF/JUDGE_MAP in step; xref_check 0
- [x] P2 touched rules, vacuity probe, side effects, precheck CLEAN, stacking
- [x] P2 trap survival (wrong variants + blinds) Docker
- [x] P2 Docker block exe_copy oracle x3 / owner / nop
- [x] Tasks_INPUT sync, diff -rq empty
- [x] Deliverables RECHECK_FIX, PL_NOTE, KEPT, STACKING_CHECK, result json

## gate36 harden dcd21a3 (started 04:19 IST 2026-10-28; prompt master_chat_tasks/prompts/issued/district-heat-flex-procurement/20261028T0418_harden.md)
OUT: master_chat_work/20261028_district-heat-flex-procurement/harden_g36_dcd21a3
- [x] G0 date, name_session (opencode ses_e80727fb1ffewGpUrQT8mR57aI; codex no match), rules + reading list + WORK docs read
- [x] G1 kit HEAD recorded; trajectory_readout.py -> OUT/TRIP.md + TRIP table (losses are TIMEOUT)
- [x] G2 Phase A diff -rq run staged tests/ environment/ vs BUNDLE (only task.toml allowed_hosts)
- [x] G3 arithmetic (173/205=84.39 -> 173/237=73.00, final 44.83; lever 64/237=27.0%)
- [x] G4 design (seeds 7120/24943, bumps from guard) (wide_2, wide_3 same family, own RNG); proto generator WORK/proto/g36/
- [x] G5 kill test (KILL36.txt ALL_DONE; all exact solvers late, greedy/merit 6/32, ref 6.41 s max) Docker (KILL_TEST solvers, a10 program, 3 blinds) -> WORK/KILL_TEST.md g36 section
- [x] G6 judge: restate a10 prediction
- [x] G7 OUT/DESIGN.md, STOP "DESIGN READY"
- [x] GO received 07:53 (build exactly as designed; COST_TABLE incl a10 + 3 blinds each <= 80)
- [x] B1 G7 before copy + digests (WORK/g36/before)
- [x] B2 test_output.src.py: WIDE_SEEDS, WIDE_BUMPS, wide_2/3 criteria + registrations; embed; reward.toml 0.5/237
- [x] B3 G7 diff before/after (only new hunks; g36/G7_tests_diff.txt); old corpora unchanged (b3.log digests SAME); ref == solve on wide_2/3 (YES)
- [x] B4 WORK docs LEVERS, QC_DEFENCE, DESIGN section, XREF + xref_check 0; TRUTH body + regen by script last
- [x] P3-1 stacking_check -> OUT/STACKING_CHECK.md
- [x] P3-2 cost table Docker (all solvers, a10, 3 blinds, all-but-one, first-write)
- [x] P3-3 precheck CLEAN + validator
- [x] P3-4 Docker gate block oracle x3/owner/nop/stub/forgery
- [x] P3-5 Tasks_INPUT sync, diff -rq empty
- [x] D deliverables HARDEN_REPORT, result json, ps clean

## Round 8d509b8 (gate v3.6 judge-only harden from a10+a11; prompt master_chat_tasks/prompts/issued/district-heat-flex-procurement/20261028T1310_harden.md)
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_district-heat-flex-procurement/harden_judge_8d509b8
- [x] date, name_session (opencode matched), kit HEAD 5574d77e ok
- [x] read rules (COMMON v5, LEVER v3, KNOWLEDGE T, LEAK, QC_RULINGS, PLAYBOOK v3)
- [x] P1.1 trajectory_readout a11 -> OUT/TRIP.md, TRIP table; also a10 evidence per criterion
- [x] P1.2 Phase A diff -rq staged tests/env vs BUNDLE
- [x] P1.3 arithmetic
- [x] P1.6 judge design (oracle solve.sh fixed: new criteria must be shown by existing solve.sh output; positive total stays 24 since reward.toml fixed)
- [x] P1.7 OUT/DESIGN.md -> STOP "DESIGN READY" (in-brief infeasible: a11 floor 50%; Option B needs solve.sh unlock; WAITING master go A/B)
- [x] master go B (solve.sh own-extract stage unlocked); solve.sh D1 + altered copies D2-D4 written, Docker run 13:29 all agree, exit 0, rerun 0
- [x] judge.toml R4/R8/R9/R10 re-targeted (positive 24)
- [x] P2 JUDGE_MAP, LEVERS, COST_TABLE, QC_DEFENCE, DESIGN "Gate v3.6 harden", TRUTH by script, XREF + xref_check 0
- [x] P3.1 stacking_check -> OUT/STACKING_CHECK.md
- [x] P3.3 precheck CLEAN, 4 QC scripts + validator 0 FAIL (PRECHECK CLEAN, A3 66 warn; validator 40/0)
- [x] P3.4 Docker gate block oracle x3/owner/nop/stub/forgery (ALL_DONE) oracle 1x3 owner 1 nop 0 stub 0.0042 forge 0.2489
- [x] P3.5 sync Tasks_INPUT, diff -rq empty
- [x] deliverables HARDEN_REPORT.md, result_8d509b8.json

## P12 fix QL1 8556721 (started 04:15 IST 2026-10-29; prompt master_chat_tasks/prompts/issued/district-heat-flex-procurement/20261029T0414_fix.md)
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_district-heat-flex-procurement/p12_fix_ql1_8556721
- [x] S0 date, name_session (opencode ses_e7b4fd82bffekQezoZXop0tFLf; codex no match), rules read, fingerprints GEN/QC clean, kit HEAD 5574d77e
- [x] S1 backup BUNDLE -> WORK/pushed_e9d91966ed25 (tree_sha e9d91966ed25 both)
- [x] P0 QC_DEFENCE/XREF exist; xref_check 0 before changes; trap baseline per lever (TRAP_g36: REENTRY 192, CHAIN1 182, RELIEF 179, wide/a10 173, greedy 72 /237)
- [x] P1 recheck F1-F11 -> OUT/RECHECK_FIX.md rows
- [x] P2a F1 tie_decisions_match on generated tie extract (tie_case_passes, case_root('tie'), want non-empty: T2-0001 North count 2 [S1-Z,S2-M])
- [x] P2b F2 instruction.md:9 removal (before copy p12/instruction_before_8556721.md; QC_DEFENCE:298 + TRUTH.src:245 mention it -> P2k)
- [x] P2c F3 units/codes drawn in hidden generator
- [x] P2d F4 missing segment adder option
- [x] P2e F5 missing kept profile row
- [x] P2f F6 within-event allowance site in two regions
- [x] P2g F7 equality boundaries claims==F and need==left
- [x] P2h F8 R3 split into two criteria, reward.toml judge 0.5/27, solve.sh check lines
- [x] P2i F10 negative stdlib trigger
- [x] P2j G7 byte diff tests/; embed; sweep F3-F7 wrong readings lose graded checks; a12 prediction
- [x] P2k docs (LEVERS, QC_DEFENCE, JUDGE_MAP, RULE_COVERAGE, XREF, TRUTH by script); xref 0
- [x] P2l touched rules, vacuity probe, side effects, precheck CLEAN, stacking_check, trap survival
- [x] P2m verifier worst case timing; Docker block oracle x3/owner/nop (ALL_DONE)
- [x] P2n sync Tasks_INPUT; deliverables RECHECK_FIX, PL_NOTE, KEPT, STACKING_CHECK, result json

## Harden round _ql1 87117da (started 05:41 IST 2026-10-29; prompt master_chat_tasks/prompts/issued/district-heat-flex-procurement/20261029T0541_harden.md)
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_district-heat-flex-procurement/harden_r_ql1
- [x] S0 date, name_session 87117da (opencode ses_e7b003ddbffeW6pD6jlvq10m4F), no LAST round, rules read
- [x] S1 read WORK DESIGN/LEVERS/QC_DEFENCE/XREF/baselines, RECHECK_FIX, QL triage; kit HEAD
- [x] P1.0 trajectory_readout a12 -> OUT/TRIP.md + table
- [x] P1.1 Phase A (staged tests vs pushed e9d91966ed25, ctrf ids, errors)
- [x] P1.2 4 causes
- [x] P1.3 lever table + arithmetic
- [x] P1.4 autopsy
- [x] P1.5 OUT/agent_program
- [x] P1.6 LEAK rows
- [x] P1.7 OUT/DIAGNOSIS.md -> DIAGNOSIS READY stop
- [ ] P2 waits for 'go' (DIAGNOSIS READY 05:56 IST); a12 tests <= 60 judged unreachable under constraints (WRONG 0, TIMEOUT cap 30% -> best counted 70)

## P12 fix QL2 19f8e1f (started 16:28 IST 2026-10-29; prompt master_chat_tasks/prompts/issued/district-heat-flex-procurement/20261029T1535_fix.md)
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_district-heat-flex-procurement/p12_fix_ql2_19f8e1f
- [x] S0 date, name_session (opencode ses_e78b09a67ffeVCZ8FPnVqGiYNV; codex no match; 19f8e1f not shown by name), rules read, kit HEAD 5574d77e
- [x] S1 backup BUNDLE -> WORK/pushed_2b289f9f9561 (tree sha 2b289f9f9561)
- [x] P0 QC_DEFENCE/XREF exist; xref_check 50/0 before changes; fingerprints qc 12/12 gen 160/160; trap baseline = p12/dout/TRAP_p12new.txt (tests byte-identical to p12/new_tests.py)
- [x] P1 recheck F1-F17 -> OUT/RECHECK_FIX.md rows
- [x] P2a F1 schema.md:309/:313 scope sentence (18:10; schema 8.3 now names event_count/event_region_count/site_count and scopes the sum sentence)
- [x] P2b F2 independent exact truth in tests (equal oracle on shipped/H1/H2/wide x4) 18:25: _exact table method live on shipped/H1/H2, wide optima stored in _WIDE_TRUTH (320, 0 mismatch); src cut by regex bug repaired by p12q2/repair_src.py (broken copy p12q2/src_broken_2005.py); check_repair.py CHECK OK
- [x] P2c F3 drop unallocated_pool_count from shipped quality_counts projection (18:14 SHIPPED_ELSEWHERE in src)
- [x] P2d F4 two value checks x6 inputs = 24 pts (src: bid_cost_rows/compliance_rows families + 8 wide w1; 78 checks, +261/-13); reward 0.5/261 pending P2g
- [x] P2e F5 receipt records counts removed (data, generator, schema, TRUTH body, solve.py unchanged); re-embed
- [x] P2f F15 delete unused specs; H1 Wh-feasibility guard (DH2,selection); H1 seed CHANGED (h1_seed.py), H2 only receipt bytes
- [x] P2g G7 tests byte diff (OUT/G7_NOTE.md, G7_src_diff.txt); embed; reward.toml 0.5/261
- [x] P2h TRUTH F6/F7/F17 + F5 edits; docs (LEVERS, QC_DEFENCE, XREF, RULE_COVERAGE, JUDGE_MAP); TRUTH by script; xref 0
- [x] P2i touched rules, vacuity probe, side effects, precheck CLEAN, stacking_check, trap survival
- [x] P2j Docker block: warm, oracle x3/owner/nop + a13 program bar (ALL_DONE)
- [x] P2k sync Tasks_INPUT; deliverables RECHECK_FIX, PL_NOTE, KEPT, STACKING_CHECK, result json
- NOTE 16:58 master: Docker large-input jobs 2 at a time (--memory 4g each); before-baseline for bar = a13 verifier output (gate_run_a13 test-stdout), do not re-run old tests.
