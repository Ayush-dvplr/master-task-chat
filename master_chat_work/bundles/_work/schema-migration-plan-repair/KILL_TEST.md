# Wave 1 kill test (board e3e74e6, 27 Oct 2026)

Docker: `python:3.12-slim`, `--cpus 2 --memory 4g`, script `proto/kill.sh`, log `proto/kill_docker.log` (ALL_DONE, 12:20-12:49 IST).
Stated limit: K14, 10 s per `plan_migration` call on 2 CPUs. Per-call alarm 10 s unless noted.

## Design 1: P-2 long stateful replay (master note 2) - FAILS

4 prototype corpora from the tests' world family (`proto/history.py`): 976 feed lines and 518-560
corrections each, 40 identities x 8 version runs per history, partner forms via id, alias and merge relays,
REISSUE chains (351-361 superseded rows), corrections pinned along revisiting plans, shuffled received_seq.
Reference = tests' `_ref_pipeline`, 0.17-0.26 s. Whole document (records + summary).

| solver | corpora exact | rows differing | points kept |
|---|---|---|---|
| oracle repo_fixed | 4/4 | 0 | 100% |
| Opus a4 final repo | 4/4 | 0 | 100% |
| blind cee149a repo | 4/4 on records | 0/976 | 100% (summary differs only by the missing `receipt_mismatches` key: the blind ran before that lever existed) |
| Opus, identity keyed by raw partner text | 0/4 | 484-518 | 0% |
| Opus, corrections applied once after execution | 0/4 | 61-67 | 0% |
| Opus, feed file order | 0/4 | 250-292 | 0% |
| Opus, greedy planner | 0/4 | 188-265 | 0% |

Both real strong programs are exact on every long chained replay: the stated rules already make the
reference structure (holder per identity, corrections per execution, received order) the natural one.
Only the deliberately wrong variants lose. Design 1 does not meet "blind program loses >= 15%".

## Design 2: P-3 exact cheapest plan on a larger hidden graph, inside the stated K14 limits - HOLDS

8 prototype instances (`proto/core.py gen /tmp/core 8 1000`), 3 payloads each: one domain, 1,038 schemas,
4,150 edges, 10 fields of which 8 are prerequisites, plan length 13 (limits 1,200 / 6,000 / 8 / 10 / 80).
Shape: a priced corridor to the canonical schema plus a large region of very cheap edges whose only exits to
the canonical schema are very expensive. Reference: label-setting search ordered by cost so far plus a
schema-graph lower bound (ties by edge-id list), checked equal to the tests' `_reference_plan` on 120 small
cases (`core.py check 40 6`: bad 0).

| solver | calls exact | wrong plan | over 10 s | seconds (max) | points kept |
|---|---|---|---|---|---|
| reference (bounded search) | 24/24 | 0 | 0 | 0.01 | 100% |
| greedy cheapest allowed edge | 0/24 | 24 | 0 | 0.04 | 0% |
| schema-only shortest path (prerequisites ignored) | 0/24 | 24 | 0 | 0.01 | 0% |
| naive exhaustive walks (<= 80 edges) | 0/24 | 0 | 24 | 10.0 | 0% |
| plain Dijkstra over (schema, field state) | 0/24 | 0 | 24 | 10.9 | 0% |
| blind cee149a planner | 1/24 | 0 | 23 | 8.53 (exact one) | 4.2% |
| Opus a4 planner | 1/24 | 0 | 23 | 8.56 (exact one) | 4.2% |
| current oracle repo_fixed planner | 0/24 | 0 | 24 | 10.8 | 0% |
| Opus variants (name keyed, end resolve, file order) | same planner as Opus | | | | <= 4.2% |

Without the alarm (first payload of core_00..02, limit 120 s): Opus 46.7 s exact, 121.9 s and 122.3 s unfinished;
blind 112.0 s exact, 124.3 s and 123.8 s unfinished. So the plain programs are 5-12x over the stated limit.
Reference max 0.01 s = 1/1000 of the limit (<= 1/4 holds).

## P-4 candidates (secondary)

| check | blind | Opus | oracle |
|---|---|---|---|
| CLI `--out` nested relative folder that does not exist (K10 "creates the output folder if needed") | PASS | PASS | PASS |
| CLI rerun into an `--out` holding an older, longer run gives the fresh-run bytes (K10 "writes") | PASS | PASS | PASS |

Both stated behaviours are kept by every program measured, so they would only dilute the lever; not proposed.

