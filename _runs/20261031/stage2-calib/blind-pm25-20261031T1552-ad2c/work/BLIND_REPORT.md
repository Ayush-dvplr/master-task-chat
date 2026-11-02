# Blind report 5c1644a (stage2-calib-pm25)
- Session rename: name_session.py printed `codex: no match` / `opencode: ['ses_e6e77d2faffegjT9ru9OsBE5yH']`, so the opencode list shows it.
- Files read in order: instruction.md, environment/Dockerfile, data/monitoring_standard.md, data/record_dictionary.md, data/report_layout.md, asset_tags.csv, extract_manifest.json, maintenance_log.json, network_policy.json, network_policy_v2.json, site_register.csv, span_register.csv, span_register_final.csv, unit_deployments.csv, zone_rules.json, then the heads of card_readings.csv and receipt_journal.csv. The judge file was read only at step 5.
- Minutes to first full write: 3 (started 16:06, program first fully written at about 16:08 to 16:09).
- Program: app/derive_report.py, copied to out/derive_report.py (the two are identical). It writes 9 reports.
- Self-check: PASS. It covered:
  - the shipped run: 0.17 s, 9 reports, stdout byte counts equal the file sizes;
  - reconciliation: 19484 card rows = 2223 excluded + 17261 valid, residual 0;
  - the data directory sha1 is unchanged after the run;
  - determinism: 2 extra runs (another cwd, and a copy of the data) are byte-identical;
  - what-if runner: 211 runs, 39.4 s.
- Crash fixed: none.
- Judge estimate: lower 11, upper 11 (lower would be 8 if R17 fires, because the final reply says 210 runs where the real count is 211). Process criteria not performed: 4 (R11 to R14).

## Lessons for the master
- The rubric expects what-if journal moves to change results. This program uses one best offset per unit (it read "the offset holds for every row"), so moves that only unmatch rows changed nothing (what-ifs 2, 3 and 8 equal the shipped values). The intended rule seems to be offset detection per row or per segment.
- The instruction does not say that an undetermined offset, or a journal entry that no card row explains, must raise an error. R13 and R14 are only reachable by inference.
- R11 and R12 (run on a different extract, record the opened files) are process steps that the blind protocol "do not build extra test inputs" forbids.
- AQ896's chosen offset sits at the boundary of +19, which hints that the single-offset model was wrong.
