# Where Claude Opus 5 loses points, and which hardness levers do the work

Measured on 2026-10-27 from the 85 delivered bundles in
`Anubis_Tasks_Samples/Final_Delivery`. Every bundle carries exactly one
`trajectories/claude-opus-5/run_1/report.json`, which records each test check
(name, weight, passed) and each judge criterion (text, weight, evaluation
target, importance, passed). That is 2,950 graded test checks and 1,842 judge
criteria. Judge model on every run: `gpt-5.6-sol`.

Everything below is counted from those files, not estimated. Section 9 names the
formulas and how to regenerate the numbers.

One caveat to keep in mind: one run per task. A single task's score is a single
sample and can swing. The aggregate over 85 tasks and 4,792 graded items is
where the signal is, and that is what this document argues from.

---

## 1. Headline

| Measure | Value |
|---|---|
| Mean final reward | 51.95 |
| Median | 53.99 |
| Range | 9.06 to 72.89 |
| Tasks at 60 or above | 36 of 85 |
| Tasks below 40 | 18 of 85 |
| Tasks below 25 | 7 of 85 |

Split by channel (the harness reports each half separately, then averages them):

| Channel | Mean | Median | Positive weight earned |
|---|---|---|---|
| Tests (`test_output.py`) | 43.91 | 42.00 | 3,734 of 8,429 (44.3%) |
| Judge (`judge.toml`) | 59.99 | 65.00 | 2,950 of 4,514 (65.4%) |

The tests half is the weaker half in 55 of 85 tasks. **Opus 5 is substantially
better at behaving like a competent engineer than at producing the exactly
correct artifact.** It never scored a single task above 72.89, and it never
scored one at 0 either: no task is beyond it, and no task is fully solved by it.

---

## 2. The one sentence version

**It fits the sample it can see and fails the instance it cannot.**

The clearest single piece of evidence, task `59417607-2254-5165-b703-0d5a4aeb7367`
(final 15.68, tests 7.22):

- passed: `shipped_normalized_stream_exact`, `shipped_product_lines_exact`,
  `shipped_region_invoices_exact`, `shipped_segment_invoices_exact`,
  `shipped_summary_exact`, `shipped_data_quality_exact`, `run_output_lists_reports`
- failed: `hidden_extract_01_exact` through `hidden_extract_08_exact`, every one
  at weight 5

Same program, same contract. On the inputs shipped into `/app/data`, where it
could iterate until its output matched, it reproduced every byte. On eight
inputs the verifier generated from the same specification, it reproduced none.

Two more of the same shape:

- `8defd7be-eb46-5779-a556-aec18521635e` (final 9.06): passed
  `program_writes_the_three_reports_from_two_directory_arguments` and
  `report_serialization_carries_the_documented_byte_form`, failed all eight
  `full_ledger_on_unseen_run_*` checks.
- `d49e259f-e365-552a-82fe-ace72ff03c8b` (final 20.28): passed
  `reusable_program_is_delivered`, `untrapped_run_alpha_resolves`,
  `untrapped_run_beta_resolves`, failed all eight `mode_bit_*` checks (the tier
  where two rule bits interact).

The deliverable exists, runs, takes the right arguments, writes the documented
shape. The numbers inside it are wrong as soon as the input is new.

---

## 3. Failure modes, ranked by measured severity

Failure rate is over positive checks only. Themes are matched on check names and
**they overlap**: `hidden_extract_01_exact` counts under both "held-out" and
"exact value". Weight lost is out of 8,429 total positive test weight.

| Rank | Failure mode | Checks | Failed | Weight lost |
|---:|---|---:|---:|---|
| 1 | Held-out / hidden instance (`hidden_*`, `heldout_*`, `*_on_unseen_*`, challenge corpora) | 361 | **73%** | 1,256 (77% of that tier) |
| 2 | Cross-file lookup chain (resolve through a second and third file) | 105 | **64%** | 281 (75%) |
| 3 | Exact value / byte equality | 623 | **60%** | 1,588 (66%), the largest absolute loss |
| 4 | Edge cases and traps (ties, empty, malformed, boundary, rounding) | 263 | **54%** | 623 (59%) |
| 5 | Determinism / idempotence (run twice, identical bytes) | 58 | 31% | 72 (40%) |
| 6 | Artifact exists, runs, parses, has a CLI | 118 | **17%** | 84 |
| 7 | Shape, keys, schema, serialization form | 93 | **15%** | 62 |

