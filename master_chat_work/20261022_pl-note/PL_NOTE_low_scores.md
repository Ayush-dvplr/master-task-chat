# Pass@1 grading bug: 4 tasks score low because the verifier cannot read the agent's program

Date: 22 Oct 2026, 12:20 IST. Author: Ayush Sah.
Repo: `ShreeyankDoliya/Anubis_Tasks_Samples`, checked at remote HEAD `048319d5` (22 Oct, 11:50 IST). All 4 task folders are unchanged since they were scored.

## 1. The issue in one paragraph
The agent writes its program with the OpenHands `file_editor` tool, and the file ends up with mode 0600 (owner-only). The verifier then drops privileges (`setpriv nobody` or uid 65532) and runs that program without chmod-ing it or copying it first. Python cannot open the file, so every check that runs the program fails, even when the program is correct. QC does not catch it because the oracle's `solve.sh` uses `cp`, which leaves a readable file, so the oracle still scores 1.0.

## 2. Root cause

Three things combine. Each one is harmless on its own.

| # | Link in the chain | Evidence |
|---|---|---|
| 1 | **The agent's editor leaves the program at 0600.** The editor writes through a temp file in the same folder and then renames it. Temp files made that way (`tempfile.mkstemp`) are created at 0600. *The temp-file mechanism is inferred, not read from the OpenHands source.* | The trajectories list the file as `-rw-------` (§3a). The temp-file write shows up in task 09, step 29: `Errno 2 ... '/app/out/.crownsettle.py.xemhsv2b.tmp'` |
| 2 | **Harbor 0.24 keeps that mode** when it hands the agent's `/app` files to the verifier. | Docker replay with the files at 0600 reproduces the recorded check results exactly (§3d) |
| 3 | **The verifier runs the program as another user without making it readable.** These verifiers do chmod the inputs, the work folders and the output folders, but never the program file. | `tests/test_output.py` lines in §3b |

**Why QC Step 10 passes anyway:** the oracle's `solution/solve.sh` copies `solve.py` into place with `cp`. This creates a normal 0644 file, so the oracle scores 1.0 and the bug is invisible until a real agent run:

| # | `solve.sh` line |
|---|---|
| 07 | `cp /solution/solve.py /app/derive_report.py` (:4) |
| 08 | `cp /solution/solve.py /app/out/optimize.py` (:6) |
| 09 | `cp "$SOLUTION_DIR/solve.py" /app/out/crownsettle.py` (:9) |
| 10 | `cp "$SOLUTION_DIR/solve.py" /app/out/reeferdispatch.py` (:9) |

**Why other Pass@1 tasks are not hit:** their verifiers make the program readable before dropping the uid:
- `grain-intake-settlement` uses `_grant_read(script)` (test_output.py:1204-1209, :1270);
- `speculative-decode-arbiter` stages a copy of the driver (:1850).

## 3. Evidence you can check on your system

Paths are relative to each task folder:
- run folder: `R = trajectories/claude-opus-5/run_1/`;
- test file: `T = tests/test_output.py`.

| # | Task folder (under `Pass@1/`) |
|---|---|
| 07 | `Sugam_Agrawal/Anjali_kumari/fdc5a20d-2dfe-5f64-a3fa-2c023318a760` |
| 08 | `Dinshi_Jain/Kunwar_Singh/registry-lock-footprint-resolution` |
| 09 | `Dinshi_Jain/Aditya_Patel/ninefold-crown-settlement-recompute` |
| 10 | `Dinshi_Jain/Swati_Sharma/reefer-power-dispatch-recompute` |

> Note: in the git checkout, `R/artifacts/app/...py` shows `-rw-r--r--` because git only stores 0644/0755. The 0600 mode is visible only in the trajectory listings and in a replay, not in the repo files.

### 3a. The agent's file was 0600 (trajectory)
Run from the task folder:
```
grep -oE -- '-rw-------[^"\\]{0,80}\.py' trajectories/claude-opus-5/run_1/agent/trajectory.json | sort -u
```

What this returns:
- **07:** `-rw-------. 1 agent agent 6896 Oct 19 17:33 derive_report.py` (step 13).
- **08:** `-rw------- 1 agent agent 41156 Oct 21 08:44 optimize.py`, plus `explore.py`, `plain.py`, `ringtest.py` and `search.py` (steps 24, 35, 36, 41). JSON files that Python wrote are `-rw-r--r--`.
- **09:** returns nothing. The trajectory never runs `ls -l` on the program, so the 0600 is proven by the replay in §3d. The program was written with `file_editor` `create` (step 31) and `str_replace` (steps 32-34, 40), the same tool as 07/08.
- **10:** written with `file_editor` `create`, the same tool. It was not replayed (see §4).

### 3b. The verifier runs the program as another user, without chmod (`T`)

| # | Uid drop and program path | What it chmods (never the program) |
|---|---|---|
| 07 | `_UNTRUSTED_UID = 65532` (:20-21); `_untrusted_kwargs()` returns user/group 65532 with umask 077 (:296-299); program `derive_report.py` (:439) | folders (:306, :313) and the input files (:331, :417, :1110) |
| 08 | `PROGRAM_NAME = "optimize.py"` (:1843); `_SETPRIV = ["setpriv","--reuid=nobody",...]` (:1865); program path (:1918) | `_open_dir` and the data tree (:1892-1901), the output folder 0777 (:1932) |
| 09 | `PROGRAM_NAME = "crownsettle.py"` (:45); `_SETPRIV` (:5810); `_untrusted()` (:5828); program path (:5922) | the work, ref and temp folders and the data (:5847-5877) |
| 10 | `PROGRAM_NAME = "reeferdispatch.py"` (:43); `_SETPRIV` (:5849); `_untrusted()` (:5857); program path (:5933); run at :5977 | the work root (:5875), cwd (:5898), the data (:5906-5910) and the output folders (:5967-5970) |

