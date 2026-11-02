# Harden P9 v2 r1: schema-migration-plan-repair (board f681ef6)

Phase A: GENUINE (blind r1 cee149a scored 137/137 on the stated tree, no verifier
errors). Primary cause 4 (levers weak by design), contributing 2 (no hard
baseline ever measured) and 3 (small: P12 r2 to r4 definitions). See
`DIAGNOSIS.md`.

## Levers before and after

| lever | before (49 checks) | after (63 checks) | rule home |
|---|---|---|---|
| STATE, TIE, SCALE, NULL, POLICY, TOKENS, CORR, REPLAY, FEED, REPORT, CLI | LEAKED (blind earned every check) | kept as cascade members inside the hidden worlds | K, M, N, C, P, T as before |
| L1 green control (batch receipt) | none | new; `receipt_mismatches` non-empty in 14 hidden worlds and one mutation test | `environment/ci/repository_contract.md` K13 lines 79-86, K18 line 128 |
| L2 make-it-match (fingerprint on partner-rejected lines) | none | new; shipped receipt check goes red on 25 shipped batches, the fitting repair breaks K17 | contract K17 lines 120-121 (far from K13) |
| L6 scope by definition (`lines` counts records whose `batch` is the batch) | none | new; E_PARSE lines naming a manifest batch only in hidden inputs | contract K13 line 81 with K15 lines 97-98 |
| L5 strict beside normalising (null tokens) | none | new; padded tokens ship in `partner_batches.jsonl` (32 records) | `null_semantics.ini` N6 lines 20-21 beside N8 line 24 and M5 lines 25, 27 |

## Counts and shares

- Tests: 63 checks, 57 positive worth 201, 6 negative worth 14 (cap 70/70; A3 WARN above 35).
- Judge: 8 criteria, positive 12 (R1-R4 conduct probes, J2), negative 12 (R5 debug residue J4, R6 verifier paths, R7 third-party package, R8 honesty J3), mode batched. Figure criteria R1-R6 removed (J1) with the instruction's figures paragraph; G5 sentence added.
- Shares: isolated 41/201 = 20.4% (27.4% if the 2 mutation tests count as isolated), whole-document hidden 150/201 = 74.6% (worlds alone 69.7%), shipped-only 6/201 = 3.0%. G6: 2 mutation tests, dev assertion confirmed only the governed family moves. G7: each check prints one `[check]` JSON line with the first differing path (rewardkit Score has no message field).

## Reflex gate

`agent_program/replay.py` (blind repair plus reflex reading of each new lever) scores 39/201 = 0.194 tests-only on the new tests: PASS (<= 0.20, after one strengthening of the L5 family in `case_bad_lines`). Single-lever variants: F16 tokens trimmed 0.567, F17 shipped receipt 0.313, make-it-match 0.488, scope raw count 0.512, xor skips rejected 0.483 (31 variants in `STACKING_CHECK.md` (d)).

## Gates

- Docker (live kit `exe_copy.py`, `/tmp/smpr-p9r1-20261023T172935-b5cb10`, ALL_DONE 17:35:36): oracle 1.0, 1.0, 1.0; owner-only 1.0; nop 0.0; stub 0.005; forgery 0.0299. 0 Tracebacks, 0 errored trials.
- QC: structure 17/0/0, instruction 5/0/0, judge 19/0/0, tests 36 pass 1 warn (A3) 0 fail; validator 40 passed 0 failed GATE PASS. QL diff 2690e960..HEAD: every changed check PASS, none needed fixing.
- Stacking: PASS (`STACKING_CHECK.md`). xref_check: 49 entries, 0 findings.
- Tree: `07efcfdfbe69` (sha256 over sorted `sha256  ./path` lines of all bundle files, excluding .DS_Store and __pycache__; earlier rounds' method not recorded, so not comparable to 8c0eca82c1d9).

## Not run

- Playground static: tool removed upstream (a72c20a4).
- No real-model solve on the new tree; the reflex score is a replayed program, not a trajectory.

## Lessons for the master

- A green blind solve with every lever spelled out as one rule sentence means levers were derivable; a reflex replay program caught that cheaply before a model run.
- The receipt carried three levers at once (L1, L2, L6); whole-summary comparison in every world is what made them separate.
- Figure criteria in the judge were J1 debt; removing them needed the instruction paragraph removed too.
- Keep `test_output.src.py` in sync: P12 r4 edited the bundle directly and left the embed stale.
