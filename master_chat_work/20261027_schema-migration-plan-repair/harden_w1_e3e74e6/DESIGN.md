# schema-migration-plan-repair, wave 1 harden design (board e3e74e6)

Status: DESIGN READY, with one change from the master notes: the named primary lever P-2 fails the
kill test (both real strong programs are exact on it); Design 2 uses P-3 (exact cheapest plan on a
larger hidden graph, inside limits the contract already states). P-4 checks are not proposed (every
program measured keeps them). Needs "go" on that swap.

## Phase A
`diff -rq` of the probe's staged `tests/` and `environment/` vs BUNDLE: empty. Tasks_INPUT vs BUNDLE: empty.
Session rename: `name_session.py e3e74e6` printed "codex: no match / opencode: ['ses_e841e838bffes1e1YxsYMiaftF']".
QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (expected 5574d77e).

## Diagnosis (probe a4, 96 steps, 112 min, tests 201/201, judge -1/13)
| minutes | steps | what the agent did |
|---|---|---|
| 0-0.5 | 3-11 | read contract, ci files, repo |
| 3.9-5.4 | 15-27 | rewrote records, planner, identity, feed, contracts tokens, classify, pipeline, cli + `__main__`: every defect fixed on first write |
| 5.5-8.7 | 28-41 | checks on shipped data, all pass |
| 9-103 | 42-65 | planner fuzz vs brute force and speed work; planner rewrites at steps 52, 59, 62 |
| 103-112 | 66-95 | deliverables, README, extra checks |
The only part that cost the agent time was planner speed; the hardest part (state-aware planner) was right at step 21.
Its final planner is still plain Dijkstra over (schema, field state) with no lower bound.

## Design 1: P-2 long stateful replay (master note 2) - FAILED
This task has no views or foreign keys; the stated rules that act on the same objects in sequence are
K16 holder / replay / conflict / REISSUE supersede chains, C3/C4 corrections that belong to every
execution of an identity and apply on first arrival along plans that revisit schemas, K13 received_seq
order and receipts, K3 alias and merge relays, and rename/drop/add/cast chains on shared field names (M4-M6).
Prototype (`WORK/proto/history.py`): 4 corpora of 976 lines and 518-560 corrections, 40 identities x 8
version runs each, 351-361 superseded rows, shuffled seqs. Result: oracle, Opus a4 and blind cee149a all
exact (the blind summary lacks only `receipt_mismatches`, a lever added after that blind ran). Only the
deliberately wrong variants lose (name keyed 484-518 rows, end resolve 61-67, file order 250-292, greedy
188-265). The stated rules make the reference structure the natural one, so longer histories add no loss.

## Design 2: P-3 exact cheapest plan on larger hidden graphs - HOLDS
Objective and constraints, as the docs already state them (no new sentence):
- M8: the plan has minimum total cost, then the smallest edge-id list; M6 prerequisites hold on the record
  as it stands at that point of the plan; M7 plans may revisit schemas.
- K14 (repository_contract.md:88): at most 1,200 schemas, 6,000 edges, 8 prerequisite fields and 10
  fields per domain, 80 edges per plan; every `plan_migration` call returns within 10 s on 2 CPUs,
  "including graphs whose number of distinct paths is far too large to list".
Hidden instance (new gadget, own RNG stream 5000+salt, generator asserts the K14 bounds):
1,038 schemas, 4,150 edges, one domain, 10 fields (8 prerequisite), optimum plan 13 edges. A priced
corridor (12 layers x 3 lanes, prerequisites and add/drop/rename ops) leads to the canonical schema; a
region of 1,000 schemas joined by edges of cost 1-4 with field churn is entered cheaply from the start
and the early corridor and leaves to the canonical schema only through edges of cost 9-10 million;
a direct escape edge costs 40 million. Every payload has a plan well under 1 million.
Reference structure: the field state never lowers the cost of reaching the canonical schema below the
schema-graph distance with prerequisites ignored, so that distance is a lower bound; a label-setting
search ordered by (cost so far + bound, edge-id list) returns the M8 plan while settling only states whose
cost plus bound is under the optimum. Checked equal to the tests' `_reference_plan` on 120 small cases.
Wrong document a plausible program writes: none from plain Dijkstra (it is exact but needs 47-124 s and
more per call: the cheap region holds up to 3^10 field states per schema, all cheaper than the optimum);
greedy and schema-only planners write the wrong plan, cost and completed steps; exhaustive times out.

