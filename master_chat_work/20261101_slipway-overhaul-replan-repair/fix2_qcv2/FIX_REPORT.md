# FIX_REPORT: slipway-overhaul-replan-repair, fix v2 (board b20fdca)

Route 1 (Ayush 1 Nov 22:33, "3. A"): fix the fail TS-24 and the minor DS-22, keep TS-20 and TS-23 as warns, then QC v3 recheck.
Status: DONE. Fixed TS-24 (and TS-28/F0c/CL-2/AL-11/AL-13, which share its root cause) plus DS-22/AL-18. Kept TS-20 and TS-23.
Bundle tree b13e6ae6acc3 -> 2f83a9bd6a10. Only two files changed: `tests/test_output.py` and `solution/TRUTH.md`.

## Finding 1: TS-24 (also TS-28, F0c, CL-2, AL-11, AL-13). The expected documents could be read and replaced in /tmp

The QC kit playbook (QC_FIX_PLAYBOOK_v3) has no TS-24 row. I fixed it the way master note 2 says, by its DO: keep the expected answers and graded inputs private, and leave `_stop_untrusted`, weights, check names and graded facts unchanged.

The bug: `_reference` and `_held_reference` wrote each round's 25 expected documents into `_scratch(...)`. That is `/tmp/slwopt-reference-*` or `/tmp/slwopt-held-reference-*`, made 0777 with files 0644 and never removed. So the engine, running as uid 65534, could glob them and copy them out.

Changes in `tests/test_output.py` (sha256 cf26ba084ebd -> f3d9d92b9fbc; 72 diff lines; the 49 `criteria.` registrations are byte-identical):

| place (new line) | old | new |
|---|---|---|
| `_private(tag)` :5012 (new helper) | - | `Path(tempfile.mkdtemp(prefix="slwopt-"+tag+"-"))`, left at 0700 root |
| `_scratch` :5004 | 0777 helper, used for everything | kept 0777, now used only for the engine's destination parent and home (docstring says so) |
| `_reference` :5055-5068 | `out = _scratch("reference")`; `ref_publish(...)`; cache bytes; dir left in /tmp | `out = _private("expected")`; `try:` ref_publish + cache bytes `finally: shutil.rmtree(out)`, so it is gone before any engine run |
| `_held_reference` :5228-5239 | `out = _scratch("held-reference")`, same as above | same as `_reference` (`_private("expected")`, cache, rmtree) |
| `_public_copy` :5037-5045 | filled a `_scratch` 0777 dir, then sealed it | filled `_private(tag)` (0700), then `_seal` (0755/0644), so it is never writable |
| `_engine_root` :5135-5145 | extracted the zip into `_scratch` 0777 | extracted into `_private("engine")`, then sealed |
| `_drive` :5161-5205 | returncode check, data tree digest and output readback after the lock | all three now run inside `with _RUN_LOCK:`, after `_stop_untrusted`, so no later run can rewrite the output before root reads it |
| `test_delivered_shipped_suite_unedited` :5340-5346 | shipped `test_visible.py` copied into `_scratch`, never removed | `_private("shipped")`, bytes read, then rmtree |
| renamed-round test :5761 | parent dir `_scratch` 0777 | `_private("renamed")`, copytree, `_seal(parent)` |
| ambient test :5772 | `_scratch("ambient")` 0777 | unchanged: it is bait for the negative training-corpus detector and holds nothing graded |

### Path audit (every path the verifier creates before or during an engine run)

The verifier runs as root. The engine runs as uid 65534 (`_demote`), one run at a time under `_RUN_LOCK`, in its own session, and is killed by `_stop_untrusted`.

