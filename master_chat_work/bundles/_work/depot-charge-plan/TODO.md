# TODO depot-charge-plan (board 154f570)
- [x] rename session (name_session.py printed opencode ses_e6c82bbdfffebyu6deVAtfxNU5)
- [x] read docs 1-5
- [x] P0.1 fingerprints GEN/QC (160+12 files byte-identical; GEN has 63 extra files under "ayush sah tasks/" not in fingerprint, not generator code)
- [x] P0.2 PREMORTEM.md
- [x] P0.3 DESIGN.md + BRANCH_FIRE.md + KILL_TEST.md (Docker)
- [x] P0.4 QC_DEFENCE.md
- [x] P0.5 DESIGN_SUMMARY.md
- [x] P0.6 STOP: DESIGN READY
- [x] P0b.1a proto/render.py (12 files from gen_proto instance)
- [x] P0b.1b proto/solve_proto.py (parse files -> core.solve_flow -> 10 outputs)
- [x] P0b.1c design_blind/instruction.md + environment/data/ (shipped sample) + docs/charging_rules.md
- [x] P0b.2 BRANCH_FIRE on sample + 3 hidden seeds via rendered files
- [x] P0b.3 STOP: DESIGN BLIND READY (path in DESIGN_SUMMARY.md)
- [x] P0b.4 score design blind fd98e12: NO CORE (EXACT 9/9 on all 5 corpora); wait for master go for G-8 redesign
## Redesign G-8 (master go 02:30): per-depot meter convention lever
- [x] R0 backup design v1 to WORK/design_v1_backup/
- [x] R1 proto2/conv.py + killconv.py; kill rows (a)-(d) on shipped1 hidden1-4 large1 (Docker conv-20261101T0240/logs/conv1.log ALL_DONE)
- [x] R2 render.py: settlements.csv + tariff.xml versions; docs rule text for meter convention; solve_proto fits shift
- [x] R3 design_blind folder re-rendered (instruction.md + environment/); run fd98e12 real program on rendered hidden corpora (Docker)
- [x] R4 KILL_TEST.md, BRANCH_FIRE.md, DESIGN.md, DESIGN_SUMMARY.md updated (path last line)
- [x] R5 STOP: DESIGN BLIND READY
- [x] R6 score design blind d9d6ab5: DESIGN BLIND PASS (100% lever points lost WRONG; log score-d9d6ab5/logs/score.log)
## Build (master: on PASS continue straight into Phase 1 and gates)
- [x] P1 scaffold via generate_bundle.py; copy to WORK/scaffold_orig/
- [x] P2a WORK/datagen.py (from proto2 render) -> BUNDLE/environment/data + docs/charging_rules.md
- [x] P2b (21853 lines) A5 volume check (>=2000 lines per csv/jsonl; total >=20000)
- [x] P3a solution/solve.py + solve.sh (self-check stages printing check <id> ok) (EXACT 9/9 on 5 corpora; selfcheck 9 ok)
- [x] P3b WORK/check_exact.py independent + override-removal probes (ce.log)
- [x] P4a tests/test_output.py (embedded generator, hidden corpora, OWNED map, mutation tests)
- [x] P4b COST_TABLE, RULE_COVERAGE, EVIDENCE_MAP, UNIQUENESS, LEVERS, RULE_TRACE
- [x] P4c reward.toml + re-embed data
- [x] P5 tests/judge.toml + JUDGE_MAP.md
- [x] P6 instruction.md
- [x] P7 TRUTH.md (sha by script last)
- [x] P8.1 4 QC scripts + validator; A5
- [x] P8.2 oracle x3 / nop
- [x] P8.3 STACKING_CHECK; P8.3b SELF_CHECKS.md; P8.4 PRECHECK CLEAN
- [x] P9 BUILD_REPORT.md + result_154f570.json

