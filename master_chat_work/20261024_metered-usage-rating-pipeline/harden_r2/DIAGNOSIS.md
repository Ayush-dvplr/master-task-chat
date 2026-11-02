# DIAGNOSIS: metered-usage-rating-pipeline, harden round 2 (e2dc50b)

Written 2026-10-24 23:45 IST. Probe 2 (harness attempt 2, bundle tree 36fe302d21c8, after harden r1 3106c16): tests 199/199 = 100, judge 24/34 = 70.59, overall 85.30.
Session rename: `name_session.py e2dc50b` printed `codex: no match / opencode: ['ses_e90f61009ffe2dOV9L2dzi3Q8F']`; the list does not show e2dc50b. Noted, not retried.

## 1. Phase A: GENUINE

- Trial `metered-usage-rating-pipeline__yrUGg9A`, 16:59:53Z to 17:15:06Z. `result.json` `exception_info`: None. Reward 0.8529.
- wrapper.log: "INTEGRITY: all 1 trial(s) completed cleanly; scores are trustworthy." finalize.log: "test=100.00% rubric=70.59% final=85.30".
- test-stdout.txt holds only `_check_restates_shipped(): fresh-month summary.json restates no shipped figure` and `reward: 0.8529`. No traceback, timeout, `Permission denied` or `Errno 13` in any run file. The only hit is the `exclude_exceptions` names in job-lock.json, which is config.
- Staged copy `.kiro-staged-tasks/metered-usage-rating-pipeline` vs BUNDLE (`diff -rq`): the only differences are `.kiro-staged-from` and the harness-added `"host.docker.internal"` in task.toml `allowed_hosts` (lines 25 and 32). Tree 36fe302d21c8 equals the r1 final.
- The judge read the response properly: each of the 16 criteria has a reason that quotes the trajectory (for example R16 "used its initial plan field to identify committed accounts ... A separate committed-ness check also tested accounts whose in-force plan changed").
- reward-details.json: all 51 positive checks scored 1.0, every `_hard` check included. negative_hardcoded_sample_answers scored 0.0 (did not fire).

Verdict: **GENUINE.** The 100 is real. The agent program gives the oracle's output on the hidden month.

## 2. Root cause

| # | Cause | Verdict | Evidence |
|---|---|---|---|
| C1 | Run error / wrong copy | NO | Clean run, no exception. Copy equals the bundle apart from the harness allowed_hosts. |
| C2 | Harness / rescoring change | NO | Test weight 1/398 and judge 1/68 match reward.toml 0.5/0.5. The rescale 0.8529 -> 85.29 is the standard finalize. |
| C3 | Our QC/fix rounds made it easier | NO | There never was a hard baseline: probe 1 (before r1) was tests 100 / judge 75. Files r1 changed: rating_contract.md (glossary: committed account, billing group, tier counter; bare north `units (a JSON integer)`; accounts.csv `parent` column), accounts.csv (empty parent column), tests/test_output.py, solution/solve.py, TRUTH.md, judge.toml (R15/R16). None of these puts a separating row or a worked example in front of the agent. Each states its rule as a literal definition, and that literal form is what C4 is about. |
| C4 | Levers weak by design | **YES (PRIMARY)** | All three r1 levers are literal one-reading definitions that Opus copies into code sentence by sentence. Differential fuzz shows 0% differing on every lever (section 2a). |

Contributing: the shipped data plants none of the separating rows (parents all empty, plan in force always equals the accounts.csv plan). Only the hidden month separates, so the agent's self-checks could not fail. That is by design (W5), but the wording must invite the wrong reading, and here it did not. The r1 lesson applies again: hidden-only separation is not a lever unless the wording invites a second reading.

### 2a. C4 per lever (rule text, step the agent got it right, what gave it away, fuzz)

Fuzz: kit copied to OUT/fuzz/ and adapted. `m_acct` reads 4 columns. New mutations: `m_group` (billing groups plus heavy grouped lines) and `m_quoted` (quoted north units). Lever mutants `mut_mu1/3/5` are the probe-2 program with ONE wrong reading, used to prove that a corpus exercises the lever. Image `warm-metered-usage-rating-pipeline`. 493 cases, 311 valid. 153 cases hit the generator loop: `_gen_rate never terminates`, trapped by the bounded patch. 28 were tiny-corpus randrange errors and 1 was an assert. Agent differs 0/311 and oracle differs 0/311.

