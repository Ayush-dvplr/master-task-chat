# Harden round 3 (last): sentinel-policy-recompute (9aaa7c6)

Phase A was GENUINE: the job ran clean, the staged copy matches BUNDLE, and the judge read the response. The primary cause is 4, levers weak by design. Each of N1, N2 and N3 is stated in a sentence that names its key, file and separating case. Differential fuzz of the probe-2 agent program on 307 corpora differed on 0% for every lever (N1, N2, N3, L7, L1, random, struct). Full diagnosis: DIAGNOSIS.md.

Following the master GO of 25 Oct, the round adds one counted lever, N4, an H7 re-entry rule written in the caldermoor F2 form. N1, N2 and N3 stay in place as feeders.

## Levers, before and after
| lever | rule (agent-visible) | r2 alone loss | r3 alone loss (P=52) | probe-2 program |
|---|---|---|---|---|
| **N4 timeout pool, re-share after drop (new, only counted lever)** | override_precedence.conf:7; `timeout_pool=` on every window in effective_windows.xml; pointer in override_deltas.json conventions line 10 | n/a | 16/52 = 30.8% for every one-fact-wrong reading (off, fits re-checked, first share kept, only dropped ms re-shared, no drop, resolved key only) | **misses**: fuzz differs 111/300 corpora (37%) |
| N1 region allowance (feeder) | quota_limits.cfg:7, values :9-23 | 52.3% | 44.2% (one counter 38.5%) | right, 0/307 |
| N2 unit cutover (feeder) | units_reference.txt:6-7 | 34.1% | 28.8% | right, 0/307 |
| N3 window admit + draw_order (feeder) | override_precedence.conf:5-6 | 52.3% | 44.2% (draw_order 28.8%) | right, 0/307 |
| L7 rounding / L1 controls (noise / amplifier) | risk_weight_rounding.txt:2-3 / conventions controls | 18.2% / 11.4% | 15.4% / 9.6% | right |

N4 truth (caldermoor reading). When the positive timeout deltas of a window's applied rows fit in the pool, each row adds its own delta. Otherwise each row gets floor(pool × d / sum). Rows whose share falls under 100 add none, and the whole pool is shared again by floor(pool × d / sum of survivors) across the survivors only. The fits branch is not checked again.

The probe-2 program never pools, and that alone gives the wrong answer. Shrunk example pool-a: truth 2771, agent 2747. The shipped answers 285/3/2250/51 are unchanged because WIN-AUTH timeout_pool 1200 holds the shipped rows (Never 11).

COUPLING: N1 and N3 decide which rows are drawn, and N2 sets the unit of each drawn delta. N4 then pools the drawn rows of every tenant per window. hidden-c and hidden-d (policy test) depend on all four.

PL note: N4 is the only counted lever. This knowingly breaks the ≥3-lever rule; the master accepted it on 25 Oct (last round).

## Grading
- Tests: 17 checks, 14 positive, P=52. Two of them are new: `hidden_timeout_pool_hard` (pool-a, pool-b) w5 and `mutation_pool_cut_reshares_timeout` w3. The pool is also planted in hidden-c, hidden-d and mutation-risk. Negatives are −5/−3/−3.
- Shares: hidden or mutated 92.3%, isolated `_hard` 38.5%, whole-document 28.8%, shipped-only 1.9%.
- Judge: 16 criteria, P=40. R1-R15 are kept and R16 (w3) is added: the agent checks timeout_pool on its own ledger. solve.sh prints `check R12 ok`..`check R16 ok`. The R16 ledger uses pool 780 and rows 60/450/300 and gives 2780.
- reward.toml weights: test_output 0.5/52, judge 0.5/40.
- Cost (G10): with N4 alone wrong, tests are 69.2. Overall is 52.1 at judge 14/40 and 79.6 at rubric 90 (info). The probe-2 agent program scores 36/52 = **0.6923** locally. It fails pool-a (2747 vs 2771), hidden-c (2610 vs 2565), mutation-risk (2610 vs 2565) and mutation-pool (2872 vs 2899).

## Gates
- Reflex gate (≤0.20): **not met**, at 0.6923. Per the master target (tests 85-95, one genuine miss, smallest honest change) I did not strengthen it. The predicted tests score, 69.2, sits slightly under that band.
- STACKING_CHECK.md: STACKING PASS, with the master-accepted single counted lever and the reflex exception noted.
- RULE_COVERAGE.md: 24 mutants (m19-m24 are N4), 0 uncovered. xref_check: 57 entries, 0 findings.
- QC kit 976c1666: the 4 scripts have 0 FAIL (X1 binary-skip warn). PRECHECK CLEAN. Validator: 37 pass, 3 fail; all 3 are the pre-existing §15.5-15.7 yaml provenance block, same as r2. There is no bytecode in the bundle, and the TRUTH sha lines were regenerated last.
- Docker, tests-only (TS 20261025T005924-dce8, ALL_DONE 01:03:51): oracle 1.0/1.0/1.0, owner-only 1.0, nop 0.0, stub 0.0.
- Forgery (policy dict hardcoded to the shipped answers in the oracle cli; self-checks removed): 0.2308. It keeps curve and trace (still computed honestly), cli, validate and shipped. It loses every policy check, and the −5 hardcoded negative fires. The first chain had an argument bug that produced no runs (log kept as `runs_failed_argbug.log`); it was relaunched once.
- Tree sha: 66e42076dd4f (sha256 over sorted relpath + file sha256).

## Not run
- No real agent run and no live judge. Next: one harness probe; if tests ≥ 95, park; otherwise go to P11 QC.

## Lessons for the master
- Fuzz the probe program before keeping a lever: N1-N3 differed on 0/307 corpora, while the H7 re-share differed on 111/300 | no change: already in the 24 Oct master notes
- A pool shared across tenants forces the oracle and the test reference to track every drawn row, not only the resolved key's | no change: task-specific
- A zsh-built chain.sh split the harbor args and every run failed in 1 s; building the chain from a python list fixed it | template_change: _adhoc/20261022_round_notes.md section G (chain recipe)
- Forgery share depends on what is hardcoded: policy-only forgery keeps the honestly computed curve/trace (0.23 vs r2 0.05) | template_change: _COMMON_RULES_v3.md forgery definition, to name which documents are hardcoded
