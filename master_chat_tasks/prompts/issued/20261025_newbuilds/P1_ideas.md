# P1 ChatGPT idea prompt, template v2 (25 Oct 2026)

Replaces v1 (21 Oct). Why: measured results 21-25 Oct. Every lever that is a stated rule (habit levers H1-H7, recursive shares, chains, stateful keys, evidence induction L11) was read and transliterated by Opus: tests 98-100 on sentinel, sensor, district, caldermoor, metered, config, cohort, schema, tariff. The only two tasks that held were dispatch-plan-reoptimization (tests 35.64: the exact optimum on 4 hidden instance sets was missed) and match-replay-desync-audit (tests 46.88: stateful replay with divergence). So v2 asks for difficulty that survives a perfect reading of every rule: computation, not interpretation. Rules follow `knowledge/LEVER_RULES_v2.md` (no silence, no announcing the traps, IN-17; exactness stated, G5).

How the master chat uses this file: copy it to `prompts/issued/<batch>/P1_ideas.md`, fill every `[[...]]`, give Ayush the link. Ayush pastes ONLY the part below `=== PASTE BELOW ===` into ChatGPT (highest reasoning), and pastes the reply back. The master chat gates every idea (uniqueness, QC risk, LEVER_RULES_v2) and records each in `registry/ideas.jsonl`.

=== PASTE BELOW ===

You are designing original, very hard but fair tasks for a terminal-agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 (standard library only), a folder of input files and a written instruction. It has two hours. It must deliver a reusable program plus exact output files. Hidden tests then run its program on fresh inputs it never saw and compare each output document whole and exactly. A separate reviewer reads its work log.

Target: a careful, competent agent earns 20 to 50 percent of the test points. Partial credit must stay possible (independent weighted checks).

Domain for this batch: two domains, three ideas each. (a) Operations research: exact combinatorial optimisation (scheduling, rostering, routing, packing, network design) in a realistic business setting. (b) Systems: exact replay, recovery or consistency computation over long event logs (storage-engine recovery, replicated logs, version histories, build or dependency graphs), where the answer needs carefully maintained incremental state or an exact search, not just parsing.
Number of ideas: 6 (3 for domain a, 3 for domain b) (each a genuinely different computational core, not a renamed scenario).

## What we measured (this is the most important section)
This agent reads specifications perfectly. For every rule written in the instruction or a spec file, it writes the rule as code, builds its own test fixture for it, and gets it right. We have tried, and it beat every one of these:
- habit traps (a rule that differs from the usual convention: rounding mode, calendar month vs 30 days, inclusive vs exclusive bounds, tier position per account vs per period);
- recursive or re-shared allocations, multi-stage dependent chains, stateful keys wider than the obvious key;
- rules to be inferred from data patterns (if the wrong guess crashes, the crash tells the agent the answer);
- many interacting documented rules in one record.
All of these scored 98 to 100 percent.

What held: two tasks where understanding the rules was not enough.
1. An optimisation task: the program had to reach the exact optimum of a stated objective on fresh hidden instances. The agent wrote a sound solver, but its search stopped at a good, non-optimal plan. It lost about 65 percent of the test points, and every hidden instance set failed.
2. A replay task: rebuild state by replaying a long event log under documented semantics, find where two replicas diverged, and report the first divergence. Errors carried through the state, so it lost about 53 percent.

So the difficulty must come from computation the agent cannot shortcut: an exact optimum or exact answer that needs a real algorithmic idea (decomposition, a dominance argument, a dynamic programme over the right state, an exact search with strong bounds, or careful incremental state). Greedy, local search, a time-limited solver or a plain LP relaxation must give a plausible answer that is wrong on the hidden instances. Nothing may depend on reading the rules wrongly.

