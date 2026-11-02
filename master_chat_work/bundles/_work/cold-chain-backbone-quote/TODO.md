# TODO 57a2dd7 cold-chain-backbone-quote

## Phase 0
- [x] P0.1 GEN and QC fingerprints checked (160 / 12 files, diff 0) 16:53 IST
- [x] P0.2 WORK/PREMORTEM.md written (append DW 16/17 timing when dwtime.log shows ALL_DONE)
- [x] P0.2b append measured DW 16/17 table to PREMORTEM section 5
- [x] P0.3 WORK/DESIGN.md
- [x] P0.4 WORK/QC_DEFENCE.md
- [x] P0.5 WORK/DESIGN_SUMMARY.md (<=40 lines)
- [x] P0.6 STOP: DESIGN READY given 17:21; go received 17:35 with master changes M1-M11 (see LOG)

## Phase 1-9 (after go)
- [x] P1 scaffold from GEN (package `task`), copied to WORK/scaffold_orig 17:29
- [x] P2 datagen.py -> environment/ci (A5 ~30k lines, 8 formats, 11 files) 17:45
- [x] P3 solve.py (built by build_solve.py from solve_body.py + fixed_repo) + check_exact.py PASS 17:52
- [x] P4 test_output.py, COST_TABLE (DW 17 row pending dwbench ALL_DONE), RULE_COVERAGE, EVIDENCE_MAP, LEVERS, reward.toml 18:24
- [x] P5 judge.toml (judge_qc PASS) + JUDGE_MAP; solve.py prints altered copy, rejected list, method 18:27
- [x] P6 instruction.md (instruction_qc PASS) 18:30
- [x] P7 TRUTH.md 18:40 (rerun finalize_truth.py after any solve change)
- [x] P8 QC scripts, validator, oracle x3, nop, stacking, precheck
- [x] P9 BUILD_REPORT.md, result_57a2dd7.json

## Master changes (go 17:35) to honour
- [x] M1 (17:59 check_exact --ties PASS) tie book T (6 small, exactly 2 optima, w3); check_exact confirms T picks by exhaustive enumeration
- [x] M2 (COST_TABLE 18:24) COST_TABLE: LV-CC-3 recorded as secondary stated-rule lever (report-only 69.4), no weight raise
- [x] M4 (contract 49-53, EVIDENCE_MAP row) contract defines corridor position (depot 0, rank by corridor order then slot, consecutive ints); equal slots in a corridor -> stated rule; EVIDENCE_MAP row
- [x] M5 (grep clean 18:30) no method hints: no heuristic/approximate/exhaustive/dynamic programming/too slow/test at largest size in instruction.md or api_contract.md; G5 sentence exact: "Each output document is graded whole on fresh books, and only an exact match counts."
- [x] M6 (Docker 12-17 in COST_TABLE 18:33; tuned DW 15.4 s at 15, 128 s at 17; ref <=0.16 s) Docker timing reference / proto DW / tuned DW per cold-room count 12-17 in COST_TABLE; tuned DW <8 s on hidden size -> move hidden to 16-17; reference <=1 s per project
- [x] M7 (TRUTH Verification table 18:40) TRUTH states per-book timeout formula + oracle Docker time per book
- [x] M8 (JUDGE_MAP 18:27) JUDGE_MAP shows R9/R10 performable in built image
- [x] M9 (local stub 18:00: oracle/kmb/greedy/perlink/report_only silent, copier fires; re-confirm in P8) N1 fires nothing for oracle and single-lever wrong variants, fires for copier
- [x] M11 stop at "BUILD READY: <bundle path>", no probe
- [x] COST_TABLE: replaced DWBENCH_17 row when runs/dwbench_docker.log shows ALL_DONE

# Wave 1 harden 678c839 (27 Oct 2026, prompt master_chat_tasks/prompts/issued/cold-chain-backbone-quote/20261027T1110_harden.md)
- [x] W0 date, session rename (opencode ok, codex no match), rules read, kit HEAD 5574d77e, fingerprints 160/12 match 11:20
- [x] W1.1 Phase A diff run staged tests/ environment/ vs BUNDLE: empty (staged .kiro-staged-tasks copy identical incl judge.toml) 11:24
- [x] W1.2 diagnosis (trajectory 60 steps 16 min; step 22 at 7.5 min first-write exact frontier DP citing span 4; tests 84/84; judge lost R3,R5) 11:34
- [x] W1.3 lever design: drop E_BAD_SPAN + size-bound sentence; wide books = blocks at cut sites, 25-34 cold rooms, shuffled positions; ref = block cut + per-block DW (proto/ref.py, 0 mismatches vs _enumerate) 11:34
- [x] W1.4 (12:17, design 2 holds; KILL_TEST.md) WORK/proto/ prototype hidden instances + reference + kill solvers, Docker timing, WORK/KILL_TEST.md
- [x] W1.5 (12:18, OUT/DESIGN.md written, waiting for go) OUT/DESIGN.md, STOP "DESIGN READY"
- [x] W2 (after go 12:20) edits, hidden corpora, tests, judge P-5, docs, XREF
  - [x] W2.0 snapshot runs/pre_w1 + old book digests 12:23
  - [x] W2.1 fixed core general exact, SPAN dropped (parsers) 12:30
  - [x] W2.2 bookgen/datagen regenerated shipped ci (no span regularity) 12:35
  - [x] W2.3 contract E_BAD_SPAN + size clause removed, hole grep 0 12:37
  - [x] W2.4 test_template general _optimum, wide_1..3 + 6 criteria (108 positive), old 8 books byte-identical 12:43
  - [x] W2.5 sweep300 SWEEP PASS 300 seeds (worst ref 16.55 s/project under 4-proc load) 13:50
  - [x] W2.6 solve_body self-check probes, solve.py + test_output.py rebuilt, oracle 108/108 local 12:52 (reward.toml pending judge)
  - [x] W2.7 Docker kill+cost on final books (runs/cost_w1.sh started 13:03, logs cost_w1_a/b.log; frontier_bfs variant rebuilt 13:05) (done 13:33, COST_TABLE wave 1)
  - [x] W2.8 judge P-5: judge.toml 13 criteria (pos 32, probes 21), judge_qc PASS, reward.toml, artifacts core.py, solve self-check tie/defects 13:02
  - [x] W2.9 docs + XREF (xref 0 findings 13:38)
