# BRANCH_FIRE (v2, prototype proto2/gen2.py; shipped seed 482617, hidden 1101-1104)

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| SR1 assist mark | mark other than 1 | 0/4 stations | 1101 4/4, 1102 4/4, 1103 4/4, 1104 4/4 |
| SR1 draft mark | mark other than 1 | 0/4 | 1101 3/4, 1102 4/4, 1103 4/4, 1104 2/4 |
| SR1 surcharge hours | window other than 22:00-06:00 | 0/4 | 1101 3/4, 1102 3/4, 1103 4/4, 1104 4/4 |
| SR1 surcharge without assist | assist not reckoned | 0/4 | 1101 2/4, 1102 0/4, 1103 3/4, 1104 2/4 |
| SR1 calendar | calendar other than own regional | 0/4 | 1101 3/4, 1102 1/4, 1103 3/4, 1104 3/4 |
| SR1 Monday after Sunday holiday | Monday not kept | 0/4 | 1101 3/4, 1102 4/4, 1103 2/4, 1104 1/4 |
| SR1 any non-headline convention | station differs from shipped choice | 0/4 | every seed 4/4 (16/16) |
| SR2 ambiguous period | > 1 listed tariff fits | 0/4 | 1101 2, 1102 2, 1103 1, 1104 2 stations (7/16, every seed) |
| SR3 notice | second period | 0/4 | 1101 2, 1102 1, 1103 3, 1104 2 stations (8/16, every seed) |

Per-station truth (kA, kD, Monday, assist reckoned, calendar, window minutes):
- 1101 North 2,9,F,F,north,(1245,525) amb; South 27,4,F,T,west,(1320,360) notice 08-12 amb p0;
  West 24,4,F,T,harbour,(1410,525); East 20,1,T,F,west,(1215,300) notice 08-14.
- 1102 North 26,2,F,T,north,(1320,360) notice 08-26; South 3,8,F,T,national,(1320,450) amb;
  West 4,10,F,T,west,(1260,420); East 27,6,F,T,east,(1125,510) amb.
- 1103 North 15,3,T,T,harbour,(1245,435) notice 08-01; South 12,8,F,F,south,(1245,300) notice 08-11;
  West 30,3,F,F,north,(1365,240) amb; East 30,3,T,F,south,(1155,345) notice 08-11.
- 1104 North 2,8,T,T,harbour,(1305,270); South 8,1,F,F,fishery,(1155,255) notice 08-01;
  West 3,9,T,F,west,(1245,300) amb; East 16,1,T,T,national,(1140,315) notice 08-26 amb p1.

Degenerate-shipped check: every hard branch has shipped count 0 and fires on every hidden
corpus that grades it (SR1 every seed every station; SR2 and SR3 at least one station per
seed, asserted by the generator). Counts computed by script from the prototype truth records. The bundle generator forces every
family branch on at least one station of every seed set (G12). Re-run on the bundle generator in Phase 2 and Phase 4.

## Phase 0b: design-blind bytes (proto3, minute-resolution hours, unit-implied domains)

Counts by script from proto3 truth (gen3.py; sample = design_blind/environment/data, seed 482617 shipped; hidden seeds
1101, 1103, 1105), stations of 4 per corpus:

| rule / branch | shipped sample | h1101 | h1103 | h1105 |
|---|---|---|---|---|
| SR1 assist mark != 1 | 0 | 4 | 4 | 4 |
| SR1 draft mark != 1 | 0 | 4 | 3 | 4 |
| SR1 surcharge hours != 22:00-06:00 | 0 | 3 | 4 | 4 |
| SR1 surcharge base without assist | 0 | 2 | 2 | 3 |
| SR1 calendar not own | 0 | 3 | 3 | 2 |
| SR1 Monday after Sunday holiday not kept | 0 | 3 | 3 | 3 |
| SR1 hours off the whole hour | 0 | 3 | 4 | 4 |
| SR1 hours off the quarter hour | 0 | 3 | 4 | 4 |
| SR1 mark outside {1,15,16,30}/{1,5,6,10} | 0 | 4 | 3 | 4 |
| SR1 any non-headline convention | 0 | 4 | 4 | 4 |
| SR2 unresolved period | 0 | 1 | 2 | 4 |
| SR3 notice (second period) | 0 | 1 | 2 | 4 |

Every hard branch: shipped 0, fires on every hidden corpus (gen3 asserts >= 1 notice station and >= 1 unresolved
period per hidden corpus; unresolved periods occur only on two-period stations, so a station is never wholly
unresolved).

## Try 4 (stations of 4, from generator truth)
| rule | branch | fires on shipped (count) | fires on hidden (h1101,h1102,h1104,h1105,h1106) |
|---|---|---|---|
| SR1 conventions | any non-headline anchor | 0 | 4,4,4,4,4 |
| SR1 conventions | per-visit anchor (flag/agent calendar or agent hours) | 0 | 4,4,4,3,3 |
| SR2 unresolved | period with more than one tariff | 0 | 1,1,1,2,2 |
| SR3 notice | station with two periods | 0 | 2,2,1,2,3 |