| path (creator, line) | holds | owner / mode | run user read | run user write | change |
|---|---|---|---|---|---|
| /tmp/slwopt-private-* (`_private_corpus` :5031) | private round papers every expected set is built from | root 0700, kept | no | no | none (already private) |
| /tmp/slwopt-expected-* (`_reference` :5061, `_held_reference` :5232) | the 25 expected documents of a round | root 0700, removed in `finally` before return | no | no | was 0777 with files 0644, never removed |
| /tmp/slwopt-corpus-*, slwopt-held-* (`_public_copy` :5040) | public round the engine reads (graded input) | root, filled at 0700, then sealed 0755/0644 | yes (by design) | no | was 0777 while being filled |
| /tmp/slwopt-engine-* (`_engine_root` :5139) | extracted delivered engine | root, filled at 0700, then sealed 0755/0644 | yes (it must import) | no | was 0777 while being filled |
| /tmp/slwopt-shipped-* (:5340) | shipped test_visible.py | root 0700, removed after read | no | no | was 0777, never removed |
| /tmp/slwopt-renamed-*/papers_under_another_name (:5761) | round under another name (graded input) | root, parent sealed 0755/0644 | yes (by design) | no | parent was 0777 |
| /tmp/slwopt-<tag>-*/destination (`_drive` :5172) | engine output | parent root 0777 (the engine must create the destination) | yes | yes | output now read inside `_RUN_LOCK` after `_stop_untrusted` |
| /tmp/slwopt-<tag>-home-* (`_drive` :5173) | HOME, TMPDIR and cwd of the run | root 0777 | yes | yes | none (holds nothing graded) |
| /tmp/slwopt-ambient-* (:5772) | cwd bait for the training-corpus detector; its data/ is sealed | root 0777 | yes | yes (parent) | none; tampering with it can only keep a negative detector silent, and an honest engine keeps it silent too |
| /tmp/slwopt-withdrawn-* (`_write_withdrawn` :3716) | withdrawn publication while a corpus is written | root 0700, removed | no | no | none |
| /logs/verifier (test.sh:7) | reward.json | root 755 | yes | no | none |
| /tests (test.sh:8) | verifier code | root, go-rwx | no | no | none |
| /app/out | agent deliverables | agent | n/a | n/a | none |

### Attack proof (Docker, tests-only copies made by the live kit exe_copy.py)

Each attack copy is the plain copy with a trailer added to `solution/solve.sh`. The trailer swaps `slwopt/__main__.py` inside `/app/out/patched_engine.zip` for the attack program and blanks the 25 `/app/out` documents, so honest answers cannot score.
- **lift**: reads `round_key` from `--data/round_header.json`. It globs `/tmp/slwopt-*` and `/tmp/slwopt-*/*` for a directory whose `01_identifier_canon.json` has the same `round_key`, and copies the newest match to `--out`.
- **overwrite**: writes placeholders to `--out`, then spends 5 s writing placeholder bytes into every writable `/tmp/slwopt-*` directory that is named reference/expected or holds `01_identifier_canon.json`.

I ran each attack against the old (QC v2) `test_output.py` and against the new one:

| lane | tests | reward | net /112 | verifier s |
|---|---|---|---|---|
| lift-old-1 | v2 (cf26ba08) | 0.6696 | 75 (pos 78, neg -3) | 161.4 |
| lift-new-1 | fixed (f3d9d92b) | 0.0 | 0 (pos 3, neg -3) | 149.4 |
| overwrite-old-1 | v2 | 0.0 | 0 (pos 3, neg -3) | 241.1 |
| overwrite-new-1 | fixed | 0.0 | 0 (pos 3, neg -3) | 210.9 |

- **lift on the old tests scored 75/112**, close to the 79/112 that QC v2 predicted. On the old tests the attack took all 12 package_crosswalk checks plus 6 state, cascade and probe checks.
- **On the fixed tests it scores 0/112**, which is the stub band. The same attack program worked on the old tests, so the zero shows the leak is closed and does not mean the attack is broken.
- **overwrite scores 0 on both versions.** The v2 tests already cached the expected bytes before any engine run. The fix removes the files as well, so there is nothing left to overwrite.

## Finding 2: DS-22 / AL-18. TRUTH.md cited the wrong source

Playbook DS-22 DO: rewrite TRUTH.md to match the shipped code and data, with sha256 values written by script as the last edit (G6).

| line | old | new |
|---|---|---|
| solution/TRUTH.md:62 | `seeds no cell is classified inert (the instruction), the round's weighted` | `seeds no cell is classified inert (output_schema_reference.md), the round's weighted` |
| solution/TRUTH.md:113-117 (was :113-115) | `...killed once it exits; the reference of every round is built beforehand from a private copy the run user cannot write.` | `...killed once it exits. The expected documents of every round are built beforehand from a private copy, in a directory only root can open, held in memory and removed before any engine run; the engine reads a sealed copy it cannot write, and its output is read back before the next run starts.` (now matches the fixed code) |

