# Paste-ready external research prompts

Each numbered block is independent. Paste one block at a time. These are research requests, not findings; the research service must verify its own sources.

## 1. ChatGPT Deep Research — published coding-agent failure evidence

```text
Goal: Identify task-design mechanisms, backed by published 2025-2026 evidence, that cause frontier coding agents to make substantive, testable mistakes.

Context: We build fair terminal-agent tasks. An agent receives a Linux environment, Python 3 standard library, input files, and a complete written contract. It repairs or writes a reusable program and emits exact outputs. Deterministic tests rerun it on fresh hidden inputs; a separate LLM judge evaluates documented verification behavior. The final score averages those two channels. Every graded rule and invocation detail must be stated in shipped documents. We seek a valid but wrong output from a strong agent, while a careful expert can solve the task. We already know that generic hidden reruns, small stated-rule puzzles, obvious algorithm hints, formatting trivia, and time pressure alone are weak; hidden-instance weight and demanding verification have been more promising.

Questions:
1. Which 2025-2026 primary benchmark papers, official technical reports, or released evaluation artifacts reveal concrete failure modes of top coding agents on repository repair, program synthesis, long-horizon tool use, or testing? Separate observed results from authors' interpretations.
2. For each failure mode, show the closest fair task lever: what visible contract and input family would elicit the mistake, and what hidden test would deterministically distinguish it from a correct solution?
3. What evidence says the failure survives a strong agent's self-tests, including constructed examples and reruns? What evidence says it does not?
4. Identify at least three attractive ideas the evidence contradicts or does not support. Highlight contamination, benchmark leakage, grader errors, model-version drift, and small sample size.
5. Rank 5-10 candidate levers by strength of direct evidence, expected test-weight impact, and cost of implementation. Give a falsifiable pilot for each.

Required output: First give a source ledger with title, authors/organization, publication date, direct URL or DOI, model/version, evaluation setup, sample size, and exact figure/table/section supporting each claim. Then provide a table with columns: lever | mechanism | why frontier agents fail it | how to grade it deterministically | cost to build | sources | evidence strength | first blind pilot | known counterexample or validity risk. Finish with a short prioritized list and open questions. Cite the source next to every empirical claim. Use primary sources where possible. Mark conjectures INFERRED and inaccessible or unverifiable claims UNVERIFIED; do not invent citations or imply 2026 coverage if none is available.
```

## 2. Gemini Deep Research — hidden-instance designs that resist memorized heuristics

```text
Goal: Find original, implementable task designs whose deterministic hidden instances defeat a plausible memorized or generic coding heuristic, without using secret rules.

Context: A frontier terminal agent gets Python 3 standard library, shipped files, and a complete contract. It must write a reusable program and exact outputs within a stated resource envelope. Hidden tests generate fresh instances inside the documented domain and run that same program. All rule branches, output conventions, tie-breaks, command flags, and runtime limits must be stated in shipped documents. The intended failure is a valid but wrong result on hidden instances; a hidden-scale timeout or crash is acceptable only if shipped inputs are fast, the limit is stated, and the loss is isolated to those checks. We already know that plain knapsack/shortest-path examples, small stated-rule mixes, raw data volume, and a mere hidden rerun often fail to create difficulty. We want mechanisms that a competent human can solve with the standard library and that a verifier can run safely.

Questions:
1. Propose 8-12 concrete program-repair, stateful processing, data-transform, or constrained-optimization task families. For each, name the plausible wrong heuristic and the exact boundary where it diverges from the correct algorithm; avoid merely relabeling textbook puzzles.
2. Give a minimal shipped instance, one hidden counterexample, a full visible contract excerpt for the deciding rule, and a correct reference algorithm at pseudocode level. Explain why the counterexample is within the stated domain and why output is unique.
3. Specify a seeded hidden generator with independent seed families, a second independent oracle/check, branch-coverage assertions, and the exact observable and test weight for each family. Explain how it prevents a program from baking in shipped values.
4. Estimate reference and plausible-solver runtime and memory across size tiers. State what must be measured before setting a verifier limit, with at least a 3x oracle-time margin and worst-case verifier work below 90% of its limit.
5. Describe a cheap design-stage blind: a fresh agent sees only the contract and small shipped sample; compare its program against three hidden seeds and a strong generic solver. State the rejection criterion if either solves all cases.

Required output: A table with columns: lever | mechanism | why frontier agents fail it | how to grade it deterministically | cost to build | sources | plausible wrong program | hidden separating instance | fairness proof | runtime risk | blind-pilot decision. Follow it with one detailed, runnable-in-principle blueprint for the best two ideas. Cite primary papers or official benchmark artifacts for any empirical failure claim and sources for algorithms; label original proposals INFERRED. If a requested source cannot be checked, mark it UNVERIFIED. Do not claim that an agent will fail without a blind run.
```

