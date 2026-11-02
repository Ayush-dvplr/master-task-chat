# LOG ed7b0c2 flood-repair-portfolio
22:24:47 IST | python3 name_session.py ed7b0c2 | 0 | codex: no match; opencode: [ses_e8c03a050ffe0YJMutfOlJc0ur]
22:26:23 IST | read rule files + checks.json | 0 | done
22:29:54 IST | fingerprint rehash GEN (160) QC (12) | 0 | 0 DIFF 0 MISSING, NO UPSTREAM CHANGE
2026-10-25 22:52:51 | proto variants memo low/mindeg/maxdeg/maxw 60s seed4 tri lattice n160 | exit 0 | all 4 TO; ordered(BFS) memo certifies 0.0s | longrun memo/classic 600s running
2026-10-25 22:57:43 | docker lpsweep tri-lattice diag 1.0 vs 0.7 etc | exit 0 | full tri lattice LP-integral (LP rounding loss 0) -> rejected; diag 0.7 tri LP frac 99-107 vars, lp_round loss 128-782 | redesign to diag 0.7
2026-10-25 23:10:06 | docker pm_docker.py 10 0.7 (6 hidden-shaped instances, --cpus=1) | exit 0 | ALL_DONE; every baseline and every generic exact loses on all 6 except lp_round_ls exact on s2; ref 0.08-0.19 s
2026-10-25 23:10:06 | docker pm_reduce.py 60 (simplicial+domination+split+cover-bound memo B&B) | exit 0 | ALL_DONE; TO on all 6 at 60 s (665k-732k nodes)
2026-10-25 23:13:59 IST | write PREMORTEM.md DESIGN.md QC_DEFENCE.md DESIGN_SUMMARY.md | exit 0 | Phase 0 complete, stopping for go
2026-10-25 23:24:34 IST | generate_bundle.py --name flood-repair-portfolio --archetype domain-calculation --category optimization --seed 558214 | exit 0 | scaffolded; copied to WORK/scaffold_orig
2026-10-25 23:40:26 | python3 -B datagen.py | 0 | shipped book seed 558214 written to environment/data, scaffold data removed, 21199 data lines
2026-10-25 23:40:33 | python3 -B datagen.py | 0 | shipped book seed 558214 written to environment/data, scaffold data removed, 21199 data lines
2026-10-25 23:46:58 IST | docker baselines.py on h1_1..h3_2 (cpus 2, exact 20 s, ILS 10 s) | exit 0 | chose H1=714301(h1_4) H2=721402(h2_1) H3=731503(h3_1); h1_1 rejected (lp+ls exact both large)
2026-10-25 23:46:58 IST | assemble_tests.py + run_tests.py solution/solve.py | exit 0 | 33 checks, 108/108, solve and test reference agree on shipped, H1-H3, M, MS, MR
2026-10-25 23:49:33 | docker python:3.12-slim tmp/time_ref.py (solve.py -I -S, 3 runs) --cpus=1 and 2 | exit 0 | shipped 0.16-0.49 s, H1 0.08-0.12, H2 0.09-0.12, H3 0.08-0.10, M 0.05-0.07; limit 20 s/book kept (ref <=1/40); generic exact TO at 20 s per round at --cpus=2 (baselines logs)
2026-10-25 23:52:01 | python3 -B check_exact.py | exit 0 | 7 books 0 record diffs vs test reference; invariants hold; 315 rounds brute-forced equal; 300 small books bad 0; probes: override blank 27 rounds changed, withdrawn->held 82, shared->exclusive 81, site exclusions dropped 47
- 00:05 value_before_files mutant rewritten (NONPOSITIVE before file faults): 0.861, 5 checks; bookgen blank line after every 97th audit query (rule 'line number counts every line' now exercised); datagen rerun 21223 lines; assemble_tests 1449 lines; solve.py 108/108; rule_mutants.py (23) + mutants (22) rerun loop started (tmp/run_all_mut.sh) exit pending
2026-10-26 00:10 | rule mutants missing_file_silent/nonpositive_unchecked/nonpositive_last_row survived -> bookgen nonpositive kind plants zero-benefit row + later negative row (rng stream unchanged; H1 H2 M sha same, SHIPPED H3 changed); missing-file check now 3 deletions incl both, rc==1, exact stderr line, no docs | datagen+assemble+run_tests exit 0 | 108/108; mutants now fail (105, 102, 102); restarted check_exact, gen300, full mutant loop
- 2026-10-26 00:27 tmp/write_cost.py -> COST_TABLE.md; DESIGN.md sections 3,6,8,9 updated to measured; QC_DEFENCE AL-28/B4/7.4 notes | rc 0
2026-10-26 00:32:22 | TRUTH golden fill; validator 41/0/0; 4 QC PASS; oracle x3 1.0 nop 0.0; PRECHECK CLEAN; fingerprints 0 DIFF; BUILD_REPORT + result json | exit 0 | BUILD READY
