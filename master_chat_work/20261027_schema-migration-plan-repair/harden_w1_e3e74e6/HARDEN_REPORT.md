# HARDEN_REPORT: schema-migration-plan-repair, wave 1 (board e3e74e6)

Verdict: DONE. Lever P-3 (exact optimum on larger hidden graphs), swapped in for P-2 on the master's "go"; P-4 dropped; judge unchanged.
Session rename: `name_session.py e3e74e6` printed `codex: no match / opencode: ['ses_e841e838bffes1e1YxsYMiaftF']` (one opencode session listed, taken as renamed).
QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (as expected).

## Why P-2 was dropped (Design 1, measured)
Long generated replays (976 lines, 518-560 corrections, chained REISSUE/replay/merge/corrections per identity), Docker python:3.12: the cee149a blind program and the Opus a4 program were exact on all 4 corpora (blind differs only by the missing `receipt_mismatches` key, which predates the r1 receipt lever). Only deliberately wrong variants lost (name-keyed 484-518 rows, end-resolve 61-67, file order 250-292, greedy 188-265). Both real programs mirror the reference pipeline; the stated replay rules leave nothing to get wrong. Details `WORK/KILL_TEST.md`.

## The lever (Design 2, P-3)
No agent-visible text changed. The objective and limits are already stated: M8 cheapest plan then smallest edge-id list (`environment/ci/migration_semantics.md`), edge cost "positive integer" (migration_semantics.md:11, no upper bound, so costs up to 40,000,000 are in the stated form), K14 limits and the 10 s per call (`environment/ci/repository_contract.md:88`).

New checks (`tests/test_output.py`):
- `world_29_core_large_graph` .. `world_36_core_large_graph`, defs :10086-:10122, registered weight 5 each at :10290-:10297; lever tag CORE in WORLDS :9518-:9525; built by `_g_core` :9386 (own RNG `_rng(5000 + n)`), `_world` branch :9541 (core worlds hold only the large domain: no filler, no late gadgets).
- Gadget: one domain, 1,145-1,195 schemas, 4,575-4,778 edges, 10 fields (8 prerequisites); a priced corridor (10-12 rows x 3 lanes, costs 2,000-9,000) with a cheap plant edge whose drop of the carried field makes the corridor's last `has:` fail; a cheap region of ~1,100 schemas (costs 1-5, renames/adds/drops over all 10 fields) entered from the start whose exits cost 9.0-9.9 million; an escape edge at 40 million. 1 hard record + 3 easy records per world, whole records file and run summary compared.
- `_g_core` asserts every K14 bound (<= 1,200 schemas, <= 6,000 edges, <= 8 prerequisite fields, <= 10 fields, plan <= 80 edges, positive integer costs) and the gadget shape; 300 seeds build, worst 1.56 s.
- Reference `_reference_plan` :8309 now a label-setting search ordered by spent cost plus the schema-graph remainder, then edge-id list. Old vs new: 180 core-like + 3,000 tie-heavy small cases, 0 differences. Digest of the 28 old worlds' inputs and expectations, ladders, revisit and tie cases: identical before/after (`TOTAL c70a4595...`, `WORK/proto/digest_before.txt`).
- Verifier child guard: `MEMORY_LIMIT_BYTES = 4096 << 20` and `_CAPPED` :60-:61 (RLIMIT_AS on Linux, equal to task.toml memory_mb; task.toml sets no verifier memory limit). Core-world child budget `TIME_LIMIT_SEC * len(lines) + 20` = 60 s :9587.
- Oracle: `solution/solve.py` plan_migration :74 with `_cost_to_target` :125 (rendered by `make_solve.py`, 22 repairs round-trip).

