# HARDEN_REPORT d11904c: tariff-engine-audit-repair, wave 1, lever P-1

Bundle `master_chat_work/bundles/tariff-engine-audit-repair/`, WORK `master_chat_work/bundles/_work/tariff-engine-audit-repair/`, QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Session rename: `name_session.py d11904c` printed "codex: no match / opencode: ['ses_e841ecdc1ffetLZZHhvl5h21Vi']"; the list did not show d11904c by name.

## Lever

P-1 computational core: the r3 statements optimum (`redeemed` = vouchers adding to the largest sum not above `balance`, api_contract.md:219-224, 10 s limit :25-28) is rebuilt at ledger scale. Data only: no contract, instruction, README or visible-test sentence was added or changed (api_contract.md and instruction.md last written 03:53/03:59, before this round). Design: OUT/DESIGN.md (design D3, scale-split vouchers).

- 7 new hidden statement corpora, one per r3 `_STATEMENT_LEVER` family, own RNG `Random(seed*59+31+1000003*attempt)`. Each: 3 cloned accounts whose read quantities are scaled so `balance` lands at 3e10-1e11 cents, 55-66 vouchers (46-55 multiples of a large unit with 3 repeated multiples, 9-11 small ones totalling below the unit, two equal); 3 small tie accounts; 1 overpaid account (0.00, []).
- Reference `_redeem_split` (tests/test_output.py:7413; oracle solution/solve.py:439): picks the smallest set of low amounts whose total stays below the gcd of the rest, a bitset over that gcd for the rest and every combination of the low set for what is left; exact for every input (k = n is plain exhaustive search; shipped data reduces to the old bitset). Equal to the r3 `_redeem` on shipped + 7 r3 corpora and to naive search on 3000 random instances (0 differences).
- Shipped data, go item 7: one account A1643 added in the same shape at small scale (balance 311.48, 12 new rows in environment/ci/vouchers.csv, 198 -> 210 rows). Only changed shipped expected value: one ADDED statement `{"account": "A1643", "balance": "311.48", "redeemed": ["V116","V16","V191","V2","V223","V353"], "due": "0.78"}`; the 60 old statements are unchanged. The go message itself said "I'd skip it"; item 7 was numbered, so it was built. It shows the two-group shape in shipped data, which a reader may notice; the blind read should judge whether it helps.

## New checks (tests/test_output.py)

| check | weight | defs | registration |
|---|---|---|---|
| `<c>_ledger_statements_feasible` x7 | 3 | :8409.. (every 5th line pattern to :8509) | :8614-8634 |
| `<c>_ledger_statement_due_exact` x7 | 5 | :8414.. | :8614-8634 |
| `<c>_ledger_statement_redeemed_exact` x7 | 5 | :8419.. | :8614-8634 |

c = fresh, rescaled, relocated, rotated, api, recoded, renamed. Helpers `_ledger_statements` :7454, bounds :7466, generator `_ledger_once` :7469, asserts `_assert_ledger` :7587, `_ledger_texts` :7612, `_ledger_run` :7629 (10 s), `_check_ledger_feasible` :7651, `_check_ledger_field` :7671. Feasibility (account order, balance exact, ids owned and distinct, spent <= balance, due consistent) is checked apart from optimality; due and redeemed are whole-document exact per corpus. The r3 code (91 checks, `_redeem`, 22 statement checks) is byte-unchanged: `diff` of the source against the backup shows additions only.

Counts: 112 checks = 110 positive (488 points) + 2 negative (-5, -3); judge 14 criteria unchanged. Lever 91/488 = 18.6%. G3 by code: hidden reruns 452 = 92.6%, shipped 19 = 3.9%, deliverable 17 = 3.5%.

## Kill test and measured cost (Docker python:3.12-slim, 2 cpus, 4 GB, real checks, built bundle)