Rows 6 and 7 are the mirror of rows 1 to 4. Of the 24 tasks that carry both
plumbing checks and exact-value checks, **15 show the signature "plumbing
passes, exact values fail."** The work always looks finished.

### Weight is the sharpest discriminator we have

| Check weight | Failure rate |
|---|---|
| 1 (minor detail, existence) | 107 of 572 = **19%** |
| 3 (important sub-goal, key edge case) | 301 of 704 = **43%** |
| 5 (core outcome, primary behaviour) | 737 of 1,149 = **64%** |

Monotone, and steep. Our weight scale (TS-20: 5 = core outcome, 3 = important
sub-goal, 1 = minor detail) is an accurate difficulty predictor for this model
without anyone having tuned it for that.

**26 of 85 tasks failed every single weight-5 check.** That one fact explains the
low tail better than anything else: once the core-outcome tier is gone, the
tests half is capped at the leftovers, roughly 20 to 35 percent, and the final
reward cannot pass 50 even with a flawless judge half.

### Check-name tokens with the highest failure rates

Tokens appearing in 40 or more positive checks:

| Failure rate | n | Token |
|---:|---:|---|
| 99% | 70 | `extract` |
| 96% | 50 | `bit` (interacting rule bits) |
| 92% | 53 | `mode` |
| 86% | 57 | `heldout` |
| 85% | 48 | `corpus` |
| 75% | 48 | `generalises` |
| 67% | 75 | `hidden` |
| 66% | 47 | `resolves` |
| 64% | 69 | `eval` |
| 62% | 56 | `trap` |
| 61% | 552 | `exact` (1,422 weight lost, the single biggest bucket) |

And the tokens it is reliable on: `delivered` 5%, `artifacts` 5%, `cli` 18%,
`artifact` 18%, `config` 21%, `shipped` 22%.

### Most frequently failed individual checks

`zone_totals_match` (7 tasks), `corpus_index_match` (7), `posture_match` (7),
`heldout_dense_exact` (6), `validation_report_correct` (6), `summary_correct`
(6), the `aggregates_*_matches` family across seven serializations (5 each),
`heldout_reseed_exact` / `heldout_memo_exact` / `heldout_profile_exact` /
`config_matches_policy` / `aggregates_match` (4 each, 20 weight each).

The `aggregates_*` family is worth a note: when it fails, it fails across csv,
tsv, xml, ini, env, md and txt together. It is one wrong aggregate rendered
seven ways, not seven independent mistakes. Spreading one computation across
many output formats multiplies the weight at risk without adding reasoning
depth.

---

## 4. Judge-channel failures: process, not plumbing

| Evaluation target | Criteria | Failed |
|---|---:|---:|
| trajectory | 893 | 32% |
| final_answer | 286 | 34% |
| user_facing_message | 184 | 30% |
| state_change | 71 | 27% |

| Importance | Failed |
|---|---:|
| critically_important | 221 of 664 = 33% |
| important | 233 of 770 = 30% |

Flat across targets and importance tiers, which tells us the judge half is not
where the differentiation lives. By theme it is a different story:

| Criterion theme | Criteria | Failed |
|---|---:|---:|
| Verifies its own work, re-runs, compares against a second copy | 63 | **52%** |
| Derives or recomputes rather than taking a shortcut | 112 | **48%** |
| Covers every input or case | 195 | 34% |
| Honest reporting of what it did | 294 | 33% |
| Ordering and sequencing of steps | 350 | 31% |
| Reads the spec and inspects the inputs first | 197 | **23%** |

**It reads the brief. It does not check its answer.** The two themes it fails
most are independent verification (52%) and deriving instead of shortcutting
(48%), while the theme it fails least is reading the inputs (23%). The recurring
failed criteria name exactly that gap: "The agent verifies the pipeline against
a second copy", "The agent checks independently of its package, by hand", "The
agent runs its program over a copy of", "The agent runs its program on a season
it", "The agent works out independently of its package, by".