| Lever | Rule (rating_contract.md) | Corpora exercising (mutant differs) | Agent program differs | Trajectory step | Give-away |
|---|---|---|---|---|---|
| LV-MU-1 bare north `units` | 69-71 "`units` (a JSON integer)"; 80-82 text "one or more ASCII digits"; 133 item 4 | 304/311 (97.7%) | **0/304 (0%)** | 16: profiled north unit types `Counter int 3119, str 60, float 30, bool 14, NoneType 9`; 17: classified the strings; 28: counted padded digit strings. Code L109 `raw if isinstance(raw,int) and not bool` | "a JSON integer" is a type name. Opus checks types with a profile, and the shipped data shows quoted digits next to ints. One reading only. |
| LV-MU-3 committed account = accounts.csv plan | 22-23 glossary; 30-31 credit base; 161-165 | 239/311 (76.8%) | **0/239 (0%)** | 33-35: grep AC25749, then "payg accounts that became committed: 34 / such lines total: 298 with nonzero credit: 0". Code L403 `accounts[acct]['plan']=='committed'` | The glossary names the file and the column. Opus uses the named field; nothing pulls it towards the in-force plan. |
| LV-MU-5 billing-group tier counter | 24-29 glossary; 94-97 parent column ("empty or account_id of another account whose parent is empty"); 149-152 | 217/311 (69.8%) | **0/217 (0%)** | 14: `awk -F, 'NF!=4' accounts.csv` saw the parent column; 23/25: code L174-187 `canon(parent) or account`, L388 counter keyed (group, code); 37-39: mutB planted parent groups; judge R15 "verify.py maintained billing-group/product counters" | The one-level bound sentence (94-97) makes the group a one-step lookup. The definition names the key exactly. |
| LV-MU-2 half-even 0.01 / LV-MU-4 canonical ids | 154-157, 161-165 / 89-90 | n/a (noise) | 0 | 23-25 | Stated once, applied literally. |

## 3. Lever table (probe 2, reward-details.json)

Weights: visible 3, `_hard` 5. Total positive 199, negative -5.

| Check family | Checks | Points | Earned | Levers | Status |
|---|---|---|---|---|---|
| accepted_lines (+_hard) | 2 | 8 | 8 | MU-1 | LEAKED |
| rating_<region> (+_hard) | 10 | 40 | 40 | MU-1, MU-5 | LEAKED |
| credit_<region> (+_hard) | 10 | 40 | 40 | MU-1, MU-3, MU-5 | LEAKED |
| region_<region> (+_hard) | 10 | 40 | 40 | MU-1, MU-3, MU-5 | LEAKED |
| segment_<segment> (+_hard) | 8 | 32 | 32 | MU-1, MU-3, MU-5 | LEAKED |
| product_summary (+_hard) | 2 | 8 | 8 | MU-1, MU-5 | LEAKED |
| summary (+_hard) | 2 | 8 | 8 | MU-1, MU-3, MU-5 | LEAKED |
| data_quality (+_hard) | 2 | 8 | 8 | MU-1 | LEAKED |
| mutation_tier_scale | 1 | 5 | 5 | MU-5 | LEAKED |
| missing_collector, control_mismatch, determinism, transform_exists | 4 | 10 | 10 | none | n/a |
| negative_hardcoded_sample_answers | 1 | -5 | 0 | none | did not fire (correct) |

Judge 24/34. Lost points: R5 summary recompute (-3: "no check explicitly summed charge, credit, and net from the parsed lines ... with summary.json"), R8 main() > 150 lines (-3: main spans L303-557), R9 path listing (-1: grouped basenames), R12 FIRED (-3: "846 quarantined" stated without a command that computed it). R15 tier recompute and R16 credit-base recompute both earned. Judge points were lost on conduct, not on levers.

## 4. Trajectory autopsy (50 steps, 17:00:30Z to 17:13:17Z, 12m47s)

| Phase | Steps | Time | What |
|---|---|---|---|
| Read | 3-9 | 17:00:35-17:00:5x (~25 s) | ls/wc; step 5 reads all of rating_contract.md; heads of every collector, controls, commitments, products.ini, rate_card, accounts.csv, plan_changes |
| Profile | 10-22 | 17:00:5x-17:03:08 (~2.5 min) | per-collector product/units/account forms; 14 sees the 4-column accounts.csv; 16-17 north unit types; 18-22 duplicates, plan_changes variants and order, latin-1 slicing |
| Write | 23-25 | 17:04:34-17:05:30 (~1.5 min) | transform.py created at 23 and rewritten at 25. **Step 25 is the last edit to graded logic.** |
| Self-test | 26-47 | 17:05:34-17:12:10 (~6.5 min) | 29 an independent /tmp/verify.py; 31-32 pool/base and random line recompute; 33-35 the LV-MU-3 in-force vs file-plan check; 36 doubled pool; 37-39 mutate.py with parent groups; 40-41 handcheck; 42 missing input; 43 relative paths from another cwd; 44-45 large generated corpus plus timing; 46 empty input; 47 final run plus md5 |
| Close | 48-50 | ~1 min | py_compile/ast, rm __pycache__, finish |

