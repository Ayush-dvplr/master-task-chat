# P12 v3 r4 LOG (c958296)
21:06 P0.0 rename ok, tree sha 7b0bc6233c65 match, kit 976c1666, lock taken
21:08 P0.2 read findings/single_lever/local_score/QC_DEFENCE (line 76 says 42 checks: stale, fix with W2)
21:10 P0.3 xref 28 entries 0 findings
21:14 P0.4 before_v3r4 copy (tests solution environment instruction.md); outputs_capture.py -> trap/outputs_before_v3r4.txt: 39 corpora (shipped + 38 hidden), all exit 0, 389 lines
21:13 P1 six rows written to OUT/RECHECK_FIX.md: REAL 6 (fix 5, keep W2), FP 0, UNSURE 0
21:20 P2.1 engine-rules.md + STATIC_NOTE_TEXT copy: drop-order sentence after 'An entry survives the window filter' (+3 lines; test_output.py lines after 1728 shift +3); notes match True; emit diff IDENTICAL; WORK cites engine-rules.md >=39 shifted +3 (DESIGN 2, LEVERS 5, QC_DEFENCE 5); QC_DEFENCE W-03 42->46; XREF 4 entries added
21:23 P2.2 14 lines 'settles to its whole scenario report.' -> '..., cadence and capture count aside.' (9 descriptions now :2923 :2928 :2933 :2938 :2943 :2958 :2963 :2978 :3003; 5 docstrings :2595 :2610 :2615 :2630 :2655); diff vs before: 1 insert (note text 1730-1732) + 14 changed lines
21:27 P2.3 solve.py Fraction: bench_row upkeep Fraction(cells) (:209, covers exact_bench sums :489 and carried), upkeep_figure Fraction(scale) (:602 same target), target Fraction(...) (:697), carried sum start Fraction(0) (:699); outputs_capture after == before (39 corpora, 389 lines, cmp OUTPUTS_IDENTICAL); no pycache
- 21:16 P2.4 M3 done: TRUTH One fact wrong header "Tests channel points earned out of 172 by the oracle with one rule changed:", third column removed; grep found no other overall/judge scores in bundle.
- 21:17 P2.5 F1 done: TRUTH Channel A sentence rewritten to code (deviation: instance_scenario_visible compares whole, cadence modulus test compares classes only); XREF value fixed; xref 32 entries 0 findings; solve_py_sha256 rewritten by script LAST -> 20987612aa54...
- 21:22 P2.7 side effects: AL-27 (from IN-16) new drop-order sentence is triggered by 9 shipped entries + charter_cap_surplus/dead_window corpora (var_precedence score pending); DS-27 (from AL-7) TRUTH grep no process narration. xref 32/0; PRECHECK CLEAN; structure/instruction/tests/judge_qc exit 0 (tests_qc WARN A3 46 only); no pycache.
- 21:24 P2.8 stacking_check exit 0 -> OUT/STACKING_CHECK.md, hand corrections (TS-26 false, PASS).
- 21:26 P2.9 Docker chain started: /tmp/opencode-logs/match-replay-desync-audit-p12v3r4-20261024T211754-b81f (copies exe_copy plain/--owner-only/--stub; warm then oracle x3, owner x1, nop x1, stub x1)
- 21:21 P2.6 done: variants rebuilt in trap/variants_v3r4_after, scores_after_v3r4 all equal r3 (perentry/opening/cancelled_draw/norenew 97, renew_strict 162, precedence 161, tiebreak 167, lifo 1, mut_* 169, ctrl_all_old 160, carry_eleven 12, oracle 172); failing-test lines identical except temp paths. test_output.py diff: 3 note lines + 14 description/docstring lines.
- 21:22 P2.9 Docker ALL_DONE 21:21:37: oracle x3 1.0, owner-only 1.0, nop 0.0, stub 0.0058; chain.sh+runs.log -> OUT/docker_block
- 21:23 P3 done: OUT RECHECK_FIX.md (91 lines), PL_NOTE.md, result_c958296.json, STACKING_CHECK.md, docker_block/; temp dir removed; lock released; tree sha 1cd9fe77061b
