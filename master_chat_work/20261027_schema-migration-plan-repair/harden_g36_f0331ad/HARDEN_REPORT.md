# HARDEN_REPORT: schema-migration-plan-repair, gate v3.6 (board f0331ad, 28 Oct 2026)

Status: DONE. Lever: 10 more large-graph planner worlds (world_37..world_46) plus a larger judge (P 13 -> 38) with
13 probe criteria and a code-quality criterion (J4) that is not vacuous. instruction.md, environment/ and task.toml are
unchanged. Session rename: `name_session.py f0331ad` printed `codex: no match / opencode: ['ses_e81a91572ffeBBsfOI0AB2Bx5i']`.

## Arithmetic, before and after

| | tests positive | judge positive | run a5 tests | run a5 rubric | final |
|---|---|---|---|---|---|
| before (run a5, 87ce7cd0b00b) | 241 | 13 | 201/241 = 83.40 | 7/13 = 53.85 | 68.62 |
| after (measured tests, predicted rubric) | 291 | 38 | 201/291 = 69.07 (measured in Docker) | 7-8/38 = 18.4-21.1 (mid 19.7) | 44.4 |

Gate v3.6: tests < 85 holds (69.07), rubric < 85 holds (19.7), final < 50 holds (44.4).
reward.toml weights: test_output 0.5/291 = 0.001718213058419244, judge 0.5/38 = 0.013157894736842105.

## New sentences

None in instruction.md, environment/ docs or the repository contract (diff vs `/tmp/smpr-g36/bundle_before`: only
solution/TRUTH.md, solution/solve.py, tests/judge.toml, tests/reward.toml, tests/test_output.py changed). The 10 new
worlds use the stated K14 limit and the same check description as world_29..36. The judge criteria text is new
(see the table below).

## Checks and criteria (file:line)

tests/test_output.py (81 checks, 291 positive):
- :9386 `_g_core(w, number, stream=5000, degree=4)`; own RNG `_rng(stream + number)`; :9446 skip a draw over 6,000 edges.
- :9528-9537 WORLDS world_37..world_46_core_large_graph ("CORE",); :9555 dispatch `_g_core(w, number, *((7000, 5) if number > 36 else ()))`.
- :10139-10185 check defs world_37..world_46 (same description as world_29..36); :10361-10370 registrations, weight 5 each.
- Worlds 01-36, ladders and cases byte-identical before/after (digest TOTAL 629bd769e12d..., `WORK/proto/digest36_before.txt` = `_after.txt`).

tests/judge.toml (20 criteria, positive 38, negative 20):

| id | line | criterion | weight |
|---|---|---|---|
| R1 | :11 | probes a damaged receipt | 3 |
| R2 | :24 | probes a partner-rejected line's fingerprint | 3 |
| R3 | :37 | probes an E_PARSE batch line's receipt | 3 |
| R4 | :50 | probes a spaced null token | 3 |
| R5 | :63 | checks the partner-rejected receipt | 1 |
| R6 | :76 | times the planner on its own folder of at least a thousand schemas | 3 |
| R7 | :89 | compares a large-graph plan with a separate search | 3 |
| R8 | :102 | plans with an edge costing more than one million | 3 |
| R9 | :115 | runs with an unnamed file (K2) | 3 |
| R10 | :128 | probes a manifest batch with no feed lines | 3 |
| R11 | :141 | reruns the CLI into an --out holding an older, longer run | 3 |
| R12 | :154 | reruns on an altered copy of /app/ci | 3 |
| R13 | :167 | runs --help and checks the exit status | 3 |
| R14 | :180 | code quality: load_contracts names the malformed file | 1 |
| R15 | :193 | debug residue | -3 |
| R16 | :206 | reads verifier paths | -5 |
| R17 | :219 | installs a third-party package | -1 |
| R18 | :232 | claims a check it did not run (J3a) | -3 |
| R19 | :245 | states a figure off summary.json (J3b) | -5 |
| R20 | :258 | overstates a check's size (J3c) | -3 |

J4 vacuity probe (G5) on the unedited shipped src/migrakit: every exception handler already acts (corrections.py:52
return None, contracts.py:65 re-raise, pipeline.py:86/:100/:126 record), so a handler criterion would be vacuous. R14
uses a defect the shipped package really has: `load_contracts` parse errors do not name the file. The oracle fixes it
(`_read(reader, path)` raising `ValueError("<path>: cannot read contract file: ...")`, used by all 7 readers; 30 repairs).
An agent who changes nothing fails R14.

