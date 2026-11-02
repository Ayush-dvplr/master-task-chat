# E-code-1 report, board 7fdff25 (plan v2 A1, A2, A3 code, A4)

Status: DONE. All four items built. Tool tests: 23 ok. Auto tests: 46 OK before, 46 OK after.
Nothing was written to MT/registry, MT/board.json, MT/decisions.jsonl, MT/knowledge, MT/auto, or anything under H/.
Every write in the checks below went to /tmp copies (`/tmp/E1-a1..a4`, `/tmp/repack-*`, `/tmp/E1-tests-*`). Those were deleted at the end.
The full raw outputs are in `scratch/verify_A1.txt`, `verify_A1b.txt`, `verify_A2.txt`, `verify_A3.txt`, `verify_A4.txt`, `auto_before.txt`, `auto_after_full.txt` and `tools_tests.txt`.

Short names: MT = `T/master_chat_tasks`, H = `T/Terminal_2.0_Harbor_Harness`, OUT = this folder.

## Files changed (sha256, first 12 characters)
| file | before | after |
|---|---|---|
| MT/tools/issue.py | 8e8257e3 (148 lines) | f3aaca643fdd |
| MT/tools/intake.py | 672eebe4 (133 lines) | d2e02e7bde5a |
| MT/tools/status.py | 2044251b (91 lines) | 06f4538e094e |
| MT/tools/repackage_one.py | (new) | 1a665aee9d23 (115 lines) |
| MT/tools/tests/test_upgrade_tools.py | (new) | c886f030fc2c (315 lines, 23 tests) |

## A1 issue.py
### Changes (before line -> after line)
- :34 KINDS -> :42, adds `"ql"`. TASK_KINDS is derived from KINDS, so it includes ql. The `--kind` choices are `sorted(KINDS)`, so they include ql too.
- :58-61 `stage()` -> :66-75 `pipeline(slug)` plus a new `ql_open(p)` at :72. **Open QL round**: `pipeline.ql_round` is not empty, `0` or `none`, AND `pipeline.ql_last` does not start with `closed` (case does not matter). The master closes a round with `ql_last="closed <TS> <path>"`.
- :71 `passed = st in (qc_pass, gate_runs, pl_ready)` -> :82-86: `open_ql = st == "pushed" and ql_open(p)` and `passed = ... or (st == "pushed" and not open_ql)`. Passed still gates only qc and harden. The stop-at-PASS check, the no-harden-after-PASS check, the fix/qc round caps and the drop rule are unchanged.
- :89-90 time box -> :104-108:
  - `since = max(REGIME, stage_since)`.
  - `free = {"ql"} | ({"qc","fix","harden"} if open_ql)`.
  - `boxed` counts only the board rows with `issued >= since` whose kind is not in `free`.
  - A kind in `free` is never refused by the time box.
- New `auto_live()` at :112. It is true when the `AUTO_RUN` env var is set. It is also true when `MT/auto/LATEST` -> `state.json` `watcher_pid` is alive and `ps` shows `auto.py` for that pid.
- New `--by` flag at :138. Override row :140 `"who": "Ayush"` -> :178 `"by": by`. If `--by` is not given, the value is `master (auto)` when `auto_live()` is true, otherwise `Ayush`.
- :122-123 file name -> :155-160. If the file already exists, the tool tries `{base}_2.md`, then `_3`, and so on.
- `HERE` honours the `MT_ROOT` env var (:38). This is only used for tests. Without it, the paths are the same as today.

