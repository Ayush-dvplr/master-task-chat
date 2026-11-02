# CHECKS (board ec4f695, depot-charge-plan)

BLIND_DIR = /Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind1-20261101T0345-360b
All data paths below are under BLIND_DIR; `D` = BLIND_DIR/environment/data.

## Step 1 - reading
- `python3 master_chat_tasks/tools/name_session.py ec4f695` | - | printed `codex: no match` and `opencode: ['ses_e6bf858ddffeYv1XCCJA6lpi76']`; session named.
- `date` | - | Sun Nov 1 03:45:07 IST 2026 (start).
- read instruction.md | BLIND_DIR/instruction.md | 25 lines; program at /app/out/derive_report.py, 9 JSON outputs, stdlib only, 120 s per run.
- `ls -la` + `find environment -type f` + `wc -c` | BLIND_DIR | Dockerfile + 13 data files; largest trips.jsonl 447 KB, roster.csv 330 KB.
- read docs/charging_rules.md | D/docs/charging_rules.md | 48 lines, 22 numbered rules (slots, rejections, need, limits, tariff/meter, objective order, report fields).
- `cat grid.ini bus_types.json depots.json service_classes.ini contracts.json tariff.xml disruption_notice.md` | D | plan_date 2026-03-14, first slot 12:00, 96 x 15 min, feeder 1300; types E12/E15/E18; cabinet 15 kWh, cabinets N30 S30 W28 E35; weights public 4 commercial 1; 17 contracts; 3 tariff versions (in force 2026-03-14: 31/27/14/22); notice = 2 cabinet outages, feeder derate 170 kWh 20:00-22:00, 3 extra trips.
- `head -4` on settlements.csv, roster.csv, fleet_register.csv, published_plan.csv, `head -3` trips.jsonl + `wc -l` | D | 2243 settlements, 4957 roster rows, 4000 vehicles, 5240 published rows, 5189 trips.
- `python3 -c` counts | D | 127 roster rows on the plan date (N33 S32 W31 E31); 359 trips dated 2026-03-15; 410 published rows on the plan date over 120 buses; settlements 558/555/561/569 per depot.
- `python3 -c` meter-candidate fit test | D/settlements.csv + D/tariff.xml | per-slot band price at the slot start reproduces `cents` for 558/558 North, 555/555 South, 561/561 West, 569/569 East; every whole-session candidate (start/end/max/min/mean) fails ~100 rows per depot, so the unique meter rule is "price of the band containing the slot start" for all four depots.

## Step 2 - program
- `python3 -c "import ast; ast.parse(...)"` x3 after each append | BLIND_DIR/app/derive_report.py | OK, 881 lines, no syntax error.

## Step 3 - self-check
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py --data environment/data --out out` | D -> BLIND_DIR/out | exit 0, real 1.38 s; wrote all 9 documents (policy_audit, 4 region, 2 segment, summary, data_quality).
- `python3 -c` dump summary.json + data_quality.json | BLIND_DIR/out | plan_date 2026-03-14, weighted_unmet 145, cost 251685 c, moved 0, feeder peak 975, 123 buses planned, 3 short, 0 changed, 5 rejected; 55 of 96 slots carry energy.
- `python3 -c` plan vs published_plan.csv cell compare | BLIND_DIR/out + D/published_plan.csv | the 409 accepted published cells and the 409 planned cells are identical (15735 kWh both); the only difference against the raw file is the rejected row 411 (B1082 19:15, 15 kWh) - this is the control the data itself defines, and it confirms moved_kwh 0 / buses_changed 0.
- `python3 -c` full constraint + cross-total verification | BLIND_DIR/out + D | 0 constraint errors: every charge inside its bus window, kWh <= max_kwh_per_slot, delivered <= need, unmet = need - delivered, charges in time order, per-slot depot energy <= cabinets-in-service x 15 (North 21:15-22:15 and South 02:00-03:00 reduced), per-slot all-depot energy <= 170 in 20:00-22:00 and <= 1300 elsewhere; feeder peak 975 = summary; region slot kWh = recomputed depot series and region feeder_kwh = all-depot series; region sums 123 buses / 15735 kWh / 251685 c / 145 unmet = summary; segment sums (commercial 90 buses 11355 kWh 178145 c 145 unmet; public 33 buses 4380 kWh 73540 c 0 unmet) = summary; weighted unmet recomputed 145; policy_audit bus_ids sorted.
- `python3 -c` rejected-row dump | D/roster.csv, D/published_plan.csv | line 1038 B5004 arrive 22:00 after depart 19:30; line 2176 B9990 absent from fleet_register.csv; line 3851 B1029 second accepted row of the plan date; line 3962 B5000 register status retired; published line 411 B1082 slot 19:15 before its 19:45 arrival.
- `cp app/derive_report.py out/derive_report.py` then `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py --data environment/data --out out` | D -> BLIND_DIR/out | exit 0, real 1.74 s, identical figures; this is the last run, made after the last change to the program.
- `ps -axo pid,rss,command | grep python` | - | no python process of this run left behind (checked again at the end of the session).

No crash occurred; the program was not changed after the self-check.
