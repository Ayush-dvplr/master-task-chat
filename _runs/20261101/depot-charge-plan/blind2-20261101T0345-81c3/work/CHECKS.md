# CHECKS (board be981e2, slug depot-charge-plan)

One line per command: command | input path | what it showed.

## Step 1 - reading
- `python3 "…/tools/name_session.py" be981e2` | - | renamed: opencode `['ses_e6bf8581dffeaayXa7xdenEZ36']`; codex "no match".
- `wc -l instruction.md` + read | `instruction.md` | 25 lines; program `/app/out/derive_report.py --data --out`, 9 JSON documents, stdlib only, <=120 s/run, rules file wins.
- read | `environment/data/docs/charging_rules.md` | 48 lines, 22 numbered rules (windows, needs, caps, tariff/meter, published plan, objective order, document shapes).
- read | `environment/Dockerfile` | python:3.11-slim, copies `data/` to `/app/data`, no extra packages -> stdlib only confirmed.
- read | `environment/data/grid.ini` | plan_date 2026-03-14, first_slot 2026-03-14T12:00, slot_minutes 15, slots 96, feeder_kwh_per_slot 1300.
- read | `environment/data/{service_classes.ini,bus_types.json,depots.json,contracts.json,tariff.xml,disruption_notice.md}` | weights public 4 / commercial 1; E12 30/20, E15 45/30, E18 60/40; cabinet_kwh_per_slot 15 with 30/30/28/35 cabinets; 17 contracts; 3 tariff versions; 2 cabinet outages + 1 derating (170 kWh/slot 20:00-22:00) + 3 extra trips.
- `wc -l` | `environment/data/*.csv`, `trips.jsonl` | fleet_register 4000, roster 4957, trips 5189, published_plan 5240, settlements 2243.
- `python3 work/scan.py` | `environment/data` | 127 roster rows on the plan date; 359 trips for 2026-03-15; 410 published rows on the plan date; settlements span 2026-02-28..2026-03-13.
- `python3 work/meter.py` | `environment/data/settlements.csv` | rule 12 meter search: "band price at the slot's own start" bills all 2243 rows exactly for all four depots; every other candidate (slot end, previous slot, hour floor/end, max/min over hour or slot) misses hundreds of rows. Half-hour floor is indistinguishable here (all band edges land on :00/:30), so one price vector per depot either way.
- `python3 work/scan2.py` | `environment/data/{roster,fleet_register,published_plan}.csv` | 123 buses accepted, 4 roster rejects, 1 published reject; need total 15880 kWh; 3 buses window-short; 3880 (bus,slot) variables.

## Step 2 - program
- `python3 -c "ast.parse(...)"` | `app/derive_report.py` | OKSYNTAX after each of the three appends (loaders, network/solver, reports).
- `cp app/derive_report.py out/derive_report.py` | - | the interface the instruction names (`/app/out/derive_report.py`) now exists in `out/` as well.

## Step 3 - self-check (shipped data only)
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py --data environment/data --out out` | `environment/data` | exit 0, **real 0.51 s** (cap 120 s), no stdout/stderr. No crash, so nothing was fixed.
- `ls -la out/` | `out/` | all 9 documents written: policy_audit.json, region_{North,South,West,East}.json, segment_{commercial,public}.json, summary.json, data_quality.json.
- `python3 -c "json.load(summary.json)"` | `out/summary.json` | plan_date 2026-03-14, weighted_unmet 145, cost 251685 c, moved 0, feeder_peak 975, 96 feeder slots, buses_planned 123, short 3, changed 0, rejected 5.
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 work/check.py` | `out/`, `environment/data` | **real 0.16 s**, 27 checks, `FAILS: none`. Covered:
  - shape: 9 documents exist; key lists and order of every document; 96 slot rows with the right slot names in every region/segment/summary list; policy_audit sorted by bus_id with 123 buses.
  - per-bus rules: charges only inside the bus's window, each <= max_kwh_per_slot, strictly increasing slot order, >0 kWh only, total <= need, need recomputed from trips+extras+reserve-soc, unmet and unmet_reason ("window"/"supply"/null) and `changed` recomputed independently.
  - feasibility: depot energy <= cabinets-in-service x 15 kWh in every slot (outages applied); feeder <= 1300 kWh, and <= 170 kWh in the 8 derated slots (max there 150).
  - cross-totals: regions sum to 15735 kWh / 251685 c, segments sum to 15735 kWh / 251685 c, both equal summary; weighted_unmet, moved, feeder_peak, feeder_kwh_by_slot, buses_planned/short/changed, records_rejected all recomputed and matched; data_quality sorted by file then line.
  - controls the data itself defines (optimality): delivered 15735 kWh equals the sum over buses of min(need, max_kwh_per_slot x window length) = the per-bus maximum, so objective 1 (weighted unmet 145) cannot be improved; cost 251685 c equals the relaxed lower bound that fills each bus's need into its own cheapest window slots ignoring the shared caps, so objective 2 is optimal; the accepted published plan costs exactly 251685 c too and moved_kwh = 0, which with equal totals forces plan == published everywhere, so objective 3 is optimal and no freedom is left for the rule-15 tie-break.
- `ps -axo pid,rss,command | grep python` | - | checked at the end: no python process of mine left running.
