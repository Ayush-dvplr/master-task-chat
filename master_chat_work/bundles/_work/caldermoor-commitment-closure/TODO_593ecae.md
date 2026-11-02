# TODO 593ecae caldermoor-commitment-closure P9 harden r2 (prompt: master_chat_tasks/prompts/issued/caldermoor-commitment-closure/20261024T1817_harden.md)
(after compaction: `date`, re-read prompt, this file, continue at first unticked; never re-run a Docker block whose log has ALL_DONE)
(previous P12 v3 r1 TODO for 8826f3a was all ticked; see LOG.md)

- [x] rename session 593ecae (opencode ses_e920aa324ffez0n5S5KKs72Cf5 listed)
- [x] read rules files (COMMON v3, round notes C/E/F/G, LEVER_RULES, LEAK_LIBRARY, QC_RULINGS, PLAYBOOK v2)
- [x] note: WORK has no DESIGN.md / LEVERS.md / QC_DEFENCE.md / baselines.json (create them this round)
- [x] kit HEAD + fingerprints
- [x] Phase A genuine check (diff copy vs bundle, result.json, verifier stdout)
- [x] causes 1-4, lever table, autopsy, agent_program saved
- [x] OUT/DIAGNOSIS.md (no go needed)
- [x] Phase 2 design new lever (H2/H3/H6) + structural fix for A, B
- [x] Phase 2 implement: data/rule docs, solve.py, tests, judge, reward.toml
  - [x] rule docs (instruction hint cut + G5, cadence allowance C, dependency predicate, protocol reserve, contract cols, glossary)
  - [x] test_output.py reference compute/write_all (allowance, reserve, queue/project allocated, manifest waivers_lapsed)
  - [x] solve.py same changes (cmp vs reference bad 0 on 7 seeds)
  - [x] generator W5 drop for shipped seed (_SHIPPED_DROP 252 edges + 74 waivers), regenerate data (8 files), shipcheck 0 mismatch
  - [x] tests restructure + weights + reward.toml (49 tests, 148 pts, 14 visible w2 + 14 _hard w5; reflex strengthen tries 1+2 done -> PILOT WEAK 0.3649)
  - [x] judge criterion C (R12 w3) + solve.sh check 4 (local run: checks 1-4 ok); _grant_read added
- [x] COST_TABLE, RULE_COVERAGE, JUDGE_MAP, LEVERS, QC_DEFENCE, DESIGN, TRUTH, XREF (TRUTH provenance hash = LAST edit)
- [x] Phase 3 stacking PASS, reflex PILOT WEAK 0.3519, QC scripts 0 FAIL, precheck CLEAN, validator 11 pre-existing
- [x] Docker block ALL_DONE: oracle 1/1/1, owner 1.0, nop 0.0, stub 0.0, forgery 0.2346
- [x] deliverables HARDEN_REPORT, result_593ecae.json (status PILOT_WEAK); temp cleaned