## Final generator (Phase 2, after "go"): the 8 graded worlds world_29..world_36

Docker `python:3.12-slim` (3.12.15), `--cpus 2 --memory 9g`, script `proto/kill2.sh`, 2 jobs in parallel,
every job under `timeout 70` and RLIMIT_AS 4 GiB (the verifier child cap), on the hard record of each world
as built by the tests' own `_world` (`proto/core2.py gen`). Log `/tmp/opencode-logs/smpr_w1_chain.log`
(13:30-14:04 IST). Worlds: 1,145-1,195 schemas, 4,575-4,778 edges, 10 fields (8 prerequisites),
hard plans 12-14 edges; reference over all 32 records (hard + 3 easy each) 0.01-0.10 s.
"Wall 70" means killed by the 70 s timeout (no plan returned): over the 60 s bar of master item 2.

| solver | worlds exact | wrong plan | killed at 70 s | max seconds | lever points kept |
|---|---|---|---|---|---|
| reference (tests `_reference_plan`, bounded) | 8/8 | 0 | 0 | 0.04 | 40/40 |
| new oracle planner (repo_fixed) | 8/8 | 0 | 0 | 0.03 | 40/40 |
| (a) speed-tuned plain Dijkstra (int base-3 state, tuple heap, stop on first goal pop) | 0/8 | 0 | 8 | >70 | 0 |
| (b) Dijkstra + dominance (same schema, superset of present prerequisites, cost <=) | 0/8 | 8 | 0 | 4.8 | 0 |
| (c) Dijkstra + greedy incumbent cost pruning | 0/8 | 0 | 8 | >70 | 0 |
| (d) bidirectional (forward product, backward schema graph, stop top_f + top_b >= best) | 0/8 | 8 | 0 | 0.16 | 0 |
| (e) Dijkstra keyed by (schema, prerequisite states) only | 0/8 | 0 | 8 | >70 | 0 |
| plain Dijkstra (prototype) | 0/8 | 0 | 8 | >70 | 0 |
| greedy cheapest allowed edge | 0/8 | 8 | 0 | 0.01 | 0 |
| schema-only shortest path | 0/8 | 8 | 0 | 0.01 | 0 |
| naive exhaustive walks (<= 80 edges) | 0/8 | 0 | 8 | >70 | 0 |
| blind cee149a planner | 0/8 | 0 | 8 | >70 | 0 |
| Opus a4 planner | 0/8 | 0 | 8 | >70 | 0 |

Every generic solver keeps 0 of the 40 lever points (bar: <= 15%). The 8.5 s prototype case is gone: no
plain program finishes any hard record inside 70 s. Reference max 0.04 s on the hard records, 0.10 s on any
record = 1/100 of the 10 s limit (bar <= 1/4). 300-seed build: `proto/core2.py seeds 300` all built, worst
1.56 s, every K14 bound and the gadget shape asserted by `_g_core` itself.
(b) is wrong because a superset of present prerequisites does not dominate (later `lacks:` requires and
the carried field differ); (d) is wrong because its backward half ignores prerequisites, so its stop rule
accepts a meeting that a cheaper product path beats.

## Gate v3.6 harden (board f0331ad, 27 Oct 2026): 10 more large-graph worlds (prototype world_37..world_46)

Generator: `proto/core3.py` = the tests' `_g_core` with its own stream `_rng(7000 + number)`, zone out-degree 5
(was 4) and a skip when a draw passes 6,000 edges. Worlds 37-46: 1,145-1,196 schemas, 5,683-5,944 edges,
10 fields (8 prerequisites), hard plans 12-14 edges; reference 0.008-0.011 s per record (4 records each).
300-seed shape run (Docker, `seeds3.log`): all built, worst 0.09 s, max 5,958 edges (<= 6,000), ALL_DONE.
Docker `python:3.12-slim`, `--cpus 2 --memory 4g`, `proto/kill3.sh`, each job `timeout 62` and RLIMIT_AS 4 GiB,
hard record of each world. Logs `proto/kill3_gen.log` (worlds 37-41), `proto/kill3_prog.log` (worlds 37-46), both ALL_DONE.
Shipped inputs fast: every program below plans all 8,000 shipped records in seconds (a5 step 43, cost runs e3e74e6).