## P12 fix v1 (board efdb667, prompt 20261101T0415_fix.md; OUT 20261101_depot-charge-plan/p12_fix_v1_efdb667)
- [x] F0.1 rename session (opencode ses_e6be0c307ffeEjTEnFbIoAnwhZ listed; efdb667 not shown) + read rules files
- [x] F0.2 backup BUNDLE to WORK/qc1_6a88219de6f8 (tree 6a88219de6f8; kit HEAD 5574d77e)
- [x] F0.3 XREF.md + xref_check 0 findings
- [x] F0.4 QC_DEFENCE entries per lever; trap baseline per lever
- [x] F1 Phase 1 recheck rows (DS-21, TS-26, JD-5/8, CL-3, AL-2, AL-27, DS-20, TS-23, JD-16, oracle x3) -> OUT/RECHECK_FIX.md
- [x] F1b DS-21 fix (rule 12 family + shipped non-zero shift East k=28) + regen (TRUTH regen deferred to last)
- [x] F1c kill row 'careful shift search' (Docker): keeps 166/166 lever points (100%) after DS-21 => PAUSED (LEVER GONE AFTER FAIRNESS FIX)
- [x] F2 remaining fixes: NOT applied (paused per master direction)
- [x] F3 deliverables (RECHECK_FIX, PL_NOTE, KEPT, result json) status PAUSED

## P12 fix v2 (board 0d6348c, prompt 20261101T1127_fix.md; OUT 20261101_depot-charge-plan/p12_fix_v2_0d6348c)
- [x] V0 rename (opencode ses_e6a4e8962ffeDIWRmbwx0LdyJx listed); rules read; tree 7e3ade15a78b; kit 5574d77e; fingerprints 0 diff
- [x] V1 digests of all checks before edits (WORK/fix2/digest_before.txt)
- [x] V2 CL-3: shipped data binds (one depot plan != published) via gen_core/datagen; regen data + embed
- [x] V3 AL-27: two-condition rejection rows shipped + hidden (gen_core)
- [x] V4 DS-20: rule 13 sentence (published row for bus not on plan) + fixture? 
- [x] V5 TS-26: relocated copy own seed/tree
- [x] V6 JD-5/JD-8: R9 split (code quality only; behaviour stays test)
- [x] V7 AL-2: tests for flagless default run, writes only into out; criterion for totals from summary.json
- [x] V8 JD-16: end-state test tried, withdrawn (separate verifier, validator 1.12 fixes artifacts); R16 kept, warn recorded
- [x] V9 TS-23 warn recorded; digests after; G7 diff
- [x] V10 WORK docs: LEVERS, COST_TABLE, QC_DEFENCE, EVIDENCE_MAP, JUDGE_MAP, RECHECK_FIX; reward.toml; TRUTH last; xref 0
- [x] V11 gates: stacking, precheck, 4 QC + validator, exe_copy lanes (oracle x3, owner, nop/stub/forgery)
- [x] V12 lever accounting Docker (blind1-3, first-write, all-but-one, careful shift search)
- [x] V13 Tasks_INPUT copy + diff; FIX_REPORT + result json; rename

## P12 fix v3 (board b7fd1ce, prompt 20261101T1402_fix.md; OUT 20261101_depot-charge-plan/p13_fix_v3_b7fd1ce; runs _runs/20261101/depot-charge-plan/fix3-20261101T1405)
- [x] W0 rename (opencode ses_e69c14e90ffem2YaiTNNAzxPD8 listed); rules read; tree 3e4d3ee74385; kit 5574d77e; fingerprints qc 12/0, gen 160/0
- [x] W1 digests before (fix3 logs/digests_before.txt)
- [x] W2 instruction.md:23 names every summary figure except non-single ones (IN-16/JD-15)
- [x] W3 judge.toml R17 + R10 completeness only (JD-14); weights unchanged
- [x] W4 digest after: only instruction.md + tests/judge.toml changed; + solution/TRUTH.md (regen by truth.py: judge sha, R17 name); xref 0
- [x] W5 WORK docs: JUDGE_MAP, QC_DEFENCE rows (IN-16, JD-14, JD-15, AL-1, AL-6, QL-5); judge mid + pred final
- [x] W6 gates: stacking_check -> OUT; precheck CLEAN; 4 QC scripts + validator
- [x] W7 Tasks_INPUT rsync + diff -rq + tree shas
- [x] W8 FIX_REPORT.md + result json; rename