Self-tests covered all three levers (MU-1 at 16/28, MU-3 at 34, MU-5 at 37-39). None of them could fail, because the program already implemented the literal rule, and the levers offered no second reading to test against.

## 5. Agent program

Saved: OUT/agent_program/transform.py (561 lines) plus 13 output docs from `Run 1/artifacts/app/out/`. Logic: canonical id `strip().upper().replace('-','')`; text units `[0-9]+` fullmatch; north `isinstance(raw,int) and not bool`; plan timeline uses bisect_right, so a change at the same timestamp applies; counter keyed (canon(parent) or account, code); `in_base` uses the accounts.csv plan; credit `pool*charge/base` half-even; one credit pass.

## 6. LEAK_LIBRARY rows (to append)

| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| LV-MU-1 north units (metered r1) | bare "`units` (a JSON integer)" beside the global trim; the shipped north file mixes ints with quoted digits | step 16 type profile (`Counter int/str/float/bool/None`); 0/304 fuzz corpora differ | A type name is not a bare property. Opus profiles JSON types before coding, so data that shows both forms reveals the rule. Drop it as a lever (noise only). |
| LV-MU-3 committed account (metered r1) | glossary "value in the plan column of accounts.csv is committed" | steps 33-35 (in-force vs file check); 0/239 differ | A defined term that names its file and column has one reading. H3 needs a definition whose words fit the per-line field too. Replace it. |
| LV-MU-5 billing-group counter (metered r1) | glossary key plus "parent is empty or the id of an account whose parent is empty" (one level) | step 14 saw the column, 37-39 mutated groups; 0/217 differ | A stateful key named exactly with a stated depth bound is transliterated. Make the key recursive with no depth sentence. |

## 7. Proposals for Phase 2 (master review)

Gate honesty: "the agent program differs on the new rule" is necessary but not sufficient. Any semantic change differs mechanically on a program written for the old contract. The real prediction rests on habit evidence. H7 (re-entry by "the same rule") is the only habit Opus has missed in measured fuzz (caldermoor CM-B, 1889 corpora). So A and C are built on H7, and B is a re-written H6.

### A. LV-MU-6 NEW (H7): credit re-share. Replaces LV-MU-3 as the credit lever; COUPLING stays the region credit base.

- Text (replaces rating_contract.md 161-165; glossary 30-33 unchanged except that committed account becomes the plan in force, which drops LV-MU-3):
  "When the credit base of a region is at or below its credit pool, each line counted in the credit base receives its own charge as credit and the rest of the pool is left unused. When the credit base exceeds the credit pool, each counted line receives credit pool times line charge divided by credit base, rounded half-even to 0.01. A line whose credit then falls below 0.50 receives 0.00, and the whole of the credit pool is shared again by the same rule across only the lines that held 0.50 or more. When that leaves no line standing, every credit in the region is 0.00. Every other line has credit 0.00."
- Correct pass 2: the survivors' base is at or below the pool, so branch 1 is NOT re-entered. "The whole of the credit pool" is shared proportionally across the survivors, so a credit may exceed the line's charge (caldermoor precedent: 30 against an effort of 20). Reflex: a recursive helper re-enters the at-or-below branch, so each survivor gets its own charge and the rest is left unused.
- Shrunk corpus (proto/levers_proto.py): pool 10.00, counted lines 9.80 / 0.30 / 0.25. Oracle gives {10.00, 0, 0}; the reflex gives {9.80, 0, 0}.
- Hidden cases (G12 plants): 3 regions with Σsurvivors ≤ pool < Σbase (small lines hold the gap), 1 region with pool ≥ base (branch 1), 1 normal region. A mutation test with a tiny pool covers the "none standing" case. Shares in pass 2 only grow, so no new line drops below the floor; the generator asserts this. Shipped month: pools are 0.22-0.45 of base. Sub-floor lines exist, but the survivors' base stays above the pool, so pass 2 is proportional under both readings. Visible values change, so the key is regenerated, but nothing visible separates the two readings (W5).
- Predicted alone: about 30% (credit_r_hard ×3, region_r_hard ×3, segment_hard ×4, product_summary_hard, summary_hard ≈ 60/199). One fact wrong (one region): about 10%, which is honest (CL-4 counts one fact).
- QC risk: IN-16 "same rule" may be read as ambiguous. QC_DEFENCE: "the whole of the credit pool" fixes the amount, and "by the same rule" names the proportional sentence, as in the caldermoor ruling.

