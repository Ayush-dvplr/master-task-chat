# HARDEN_REPORT flood-repair-portfolio, harden r2 (cb8dada, 1 Nov 2026)

## Diagnosis
Paid run a1 scored tests 108/108, judge 13.33, final 56.66. The a1 program
(WORK/h1_a1/a1_program/derive_report.py) is a memo branch and bound planner
(L374-535) that is exact but slow per large round (1.2 to 4.1 s per 160 node
round). The old fresh books carried only two large rounds each, so it fit inside
the stated 20 s limit (contract.md:15). The agent timed only the shipped book
(steps 55, 61, 70: 3.3, 2.3, 2.2 s) and never a book with more large rounds,
although contract.md:11-12 allow 200 rounds of up to 160 rows. Details: TRIP.md.

## Lever (LV-FP-1 at stated scale, time-out lever)
- Fresh books H1, H2, H3 are rebuilt by the existing generator with new seeds
  815301, 822402, 833503 and each large round list repeated 30 times: 100 rounds,
  60 large (144 to 160 proposals, records 425 to 517), every size inside
  contract.md:11-12. Registers scale with k=60 (crews 4300, permits 5400, sites 4100).
- Written in WORK/hidden_meta.json, assembled into tests/test_output.py `_BOOKS`
  (L668-728) with new sha256 pins. Limit stays 20 s; no doc changed.
- Verifier cap hardening (master correction 2): `_launch` tests/test_output.py:1163
  now starts the program in its own session and `_stop_untrusted` L1183 kills the
  group and any leftover process of user nobody. Fork probe before: 4 survivors
  (logs/fork1.log); after: 0 (logs/fork2.log).
- Old check bodies byte identical: digest with `_BOOKS`, `_launch`,
  `_stop_untrusted` and 2 imports removed = b1d31eb43bec1684 before and after.
  No registration, weight, judge, data or doc change.
- Generator asserts over 300 seeds (gen300.log): 0 errors, 19/19 fault kinds,
  bounds asserted in `_check_bounds` L601.
- Lever 2 (WRONG kind): none found. a1 `add()` skips a==b (L270-272), permit
  members dedup (L294-295), ids fixed width so string sort equals numeric,
  fuzz 150/150 MATCH.

## Arithmetic
Positive 108. Lever points on a1: 3 fresh books x 25 = 75, plus reruns_identical 3
(runs H1 twice) = 78, share 78/108 = 72%. Predicted a1 tests 30/108 = 27.78;
judge mid 13.33 unchanged; final (27.78 + 13.33)/2 = 20.56 <= 35.
Time out share of the lever: 100% (Ayush flood time-out exception, decisions.jsonl:608).

## Kill table (Docker, 4 GiB, 2 CPUs, rep30 books N1-N3 = pinned H1-H3, cap 60 s)
| program | N1 s | N2 s | N3 s | verdict | peak MB | lever pts kept |
| a1 paid run | T@60 | T@60 | T@60 | TIMEOUT | 71 | 0 |
| first write (step 11) | T@40 | T@40 | T@40 | TIMEOUT (rep20) | 472 | 0 |
| all but one (ref, plain BFS start) | 42.86 | 54.89 | 42.46 | EXACT > 20 s = TIMEOUT | 605 | 0 |
| dae9563 | T@40 | T@40 | T@40 | TIMEOUT (rep20) | 63 | 0 |
| elim_program | 7.93 | 7.55 | 6.51 | EXACT | 117 | 78 (lost 25 under verifier load) |
| vebest_program (careful enumerator) | 6.86 | 6.51 | 5.93 | EXACT | 95 | 78 |
| strong.py | per round sweep T@60 | | | TIMEOUT | | 0 |
| ref busy / unbusy | 1.12 / 1.20 | 1.11 / 1.11 | 0.95 / 0.97 | EXACT | 51 | |
The careful enumerator keeping the lever is recorded, not a blocker (R5 d).
Ref 1.20 s max = 1/16 of the limit.

## Cost table (final tests, tests-only verifier in Docker, cb8dada_verif image)
| program | shipped s | verifier s | tests of 108 |
| a1 | 2.6 | 167.18 | 30 |
| first write | >300 (killed) | 225.13 | 3 |
| all but one | 7.01 | 161.04 | 30 |
| dae9563 | 12.56 | 191.80 | 30 |
| elim | 0.86 | 161.72 | 83 |
| vebest | 1.33 | 150.16 | 108 |
| oracle (earlier tests-only) | 0.2 | 40.85 | 108 |
Verifier worst case with the slow path (master correction 1): a1 delivered,
167.18 s (earlier run 146.65 s), far under 2430 s. No negative check fired.

## Gates
- stacking_check: OUT/STACKING_CHECK.md, TS-26 groups cleared by hand, 34 tests, 11 criteria.
- precheck.sh: last line `PRECHECK CLEAN` (after TRUTH update), kit scripts 0 warns.
- xref_check: 36 entries, 0 findings.
- exe_copy lanes (_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818):
  oracle 1.0 x3 (verifier 124.27, 139.64, 151.49 s), owner 1.0 (125.21 s),
  nop 0.0 (109.39 s), stub 0.0093 = 1/108 (91.12 s), forgery 0.1481 = 16/108
  (artifacts 1 + shipped 15; CL-2 price share 14.8%, 96.05 s). Lanes ALL_DONE.
- TRUTH.md updated by script last (WORK/h2_a1/truth_update.py): sizes, timings,
  tie facts, provenance; sha lines recomputed.
- Tasks_INPUT: `cp -Rp` TRUTH.md and tests/test_output.py; `diff -rq` empty;
  tree sha BUNDLE 931f8f817d76 == Tasks_INPUT 931f8f817d76 (start cd11476e6e14).

## QC rows
WORK/QC_DEFENCE.md and WORK/EVIDENCE_MAP.md r2 sections: TS-11/Law-1 v3.5 (Ayush
quote), TS-11 cap, TS-19, IN-15, IN-16, IN-17, DS-21, DS-22, TS-23, TS-26, JD-5,
JD-8, AL-2, AL-27, CL-2, CL-3. Previous QC copy for recheck: QC/copies/6a62b99.

## Docs changed
No. instruction.md, contract.md, data, judge.toml, reward.toml, task.toml unchanged.

## Not run
Paid run on the new tests (next: master QC v3 recheck, freeze, paid run attempt 2).
elim lost H1 under verifier CPU load in the cost run; the cause was not logged.

## Lessons for the master
- A per-book limit with only two large rounds per fresh book let an exact but slow
  planner pass; filling fresh books to stated scale makes the limit bite.
- subprocess.run timeout kills only the direct child; forked workers survived
  until the verifier used its own session and a group kill.
- A careful VE enumerator still keeps the lever; time-out levers price speed, not care.