## Kill table (Docker python:3.12-slim, --cpus 2, --memory 4g, 10 s alarm per call; WORK/KILL_TEST.md)
| solver | instance | seconds | exact | points kept |
|---|---|---|---|---|
| reference bounded search | 8 x 3 payloads | 0.01 max | 24/24 | 100% |
| greedy cheapest allowed edge | same | 0.04 | 0/24 wrong plan | 0% |
| schema-only shortest path | same | 0.01 | 0/24 wrong plan | 0% |
| naive exhaustive (<= 80 edges) | same | >10 | 0/24 | 0% |
| plain Dijkstra over (schema, state) | same | >10 | 0/24 | 0% |
| blind cee149a planner | same | 8.53 one exact, rest >10 | 1/24 | 4.2% |
| Opus a4 planner | same | 8.56 one exact, rest >10 | 1/24 | 4.2% |
| current oracle repo_fixed planner | same | >10 | 0/24 | 0% |
| name keyed / end resolve / file order | same planner as Opus | >10 | <= 1/24 | <= 4.2% |
No alarm, first payload of 3 instances: Opus 46.7 s exact, 121.9 and 122.3 s unfinished; blind 112.0 s
exact, 124.3 and 123.8 s unfinished. Reference max 0.01 s = 1/1000 of the limit.
P-4 candidates (nested relative `--out`, rerun over an older longer run): PASS for blind, Opus and oracle.

## Phase 2 build plan (after "go")
1. Tests (`WORK/test_output.src.py` -> embed.py): add `_g_core` gadget and 8 worlds `world_29`..`world_36`
   (tag CORE) appended to WORLDS so existing salts and expectations are unchanged. Each core world holds
   only the core domain: one hard record from the start schema and 3 easy records from late corridor
   schemas, one partner, no other gadgets (no double pay, TS-26). Graded whole document (records +
   summary) like the other worlds; child budget 10 s per record plus 20 s overhead (fair to the per-call
   limit). Retune so every hard payload takes plain Dijkstra > 60 s in Docker (the one 8.5 s case goes).
2. Tests' reference planner: add the bounded search beside `_reference_plan`, used for every world;
   re-run check_exact / check_worlds to show all 28 existing expectations byte-identical (G9).
3. Oracle: `WORK/repo_fixed` planner and `solution/solve.py` (make_solve.py) switched to the bounded
   search; oracle must pass every core world in <= 1/4 of the budget.
4. Weights: 8 x 5 = 40 points; positive total 201 -> 241; lever share 16.6% (inside 10-30%);
   all-but-one program (core worlds only lost) 201/241 = 83.4% (<= 92). Hidden share rises (Shape D).
5. Docs: no new sentence. K14 already states the sizes, the 10 s limit and the too-many-paths clause;
   no method words added; no size bound beyond K14. G5 whole-document sentence already in instruction.md.
6. Rule 6 (embed `_SHIPPED_DATA`, reward.toml 0.5/241, TRUTH by script last), DESIGN "Wave 1 hardening",
   LEVERS, COST_TABLE, QC_DEFENCE (AL-1, AL-2, AL-27, CL-4, TS-13, TS-19, TS-20, IN-15/16/17 rows),
   XREF until 0 findings, stacking_check, precheck, Docker gates oracle x3 / owner / nop / stub / forgery.

## Risks
- Tariff lesson: a schema-level lower bound is a short, known change. The blind and Opus both spent their
  speed effort on constant factors, but a fresh solver that times the shipped limit sentence against a
  large self-built graph may find it. The P13 blind read is the measure.
- Memory: plain Dijkstra reached 1.6-2.2 GB RSS before the alarm; the 4 GB container holds it.
- The current oracle fails the new worlds until step 3 lands; gates run only after it.