### Verify (the plan's flag form `<draft> --slug .. --kind ql` does not exist; the real CLI is positional `SLUG KIND DRAFT OUT`, so I ran the adapted command on the copy tree `/tmp/E1-a1`)
```
$ python3 MT/tools/issue.py --help | grep -c ql
2
-- negative (original bak):
$ python3 OUT/bak/issue.py --help | grep -c ql
0
$ python3 /tmp/E1-a1/tools/issue.py sentinel-policy-recompute ql /tmp/E1-a1/draft.md "ql review" --dry-run
DRY RUN ok: would write /private/tmp/E1-a1/prompts/issued/sentinel-policy-recompute/20261029T0116_ql.md; refusals=none; override=no
exit=0
-- negative: same task, kind harden (time box still counts it, no open QL round):
REFUSED (cap):
  - task already passed QC (stage pushed); no harden after PASS
  - drop rule: 8 harden/rebuild rounds already (55d3b87, ...)
  - time box: 27 sessions for sentinel-policy-recompute since 2026-10-24 11:26
exit=1
-- negative: original issue.py with kind ql:
issue_orig.py: error: argument kind: invalid choice: 'ql' (choose from 'adhoc', 'blind', 'build', 'fix', 'harden', 'loss', 'probe', 'qc', 'rebuild', 'research', 'run')
$ grep -n '"who"' MT/tools/issue.py
exit=1 (1 = no hit)
-- negative: grep -n '"who"' OUT/bak/issue.py
140:            f.write(json.dumps({"ist": t.strftime("%Y-%m-%d %H:%M"), "who": "Ayush",
```
Real issues in the temp tree (its board.py, pending.py, pending.db and decisions.jsonl are all copies under /tmp/E1-a1):
```
20261029T0116_ql.md
20261029T0116_ql_2.md
$ tail -1 /tmp/E1-a1/decisions.jsonl     (--by "master (test)")
{"ist": "2026-10-29 01:16", "by": "master (test)", "decision": "cap override for sentinel-policy-recompute harden (275ba71): ...", "verbatim": "test words"}
-- no --by, AUTO_RUN unset, no live auto run:
{"ist": "2026-10-29 01:16", "by": "Ayush", "decision": "cap override for sentinel-policy-recompute harden (461983f): ...", "verbatim": "test words 2"}
```
The real board.json, decisions.jsonl and BOARD.md contain none of the test shas (82c4c7a, c62965d, 275ba71, 461983f): the grep count was 0 for each.

