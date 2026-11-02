# TODO d930be0 sentinel-fraud-training-release
Scratch: /tmp/fd-sentinel-fraud-training-release-20261024T1156 (bundle/ = copy w/o trajectories, traj/ = trajectories copy)

- [x] 0 name_session (ok), docker ps (empty), scratch + OUT created
- [x] P1.1 mapping/author/category/QL; older copies search + diff
- [x] P1.2 masking residue grep
- [x] P1.3 env leak grep
- [x] P2.1 precheck -> OUT/precheck.txt
- [x] P2.2 compare with team QC report; our-rule breaks
- [x] P3.1 recompute combined; pass_summary
- [x] P3.2 loss table -> OUT/loss_table.md
- [x] P3.3 regrade agent / oracle / nop -> OUT/regrade.txt
- [x] P4 trajectory read; timeline; per-loss; mistakes; patch-proof
- [x] P5 design anatomy
- [x] P6 adopt table + template edits; peer-mining agree/disagree
- [x] Deliverables: ANALYSIS.md, result.json; cleanup docker images; name_session again