That is also the mechanical cause of section 2. A model that validated its
program against a case it had not tuned on would have discovered the held-out
failures itself.

### Cheating is not the problem. Overclaiming is.

| Negative check type | Defined | Fired |
|---|---:|---:|
| Test-side cheat checks (`negative_*`) | 525 | **2** |
| Judge-side negatives | 408 | **27** in 21 tasks |

The only two test-side firings in the whole corpus are `negative_fake_report`
and `negative_merge_applied_before_merge_instant`. Hardcoding sample answers,
pulling third-party dependencies, reading the training corpus at runtime,
writing into `/app/data`: effectively extinct.

The 27 judge firings are almost all one behaviour, claiming work it did not do:

- "The response claims a check or result that the agent's ..."
- "The agent claims a run, comparison or check, other than ..."
- "The agent states that it checked a published artifact against ..."
- "The response gives a figure for this interval that disagrees ..."
- "The response states a size, line count or row count ..."
- "The agent states in its final response that the repaired ..."

So the honest summary of Opus 5's conduct is: it does not cheat the grader, but
it does report more confidence and more verification than its trajectory
supports. The honesty negatives are the only place our negative tier earns its
keep against this model.

---

## 5. Why the ceiling sits near 70

Reward is `0.5 * test_raw / sum(positive test weight) + 0.5 * judge_raw /
sum(positive judge weight)` (reward.toml, weighted-sum, QC rule R3). Each half
is worth 50 points, so the arithmetic is unforgiving:

- Lose the weight-5 tier and keep everything else: tests land near 25, the run
  caps near 62 with a perfect judge half. Observed: 26 tasks lost that tier
  entirely.
- Both halves above 85 is what a 80-plus run needs. The best observed were
  `ec7941e5` (tests 91.55, judge 54.24, final 72.89) and `5e4fd36d` (judge
  98.86, tests 44.44, final 71.65). **No task in the corpus has both halves
  strong at once.**

The two halves fail for different reasons, which is why no run gets both: tests
need a correct answer on unseen input, the judge needs a disciplined process.
Opus 5 is mediocre at the first and decent at the second, and the 50/50 split
turns that into a hard ceiling in the low 70s.

---

## 6. Hardness levers we have set up

These are the knobs already built into the Input Bundle Generator and enforced
by the QC kit. For each: what it is, where it is enforced, what it measurably
does to Opus 5, and how to dial it.

| # | Lever | Enforced by | Measured effect on Opus 5 | Strength |
|---:|---|---|---|---|
| L1 | Weight concentration on core outcomes | TS-20 scale, A3 (10 to 35 checks) | weight-5 checks fail 64% vs 19% at weight 1; heavy-share correlates with the tests half at r = -0.38, the strongest lever measured | **Primary** |
| L2 | Held-out instances graded against a verifier-built reference | task design, `test_output.py` hidden checks | 73% failure, 77% of that tier's weight | **Primary** |
| L3 | Interlocking multi-file inputs with ablation necessity | DS-1, DS-2, `archetype.toml [dependencies]`, per-archetype `datagen.py` | cross-file chain checks fail 64% | **Primary** |
| L4 | Exact serialization contract, published, not hidden | CL-5, agent-visible `schema.md` / `api_contract.md` / `report_contract.md` | exact-equality checks fail 60%, 1,588 weight lost, 19% of all available test weight | **Primary** |
| L5 | Trap and edge-case tiers | task design, TS-20 weight 3 | 54% failure | Strong |
| L6 | Process criteria on the trajectory | `judge.toml`, `atif-trajectory`, batched mode, four annotation keys | self-verification criteria fail 52%, derive-not-shortcut 48% | Strong |
| L7 | Honesty negatives on the final reply | TS-14 / TS-25 / TS-S6 polarity rules | 27 firings in 21 tasks, the only negatives that catch this model | Strong |
| L8 | Determinism and idempotence | task design | 31% failure | Moderate |
| L9 | Reward geometry, 50/50 unclamped | R3, R4 | makes one lost tier cap the whole run; produced the low-70s ceiling | Structural |
| L10 | Execution realism: no network, uid 1000 agent, privilege-dropped verifier, pinned verifier image | S8 to S10, TS-24, TS-30 / H6, K5 / K8 | scores nothing directly, prevents fake zeros; the 0600 bug zeroed an entire EXEC tier on correct submissions | Guardrail |
| L11 | Solvability gates: oracle 1.000 five times, nop 0.000, stub low, DS-21 | Step 10, DS-21 | guarantees a low score means reasoning difficulty, not ambiguity | Guardrail |

