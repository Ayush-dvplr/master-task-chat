# DESIGN: schema-migration-plan-repair, gate v3.7 redesign a6 (board 9111ecc, 29 Oct 2026)

Input: frozen bytes 308399b4016e (QC v11 PASS). Run a6: tests 100.0 (291/291), rubric 28.95 (11/38), final 64.47.
a4f790c half-build (34 gated worlds, 30 s cap) kept as WORK/halfbuild_a4f790c (tree fe32d3435385); BUNDLE reset to
308399b4016e (diff -rq vs Tasks_INPUT empty). Its code (`_g_gate`, projection remainder in `_reference_plan`,
repo_fixed planner, make_shipped/make_solve patches) is reused in Phase 2; every piece re-measured below.

## 1. Arithmetic

- a6 has no WRONG path: its planner (WORK/a6_repo/src/migrakit/core/planner.py) is an exact A* over (schema, state of
  every named field) with the schema-graph remainder and an exact M8 reconstruction, and every other module matches the
  oracle (diff vs WORK/repo_fixed: cosmetic or error-text only). So a6 loses only by hidden-scale TIMEOUT.
- Old: positive 291 (18 old core worlds w5 = 90 of it). a6-like tests with N new w5 worlds = 291 / (291 + 5N).
- Judge (section 4): a6-graded mid 7/49 = 14.3. final <= 35 needs tests <= 55.7, so N >= 47.
- Time: verifier limit 2,700 s (task.toml:22), bar 90% = 2,430 s. Old core worlds 18 x 60 s cap = 1,080 s.
  Measured a5-like run on the a4f790c 34-world tests: 2,158 s for 1,080 + 34 x 30 = 2,100 s of caps, so 58 s other.
  New per-world cost = child cap + parent build and reference (measured 0.4-1.7 s).
- Chosen: N = 60 worlds, child cap TIME_LIMIT_SEC + 5 = 15 s (stated limit 10 s per call, K14 repository_contract.md:90-93).
  Positive 291 + 300 = 591. Lever (new tier) 300/591 = 50.8% (>= 40%; held-out w5 tier >= 50%). All core w5: 390/591 = 66%.
  a6-like tests 291/591 = 49.2. Worst case (program timing out every core world): 1,080 + 60 x 15 + 60 x 1.7 + 58 = 2,140 s
  (<= 2,430). a6-like: 67 + 60 x 15 + 60 x 1.7 = 1,069 s.

## 2. Design (tests)

60 held-out worlds `world_47_core_gated_graph` .. `world_106_core_gated_graph` (w5, one check each, CL-4 one artifact:
records + summary of one child run, whole-document exact, owned rows G1/G1a), all from the existing `_g_core` family
through `_g_gate(w, number)` with its own stream `_rng(9000 + number)` (G8). Old 81 checks byte-identical; only new
registrations, the `_g_gate` function, the `_world` dispatch for GATE, one GATE timeout branch in `_world_holds`
(TIME_LIMIT_SEC + 5) and the projection remainder in `_reference_plan`. The fresh Docker audit confirmed all 987 old
calls identical (digest b0f465e55d9b6d1a), old world documents unchanged and 300 shape seeds passing.

World shape (a4f790c, unchanged): a fourth prerequisite field `gate` that no zone or entry operation names; one edge
`start -> door` adds `gate` at cost 5-6 million; `door -> zone` 1-5; 40 zone exits `has:gate` to the canonical schema at
cost 1-5. One hard record per world. Cheap paths to the zone never set `gate`, so a schema-graph remainder underestimates
by millions and A* / Dijkstra expand the whole (schema, state) space before taking the door.

Doc sentences each figure follows from (no new rule, no size or method word added):
- K14 repository_contract.md:88-93: <= 1,200 schemas, <= 6,000 edges, <= 8 prerequisite fields and <= 10 fields per
  domain, plan <= 80 edges, each `plan_migration` call within 10 seconds on 2 CPUs. Built: 1,136-1,200 schemas,
  5,675-5,989 edges, 4 prerequisite fields, <= 10 fields, plans 12-14 edges (all inside).
- M2 migration_semantics.md:10-11 (positive integer cost, million costs allowed), M3 :13-15 (`has:`), M4 :17-22
  (`add:`), M6 :31-33 (prerequisite on the state at that point), M7 :35-39 (revisits), M8 :41-44 (cost then edge ids).
- N2 null_semantics.ini:7-10 and N4 (fill rule) for the `add:gate` value.
Reference: `_reference_plan` with remainder = max(schema rest, per-prerequisite-field projection); measured 0.20-0.82 s
per world in the container (<= 1/12 of the 10 s limit, <= 1/4). Shipped data untouched; docs untouched.
a6 loss on each world: TIMEOUT at the 15 s cap (measured > 20 s on 52 worlds, > 15 s on 8; a4f790c: > 151 s, 4 GiB kill
at 78 s). Hidden-scale loss counts (LEVER_RULES 1C v3.5): (1) no shipped input slow (a6 291/291 in 67 s), (2) limit
stated (K14 sentence, no method word), (3) each world its own child call.

## 3. Measured kill table (WORK/KILL_TEST.md section 9111ecc; logs WORK/proto/kill5.log, kill6.log, both ALL_DONE)