- [x] W3 gates (14:03: stacking PASS, PRECHECK CLEAN, QC 0 FAIL, validator 9 FAIL from core.py artifact, oracle x3 1.0 owner 1.0 nop 0 stub 0 forgery 0.1944, Tasks_INPUT synced, tree b2df10e170e9): stacking, cost table, precheck, Docker oracle/owner/nop/stub/forgery, sync Tasks_INPUT, report, result json

# Law-1 fix 25c745d (27 Oct 2026, prompt master_chat_tasks/prompts/issued/cold-chain-backbone-quote/20261027T2025_fix.md)
- [x] L0 date, rename (opencode ok, codex no match), rules read, kit HEAD 5574d77e, fingerprints 160/12 match 20:32
- [x] L1 (20:46, runs/time_before.log) Docker timing eac8712 + DW per project on old books + shipped data
- [x] L2 (20:48) OUT/DIAGNOSIS.md
- [x] L3 (20:54 tests rebuilt, G7 3 hunks, AST only _fresh_book_parts, sweep PASS 300) fix _fresh_book_parts cold-room range in test_template, rebuild tests, sweep300, AST compare, G7 diff
- [x] L4 (21:31 xref 0, TRUTH by truth_l1+finalize_truth) WORK LEVERS/COST_TABLE/QC_DEFENCE/XREF, xref 0, RECHECK_FIX, TRUTH last
- [x] L5 (21:27 runs/kill_l1_{a,b}.log ALL_DONE, eac8712 84/108) kill table Docker on final data (+eac8712)
- [x] L6 (21:38 STACKING PASS by hand split, PRECHECK CLEAN, QC 4 PASS, validator 41/9 pre-existing) stacking, precheck, QC, validator
- [x] L7 (21:40 gates oracle x3 1.0 owner 1.0 nop 0 stub 0 forgery 0.1944)
- [x] L8 (21:45 Tasks_INPUT synced diff empty, tree 61ec481d33a6, FIX_REPORT, result json)

# P12 fix QC v1 (28 Oct 2026, prompt master_chat_tasks/prompts/issued/cold-chain-backbone-quote/20261028T0307_fix.md, board 5951927)
- [x] F0 date, rename (opencode ok, codex no match), rules read, kit HEAD 5574d77e 03:10
- [x] F1 (03:12 xref 0; trap baseline = kill_l1_parsed.json + p12_trap old-tests run) Phase 0
- [x] F2 (03:44) Phase 1 recheck 16 findings -> OUT/RECHECK_FIX.md
- [x] F3 (03:30 runs/p12_digests_before.log) digest table of every expected doc of every hidden book (before)
- [x] F4 (03:40 400 small vs _enumerate 0 bad; 2648 calls old==new 0 mismatch; after digests identical except rejections) fix 1 DS-24 independent verifier solver + WORK cross-check (300 small vs _enumerate, all hidden+shipped vs oracle) + Docker timing
- [x] F5 (03:32 tests rebuilt, G7 diff runs/p12_g7_tests.diff all hunks named) fixes 4,5,9,10,14 in test_template; rebuild tests; G7 diff; digests equal
- [x] F6 (03:25) fixes 6,7,11,15 judge.toml; 8 instruction.md; 12 task.toml; 13 solve.py
- [x] F7 (04:50) TRUTH (fixes 2,3) by script last; XREF; RULE_COVERAGE row
- [x] F8 (04:50) touched rules, vacuity, side effects, precheck, stacking, trap survival
- [x] F9 (04:50) Docker gates oracle x3 owner nop (warm image first)
- [x] F10 (04:50) sync Tasks_INPUT, KEPT, PL_NOTE, result json, tree sha
  - [x] F8a (04:50) trap chain runs/p12_trap.log + p12_trap2.log (kmb, mutant unknown_before_dup) ALL_DONE -> trap survival table, RULE_COVERAGE row, truth_p12.py scores

