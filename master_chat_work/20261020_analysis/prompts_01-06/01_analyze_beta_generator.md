# Analyse: Ayush's beta-task-generator (Harbor 0.23.0)

You are a read-only analyst. Reverse-engineer one codebase and write a complete report another agent can rely on without reopening the source. You build nothing and fix nothing.

## Paths (absolute)
- SOURCE (read only): `/Users/mac/Desktop/Terminal Bench/beta-task-generator/`
- REPORT OUT: `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/reports/beta_generator/`
- SCRATCH (only place you may execute code): `/tmp/beta-analysis-<YYYYMMDDTHHMM>/`
- LOGS: `/tmp/opencode-logs/beta-analysis-<YYYYMMDDTHHMM>/`

## Background
Ayush built this generator for Harbor 0.23.0. Harbor is now 0.24 and the old task format is obsolete, but the ideas are not. In 1 to 1.5 weeks Ayush will build a new generator for 0.24 and wants every good idea from this one carried over. Known weak spots of the generators so far: generated data files were too small, and too few file formats were accepted. Ayush used ChatGPT for idea generation (see `playbooks/chatgpt-ideas.md`, `prompts/idea-workshop.md`).

Size: about 353 files, 5.4 MB, ~7.7k lines in `core/*.py`, ~2.5k lines of docs. Top level: `generator-use-instruction.md`, `BETA-GENERATOR-HANDBOOK.md` (1000+ lines), `README.md`, `AGENTS.md`, `CLAUDE.md`, `config/` (defaults.json, source_components.json, agent_adapters/), `core/` (~60 modules), `playbooks/` (12 modes), `prompts/`, `qc/policy/beta.json`, `qc/snapshots/upstream-c6cc84f98f9e/` (pinned QC + generator reference), `references/` (catalog.json, curated/design-guide.md, source-catalog.md), `tests/`, `tools/archive_sources.py`. Git: 3 commits, latest `17e9f70`.

## Hard rules
1. Never modify, create or delete anything inside SOURCE. Never run `python -m core init` or any write command in SOURCE (`init` creates `workspace/`). No git writes anywhere.
2. To execute anything (CLI `--help`, `core status`, the test suite, a dry run), first `cp -R` SOURCE into SCRATCH and run there with `--root` pointing at SCRATCH.
3. Read, do not grep-and-conclude. Use grep to find lines, then read them in context. Read every doc file in full and every `core/*.py` file at least at function level (signature + body skim). If a read says truncated, read the rest with an offset.
4. Every claim cites `path:line` or a command and its output. Anything you could not confirm is marked UNVERIFIED.
5. Any command that may take more than about 4 minutes runs as `nohup ... > LOGS/<name>.log 2>&1 &` and you poll it with waits under 4 minutes. Never block a single tool call past 4 minutes. Do not end your turn while your own job runs.
6. Use subagents only for genuinely parallel reading of separate module groups. Verify their findings against the source before writing them down.
7. Write each report section to disk as soon as it is done, so a compaction cannot lose it.

## What to find out (all of it)
A. Purpose and operating model: what the generator is, what it refuses to do, the safety model (write scopes, proposals, approvals).
B. Architecture map: every `core/` module, one line on its role, what it reads and writes, and which CLI command uses it. Draw the data flow from idea to delivered bundle.
C. The 12 modes: for each, inputs, steps, outputs, records written, and stop conditions. Quote the playbook.
D. Hardness. This is the most important section. Every technique the generator, its playbooks, design guide or policy uses to make tasks hard or to measure hardness: mechanism cards, overgenerate/refine, hardening loop, score thresholds, underivability or originality checks, cheat vectors, partial-credit design, baselines. For each: name, how it works, where it is (`path:line`), whether it is enforced in code or only advised in prose, and any measured evidence it worked.
E. Ideas pipeline: how ideas are produced (ChatGPT playbook and prompts), reviewed, scored, selected and recorded. Copy the idea-workshop prompt structure exactly.
F. QC handling: the QC policy, the pinned snapshot, qc_runner, qc_repair, receipts, semantics, the three-category analysis and repair selection. How it decides a finding is real, and how it repairs without breaking hardness.
G. Scores and feedback: how harness results are ingested, diagnosed and fed back (scores.py, verdicts, findings, feedback playbook, benchmark playbook).
H. Data and file formats: which file formats generated tasks can contain, how data volume is decided, every size or count limit in `config/defaults.json` and code, and assets and licensing. State plainly where data volume or format variety is limited.
I. Upstream and update handling: how the generator detects an upstream (PL generator or QC) change, diffs it (`source_diff.py`, `upstream.py`, `update.py`) and migrates. This matters because the PL generator and QC change often.
J. Portability to Harbor 0.24: classify every major idea as PORTABLE (format-independent), ADAPT (needs change) or OBSOLETE (0.23-only), with a reason.
K. Strengths, weaknesses and gaps, including dead code, documented features with no implementation, and implemented features with no docs.
L. Run evidence: in SCRATCH, run the test suite and `--help` for every subcommand. Record pass/fail counts and anything broken.

## Deliverables (in REPORT OUT)
1. `REPORT.md`: sections A to L in that order, plus `## Not checked` (what you did not read or run, and why). No filler. Tables where they help.
2. `ideas.json`: every reusable idea. `[{"id":"B-001","name":"","category":"hardness|data|format|qc|scoring|ideation|workflow|safety|update","summary":"","how_it_works":"","evidence":["path:line"],"enforced":"code|prose|both","portability":"PORTABLE|ADAPT|OBSOLETE","portability_note":"","value_for_v2":"high|medium|low"}]`
3. `modes.json`: `[{"mode":1,"name":"","inputs":[],"steps":[],"outputs":[],"records":[],"playbook":"path"}]`
4. `limits.json`: every numeric limit and default with its source path:line.
5. `fingerprint.json`: `{"source":"<abs path>","git_head":"","generated_ist":"","files":{"<relpath>":"<sha256>"}}` for every file except `.git/`.
6. `RUN_LOG.md`: commands you ran and their exit codes.

## Done when
All six files exist, every section A to L is filled or explicitly says "nothing found" with what you searched, `ideas.json` parses with `python3 -m json.tool`, SOURCE is unchanged (re-hash and compare to `fingerprint.json`), and SCRATCH is deleted. Finish with a reply of at most 10 lines: file paths, idea counts by category and portability, and the top 5 hardness ideas.
