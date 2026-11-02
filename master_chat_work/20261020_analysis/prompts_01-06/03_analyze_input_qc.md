# Analyse: Input_Bundle_QC (Harbor 0.24)

You are a read-only analyst. Map every check in the Input Bundle QC so another agent can write task-building prompts that pass it the first time, and can tell quickly what changed when the QC is updated. You fix nothing.

## Paths (absolute)
- SOURCE (read only, pushed `main`): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`
- Related, read only, for cross-reference: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/validate_bundle.py`
- REPORT OUT: `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/reports/qc/`
- SCRATCH (only place you may execute code): `/tmp/qc-analysis-<YYYYMMDDTHHMM>/`
- LOGS: `/tmp/opencode-logs/qc-analysis-<YYYYMMDDTHHMM>/`

## Background
Every task Ayush builds must pass this QC. It changes more often than the generator, so prompts must never hardcode its rules. They will read the live QC and use your report as the map. The QC has 12 files (~6.5k lines): `Starter.md` (orchestrator), `01_Instruction_QC.md`, `02_Data_Solution_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`, `Final_checklist.md` (1259 lines), scripts `structure_qc.py`, `instruction_qc.py`, `tests_qc.py`, `judge_qc.py`, `exe_copy.py` (Step 10 oracle/nop/stub copies).
Known: `tests_qc.py` A3 fails below 10 checks and warns above 35. Ayush ignores count-cap warnings on purpose, because more tests scored better. Still list every cap and whether it is a FAIL or a WARN. Verdicts are FAIL / WARN ("tasker approval needed") / MINOR / PASS. The judge (rubric) channel never runs locally (no OPENAI_API_KEY), so note every check that needs the judge to run.

## Hard rules
1. Never modify, create or delete anything inside `Terminal_2.0_Harbor_Harness/`. Read-only git only (`git log`, `git show`, `git diff`). Never commit, push, pull or checkout.
2. Execute scripts only in SCRATCH, on copies. To see real script output, generate a throwaway bundle in SCRATCH with the PL generator (`generate_bundle.py` with an output dir inside SCRATCH, fixed seed), then run each QC script on it. Never run them against anything in `QC assigned/` or the clone.
3. Read, do not grep-and-conclude. Read every `.md` in full and every `.py` file in full. `Final_checklist.md` is long, so read it in offset chunks until the end. If a read says truncated, read the rest.
4. Every claim cites `path:line`. Anything not confirmed is UNVERIFIED. Flag every place where the markdown guides, the scripts, `Final_checklist.md` and `validate_bundle.py` disagree (a different threshold, a check in one but not another, or a different severity).
5. Any command that may take more than about 4 minutes runs as `nohup ... > LOGS/<name>.log 2>&1 &`, polled with waits under 4 minutes. Do not end your turn while your own job runs. `exe_copy.py` plus Docker builds count as long.
6. Subagents only for parallel reading of separate gate files. Verify their claims yourself.
7. Write each section to disk as soon as it is done.

## What to find out (all of it)
A. Workflow: the full QC procedure from `Starter.md`, in order: steps, gates, which script or manual review each step uses, how verdicts combine, what the report must contain, and Step 10 (exe_copy: what it builds, oracle/nop/stub expectations and thresholds).
B. Every check: for each of the five gates, plus the checklist and each script, list every check ID, what it checks, how (automated script, manual judgment, or both), severity, numeric thresholds, the files it reads, and what passing evidence looks like.
C. Hard FAIL list: every condition that fails a bundle outright, grouped by file it touches (`instruction.md`, `task.toml`, Dockerfile, data, solution, TRUTH.md, tests, `reward.toml`, `judge.toml`).
D. Judgment checks: every check that cannot be scripted (overlap, double payment, trigger depth, truth against the oracle, negative grammar, etc.), with the exact wording of what a reviewer looks for, and common ways bundles fail them.
E. Judge/rubric rules: criterion count, weights (positive and negative sums), `evaluation_target`, allowed types, grammar rules and the five-key `[judge]` header. Also the reward arithmetic combining tests and judge.
F. Instruction rules: length, banned phrasing, what must or must not be disclosed, metadata (description at most 100 words, author name format, etc.).
G. Caps and limits: every numeric cap or minimum, each with FAIL/WARN and source.
H. Cross-reference with `validate_bundle.py`: which QC checks the generator validator already covers, which it does not, and any conflicts.
I. Run evidence: in SCRATCH, output of every script on the throwaway bundle (pass/warn/fail counts and the failing IDs). Explain what a fresh scaffold fails before any authoring.
J. Change tracking: `git log` for this folder (last 15 commits, with what changed and which check IDs), to show how often and in what way the QC changes.
K. A QC-safe authoring checklist: a short, ordered list a builder follows so a new bundle passes on the first run. Every item points to its check IDs.

## Deliverables (in REPORT OUT)
1. `REPORT.md`: sections A to K, plus `## Disagreements between QC sources` and `## Not checked`.
2. `qc_checks.json`: `[{"id":"","gate":"01|02|03|04|05|final|script","source":"path:line","checks":"","method":"script|manual|both","script":"","severity":"FAIL|WARN|MINOR","threshold":"","files":[],"needs_judge_run":false}]`. One entry per distinct check ID; list the same ID from several sources once, with all its sources.
3. `caps.json`: every numeric limit with its severity and source.
4. `authoring_checklist.md`: section K on its own, ready to paste into a builder prompt.
5. `fingerprint.json`: `{"source":"<abs path>","git_head":"","generated_ist":"","files":{"<relpath>":"<sha256>"}}`.
6. `RUN_LOG.md`: every command with exit codes.

## Done when
All six files exist and the JSON parses (`python3 -m json.tool`), every check ID found in any source appears in `qc_checks.json`, the clone is unchanged (`git status` clean for this folder), and SCRATCH is deleted. Finish with a reply of at most 10 lines: paths, check counts by gate and severity, the number of judgment-only checks, and the top 5 ways a fresh bundle fails.
