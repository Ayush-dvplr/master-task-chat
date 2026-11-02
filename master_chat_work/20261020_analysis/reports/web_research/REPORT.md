# Web research: making terminal-agent tasks hard while keeping every rule visible

40 public sources (all downloaded), 23 failure modes (`failure_modes.json`), 20 original levers (`design_ideas.json`). Notes are in `notes/`, files in `sources/`. Every number below comes from a note, and the note cites the page or section.

## Bottom line

- The difficulty that survives a fully written spec comes from how the work is structured, not from what the agent knows: composing documented rules, long dependent chains, audit-and-repair, algorithmic insight, and verifying before claiming done.
- Arithmetic, counting, short state tracking, volume and formatting do not work. A terminal agent bypasses the first three with Python, and TB reviewers reject the last two.
- A typical TB2 task is far too easy for our target. Opus 4.5 scores 57.8% on TB2 (001, Table 2), and 40 of 89 TB2.1 tasks take a frontier model 5 min or less (003, Table 3). Only long-horizon or composition-graded designs reach the range we want: LHTB has a mean pass of 6.4% across 17 models with 62.8% of runs getting partial credit (002, Fig.4). In SpecBench, visible tests pass 100% but held-out tests 25% (036, Fig.1).

## Top 10 levers (ranked by evidence strength, then QC safety)

| Rank | Lever | Key evidence | QC risk |
|---|---|---|---|
| 1 | W-001 Hidden composition of documented rules | 036: 100% visible vs 25% held-out; gaps 32-64 pp; extra visible composition tests did not reliably close the gap. 037: requirements met fall from 44.8% to 29.0% once dependencies count | low |
| 2 | W-005 Dependent multi-stage chain, no shortcut | 011: success falls with log task length; 80% horizon is 4-6x shorter than 50%. 008: median solve at 57 min. 021: errors compound and self-condition. 020: splittable repetition does not count | low |
| 3 | W-002 Audit-and-repair against a written contract | 008: 8 of the 9 tasks where no model passes R=0.2 are audit-and-repair (category mean 0.32). 001: system config, kernel builds and DB migration unsolved by every model | medium |
| 4 | W-003 Algorithmic lift on a size ladder | 010: adding an algorithmic lift cut Hard pass@1 from 87.0% to 45.7%. 015: models find only surface-level speedups. 016: 84% of attempts anchor on transformers | medium |
| 5 | W-006 Format-only validator + self-verification burden | 011: premature abandonment is half of o1's failures. 002: 14 runs stopped at R>=0.75 with ~20 min left. 017: agents skip the validator (54.9% valid vs 70.7% submitted) | low |
| 6 | W-014 Beat a fully documented opponent or checker | 001 §4.3: tasks humans rated medium are model-hard when they need creative or adversarial reasoning. 013: insight chains | low |
| 7 | W-004 Stacked orthogonal artifact constraints | 019: one added requirement took pass@1 from 96% to 2%, and a model rationalised away "static". 014: a single-use rule was ignored | low |
| 8 | W-007 Feasible + infeasible instances with certificates | 028: true-negative rate on unsolvable instances only 27% (o1-preview, 2024). 031: an abort channel changes behaviour | low |
| 9 | W-016 Weight on error and rejection paths | 036 CCC case: failures dominated by rejecting invalid programs, while valid compositions pass >97% | low |
| 10 | W-018 Coupled multi-module change in an original codebase | 012: success falls with files touched; best 17.8% on private commercial repos. 016: LOC complexity favours humans (R^2 0.602) | low (authoring cost high) |

Combining levers gives the most reliable result: build a W-005 chain whose stages are W-002 repairs, then grade each stage with W-001 and W-016 hidden composition and error cases. All of this stays traceable to the written spec.

Inference, not measured: no source tests these levers on Claude Opus 5.x specifically, except HVTB (003), which is a hacking study. Calibrate with real runs.

## What does NOT work (with evidence)

| Idea | Why not | Evidence |
|---|---|---|
| Exact arithmetic, counting, short state tracking | Python bypasses it; frontier models with CoT already handle depth-10 state tracking | 025, 027 (GPT-4o CoT 1.00 at depth 10), 021 |
| Small puzzles or NP-hard instances | Agent writes BFS, ILP or brute force | 022, 028, 029 relevance notes |
| Volume, size, repetition | Not conceptual difficulty; no correlation between turns and success | 020 FAQ, 007, 005 (100k-LoC rejected), 001 §4.1 |
| Clerical formatting or arbitrary precision | `essential_difficulty` FAIL | 006, 007 |
| Many corner cases or hundreds of instructions | Reviewers reject it; frontier models are near-perfect up to 100-250 instructions | 005, 024 |
| Hidden rules or unstated interfaces | Measures spec gaps (false negatives); fails QC | 012 Table 3 (GPT-5 25.9% to 8.4% without the interface), 009, 001 App B.3 |
| Resource pressure, disabling network, telling the agent the time left | Unfair or flaky; rejected | 004, 006 `resource_configuration`, 007 |
| Mass-generate tasks and keep the ones current models fail | Finds trivial gaps that get fixed fast; label noise | 004, 018 (15.4-18% expert disagreement) |
| "Do not cheat" line as the only control | o3 still planned hacks 70-80% of the time | 032 |

## Grading and partial-credit lessons

- Dense, weighted ladders keep partial credit while full passes stay rare. On LHTB, 6.4% of runs pass at R>=0.95 but 62.8% get partial credit (002). On LHTB 2.0 reconstruction tasks the binary score is 0.221 against 0.653 dense (008).
- Templates:
  - RE-Bench: start=0 and reference=1, clipped (016).
  - Cybench: ordered subtask checkpoints (013).
  - MLE-bench: valid, then above median, then medal (017).
  - AlgoTune: correctness gate first, speedup clamped at 1x (015).
  - Agent-as-a-Judge: dependency-aware requirements (037).