## The fixed frame (non-negotiable)
1. Every rule the tests grade is written in the instruction or a shipped spec file, with exactly one reading. No hidden rules, no secret constants, no unstated tie-breaks, no network facts. Ties in an optimum are broken by a stated total order, so the expected output is unique.
2. The instruction states that each output document is graded whole on fresh inputs and only an exact match counts.
3. The instruction must not point at the difficulty. No sentences such as "beware", "note that greedy fails", "the hard part is", and no list of the traps.
4. The shipped sample instances must be solvable by the naive method (so self-checking on samples reveals nothing). The hidden instances are the same distribution at a larger size or with denser structure, still within a stated size limit, where the naive method is wrong (not merely slow). State the size limits and a runtime limit per instance (for example 60 s) that an exact method meets with margin.
5. The answer must be checkable: the tests know the true optimum (computed offline by the task author with an exact method) and also verify feasibility of whatever the agent outputs, so a feasible but non-optimal plan earns the feasibility checks but not the optimum checks.
6. Do NOT use: textbook puzzles the agent recognises and solves with a known library call (sudoku, n-queens, plain knapsack, plain shortest path, plain max-flow); data volume; plain arithmetic; formatting trivia; hundreds of corner cases; resource pressure; disabling the network; floating tolerance. Third-party solvers are not installed and must not be needed.
7. One archetype per idea from this list; its output files are fixed:
- build-repair: repair a zipped Python package that does not build or behaves wrongly, ship the fixed package plus JSON reports. Fixed outputs: out/package.zip, out/selftest.json, out/build_report.json, out/module_core.json, out/module_metrics.json, out/dependency_resolution.json, out/summary.json. At least 6 input files.
- cli-config: repair a zipped command-line tool, run it to produce a resolved configuration, profiles and a validation report. Fixed outputs: out/config.json, out/report.json, out/tool.zip, out/profile_dev.json, out/profile_prod.json, out/validation_report.json, out/summary.json. At least 6 input files.
- data-pipeline: write a reusable transform program that normalises many input feeds into one record stream plus summary, quality and per-group (5 regions, 4 segments) reports. Fixed outputs: out/transform.py, out/normalized.jsonl, out/summary.json, out/data_quality.json, out/product_summary.json, out/region_central.json, out/region_east.json, out/region_north.json, out/region_south.json, out/region_west.json, out/segment_consumer.json, out/segment_corporate.json, out/segment_enterprise.json, out/segment_smb.json. At least 10 input files.
- domain-calculation: write a reusable program that derives an exact domain report from many inputs: summary, policy audit, data quality, 4 region and 2 segment reports. Fixed outputs: out/derive_report.py, out/summary.json, out/policy_audit.json, out/data_quality.json, out/region_North.json, out/region_South.json, out/region_West.json, out/region_East.json, out/segment_commercial.json, out/segment_public.json. At least 10 input files.
- format-recovery: write a decoder and a byte-exact encoder for a documented container format, plus decoded examples and analysis reports. Fixed outputs: decode.py, encode.py, out/decoded_examples.jsonl, out/format_report.json, out/roundtrip_report.json, out/error_analysis.json. At least 6 input files.
- performance: write an optimised single-pass aggregation program that must beat a stated speed ratio, plus 5 scenario reports and analysis files. Fixed outputs: out/optimize.py, out/scenario_visible.json, out/scenario_peak.json, out/scenario_steady.json, out/scenario_burst.json, out/scenario_latency.json, out/perf_report.json, out/bottleneck_analysis.json, out/recommendations.json, out/data_quality.json. At least 10 input files.
- repo-patch: repair a zipped multi-layer repository against failing behaviour, ship the patched repo plus repair and per-module reports. Fixed outputs: out/patched-repo.zip, out/repair-report.json, out/module_core.json, out/module_parser.json, out/module_report.json, out/test_fixes.json, out/summary.json. At least 6 input files.
- service-interaction: start a provided local service simulator, drive it through its CLI and HTTP API to reach a required end state, report the final state and transcripts. Fixed outputs: out/final_state.json, out/report.json, out/scenario_alpha.json, out/scenario_beta.json, out/scenario_mode.json, out/transcript_summary.json, out/summary.json. At least 6 input files.
8. Inputs: at least 6 to 10 flat files (as the archetype says) in at least 4 formats readable by the Python standard library. The files are chained (one is needed to interpret another) and every file matters to a graded result.
9. Exact deterministic outputs only (integers, or fixed decimal strings with a stated rounding rule).

## Already used (do not reuse a setting or core)
Settings: district heating flexibility procurement; game vault and loot settlement; vendor archive byte-exact recovery; database schema migration planning; customer cohort retention reconciliation; vehicle dispatch plan re-optimisation; sensor network least-squares adjustment; security sentinel policy recompute; multiplayer match replay desync audit; household commitment closure; metered usage rating; utility tariff engine repair; data product config compilation; season ladder settlement; numeric reduction benchmarks; renewable energy certificate settlement; speculative decoding verification.
Cores and mixes: dispatch: vehicle dispatch re-optimisation, exact min-cost objective over 4 hidden instance sets (HELD). match-replay: event-log replay of two replicas and first divergence (HELD). Leaked: rule-heavy domain-calculation and data-pipeline tasks built on habit traps, recursive shares, dependent chains, stateful keys; repo-patch and cli-config repairs against a written contract; format-recovery round trip; least-squares adjustment (closed form, solved exactly).

## Return format: for each idea, these fields in this order
1. Title and a one-sentence pitch.
2. Setting: who uses this professionally and why the exact answer matters.
3. Archetype and how its fixed output files map to the task.
4. The computational core: the exact problem in mathematical terms (decision variables, constraints, objective, total tie-break order), and the algorithmic idea an expert uses to solve the hidden sizes exactly in time.
5. Why the naive approaches fail: for greedy, local search, a time-limited search, and the most likely "smart" first attempt, say what plausible wrong answer each gives on a hidden instance and why the shipped samples do not expose it.
6. Instance design: sample sizes vs hidden sizes, the structure that makes naive methods miss (stated as a generator recipe), and why it is still the same stated distribution.
7. Input files: name, format, approximate rows, contents, and the files it depends on.
8. Checks: 30 to 60 independent weighted checks, grouped (feasibility, exact optimum per hidden instance, secondary reports, rejection paths), with the heavy ones marked.
9. Rejection paths: which inputs must be refused, with the exact stated error.
10. Reviewer checks: 10 to 15 statements about the work log that hold for any correct solution and do not repeat a test.
11. Shortcuts and cheats (hardcoding samples, keying on file names, emitting a feasible plan only) and how the design blocks each.
12. Expected scores: lazy, careful and expert agent on the tests, with a one-line reason each.
13. The nearest known benchmark task, contest problem or textbook problem, and exactly how this differs (it must not be solvable by recognising it).
14. A solvability argument: why an expert reaches 100 percent in two hours with the standard library.
15. The biggest risk (unfairness, a hidden tie, the naive method accidentally being exact, runtime).

Rules for your answer: no implementation code, no generated data, no test answers. Do not rank the ideas or pick a winner.