## Kill table (final generator, Docker, hard record of each world, timeout 70 s, RLIMIT_AS 4 GiB)
| solver | exact | wrong | killed 70 s | lever kept |
|---|---|---|---|---|
| reference / new oracle | 8/8 (max 0.04 s / 0.03 s) | 0 | 0 | 40/40 |
| (a) speed-tuned plain Dijkstra | 0 | 0 | 8 | 0 |
| (b) dominance pruning | 0 | 8 (<= 4.8 s) | 0 | 0 |
| (c) greedy incumbent + cost pruning | 0 | 0 | 8 | 0 |
| (d) bidirectional | 0 | 8 (<= 0.16 s) | 0 | 0 |
| (e) state keyed by prerequisites only | 0 | 0 | 8 | 0 |
| plain Dijkstra, exhaustive | 0 | 0 | 8 each | 0 |
| greedy, schema-only | 0 | 8 each | 0 | 0 |
| blind cee149a planner, Opus a4 planner | 0 | 0 | 8 each | 0 |
Reference max 0.10 s over every record = 1/100 of the 10 s limit.

## Counts and shares
71 checks: 65 positive worth 241, 6 negative worth 14 (WARN A3 >35, TS-23 recorded). Judge unchanged: 9 criteria, positive 13. Whole-document hidden worlds 36 x 5 = 180 (74.7%), with mutations 190 (78.8%); lever 40 (16.6%); isolated 41 (17.0%); shipped-only 5 (2.1%). reward.toml test_output 0.5/241, judge 0.5/13.

## Measured cost table (Docker, verifier image, full tests)
| program | tests |
|---|---|
| oracle | 241/241 = 100% |
| first write (Opus a4 deliverable) | 201/241 = 83.4% (8 core worlds killed at 60.4-60.9 s, all other 63 checks pass, run continues) |
| all-but-one (oracle + pre-wave plain planner) | 200/241 = 83.0% (201 without the module-claims swap artefact) |
| prior blind cee149a | 44/241 = 18.3% |
| memory runaway planner (6 GiB) | 200/241: 8 core worlds fail in 0.27-0.43 s (allocation refused), every other check scores |
Memory proof (master item 3): one runaway check costs only its own world.

## Gates
- stacking_check.py: `OUT/STACKING_CHECK.md`, `STACKING PASS` (TS-26 / AL-28 groups resolved by hand as in r1).
- precheck.sh last line: `PRECHECK: 1 finding(s)`. The one finding is `FIND J4 judge.toml has 0 code-quality criteria, want exactly 1 (JD-18)`: it is in the judge as it was before this round, and master note 5 keeps the judge, so it is left for the master. 0 IN17/G5 warns; structure, instruction, tests, judge QC exit 0 warns 0; WARN A3 71 checks.
- validate_bundle.py: `SUMMARY: 40 passed, 0 failed, 0 warnings`, `GATE: PASS` (`OUT/validate_bundle.txt`).
- xref_check.py: 50 entries, 0 findings.
- Docker, tests only, copies from live kit `exe_copy.py` (`/tmp/smpr-w1-20261027T141352`): oracle x3 = 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0041, forgery 0.0249 (chain 14:33-14:51 IST, `ALL_DONE`; lock removed).
- No `__pycache__` or .pyc in the bundle. Tree sha (sha256 over sorted `sha256  ./path` lines): 87ce7cd0b00b.

## Tasks_INPUT
Copied with `cp -Rp` (4 changed files: tests/test_output.py, tests/reward.toml, solution/solve.py, solution/TRUTH.md). `diff -rq` BUNDLE vs Tasks_INPUT copy: empty (rc 0).

## Not run
- No P13 blind read (master issues it). No QC run and no probe (by design).
- Planner-only kill solvers were not run through the full test file; their tests% is the upper bound (201 + 0)/241.

## Lessons for the master
- Stated-rule replay levers die when strong programs mirror the reference structure; measure the blind program first before building corpora | no change: section 1C already says so.
- A lever that needs a time budget needs a child memory cap too, or one runaway check can stop the verifier | template_change: _COMMON_RULES_v4.md (time limits rule) add "cap child memory".
- precheck J4 fires on judges built before JD-18; frozen-judge rounds will always show 1 finding | no change: master decides per task.
