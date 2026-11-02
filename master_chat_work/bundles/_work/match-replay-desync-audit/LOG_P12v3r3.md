# LOG P12 v3 r3 (878a0e4). Prior: LOG_P12v3r2.md
- 18:19 name_session.py 878a0e4 exit 0 (opencode listed); tree sha 666226360826 match; kit 976c166611e5
18:21 P0.2-P0.4 ticked (xref 27 entries 0 findings; before_v3r3 copy made). Compaction 1 at 18:20.
18:52 P0.5 PROBE_DIAGNOSIS.md: decode 0, settlement 55 (11 tests), runtime-only 30 (6 trap tests, branch explosion)
18:58 P0.6 ticked (BEFORE = r2 AFTER scores, tests/solve unchanged; extra one-rule variants measured on AFTER, QC v3 figures quoted for BEFORE). Lock taken.
18:58 P2.1 ticked: solve.py 4 CTRL rules fixed (warded zero-fill, carry reset, stepped stored 0, index modulo); shipped outputs old vs new diff -r IDENTICAL (9 files); candidate 200 CTRL-C figure now 1502353130b5 (QC rule figure), old fa89167d0052; verifier _peel already follows notes
19:02 P1 rows written to OUT/RECHECK_FIX.md (6 rows: F1-F4 REAL fix, M1 REAL fix, W1 KEEP). Next P2.2.
19:13 P2.2 done: 4 damage tests (weight 3) + _plant_damage/_check_damage; RULE_COVERAGE.md 4 rules, each mutant 169/172, oracle 172/172. P2.3 done: heft 1 for trap/damage sets + _check_unbound (max ratio 0.341); whole-doc compares kept.
19:15 P2.4 done: solve.sh 60->182 lines, self-check heredoc (:62-182) builds R7/R8/R9 inputs under /app/out/selfcheck, prints check R7/R8/R9 ok, rmtree; local run outputs byte-identical; variants perentry/norenew/cancelled_draw each fail own check; R7-R9 wording kept; JUDGE_MAP.md written; QC_DEFENCE :53,:55 updated. P2.5 done: R11 = M1 exact wording, weight 3; judge 11 criteria +17/-8.
- 19:16 P2.7 started: single_lever.py +var_precedence/var_renew_strict/var_tiebreak/var_lifo; variants -> trap/variants_v3r3_after (+mut_* and var_ctrl_all_old); nohup chains trap/run_after_v3r3.sh and trap/run_probe_after.sh
- 19:16 reward.toml test_output weight 0.003125 -> 0.0029069767441860465 (0.5/172) after 4 new tests
- 19:22 F4 follow-up: tiebreak mutant light (heft 1) so var_tiebreak separates (was hidden by cap); trap flipped/warded compare data_quality via _dropped_view (drop counts summed) so precedence swap no longer cascades into traps; reran AFTER variant chain + probe
- 19:23 Always 11: generator emit -> diff -r vs environment/data IDENTICAL; notes match shipped True; no pycache
- 19:23 grammar_check.py on shipped data + new oracle reports: RESULT 11/11 (single hit each)
19:29 P2.6 TRUTH.md edited by script ($TMPDIR/opencode/p26/truth.py): F2 chained-mask wording, stage 3/4 CTRL rules, counts 46/42/172, trap heft-1 + damage tests, judge R11 + self-check, One fact wrong table, pitfalls, solve_py_sha256 b18c6baed8a9 (337 lines).
19:31 P2.8: XREF.md updated (28 entries, 0 findings); precheck PRECHECK CLEAN (A3 warn 46 checks only; AL-27 4 rule rows); live structure_qc exit 0; stacking_check exit 0 -> OUT/STACKING_CHECK.md PASS after hand corrections; side effects JD-5 -> JD-2/JD-7/JD-9/JD-15/IN-8 and JD-7 -> JD-15 rechecked; no pycache.
19:32 P2.9 Docker chain started: /tmp/opencode-logs/match-replay-desync-audit-p12v3r3-20261024T193126-baa8 (runs.log ends ALL_DONE).
19:36 P2.9 Docker ALL_DONE 19:35:10: warm rc 0; oracle-1/2/3 1.000; owner-only-1 1.000; nop-1 0.000; stub-1 0.0058 (1/172); oracle agent log prints check R7/R8/R9 ok; chain.sh + runs.log copied to OUT/docker_block/.
19:56 P2.7 probe after: 75/172 (43.60%), overall 30.63 @17.65, 66.80 @90; gate PASS, kill rule not hit; COST_TABLE + RECHECK_FIX updated.
19:57 P3 reports written (RECHECK_FIX, PL_NOTE, STACKING_CHECK, result_878a0e4.json); temp dirs removed; no pycache; tree sha 7b0bc6233c65; lock released; rename run.
