# TODO harden r4 ea94780 (prompt master_chat_tasks/prompts/issued/flood-repair-portfolio/20261101T1957_harden.md)
R=/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden4-20261101T2000
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/harden_r4
W=WORK/h4_rule ; older r3 TODO/LOG copied to TODO_harden_c510591.md / LOG_harden_c510591.md

## Phase 0
- [x] rename (opencode ses_e687bf897ffeELcDEuw18nYS48), read rules, fingerprints qc 12/12 gen 160/160, kit 5574d77e, tree 931f8f817d76
- [x] read r3 HARDEN_REPORT/DESIGN/TRIP, a3 score, contract.md, solve.py, a3 derive_report.py
- [x] OUT/TRIP.md (a3 rule locations file:line)
## Phase 1
- [x] DESIGN candidates (2-3 rules): A shared-crew cap 3 chosen; B override cap, C households knapsack, D fewer-ids tie rejected
- [x] prototype chosen rule (CAP 4; cap 3 changed shipped R62233): proto/solve.py, proto/capgen.py, shape300 SEEDS_OK 0-300, SHIPPED_DIFF_ROUNDS []
- [x] kill-table programs: programs/a3_natural(.diff post-step), a3_correct, a3_prefilter, a3_unchanged; a1/fw/abo reused
- [x] kill table in Docker (kill3_capfeas.log ALL_DONE; cap-aware feasible; a3nat/a3pre/a3unc 3/25 per H+Mc, a3cor 25/25, a1/fw/abo 0-3)
- [x] embedded-reference prototype crosscheck.py (ledger _capped vs proto solve, 300 seeds + Hc/Mc + shipped) -> logs/crosscheck.log
- [x] judge redesign draft + a1/a3 low/mid/high
- [x] instruction time-budget sentence (C1 check)
- [x] OUT/DESIGN.md -> DESIGN READY / NO CORE; stop
- [x] OUT/HARDEN_REPORT.md + result_ea94780.json (PAUSED, DESIGN READY); Phase 2/3 wait for go
## Phase 2 (go 22:31, master corrections 1-7)
- [x] docs grep portfolio/conflict/shared/mode (one definition only, contract.md:62; crews.tsv mode 1454 exclusive / 946 shared)
- [x] digest before (h2_a1/digest_checks*.py) -> h4_rule/digest_before.txt
- [x] contract.md:62 + instruction.md:15 sentences
- [x] solution/solve.py from proto (count state)
- [x] test_output.py: embedded generator capped branch, _BOOKS capped+sha, _Ledger _capped, _feasible cap
- [x] solve.sh R7 crowded/R8 tie stages; judge.toml rebuilt 12 criteria (judge_qc PASS); reward.toml 0.5/32
- [x] digest after + diff listed (h4_rule/digest_diff.txt); untouched checks identical
- [x] Docker: oracle on new tests (local verifier run), shape asserts, cost table all kill programs, fork probe (verif_all.log ALL_DONE pending abo; fork SURVIVORS 0)
- [x] WORK docs: LEVERS, COST_TABLE, QC_DEFENCE (IN-16/DS-21, IN-17, TS-19, TS-26), EVIDENCE_MAP, JUDGE_MAP; TRUTH.md by script; xref 0 (QC_DEFENCE, EVIDENCE_MAP, JUDGE_MAP, TRUTH v1, xref 0 done; LEVERS + COST_TABLE r4 written 23:23; TRUTH re-run 23:3x done)
## Phase 3
- [x] stacking_check -> OUT/STACKING_CHECK.md
- [x] precheck CLEAN, 4 QC scripts + validator + judge_qc 0 FAIL
- [x] gate lanes oracle x3, owner, nop/stub/forgery (lane1 oracle 1.0 x3 verifier 102.5/99.4/105.8 s; lane2 owner 1.0 101.2 s; lane3 nop/stub/forgery started 23:21)
- [x] Tasks_INPUT sync (7d68065946fd), diff -rq empty; tree shas
- [x] re-grade a3/a1 on final judge; HARDEN_REPORT, result json DONE; rename; final reply
