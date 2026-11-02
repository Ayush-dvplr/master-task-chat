# DESIGN_SUMMARY 49087b0 pilotage-dues-reconstruction (v3 design-blind bytes, L-CONV)

Shape D. Lever SR1 L-CONV: each station has six billing conventions (assist mark, draft mark,
surcharge hours, whether the surcharge base takes the assist line, holiday calendar kept,
whether the Monday after a Sunday holiday is kept). Docs name each family once in its governing
file with a unit-implied domain ("a whole number of minutes no longer than a block", "times of
day to the minute", "one of these calendars"); no ranges listed for a loop, no per-station
readings anywhere (G-2). Principle once (circular s5): the station's accepted paid invoices are
the only record, and exactly one choice of the conventions fits every period (G-1, generator asserts).
SR2 unique tariff fit (>1 listed tariff -> unresolved, cannot_recompute). SR3 notice period split.
COUPLING sentence in circular s6.

Changes from v2 (DESIGN READY): surcharge hours at minute resolution (hidden starts/ends on any
minute); marks unit-implied, not ranged; unresolved periods only on two-period stations
(a narrow solver mapping no fit to unresolved cannot score them); each hidden corpus asserts >= 1 notice and >= 1 unresolved period.

Design-blind folder: WORK/design_blind/ = instruction.md (1,408 chars) + 14 data files
(sample seed 482617, 6,629 lines; docs tariff_circular, exemption_policy, output_contract,
rule_register, station_notices). No tests, solution, TRUTH, notes or proto code.
Hidden prototype seeds for the blind diff: 1101, 1103, 1105 (WORK/proto3/gen3.py).

BRANCH_FIRE (proto3): every hard branch shipped 0/4; hidden 1101/1103/1105 non-headline
stations 4/4 each; SR2 unresolved stations 1/2/4; SR3 notice stations 1/2/4.

Kill lines still true on the fresh design_blind bytes (Docker 4g/2cpu, alarm 600,
logs/run3.log ALL_DONE; units = 12 station x hidden corpus):
| solver | kept | loss |
|---|---|---|
| K1 one convention everywhere (= shipped-carried = v1-equivalent) | 0/12 | WRONG |
| K4w careful wide natural (marks {1,15,16,30}/{1,5,6,10}, whole-hour windows, 7 calendars) | 0/12 | WRONG |
| K4q full marks, all calendars, quarter-hour windows (strongest narrow row) | 1/12 | WRONG (92% lost) |
| reference (full stated domain, decomposed) | 12/12 | EXACT, 0.19-0.26 s |
All solvers <= 0.3 s, shipped 4/4 for every row; no timeout or crash. Optimisation rows N/A.

Plan numbers unchanged from v2 DESIGN.md: 35 checks, positive 143, hidden 91%, w5 tier 70%,
lever 78%; judge 35 positive, probe share 69%, est 26/40/63; predicted final 28.8.

Honest risk: a careful agent that searches the full minute-level domain with decomposition is
the reference and is EXACT. The design blind must lose >= 40% of lever points, else NO CORE.
Shipped boundary plants sit at 21:59/22:00/05:59/06:00 (needed for shipped uniqueness).

## Design blind 5456c27
Verdict: NO CORE. Blind kept 12/12 hidden station units (h1101, h1103, h1105) and 4/4 shipped; 0% of lever points lost; 0 WRONG, 0 TIMEOUT, 0 CRASH.
Seconds per corpus: sample 0.89, h1101 0.87, h1103 1.01, h1105 1.07 (4 min to first full write).
Conventions wrong, per family: assist mark 0/12; draft mark 0/12; surcharge hours 0/12 (minute exact, e.g. 17:36-05:19);
surcharge base 0/12; calendar 0/12; Monday rule 0/12; unresolved periods 0/7; notice splits 0/7.
Full stated domain searched: yes (range(1,11), range(1,31), both bases, all calendars x Monday, arc rectangles at minute level).
| solver | kept/12 | loss |
|---|---|---|
| K1 one convention everywhere | 0 | WRONG |
| K4w careful wide natural | 0 | WRONG |
| K4q full marks, quarter-hour windows | 1 | WRONG |
| blind 5456c27 | 12 | none (EXACT) |
| reference | 12 | EXACT |
Shipped sample check (master 13:20): the shipped conventions are the same at every station by design (degenerate instance) except the calendar,
and they are pinned, not loose: reference and blind each find exactly one choice per station (boundary plants at kA-1/kA, kD-1/kD,
21:59/22:00/05:59/06:00). The uniform prior did not mislead this blind, which searched from the docs, not from shipped values.
Why it failed: once each family's domain is stated (even unit-implied), the loop is small (300 mark pairs x 2 x 180 tariffs, then
calendars and arcs) and a careful first write enumerates it; the L-CONV margin seen in warrant does not hold here.

