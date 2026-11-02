# P12 v3 r5 LOG (57e415c)
- 22:33 rename ok (opencode listed); tree 1cd9fe77061b match; kit 976c166611e5
- 22:35 P0.1 done: rules read; fingerprints match
- 22:45 P0.2/P0.3 done: xref 32 entries 0 findings; before_v3r5 copied; probe nat57: 50/50 natural corpora part on cancellation order; no planting anywhere -> var_lifo 6/172 (master fix alone cannot reach 100-165); plan: partition with _settle_one_order repair on non-grading corpora
- 22:47 lock taken; F1 edit: _grades_order + _settle_one_order + postcondition guard; oracle 172/172, var_lifo 157/172 (fails 5 instance + density + tiebreak); full AFTER run started (run_after_v3r5.log)
- 22:58 AFTER rows: lifo 1->157, opening 97->102 (passes general_cadence_partition now), tiebreak 167->162 (also fails general_population_scale), others unchanged; oracle 172
- 22:48 docs (XREF, DESIGN, COST_TABLE, RULE_COVERAGE) + TRUTH table by script; shipped emit identical; xref 33/0; PRECHECK CLEAN; kit 4 scripts exit 0 (A3 warn); tree 765e3d04ab89
- 22:49 P2.2 P2.3 P2.5 done (see RECHECK_FIX); next side effects + Docker
- 22:53 Docker ALL_DONE oracle 1.0x3 owner 1.0 nop 0 stub 0.0058; reports written; tree 765e3d04ab89; lock released; temp dirs removed

# P12 v3 r6 LOG (c45716e)
- 16:29 rename ran (opencode ses_e8d48bb6dffeAqIOiQgfJLC0bQ, title not echoed); tree 765e3d04ab89 match; kit HEAD 5574d77eb9f2
- 16:31 P0.1 rules read; TODO written
- 16:34 P0.2 kit rules recorded (01:46,01:47,03:47,03:62,FC:491); xref before 33 entries 0 findings; noise diff vs a9d62f3 copy: identical
- 16:52 P0.3 started: trap/before_v3r6 copy, variants_v3r6 (+var_decoded_live = CL-4 reading B), run_before_v3r6.log; P2.2 F2 negative rewritten as planted-decoy behavioural trigger; local: oracle no fire, honest_names_paths no fire (old would fire), cheat_copy_out FIRED, out root restored byte for byte
- 17:00 P0.3 done: BEFORE losses (172 - earned) perentry 75, norenew 75, opening 70, cancelled_draw 75, carry_eleven 160, precedence 11, renew_strict 10, tiebreak 10, lifo 15, ctrl_all_old 12, mut_* 3, decoded_live (CL-4 reading B) 135 (37/172=0.2151 = QC); oracle 172
- 17:06 P2.1 F1 applied: engine-rules.md L79-81 (+cancelled/reversal carried), L97-98 (settled total), report-schema.md new para L13-15 (decoded fields count every decoded entry before identity/windows/cancellation); same in STATIC_NOTE_TEXT; tk notes True; emit IDENTICAL to bundle data; vs before only those 2 files differ. P2.3 instruction: N1-N7 deleted, L7 withheld quantities, L13 G5 sentence
- 16:43 CORRECTION: lines stamped 16:52/17:00/17:06 above were estimates; real clock (date) now 16:42. Work they record is done. XREF updated (G5 + judged list values, +5 entries incl retired strings): xref_check 38 entries 0 findings
- 16:47 W9 rows for F1 + instruction edits appended to W9_SELFTEST.md: no oracle-losing literal reading; P2.3 ticked
- 16:48 P2.4 AFTER run ALL_DONE (trap/run_after_v3r6.log): every lever earned identical to BEFORE (losses unchanged), oracle 172/172, negatives 0 -> trap survival PASS (100%)
- 16:52 P2.5 QC_DEFENCE D7 edit + D11, LEVERS r6 effect table, DESIGN r6 note written (TRUTH pending, last)
- 16:58 P2.6 kit structure/instruction/tests/judge rc 0 (tests WARN A3 only) -> OUT/kit_*.txt; stacking PASS after hand correction -> OUT/STACKING_CHECK.md; TRUTH sha by script (solve_py unchanged); precheck PRECHECK CLEAN; tree sha 9c687037cd93; no __pycache__
- 16:46 P2.7 lock taken; Docker chain started /tmp/opencode-logs/match-replay-desync-audit-p12v3r6-20261025T164537-9df7 (warm, oracle x3, owner-only x1, nop x1)
- 16:47 CORRECTION: earlier r6 LOG stamps 16:47-16:58 were estimates; real clock at Docker start 16:45. P1 rows written to OUT/RECHECK_FIX.md (REAL 11, FP 0, UNSURE 0). Docker oracle-1..3 = 1.000.
- 16:49 P2.7 ALL_DONE 16:48:23: oracle 1.0 x3, owner-only 1.0, nop 0.0. P3: RECHECK_FIX.md, PL_NOTE.md, result_c45716e.json written; /tmp/mrda_emit removed; lock released; tree sha 9c687037cd93; precheck CLEAN. DONE.
