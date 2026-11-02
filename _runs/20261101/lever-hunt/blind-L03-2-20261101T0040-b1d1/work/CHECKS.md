# CHECKS — blind L03-2 (85a4df3)

One line per command: command | input path | what it showed.

1. `python3 master_chat_tasks/tools/name_session.py 85a4df3` | — | `codex: no match`, `opencode: ['ses_e6ca4f77fffepvurFxPkeBJUSr']` (session named).
2. `date` | — | `Sun Nov  1 00:36:37 IST 2026`.
3. `ls -la; find . -maxdepth 3` | BLIND_DIR | instruction.md + environment/data/{corpus,output_schema.json,panel_contract.md,source_rules.md}; empty app/, out/, work/.
4. `Read instruction.md` | BLIND_DIR/instruction.md | program `/app/derive_report.py <corpus_dir> <out_dir>`, stdlib only.
5. `Read panel_contract.md` | environment/data/panel_contract.md | 4 depots, 3 quarters, 5 assays+limits, validation order, aggregation rules, 6 output files.
6. `Read source_rules.md` | environment/data/source_rules.md | lab tiers NRL 1, ACM/BLX 2, FSK 3; tie inside tier = latest `reported_at`; worked example CS268129/HG → T67576.
7. `Read output_schema.json` | environment/data/output_schema.json | exact key sets/types; null in panel cells, `-1` in summary files; empty-quarter example.
8. `find corpus; wc -l` | environment/data/corpus | 41 CSVs under `transmissions/`, 232 lines total.
9. `head -3 ACM_2026-01.csv` + python census | corpus/transmissions | 191 data rows, one header per file; labs ACM/BLX/FSK/NRL only; depots include bad `KES2`,`DUN`; assays include bad `PB2`,`NI`; `collected_on` range 2025-12-05..2026-10-15; no blank fields; no duplicate transmission_id; max 2 transmissions per `(sample_id,assay)`; all results 3 decimals.
10. `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py environment/data/corpus out` | corpus | exit 0, **real 0.05 s**; wrote 13 files (panel.json, 4 depots, 5 assays, quarters.csv, measurements.csv, rejected.csv).
11. python self-check script (asserts) | out/ | ledger `rows_read 191 = accepted 162 + superseded 17 + rejected 12` ✔; 12 panel rows in depot→quarter order, each with all 5 assay keys in order ✔; sum of all cell `n` = 162 = accepted ✔; measurements.csv 162 rows, header exact, sorted by sample_id then assay order ✔; rejected.csv 12 rows (UNKNOWN_DEPOT 5, UNKNOWN_ASSAY 5, OUT_OF_PERIOD 2) ✔; quarters.csv samples per quarter equals sum of that quarter's panel-row samples (13/13/17) ✔; each assay report `n` equals panel column total and equals sum of its `by_quarter` n ✔; each depot `total_samples` equals distinct sample_ids for that depot in measurements.csv (KES 11, MAR 9, OSS 11, TAL 12) ✔; source_rules worked example reproduced: CS268129 HG accepted from BLX T67576 result 0.115 ✔. No assertion failed.
12. `cp app/derive_report.py out/derive_report.py; grep -c blind-L03-2 app/derive_report.py` | app/ | 0 matches → no BLIND_DIR path hard-coded.
13. `python3 -c "print(open('out/quarters.csv','rb').read()[:60])"` | out/quarters.csv | bytes show header then `\n` endings (no `\r`).
14. `ps -axo pid,rss,command | grep python` | — | no python process of this session left running.
