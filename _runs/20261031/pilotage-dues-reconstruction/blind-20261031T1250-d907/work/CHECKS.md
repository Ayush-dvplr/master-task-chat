# CHECKS (5456c27)
- `python3 master_chat_tasks/tools/name_session.py 5456c27` | - | codex no match; opencode ['ses_e6f282240ffeKks2zdDA3btLkx'] (renamed); date 12:54:24 IST
- `ls -laR <BLIND_DIR>` | BLIND_DIR | 14 data files, empty app/ out/ work/
- `head/tail` of paid_*, disputed_batch.csv, vessel_register.tsv, pilot_movements.log (first try with `cat -A` failed: macOS cat has no -A; redone with `cat -vet`) | environment/data | layouts match tariff_circular §7; LF endings
- `grep -nvE <layout regex>` on log and each paid/disputed file | environment/data | log: only NOTE lines off-layout, 1425 BOARD / 1425 RELEASE, no duplicate visit ids; one `12,40` amount per paid file; disputed line 254 `abc`
- `python3 - (certificates vs register)` | certificates.json, vessel_register.tsv | 158 certs, 1398 vessels; no holder mismatch; public+cert 158, public no cert 42
- `grep '[^0-9]0\.00' paid_*` | paid files | no 0.00 paid amounts
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py --data environment/data --out out` | environment/data | exit 0, real 0.72 s; 9 documents written; stderr: every station draft_mark=1 assist_mark=1 assist_in_base=True hours 22:00-06:00, monday=True, calendars north/south/west/east; no ambiguity warning
- `cat out/summary.json data_quality.json region_North.json` + json dump of the rest | out/ | shapes as contract; 248 disputes = 253 data rows - 5 rejected; verdicts 103/102/43/0 sum 248; regions 62x4=248; segments 212+36=248; paid accepted 290 per station = 296 - 6 rejected; rejected counts 9/10/5/5
- `ps -axo pid,rss,command | grep python` | - | no derive_report.py process (other listed pythons belong to other jobs)
