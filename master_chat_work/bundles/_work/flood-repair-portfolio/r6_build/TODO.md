# r6_build TODO (board ea04435, harden r6 build)
Prompt: master_chat_tasks/prompts/issued/flood-repair-portfolio/20261102T2014_harden.md
R (scratch/logs) = /Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/r6b-20261102T2018/
OUT = master_chat_work/20261102_flood-repair-portfolio/harden_r6
## Phase 0
- [x] rename ea04435 (opencode ses_e63461152ffeiaRlDOTEC3adZ8); read rules; fingerprints qc 12/12 gen 160/160 unchanged; kit 5574d77e; tree 7d68065946fd
- [x] read r6 design, gen_r6.py add_crowd, test_output.py book generator, P lines; OUT/TRIP.md (20:23)
- [x] read a4 trajectory: which probe acts skipped (step ids) (20:40)
## Phase 1
- [x] snapshot BUNDLE to R/scratch/bundle_before; expected-doc digests of old checks (before) (20:29, R/scratch/digest/before.json)
- [x] edit test_output.py generator: crowd rounds own RNG (krng seed*37+9011, burn-and-replace idx 0,10..50 after capped); H pins updated; books differ from r6_budget -> re-measure in G1 (20:31)
- [x] 300-seed shape asserts 0 errors (logs/shape300.log; _check_bounds in _assemble = contract limits); digests after == before for old checks (20:33)
- [x] leak check: agent image copies shipped data only; /tests root-private, expected docs in verifier memory; measured expected dirs 0700; _launch kills group after every run (20:48)
- [x] verifier oracle wall time 655.809117 s (oracle1, reward 1.0); below 2430 s, no oracle speedup needed
- [x] judge.toml probes R9-R11 w3 (renumber R12-R15, positive 41, reward.toml judge 0.5/41) + solve.sh witnesses (Docker solvesh2 rc 0, R1-R11 ok); a4 graded low 29.27 mid 29.27 high 56.10 (20:38)
- [x] WORK docs: LEVERS, QC_DEFENCE, EVIDENCE_MAP, JUDGE_MAP; witness copied; TRUTH.md regenerated last with three measured oracle receipts; xref 36 entries 0 findings
## Phase 2
- [x] G1 re-measure kill table on verifier books: P/P_x4 WRONG 3/3, P_inf EXACT 3/3, loss 57/108; busy reference max 2.2411 s; all paired P reruns identical; g1.log bare ALL_DONE
- [x] G2 stacking_check -> OUT/STACKING_CHECK.md (static output and hand corrections; 108 unchanged)
- [x] G3 final measured TRUTH refreshed by script; precheck_final.log ends PRECHECK CLEAN, 4 QC scripts exit 0; validator_final.log 41 passed/0 failed/0 warnings; xref 36 entries/0 findings
- [x] G4 exe_copy lanes: oracle x3 1.0 (655.809117/651.167954/527.382443 s), owner 1.0 (500.797812 s), nop 0.0 (513.554693 s), stub 0.0093 = 1/108 (500.823477 s), forgery 0.1481 = 16/108 (437.477505 s); all logs ALL_DONE
- [x] G5 paid__HrEL8N2 final tests 51/108 = 47.222222%; reruns_identical passes, no negative fires; verifier 513.155045 s; predicted final 38.245257/38.245257/51.659892
- [x] G6 rsync -a --delete Tasks_INPUT; diff -rq empty/exit 0; BUNDLE and Tasks_INPUT tree d4059c875b73; no __pycache__
## Deliverables
- [x] OUT/TRIP.md (62 lines), STACKING_CHECK.md, HARDEN_REPORT.md and result_ea04435.json validated; zero own workers/containers; final command reserved for required ea04435 rename