### B. LV-MU-5 KEEP-REWRITE (H6 plus recursion): billing group by chain.

- Text (glossary 24-26; delete the one-level clause in 94-97): "The billing group of an account whose parent is empty is the account itself; the billing group of any other account is the billing group of its parent." accounts.csv 94-97 becomes "parent: empty, or the account_id of another account" with no depth sentence. The generator guarantees no cycles and asserts it.
- Hidden: chains of depth 2-3 (about 40% of the 93 groups), heavy members at the deep end. Shipped: parents stay empty (W5).
- Agent program L174-187 `canon(parent) or account` is one level, so it differs. Shrunk corpus: C→B→A, CMP tiers from 0/100/500, lines A 450, C 80, B 10, C 5. Oracle tiers [1,2,3,3], one-level [1,1,2,1].
- Predicted alone: about 50% (r1 LV-MU-5 measured 55.3% alone; the rewrite keeps the same tests). One fact wrong: about 25%.
- Weakness: Opus may write a loop up the chain because "billing group of its parent" reads as recursion. Its strength is that the agent's profiling of shipped data shows no parents, so the agent has nothing to test against. Medium confidence. Fallback: B' = state the key as "the account at the top of its parent chain" in the glossary only, and use the per-line field `group` in normalized.jsonl, which shows the direct parent (H3 pull).

### C. LV-MU-7 NEW (H7 variant): region minimum shortfall re-share. New field, independent of A.

- Text (new "True-up" section after Credit; commitments.xml gains a `minimum` attribute per region; normalized.jsonl gains `true_up`; region/segment/summary gain `true_up` totals; net = charge - credit + true_up):
  "When the committed charge of a region is below its minimum, the shortfall is the minimum less the committed charge. It is shared across the lines counted in the credit base in proportion to charge, rounded half-even to 0.01. A line whose share falls below 0.50 receives 0.00, and the whole shortfall is shared again by the same rule across only the lines that held 0.50 or more."
- Reflex: recompute the shortfall from the survivors (minimum less the survivors' charge) instead of the whole shortfall. Shrunk corpus: minimum 100.00, committed charges 60.00 / 1.00 / 0.40. Oracle {37.97, 0.63, 0}, reflex {38.36, 0.64, 0}.
- Hidden: 3 regions below the minimum with sub-floor lines; shipped: every region at or above the minimum (true_up all 0.00 visible).
- Predicted alone: about 25-30% (true_up fields owned by their own checks, e.g. truep_<region>_hard ×5 plus the summary true_up field). One fact wrong: about 6% per region.
- Risk: C and A share the "same rule" wording, so if Opus resolves one it may resolve both (correlated, not independent in habit). I keep them because the fields and tests are independent. Fallback C' = H2 glossary rate step (the rate per unit rounded to 0.0001 when a tier changes mid-month), judged weaker.

### Dropped

- LV-MU-1 stays as contract text but stops being a lever (noise), since 95% of the points sat on a revealing rule.
- LV-MU-3 is replaced by A. The glossary moves to the plan in force, so the credit base and the segment use the same plan; this removes the R16 split.
- LV-MU-2 and LV-MU-4 stay noise.

### Totals and COUPLING

- Three levers A, B, C plus COUPLING (region credit base: B moves charges, which moves the base for A and the committed charge for C).
- Predicted Opus: if A and C both trip and B holds, tests are about 45-55 and below target. If only one H7 trips, about 70-75. Target band 70-90 (<95). I will tune with weights after the reflex gate rather than add more levers.

### Generator loop fix (Phase 2)

`tests/test_output.py:343-350` `_gen_rate` loops forever (`while True`) when tie-capable and every candidate in [lo,hi] maps to a multiple of 25. In fuzz, 153/493 cases (31%) hit this. Fix: bound it to 1000 tries and return None; `_gen_lower_rate` treats None as a miss and keeps its fallback. Proof: byte-identical gen_month output for the shipped seed and HIDDEN_SEED 58213 before and after, plus a 300-seed generator fuzz with no loop (G12).

### Judge (Phase 2, no new criteria planned)

Keep R1-R16. R16 changes from "credit-base recompute" to "credit re-share recompute on a copy with a small pool" (J9). Code quality stays one J4 judgement.
