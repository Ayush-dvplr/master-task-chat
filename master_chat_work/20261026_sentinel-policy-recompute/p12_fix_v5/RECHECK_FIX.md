# P12 fix of QC v5: sentinel-policy-recompute (d95f83e)

Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute`
QC report: `/Users/mac/Desktop/Terminal Bench/QC/reports/sentinel-policy-recompute/v5.md`
Result: 3 FIXED (1, 2, 5), 3 KEPT (3, 4, 6). Not touched: environment/data, generators, hidden corpora, ledger_repair, every positive test weight, solve.py, solve.sh, reward.toml, instruction.md.

Session rename: `name_session.py d95f83e` printed `codex: no match` / `opencode: ['ses_e844255b2ffePjkPnS1EnyPQ3E']`. The output does not show d95f83e, so the rename is unconfirmed. I did not retry it.

## 1. JD-15 R10 label: FIXED
`tests/judge.toml:137`
- before: `type = "instruction following"`
- after: `type = "agent behavior"`

Only the label changed. The R10 text, weight 3, evaluation target and importance did not change. R12 keeps `type = "instruction following"` (judge.toml:163).

## 2. AL-2 promises: FIXED
(a) instruction.md:9 ("Use only the Python standard library and the pyarrow package ...") now has a negative check.
- `tests/test_output.py:43` added: `TOOL_DIR = Path("/app/tool")`
- `tests/test_output.py:1770` added `third_party_imports()`. It parses every `*.py` in the delivered tool.zip extract and in `/app/tool` with `ast`. For each `import` and each `from` import with level 0, it takes the top-level module and flags it when that module is outside `sys.stdlib_module_names | {"pyarrow"} | <tool's own module names>`.
- `tests/test_output.py:1792` added `test_negative_weight_third_party_import_in_tool()`: "NEGATIVE: fires when a Python file of the delivered tool imports a module outside the standard library, pyarrow and the tool itself."
- `tests/test_output.py:2009` added the `@criterion` wrapper `negative_third_party_import_in_tool`, with the kit's `# True means the cheat happened; the negative weight applies.` line.
- `tests/test_output.py:2048` registered: `criteria.negative_third_party_import_in_tool(weight=-3)`, placed after `negative_url_or_secret_in_artifacts(weight=-3)`.

(b) instruction.md:7 ("listing every input file present in the reference data") now gets a comparison against the real file names. The weight is still 1, inside `shipped_artifacts_carry_policy_runs_and_archive`.
- before, test_output.py:1728: `assert summary["inputs"] == sorted(summary["inputs"]) and summary["input_count"] == len(summary["inputs"]) >= 50, "summary.json inputs differ"`
- after, test_output.py:1729-1730: `corpus_names = sorted(Path(name).name for name in corpus_files() if not name.endswith("/"))` / `assert summary["inputs"] == corpus_names and summary["input_count"] == len(summary["inputs"]), "summary.json inputs differ"`
- The docstring tail changed from "...and a sorted input list of at least 50 names whose count matches." to "...and the sorted file names of the reference corpus as inputs with their count."

TRUTH.md was updated to match:
- `solution/TRUTH.md:155-157` adds to the out-of-bounds list: "a tool Python file importing a module outside the standard library, pyarrow and the tool itself (`negative_third_party_import_in_tool`)".
- `:267`: "declares 34 checks, positive total 131, negative total -11" became "declares 35 checks, positive total 131, negative total -14".
- `:324`: "both profiles and a sorted input list" became "both profiles and the sorted corpus file names as inputs".
- `:327-328`: the negatives list adds "`negative_third_party_import_in_tool` (-3)".
- `:456`: the test_output.py sha changed from `abcf8dae...ce721` to `4103f421505a8a3176a0575f0603f335ac055da1da1266ae77eb6613b9585621`. The solve.py sha (`1fb297ed...`) and the tool.zip sha (`7fd26ac3...`) were recomputed and have not changed.

## 3. TS-13 multi-property checks: KEPT
The two checks that hold several properties (w1 and w3) have weights that were already measured by two harness probes (65.59/96.18/35.0 and 45.56/78.63/12.5). Splitting them would move positive weight, and the rules for this step forbid that.

## 4. TS-20 artifacts at weight 1: KEPT
The artifact contents are graded mostly through the hidden reruns and the document checks (weight 5 each). This check covers only their presence and shape. Raising it would change a positive weight that the harness probes already calibrated.

## 5. JD-15 R11 label: FIXED (weight KEPT)
`tests/judge.toml:150`
- before: `type = "task completion"`
- after: `type = "agent behavior"`

Weight 5 and `critically_important` are kept, because a cli.py whose handlers swallow errors is the defect the task exists to repair, so missing it is not survivable.

## 6. JD-13 R12 weight 5: KEPT
R12 at weight 5 is part of the judge channel that the two harness probes measured (rubric 35.0 and 12.5). Lowering it would re-weight a channel that is already calibrated, and an output summary that omits paths hides deliverables from the reviewer.

## Gates (each run once)
- `__pycache__` removed under tests/.
- precheck.sh: last line `PRECHECK CLEAN` (tests 35, judge criteria 15). I re-ran it once after the TRUTH sha edit, and it was still CLEAN.
- QC kit scripts, all exit 0 with 0 FAIL:
  - structure_qc: 17 pass, 1 warn. The warn is X1: 8 files are skipped as binary, and they really are binary, as v5 also found.
  - instruction_qc: 5 pass.
  - tests_qc: 37 pass.
  - judge_qc: 19 pass.
- Local oracle: `oracle_local.py` reported solve exit 0. Then `local_score.py` gave `SCORE 1.0000 (131/131)`. `negative_third_party_import_in_tool` did not fire ("honest baseline: the tool imports only the standard library and pyarrow"). This ran in a temp venv at /tmp/spr_venv with pyarrow and harbor-rewardkit 0.2.1.
- The negative fires (scratch copies in /tmp only):
  - `import yaml` prepended to cli.py inside out/tool.zip: `negative_third_party_import_in_tool w=-3 PASS`.
  - `import yaml` prepended to /app/tool/cli.py: `negative_third_party_import_in_tool w=-3 PASS`, `SCORE 0.9771 (128/131)`.
- Docker (tests-only copy from exe_copy.py at /tmp/spr_exe, `OPENAI_API_KEY=unused`, run through `yes | harbor ...`):
  - oracle: reward 1.0 (rc 0, 49 s). In reward-details.json, `negative_third_party_import_in_tool` has raw false.
  - nop: reward 0.0.
- Tasks_INPUT sync: `cp -Rp` done, and `diff -rq` printed nothing (rc 0).
