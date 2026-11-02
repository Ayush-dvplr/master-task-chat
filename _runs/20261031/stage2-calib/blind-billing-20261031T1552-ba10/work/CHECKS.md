# CHECKS (d830ccb) - one line per command: command | input path | what it showed

1. `python3 .../master_chat_tasks/tools/name_session.py d830ccb` | - | opencode list shows ['ses_e6e77df83ffebNinKBMWWq8wYA'] (codex: no match)
2. `ls -laR BLIND_DIR` | BLIND_DIR | app/, out/, work/ empty; environment/data holds 16 files; no TODO.md existed, so I created it
3. `cat instruction.md; cat environment/Dockerfile` | BLIND_DIR | the task: /app/out/transform.py DATA_DIR OUT_DIR, 13 reports, 8 what-ifs
4. `cat billing_standard.md record_dictionary.md report_layout.md` | environment/data | the rules, the dictionary and the report layout
5. `cat cycle.json plans.csv code_aliases.csv service_catalog.csv zone_rules.csv holidays.csv rate_card.csv; cmp rate_card.csv rate_card_final.csv; head/wc of the rest` | environment/data | rate_card_final.csv is in force and differs from rate_card.csv; closings.csv has 1152 rows, legacy 388 rows in seconds, register 1467 rows, 31 amendments
6. `grep revert/quotes/BOM; file *` | environment/data | no revert actions, no quoted fields, no BOMs, all ASCII; 3 ZZ-* unknown codes plus lower-case codes in closings
7. `python3 work/explore_offsets.py environment/data` (throwaway, deleted) | environment/data | register matches per handset clock offset: H-08 +1 (187/192), H-11 -7 (178/184), H-13 -7 (163/177), H-15 -11 (184/203), H-18 -3 (189/193), H-25 +7 (185/189), H-31 -15 (194/201), H-33 +8 (193/201); runner-up score <= 8 for each
8. `shasum environment/data/*` (before the run) | environment/data | baseline hashes taken
9. `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/transform.py environment/data out` | environment/data -> out | rc=0, real 0.07 s; stdout 13 `wrote NAME SIZE` lines in code point order (normalized.jsonl 615079 bytes, summary.json 399)
10. `cp app/transform.py out/transform.py` | app -> out | the program is also at out/transform.py
11. `cat out/*.json; head -2 out/normalized.jsonl; wc -l out/normalized.jsonl` | out | all 13 reports exist, each JSON compact with sorted keys and a final LF; normalized.jsonl 1518 lines = closings_billed 1518; reconciliation: normalized/product/region/segment net all 95969825500, residual_micro 0; region closings 226+397+332+352+211 = 1518; segment closings 355+439+390+334 = 1518; closings_received 1536 = 1152 main + 388 legacy - 4 duplicates; 6 rejected, 12 void, 0 unrated, 0 outside_cycle, 0 amendments_without_effect
12. `shasum environment/data/* | diff - baseline` | environment/data | DATA_UNCHANGED
13. `cd /tmp && python3 app/transform.py environment/data /tmp/d830ccb_o2; diff -r out /tmp/d830ccb_o2` (temp dir deleted after) | environment/data -> another cwd and OUT_DIR | IDENTICAL_2ND_RUN (byte-identical across cwd and output dir)
14. `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 work/whatif.py` | copies of environment/data under work/whatif_tmp (deleted after) | real 1.76 s; 19 program runs on 19 changed extracts, 1536 received closings each = 29184 closings; Q1 96945842500, Q2 76399338500, Q3 66678709500, Q4 840, Q5 20278774500, Q6 34371706500, Q7 5077580500, Q8 143108240000
15. `ps -axo pid,rss,command | grep python` | - | no python process of mine (only an unrelated watcher process, pid 73156, not started by me)
16. `grep -c except app/transform.py; grep -nE 'subprocess|socket|urllib' app/transform.py; cmp app/transform.py out/transform.py` (read-only, after freeze) | app/transform.py | 0 except clauses (no bare except); no subprocess/socket/urllib; SAME_COPY
