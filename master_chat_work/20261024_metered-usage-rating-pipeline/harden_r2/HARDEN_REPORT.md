# Harden round 2: metered-usage-rating-pipeline (e2dc50b)

Status DONE. Bundle tree ea4a234ce72b (before 36fe302d21c8). Phase A GENUINE, primary cause C4: all three r1 levers were literal definitions, and the differential fuzz on the probe-2 program found 0 differing corpora out of 311 valid ones (see DIAGNOSIS.md). Session rename: `name_session.py e2dc50b` printed "codex: no match / opencode: ['ses_e90f61009ffe2dOV9L2dzi3Q8F']". e2dc50b was not listed, and I did not retry.

## What changed
- **LV-MU-6 (new, H7 re-entry, A)**: the credit section in rating_contract.md:162-177 has two branches. When base <= pool, each line's credit is its own charge. When base > pool, the first share is pool x charge / base. Any line below 0.50 gets 0.00, and then "every cent of the credit pool is shared again, pool × line charge ÷ summed charge of the lines that held 0.50 or more, rounded half-even to 0.01, across only those lines" (the F2 wording as the master asked).
- **LV-MU-7 (new, H7 re-entry, C)**: the `minimum` attribute is added to commitments.xml, with a glossary entry at 34-35 and a True-up section at 179-189. The shortfall is minimum - base. It is shared "in proportion to charge, rounded half-even to 0.01", with a 0.50 floor and a re-share across only the lines that held 0.50 or more. There is a new `true_up` field on lines and documents, and net = charge - credit + true_up.
- **LV-MU-5 (rewritten, H6 recursive)**: the billing group is now "the account itself when its parent column is empty, and otherwise the billing group of the account named in its parent column" (24-26). The one-level bound sentence at accounts.csv 96-99 is removed. The hidden month has chains up to 4 deep (depth 2: 70 accounts, depth 3: 21).
- **Noise**: LV-MU-1 (bare JSON integer) and LV-MU-3 (committed account = accounts.csv plan) are unchanged and are now counted as noise. Deviation from DIAGNOSIS: I left the committed-account glossary as it was because that is the smallest change.
- **Generator**: `_gen_rate` is bounded to 1000 tries. Output is byte-identical for the shipped seed 461927 and for 58213 (OUT/proto/hash_before.txt and hash_after_p21.txt). A second latent crash is fixed: `randint(1,0)` in 28 of 300 seeds when an STO rate fell to 1. The redraw keeps r2 data byte-identical. A 300-seed generator fuzz now gives 0 loops and 0 errors.
- **Hidden plants**: 3 'sep' regions where the re-share makes credit exceed charge (323-358 lines each), 1 region with base < pool, 1 region with a credit tie, and 3 shortfall regions (664-699 true-up lines). The shipped month separates nothing: parents are empty, pools are 0.20-0.45 of base, and every minimum is below base.
- **Tests**: 64 checks, 247 positive points, -5 negative. A new true_up_<r> family was added. credit_<r> now owns plan and credit. Two new mutation tests: mutation_small_commitment (w3) and mutation_near_base_pool (w5). Judge R16 now checks that every credit and true-up was recomputed (`check credit_true_up ok`). There are still 16 criteria (+34/-14).

## Measured
| lever | alone lost | one-fact-wrong | fuzz: reflex exercised / probe-2 program differs |
|---|---|---|---|
| r1 LV-MU-1 / 3 / 5 (before) | 95.0 / 42.7 / 55.3 | 73.9 / 22.6 / 25.1 | 304, 239, 217 of 311 / **0, 0, 0** |
| LV-MU-6 (A) | 26.3% (13) | 10.1% (5) | 209/347 / 209/209 |
| LV-MU-5 (B) | 53.8% (27) | 53.8% (cascade via COUPLING) | 244/347 / 244/244, tier diffs identical to the reflex mutant in 347/347 |
| LV-MU-7 (C) | 26.3% (13) | 12.1% (6) | 253/347 / 253/253 |
| noise LV-MU-1 / LV-MU-3 | 84.6 / 47.8 | - | - |

Predicted outcomes at the measured judge score of 70.59:

| reflex readings taken | tests | overall |
|---|---|---|
| A and C (B right) | 61.5 | 66.1 |
| A or C only | 73.7 | 72.2 |
| all three | 46.2 | 58.4 |

- **Shares**: hidden or mutated 65.6%, row-owned 0.518, whole-document 0.389, shipped-only 0.344, mutation 5.3%. One check has weight 1 (transform_exists).
- **Reflex gate**: the probe-2 agent program scores 41/247 = **0.166, which passes**. The caveat is that most of its failures come from the new `true_up` surface. Running all three reflex readings on the oracle gives 0.462 as an advisory figure. Following master note 5, I did not add a fourth lever.

## Gates
- **STACKING_CHECK**: PASS (parts a-e).
- **RULE_COVERAGE**: 64 rules, 0 uncovered.
- **QC kit 976c166**: structure WARN X1 only, instruction PASS, tests WARN A3 (64 checks), judge 19/0/0.
- **validate_bundle**: 39/0.
- **precheck**: PRECHECK CLEAN.
- **xref**: 16 entries, 0 findings.
- **Oracle against the independent checks**: solve.py == ref_compute on 4 seeds, and check_exact passes.
- **Docker chain 20261025T013018-a804**: oracle 1.0/1.0/1.0, owner-only 1.0, nop 0.0, stub 0.0, forgery 0.336.

## Notes
- The fuzz cannot show whether A and C will catch a fresh agent. The probe-2 program differs on them only because those rules are new. The prediction rests on H7 alone, which is the only habit Opus has missed, and the F2 wording names the method explicitly, so A and C may turn out REVEALING. B is the only lever where the old program reproduces the reflex reading exactly.
- A and C use the same habit, so a fresh agent will likely get both right or both wrong (38.5% lost together).
- B's one-fact-wrong cost is 53.8% because a wrong tier cascades through charge, base, credit and true-up. QC_DEFENCE carries the CL-4 exemption sentence for this.
- The fuzz harness rejected 6 of 353 cases because of a double-variant spelling bug in the harness. This is not a task defect.
- Not run: a fresh agent probe, which is for the master to schedule.

## Lessons for the master
- The probe-2 program differs on new rules by construction, so the "agent program differs" gate cannot tell a REVEALING new lever from a working one. Only the probe can.
- Rewriting a definition recursively (B) is the one case where the old program reproduces the reflex reading exactly, so measure it first.
- The generator had a second latent crash (`randint(1,0)`) in 9% of seeds. The 300-seed generator fuzz should be a standing gate.