- I checked every other citation in TRUTH.md against its source and all are valid: (p02) EDG-SELF/UNKNOWNJOB p02:11-12,22; (p01) crosswalk p01:20-21; (p13) inverse p13:14; (p10,p11) twelve places p10:29; (the schema reference) aliases_active schema:12; (judge R2).
- `grep "the instruction"` now matches only TRUTH.md:73, "The instruction points at all three". That line is valid because instruction.md:5 says "Read all three".
- The sha256 lines were rewritten by script as the last edit; the values did not change (fix_patch_sha256 0419c9b5..., solve_py_sha256 101a83ec...). TRUTH.md sha256 6c41bba1 -> 08d06cbe.
- xref_check: 11 entries, **0 findings** (WORK/XREF.md).

## KEPT (OUT/KEPT.md, copied unchanged from fix1_qcv1/KEPT.md)

| id | where now | why kept |
|---|---|---|
| TS-20 | tests/test_output.py:6065-6076 (12 `package_crosswalk_*_exact`, weight 5 each = 60/112 = 53.6%) | route 1 keeps it as a warn; see KEPT.md |
| TS-23 | tests/test_output.py:6045-6093 (49 registrations: 32 positive = 112, 17 negative = -63) | route 1 keeps it as a warn; precheck reports it as WARN A3 49 > cap 35 |

The line numbers in KEPT.md (:6021-6069 / :6041-6052) are from fix1. My edits moved the block down by 24 lines, and the registrations themselves are byte-identical.

## Static gates (live kit 5574d77e)
- `structure_qc`, `instruction_qc`, `tests_qc` and `judge_qc` all exited 0 with 0 FAIL.
- Warnings: WARN A3 (49 checks > 35, which is TS-23, kept) and WARN X1 (binary files, unchanged).
- NOTE DS-22 TRUTH.md:337 `fix_patch_sha256` has no file of that name. This was there before my edits.
- precheck.sh last line: **`PRECHECK CLEAN`**.

## Docker lanes (fix2-2237/lanes, `--memory 8g --cpus 4`, dockfree START=yes before each, ALL_DONE 23:32)

| lane | copy | reward | net /112 | verifier s |
|---|---|---|---|---|
| oracle-1 | plain | 1.0 | 112 | 131.6 |
| oracle-2 | plain | 1.0 | 112 | 159.2 |
| oracle-3 | plain | 1.0 | 112 | 166.0 |
| owner-1 | --owner-only | 1.0 | 112 | 171.7 |
| nop-1 | plain, nop agent | 0.0 | 0 | 151.5 |
| stub-1 | --stub | 0.0 | 0 | 159.4 |
| forgery-1 | plain + echo forgery | -0.0089 | -1 (pos 4, neg -5) | 260.6 |
| lift / overwrite | see attack table | 0.0 (new tests) | 0 | 149.4 / 210.9 |

- The slowest verifier run was 260.6 s, which is 4.8% of the 5400 s limit (the cap is 90%).
- Every lane copy carried tests sha f3d9d92b9fbc, the same file as the bundle.
- All lane logs and the summary are in `/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix2-2237/lanes/logs/`.

## a3 program
The fix1 method (diag2.py + score.py) on the final tests gives `d_a3_program tests 52/112 = 46.43% lever 0/60`, unchanged (fix2-2237/a3_score.txt).

## Digests
- Unchanged: instruction.md 0c91175d, tests/judge.toml c0e15264, tests/reward.toml f3d79a9f, tests/test.sh 5302b9b8, tests/Dockerfile 1d197d71, task.toml 381a4dbd, environment/Dockerfile efd9f88b, solution/solve.py 101a83ec, solution/solve.sh 0419c9b5, and all 58 environment/data files (including the docs).
- Changed: tests/test_output.py, solution/TRUTH.md.
- Full lists are in WORK/fix2/digests_before.txt and WORK/fix2/digests_after.txt.

## Tree / sync
- BUNDLE b13e6ae6acc3 -> **2f83a9bd6a10**.
- Tasks_INPUT synced with `rsync -a --delete`: 2f83a9bd6a10; `diff -rq` is empty; no `__pycache__`.

## Not run
- The LLM judge, because tests/judge.toml is unchanged.
- Paid agent attempts.
- The QC kit itself (QC v3 is the master's step).

## Lessons for the master
- Anything the verifier writes to a world-readable /tmp dir before an engine run is an answer key. Default to private dirs and `rmtree` them, and only open up what the engine must read (sealed) or write.
- When proving a leak is closed, run the same attack against the old tests too. A real score there (75/112) shows the 0 on the new tests is the fix and not a broken attack.
