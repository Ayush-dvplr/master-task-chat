# LOG
- 01:13 date; name_session.py 154f570 -> codex: no match; opencode: ['ses_e6c82bbdfffebyu6deVAtfxNU5']

- 01:16 read QC_FIX_PLAYBOOK_v3, KNOWLEDGE, checks.json (selected ids)
- 01:17 fingerprint recheck: pl_generator 160/160 match, qc 12/12 match; harness git HEAD 5574d77e
- 01:31 kill block1 started (Docker, CAP=300, 7 instances x 11 solvers) log /Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/kill-20261101T0130/logs/block1.log
- 01:22 block1 (kill-20261101T0130/logs/block1.log) 70 ROW: all 10 heuristic/plain solvers EXACT shipped (flow_post WRONG shipped: post-pass moves energy), WRONG 0/8 (depot_priority 1/8 once) on hidden 1..6; careful_resolve TIMEOUT 300 s on shipped (killed block before ALL_DONE; not re-run on shipped).
- 01:27 gen_proto hidden: added feeder derating block (30%) over arrival peak so weighted unmet fires.
- 01:29 block2 started: logs/block2.log (scratch2): 10 solvers x shipped+hidden1..6 CAP 300, then careful_resolve hidden1..3 CAP 600.
01:32 killed block1 container 0184b6c98a6a (careful_resolve redundant with block2)
01:33 gen_proto hidden: short-window cluster in derate block (18%); core.py: added flow_bigint (lex order as big-int cost). DESIGN.md draft written.
- 01:34 block3 flow_bigint/flow_plain/split_exact on hidden1-3+shipped CAP600 log logs/block3.log scratch3
- 01:38 block3 ALL_DONE: flow_bigint EXACT 8/8 hidden1-3 (3-4 s) and shipped (55 s); flow_plain, split_exact WRONG 0/8 hidden, EXACT shipped. ref shipped 1.96 s; hidden ref obj unmet 35/820/0 (term1 fires 2/3). 01:38 block4 large:1-2 (350-450 buses) flow_plain+flow_bigint CAP900 log block4.log
- 01:45 block4 ALL_DONE: large:1 (371 buses) ref 7.15 s, flow_bigint 172 s EXACT, flow_plain WRONG 0/8; large:2 ref 7.05, bigint 157 EXACT. Shipped n set to 120 in gen_proto. block5 started: 11 solvers x shipped1-2,hidden4-6,large3 CAP600 log block5.log
- 01:52 block5 ALL_DONE (66 ROW): all 10 non-bigint solvers EXACT 8/8 on shipped 1-2 (120 buses) except flow_post WRONG; WRONG 0/8 on hidden4-6 and large3. flow_bigint EXACT everywhere: shipped 8/6 s, hidden 2-8 s, large3 186 s (ref 7.56 s). Added bigint_min (lex-min) solver. block6: bigint_min + careful_resolve on shipped1-2,hidden4 CAP600
- 01:58 block6: bigint_min WRONG on shipped1-2 (tie decided on shipped: BAD for Shape D). Fixed gen_proto shipped published = cheapest full-rate fill (unique optimum, moved 0). block7: verify on shipped1-3
- 01:55 block8: ref_nofeed ref_nocab ref_noterm3 x shipped1,hidden1-4,large1 CAP300 log block8.log scratch8
- 01:57 block8 ALL_DONE: ref_nofeed/ref_nocab WRONG 0-3/8 on hidden1-4+large1, EXACT shipped; ref_noterm3 WRONG everywhere incl shipped. careful_resolve hidden1-2 'Alarm clock' at 600 s (scratch2 err files). Killed careful containers acbbc78c2df2 0e1b35381c4c. KILL_TEST.md + BRANCH_FIRE.md written.
- 01:58 QC_DEFENCE.md, DESIGN_SUMMARY.md written; DESIGN.md section 8 updated. STOP: DESIGN READY. Next on go: Phase 0b design_blind.
- 02:02 master go Phase 0b; TODO P0b items added
- 02:12 Docker bf block started: render+ref+BRANCH_FIRE on shipped:1 hidden:1-3 large:1 (log p0b-20261101T0210/logs/bf.log)
- 02:08 gen_proto: every 37th bus (i%37==5) gets a window shorter than its need (unmet_reason window fires). Moved docs to design_blind/environment/docs/; rendered shipped seed 1 into design_blind/environment/data/ (host, generator only).
- 02:10 Docker bf2 (dockfree START=yes): shipped + hidden1-3 + large1 rendered and checked; ALL_DONE; table in BRANCH_FIRE.md.
- 02:12 design_blind/instruction.md written. STOP: DESIGN BLIND READY.
- 02:25 copied blind fd98e12 program to proto/blind_fd98e12/. 02:26 dockfree START=yes; Docker score run (score-fd98e12/logs/score.log ALL_DONE): EXACT 9/9 on shipped1, hidden1-3, large1. NO CORE. Wrote DESIGN_BLIND.md, KILL_TEST.md row, DESIGN_SUMMARY section.
