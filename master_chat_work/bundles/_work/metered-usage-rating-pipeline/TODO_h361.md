# TODO 361674d gate v3.6 harden (prompt: master_chat_tasks/prompts/issued/metered-usage-rating-pipeline/20261027T2229_harden.md)
Old wave-2 list saved as TODO_w2.md.

## Phase 1 (no BUNDLE edits)
- [x] setup: date, rename session (opencode ok), fingerprints 0 diff, QC kit HEAD 5574d77e, reading list
- [x] 1.1 trajectory_readout -> OUT/TRIP.md + TRIP table
- [x] 1.2 Phase A diff
- [x] 1.3 arithmetic (4 combined corpora x 26 = 104; share 38.1%)
- [x] 1.4 lever design LV-MU-9 50000-tier ladder + reseller tree combined corpora
- [x] 1.5 kill test Docker -> WORK/KILL_TEST.md (ladder5 72003 all solvers; ladder6 72002 rest)
- [x] 1.6 judge band
- [x] 1.7 OUT/DESIGN.md -> DESIGN READY

- [x] WAIT for go (go 28 Oct: + 3-4 w3 probes so probe-3 mid <= 21%, P >= 48)

## Phase 2 (after go)
- [x] B0 digests before (tests/ copy + DIGESTS) 
- [x] B1 tests_template: LADDER_SHAPES, _ladder_files, ladder checks; assemble_tests criteria; G7 diff
- [x] B2 judge.toml B11-B17 (P=49) + reward.toml 0.5/407, 0.5/49
- [x] B3 solve.sh self-check new probe acts (plain prints)
- [x] B4 shape check 300 seeds ladder (Docker): LADDER_SHAPE_OK, min distinct tiers used 4944, min top tier 49915, 880 s
- [x] B5 rule coverage / check_exact: not re-run (no rule, sentence or shipped data changed; noted in report)
- [x] B6 docs: LEVERS, QC_DEFENCE, JUDGE_MAP, COST_TABLE, DESIGN 'Gate v3.6 harden', XREF, TRUTH last
## Phase 3 gates
- [x] G1 stacking_check -> OUT/STACKING_CHECK.md
- [x] G2 measured cost table Docker
- [x] G3 precheck CLEAN + QC scripts + validator
- [x] G4 step10: oracle 1/1/1, owner 1, nop 0, stub 0, forgery 0.2555
- [x] G5 Tasks_INPUT sync (diff empty, tree 90e780db2184)
- [x] G6 HARDEN_REPORT + result json