Quick check:
```
grep -nE "setpriv|65532|PROGRAM_NAME|chmod|_grant_read|copyfile" tests/test_output.py
```
Every `chmod` hit is a folder or an input file. None is the program.

### 3c. The failure pattern in the recorded results
`R/verifier/ctrf.json` has empty failure messages, so the evidence is the pattern of which checks fail:
- checks that only **read** the agent's output files pass;
- checks that **run** the program all fail, including checks that need only a clean exit.

| # | Checks that run the program (EXEC) | Checks that only read outputs (READ) | Other |
|---|---|---|---|
| 07 | 0/27 pass | 4/4 pass, incl. the independent derivation (weight 5) | `R/result.json` has `exception_info: RewardFileNotFoundError` |
| 08 | 0/27 pass | READ decode checks pass | |
| 09 | 0/19 pass, incl. 3 manifest checks that need only a clean exit | 8/8 byte-exact | a false -5 from `negative_hardcoded_sample_answers` (`_is_replayer`, :6370-6393), which fired because the program never ran |
| 10 | 0/9 pass | only 1 of 5 shipped blocks passes (the agent's outputs were already wrong) | |

### 3d. Docker replay (Harbor 0.24.0, QC Step 10 method, tests only)
**Method** (22 Oct, 09:19-09:24 IST [03:49-03:54 UTC]):
1. Build a tests-only copy with the QC kit:
   ```
   python3 <QC_FOLDER>/exe_copy.py "<task folder>" /tmp/<task>-replay
   ```
2. Replace `/tmp/<task>-replay/solution/solve.sh` with a script that:
   - copies the saved `trajectories/claude-opus-5/run_1/artifacts/app/` files into `/app` (the oracle agent runs as uid 1000, the same uid as the real agent);
   - then sets the modes. **V600:** every `.py` 0600, other files 0644. **V644:** every file 0644.
3. Run each variant once:
   ```
   harbor run --path /tmp/<task>-replay --agent oracle --env docker --job-name <task>-V600 -y
   ```
   Then repeat with V644. The oracle log of each trial shows the mode (`-rw-------` vs `-rw-r--r--`).
4. Compare the per-check results in each job's `verifier/ctrf.json` with the recorded `R/verifier/ctrf.json`.

| # | Recorded tests | V600 (agent's real mode) | V644 (readable) | Corrected overall (recorded rubric kept) |
|---|---|---|---|---|
| 07 | 15.69% | 15.69%, 0 of 35 checks differ from the record | 100%, 27 checks fail→pass | 25.49 → **67.65%** |
| 08 | 2.16% | 2.16%, 0 checks differ | 41.73%, all 11 `trap_*` checks fail→pass | 27.40 → **47.18%** |
| 09 | 15.29% | 15.29%, 0 checks differ | 100%, 19 checks fail→pass, false -5 gone | 29.18 → **71.53%** |

V600 reproduces each record check for check, so this is what the verifiers saw. V644 shows the agents' programs were correct (07, 09) or mostly correct (08).

### 3e. Minimal repro (about 10 seconds, any machine with Docker)
This mimics the editor (temp file + rename) and the verifier (`setpriv nobody`):
```
docker run --rm python:3.12-slim sh -c 'cd /tmp && python3 -c "import tempfile,os; fd,p=tempfile.mkstemp(dir=\".\",suffix=\".tmp\"); os.write(fd,b\"print(\\\"ok\\\")\\n\"); os.close(fd); os.replace(p,\"prog.py\")"; ls -l prog.py; setpriv --reuid=nobody --regid=nogroup --clear-groups python3 prog.py; echo "exit=$?"; chmod a+r prog.py; setpriv --reuid=nobody --regid=nogroup --clear-groups python3 prog.py'
```
Output on our machine (22 Oct, 12:17 IST):
```
-rw------- 1 root root 12 Oct 22 06:47 prog.py
python3: can't open file '/tmp/prog.py': [Errno 13] Permission denied
exit=2
ok
```

## 4. Effect per task
- **07 and 09:** the bug caused the low score. Graded correctly, both get 100% on tests and are not low scorers.
- **08:** the bug cost the 11 trap checks. The 16 held-out checks still fail for a genuine reason: the agent inverted the `quarantined_records` field.
- **10:** the bug is present (0/9 EXEC), but it did not cause this low score, because 4 of the 5 READ blocks were already wrong on the shipped data. Any future run whose program is saved at 0600 will be under-graded. Not replayed.

## 5. Fix
**In each verifier,** before dropping the uid, do one of these:
- run `chmod a+r` on the program and `a+rx` on its parent folders;
- or copy the program into a grader temp folder, make it readable, and run the copy (as `speculative-decode-arbiter` does).

**In 09,** the replayer negative should not fire when the program did not run cleanly.

**In QC Step 10,** add one oracle run with the program set to 0600 (e.g. `chmod 600` at the end of `solve.sh`), so this bug is caught before any trajectory.

## 6. Questions for the PL
1. Should 07, 08 and 09 be re-scored or re-run after their verifiers are fixed?
2. Should the authors of 07, 08, 09 and 10 patch their verifiers as in §5?
3. Should QC Step 10 add the 0600 oracle run?