## Try 4 (anchor-type conventions, 31 Oct 14:05)
- Lever: a station's five conventions are anchors into data the agent holds, not numeric ranges: tonnage (register gross or net), draft (BOARD measured, ORDER declared, register max_draft), time read against hours and holidays (ORDER, BOARD, RELEASE), surcharge hours (stations.tsv watch, outside the station office, outside the vessel agent's office), calendar (vessel flag state, agent office city, or one named calendar of holidays.json). Domain of the reference: 16 x 3 x 3 x 3 x 2 = 864 per station.
- Doc diffs from try 3: numeric rules now fixed and stated (assist per started 30 min, draft per started tenth, surcharge base takes all four lines); new files agents.tsv and stations.tsv; register gains net_tonnage, max_draft, flag, agent; log gains an ORDER line with a declared draft; circular s5 names the five families once without readings ("written down nowhere ... accepted paid invoices are the only record ... exactly one choice"); holidays.json describes its calendars by kind (national, region, flag state, agent office city), never pairs them with a station.
- Shipped (482617): every station port calendar / watch hours / BOARD / measured / gross, 1 period, no notice, no unresolved period; carried reading exact on shipped. The generator asserts one fit over the 864 on shipped as well.
- Hidden prototype corpora h1101 h1102 h1104 h1105 h1106 (1103 fails the corpus assert): non-headline 4/4 each; per-visit anchor (flag/agent calendar or agent hours) 4,4,4,3,3; notice 2,2,1,2,3; unresolved period 1,1,1,2,2. Generator asserts exactly 1 of 864 fits per station per corpus (UNIQUENESS) and the truth tariffs.
- Kill table, Docker (python:3.12-slim, 4g, 2 cpus, alarm 600; log _runs/.../try4-20261031T1353/logs/kill4.log ALL_DONE), hidden stations kept of 20:
  | solver | seconds | result | lever kept |
  |---|---|---|---|
  | ref = K5 full reading (every field and entity the docs mention, 864 per station, count) | 0.22-0.30 | EXACT | 20/20 |
  | K1 shipped reading carried (port/watch/board/measured/gross) + tariff count | 0.16-0.19 | WRONG | 0/20 |
  | K2 first fit over station-wide constants, no count | 0.20-0.26 | WRONG | 1/20 |
  | K4w careful wide over station-wide constants (every calendar as constant, both station hour columns, all times, drafts, tonnages) with count | 0.20-0.29 | WRONG | 2/20 (90% lost) |
  Optimisation solvers N/A (fit task). Shipped inputs fast; every solver exact on shipped.
- Predicted: K1/K4w first write tests about 17-20% (shipped checks and data_quality only), judge mid 40% -> final about 29.
- Honest risk: K5 is exact. A blind that reads the register's flag and agent columns and the holidays.json description and tries them as per-visit anchors recovers everything in under 1 s. The lever rests on the agent fitting station-wide constants (the 5456c27 pattern) and not trying per-visit anchors. Decision for the master: whether a design that a full reading solves exactly is worth the one blind read.
- design_blind refreshed: WORK/design_blind/ = instruction.md (unchanged text) + environment/data/ 16 files (12 data + 4 docs, 7,500 lines) from sample 482617.

## Design blind 529e4de (try 4)
- Program: proto/blind4/derive_report.py (sha256 1735c8e5f442a527c1c5c15647d94ef595f7850d2aa14bca3b159a2246548459), 4 min to first write, shipped-only self-check.
- Docker (4g, 2 cpus, alarm 600; log _runs/.../score-529e4de/logs/score.log ALL_DONE): shipped 4/4 EXACT; hidden h1101 4/4, h1102 4/4, h1104 4/4, h1105 4/4, h1106 4/4 = kept 20/20, lever points lost 0%, no TIMEOUT, no CRASH. Seconds per corpus: sample 2.17, h1101 2.72, h1102 1.83, h1104 1.70, h1105 1.76, h1106 2.07. Summary, segment and data_quality documents also equal the reference on every corpus.
- Anchor families wrong: tonnage none; draft none; time read none; surcharge hours none; calendar none.
- Per-visit anchors tried: yes. Its domain is tonnage gross/net, draft measured/declared/max, time order/board/release, hours watch/station_closed/agent_closed (widened to station_open/agent_open/none when nothing fits), calendar national/region/flag/agent_city. That covers every family the docs name, with a unique-fit count per station.
- Verdict: NO CORE. The blind loses 0% of lever points, well below the 40% bar. Same outcome as try 3: once the docs name the families (circular s5) and the data holds the anchors (register flag/agent, agents.tsv, stations.tsv, ORDER/RELEASE lines), a careful first write enumerates them all in about 2 s. K5 full reading is exact, and the blind did K5.
  | solver | kept /20 | lost | kind |
  |---|---|---|---|
  | ref = K5 | 20 | 0% | EXACT |
  | K1 shipped carried | 0 | 100% | WRONG |
  | K2 first fit constants | 1 | 95% | WRONG |
  | K4w careful constants | 2 | 90% | WRONG |
  | blind 529e4de | 20 | 0% | EXACT |
- Per the master's 13:45 rule, pilotage stays parked; no further tries.
