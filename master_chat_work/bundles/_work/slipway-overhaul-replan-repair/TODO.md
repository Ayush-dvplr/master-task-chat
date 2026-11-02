# TODO e2bfbf0 slipway-overhaul-replan-repair harden-g37-a3
- [x] P0.1 date, rename session (opencode renamed; codex no match), rules read
- [x] P0.2 fingerprints QC 12/12 + GEN 160/160 OK; QC HEAD 5574d77e; tree 62dbcde0c809
- [x] P0.3 read bundle: instruction, task.toml, judge.toml, solve, data docs, test_output.py structure
- [x] P0.4 unzip a3 patched_engine.zip -> WORK/a3_program
- [x] P0.5 OUT/TRIP.md (5 lost tests diff, judge criteria earned cheap vs real, levers today)
- [x] P1.1 arithmetic + design
- [x] P1.2 prototypes WORK/proto + kill test in Docker (a3 first + 3-5 generic)
- [x] P1.3 KILL_TEST.md, judge grading of a3 trajectory
- [x] P1.4 OUT/DESIGN.md -> NO CORE (two tries measured)

# bddb388 harden-r2 (1 Nov 2026): live TODO at h2_a3/TODO.md

# 451146f fix-v1 (QC v1 findings), started 17:45 IST 1 Nov 2026
- [x] S1 rename session (opencode OK, codex no match); tree d3c86f82834f; per-file digests WORK/fix1/digests_before.txt
- [x] S2a AL-27 generator (code done; local oracle_fixed 112/112, a3 52/112; 300-seed scan rerun 18:16 with PYTHONPATH stub, fix1-1750/scan/scan.log, read result in S8): legacy ids in precedence(both ends)/frozen/carried/licence/supplement on held rounds; 300-seed assert
- [x] S2b TS-24 (code; fork probe pending in S4) engine run: new session, pgkill, uid 65534 sweep, held ref before run; fork probe
- [x] S2c AL-10 (code; forgery lane pending S4) hardcoded_sample_answers fires on shipped-docs equality; forgery <= stub
- [x] S2d TS-13 (112 pos pts, 49 checks) split delivered_package_shape into 3
- [x] S2e judge: variant (a): R3 deleted + instruction.md:21 deleted; R2 missing/malformed clause dropped; R10 -> crosswalk legacy-id probe (now R9); R18 dropped; renumbered R1..R16 (pos 36, neg -14); reward.toml test 0.5/112, judge 0.5/36; solve.sh SELFCHECK renumbered + check_crosswalk_copy (local dry run all 12 reports ok, 18:11)
- [x] S2f no env data edited (compare_ref equal) so no _SHIPPED_DATA regen; TRUTH.md DS-22 (27 repairs, nine modules), DS-27 (authoring narration removed), AL-7 (measured_*_test_channel), counts 112/36; shas by script 18:16 (redo if solve.sh changes)
- [x] S2g xref_check 11 entries 0 findings (18:20; weights updated, retired names added)
- [x] S3 static gates: stacking -> OUT/STACKING_CHECK.md (AL-28 by hand <=5); precheck PRECHECK CLEAN 0 IN17/G5; 4 QC rc=0 (warns X1 binary, A3 49>35 = TS-23 kept); validator 38/1 S1.12 template artifacts (not a bundle defect)
- [x] S4 Docker lanes (ALL_DONE 18:43: oracle 1/1/1, owner 1, nop 0, stub 0, forgery -0.0089; max verifier 145.8 s): oracle x3, owner-only, nop, stub, forgery (fork probe DONE 18:22: 1 -> 0 survivors; lanes running from 18:23, fix1-1750/lanes/logs/lanes.log)
- [x] S5 kill table (a3 52/112 46.43, lever 0/60; kill_score.txt)
- [x] S6 a3 judge low 3/36 8.3, mid 9/36 25.0, high 9/36 25.0; pred final 35.71
- [x] S7 sync Tasks_INPUT (d3c86f82834f -> b13e6ae6acc3, diff -rq empty, no __pycache__)
- [x] S8 WORK maps (EVIDENCE/JUDGE/QC_DEFENCE/RECHECK_FIX), OUT/KEPT.md, FIX_REPORT.md, result json, rename

