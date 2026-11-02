# schema-migration-plan-repair, gate v3.6 harden after run a6 (board a4f790c)

Status: DESIGN READY. Lever: 34 gated large-graph worlds (world_47..world_80, w5 each, 170 points; master go 17:0x changed 28 -> 34) from the
`_g_core` family, own RNG stream, where the schema-graph remainder no longer prunes the cheap region. No doc,
instruction, environment or judge change. a6 final repo measured: 0 of 30 prototype worlds (TIMEOUT / 4 GiB kill).

## 1a. Why a6 beat the old lever
a6's planner (WORK/a6_repo/src/migrakit/core/planner.py:83-184, contracts.py:99-122) is an A* over
(schema, field-state tuple) whose remainder is the cheapest schema-graph cost to the canonical schema with
prerequisites ignored (reverse Dijkstra, cached per domain), with per-edge state tables compiled once, a stop when
the popped estimate passes the found total, then a reverse pass over the optimal subgraph and the smallest edge id
(exact M8). That is the tests' own reference method (test_output.src.py:401-456) and the f0331ad kill table's
"A* with schema-graph bound" row (exact 5/5, flagged as a risk). The old worlds hide a cheap 1,100-schema zone
behind exits that cost 9.0-9.9 million, so the schema remainder alone prunes the whole zone: Docker re-run
(proto/a6_old.log) a6 exact on world_29..46, 0.01 s each, versus a5, the blinds and every generic Dijkstra
over 62 s. a6 found the bound at steps 46-65 by profiling its own layered stress graphs (plain planner >180 s on
120 schemas). Every other a6 module equals the oracle (diff only cosmetic), so no WRONG-output lever exists against
it on candidates R3, R4, R8-R12: its code handles each of them like the oracle. A differently shaped world does
beat it inside Law-1 v3.5: make the zone's exits cheap in the schema graph but gated by a prerequisite the zone
never makes present. The schema remainder then stays near zero across the zone, a6 unfolds up to 3^9 field states
per zone schema and runs out of time or memory, while a strictly stronger consistent remainder (per-field
projection, below) prunes the zone and returns the same optimum in 0.2-0.37 s.

## TRIP summary (OUT/TRIP.md)
- Phase A: staged tests/, environment/, solution/, instruction.md identical to BUNDLE; task.toml differs only by
  allowed_hosts staging (lines 25, 32).
- Run a6 on 308399b4016e: tests 291/291 = 100.00, rubric 11/38 = 28.95, final 64.47; 82 steps, 32 min.
- First write steps 19-31 (all graded rules right); steps 46-65 found the schema-graph bound; last src edit
  step 69, re-run step 82 (no FALSE_CLAIM). Judge earned R1, R2, R5, R13, R14; skipped R3, R4, R6-R12
  (never built a graph of 1,000+ schemas, no spaced token, no cost above one million, no K2 comparison).

## Arithmetic
| | tests | rubric | final |
|---|---|---|---|
| a6 now | 291/291 = 100.00 | 11/38 = 28.95 | 64.47 |
| a6 repo after (all 34 new worlds lost) | 291/461 = 63.12 | 28.95 (a6 actual) / 19.7 (f0331ad mid) | 46.0 / 41.4 |
Needed: 291/(291+L) <= 75 gives L >= 97; final <= 50 at a6's own rubric needs tests <= 71, L >= 119.
Chosen L = 170 (34 x 5): lever share 170/461 = 36.9% (band 25-40). A first-write program that also fails the
old 18 core worlds (a5, blinds) loses 90 + 170: 201/461 = 43.6 (combined core share 56.4%; accepted by master, see risks).

## Design (P-3 instance, hidden-scale loss under v3.5)
Docs it follows from (no new sentence, no size or method word):
- K14 repository_contract.md:88-93: <= 1,200 schemas, <= 6,000 edges, <= 8 prerequisite fields, <= 10 fields,
  plan <= 80 edges; "every plan_migration call must return within 10 seconds on a machine with 2 CPUs, including
  graphs whose number of distinct paths is far too large to list".
- M2 migration_semantics.md:10-11 (positive integer costs), M3 :13-15, M4 :17-22, M6 :31-33, M7 :35-39
  (revisits allowed), M8 :41-44 (smallest cost, then smallest edge-id list); N2-N4 null_semantics.ini (presence, add).
Generator `_g_gate(w, number)` (copy of `_g_core` body, stream `_rng(9000 + number)`, zone out-degree 5):
corridor, side and 40,000,000 start->target edge as `_g_core`; a fourth sampled field `gate` (a prerequisite
field, policy default 1-9) that no zone or entry operation names; `start -> door` with `add:gate` at 5-6 million;
`door -> zone` 1-5; 40 zone exits `has:gate` to the canonical schema at cost 1-5. Same rejection filters as
`_g_core` (plan exists, <= 80 edges, cost < 1,000,000, first edge without operations, side unused) and the same
K14 asserts. One hard record per world (child timeout 10 x 1 + 20 = 30 s). Prototype 47-76: 1,146-1,200 schemas,
5,719-5,989 edges, plans 12-14 edges; 300 seeds all built, max 1,200 / 5,995, reference max 0.372 s.
Reference: `_reference_plan` gains a stronger remainder, max(schema-graph remainder, for each prerequisite field
the cheapest cost to the canonical schema in the projection (schema, state of that field), other fields unknown:
its own `has`/`lacks` exact, rename into it may give null or value, rename out of it or drop gives absent, add per
N4). Each projection is a relaxation, so the remainder is admissible and consistent; with the heap key
(cost + remainder, edge-id list) the first canonical pop is still the M8 optimum. Measured: on all 987 calls the
current tests make (46 worlds, ladder, scale cases) the stronger reference returns identical plans
(proto/gate.py same: diff 0, expected digest b0f465e55d9b6d1a), so every old check's expected output is unchanged.
Loss for a schema-bound A* (a6, old oracle), plain or tuned Dijkstra, exhaustive: no plan within the 30 s child
cap (a6 killed at 4 GiB after 78 s on world_47); dominance, prerequisite-keyed, greedy, schema-only: WRONG plan.