# P12 fix QC v2 (28 Oct 2026, prompt master_chat_tasks/prompts/issued/cold-chain-backbone-quote/20261028T1205_fix.md, board 905cf6e)
- [x] V0 date, rename (opencode ok, codex no match), rules read, kit HEAD 5574d77e 12:21
- [x] V1 Phase 0: QC_DEFENCE exists; xref 0; trap baseline perlink 94 kmb 81 dw_global 24 report_only 46 (runs/p12_g5.log, p12_trap.log)
- [x] V2 Phase 1 recheck 5 items -> OUT/RECHECK_FIX.md (12:35; 4 REAL fix, 1 KEEP)
- [x] V3 digests before (runs/v2_digest_before.json 12:52)
- [x] V4 fixes: judge R10 R5; solve_body far-book print; test_template TS-26 guard; rebuild tests; G7 diff runs/v2_g7_tests.diff (12:58)
- [x] V5 rejection book timing Docker (0.04 s, 11/54); TRUTH by script last 12:59
- [x] V6 (13:48) touched rules, vacuity, side effects, precheck, stacking, trap survival
- [x] V7 (13:48) Docker gates oracle x3 owner nop
- [x] V8 (13:48) sync Tasks_INPUT, KEPT, PL_NOTE, result json

# P12 fix QC v3 (28 Oct 2026, prompt master_chat_tasks/prompts/issued/cold-chain-backbone-quote/20261028T1553_fix.md, board b0aca9b)
- [x] X0 (15:54) date, rename (opencode ok, codex no match), rules + playbook 1b read, kit HEAD 5574d77e, BUNDLE == QC v3 copy (diff -rq empty)
- [x] X1 (15:58) shipped-book count by /tmp/ccq-p12v3/count.py on QC copy: widest open link 51 (P9582 L81912) == QC
- [x] X2 (15:55) build_solve regenerates current solve.py identically; edit solve_body.py book_reach; regenerate; diff
- [x] X3 (15:56) TRUTH.md solve_py_sha256 by script (last bundle edit); 42 grep
- [x] X4 (15:56) checks 1-3 (only solve.py+TRUTH.md differ; PRECHECK CLEAN; tests/ identical): diff -rq vs copy, precheck, tests/ identical
- [x] X5 (16:25) Docker block ALL_DONE: oracle 1/1/1, owner 1, nop 0; (warm image; oracle x3, owner x1, nop x1) runs/v3_chain.log ALL_DONE
- [x] X6 (16:28) Tasks_INPUT sync, OUT KEPT.md, RECHECK_FIX.md, result json

# Harden round _a4 (29 Oct 2026, prompt master_chat_tasks/prompts/issued/cold-chain-backbone-quote/20261029T0419_harden.md, board b223662)
- [x] H0 (04:20) date, rename (opencode ok, codex no match), rules read, round limit check (round 2 of 3, no LAST)
- [x] H1 (04:24) trajectory_readout -> OUT/TRIP.md + table
- [x] H2 (04:28) Phase A genuine check (staged tests vs BUNDLE, copy diff, errors)
- [x] H3 (04:35) root cause 4 causes, lever table, autopsy, agent_program, LEAK rows
- [x] H4 (04:40) OUT/DIAGNOSIS.md -> DIAGNOSIS READY, wait go
- [x] H5 (04:55) go with 30% CRASH/TIMEOUT cap -> infeasible (a4 exact; only scale losses) -> PAUSED, HARDEN_REPORT + result json written; no bundle edits


# Cap-60 build (30 Oct 2026 12:00 go, board b223662, layout A: 7 new held-out wide books, P=200, W=115)
- [x] C0 (11:58) backup frozen tree -> WORK/pre_cap60_8ca9c267f59b/
- [x] C1 (12:08) test_output.py: wide_4..10 books, each core w5 report w5 summary w3, own call
- [x] C2 (13:24 TRUTH measured line /200 + finalize_truth sha done) TRUTH.md:24-25 G05-M1 fix; reward.toml recompute; TRUTH sha by script last
- [x] C3 (12:20) reference timing on new wide books (<= 12.5 s each); a4 rescore (<= 60 tests, C+T share <= 60%)
- [x] C4 (13:22) kill table (a4, a4 first-write, DW, sweep, kmb, greedy, perlink) W/T/C
- [x] C5 (13:39: tests 1107 s, worst <= 1507 s) verifier worst case (<= 2430 s), cost table
- [x] C6 (13:24: STACKING PASS, PRECHECK CLEAN mid-build, QC 0 FAIL, validator 1 pre-existing FAIL 1.12, xref 0) STACKING_CHECK, precheck, QC scripts, validator, xref_check
- [x] C7 (13:24 chain runs/gates_cap60.sh started, waits for c5) Docker oracle x3 / owner / nop / stub / forgery (15:08 oracle 1/1/1, owner 1, nop 0, stub 0, forgery 0.1)
- [x] C8 Tasks_INPUT sync + both tree shas; HARDEN_REPORT BUILD DONE; result json (15:15 Tasks_INPUT synced, both trees c10ae543512d, report+json DONE)
