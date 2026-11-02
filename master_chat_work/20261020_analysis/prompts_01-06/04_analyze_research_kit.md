# Analyse and refresh: Ayush's Harbor 0.23 to 0.24 research kit

You are a read-only analyst. Check one research kit against the current state of the tools and QC, and say what still holds, what is stale and what is missing for authoring hard tasks that pass QC. You fix nothing in the sources.

## Paths (absolute)
- SOURCE (read only): `/Users/mac/Desktop/Terminal Bench/research/` (274 files, 1.9 MB, written 17 Oct 2026). Start with `00-index.md`, then `01-report-0.23-to-0.24.md`, `02-format-spec-0.24.md`, `03-decisions.md` (D1-D15), `04-checklist.md` (A-I), `examples/`, `_scaffold-0.23/`, `_scaffold-0.24/`, `_evidence/`.
- CURRENT AUTHORITIES (read only), to compare against:
  - QC: `/Users/mac/Desktop/Terminal Bench/QC assigned/Input_Bundle_QC/` (matches GitHub head 9b8229f6). Do NOT use `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`: its markdown guides are 2 commits stale (scripts are identical).
  - Generator: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/` (`validate_bundle.py`, `templates/*/`).
  - Installed tools: `harbor` 0.24.0 and `harbor-rewardkit` 0.2.1 (check with `harbor --version`, `pip show`/`uv tool list`).
- REPORT OUT: `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/reports/research_kit/`
- SCRATCH (only place you may execute or write): `/tmp/research-kit-analysis-<YYYYMMDDTHHMM>/`
- LOGS: `/tmp/opencode-logs/research-kit-analysis-<YYYYMMDDTHHMM>/`

## Background
Harbor moved from 0.23.0 to 0.24. The kit says the task format itself is byte-identical between the two and only runtime behaviour and CLI flags changed. Ayush's working belief is that "all the old tasks and formats are gone". The real difference is probably the QC's required bundle shape (rewardkit `test_output.py`, `reward.toml`, `judge.toml`, exact file set, schema 1.4 with per-role `network_mode`), not Harbor's own schema. Settle this with evidence.

## Hard rules
1. Never modify anything in SOURCE, `QC assigned/`, `Terminal_2.0_Harbor_Harness/` or `beta-task-generator/`.
2. Git and gh: read-only only (`log`, `show`, `diff`, `status`, `ls-remote`, `gh api` GET). Never pull, commit, push, merge, checkout, reset or open a PR. If one is needed, write the exact command in the report for Ayush to run. Allowed repos only: ShreeyankDoliya/Terminal_2.0_Harbor_Harness, ShreeyankDoliya/Anubis_Tasks_Samples, ayushsah-dev/beta-task-generator, ShreeyankDoliya/Finalized_Tasks_RFP.
3. Execute only in SCRATCH (`harbor task init`, `harbor task schema`, `--help` captures). No `harbor run` against real agents or models, and nothing that sends bundle content to an external service. Docker runs (oracle/nop on a scaffold) only in the background.
4. Read every `.md` in SOURCE in full. For `_evidence/` and `_scaffold-*`, list everything and read what a claim depends on. If a read is truncated, read the rest.
5. Every claim cites `path:line` or a command and its output. Unconfirmed means UNVERIFIED.
6. Anything that may run over about 4 minutes goes `nohup ... > LOGS/<name>.log 2>&1 &`, polled with waits under 4 minutes. Do not end your turn while your own job runs.
7. Write each section to disk as soon as it is done.

## What to find out
A. Summary of the kit: what each file claims, in a table.
B. Re-verify: for every claim in `00-index.md` and `01-report`, and every decision D1-D15, mark STILL TRUE / STALE / UNVERIFIED against installed Harbor 0.24.0 (re-run the cheap commands in SCRATCH), with evidence.
C. Harbor schema vs QC bundle shape: a side-by-side of what Harbor accepts (`02-format-spec-0.24.md`, `harbor task schema`) and what the current QC and the generator require. Every place the QC is stricter, narrower or different (files, keys, values, reward mechanism, judge). This answers "what is actually gone".
D. Checklist `04-checklist.md`: for each item A-I, whether it is still needed, already covered by a QC check (cite the check ID), or conflicts with QC.
E. The traps the kit found (unknown keys silently ignored, one-line canary stripping, step verifier timeout not inherited, separate verifier sees only `artifacts`, `final` vs `mean` multi-step strategy). Does each still hold in 0.24.0, and could any be used for hardness or cause a QC fail?
F. Multi-step tasks: does the current QC or generator allow them? If yes, under what rules. If no, cite where it says so.
G. Anything in the kit useful for making tasks harder, in a list.
H. Gaps: what an author still needs that neither the kit nor the QC documents.

## Deliverables (in REPORT OUT)
1. `REPORT.md`: sections A-H, plus `## Commands for Ayush` (only if needed) and `## Not checked`.
2. `claims.json`: `[{"id":"","source":"path:line","claim":"","status":"STILL_TRUE|STALE|UNVERIFIED","evidence":""}]`
3. `harbor_vs_qc.json`: `[{"item":"","harbor_0_24":"","qc_requires":"","generator_requires":"","difference":"same|stricter|different|qc_only"}]`
4. `fingerprint.json`: sha256 of every SOURCE file, plus `generated_ist`.
5. `RUN_LOG.md`: commands with exit codes.

## Done when
All five files exist, the JSON parses (`python3 -m json.tool`), every D1-D15 and every checklist item is classified, SOURCE is unchanged (re-hash), and SCRATCH is deleted. Final reply of at most 8 lines: paths, counts of STILL_TRUE/STALE/UNVERIFIED, and a one-line answer to "what is actually gone between 0.23 and 0.24".
