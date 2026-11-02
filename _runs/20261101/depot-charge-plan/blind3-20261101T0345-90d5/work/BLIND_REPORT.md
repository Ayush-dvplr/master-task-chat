# BLIND_REPORT.md - board a60099a / depot-charge-plan / blind3

Session rename: `name_session.py a60099a` ran first and printed `codex: no match`,
`opencode: ['ses_e6bf85760ffe6ERmqUJS1qG75c']` - the rename took on the opencode side.

## Files read, in order

1. `instruction.md`
2. `environment/data/docs/charging_rules.md` (the 22 numbered rules)
3. `environment/data/grid.ini`, `depots.json`, `bus_types.json`, `service_classes.ini`
4. `environment/data/contracts.json` (head), `tariff.xml`, `disruption_notice.md`
5. Headers and samples of `fleet_register.csv`, `roster.csv`, `published_plan.csv`,
   `settlements.csv`, `trips.jsonl` (row counts 4001 / 4958 / 5241 / 2244 / 5189 lines)
6. `environment/Dockerfile` (confirmed the data layout only)
7. At step 5 only: `blind3-20261101T0345-90d5.judge.md`

Nothing outside the blind directory was opened.

## Minutes to first full write

Start 03:45 IST, the program was complete and syntax-clean at 03:56 IST -> **11 minutes**.
The program was written once, in four appended chunks, and then copied to `out/derive_report.py`.

## What the self-check covered, and its result

One run of the program on the shipped data only (0.47 s wall clock against the instruction's 120 s
budget), then two separate checker scripts (`work/verify.py`, `work/localopt.py`). Result: **PASS**.
Coverage, all logged in `work/CHECKS.md`:

- all nine named documents exist; every `slots` list is the full 96 slots in exact time order
- per-bus arithmetic across all 123 buses: zero violations (charges sum to delivered, need - delivered
  = unmet, each charge within 1..max_kwh_per_slot of its type, charges in time order, buses sorted)
- no slot breaks a depot cabinet limit or the feeder limit, cabinet outages and the 20:00-22:00
  derating to 170 kWh included
- region and segment roll-ups reconcile with policy_audit; the four depot costs and the two class costs
  both sum to 251685 = summary.energy_cost_cents
- weighted_unmet_kwh 145 equals its theoretical per-bus window lower bound, so criterion 1 is optimal;
  moved_kwh 0 is the global minimum; no single kWh can move to a cheaper slot without breaking a cap
- missing data folder -> exit 2 with the path named on stderr
- `out/` holds only the nine documents plus the program; the data folder was left untouched; no python
  process of mine left running

## Crash fixed

None. The program ran correctly on its first execution; no logic was reworked after the self-check.

## Judge estimate totals

- lower (PASS only, no negatives fired): **8 / 35**
- upper (PASS + UNSURE): **20 / 35**
- process criteria not performed: 5 (R1, R2, R6, R7, R8)

The rubric turned out to be almost entirely about verification acts on data folders I would have had to
build or alter myself (tiny 3-bus witness, lowered feeder copy, altered-need copy, relocated copy,
copy with one input removed). The blind protocol's step 4 freeze - "do not build extra test inputs" -
rules every one of those out, so the ceiling here was set by the protocol, not by the solution.

## Lessons for the master

1. The judge rubric rewards eight *self-built* test corpora, which step 4's "do not build extra test
   inputs" forbids; a blind run on this task cannot score above ~20/35 however good the program is.
2. Instruction said "only an exact match of the document counts" but never fixed the JSON formatting
   (indent, key order, trailing newline); I had to guess indent=2 with rule-order keys.
3. Rule 12's "the settlements allow exactly one" meter reading is not true literally - several candidate
   readings coincide on this tariff; the rule should say the price per slot is unique, not the rule.
4. Rule 15's last tie-break reads "greater at the first difference" without naming the order direction
   of the comparison; I read it as lexicographically greatest over slot-then-bus_id.
5. A checker that re-reads caps and weights *from the data files* rather than hard-coding them would
   have turned two UNSURE rows (R3, R4) into PASS for almost no extra work - worth making the default.