## A2 intake.py
### Changes
- :11 docstring `overall<50` -> :12 `final<40`.
- New `FINAL_GATE = 40` at :33.
- New `SHA_EVENTS = ("gate_run","ql_rerun")` at :34.
- :104 `gate = t < 85 and r < 85 and o < 50` -> :147 `o < FINAL_GATE`.
- :106 print text -> :149 `gate (tests<85, rubric<85, final<40)`.
- :124 `--event` choices -> :184, adds `ql_rerun` and `regrade`. New `--ayush-ok` at :185. It is rejected for any event other than regrade (:191).
- New `tree_sha(d)` at :46. It is a byte-identical Python version of `find . -type f | LC_ALL=C sort | xargs -I{} shasum -a 256 "{}" | shasum -a 256 | cut -c1-12`:
  - It only takes regular files, not symlinks.
  - Paths are `./...` and are sorted as bytes.
  - Each line is `hex  path\n`.
  - Names that contain `\` or a newline get shasum's escape form.
- Each row gets `tree_sha` from `--bundle`. The default bundle is `H/Tasks_INPUT/<job>`.
- :150-157 `gate_run` and `ql_rerun` are refused in both dry and `--apply` mode, before anything is written:
  - when the registry `tree_sha` is empty, with `registry tree_sha empty: set it at freeze (status.py set <slug> tree_sha=...)`;
  - when the two shas differ.
- :159-160 a regrade row has `valid = bool(--ayush-ok)`, and `artefact_reason "regrade without --ayush-ok"` when that flag is missing. The words are stored as `ayush_ok`.
- :170 without `--apply`, the tool prints `would append row (no --apply, nothing written): {...}` and writes nothing. Before, it printed nothing about the row.
- `HERE` honours `MT_ROOT` (:29). `HARNESS` (:31) is now based on the file's own location, so it ignores `MT_ROOT`. If the report path is not under ROOT, the full path is used instead.

### Verify
```
$ grep -n -e "o < 50" -e "overall<50" MT/tools/intake.py
exit=1 (1 = no hit)
-- negative on OUT/bak/intake.py:
11: ... gate check (tests<85, rubric<85, overall<50; Ayush 27 Oct 22:20) ...
104:    gate = t < 85 and r < 85 and o < 50
106:    print(f"gate (tests<85, rubric<85, overall<50): ...
$ grep -n "FINAL_GATE = 40" MT/tools/intake.py
33:FINAL_GATE = 40
-- negative on bak: 0
$ python3 MT/tools/intake.py --job district-heat-flex-procurement | grep -e gate -e tests
scores tests 73.0 rubric 16.67 overall 44.84 runs 1
gate (tests<85, rubric<85, final<40): not met | kill rule tests>=95: no
$ python3 MT/tools/intake.py --job sentinel-policy-recompute | grep -e gate -e tests
scores tests 80.95 rubric 0.0 overall 40.48 runs 1
gate (tests<85, rubric<85, final<40): not met | kill rule tests>=95: no
-- negative (original code, same jobs):
$ python3 OUT/bak/intake.py --job district-heat-flex-procurement --harness H | grep gate
gate (tests<85, rubric<85, overall<50): MET | kill rule tests>=95: no
$ python3 OUT/bak/intake.py --job sentinel-policy-recompute --harness H | grep gate
gate (tests<85, rubric<85, overall<50): MET | kill rule tests>=95: no
$ python3 MT/tools/intake.py --job sentinel-policy-recompute --event regrade     (no --apply)
tree_sha 583e77e1ae94 (.../Tasks_INPUT/sentinel-policy-recompute)
would append row (no --apply, nothing written): {"ist": "2026-10-29T01:16+05:30", "slug": "sentinel-policy-recompute", "event": "regrade", "rewards": {"tests": 80.95, "rubric": 0.0, "combined": 40.48}, "valid": false, "artefact_reason": "regrade without --ayush-ok", "tree_sha": "583e77e1ae94", "note": "", "report": "Terminal_2.0_Harbor_Harness/jobs/sentinel-policy-recompute"}
-- negative (same, with --ayush-ok "ok regrade it"): ... "valid": true, "artefact_reason": null, ... "ayush_ok": "ok regrade it"}
-- --ayush-ok on --event run: "intake.py: error: --ayush-ok is only for --event regrade", exit=2
$ tree_sha (python) vs shell one-liner:
cold-chain-backbone-quote python=8ca9c267f59b shell=8ca9c267f59b
district-heat-flex-procurement python=e9d91966ed25 shell=e9d91966ed25
$ python3 MT/tools/intake.py --job cold-chain-backbone-quote --event gate_run     (real registry, tree_sha empty today)
REFUSED gate_run: registry tree_sha empty: set it at freeze (status.py set cold-chain-backbone-quote tree_sha=...)
exit=1
$ ... --event ql_rerun
REFUSED ql_rerun: registry tree_sha empty: set it at freeze (status.py set cold-chain-backbone-quote tree_sha=...)
-- mismatch, temp registry (MT_ROOT=/tmp/E1-a2, tree_sha=000000000000), with --apply:
REFUSED gate_run: tree_sha 8ca9c267f59b of .../Tasks_INPUT/cold-chain-backbone-quote != registry tree_sha 000000000000
-- match (temp tree_sha=8ca9c267f59b), no --apply:
gate (tests<85, rubric<85, final<40): not met | kill rule tests>=95: KILL
would append row (no --apply, nothing written): {... "event": "gate_run", "rewards": {"tests": 100.0, "rubric": 70.0, "combined": 85.0 ...
temp scores.jsonl still identical to real (nothing appended without --apply / on refusal)
scores.jsonl unchanged
```
The tree-sha unit test also compares the Python and shell results on a directory that has a space, uppercase letters, an underscore and a symlink in its names. They agree.

## A3 status.py
### Changes
- FIELDS :22-23 -> :26-27, adds `tree_sha`, `ql_round`, `ql_last`.
- There is no new stage.
- New: `set stage=X` stamps `pipeline.stage_since` (IST `%Y-%m-%d %H:%M`) when the stage changes, or when `stage_since` is missing (:62-63). issue.py uses this to reset the time box. The idea comes from how `updated` is already set automatically. `stage_since` is not in FIELDS, so nobody sets it by hand.
- `HERE` honours `MT_ROOT` (:22).

### Verify (on the temp copy `MT_ROOT=/tmp/E1-a3`)
```
$ MT_ROOT=/tmp/E1-a3 python3 MT/tools/status.py set cold-chain-backbone-quote zz=1
bad field zz; allowed ['stage', 'kind', 'qc_round', 'fail', 'minor', 'warn', 'oracle', 'nop', 'stub', 'v0_reward', 'traj_tests', 'traj_rubric', 'traj_overall', 'next', 'updated', 'tree_sha', 'ql_round', 'ql_last']
exit=1
tasks.json unchanged (sha same)
-- negative (original status.py on the same tree):
bad field zz; allowed ['stage', 'kind', 'qc_round', 'fail', 'minor', 'warn', 'oracle', 'nop', 'stub', 'v0_reward', 'traj_tests', 'traj_rubric', 'traj_overall', 'next', 'updated']
$ MT_ROOT=/tmp/E1-a3 status.py set cold-chain-backbone-quote tree_sha=8ca9c267f59b ql_round=1 ql_last=open
ok
{'stage': 'gate_runs', 'tree_sha': '8ca9c267f59b', 'ql_round': '1', 'ql_last': 'open', 'stage_since': None}
$ grep -c tree_sha MT/registry/tasks.json      (real registry untouched)
0
```

## A4 repackage_one.py (new)
`repackage_one.py --slug S --run-dir JOB --task-dir TASK [--output-root H/Output_RFP] [--dry-run]`
- It loads `package()` from `H/scripts/package_rfp_bundles.py` with importlib. It never calls `main`.
- It refuses, before any write, when:
  - the slug and the task-dir name differ;
  - `run-dir/trajectory` is missing;
  - the task dir is missing;
  - the registry `tree_sha` is empty;
  - the registry `tree_sha` differs from the task dir's tree sha.
- It stages to `/tmp/repack-<slug>-<TS>/staged`.
- It writes `old.sha256`, `staged.sha256` and `diff.txt`, and prints the differences.
- `--dry-run` stops at that point.
- Otherwise it:
  1. backs up the whole old output folder (trajectories included) to `/tmp/repack-<slug>-<TS>/old/<slug>`;
  2. replaces the output folder with the staged copy;
  3. writes `after.sha256`, which must equal `staged.sha256` (if not, it exits with ERROR).

### Verify (fake output root `/tmp/E1-a4/Output_RFP` = a copy of the pushed sentinel folder; temp registry via MT_ROOT)
```
-- negative 1: registry tree_sha empty
REFUSED: registry tree_sha empty: set it at freeze (status.py set sentinel-policy-recompute tree_sha=...)
exit=1
-- negative 2: registry tree_sha mismatch (deadbeef0000)
REFUSED: tree_sha 583e77e1ae94 of .../Tasks_INPUT/sentinel-policy-recompute != registry tree_sha deadbeef0000
exit=1
repack work dirs after refusals: 0
$ MT_ROOT=/tmp/E1-a4 repackage_one.py --slug sentinel-policy-recompute --run-dir H/jobs/sentinel-policy-recompute --task-dir H/Tasks_INPUT/sentinel-policy-recompute --output-root /tmp/E1-a4/Output_RFP --dry-run
tree_sha 583e77e1ae94 == registry
    claude-opus-5: 1 run(s)
  sentinel-policy-recompute (Tasks_INPUT/): 1 run(s)
work /tmp/repack-sentinel-policy-recompute-20261029T011718
old 89 files (/tmp/E1-a4/Output_RFP/sentinel-policy-recompute), staged 89 files, 9 differences:
  changed   trajectories/claude-opus-5/pass_summary.json
  changed   trajectories/claude-opus-5/run_1/config.json
  changed   trajectories/claude-opus-5/run_1/report.json
  changed   trajectories/claude-opus-5/run_1/result.json
  changed   trajectories/claude-opus-5/run_1/verifier/reward-details.json
  changed   trajectories/claude-opus-5/run_1/verifier/reward.json
  changed   trajectories/claude-opus-5/run_1/verifier/reward_raw.json
  changed   trajectories/claude-opus-5/run_1/verifier/score.json
  changed   trajectories/claude-opus-5/run_1/verifier/test-stdout.txt
DRY RUN: nothing copied to /tmp/E1-a4/Output_RFP
-- dry-run wrote nothing to fake root: diff -rq fake real-pushed -> identical
$ (no --dry-run, same args)
work /tmp/repack-sentinel-policy-recompute-20261029T011727
old 89 files (...), staged 89 files, 9 differences:
backup /tmp/repack-sentinel-policy-recompute-20261029T011727/old/sentinel-policy-recompute
copied: /tmp/E1-a4/Output_RFP/sentinel-policy-recompute == staged (89 files)
-- backup == pre-copy folder: identical; fake root == staged: identical
-- real H/Output_RFP/sentinel-policy-recompute unchanged: same tree hash b9168ccb7949 before and after
```
The staged copy matches the pushed folder in all 89 files except 9 score files. The reason is that `H/jobs/sentinel-policy-recompute` is the original a8 run (40.48), while the pushed `run_1` is the 44.53 run rebuilt after the regrade.

## Tests
- `python3 -m unittest discover -s MT/tools/tests` -> `Ran 23 tests in 4.199s OK`.
- The tests copy the tools and the registry, board, pending.db and decisions files into `/tmp/E1-tests-*`, with `MT_ROOT` pointing there.
- Coverage:
  - **A1:** ql passes the time box, and run is refused by it; ql rows are not counted; an open QL round frees qc, fix and harden, and a closed round refuses them; pushed without QL refuses harden; a stage change resets the box; the override `by` comes from the flag, defaults to Ayush, and becomes `master (auto)` under AUTO_RUN; the `_2`/`_3` suffixes.
  - **A2:** tree sha values and the comparison with the shell; the gate text, and `not met` for both district and sentinel; regrade valid false/true; regrade `--apply` writes in the temp tree; the empty, mismatch and match cases for gate_run and ql_rerun, with scores.jsonl unchanged.
  - **A3:** a bad field lists the 3 new fields and leaves the file unchanged; the new fields can be set; stage_since is only set when the stage changes.
  - **A4:** refusal on mismatch and on empty sha creates no work dir; dry-run leaves the real Output_RFP, jobs, Tasks_INPUT and registry snapshots unchanged and writes only under /tmp; a real copy into the fake root matches the staged copy and has a full backup.
- Auto tests: before `Ran 46 tests in 0.431s OK`, after `Ran 46 tests in 0.470s OK`.

## Choices made
1. CLI: issue.py keeps its positional form `SLUG KIND DRAFT OUT`. The plan's flag form was adapted in the verify commands.
2. The time box resets on a stage change through the new `pipeline.stage_since`, which status.py stamps. Tasks without it fall back to REGIME until their next `stage=` set.
3. Only qc and harden are gated by `pushed` + passed. fix is not refused after PASS: plan v2 wins over the R1 draft.
4. The tree-sha refusals also run in dry mode, so a dry run shows exactly what `--apply` would do.
5. A regrade row's `valid` depends only on `--ayush-ok`. The live/author-note checks still print, but they do not decide its validity.
6. intake's HARNESS path is now based on the file's own location (`MT/../Terminal_2.0_Harbor_Harness`). The value is the same as before, because ROOT was already `HERE.parent`.

## Needs master
- Run `status.py set cold-chain-backbone-quote tree_sha=8ca9c267f59b` (A3 backfill). Until then, a real `gate_run` intake on cold-chain is refused, which is expected. Also set `tree_sha` for sentinel (`583e77e1ae94`, Tasks_INPUT) and district (`e9d91966ed25`) if wanted.
- To open and close a QL round: `status.py set <slug> ql_round=N ql_last=open`, then `ql_last="closed <TS> <path>"`.
- The rule text (C1/C2/C3/A7) was not touched.

## Rollback
```
cp OUT/bak/issue.py  MT/tools/issue.py
cp OUT/bak/intake.py MT/tools/intake.py
cp OUT/bak/status.py MT/tools/status.py
rm MT/tools/repackage_one.py; rm -r MT/tools/tests
```
The registry was never changed, so it needs no rollback. `stage_since` keys only appear after someone sets a stage with the new status.py. The old tools ignore that key.
