# TODO d62ffe6 tariff-engine-audit-repair (P9 harden r1)
Prompt: master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261024T2317_harden.md
(build TODO archived: TODO_build_a5f8657.md)

## Phase 0
- [x] rename session d62ffe6 (opencode ses_e90f673bcffebCnCl2i7pl1t46; codex no match)
- [x] read COMMON_RULES_v3, round notes C/E/F/G, LEVER_RULES_v1, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2
- [x] read WORK DESIGN (XREF.md missing, no baselines.json), LEVERS, QC_DEFENCE, XREF, baselines.json; TEST_DEPTH.md 21-67 + result.json
## Phase 1 (no edits to BUNDLE)
- [x] A: genuine? diff -rq copy vs BUNDLE, result.json, verifier stdout
- [x] lever table from reward-details.json
- [x] trajectory autopsy
- [x] OUT/agent_program/ saved
- [x] fuzz re-run >=300 corpora on agent program (OUT/fuzz/)
- [x] prototype rewritten levers, shrunk corpus per lever (OUT/prototype/proto_run.txt)
- [x] OUT/DIAGNOSIS.md -> STOP "DIAGNOSIS READY" (waiting for go)
## Phase 2/3: after go
- [x] GO received 00:3x: N1, N2, N3; LV-TR-4/TR-2/TR-1 uncounted gates; N1 rule spelled; N3 accepted; shipped account totals under tier 1; fix tests:5526 + byte-identical proof; write XREF.md; R12/R13; lessons only in DIAGNOSIS; no LEVER_RULES edit
## Phase 2
- [x] P2.1 crash fix in test_output.src.py (_Ledger int standing_charge) + embed; prove byte-identical old vs new on shipped + seeded tiers (OUT/crashfix/)
- [x] P2.2 api_contract.md: N1 allowance column + share rule + re-share; N2 Month calendar + standing per month; N3 account quantity tiers; :77-79 de-enumerated; regression row allowance
- [x] P2.3 refengine.py new rules; datagen.py (allowance, account totals <= tier1 up_to, cases too, one-pass exact); regenerate CI data; check shipped package runs
- [x] P2.4 solution/solve.py new rules; solve.sh check r12/r13
- [x] P2.5 test_output.src.py: _Ledger, _assemble allowance, _corpus lever flags (Plan X: FR N1+N2, LT N1+N3, A N2+N3), _assert_bounds plants, _case_texts allowance
- [x] P2.6 visible tests/repo consistency; judge.toml R12/R13; embed; reward.toml; run_checks oracle=all pass, agent program score
- [x] P2.7 WORK docs: LEVERS, COST_TABLE, RULE_COVERAGE (rule_mutants), QC_DEFENCE, JUDGE_MAP, DESIGN Harden round 1, XREF.md + xref_check 0; TRUTH sha256 last (sha + golden provenance deferred to after Docker block)
## Phase 3
- [x] stacking_check -> OUT/STACKING_CHECK.md (STACKING PASS; tool hints TS-26, AL-28, G3 corrected by code; G10 all-but-one PASS with measured rubric 62.5, FAIL with 90)
- [x] reflex gate agent program <=0.20 + single-lever table (0.1811 = 23/127; OUT/single_lever/)
- [x] QC scripts + precheck CLEAN (judge R12/R13 moved after R11 for J2 sequential ids, "some" reworded J11; validator repo-patch GATE PASS after solve_py_sha256 update; playground removed upstream)
- [x] Docker block oracle x3/owner/nop/stub/forgery (1,1,1 / 1.0 / 0.0 / 0.0 / 0.2047)
- [x] HARDEN_REPORT.md + result_d62ffe6.json