| solver | worlds | exact | WRONG | TIMEOUT (>62 s) | max s | lever pts kept | shipped inputs fast |
|---|---|---|---|---|---|---|---|
| reference (tests `_reference_plan`) | 10 | 10 | 0 | 0 | 0.01 | 100% | yes |
| oracle planner repo_fixed | 10 | 10 | 0 | 0 | 0.01 | 100% | yes |
| run a5 agent planner (patched-repo.zip) | 10 | 0 | 0 | 10 | >62 | 0% | yes |
| blind 4f7606c planner | 10 | 0 | 0 | 10 | >62 | 0% | yes |
| blind cee149a planner | 10 | 0 | 0 | 10 | >62 | 0% | yes |
| Opus a4 planner | 10 | 0 | 0 | 10 | >62 | 0% | yes |
| (a) speed-tuned plain Dijkstra | 5 | 0 | 0 | 5 | >62 | 0% | yes |
| (b) dominance pruning | 5 | 0 | 5 | 0 | 1.73 | 0% | yes |
| (c) greedy incumbent + cost pruning | 5 | 0 | 0 | 5 | >62 | 0% | yes |
| (d) bidirectional | 5 | 0 | 5 | 0 | 0.03 | 0% | yes |
| (e) state keyed by prerequisites | 5 | 0 | 0 | 5 | >62 | 0% | yes |
| plain Dijkstra | 5 | 0 | 0 | 5 | >62 | 0% | yes |
| naive exhaustive | 5 | 0 | 0 | 5 | >62 | 0% | yes |
| greedy cheapest edge | 5 | 0 | 5 | 0 | 0.00 | 0% | yes |
| schema-only shortest path | 5 | 0 | 5 | 0 | 0.01 | 0% | yes |
| A* with schema-graph bound (reference method, not a plausible-program row) | 5 | 5 | 0 | 0 | 0.01 | 100% | yes |

Bar: every generic solver and every blind or agent program keeps 0% (loses 100% >= 15%) of the lever points;
losses WRONG or hidden-scale TIMEOUT (v3.5: limit stated K14 repository_contract.md:90-93, no shipped input slow,
each world its own child call). Reference 0.011 s max = 1/900 of the 10 s limit (<= 1/4).

## Gate v3.6 harden a6 (board a4f790c, 28 Oct 2026): gated core worlds (prototype world_47..world_76)

Generator `proto/gate.py g_gate` = the tests' `_g_core` family with its own stream `_rng(9000 + number)`, zone
out-degree 5, a fourth sampled field `gate` that no zone operation touches, 40 zone exits to the canonical schema
`has:gate` at cost 1-5 (cheap in the schema graph, so the schema-graph remainder no longer prunes the zone), and one
entry `start -> door` with `add:gate` at 5-6 million (dearer than the corridor plan). One hard record per world.
Worlds 47-76: 1,146-1,200 schemas, 5,719-5,989 edges, 10 fields (<= 8 prerequisite fields), plans 12-14 edges.
Reference `strong_plan`: the tests' label-setting search with remainder max(schema-graph remainder, per-prerequisite-field
projection remainders); consistent, so the plan is the same (cost, edge-id list) optimum: on every one of the 987
reference calls the current tests make (46 worlds + ladder) it returns the identical plan (`gate.py same`, diff 0,
expected digest b0f465e55d9b6d1a). 300-seed shape run (`gate.py seeds 1001 1300`, `seeds4.log`): all built, max 1,200
schemas / 5,995 edges, reference max 0.372 s.
Docker `python:3.12-slim`, `--cpus 2 --memory 4g`, `proto/kill4.sh`, RLIMIT_AS 4 GiB, each job `timeout 40` (the tests'
child cap for a one-record world is 10 x 1 + 20 = 30 s), log `proto/kill4.log` (171 rows, ALL_DONE 16:59 IST).
Shipped inputs fast: yes for every program (a6 passed all 291 points incl. shipped and visible runs; a5 and the blinds ran the shipped data in seconds).

