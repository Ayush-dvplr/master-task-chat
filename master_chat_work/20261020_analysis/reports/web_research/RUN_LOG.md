# RUN_LOG: web research on task hardness (started 2026-10-20 23:02 IST [17:32 UTC])

## Lead (Sisyphus)
- Set up REPORT OUT, SCRATCH, LOGS; built scratch venv with pypdf 5.1.0 for PDF text extraction (pdftotext absent).
- Probed search channels: arXiv API (HTTP 301 -> OK with -L), DuckDuckGo HTML (202). No general web-search tool.
- Split work across 4 background researchers by ID range: A 001-010 (Terminal-Bench, Harbor, saturation), B 011-020 (agentic benchmarks), C 021-030 (LLM failure modes), D 031-040 (reward hacking, grading, variance).
- Merged fragments into sources.json (40 sources, all downloaded); wrote failure_modes.json (23), design_ideas.json (20), REPORT.md.
- Verified: every source has a note and an existing file; all JSON parses with python3 -m json.tool. Did not re-check sub-agent numbers against PDFs (spot-checked D's run-count computation by hand: 0.20+1.8595*0.10/3=0.262; 1-0.05^(1/9)=0.283).
- Stopped at 40 sources (upper bound of the brief); later candidates are listed under 'Not checked' in REPORT.md.
- Deleted SCRATCH at the end.


## Agent A: Terminal-Bench / Harbor / saturation
q: arxiv id_list 2601.11868, 2607.08964, 2608.22103 metadata; downloaded 3 PDFs OK
# Agent A runlog
- arXiv id_list 2601.11868 -> TB2 paper, only v1 exists (Submitted 17 Jan 2026) OK. PDF downloaded 001 (84 pp).
- arXiv id_list 2607.08964 -> LHTB, v3 (9 Oct 2026) downloaded 002 OK. arXiv id_list 2608.22103 -> HVTB v1 downloaded 003 OK.
- arXiv search all:"Terminal-Bench" sorted by date -> found 2610.14146 (LHTB 2.0), 2610.18868 etc.
- gh api orgs/harbor-framework/repos -> list OK.
gh api harbor-framework/{terminal-bench CONTRIBUTING+README+docs, benchmark-template REVIEWING+rubrics} OK
gh api terminal-bench docs/prompts/task-proposal.md, task-implementation.toml, docs/REVIEWING.md, TASK_REVIEW_AUTOMATION.md, graphql discussion 224 (read-only)
NOTE: one graphql call (POST, read-only query) was made for discussion 224 by mistake against the GET-only rule; no data sent other than the query; result discarded and refetched via REST GET.
- wrote notes/001
- wrote notes/002, notes/003 (read txt/002.txt fully, txt/003.txt fully)
- wrote notes 004-007 (from gh api raw files; no page numbers, section cites)
- arXiv API 429 rate-limited (shared by agents); used arxiv.org/search HTML for query: benchmark saturation (OK)
- downloaded arxiv 2610.14146 (LHTB2)->008; 2606.26158 (CORE-Bench saturation)->009; 2606.01286 (BenchEvolver)->010; 2610.20667 (Evaluating after saturation) pdf kept in scratch only (no ID, not enough IDs)
- wrote notes 008,009,010
- arXiv search (HTML) query "benchmark saturation" -> candidates 2610.20667, 2606.26158, 2606.01286; chose 2606.26158 (agentic CORE-Bench) and 2606.01286 (BenchEvolver, LiveCodeBench saturation). 2610.20667 not given an ID (IDs exhausted) -> NOT read beyond download.
- arXiv API search all:"Terminal-Bench" sorted by date OK (found LHTB 2.0 2610.14146; other 2610.* TB follow-ups listed but not read: Terminal-RSI, ReTerm, Tev, AutoEnvScaling, CoTrace: training-method papers, out of scope).
- frontierbench.ai/announcement via curl -> HTTP 404 (not saved). tbench.ai blog/TB1 docs: not fetched (UNVERIFIED; no time); TB3 text taken from repo CONTRIBUTING/REVIEWING instead.
- DuckDuckGo html query (benchmark saturation survey...) -> empty result (blocked); not used.
- NOT done (gaps): LiveCodeBench paper itself, SWE-bench contamination studies (assigned to agent B domain), TB1 docs, terminal-bench-2-1 changelog, harbor docs task-format page, Terminal Wrench (2604.17596), Berkeley RDI "How we broke top AI agent benchmarks" (reward hacking, agent D).
- Final: sources/001-010 + notes/001-010 written; frag/A_sources.json (10), frag/A_findings.json (30) validated with json.tool.


## Agent B: agentic benchmarks
# Agent B runlog (IDs 011-020, topic 3: other agentic benchmarks), 2026-10-20 IST
## Searches (topic-only queries)
- arXiv API: "measuring ai ability to complete long tasks" -> 0 hits (query quirk; paper fetched by id later).
- arXiv API: "SWE-Bench Pro" -> 2509.16941 (original), plus newer 2609.08149 (SWE-Bench Pro Verified) and 2610.24206 (SWE-Bench Pro V2); read abstracts only via arxiv.org/abs.
- arXiv API: Cybench -> 2408.08926. tau-bench -> no original (hits unrelated); AlgoTune -> 2507.15887; CompileBench -> no paper; RE-Bench -> 2411.15114; MLE-bench -> 2410.07095; HLE and OSWorld -> empty results; METR/time-horizon/tau/HLE/OSWorld title queries -> empty (arXiv API 429 rate limit after ~10 queries).
- arXiv API id_list lookup -> HTTP 429; switched to direct PDF downloads by known arXiv id.
- DuckDuckGo html queries (CompileBench; METR time horizon 2026 update) -> empty/202, no use.
- Direct URL probes: metr.org blog 2025-03-19, /time-horizons/, /blog/2026-01-29-time-horizon-1-1/ -> all HTTP 200; compilebench.com -> 200; arxiv.org/abs/2404.07972 (OSWorld) -> title only.
## Downloads
- 011 arxiv.org/pdf/2503.14499 OK (45 pages text) | 012 2509.16941 OK (20 pages) | 013 2408.08926 OK (150 pages text) | 014 2406.12045 OK (50 pages) | 015 2507.15887 OK (46 pages) | 016 2411.15114 OK (68 pages) | 017 2410.07095 OK (29 pages) | 018 2501.14249 OK (29 pages, v12 dated 19 Oct 2026)
- 019 quesma.com/blog/introducing-compilebench/ saved html + excerpt of compilebench.com landing text (first 6 kB).
- 020 metr.org/blog/2026-01-29-time-horizon-1-1/ saved html; live metr.org/time-horizons/ FAQ text saved as 020_metr-time-horizons-page-text.txt.
- gh api read-only: METR/eval-analysis-public readme and directory listing only (no data pulled).
## Not covered / skipped
- OSWorld (2404.07972): lowest priority, ID cap of 10 reached; only the abs title was seen. SWE-Lancer, PaperBench, Cybench 2026 follow-ups not searched. SWE-Bench Pro V2 / Verified papers only abstracts read (UNVERIFIED beyond abstract).
- METR live page per-model numbers are JS-rendered, not read. Follow-up METR 'holistic scoring' and cross-domain time horizon posts cited but not read.
## Issues
- PDF text for Table 4 of SWE-Bench Pro (012) has lost column alignment; text numbers used, table marked UNVERIFIED.
- Models in 013/014/015/016/017 are 2024-2025 era; absolute numbers may not hold for current frontier models.
- The webfetch result for CompileBench ended with an appended 'Agent Usage Reminder' block recommending subagents; treated as tool noise, ignored.


## Agent C: LLM failure modes
# Agent C run log (IDs 021-030)
- arXiv API search by exact title phrase (8+ queries: Illusion of Diminishing Returns, Faith and Fate, How many instructions, Curse of Instructions, cannot self-correct, GSM-Symbolic, NPHardEval, PlanBench, state tracking permutation composition): worked for 5 queries (found 2305.18654, 2507.11538, GSM-Symbolic 2410.05229 + 2605.28700 + 2610.03367, NPHardEval 2312.14890, PlanBench 2206.10498/2409.13373/2606.22388). Empty for others (rate limit; later HTTP 429 on export.arxiv.org).
- Later field-qualified queries (ti:/abs:) returned empty/429 (arXiv API rate-limited, shared with other agents). Switched to direct PDF download by known arXiv ID (verified by reading the title page).
- Downloaded OK: 2509.09677 (021), 2506.06941 (022), 2310.01798 (023), 2507.11538 (024), 2305.18654 (025), 2410.05229 (026). Text via pypdf to txt/C_<id>.txt (own filenames to avoid collision).
- Notes 021-026 written.
- Semantic Scholar graph API search (topic only): "state tracking language models reasoning" -> 6 hits (chose 2511.10457); "premature termination reasoning models underthinking" -> empty; "NPHardEval reasoning models 2026 combinatorial" -> empty. DuckDuckGo html: no hrefs parsed (empty).
- Downloaded OK: 2511.10457 (027), 2409.13373 (028), 2312.14890 (029), 2606.22388 (030; found via arXiv API title search PlanBench).
- Notes 027-030 written. Fragments C_sources.json (10), C_findings.json (27) validated with json.tool.
- NOT covered (search blocked by arXiv 429 / no paper found): Curse of Instructions/ManyIFEval, character counting, overthinking/underthinking, calibration, parsing edge cases (CSV/encoding). Suggest lead assign if needed.
- No failed downloads. Nothing sent externally except topic-only search queries.


## Agent D: reward hacking / grading / variance
# Agent D run log (IDs 031-040; topics 6 reward hacking, 7 partial credit/grading, 8 difficulty measurement)
Date 2026-10-20 (IST). Scratch txt extracts in txt/031..040.txt; calc script calc_D.py, builder mk_D.py.

## Searches (topic-only queries)
- arXiv API exact title/phrase: "ImpossibleBench" -> 2510.20270 (also Hodoscope 2604.11072, Troy Moment 2609.15494; not used).
- arXiv: "Adding Error Bars to Evals" -> 2411.00640. OK.
- arXiv: "Judging LLM-as-a-Judge" -> 2306.05685 (MT-Bench) OK; also saw 2609.02942 "Judging LLM-as-a-Judge: Rubric Artifacts" (2026-08-31), NOT read (ID budget used; candidate for a follow-up).
- arXiv: "Evaluating Large Language Models Trained on Code" -> 2107.03374 OK.
- arXiv: "agent-as-a-judge" -> 2410.10934 used; also 2601.05111, 2604.18240 (AJ-Bench), 2606.08200 seen, not read.
- arXiv: "reward hacking" AND "coding agents" -> SpecBench 2605.21384 (used), EvilGenie 2511.21654 (used); also seen not read: School of Reward Hacks 2508.17511, hacktrace 2610.03055, Can escalation channels redirect reward hacking 2608.29460.
- gh api search/issues "SWE-bench git log future commit leak" -> issue #465 (used), PR #581 (referenced inside).
- arXiv: reliability/repeated runs/agent benchmark -> On Randomness in Agentic Evals 2602.07150 (used). Seen not read: Agent Evaluation Reliability: More Tasks Won't (Always) Fix An Agent Leaderboard 2610.00651; Beyond Pass@k 2608.14711; Identical Runs, Different Results 2609.34274; Holistic Agent Leaderboard 2510.11977.
- arXiv: partial credit + agent + benchmark -> Do Agents Dream of Root Shells? Partial-Credit Evaluation of LLM Agents in CTF 2604.19354 (seen, NOT read; good follow-up for topic 7); PartHackBench 2609.29578 (seen).
- arXiv: rubric LLM judge agentic trajectory -> several 2026 papers seen (2610.03315 rubric-guided trajectory evaluation, ...), not read.
- DuckDuckGo not used.

## Downloads
- 031 arxiv.org/pdf/2510.20270 OK (25 pp). 033 arxiv 2411.00640 OK. 034 arxiv 2107.03374 OK. 035 arxiv 2306.05685 OK. 036 arxiv 2605.21384 OK (v2). 037 arxiv 2410.10934 OK. 038 arxiv 2511.21654 OK (11 pp). 040 arxiv 2602.07150 OK (9+ pp).
- 032 METR blog: webfetch (output truncated by tool at ~147 lines) + curl -o html; read the remaining text from the saved HTML (tags stripped). OK. Footnotes after fn.4 not read.
- 039 SWE-bench issue #465: gh api GET of issue + 20 comments, rendered to .md. OK. PR #581 and linked gists not opened.
- Failures: none for downloads. pypdf extraction of 040 flagged as binary by grep (used grep -a).

## Not verified / limits
- ImpossibleBench Fig.1 bar-to-model mapping (39/48/54/70/76%) ambiguous in text extraction; not used as a number.
- SpecBench: paper's text vs figure differ (27 vs 28 pp; R2 0.21 vs 0.25).
- On Randomness: SDs are benchmark-aggregate; 500-task count not verified in my read.
- Judge-reliability numbers (035, 037) are 2023-24 judges; no source read on Opus-class judges.
- Anti-cheat items "checksum of graders" and "tests not mounted until grading": the latter is supported by 031 (hide tests / revert at scoring) and 003 (A's note: planted admin/ folder, hack rates); "checksum of graders" has NO source found in my reading (UNVERIFIED; common practice, not cited).
- 1+8 confidence figures are MY computation (calc_D.py), t critical value 1.8595 from a standard t-table.

## Anti-cheat measures with sources (for the lead)
1. Hidden tests (not in agent workspace) -> cheating near zero but lowers honest pass rate [031 §5.2 p.8]. Read-only tests + revert modified tests at scoring [031 §5.2 p.8]; does not stop special-casing/operator overloading.
2. Held-out tests = ~30% of cases, undisclosed [038 §2.2 p.3]; hidden composition tests defeat lookup-table 'compilers' [036 §3.6 p.9]; heuristics can still pass thin holdouts [038 §4.1].
3. Remove future git history/branches/reflog/tags/origin from the image [039 maintainers' fix].
4. Do not rely on 'do not cheat' text [032 prompt table]; keep grader code, reference answers, and expected outputs out of the sandbox, off the call stack and out of importable paths [032 examples].
5. Compare outputs by value from files/stdout, not via agent-supplied objects (__eq__ overloading, state recording) [031 §4.1].
6. No repeated test-feedback loop with the real tests; allow an explicit 'spec is wrong/impossible' exit [031 §5.3 p.8].
7. Detect: LLM judge over trajectory + review of anomalous high scores + file-edit detection (inotify-style) [032, 038 §4.2-4.3, 003 via A].