## Harden r3 (board c5b188a, prompt 20261101T1733_harden.md; WORK h3_a1/; OUT 20261101_depot-charge-plan/harden_r3; runs _runs/20261101/depot-charge-plan/harden3-<TS>)
- [x] H0 rename (opencode ses_e68fe1c71ffeym7Th9Qjg0sxHB listed); rules read; tree 088691cb6539; kit 5574d77e; fingerprints qc 12/0 gen 160/0; a1 copied to OUT/gate_run_a1
- [x] H1 trajectory read (files opened w/ steps, rules implemented, literals, where checking stopped) -> only WRONG documented case: derate above base (a1 min vs rule 11 replace)
- [x] H2 fuzz: shipped/hidden/hidden_reorder/large 300 seeds each, all MATCH (logs harden3-20261101T1746/h3fz_{a,b,c}.log)
- [x] H3 OUT/TRIP.md (uplift proto fuzz 300/300 DIFF, 8 plan docs each)
- [x] H4 proto hidden folders + kill table (Docker) h3kill.log ALL_DONE; a1 0/72
- [x] H5 judge redesign (proto/judge.toml 19 crit, probes 68.2%) a1 25.0/31.8/38.6
- [x] H6 OUT/DESIGN.md -> DESIGN READY; waiting for go (Phase 2 not started)

## Harden r3 Phase 2/3 (go 19:54)
- [x] B1 backup BUNDLE tests/solution/ -> h3_a1/before/, digest; assemble reproduces current test_output.py
- [x] B2 gen_core.py uplift branch + asserts (lim<=room, non-uplift bytes == hidden render) 300 seeds; old renders byte-identical 300 seeds x shipped/hidden/large -> h3fz_u2 300/300 DIFF all 8 plan docs, bytes true 300, walk 105 (max +7), ref max 3.29 s; old renders identical by construction (G7 additions only)
- [x] B3 assemble_tests: u1..u9 x 8 docs w5; reward.toml 0.5/557, 0.5/44; old check text byte-identical (G7)
- [x] B4 judge_spec -> judge.toml (19 crit); selfcheck +4 -> solve.sh
- [x] B5 isolation row (raise on u5) + full tests oracle/a1 verifier time x2 in Docker -> iso_u5 517/557 (u5 40 only); oracle 89 s, a1 52 s vs 2700
- [x] B6 WORK docs LEVERS/COST_TABLE/QC_DEFENCE(corr 1 grep)/EVIDENCE_MAP/JUDGE_MAP; judge regrade a1 (corr 6) -> done 20:1x (COST_TABLE in G2)
- [x] B7 TRUTH by script (truth.py text +uplift, 13 self-checks); xref 0 (XREF.md settlements entry: judge.toml dropped)
- [x] G1 stacking_check -> OUT/STACKING_CHECK.md (TS-26/AL-28 hints pass by hand)
- [x] G2 measured COST_TABLE all kill programs on final tests -> COST_TABLE.md Harden r3 section
- [x] G3 precheck CLEAN (only A3 120-check warn = TS-23; 0 IN17/G5), 4 QC scripts exit 0 warns 0, validator 40 pass 0 fail (OUT/PRECHECK.txt, VALIDATOR.txt)
- [x] G4 gate lanes oracle x3, owner, nop/stub/forgery -> 1.0 x3, owner 1.0, nop 0.0, stub 0.0018, forgery 0.0287; verifier max 124.6 s
- [x] G5 Tasks_INPUT sync, diff -rq empty (tree 07c7f6bfb71c both)
- [x] G6 HARDEN_REPORT, result json, rename