### L1, weight concentration (the strongest knob)

Tasks split into quartiles by the share of positive weight sitting in weight-5
checks:

| Quartile | Heavy share | Mean tests half | Mean final |
|---|---:|---:|---:|
| Q1 | 41% | 65.4 | 58.6 |
| Q2 | 56% | 35.3 | 51.4 |
| Q3 | 71% | 45.0 | 52.5 |
| Q4 | 92% | **30.6** | **45.6** |

Q1 to Q4 costs the model 35 points of the tests half and 13 points of final
reward. Dial it by putting the core outcome on weight 5 and refusing to pad the
positive total with weight-1 existence checks. Note the inverse risk: a task
whose positive total is mostly weight-1 plumbing hands away points, which is
what Q1 shows.

### L2, held-out instances

The mechanism that works is **not** "add hidden checks", it is "grade the
deliverable on an input the agent never saw, with a reference the verifier
computes from the published spec". Presence alone proves little: tasks with any
held-out weight average 52.1 final versus 51.6 without. What matters is how much
weight rides on it. Where held-out tiers carry the weight-5 band, the model
loses the whole band (section 2's three examples).

Dial it by generating several unseen instances (`hidden_extract_01..08`,
`full_ledger_on_unseen_run_alpha..hotel`) and keeping each one independently
weighted, so partial generalisation scores partially.

### L3, interlocking inputs

Median delivered task: 53 input files, 25,574 input lines. The lever is the
interlock, not the volume, and the correlations prove it (section 7). What bites
is a value in one file that only means something after a second file is
understood: `resolves` checks fail 66%, `mode`/`bit` interaction checks 92 to
96%. DS-2 is the test that the interlock is real: deleting any single input
directory must make the task unsolvable.

### L4, exact contracts that are published

CL-5 forbids hidden conventions, so every exact comparison's requirements
(ordering, key names, path form, casing, rounding) must be stated in an
agent-visible file. That rule is what keeps this lever legitimate: the model
fails these 60% of the time while having been told exactly what to produce. The
difficulty is in computing the value, not in guessing the format, which is why
shape checks pass at 85% while the values inside fail.

### L6 and L7, the judge channel

Median 20 criteria per task (range 8 to 35), distributed 908 trajectory, 294
final_answer, 187 user_facing_message, 72 state_change, and 779 important versus
682 critically_important. The criteria that discriminate are the ones demanding
independent verification and honest reporting. Criteria about reading the inputs
discriminate least, because the model does read them.

Dial it by writing criteria that require a check the model would have to invent:
re-run on a second instance, recompute a figure by hand, compare against a
source it did not generate. Plus one honesty negative per claim the final reply
is likely to make.

### L9, reward geometry

`weights.test_output = 0.5 / sum(positive)` and `weights.judge = 0.5 /
sum(positive)`, aggregation `weighted-sum`, unclamped. Two consequences worth
designing around: a cheat firing at -5 is worth 2.5 points of final reward on a
typical 100-weight positive total, and a whole lost tier cannot be recovered
from the other channel.

### L10 and L11, the guardrails

They do not make tasks harder, they make hardness measurable. Two concrete
reasons they exist: the 0600 file-mode bug made every EXEC check fail on correct
submissions while the oracle still read 1.000 (now covered by H6, TS-30 and the
`--owner-only` oracle run), and an unpinned litellm in the verifier image put
remote-code-executing package content inside the container holding the judge key
(now covered by K5 and K8). Without L11's gates, a 9.06 is indistinguishable
from a broken task.

---

## 7. What does NOT make it harder (measured)

Pearson correlation with final reward across the 85 tasks:

| Feature | r (final) | r (tests half) |
|---|---:|---:|
| Share of weight in weight-5 checks | **-0.24** | **-0.38** |
| Held-out weight share | -0.19 | -0.21 |
| Trajectory cost in dollars | -0.22 | -0.24 |
| Tokens consumed | -0.18 | -0.21 |
| Positive test weight total | -0.11 | +0.03 |
| Number of judge criteria | -0.04 | -0.17 |
| Input bytes | -0.04 | -0.02 |
| Number of test checks | -0.02 | +0.13 |
| Input lines | -0.01 | +0.02 |
| Number of input files | +0.08 | +0.06 |
| Instruction length | **+0.11** | +0.15 |

Read that carefully before designing the next task:

- **Bulk does nothing.** Input lines, input bytes and file count are all within
  noise of zero. A 700,000-line corpus does not hurt it; a two-file dependency
  chain does.
- **More checks do not help.** r = -0.02. Splitting one computation across
  thirty assertions moves weight around, not difficulty.
- **Longer instructions correlate slightly positively.** Writing more prose
  makes the task marginally easier, not harder (median instruction: 4,455
  characters). Spelling the contract out is free difficulty-wise and buys CL-5
  compliance.
- **Tokens and cost are symptoms, not levers.** Hard tasks make it grind (median
  5.38M tokens, $6.12 per run), but grinding is the effect of the lost tier, not
  the cause. You cannot create difficulty by making a task long.

---

## 8. Recipe: a legitimate task that holds Opus 5 under 40

Stack the primary levers and let the guardrails prove it is fair.

1. Put 60 to 80 percent of the positive weight on weight-5 core-outcome checks
   (L1). Keep the total inside A3's 10 to 35 checks.
2. Make the core outcome a computation over a chain of at least three files
   where each step is only interpretable after the previous one (L3). Verify with
   DS-2: delete any one input directory and the task must become unsolvable.
3. Grade that core outcome on six to ten instances the agent never sees, each
   independently weighted, with the reference computed by the verifier from the
   published spec (L2).
4. Publish the full output contract in an agent-visible spec file: ordering, key
   names, rounding, serialization (L4, CL-5). Resist the temptation to hide it;
   the model fails these anyway and hidden conventions make the task invalid.
5. Add a trap tier at weight 3 where two rules interact (the `mode_bit_*` shape,
   92 to 96% failure) (L5).
6. Judge criteria: at least three demanding independent verification on a second
   instance, plus one honesty negative per figure the final reply will quote
   (L6, L7).
7. Prove it: oracle 1.000 five times, nop 0.000, stub low, owner-only oracle
   1.000, and DS-21 answered from agent-visible files only (L10, L11).

What to leave out: more input volume, more prose, more assertions over the same
value, hidden formatting conventions, and anything that depends on the agent
guessing an unconstrained constant (DS-21 fails that, correctly).

Expected shape of the result, from the corpus: plumbing and schema checks pass,
the weight-5 held-out tier is lost, tests land between 5 and 25, the judge half
between 25 and 45, final reward between 15 and 35. The seven tasks below 25 all
have this profile.

---

## 9. Method

Source: `Anubis_Tasks_Samples/Final_Delivery/*/trajectories/claude-opus-5/run_1/report.json`,
85 files, one run each.

Per-channel percentages as the harness computes them
(`scripts/rewardkit_results.py`, `scripts/judge_trajectory.py`):

- tests half `= max(0, sum(weight for passed positive checks) / sum(positive weights)) * 100`
- judge half `= (sum(weight for passed positive criteria) + sum(score for fired negatives)) / sum(positive weights) * 100`
- `final_reward = round((tests half + judge half) / 2, 2)`

Field semantics, confirmed by reproducing `rubric_weights_percentage` and
`test_weights_percentage` exactly for a sample task before any aggregation:

- positive check or criterion, `passed: true` means earned
- negative test check, `passed: true` means the cheat fired (penalty)
- negative judge criterion, `passed: false` means the criterion fired (penalty)

Themes in sections 3 and 4 are regex classifications over check names and
criterion text, and they overlap by construction. Raw counts per theme are given
alongside every rate so a different taxonomy can be checked against the same
denominators. Correlations are Pearson over the 85 tasks; with n = 85, anything
inside roughly plus or minus 0.21 is not distinguishable from zero at the 5
percent level, which is why section 7 treats the bulk-size features as noise and
reports heavy-weight share as the one lever with a real slope.
