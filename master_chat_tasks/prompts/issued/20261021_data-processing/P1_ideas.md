# P1 ideas, batch 20261021_data-processing (issued 21 Oct 2026 12:24 IST, from template P1 v1)

Paste ONLY the part below `=== PASTE BELOW ===` into ChatGPT (high reasoning). Bring the full reply back to the master chat; I gate every idea and record it in `registry/ideas.jsonl`.

Fill notes (master): N_IDEAS = 5 (Ayush gave no count; my default). Generator category key for the build: `data-processing`. Trial lessons applied here (pending review): district-heat leak pattern listed as leaked; emberforge's 100% reviewer score and a suspected labelled reference file listed as leaked patterns.

=== PASTE BELOW ===

You are designing original, very hard but fair tasks for a terminal-agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container, a folder of input files and a written instruction, has two hours, and must produce exact output files. Hidden tests then run its delivered program again on fresh inputs it never saw and compare outputs field by field. A separate reviewer reads its work log.

Target: a careful, competent agent should earn only 10 to 20 percent of the test points, while partial credit stays possible (each check is independent and weighted).

Domain for this batch: Data processing (data engineering and ETL: ingesting, normalising, reconciling and reporting on many messy but fully specified feeds).
Number of ideas: 5 (give exactly this many, each a genuinely different mechanism, not a renamed scenario).

## The fixed frame (non-negotiable)
1. Every rule the tests grade must be written in the instruction or in a shipped specification file. No hidden rules, secret constants, undocumented tie-breaks or required network facts. A rule may be long, but it must be stated.
2. Difficulty must come from the structure of the work, not from secrecy. What reliably defeats careful agents, by evidence:
   - A. Hidden composition: each rule is documented, but the hidden inputs combine several rules in one record or case, so rules interact in ways no single visible example shows.
   - B. Dependent chain: four or more stages, each needing the exact output of the previous one (for example parse, then reconcile, then allocate, then report). Later stages are graded on correct inputs supplied by the tests, so one early slip does not zero everything.
   - C. Audit-and-repair: a provided component or pipeline is broken in several quiet ways against a written contract.
   - D. Size ladder: small instances are easy, the largest needs an algorithmic idea (brute force is too slow within the stated limits).
   - E. Stacked orthogonal constraints on the same output that pull against habit.
   - F. Rejection paths: some inputs must be refused with a stated error, and that is weighted heavily.
   Every idea must use A and B, plus one or two of C to F, plus NEW levers of your own (see below).
3. What does NOT work, so do not use it: sheer data volume, plain arithmetic or counting (the agent writes Python), small puzzles or textbook NP-hard instances (the agent writes a solver), formatting trivia, hundreds of corner cases, resource or time pressure, disabling the network, or any hidden or ambiguous rule.
4. The agent builds one reusable program plus a fixed set of output files. Choose ONE archetype per idea from this list; its output files are fixed and cannot change:
- build-repair: repair a zipped Python package that does not build or behaves wrongly, ship the fixed package plus JSON reports. Fixed outputs: out/package.zip, out/selftest.json, out/build_report.json, out/module_core.json, out/module_metrics.json, out/dependency_resolution.json, out/summary.json. At least 6 input files.
- cli-config: repair a zipped command-line tool, run it to produce a resolved configuration, profiles and a validation report. Fixed outputs: out/config.json, out/report.json, out/tool.zip, out/profile_dev.json, out/profile_prod.json, out/validation_report.json, out/summary.json. At least 6 input files.
- data-pipeline: write a reusable transform program that normalises many input feeds into one record stream plus summary, quality and per-group (5 regions: central, east, north, south, west; 4 segments: consumer, corporate, enterprise, smb) reports. Fixed outputs: out/transform.py, out/normalized.jsonl, out/summary.json, out/data_quality.json, out/product_summary.json, out/region_central.json, out/region_east.json, out/region_north.json, out/region_south.json, out/region_west.json, out/segment_consumer.json, out/segment_corporate.json, out/segment_enterprise.json, out/segment_smb.json. At least 10 input files.
- domain-calculation: write a reusable program that derives an exact domain report from many inputs: summary, policy audit, data quality, 4 region (North, South, West, East) and 2 segment (commercial, public) reports. Fixed outputs: out/derive_report.py, out/summary.json, out/policy_audit.json, out/data_quality.json, out/region_North.json, out/region_South.json, out/region_West.json, out/region_East.json, out/segment_commercial.json, out/segment_public.json. At least 10 input files.
- format-recovery: write a decoder and a byte-exact encoder for a documented container format, plus decoded examples and analysis reports. Fixed outputs: decode.py, encode.py, out/decoded_examples.jsonl, out/format_report.json, out/roundtrip_report.json, out/error_analysis.json. At least 6 input files.
- performance: write an optimised single-pass aggregation program that must beat a stated speed ratio, plus 5 scenario reports and analysis files. Fixed outputs: out/optimize.py, out/scenario_visible.json, out/scenario_peak.json, out/scenario_steady.json, out/scenario_burst.json, out/scenario_latency.json, out/perf_report.json, out/bottleneck_analysis.json, out/recommendations.json, out/data_quality.json. At least 10 input files.
- repo-patch: repair a zipped multi-layer repository against failing behaviour, ship the patched repo plus repair and per-module reports. Fixed outputs: out/patched-repo.zip, out/repair-report.json, out/module_core.json, out/module_parser.json, out/module_report.json, out/test_fixes.json, out/summary.json. At least 6 input files.
- service-interaction: start a provided local service simulator, drive it through its CLI and HTTP API to reach a required end state, report the final state and transcripts. Fixed outputs: out/final_state.json, out/report.json, out/scenario_alpha.json, out/scenario_beta.json, out/scenario_mode.json, out/transcript_summary.json, out/summary.json. At least 6 input files.
5. Inputs: at least 10 flat files in at least 5 different formats readable by the Python standard library (csv, tsv, jsonl, json, xml, ini, fixed-width text, sqlite, gzip, zip, log). The files must be chained (a value in one file is needed to interpret another), and every file must matter to a graded result. Size: large enough to need a program, but size is not the difficulty.
6. Exact deterministic outputs only (integers or fixed decimal strings with stated rounding). No floating tolerance.

