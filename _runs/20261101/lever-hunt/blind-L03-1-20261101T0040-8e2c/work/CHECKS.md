# CHECKS — blind L03-1 (sha 6c0c3d8)

One line per command: command | input path | what it showed.

- `python3 master_chat_tasks/tools/name_session.py 6c0c3d8` | n/a | session named; opencode `['ses_e6ca4f901ffefPwAqb6iWmEU6C']`, codex "no match".
- `date` | n/a | Sun Nov  1 00:36:37 IST 2026 (start).
- `ls -la` + `find environment -maxdepth 3` | BLIND_DIR | app/, out/, work/ empty; environment/data holds panel_contract.md, source_rules.md, output_schema.json, corpus/transmissions.
- `read instruction.md` | BLIND_DIR/instruction.md | program `/app/derive_report.py <corpus_dir> <out_dir>`, stdlib only, runs on other extracts.
- `read panel_contract.md` | data/panel_contract.md | 4 depots x 3 quarters x 5 assays, validation order, aggregation rules, output file list, half-up 3dp.
- `read source_rules.md` | data/source_rules.md | lab tiers NRL=1, ACM=BLX=2, FSK=3; tie inside tier = latest reported_at; worked example CS268129/HG -> T67576 @0.115.
- `read output_schema.json` | data/output_schema.json | exact key sets/types; `-1` sentinels in summary files; null in panel cells; NO_DATA example for an empty quarter.
- `ls -la transmissions; wc -l transmissions/*.csv` | data/corpus/transmissions | 41 csv files, 232 lines total.
- `cat ACM_2026-01.csv NRL_2026-10.csv ACM_2025-12.csv; awk FNR==1 | sort -u` | same | one identical header everywhere; saw PB2 / NI / DUN dirty values.
- `awk -F, 'FNR>1{print $N}' *.csv | sort | uniq -c` | same | 191 data rows, 8 fields each; labs ACM 70 / BLX 60 / FSK 32 / NRL 29 (no unknown labs); depots incl. DUN 2, KES2 3; assays incl. NI 2, PB2 3.
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py environment/data/corpus out` | corpus -> out | exit 0, **real 0.04 s** (user 0.02, sys 0.01); 13 output files written (panel.json, 4 depots, 5 assays, 3 csv).
- `find out -type f` | out/ | all contract-named files present: panel.json, depots/{KES,MAR,OSS,TAL}.json, assays/{PB,CD,HG,AS,HIS}.json, quarters.csv, measurements.csv, rejected.csv.
- self-check script (stdlib, inline heredoc) | out/ | ledger 191 = 162 accepted + 17 superseded + 12 rejected (identity TRUE); 12 panel rows in depot-then-quarter order; every row has all 5 assay keys in declared order with exact key sets; sum of cell `n` = 162 = accepted; measurements.csv 162 rows sorted by sample_id then assay order; rejected.csv 12 rows sorted by transmission_id with reasons only from {UNKNOWN_DEPOT, UNKNOWN_ASSAY, OUT_OF_PERIOD}; assay `by_quarter` n sums equal assay n for all 5 assays; sum of assay n = 162; quarters.csv = header + 3 lines and every field re-derived from panel rows matched; depot `total_samples` sum 43 = distinct sample ids in measurements.csv; worked example reproduced exactly (CS268129/HG -> BLX/T67576/0.115).
- `grep -c $'\r' out/*.csv` | out csvs | 0 CR in all three — `\n` endings only; line counts 4 / 163 / 13.
- `grep -c "blind-L03-1" app/derive_report.py` | app/derive_report.py | 0 — no BLIND_DIR path hard-coded.
- `cp app/derive_report.py out/derive_report.py` | app -> out | program copy placed in out/ per path-mapping rule.
- `ps -axo pid,rss,command | grep python` | n/a | no python process of mine left running (my only two runs, `derive_report.py` and the inline self-check, both exited). Three foreign processes were visible and left untouched: pid 12331/12335 (`proto/gen_proto.py`, another agent) and pid 88920 (`master_chat_tasks/auto/auto.py watch`, the harness).
