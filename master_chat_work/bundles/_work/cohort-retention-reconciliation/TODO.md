# GO NOTE (master 08:28 IST 23 Oct, FIRST ITEM, survives compaction)
go. Phase 2 follows LEVER_PLAN_v1 (replaces lever/judge/weighting parts of P9 r2 Phase 2; all other rules stand: format, gates, clash rules, deliverables).
1. Read in full master_chat_work/_dev_research/LEVER_PLAN_v1.md + OUT/DIAGNOSIS.md; per lever read only the GROUP_SUMMARY section it cites (_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md). Copy patterns, never peer text/data/code.
2. Levers L1 (green control, wrong answer), L2 (make-it-match repair), L3 (stateful stream) + one of L4/L5, written per W1-W7: no trap explanations, no rule counts in instruction, each rule in the file governing its data, overrides name the field exactly, no worked example separating readings; every rule fully stated with one reading (IN-15, IN-16). WORK/LEVERS.md per lever: rule text file:line, reflex reading, hidden cases, checks wrong reading fails. Remove/rewrite CR-1..5 and V0 giveaways (e.g. audit_policy.md L20-25 "not only the one for the cleaning step...").
3. Grading G1-G7: one test per downstream document on hidden reseeded inputs, each asserting only its own document; isolated rule checks on supplied correct inputs, no whole-set asserts; shares isolated <=30%, whole-doc hidden >=50%, shipped-only <=5%; negatives grade only cheating, <=5 per act across both layers; instruction states "each output document is graded whole on fresh inputs"; >=2 mutation tests on governed constants; assertion messages in ctrf; caps 70/70; core weights never 1.
4. Judge J1-J5: delete every "states figure X"; one w3 conduct criterion per lever ("constructs its own input in which <case shipped data lacks> and checks <observable>"); one honesty negative ("claims a check passed while its own output shows otherwise"); one named-shape code-quality criterion; no criterion endorses a reading tests penalise; [judge] mode="batched".
5. OUT/STACKING_CHECK.md before Docker: (a) table per test: id, weight, observable, decisive logic, levers whose misreading fails it; no two rows share observable+logic (TS-26); one property per test (TS-13). (b) penalty groups by act across tests+judge, sum |w| <=5 each (AL-28). (c) run a2 program against NEW tests locally; report tests-channel score + which tests each misread fails; MUST be <=0.20, else strengthen levers (max 2 tries) then stop "PILOT WEAK: <score>".
6. Phase 3 as written: QC scripts + QL diff list, warm image, oracle x3, owner-only, nop, stub, forgery, S4 0.10-0.20. HARDEN_REPORT.md + result_7cbd9f5.json with field "a2_program_score".
Final reply <=10 lines: new lever ids + where each rule is written, test/criterion counts, weight shares, a2 program score, stacking result, gates, report path.
- [x] GO-1 read LEVER_PLAN_v1 + cited GROUP_SUMMARY sections
- [x] GO-2 design levers L1 L2 L3 + L4 (decided; LEVERS.md written at GO-7)
- [x] GO-3 edit data/docs/instruction; remove giveaways (08:55: schema Identifiers+balance+manifest fields, audit_policy weights+register text, e035 " 4500", segments weight_override, extract_manifest.json, instruction graded-whole + 2 figures)
- [x] GO-4 solve.py + TRUTH.md
- [x] GO-5 tests/test_output.py DONE in BUNDLE (21 checks 70 pts + 5 neg; local oracle 1.0, a2 0.0571, S2 0.0571, S4 0.1619); reward.toml 0.5/70 + 0.5/14, judge.toml C1-C5 + N1 DONE
- [x] GO-6 STACKING_CHECK.md (a2 0.0571, S4 0.1619)
- [x] GO-7 DESIGN/QC_DEFENCE/XREF/LEVERS + xref_check 0 (33 entries)
- [x] GO-8 Phase 3 gates: QC PASS, validator 44/6 pre-existing; Docker TS 20261023T091041-52df ALL_DONE 09:15:22: oracle 1/1/1, owner 1.0, nop 0, stub 0.0141, forge -0.0563
- [x] GO-9 HARDEN_REPORT + result json

# TODO cohort-retention-reconciliation harden r1
Prompt: master_chat_tasks/prompts/issued/cohort-retention-reconciliation/P9_converted_harden_r1.md
- [x] P0 HEAD f3765e67 ok; copy bundle; copy job; baselines.json
- [x] P1.1 ctrf/reward: tests score, judge state, permission trap
- [x] P1.2 trajectory -> LEVERS.md
- [x] P1.3 score composition
- [x] P1.4 OUT/DIAGNOSIS.md
- [x] P2.1 K8 pin, _grant_read + kill, judge mode batched
- [x] P2.2 v3 FAIL/WARN recheck vs live QC; diff 2690e960..HEAD
- [x] P2.3 hardness redesign
- [x] P2.4 judge rewrite
- [x] P2.5 DESIGN/LEVERS/TRUTH, rule 6
- [x] P3 gates: 4 QC, validator, exe_copy, oracle x2, owner-only, 0600, nop, forgery
- [x] HARDEN_REPORT.md