## 3. Research — LLM-judge rubrics for real verification

```text
Goal: Design a fair LLM-judge rubric that rewards observable verification work and avoids paying twice for a deterministic test failure.

Context: A coding agent writes or repairs a program and supplies artifacts. Deterministic tests rerun it on fresh inputs and grade exact output values and behavior. An LLM judge can inspect the agent trajectory, final message, and delivered files. We need criteria for useful acts such as constructing an edge input, rerunning after a change, checking a result independently, testing a changed copy, and accurately reporting coverage. A criterion must describe one observable act and a requirement it serves; the reference solution must demonstrate it. Deterministic artifact behavior belongs in tests. We already have a probe-heavy rubric and want independent evidence and better calibration, not a list of superficial process rituals.

Questions:
1. What 2025-2026 primary research or official evaluation guidance supports or challenges trajectory-based verification rubrics? What is known about judge reliability, position bias, verbosity bias, reward hacking, and disagreement with ground-truth tests?
2. Propose 10-15 single-act criteria that make an agent more likely to catch a real bug. For each, specify observable proof in a tool log and the defect class it can reveal. Include at least three checks that test a fresh or perturbed input.
3. Give a test-versus-judge ownership rule so one output mistake or one omitted act cannot be charged twice under different wording. Provide three concrete overlap examples and corrected criteria.
4. Design honesty negatives for claiming a successful rerun after the last edit without evidence, reporting inflated coverage, or quoting a delivered figure incorrectly. State guardrails against false positives and show how a truthful but failed run should score.
5. Propose a calibration study: blinded judge scoring, two independent raters, disagreement adjudication, oracle trajectory controls, ablations of criteria, and correlation with hidden-test correctness. Define a go/no-go threshold before adopting a new criterion.

Required output: A table with columns: lever | mechanism | why frontier agents fail it | how to grade it deterministically | cost to build | sources | trajectory evidence | test overlap check | false-positive risk. Add example criterion wording, a criterion-to-requirement map, calibration protocol, and cited source ledger. Distinguish empirical evidence from proposed rubric design. Cite direct sources for every measured claim; mark proposals INFERRED and unavailable claims UNVERIFIED.
```

## 4. Research — reduce token and elapsed-time cost without quality loss

```text
Goal: Find measurable ways to reduce total agent tokens and wall time in a multi-stage coding-task pipeline while preserving task fairness and final quality.

Context: The pipeline chooses a task idea, builds a full contract/program/verifier, runs fresh blind solves, performs QC and fixes, freezes exact bytes, runs one paid frontier-agent probe, then diagnoses failures. It stores structured status and evidence across sessions. Costs arise from long context, repeated document reads, agent startup, waiting for handoffs, polling, QC rework, and paid probes. An accepted change must preserve the same rule coverage, independent verifier, blind validity, QC outcome, and score interpretation. We are interested in cheap gates before expensive work, concise state retrieval, caching only when inputs and rules are unchanged, and scheduling that reduces idle time. No paid experiment is authorized by this request.

Questions:
1. Find primary 2025-2026 evidence or official engineering measurements for context compression, retrieval, prompt caching, staged evaluation, incremental checks, test selection, and parallelism in coding-agent workflows. Report the measured workload, metric, and quality effect rather than generic tips.
2. For each candidate change, identify the exact pipeline step, data needed, an invalidation key, expected token/time saving, and a quality guardrail. Separate one-time setup cost from per-task savings.
3. Design a measurement plan comparing old versus new on the same task cohort: total tokens, model calls, wall time, idle time, QC rework, blind scores, and accepted final scores. Explain how to avoid selecting only easy tasks and how to handle score variance.
4. Which changes could damage quality by losing context, using stale QC rules, leaking a blind solution, skipping a meaningful test, or confusing a grader error with an agent error? Give a rollback signal for each.
5. Rank the safest three changes that require no new paid run, then the best changes that require a controlled pilot.

Required output: A table with columns: lever | mechanism | why frontier agents fail it (or pipeline failure it prevents) | how to grade it deterministically | cost to build | sources | measurable saving | quality guardrail | invalidation key | pilot design. Cite primary sources for measured savings; mark extrapolated savings INFERRED and unverified claims UNVERIFIED. Do not promise zero quality loss without a non-inferiority measurement.
```

