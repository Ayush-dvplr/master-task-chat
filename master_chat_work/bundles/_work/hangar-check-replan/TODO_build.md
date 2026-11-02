# TODO af5dddf hangar-check-replan

## Phase 0
- [x] 0.0 session rename (opencode list shows ses_e6d392a38ffeZtPeeqtsrQbHzZ; codex no match)
- [x] 0.0 required reads (COMMON_RULES_v5, LEVER_RULES_v3, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v3, KNOWLEDGE, checks.json)
- [x] 0.1 GEN + QC fingerprints (all files match; GEN git head 5574d77e vs recorded 976c1666, files byte-identical)
- [x] 0.2 PREMORTEM.md
- [x] 0.3a DESIGN.md model section (written early from design thinking)
- [x] 0.3b proto reference solver WORK/proto/ref.py (per-base DP + merge, exact)
- [x] 0.3c proto generator WORK/proto/gen.py (shipped degenerate + hidden seeds) [seeds picked: shipped 1, hidden accept list in LOG]
- [x] 0.3d brute-force check on tiny seeds (DS-20)
- [x] 0.3e wrong solvers WORK/proto/wrong.py (+ detect.py)
- [x] 0.3f kill test in Docker -> KILL_TEST.md
- [x] 0.3g BRANCH_FIRE.md
- [x] 0.3h DESIGN.md rest (sections 4-9 done)
- [x] 0.4 QC_DEFENCE.md
- [x] 0.5 DESIGN_SUMMARY.md
- [x] 0.6 STOP: DESIGN READY (said 23:37; waiting for go)

## Phase 0b (after go)
- [x] 0b.0 go received 23:33 (additions: fixed declared universe; plant no_slot)
- [x] 0b.1 proto/gen_proto.py: full-format data writer (all files, rejects, empty base + empty segment in 2 hidden corpora, no_slot planted)
- [x] 0b.2 proto/solve_proto.py: reads data dir, rejects, solves, writes outputs (incl. empty axis rows)
- [x] 0b.3 design_blind/environment/data/ shipped sample + docs/ (README, planning, overtime, deferral, data_conventions, output_schema)
- [x] 0b.4 design_blind/instruction.md draft
- [x] 0b.5 BRANCH_FIRE on sample + 3 seeds (add empty-axis + no_slot rows) ; kill row reference-derives-axes-from-records
- [x] 0b.6 DESIGN_SUMMARY + DESIGN.md + KILL_TEST update with new prediction
- [x] 0b.7 STOP: DESIGN BLIND READY (said 23:46; waiting for blind program)
- [x] DESIGN_BLIND.md after blind program returns (v1 24bff4e 00:00; r1 d0dc88d 01:15)

## Phase 1-9: see prompt

- [x] 0b.8 score design blind 24bff4e: 100% kept, EXACT 6/6 -> NO CORE (00:00); STOP for master

## Redesign 1 (G-8, master m0183: Office package current-text lever)
- [x] r1.0 backup to design_v1_backup/; evidence + PILOT read
- [x] r1.1 proto/docx.py: writer (plain + traps F1 relmain, F2 altcontent, F3 tracked move, F4 del/ins) and reader (current text + kill slip modes)
- [x] r1.2 render.py -> disruption_notice.docx + planning_limits.docx; solve_proto.py reads them via docx.py (mode arg)
- [x] r1.3 trap target selection: every trap changes reference outputs (amplification check per wrong reader)
- [x] r1.4 Docker: reference + 7 reader slips + 24bff4e blind on shipped + h1..h6; score per family
- [x] r1.5 DESIGN.md sec 11, KILL_TEST, BRANCH_FIRE, QC_DEFENCE, DESIGN_SUMMARY 'redesign 1'
- [x] r1.6 STOP: DESIGN READY (said 00:58; design_blind folder updated to docx inputs, shipped seed 2; waiting for fresh blind)
- [x] r1.7 score design blind d0dc88d (score-d0dc88d): EXACT 11/11 corpora, 100% lever kept -> second NO CORE (01:15); STOP, hangar pauses

## Redesign 2 (LAST, master m0300: L01 settlement rule with propagation)
- [x] r2.0 backup to design_r1_backup/; PILOT + B2 FINDINGS read; DESIGN.md sec 12 (rule, layout, slips)
- [x] r2.1 proto/settle.py (ref + slip modes) and solve_proto.py settlement outputs (SETTLE env)
- [x] r2.2 gen_proto.py grants by stype (slack/cap/short/bind) + render.py allowance table
- [x] r2.3 scoreblind.py settle families (new lever kept separately)
- [x] r2.4 Docker kill row (a): 4 naive slips; any > 60% kept -> NO CORE stop (r2b, r2c: pass; max kept 50%)
- [x] r2.5 Docker rows (b) literal, (c) blinds without settlement, (d) other slips
- [x] r2.6 KILL_TEST, BRANCH_FIRE, DESIGN sec 12 numbers, DESIGN_SUMMARY 'redesign 2', design_blind docs
- [x] r2.7 STOP: DESIGN READY (redesign 2) (said 01:42)
- [x] r2.8 score blind e8e9c82 (02:10): 100% kept on every family -> NO CORE (second); hangar parked; STOP

## Build (route 1, master m0368 go 11:27; route1_notes read 11:34)
- [x] B.0 go received; route1_notes + build prompt re-read
- [x] B.1 copy e8e9c82 program to WORK/kill/e8e9c82_program.py; read for sample-fitted readings -> DESIGN.md sec 13 note (+ hidden fixture if a stated rule allows)
- [x] B.2 Phase 1 scaffold (generate_bundle.py) + WORK/scaffold_orig/
- [x] B.3 Phase 2 WORK/datagen.py -> BUNDLE/environment/data + docs (A5 volume, shipped seed 2, BRANCH_FIRE shipped 0)
- [x] B.4 Phase 3 solution/solve.py [done, == derive on shipped+h1..h6; check_exact OK; override probe; probes P1-P9 ok in Docker] + solve.sh (check stages), WORK/check_exact.py (independent) + override-removal probe
- [x] B.5 Phase 4 (G12 300/300 OK 14:13) tests/test_output.py (embedded generator, own RNG, hidden h1..h6, mutations), wrong impls, COST_TABLE, RULE_COVERAGE, RULE_TRACE, EVIDENCE_MAP, LEVERS, reward.toml, re-embed
- [x] B.6 Phase 5 tests/judge.toml + JUDGE_MAP (12:15, judge_qc PASS)
- [x] B.7 Phase 6 instruction.md (12:17, instruction_qc PASS, 2227 chars)
- [x] B.8 Phase 7 TRUTH.md (shas rerun 14:15, unchanged)
- [x] B.9 Phase 8 (QC x4, validator 40/0, A5 21071, stacking PASS, oracle x3 1.0, owner-only 1.0, nop 0.0 (pre-lock tests), precheck CLEAN 14:16)
- [x] B.10 Tasks_INPUT cp -Rp + diff -rq empty + tree shas 3df66c1d1ab2 both
- [x] B.11 Phase 9 BUILD_REPORT, result_af5dddf.json, KILL_TEST/COST_TABLE e8e9c82 row, name_session again
