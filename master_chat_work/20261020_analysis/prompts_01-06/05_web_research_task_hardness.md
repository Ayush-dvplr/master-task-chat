# Web research: how to make terminal-agent tasks hard (low harness score) while staying fair

You are a research analyst. Find, download and digest public papers and web pages on what makes agentic coding and terminal tasks hard for frontier models, then turn the findings into design ideas Ayush can use. You build no task.

## Paths (absolute)
- REPORT OUT: `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/reports/web_research/`
  - `sources/`: downloaded PDFs and saved HTML or markdown copies, one file per source, named `<NNN>_<short-slug>.<ext>`
  - `notes/`: one `<NNN>_<short-slug>.md` per source
- SCRATCH: `/tmp/web-research-hardness-<YYYYMMDDTHHMM>/`
- LOGS: `/tmp/opencode-logs/web-research-hardness-<YYYYMMDDTHHMM>/`

## Background
Ayush builds Terminal-Bench 2.0 style tasks for Harbor 0.24. Each task is a Docker environment with input files, an `instruction.md`, a reference solution, and pytest-style weighted checks (tests channel) plus an LLM judge rubric on the agent's trajectory. Final score = 0.5 tests + 0.5 judge. Target: a careful frontier model (Claude Opus class) scores under 0.20 on tests and under 30% overall, while partial credit still exists.

Hard constraint from QC: everything needed to solve the task must be stated in the visible files. Hidden or undocumented rules fail QC. A previous task documented every rule and a careful model passed it in 15 minutes (3/10 difficulty). So hardness must come from what the model does badly even when the rules are written down: exact computation, search beyond brute force, long chains of dependent steps, state tracking, messy but spec-legal inputs, precise spec following over long documents, numeric exactness, ties and ordering, verification discipline, time budgets and so on. Find evidence for which of these actually lower scores.

## Hard rules
1. Public sources only. Download only what is freely and legally available (arXiv, conference proceedings, official blogs, docs, GitHub READMEs). Respect robots and paywalls; for paywalled items save only the abstract and citation.
2. Never send any local file, code, task content, key or token to any website or service. Search queries describe topics only.
3. Never copy a benchmark task into a design idea. Ideas must be original; cite what each is inspired by and say how it differs.
4. Git and gh: read-only only. Never clone, pull, commit, push or open a PR on anything; read GitHub pages via the web or `gh api` GET. Allowed repos if you need local context: ShreeyankDoliya/Terminal_2.0_Harbor_Harness, ShreeyankDoliya/Anubis_Tasks_Samples, ayushsah-dev/beta-task-generator, ShreeyankDoliya/Finalized_Tasks_RFP. Read-only, and only if a finding needs it.
5. Every claim in a note cites the source and page or section. Numbers come from the source, never from memory. Unconfirmed means UNVERIFIED.
6. Downloads or batches that may run over about 4 minutes go `nohup ... > LOGS/<name>.log 2>&1 &`, polled with waits under 4 minutes. Do not end your turn while your own job runs.
7. Save each note as soon as it is written. Aim for 25 to 40 sources; stop when new sources stop adding new findings.

## Topics to cover (search each)
1. Terminal-Bench 2.0 and Terminal-Bench 1: paper, task design guidance, what failed, difficulty calibration, task quality review.
2. Harbor framework and frontier-bench task guidelines (harbor-framework on GitHub): what makes a good or hard task.
3. Other agentic benchmarks with hard tasks and failure analyses: SWE-bench Verified and Pro, SWE-Lancer, MLE-bench, RE-Bench, PaperBench, OSWorld, tau-bench, Cybench, CTF benchmarks, LiveCodeBench, Humanity's Last Exam (method only), METR task-length studies, AlgoTune, CompileBench.
4. Documented LLM failure modes: long-horizon error compounding, state tracking, exact arithmetic and counting, constraint satisfaction and search, combinatorial optimisation, spec following in long documents, instruction hierarchy, lazy defaults and premature stopping, self-verification failures, overconfidence, tie and ordering conventions, off-by-one and boundary errors, parsing edge cases (encodings, quoting, fixed-width, mixed formats).
5. Benchmark saturation and contamination: why tasks get solved, and what keeps them unsaturated.
6. Reward hacking and cheating by agents (reading tests, hardcoding outputs, editing graders) and how benchmarks block it.
7. Partial-credit and grading design: weighted checks, rubric or LLM-judge reliability, avoiding all-or-nothing scores.
8. Difficulty measurement: pass@k, how many runs are needed, variance between runs (Ayush runs 1 trajectory while building and 8 at final approval).

## Deliverables (in REPORT OUT)
1. `sources.json`: `[{"id":"001","title":"","authors":"","year":0,"url":"","type":"paper|blog|docs|repo|other","file":"sources/...","downloaded":true,"topics":[1,4]}]`
2. `notes/<NNN>_<slug>.md`: per source, at most 40 lines: what it is, key findings with numbers and section cites, what lowers scores, and relevance to our constraint (rules must be visible).
3. `failure_modes.json`: `[{"id":"F-001","mode":"","evidence":[{"source":"001","where":"","finding":""}],"strength":"strong|medium|weak","works_with_visible_rules":true,"how_to_use":""}]`
4. `design_ideas.json`: 15 to 30 original task-level levers, `[{"id":"W-001","lever":"","mechanism":"","why_models_fail":"","evidence":["F-001"],"qc_risk":"low|medium|high","qc_risk_note":"","partial_credit_design":"","grader_cost":"","not_copied_from":""}]`
5. `REPORT.md`: at most about 300 lines: top 10 levers ranked by evidence strength and QC safety, what does NOT work (with evidence), grading and anti-cheat lessons, run-count and variance guidance, and `## Not checked`.
6. `RUN_LOG.md`: searches and downloads, with failures.

## Done when
All six deliverables exist, every source in `sources.json` has a note and either a file or `downloaded:false` with the reason, the JSON parses (`python3 -m json.tool`), and SCRATCH is deleted. Final reply of at most 10 lines: source count, top 5 levers, and the strongest piece of evidence.
