# BLIND_REPORT (board be981e2, slug depot-charge-plan, blind2-20261101T0345-81c3)

Session renamed to `be981e2` at 03:45 IST: the tool listed `opencode: ['ses_e6bf8581dffeaayXa7xdenEZ36']`
and `codex: no match`. Start 03:45, frozen (step 4) 03:56 IST.

## Files read, in order
1. `instruction.md`
2. `environment/` listing, `environment/Dockerfile`
3. `environment/data/docs/charging_rules.md` (the 22 rules)
4. `environment/data/grid.ini`, `service_classes.ini`, `tariff.xml`, `bus_types.json`, `depots.json`, `disruption_notice.md`
5. heads of `fleet_register.csv`, `roster.csv`, `published_plan.csv`, `settlements.csv`, `trips.jsonl`, `contracts.json`
6. full scans through my own scratch scripts: `work/scan.py` (counts), `work/meter.py` (rule-12 meter search over `settlements.csv`), `work/scan2.py` (roster acceptance, needs, windows, published-plan rejects)
7. `work/TODO.md` (written by me at the start, re-read before each step)
8. `blind2-20261101T0345-81c3.judge.md` — only at step 5, after step 4 was ticked

## Minutes to first full write
**~9 minutes.** `app/derive_report.py` was written complete in three appends (loaders → network and
solver → reports) and first ran successfully at 03:54, 9 minutes after the 03:45 start. No earlier
partial version was run.

## What the self-check covered, and its result
One run of the program on the shipped data only: `app/derive_report.py --data environment/data --out out`,
exit 0, **0.51 s** wall clock against the instruction's 120 s cap, no output on stderr. Then one separate
script, `work/check.py` (**0.16 s**), with **27 checks, all PASS, `FAILS: none`**:

- shape — all 9 documents present; exact key lists and key order per document; 96 slot rows with the
  right slot names in every region, segment and summary list; `policy_audit.json` sorted by `bus_id`
  over all 123 accepted buses;
- per-bus rules recomputed from the raw files — charges inside the window, ≤ `max_kwh_per_slot`,
  strictly increasing in time, positive only, summing to `delivered_kwh` and never above `need_kwh`;
  `need_kwh` from trips + extra trips + reserve − soc; `unmet_kwh`, `unmet_reason` and `changed`;
- feasibility — depot energy ≤ cabinets-in-service × 15 kWh in every slot with both outages applied;
  feeder ≤ 1300 kWh everywhere and ≤ 170 kWh in the 8 derated slots (peak there 150 kWh);
- cross-totals — the four regions and the two segments each sum to 15735 kWh and 251685 cents, equal
  to `summary.json`, every field of which was recomputed; `data_quality.json` sorted by file then line;
- controls the files themselves define (optimality) — delivered 15735 kWh equals Σ min(need,
  `max_kwh_per_slot` × window length), so objective 1 (weighted unmet 145) is at its floor; cost
  251685 c equals the relaxed lower bound that fills each bus's need into its own cheapest window slots
  ignoring the shared caps, so objective 2 is optimal; the accepted published plan costs the same
  251685 c and `moved_kwh` is 0, which with equal totals forces plan = published slot by slot, so
  objective 3 is optimal and rule 15's final tie-break has nothing left to choose.

Key figures: plan_date 2026-03-14, weighted_unmet 145 kWh, cost 251685 c, moved 0 kWh, feeder peak
975 kWh, 123 buses planned, 3 short (all `window`-limited), 0 changed, 5 records rejected.

## Crashes fixed
**None.** The first run of the completed program exited 0 and produced all nine documents; no logic or
crash fix was made after the self-check.

## Judge estimate totals
- lower (PASS only, minus fired negatives): **14 / 35 = 0.40**
- upper (PASS + UNSURE, minus fired negatives): **20 / 35 = 0.571**
- process criteria not performed: **5** (R1, R2, R6, R7, R8 — all need extra or altered data folders)
- No negative criterion fired.

## Lessons for the master
1. The judge's positive weight is dominated by process criteria (R1, R2, R6, R7, R8 = 15 of 35 points) that all require building or altering extra data folders, which the blind protocol's step 4 explicitly forbids — the blind run cannot score above ~0.57 by construction.
2. R11 wants the literal `python3 /app/out/derive_report.py --data /app/data --out /app/out` after the last edit, but the blind path mapping makes me run `app/derive_report.py` and copy to `out/` afterwards; mapping and freeze together cost a criterion that the containerised run would pass.
3. R5 asks to show that **exactly one** meter candidate fits, yet in this corpus two candidates (slot-start and half-hour floor) bill all 2243 settled rows exactly, because every band edge lands on :00 or :30 — the rule's "the settlements allow exactly one" is not true of the shipped data for any reasonable candidate family.
4. Rule 12's "each depot's meter has its own way of applying a tariff" reads as if the four depots differ; they do not here (one identical price vector), so the whole per-depot machinery is dead weight and invites over-engineering.
5. `moved_kwh = 0` and `buses_changed = 0` mean the published plan already is the optimum, so rules 14, 15's tie-break and the `changed` field are never exercised — a corpus where the published plan is slightly infeasible would test far more of the stated objective order.