# b20fdca fix-v2 (QC v2 findings TS-24 fail, DS-22 minor; TS-20/TS-23 kept), started 22:35 IST 1 Nov 2026
Scratch: _runs/20261101/slipway-overhaul-replan-repair/fix2-2237/
- [x] S1 rename (opencode OK, codex no match); tree b13e6ae6acc3; per-file digests WORK/fix2/digests_before.txt
- [x] S2a TS-24 (22:44; also public copy/engine root filled private, shipped private+rmtree, renamed parent sealed, _drive reads output inside _RUN_LOCK): _reference/_held_reference into private mkdtemp 0700, read into cache, rmtree; audit every verifier path (table in WORK/fix2/PATH_AUDIT.md)
- [x] S2b DS-22 (TRUTH:62 + 108-110 rewritten; other citations ok; shas by script, unchanged values): TRUTH.md:62 citation; recheck all citations; TRUTH 108-110 wording; shas by script last
- [x] S2c xref_check 11 entries 0 findings
- [x] S3 precheck PRECHECK CLEAN (kit 5574d77e: structure/instruction/tests/judge exit 0; warns X1 binary, A3 49>35 = TS-23 kept); log fix2-2237/gates/precheck.log
- [x] S4 lanes ALL_DONE 23:32: oracle 1.0 x3 (131.6/159.2/166.0 s), owner 1.0 171.7, nop 0.0, stub 0.0, forgery -0.0089, lift old 0.6696 -> new 0.0, overwrite old/new 0.0; max verifier 260.6 s
- [x] S5 a3 program tests 52/112 = 46.43% lever 0/60 (unchanged; fix2-2237/a3_score.txt)
- [x] S6 sync Tasks_INPUT 2f83a9bd6a10 both, diff -rq empty, no __pycache__
- [x] S7 OUT: FIX_REPORT.md, KEPT.md, result_b20fdca.json (parses); RECHECK_FIX rows; rename

# 481e976 fix-ql1 (QL1 findings; prompt master_chat_tasks/prompts/issued/slipway-overhaul-replan-repair/20261102T1443_fix.md), started 14:48 IST 2 Nov 2026
Scratch: _runs/20261102/slipway-overhaul-replan-repair/fix3-20261102T1448/ ; OUT master_chat_work/20261102_slipway-overhaul-replan-repair/fix_ql1 ; backups WORK/fix3/*.before
- [x] S1 rename (opencode ses_e6472c329ffe7AMagD1O6kB5lp; codex no match); tree 2f83a9bd6a10 = Tasks_INPUT; digests WORK/fix3/digests_before.txt
- [x] S2a F1 task.toml:12 Optimization -> Debugging (no enforced list in harness; kit 01:42 example + Tasks_INPUT/sentinel-policy-recompute use Debugging)
- [x] S2b F2 p13:8-9 clause; mirrored into test_output.py minted p13 copy (was byte-identical)
- [x] S2c F3 schema doc23+doc25 clauses + F10 doc24 wording; mirrored into test_output.py minted schema copy
- [x] S2d F4/F5 solve.sh (open papers first; R6 per stage; R10 subsets; R4 sets) + local selfcheck dry run
- [x] S2e F6 test_output.py positive earned + new negative -3; F13 docstring/comment; reward.toml
- [x] S2f F7 judge.toml R15/R16 stand-down; judge_qc.py; JD/AL-28 recheck
- [x] S2g F11 TRUTH.md; data digests (_SHIPPED_DATA? AL-18); TRUTH shas by script last
- [x] S2h xref_check 0 (11 entries 0 findings); stacking_check -> OUT/STACKING_CHECK.md
- [x] S3 precheck CLEAN; 4 QC scripts; validator (logs/precheck3.log; validator only S1.12 pre-existing)
- [x] S4 lanes: oracle x3, owner, nop, stub, forgery (+ unrepaired engine fails new positive)
- [x] S5 a4 re-score tests + judge; a3 tests
- [x] S6 sync Tasks_INPUT
- [x] S7 OUT: FIX_REPORT, KEPT, result json; WORK maps (QC_DEFENCE, EVIDENCE_MAP, RECHECK_FIX); rename
