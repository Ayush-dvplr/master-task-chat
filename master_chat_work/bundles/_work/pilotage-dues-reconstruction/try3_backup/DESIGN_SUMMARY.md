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