| program | tests | lever points kept of 91 |
|---|---|---|
| oracle | 1.0000 | 91 |
| blind r3 program (36f4266) | 0.8135 | 0 |
| blind r3 program with reference redeem (float check) | 1.0000 | 91 |
| oracle with blind r3 `_redeem` | 0.8135 | 0 |
| oracle with cents bitset (gcd reduced, rebuild) | 0.8135 | 0 |
| oracle with bitset optimum sum only | 0.6598 | 0 |
| oracle with dict table / Pareto / sorted halves / deduped halves x2 / branch and bound / naive | 0.6270 | 0 |
| oracle with largest-first greedy | 0.7029 | 21 |
| Q1 / Q2 / Q3 / Q4 / Q5 wrong alone | 0.8197 / 0.8299 / 0.6885 / 0.7500 / 0.8934 | 65 / 65 / 52 / 52 / 78 |
| U1 / D1 / D2 wrong alone | 0.9057 / 0.8955 / 0.8955 | 78 / - / - |
| all-but-one (best single, U1) | 0.9057 | 78 |
| first write following docs plainly | 0.3422 | 0 |
| first write + bitset / + greedy | 0.3422 / 0.3217 | 0 / 0 |

Every generic solver loses at least 76.9% of the lever points (rule 15%). No negative fired. Oracle: slowest ledger check 1.11 s (corpus build + CLI), all checks 24.09 s, wall 30.4 s; `ref_seconds_max` 1.11 s against the 10 s limit. Prototype kill table: OUT/DESIGN.md; full tables WORK/KILL_TEST.md, WORK/COST_TABLE.md. G12: 300 seeds, all plants asserted, big balances 4.01e10-7.99e10 cents, at most 5 of 40 attempts.

## Gates

- STACKING_CHECK: OUT/STACKING_CHECK.md, `STACKING PASS` (tool hints TS-26 and AL-28 corrected by hand as in r3; G3 by code hidden 92.6%).
- xref_check: 71 entries, 0 findings.
- Validator (validate_bundle.py): 40 passed, 0 failed, 0 warnings.
- 4 QC scripts (kit 5574d77e): structure, instruction, tests, judge exit 0, warns 0 (A3 112 checks over cap 35 is the same warn kind as r3).
- PRECHECK last line: `PRECHECK CLEAN` (0 IN17/G5 warns).
- Docker (copies by live kit `exe_copy.py`, harbor 0.24, tests channel, one nohup chain, ALL_DONE 14:21:59; 35 min of slot waits for foreign containers):

| run | trial | reward |
|---|---|---|
| oracle-1 | plain__6EdDt3N | 1.0 |
| oracle-2 | plain__KdtkKJP | 1.0 |
| oracle-3 | plain__Zd3w4ch | 1.0 |
| owner-only | owner__2NM3V7S | 1.0 |
| nop | plain__36YcPHn | 0.0 |
| stub | stub__r5wSYYu | 0.0 |
| forgery (shipped-answer replay) | forgery__Yi5MWCp | 0.0635 |

- TRUTH.md regenerated by script last (t4_scripts/truth4.py): item 24 oracle and ledger corpora, 110 checks / 488, measured costs, golden trial plain__6EdDt3N, solve_py_sha256 ceb1015ab794. TRUTH is solution-only and changed after the gate copies; solve.py and tests were not touched after the copies.
- Hygiene: no `__pycache__` or .pyc in the bundle. Tree sha (sha256 over sorted relative paths and file bytes): 506e7f683958.
- Tasks_INPUT: `cp -p` of 5 files (environment/ci/vouchers.csv, solution/TRUTH.md, solution/solve.py, tests/reward.toml, tests/test_output.py); `diff -rq` BUNDLE vs copy empty (rc 0).

## Not run

- No fresh blind read (master issues it next). No harness probe. Kill test on prototypes plus whole-program cost run on the final generator output; no second design was needed.

## Lessons for the master
Width, not count, killed r3: the blind bitset was exact because 4M-12M cents fits memory; check the widest one-sum table against the 4 GB box before calling a core hard | template_change: LEVER_RULES_v3.md:211 (add "table width in bits vs box memory" to the design-blind line)
Kill solvers measured as whole programs through the real checks (hook the solver in before solve.py zips the repo) also caught r3 points lost by the sum-only bitset | no change: Phase 3 cost table already asks for it
The go message carried a numbered item with "I'd skip it" inside; built it as numbered and flagged it | no change: master's call
Docker slot waits took 35 of 53 gate minutes under the max-2 rule | no change: scheduling, not a template issue