| solver | worlds | exact | WRONG | TIMEOUT | lever kept | shipped fast |
|---|---|---|---|---|---|---|
| a6 final repo | 60 | 0 | 0 | 60 | 0% | yes |
| run a5 agent program | 6 | 0 | 0 | 6 | 0% | yes |
| blinds cee149a, 4f7606c, Opus a4, d721, d2fb, 9179, b686 | 6 each | 0 | 0 | 6 each | 0% | yes |
| fast Dijkstra, incumbent, bidirectional, prerequisite-keyed, Dijkstra, exhaustive, A* schema bound | 4 each | 0 | 0 | 4 each | 0% | yes |
| dominance | 4 | 0 | 4 | 0 | 0% | yes |
| greedy, schema-only | 4 each | 0 | 4 each | 0 | 0% | yes |
| strong reference / oracle repo_fixed | 60 / 60 | 60 / 60 | 0 | 0 | 100% (max 0.59 / 0.68 s) | yes |

Solvers from e3e74e6, f0331ad and a4f790c KILL_TEST are all rows above. Per-world seconds: build 0.23-0.92, reference
0.20-0.82, killed solvers at the cap. Verifier worst-case sum 2,140 s bounded from these figures (Phase 3 measures it).

## 4. Judge changes (judge.toml; docs unchanged)

Drop R13 (w3 `--help` run, easy, a6 earned) and R5 (w1, same setup as R2, a6 earned). Keep R1-R4, R6-R12, R14 (J4),
negatives R15-R20 (J3 honesty incl. R18-R20). Add five w3 probes (binary, one act each, evaluation_target trajectory,
importance important; JUDGE_MAP rows and five measured solve.py `check <id> ok` witnesses), all skipped by a6
(grep of the 84 a6 steps: no missing or malformed contract file, no empty feed, no altered policy or INI copy of /app/ci):
- R21 (P-h) copies a contract folder, deletes one of the seven files K2 names (repository_contract.md:18-23) from the
  copy, runs the repaired package on that copy, and checks the exit status or error the run reports.
- R22 (P-h) runs the repaired package with a feed file that holds no lines and checks the run summary it writes (K15
  :95-99; distinct from R10, a manifest batch with no lines).
- R23 (P-h) copies a contract folder, replaces the cost of one line of migration_edges.csv with non-integer text in the
  copy (M2 migration_semantics.md:10-11), runs the repaired package on it, and checks the exit status or error reported.
- R24 (P-d) copies /app/ci, changes one row of field_policy.tsv in the copy (N3), runs the shipped feed against it, and
  compares one record of that row's domain with the same record from a run on /app/ci.
- R25 (P-d) copies /app/ci, changes `[presence] explicit_null` in null_semantics.ini (:26-27) in the copy, runs the
  shipped feed against it, and compares one record holding an explicit null with the run on /app/ci.
None overlaps a test (no test reads a missing/malformed file, an empty feed or an altered copy); no figure criterion
(J1); no session confinement. Probe band 16 x 3 = 48 of 49 positive (98%, the recorded 97% deviation kept).

Grading the a6 trajectory and final reply on the new judge: earned R1, R2 (own manifest and feed probes, step 66),
R14 (J4); skipped R3, R4, R6-R12, R21-R25; no negative fired (as in the a6 grading). a6-graded mid 7/49 = 14.3.
Peer formula (probes at 25%, LEVER_RULES section 6): (12 + 1)/49 = 26.5; a6's own probe rate was 2/12 = 17%.

## 5. Predicted run score (a6-like agent)

| figure | value |
|---|---|
| tests | 291/591 = 49.2 (first write Opus a4 and all-but-one 201/591 = 34.0; a5 34.0; blinds d721/d2fb 199/591 = 33.7) |
| judge mid | 14.3 a6-graded (26.5 at peer 25%) |
| final | (49.2 + 14.3)/2 = 31.8 (37.9 at peer 25%) |
| lever share | 300/591 = 50.8% |
| a6 lever loss kind | 100% TIMEOUT (hidden-scale); generic solvers 3 of 10 losers WRONG |

## 6. Bar check (C2 v3.7 and note 4)

(a) final 31.76 <= 35 (judge low/mid/high 8.16/14.29/26.53 -> final 28.70/31.76/37.88). (b) new tier 300/591 =
50.76%: yes. (c) measured blinds cee149a 7.11, 4f7606c/d721/d2fb 33.67 (9179/b686 skipped: identical to 4 measured
blinds); first write 33.67, all-but-one 33.84, a5 34.01, a6 49.24 <= 60. (d) verifier worst MEASURED 2,348 s
(generic exhaustive, direct runner); Harbor forgery 2,118.9 s; both <= 2,430 s. (e) every generic solver and blind
loses all 300 lever points (greedy, schema-only, dominance WRONG; the rest TIMEOUT); reference 0.82 s <= 2.5 s.
Harbor gates: oracle 1.0 x3, owner-only 1.0, nop 0.0, stub 0.0017, forgery 0.0102. Old 81 checks and 987 calls same.
Master go 14:15 raised the bundle-only CRASH+TIMEOUT cap to 70% of positive test weight. All programs are inside it
(max 65.99%) except the generic exhaustive solver: 71.57%, because it also times out on 33 points of OLD frozen checks
(SCALE worlds 04/08/12/15/18/28 and ladder_large_state, unchanged since QC v11) on top of old core 90 + new 300.

Docs changed: no. Judge changed: yes (R5, R13 out; R21-R25 in; live IDs R1-R23). Slug unchanged.

PAUSED: exhaustive crash+timeout share 71.57% > 70% cap. Candidate retained in BUNDLE (ebf080b7b781);
Tasks_INPUT not synced (308399b4016e). Master options: exempt the generic exhaustive solver, or cap 72%.

## Lessons for the master
Cap checks must count inherited old-check timeouts per program | no change: master owns the cap ruling.