## 5. Research — schedule parallel Docker workloads on one Mac

```text
Goal: Produce a safe, efficient scheduler design for independent Docker-based verifier, QC, build, and blind-solve jobs running on one Mac.

Context: A task pipeline may have multiple ready jobs but only one Mac running Docker Desktop. Jobs vary in CPU, memory, disk I/O, wall time, and critical-path priority. Some produce large logs or images. A Docker build or solver run can consume enough host resources to stall other work. Every job needs a resource cap and clear owner; the scheduler must avoid disturbing unrelated running jobs. We want to improve elapsed time and utilization without changing scores, test inputs, frozen bytes, or QC behavior. No local command execution is requested here; research only.

Questions:
1. Using current official Docker Desktop/macOS documentation and primary scheduling literature, distinguish container CPU/memory limits from the Docker VM's host footprint. Which resource and concurrency controls actually work on macOS, and what are their failure modes?
2. Propose an admission rule using observed peak RSS, CPU, I/O, wall time, and a reserve for the host and Docker VM. How should unknown-size jobs enter conservatively? How should it adapt after measurements?
3. Specify a dependency-aware queue with job classes, priorities, fairness/aging, locks for shared images or output directories, cancellation limited to owned children, and crash recovery. State how to prevent two jobs from writing the same task state.
4. Compare FIFO, shortest-remaining-processing-time, critical-path-first, and memory-aware backfilling on a small worked example. Show predicted makespan, host pressure, and starvation risk. Do not assume perfect runtime estimates.
5. Design read-only observability and a small dry-run/simulation pilot: what timestamps and resource samples to collect, what baseline period to compare, and what result proves improvement without score drift.

Required output: A table with columns: lever | mechanism | why frontier agents fail it (or scheduling failure it prevents) | how to grade it deterministically | cost to build | sources | required telemetry | host risk | rollback trigger. Include a one-page scheduling policy, pseudocode, worked queue example, and citations to official current Docker/macOS docs and primary research. Mark untested performance claims INFERRED and inaccessible platform claims UNVERIFIED. Never recommend killing unrelated processes.
```

## 6. Research — adversarial search for new fair difficulty levers

```text
Goal: Generate and filter genuinely new, testable difficulty levers for frontier terminal coding agents, then identify the few worth a blind pilot.

Context: An agent receives Linux, Python 3 standard library, visible input files, and a complete written contract; it repairs or writes a reusable program. Hidden seeded inputs rerun that program and exact documents are graded. A separate judge scores evidenced verification. Every graded rule, branch, output convention, tie-break, and invocation detail must be stated in shipped documents. Existing candidates include held-out hard instances, hidden-scale optimization, long stateful replay, exact whole-document grading, finite candidate search with a stated domain and decision rule, and trajectory verification probes. Local experience found that simple stated-rule traps, memorized textbook algorithms, generic hidden reruns, formatting trivia, and raw volume are weak. We seek strong agents' plausible valid-but-wrong outputs, not ambiguity, secret facts, or grader accidents.

Questions:
1. Propose at least 12 mechanisms that are distinct from the listed candidates. For each, write the smallest visible contract, the agent's likely wrong implementation, a hidden separating instance, and an expert reference approach using the Python standard library.
2. For each mechanism, identify the exact cause of failure: search approximation, state coupling, incomplete verification, authority resolution, model of an input format, or another mechanism. Explain why a strong agent might still fail after reading the contract and self-testing; cite evidence or mark this INFERRED.
3. Reject any proposal whose hardness depends on unstated semantics, undocumented data, a broken oracle, a hidden out-of-domain input, general resource exhaustion, or charging one wrong observable repeatedly. Explain why it fails.
4. Rank surviving ideas by expected hidden-test loss, authoring time, oracle complexity, QC risk, and transferability across domains. Give one cheap blind-design pilot for each top-five idea and a concrete criterion that would falsify it.
5. Highlight any idea with a source showing both a failure and a successful mitigation by a frontier agent. What would that imply for the hidden generator or task design?

Required output: A table with columns: lever | mechanism | why frontier agents fail it | how to grade it deterministically | cost to build | sources | visible rule | hidden counterexample | reference approach | validity risk | blind rejection rule. Then give a rejected-ideas table and the top-five pilot sequence. Cite primary sources for empirical claims; label original hypotheses INFERRED and unverifiable claims UNVERIFIED. Do not treat a proposed lever as proven until a fresh blind agent fails it on valid hidden cases.
```