| solver | worlds | exact | WRONG | TIMEOUT/CRASH | max s | lever pts kept | shipped inputs fast |
|---|---|---|---|---|---|---|---|
| a6 final repo (patched-repo.zip) | 30 (47-76) | 0 | 0 | 30 (>40 s) | - | 0% | yes |
| a6 final repo, 300 s cap | 2 (47, 48) | 0 | 0 | 2 (world_47 killed at 4 GiB after 78 s; world_48 >151 s) | - | 0% | yes |
| strong reference (new) | 30 | 30 | 0 | 0 | 0.34 | 100% | yes |
| old tests reference / oracle repo_fixed (schema bound) | 5 / 6 | 0 | 0 | 5 / 6 | - | 0% | yes |
| run a5 agent planner | 6 | 0 | 0 | 6 | - | 0% | yes |
| blind cee149a, blind 4f7606c, Opus a4 | 6 each | 0 | 0 | 6 each | - | 0% | yes |
| blinds d721, d2fb, 9179, b686 | 6 each | 0 | 0 | 6 each | - | 0% | yes |
| (a) fast Dijkstra, (c) incumbent, (d) bidirectional, plain Dijkstra, exhaustive, A* schema bound | 5 each | 0 | 0 | 5 each | - | 0% | yes |
| (b) dominance | 5 | 0 | 5 | 0 | 1.18 | 0% | yes |
| (e) prerequisite-keyed states | 5 | 0 | 5 | 0 | 37.1 | 0% | yes |
| greedy, schema-only | 5 each | 0 | 5 each | 0 | 0.00 | 0% | yes |

Bar: every program and generic solver keeps 0% (loses 100% >= 15%) of the lever points; reference 0.372 s max = 1/27 of
the stated 10 s (<= 1/4). Losses are WRONG or v3.5 hidden-scale TIMEOUT/CRASH (limit stated K14 repository_contract.md:88-93,
no shipped input slow, each world its own child call).

## Gate v3.7 redesign a6 (board 9111ecc, 29 Oct 2026): 60 gated worlds world_47..106 at a 15 s child cap

Prototype: proto/gate.py `gen` (same `_g_gate` family as a4f790c, stream 9000+n), worlds 47-98 built by proto/kill5.sh
(log proto/kill5.log, per-job wall cap 20 s) and worlds 99-106 by proto/kill6.sh (log proto/kill6.log, cap 15 s), both in
python:3.12-slim, --memory 4g --cpus 2, 2 parallel jobs, ALL_DONE in both logs. Built worlds: 1,136-1,200 schemas,
5,675-5,989 edges, plans 12-14 edges; build 0.23-0.92 s, reference 0.20-0.82 s per world (GEN_TOTAL 35 s / 52, 10 s / 8).
Any solver killed at 20 s is also killed at the 15 s cap; WRONG rows stay WRONG.

| solver | worlds | exact | WRONG | TIMEOUT/CRASH | max s | lever pts kept | shipped inputs fast |
|---|---|---|---|---|---|---|---|
| a6 final repo (patched-repo.zip, WORK/a6_repo) | 60 (47-106) | 0 | 0 | 60 (52 at 20 s, 8 at 15 s) | - | 0% | yes (291/291 old points, verifier 67 s) |
| strong reference (proto gate.py) | 60 | 60 | 0 | 0 | 0.59 | 100% | yes |
| oracle planner WORK/repo_fixed (a4f790c projection remainder) | 60 | 60 | 0 | 0 | 0.68 | 100% | yes |
| run a5 agent planner | 6 (77,81,85,89,93,97) | 0 | 0 | 6 | - | 0% | yes |
| blind cee149a (proto/blind), blind 4f7606c (proto/blind2), Opus a4 (proto/opus) | 6 each | 0 | 0 | 6 each | - | 0% | yes |
| blinds d721, d2fb, 9179, b686 (= /tmp/blind/*/app copies in proto/tb_*) | 6 each | 0 | 0 | 6 each | - | 0% | yes |
| old tests reference (`reference` name in gate.py) | 4 (78,84,90,96) | 4 | 0 | 0 | 0.36 | 100% | yes |
| (a) fast Dijkstra, (c) incumbent, (d) bidirectional, (e) prerequisite-keyed, plain Dijkstra, exhaustive, A* schema bound | 4 each | 0 | 0 | 4 each | - | 0% | yes |
| (b) dominance | 4 | 0 | 4 | 0 | 1.46 | 0% | yes |
| greedy, schema-only | 4 each | 0 | 4 each | 0 | 0.01 | 0% | yes |

(e) moved from WRONG at 33-37 s (a4f790c, 40 s cap) to TIMEOUT at the 15/20 s cap. /tmp/blind/...-92d4 has no app/;
its program is the proto/blind copy a4f790c recorded. Bar: every program and generic solver keeps 0% of the lever
points (>= 15% lost); reference 0.82 s max = 1/12 of the stated 10 s (<= 1/4).