## What has been learned so far (use it)
Levers that held against real agents: none measured yet.

Levers that leaked (agents solved them; do not reuse as the main difficulty):
- A single documented rule written once, far from where it is used: a status precedence chain in a Conventions section; a tie-break where the greatest id tuple wins; a cap applied after an uplift, min(base + uplift, cap); largest-remainder rounding with equal remainders broken by descending id; quantising each value when first derived instead of at the end. A careful agent read and implemented every one of these (independent reviewer rated the task 3 out of 10; at build time a solver that got only the first rule right scored 0.92, and an all-lazy solver 0.59). Lesson: a rule that is merely placed far away or easy to overlook is NOT hard. It must interact with other rules on hidden cases.
- Shipping a worked reference or calibration answer file next to the inputs (suspected, under review): the agent can fit its rules to the expected outputs instead of reasoning from the spec. Do not ship any file that contains expected outputs.
- Reviewer statements that any reasonable run satisfies: in a real run every reviewer statement passed (100%) while tests were 68%. Reviewer statements must be about concrete facts the agent reports, which a typical run can genuinely get wrong or omit.

Settings already used (do not reuse):
- district heat network flexibility procurement (offers, uplift caps, credits by region)
- live-service crafting-game season settlement (smith identity, recipe editions, scarcity caps, vault floors, requisition allocation)

Recent archetype and lever mixes (your mix must differ from each):
- domain-calculation + district heat procurement + the five "rule written far from use" levers above (precedence chain, tuple tie-break, cap after uplift, largest remainder, early quantisation)
- custom report set (domain-calculation style) + crafting-season settlement + withheld parameter recovered from a calibration slice, identity canonicalisation, governing-edition resolution, stable assignment under interacting caps and floors, allocation, reconciliation
Prefer an archetype other than domain-calculation in at least four of the five ideas.

## New levers
Each idea must introduce several new levers that are not in the A to F list and not in the lists above. A lever is a documented rule or structure plus the specific way a careful agent gets it wrong. Only if an idea truly cannot carry more than one new lever, say why.

## Return format: for each idea, exactly these fields, in this order
1. Title and one-sentence pitch.
2. Setting: who uses this and why the output matters (a realistic professional context, not a game).
3. Archetype (from the list) and how the fixed output files map to the task.
4. Deliverable program: what it reads, what it writes, what it must handle on fresh inputs.
5. Input files: name, format, approximate rows, what each holds, and which other file it depends on. Show at least three dependency chains of length four or more.
6. Spine: the stages of the dependent chain (lever B), and which stage outputs the tests check on supplied correct inputs.
7. Levers. For each lever, including A, B, the chosen C to F, and every new lever:
   a. name (mark NEW or STANDARD),
   b. the rule as it will be written, and where (instruction or which spec file),
   c. what a careful but hurried agent will most likely do instead (the reflex reading),
   d. a constructed hidden case where the reflex reading changes the output, and which fields change,
   e. why the shipped sample data does NOT reveal the reflex error (the agent cannot confirm the rule by checking the samples),
   f. whether it is independent of the other levers (independent levers give finer partial credit).
8. Rejection paths: which inputs must be refused and the exact stated error.
9. Partial-credit plan: roughly 40 to 70 independent checks, grouped by lever, with which ones are heavy.
10. Reviewer checks on the work log: 10 to 20 statements about what the agent says or reports (for example "the agent reports which records it rejected and the stated reason"). Each must be true for any correct solution, must not repeat what a test already checks, and must not reward effort alone.
11. Shortcuts and cheats an agent might try (hardcoding sample answers, keying on file names, reading files it should not), and how the design blocks each.
12. Expected scores: what a lazy agent, a careful agent and a perfect agent would each earn on tests, with a one-line reason per lever.
13. Nearest known benchmark task or textbook problem, and exactly how this idea differs.
14. Solvability argument: why an expert with the instruction and files can reach 100 percent in two hours.
15. Biggest risk to the idea (fairness, ambiguity, or a lever that might leak).

Rules for your answer: no implementation code, no generated data, no test answers. Do not rank the ideas or pick a winner. Do not reuse a setting or a lever mix from the lists above.