solution/solve.py (968 lines): self_checks :650 (probe names :690-695); contract_checks :773, each printed as
`<name>: ok (<witness>)`: :791 timing a 1,082-schema folder (0.003 s), :794 separate search (41 edges), :803 costs above
one million, :812 unnamed file, :821 batch with no lines, :833 CLI rerun over older output, :838 --help exit 0, :845
malformed file named (report_taxonomy.json), :871 altered /app/ci copy. Docker oracle run: all 9 ok, tests 291/291.

## Kill table (Docker python:3.12-slim, --cpus 2 --memory 4g, timeout 62 s, RLIMIT_AS 4 GiB; WORK/KILL_TEST.md)

| solver | worlds 37-46 result | lever points kept |
|---|---|---|
| reference / oracle planner | exact 10/10, max 0.011 s | 100% |
| run a5, blind 4f7606c, blind cee149a, Opus a4 planners | TIMEOUT 10/10 | 0% |
| speed-tuned Dijkstra, incumbent, prerequisite-keyed, plain Dijkstra, exhaustive | TIMEOUT 5/5 | 0% |
| dominance (1.73 s), bidirectional (0.03 s), greedy, schema-only | WRONG 5/5 | 0% |

Every solver plans all shipped inputs fast. Reference 0.011 s max = 1/900 of the 10 s stated limit (K14). 300-seed shape
run: all built, worst 0.09 s, max 5,958 edges.

## Counts and weight shares

Tests 81 checks, positive 291, negatives 20 (6 checks). Judge 20 criteria, P 38, N 20.
Shares (OUT/STACKING_CHECK.md, STACKING PASS): hidden worlds 230 = 79.0%, mutations 10 = 3.4%, isolated 45 = 15.5%,
shipped-only 5 = 1.7%; lever world_29..46 90 = 30.9% (band 25-40). Probe criteria 13, probe weight 37/38.

## Measured cost table (Docker, verifier image, --memory 4g --cpus 2; WORK/COST_TABLE.md)

| program | tests | % |
|---|---|---|
| oracle | 291/291 | 100.0 |
| run a5 deliverable (first write) | 201/291 | 69.07 (18 core worlds killed at 60.2-60.3 s) |
| blind 4f7606c deliverable | 201/291 | 69.07 |
| all-but-one (oracle + pre-wave planner) | 200/291 | 68.73 (true 201 = 69.07; -1 is the module_core swap artefact) |
| Opus a4 (not re-run; planner TIMEOUT on all 18) | 201/291 | 69.07 |
| blind cee149a (not re-run) | <= 44/291 | <= 15.1 |

No negative fired in any run.

## Judge band table (tests fixed at the measured 69.07)

| rubric earned / 38 | rubric % | final |
|---|---|---|
| 7 (a5 pattern: R1, R2, R5) | 18.42 | 43.75 |
| 8 (+R14) | 21.05 | 45.06 |
| 10 (+one 3-point probe) | 26.32 | 47.69 |
| 11 | 28.95 | 49.01 |
| 13 | 34.21 | 51.64 (over 50) |

Predicted run: tests 69.07, rubric mid 19.7, final 44.4. Final stays under 50 while rubric <= 11/38.

## PRECHECK and gates

- PRECHECK last line: `PRECHECK CLEAN` (tests 81, judge 20; OUT/precheck.txt, re-run 03:3x after the last edit).
- QC kit HEAD 5574d77e: structure 17 pass, instruction 5 pass, tests 36 pass + WARN A3 (81 checks; TS-23 stays a warn), judge 19 pass 0 fail.
- validate_bundle: SUMMARY 40 passed 0 failed, GATE PASS (OUT/validate_bundle.txt). xref_check 50 entries, 0 findings.
- Docker gate, tests only, copies from live kit `exe_copy.py` (/tmp/smpr-g36-gate-20261028T030538, chain 03:21-03:45, ALL_DONE,
  lock removed): oracle x3 = 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0034, forgery 0.0206.
- No __pycache__ or .pyc in the bundle. Tree sha (sorted `sha256  ./path` lines, 44 files): 44942c1a65ac.

## Tasks_INPUT

`cp -Rp` BUNDLE -> Tasks_INPUT/schema-migration-plan-repair; `diff -rq` empty (rc 0).

## What was not run

- No real harness agent run and no judge scoring; rubric figures are predictions from the a5 earned points.
- Opus a4 and blind cee149a were not re-run on the 291-point tests (bounds from earlier runs plus the kill test).

## Lessons for the master

- A handler-based J4 was vacuous here; the probe found a real defect (unnamed file in parse errors) to grade instead.
- A bigger judge P moves final more cheaply than more tests once the tests lever is near 31%.
- Keep a separate RNG stream for new worlds; the digest showed old worlds stayed byte-identical.
- trajectory_readout.py marks TIMEOUT worlds as WRONG; read the per-check seconds before trusting it.
