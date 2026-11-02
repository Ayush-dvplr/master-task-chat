# HARDEN_REPORT, cold-chain-backbone-quote, round _a4 (board b223662): BUILD DONE

Phase A GENUINE (run on frozen tree 8ca9c267f59b; staging diff = .kiro-staged-from + allowed_hosts only).
Primary cause 4 (P-1 bites only by scale: the a4 Dreyfus-Wagner package is exact on every contract-legal input and
dies by OOM / the 50 s cap on wide books), contributing cause 3 (Law-1 fix 25c745d put fresh books at shipped scale).
The 6 a4 wide losses were CRASH (OOM, rc -9 empty stderr, memory.peak 4294967296) and TIMEOUT, not WRONG; the readout
tool's WRONG label is incorrect. Details: OUT/DIAGNOSIS.md.

First pass (04:46 go, 30% cap) stopped PAUSED. Cap-60 go (30 Oct 12:00, Ayush: allow the 57.5% exception for this
bundle only) built layout A tests-only: no change to instruction.md, api_contract.md, environment data, or judge.toml.

## What changed (BUNDLE)
- tests/test_output.py (regenerated from WORK/test_template.py by embed_tests.py): HELD_WIDE_BOOKS = wide_4..wide_10,
  seeds BOOK_SEED+8..+14 from the existing far-reaching builder (wide_1..3 seeds unchanged); 21 new checks
  wide_K_core w5, wide_K_report w5, wide_K_summary w3, each book its own CLI call under the stated limit
  (api_contract.md:91-92, 4 s per project + 10 s; container memory 4096 MB, task.toml).
- tests/reward.toml: test_output weight 0.0045871559633027525 -> 0.0025 (0.5/200); judge 0.015625 unchanged.
- solution/TRUTH.md: QC v4 G05-M1 fixed (lines 24-25: non-depot links reach 3-16 positions, depot links up to 51);
  timing table 17 books; wide_1..wide_10 description; checks table total 200; measured line /200; hashes by script last.

## Before / after lever table (tests channel)
| lever / family | before (frozen, P=109) | after (P=200) | a4 program before -> after | loss kind |
|---|---|---|---|---|
| P-1 far-reaching books | 6 checks, 24 pts (22.0%) | 27 checks, 115 pts (57.5%) | lost 24 -> lost 115 | TIMEOUT 97 + CRASH(OOM) 18 |
| LV-CC-1 exact network (fresh/rescaled/relocated/ties) | unchanged | unchanged | earned | kmb/greedy WRONG |
| LV-CC-3 activation once | unchanged | unchanged | earned | perlink WRONG |
| shipped docs, archive, fixes, repair report, rerun | 85 non-lever | 85 non-lever | earned | - |

Counts: tests 54 (52 positive, 2 negatives -5/-3), judge criteria 13 (positive 32, batched, unchanged).
Weight shares (stacking_check): whole_doc 59.0%, hidden_rows 30.0%, isolated 3.0%, shipped_only 8.0%, G3 89.0%;
P-1 lever 57.5%; held-out w5 tier 120/200 = 60.0%; weight-1 checks none core.

## Measured (Docker, --memory 4g --cpus 2, scored by WORK/run_local_tests.py on the new tests)
| program | tests /200 | % | lever lost | non-lever lost | kind |
|---|---|---|---|---|---|
| oracle | 200 | 100.0 | 0 | 0 | - (negatives silent) |
| a4 final package (OUT/agent_program/repo_from_zip) | 85 | 42.5 | 115 | 0 | TIMEOUT 97, CRASH 18 |
| a4 first write (steps 19-24) | 85 | 42.5 | 115 | 0 | TIMEOUT 97, CRASH 18 |
| Dreyfus-Wagner over all cold rooms | 85 | 42.5 | 115 | 0 | TIMEOUT 97, CRASH 18 |
| last-use sweep, corridor order | 82 | 41.0 | 115 | 3 | CRASH 115; tie WRONG 3 |
| terminal-metric tree (kmb) | 28 | 14.0 | 112 | 60 | WRONG |
| greedy nearest cold room | 28 | 14.0 | 112 | 60 | WRONG |
| activation per booked link | 19 | 9.5 | 115 | 66 | WRONG |
| hang package (verifier worst case) | 22 | 11.0 | - | - | every run at cap, 1107 s |

- CRASH+TIMEOUT share of the a4 program: 115/200 = 57.5% (cap 60%), only on the 27 P-1 checks.
- Trap survival of existing levers: kmb/greedy/perlink still lose every point they lost on 109 (100% kept).
- Reference: oracle CLI 0.13-0.17 s per new wide book (bar 12.5 s = 1/4 of 50 s); test-side expected 5.07-8.26 s.
- Shipped book fast and quiet for every program above.
- Verifier worst case: 1107 s (hang) + 400 s (a4 harness tests+judge) = 1507 s <= 2430 s (62%).
- Predicted final: judge unchanged, a4 marking 14/32 = 43.75 (also 43.75 at 25% probes) -> (42.5 + 43.75)/2 = 43.1.
  The 34.9 of layout A assumed the probe-band judge rebuild (44 positive, mid 27.3), which the cap-60 go excluded.
  Not a stop condition of the go; it does miss DESIGN READY (a) <= 35 until the judge half is rebuilt.

## Cost table, gates
- STACKING_CHECK: STACKING PASS (OUT/STACKING_CHECK.md; TS-26 and AL-28 hand corrections).
- PRECHECK last line: `PRECHECK CLEAN` (OUT/precheck.txt).
- QC scripts: structure 17/0/0, instruction 5/0/0, tests 35 pass 1 WARN ([A3] 54 checks > 35, tasker approval) 0 FAIL,
  judge 19/0/0. Kit HEAD 5574d77eb9f2, `git diff 5574d77e HEAD -- Input_Bundle_QC/` empty (QL list empty).
- Validator (--archetype repo-patch): 39 pass, 1 FAIL [1.12] artifacts list includes /app/repo/src/task/core.py;
  pre-existing on the frozen tree 8ca9c267f59b (QC v4 passed it), left unchanged by the go.
- xref_check: 15 entries, 0 findings.
- Docker gates (exe_copy.py copies, harbor run, tests only): oracle x3 = 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0, forgery 0.1
  (forgery earns only the shipped-only checks + test_fixes + repair_report = 20/200). Log WORK/runs/gates_cap60.log, ALL_DONE.

## Trees
- BUNDLE before: 8ca9c267f59b (backup WORK/pre_cap60_8ca9c267f59b/). After: c10ae543512d. Tasks_INPUT after sync: c10ae543512d (rsync -a --delete; diff -rq SAME).

## Not run
- Judge probe-band rebuild (excluded by the cap-60 go). Blind reads (master's P13). Full QC v5 / P11 v3 recheck vs
  QC/copies/78b8d5b. Harness run. Mutation tests (count stays 0 as at QC v4).

## Lessons for the master
- Hidden-scale share above 30% was the only way to put an exact-but-slow a4 program under tests 60 without a new rule.
- With the judge frozen, final cannot reach 35: the tests half alone is not enough (43.1); pair cap-60 with the probe band.
- trajectory_readout.py labels rc -9 kills as WRONG; read test-stdout and reproduce in Docker before calling it WRONG.
- stacking_check.py groups per-book checks by helper name; TS-26 needs a by-hand line every round.