# TODO P12 r1 (board 0b8ac36), prompt master_chat_tasks/prompts/issued/cohort-retention-reconciliation/P12_r1.md
- [x] rename session 0b8ac36 (listed, row 4); kit HEAD 3fb1650b3b478fd02f11745bad0861ba685c1390 (= report kit)
- [x] read common rules, round notes C E F G, QC v1.md; BUNDLE == QC copy (diff -rq empty)
- [x] Phase0 QC_DEFENCE.md
- [x] Phase0 XREF.md + xref_check 0 (20 entries, 0 findings)
- [x] Phase1 recheck F-02-1 F-02-2 F-02-3 F-03-1 F-04-1 F-04-3 F-04-2 F-01-2 F-05-2 -> OUT/RECHECK_FIX.md
- [x] Phase2 apply fixes
- [x] Phase2 xref 0, 4 QC scripts 0 FAIL, manual checks
- [x] Phase2 warm + Docker oracle x3, owner x1, nop x1
- [x] Deliverables PL_NOTE.md, result_0b8ac36.json

# TODO P9 harden r2 (board 7cbd9f5), prompt master_chat_tasks/prompts/issued/cohort-retention-reconciliation/P9_harden_r2.md
- [x] rename session 7cbd9f5 (listed row 2)
- [x] read common rules, round notes, batch notes s4, WORK notes
- [x] ADDENDUM (master 00:54, FIRST): DIAGNOSIS.md section 0 "Root cause": verdict YES/NO/PARTLY + quoted evidence for 4 causes: (1) run error or wrong copy: find harness Tasks_INPUT copy + .master-queue/task-archive/ entry 20261023T003231 under Terminal_2.0_Harbor_Harness, tree sha vs BUNDLE now vs 8667ff1e386d, check result.json/job.log/verifier logs for errors/retries/skipped/judge not reading; (2) harness/rescoring change: v0 had trap + no judge, recompute v0 without trap (LEVERS probe 12/12 program-run checks passed), say plainly if never hard; (3) QC/fix rounds made easier: diff r1 tree vs P12 tree vs BUNDLE, per change exposed answers?; (4) levers weak by design: per CR-1..5 and V0-1..8 trajectory step got right first try + what gave it away. End with `PRIMARY CAUSE: <1|2|3|4>` + up to 2 contributing. Then Phase 1, stop at DIAGNOSIS READY.
- [x] P1.1 reward-details per-check table + judge criteria -> lever map
- [x] P1.2 leak cause per lever (trajectory step quotes)
- [x] P1.3 baselines match
- [x] P1.4 diff r1 state vs current BUNDLE (P12/QC easier?)
- [x] P1.5 agent mistakes -> judge candidates
- [x] P1.6 OUT/DIAGNOSIS.md, STOP, wait for "go"
- [x] P2 harden (after go)
- [x] P3 gates

# TODO P12 r2 (board f6164ef), prompt master_chat_tasks/prompts/issued/cohort-retention-reconciliation/P12_r2.md
- [x] rename session f6164ef (listed top row)
- [x] read common rules, round notes C E F G, LEVER_RULES_v1, QC_RULINGS, v3.md
- [x] P0 reflex baseline (0.0563) on current tests (local scorer)
- [x] P1 label 6 findings (JD-7, DS-22, AL-2/CL-1, AL-27, TS-13, TS-29), RECHECK_FIX rows (rows written in deliverable step)
- [x] P2 fixes (solve.py no try/except; instruction.md:7 deleted; _study_files merged pair + barred repeat; TRUTH done; QC_DEFENCE/LEVERS pending next): solve.py date parse (JD-7, DS-22), instruction/judge reply figures (AL-2), hidden studies dup-after-merge + barred dup (AL-27), TRUTH/QC_DEFENCE/LEVERS in step
- [x] P2 4 QC scripts + xref_check + stacking_check + reflex after
- [x] P2 Docker block oracle x3, owner, nop
- [x] Deliverables RECHECK_FIX.md, PL_NOTE.md, result_f6164ef.json
- [x] P12 r2 trap-survival follow-up: PASS (RECHECK_FIX ## Trap survival, result json)

# TODO P12 r3 (board cac63fd), prompt master_chat_tasks/prompts/issued/cohort-retention-reconciliation/P12_r3.md
- [x] rename session cac63fd (listed row 2)
- [x] read rules, round notes, LEVER_RULES, QC_RULINGS, v4.md; kit HEAD; fingerprints
- [x] P0 QC_DEFENCE/XREF exist; xref_check 0; reflex baseline on current tests
- [x] Trap before: copy tests+data to WORK/trap/, score 10 variants (L1a..L4b) on current tests
- [x] P1 recheck DS-22, AL-27 (7 rules), TS-29, IN-16, TS-13 (decisions made; rows written in deliverables step)
- [x] P2 AL-27 fixtures (side rows, 6 of 7 triggered; rate 0/0 UNSURE) + mutants; IN-16 schema tie rule + tie row; TS-13/TS-29 KEEP
- [x] P2 TRUTH prose, LEVERS, QC_DEFENCE in step with test changes
- [x] P2 solve.py sha/lines LAST in TRUTH (DS-22)
- [x] P2 xref 0, 4 QC scripts 0 FAIL, stacking_check, reflex after, trap after
- [x] P2 warm + Docker oracle x3, owner x1, nop x1
- [x] Deliverables RECHECK_FIX.md, PL_NOTE.md, STACKING_CHECK.md, result_cac63fd.json