## Measured kill table (Docker python:3.12-slim, --cpus 2 --memory 4g, RLIMIT_AS 4 GiB, timeout 40 s; WORK/KILL_TEST.md, proto/kill4.log)
| solver | worlds | exact | WRONG | TIMEOUT/CRASH | max s | lever kept | shipped fast |
|---|---|---|---|---|---|---|---|
| a6 final repo | 30 | 0 | 0 | 30 (300 s cap: killed 78 s, >151 s) | - | 0% | yes |
| strong reference | 30 | 30 | 0 | 0 | 0.34 | 100% | yes |
| old reference / oracle repo_fixed | 5 / 6 | 0 | 0 | 5 / 6 | - | 0% | yes |
| run a5 program | 6 | 0 | 0 | 6 | - | 0% | yes |
| blinds cee149a, 4f7606c, Opus a4 | 6 each | 0 | 0 | 6 each | - | 0% | yes |
| blinds d721, d2fb, 9179, b686 | 6 each | 0 | 0 | 6 each | - | 0% | yes |
| fast Dijkstra, incumbent, bidirectional, Dijkstra, exhaustive, A* schema bound | 5 each | 0 | 0 | 5 each | - | 0% | yes |
| dominance / prerequisite-keyed | 5 each | 0 | 5 each | 0 | 1.18 / 37.1 | 0% | yes |
| greedy / schema-only | 5 each | 0 | 5 each | 0 | 0.00 | 0% | yes |
Bar: a6 repo 63.12 <= 75 (computed: 34 worlds x 5 lost, every other check passes as in run a6); every program
and generic solver loses 100% (>= 15%) of lever points; reference 0.372 s = 1/27 of the stated 10 s (<= 1/4);
first-write (a5-like) 43.6 and all-but-one 63.1 <= 75. v3.5: (1) no shipped or visible input is slow (a6 and a5
ran them in seconds), (2) limit stated K14 :90-93, (3) cost 36.9% (v3.6 band) inside 34 lever checks, each its own
child call. Full-test Docker measurement of the a6 repo runs in Phase 3 (cost table).

## Predicted run score
tests 63.1 (a6-like) to 43.6 (a5-like), rubric 15-30 (f0331ad mid 19.7; a6 28.95), final 41.4-46.0 for an
a6-like run; with ±17.5 tests variance a final above 50 needs tests above 71 and rubric near 29 together.

## Phase 2 hunks (G7: every tests/ and solution/ hunk named here)
1. test_output.src.py: new `_g_gate` after `_g_core` (:1575); `_reference_plan` (:401-456) gains the projection
   remainder (expected outputs of all old checks byte-identical, digest before/after of every world expectation,
   ladder and case); WORLDS gains world_47_core_gated_graph .. world_80_core_gated_graph (`("GATE",)`); `_world`
   (:1641) one dispatch branch for GATE (salt 100 + index as now); `_world_holds` timeout line gains GATE
   (TIME_LIMIT_SEC * len(lines) + 20, same formula as CORE); 34 check functions (same body shape as world_29);
   34 registrations weight 5. Old check bodies byte-identical. Then embed.py (reward.toml 0.5/461).
2. solution/solve.py planner (:92-150) and WORK/repo_fixed + make_solve.py/solve_template.py: same projection
   remainder so the oracle passes the new worlds (oracle runs in the Docker gate x3).
3. No change to instruction.md, environment/, task.toml, tests/judge.toml (no criterion pays the same observable;
   R6/R7 grade trajectory acts, not plans). TRUTH.md, LEVERS, COST_TABLE, QC_DEFENCE, XREF, DESIGN by script/hand last.
Checks 81 -> 115 (TS-23 warn kept, option A); positive 291 -> 461. Verifier worst case (program failing all 46
core worlds): 18 x 60 s + 34 x 30 s + ~120 s ~ 2,220 s of 2,700 s; a6-like ~67 + 34 x 30 = ~1,090 s.

## Risks
- A careful Opus may find the projection bound when it times a 1,000-schema graph whose cheap exits are gated
  (R6/R7 probes); a6 never built one. The 3 fresh blinds (if master runs them) are the measure.
- Combined core share for weak programs is 56.4% of positive points (old 90 + new 170); the v3.6 band (25-40%) is
  met by the new lever alone (32.5%). Master to accept or ask for fewer new worlds (24 worlds: 29.2%, a6 70.8,
  final at a6 rubric 49.9, too thin).
- Docs unchanged, so no fresh blinds are required by the prompt rule; judge unchanged.

## Lessons for the master
- A TIMEOUT lever holds only against programs weaker than the reference method | no change: kill tables must include the reference method itself as a plausible solver row (f0331ad listed it and still counted the lever).
- Gate the cheap region with a prerequisite, not with a dear exit, so the obvious admissible bound stops pruning | no change: design note for P-3 levers.
