# LOG 49087b0 pilotage-dues-reconstruction

v1 log is v1_design_backup/LOG.md.

- 11:42 `python3 master_chat_tasks/tools/name_session.py 49087b0` -> codex: no match; opencode: ['ses_e6f69d6aeffesgVMevkmI7iOjM']
- 11:43 `date` ok. Read _COMMON_RULES_v5, LEVER_RULES_v3, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v3, KNOWLEDGE, checks.json, IDEA_v2.
- 11:45 cp v1 design files -> v1_design_backup/ (G-7)
- 11:47 fingerprint rehash: qc.json 12 files 0 diff (head 5574d77e = recorded); pl_generator.json 160 files 0 diff
- 11:50 read v1 DESIGN, DESIGN_BLIND, proto docs; warrant UNIQUE_FIT, LEVERS, KILL_TEST, blinds/BLINDS.md (3 blinds lost 80/80 conv points by WRONG; P6o careful wide EXACT); warrant docs state the family ("Which clock ... is the gateway's convention") without listing readings
- 11:52 v1 blind programs (/tmp/blind/pilotage-*) no longer exist; kill row 5 uses the v1-equivalent program (headline conventions + full tariff count, which the v1 blinds matched exactly)
- 11:53 rm top-level v1 TODO/LOG/PREMORTEM (copies in v1_design_backup/), new TODO/LOG written
- 11:56 wrote proto2/core2.py (constants, due, decomposed fit), gen2.py (per-station conventions over stated domains kA 1..30, kD 1..10, S, B, 7 calendars, quarter-hour windows; coverage plants; observe loop RNG seed*13+7; uniqueness asserts), kill2.py (ref K1 K2 K4 K4w K4q), score2.py
- 11:58 host: gen2.py 482617 --shipped (0.5 s), 1101..1104 (0.6-0.8 s), all uniqueness asserts pass, 0 observe rows needed
- 11:59 dockfree START=yes FREE_MB=12898; docker run --rm --memory 4g --cpus 2 python:3.12-slim scratch/run.sh -> logs/kill1.log (zero-fit reason bug), fixed reasons, logs/kill2.log ALL_DONE
- 12:02 kill2: ref 20/20 stations exact; K1 K2 K4 K4w shipped 4/4, hidden 0/16; K4q 3/16; all <=0.1 s, every loss WRONG

- 12:09 date ok. Wrote DESIGN.md v2, BRANCH_FIRE.md (counts by script from prototype truth), UNIQUENESS.md (core2.fit full space 1 fit per station all corpora; natural-wide 0 on hidden; second period alone 2..288), EVIDENCE_MAP.md, QC_DEFENCE.md, DESIGN_SUMMARY.md (40 lines). Removed stale v1 COST_TABLE.md, DESIGN_BLIND.md from top level (identical copies in v1_design_backup/).
- 12:14 STOP: DESIGN READY. Waiting for go.
- 12:33 go received (master 12:45 msg). Moved v1 design_blind contents to v1_design_backup/design_blind_old/.
- 12:35-12:44 proto3: core3.py (minute windows, unit-implied marks), gen3.py (renders 14-file layout, uniqueness asserts, obs RNG seed*13+7), docs in proto3/docs, solve3.py (ref|K1|K4w|K4q), score3.py. Hidden 1102/1104 fail corpus assert (skipped); valid 1101,1103,1105-1108; sample 482617 0.1 s.
- 12:44 dockfree START=yes FREE_MB=4706; docker run3 (logs/run3.log ALL_DONE): ref exact 0.19-0.26 s; K1 0/12, K4w 0/12, K4q 1/12 hidden, all WRONG; shipped 4/4 all rows.
- 12:46 design_blind/ built (instruction.md + 14 data files from sample2). BRANCH_FIRE and KILL_TEST Phase 0b tables appended.
- 12:48 DESIGN_SUMMARY.md rewritten (v3, kill lines on fresh bytes). STOP: DESIGN BLIND READY.
- 13:07 score blind 5456c27: copied app/derive_report.py to proto/blind/ (sha256 10de7239dbf9a9faa752737b35440f84faa5c50e71181d03d122770c1a6ec861; app and out copies identical). dockfree START=yes FREE_MB=4706. Docker score-5456c27/logs/score.log ALL_DONE: ref 0.19-0.22 s; blind sample 4/4, h1101 4/4, h1103 4/4, h1105 4/4 EXACT, 0.87-1.07 s. Blind searched full stated domain. Verdict NO CORE. Wrote KILL_TEST row, DESIGN_SUMMARY section, QC_DEFENCE blind lessons, DESIGN_BLIND.md. STOP.
- 13:53 try 4 started (anchor-type conventions). proto4/ to be written.
- 13:55 proto4/docs written (tariff_circular.md s1-s7 anchor families named once in s5, exemption_policy.md register/agents/stations layouts, rule_register.md 12 data files, output_contract.md + station_notices.md from proto3).
- 13:56 gen4 host runs: sample 482617 (headline), hidden h1101 h1102 h1104 h1105 h1106 ok (1.4-2.6 s); 1103 fails 'fewer than 3 per-visit anchors' (skipped).
- 13:57 solve4.py (ref=K5, K1, K2, K4w) + score4.py written; host ref sample/h1101/h1102 ref_vs_truth OK 4/4.
- 13:58 dockfree START=yes FREE_MB=12898; Docker kill table started: logs/kill4.log (scratch try4-20261031T1353/run4.sh).
- 14:05 kill4 done (ref=K5 EXACT 20/20, K1 0/20, K2 1/20, K4w 2/20 WRONG); design_blind data replaced with try-4 sample (16 files); DESIGN_SUMMARY '## Try 4', KILL_TEST and BRANCH_FIRE try-4 tables written.
- 14:36 blind 529e4de copied to proto/blind4/derive_report.py sha256 1735c8e5f442a527c1c5c15647d94ef595f7850d2aa14bca3b159a2246548459; dockfree START=yes FREE_MB=4706; Docker scoring started (score-529e4de/logs/score.log).
- 14:36 blind 529e4de scored: shipped 4/4, hidden 20/20 EXACT (0% lost, 1.7-2.7 s/corpus). NO CORE written to DESIGN_SUMMARY.md; KILL_TEST row and QC_DEFENCE lessons added. Pilotage parked.