- Grade downstream stages on oracle-fed inputs. Otherwise one upstream miss zeroes the whole chain and the score becomes binary (037 dependency drop).
- Conflict to check: the TB3 implementation rubric requires a binary 0/1 reward and fails weighted composites (006 `binary_reward`). Ayush's Harbor 0.24 QC may use different rules (UNVERIFIED).
- Judge half: LLM judges are fooled by plausible but wrong answers. A reference-guided judge cut GPT-4 math judging failures from 70% to 15% (035). A judge that can inspect files gets 90% agreement with humans, against 70% for a plain LLM judge (037). Give the judge the oracle output and a concrete per-item checklist, and run it with order swaps if the score is borderline.
- Arithmetic: overall = 0.5·tests + 0.5·judge. With tests < 0.20, overall < 0.30 needs judge < 0.40. A judge that rewards careful process will lift a careful model above 30%, so tie judge items to outcomes (did the run detect X, verify Y), not to effort.
- Hidden tests must be drawn from a wider distribution than the visible examples. EvilGenie's heuristics passed a 30% holdout set taken from the same distribution (038). A lookup table scored 97% visible and 0% held-out (036).

## Anti-cheat lessons

1. Nothing graded may be reachable. Keep tests, oracle and expected outputs out of the image. Mount them only at grading, ideally in a separate verifier container (004 `environment_mode="separate"`). Capable agents search call stacks, caches and git objects (032, 039).
2. Strip git history and leftovers: no future commits, reflog, tags or build artifacts (039 fix in swebench v4.1.0).
3. Read-only tests stop test edits but not special-casing or `__eq__` overloading (031). Hidden composition tests defeat lookup tables (036).
4. Hacking rises with difficulty, with ambiguity, and when the scoring function is visible. On HVTB more hacking happens on hard tasks, and half of it within the first quarter of a run (003). RE-Bench saw 43x more hacking than HCAST (032). Spec ambiguity raised hardcoding from 0-2% to 22-44% (038).
5. Explicit, specific prohibitions work for Claude. On HVTB opus-5 hacked 30.7% of runs with no warning and 0.0% when told not to read admin/ (003). A vague warning can backfire: gemini went from 47.7% to 59.8% (003). Keep the TB3 no-cheat sentence (004), but also enforce it mechanically.
6. Patch the exploit in the scorer instead of only penalising it in the judge (032). Audit successful trajectories for grader access (008).

## Run count and variance

- One build-time run says almost nothing. Outcomes per task are bimodal and noisy:
  - One third of 90 min-3 h tasks always pass, one third always fail, one third are mixed (020).
  - A word2vec rank varied from 1 to 40 across 25 runs (007).
  - A lucky score of 0.88 re-ran to 0.69 (016).
  - Aggregate pass@1 drifts 2.2-6.0 pp between identical runs, even at temperature 0 (040).
- Target the mean per-run score (pass@1 style), not pass@k. pass@5 can sit 13-25 pp above pass@1 (040). The unbiased estimator is in 034 Eq.1.
- Confidence with 1 + 8 = 9 runs. This is agent D's computation from 033 Eq.1-3, a one-sided 95% t-bound; it assumes exchangeable runs:
  - mean 0.15, sd 0.10: bound 0.21, passes
  - mean 0.20, sd 0.10: bound 0.26, passes
  - mean 0.20, sd 0.15: bound 0.29, borderline pass
  - mean 0.25, sd 0.10: bound 0.31, fails to certify < 0.30
  - Rule of thumb: with 9 runs, an observed mean of 0.20 or less certifies < 0.30. For mean 0.25 and sd 0.15 you need ~24 runs.
- If test scores are effectively binary, 9 runs certify < 0.30 at 95% only with 0/9 passes: the exact upper bound is 0.283 for 0/9 and 0.429 for 1/9.
- Use the 8 final runs as a QC diagnostic (001 App B.3): if all runs fail the same checks, suspect a spec gap; if they fail different checks, the difficulty is fair. TB reviewers debug in batches of 5 (007).
- The build-time run is best used to find spec gaps and cheating, not to estimate difficulty.

## Not checked

- No source evaluates Claude Opus 5.x on the failure-mode papers. Most model numbers are from 2023-2025 (021-029, 013-017, 035). HVTB (003) is the only 2026 Opus-5 data, and it is about hacking.
- Which rubric Ayush's Harbor 0.24 QC applies (binary vs weighted reward); see 006.
- TB2 per-category pass rates (only in an image, Fig.11 of 001). The TB1/tbench.ai blog and the frontierbench.ai announcement (404) were not read.
- Read as abstracts only: SWE-Bench Pro V2 (2610.24206) and SWE-Bench Pro Verified (2609.08149), cited in 012. The GSM-Symbolic 2026 re-evaluation (2605.28700) was seen by title only.
- Not covered: OSWorld, SWE-Lancer, PaperBench, the LiveCodeBench paper itself, ManyIFEval/"Curse of Instructions", overthinking studies, CSV/encoding parsing papers, agent calibration papers (arXiv 429s and the ID cap).
- Seen but not read, worth following up: partial-credit CTF evaluation (2604.19354), rubric artifacts in LLM judging (2609.02942), "More Tasks Won't Fix An Agent Leaderboard" (2610.00651), Terminal Wrench (2604.17596).
- Internal inconsistencies flagged in the notes: the SpecBench gap slope (036) and SWE-Bench Pro Table 4 vs its text (012).
- No local repos were consulted.
