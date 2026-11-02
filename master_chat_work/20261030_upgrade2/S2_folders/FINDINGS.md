VERDICT: Keep the master control repository isolated, defer physical moves until all sessions are idle, and delete nothing solely because it is old.

## 1. Folder inventory

**Finding.** `INVENTORY.csv` has 200 entries: 21 root entries (20 directories, 1 file) and 179 entries one level below `master_chat_tasks`, `master_chat_work`, `QC`, and the harness. Each row has `du -sh`, KiB, regular-file count, oldest/newest regular-file mtime, inferred purpose/writer, static reference locations, and reader status. These are measurements at scan time; the tree is live. The inventory script walks regular files and calls `du -sk` and `du -sh` for each row (`scripts/inventory.py`). At 30 Oct ~22:45 IST the root included `master_chat_tasks` 9.0M, `master_chat_work` 1.8G, `QC` 272M, harness clone 2.5G, `Anubis_Tasks_Samples` 4.3G, `anubis-stage-1` 2.1G, and `anubis-stage-2` 2.8G (`INVENTORY.csv`, level=1). Static references establish a possible dependency, not a runtime read; rows with none are marked UNVERIFIED. `rg -l -F` over master control and harness scripts found 347 files naming `master_chat_work/bundles`, 147 naming `QC/copies`, and 111 naming `jobs/` (commands in terminal readout; archived files included).

**Recommendation.** Use the CSV as the migration checklist and remeasure just before changes. Keep all separately owned folders in place. **Gain:** a bounded move scope. **Risk:** inferred owners and dynamic path construction can evade the static scan. **Verify:** owner review and a fresh inventory plus runtime path checks when no session is active.

## 2. Hard-coded path references

**Finding.** `PATH_REFS.csv` records 1,030 quoted filesystem-looking path strings with source line: 543 absolute, 345 relative, 142 variable-based (`python3 scripts/path_refs.py` output). It covers `tools/`, `auto/`, `prompts/templates/`, `AUTO_POLICY.md`, and harness `scripts/`; excludes vendored `.venv`. It is a conservative candidate index, not proof every dynamically assembled path has been found. Current code derives project location from the file: `master_chat_tasks/auto/auto.py:52-59` uses `HERE.parents[1]` to find the harness and board; `master_chat_tasks/tools/issue.py:38-39` derives `ROOT=HERE.parent`. Moving control under `master/` would silently change those defaults. Current templates encode absolute old destinations: `master_chat_tasks/prompts/templates/P2_build_v4.md:43-44` and `P11_full_qc_v3.md:17,25`.

**Recommendation.** Add one explicit path map/configuration to master tools, auto mode, and prompt issuance, then migrate templates and check every `PATH_REFS.csv` row before any physical move. **Gain:** future moves become a config change. **Risk:** stale issued prompts remain valid only if old paths keep resolving. **Verify:** path-resolution checks for all control commands and already issued prompt paths against the old and new locations.

## 3. Proposed layout and migration order

**Finding.** Existing folders cannot be consolidated safely during active work: `auto.py:54-59` derives sibling paths and issued prompts embed absolute paths. The harness is its own Git checkout (`find TB -maxdepth 2 -name .git` found `.git` in harness, `Anubis_Tasks_Samples`, `beta-task-generator`, `anubis-stage-1`, and `anubis-stage-2`). `QC/PATH_MAP.md:1-3` documents an earlier move and warns issued prompts retained old paths.

**Target tree (maximum three levels; proposed, not created):**

```text
Terminal Bench/
  master/
    control/       # private Git repo: tools, prompts, knowledge, records
    work/          # session outputs and working task bundles; local only
    qc/            # QC reports and frozen copies; local only
  master_chat_tasks -> master/control   # compatibility link
  master_chat_work  -> master/work       # compatibility link
  QC                -> master/qc         # compatibility link
  Terminal_2.0_Harbor_Harness/          # separate checkout; do not touch
  anubis-stage-1/, anubis-stage-2/      # other repos; do not touch
  Anubis_Tasks_Samples/                 # other repo; do not touch
  beta-task-generator/                  # other repo; do not touch
  other root folders/                   # ownership review; do not touch
```

**Migration order.** (1) Create the private repository at the *existing* `master_chat_tasks` root first; no root move required. (2) Introduce a single configurable path map while old paths are authoritative; update tools, auto, and templates; leave issued prompts intact. (3) Audit `PATH_REFS.csv` and test both path maps in an isolated copy. (4) Stop new issuance and wait until workers, QC, and harness jobs are idle; verify no active process has an old working directory. (5) Copy and checksum master-owned trees to target; switch old names to compatibility symlinks only in the idle window, then validate read/write paths before resuming. (6) Retain the links until every issued prompt and external reference is retired. **Gain:** a clean root without forcing other repositories into the master repo. **Risk:** `Path.resolve()` follows symlinks and can alter sibling discovery; this must be fixed in step 2. **Verify:** smoke checks for issue/intake/auto path resolution, prompt rendering, QC copy/report destinations, and harness queue status before resuming work.

## 4. Cleanup policy and measured space

**Finding.** `python3 scripts/cleanup_measure.py` measured top-child disk usage and age from the newest regular-file mtime on 30 Oct. Age is not a safe deletion test. Values below are **upper bounds before reference/ownership checks**, not approved reclaimable space. `du -sh` separately measured the live opencode DB at 4.5G. `/tmp/oracle-qc` was empty; `/tmp/harbor-jobs-qc` held 18M. Ayush's session prompt reports macOS temporary-file eviction after three idle days and a 30 Oct reboot wipe; those system behaviors were not independently verified here.

| Type | Current measured size | Proposed rule | Age-qualified now | Safely deletable now |
|---|---:|---|---:|---:|
| Harness `jobs/` | 179,748 KiB, 26 dirs | Keep raw run 14 days after final intake **and** verified durable archive; keep score/manifest and referenced run forever | 0 KiB at 14 days; 6,412 KiB at 7 days | 0 verified |
| `gate_run_a*` copies | 60,052 KiB, 20 dirs | Keep 30 days after decision; retain any referenced run/trajectory or content-addressed archive forever | 0 KiB at 30 days | 0 |
| `QC/copies` | 271,700 KiB, 79 dirs | Keep referenced frozen copies forever; review unreferenced copies after 30 days | 0 KiB at 30 days; 69,680 KiB at 7 days | 0: all 79 IDs occur in QC reports and master root JSON/JSONL (`python3 scripts/qc_refs.py`: `copy_dirs 79 in_reports 79 in_master_records 79 in_neither 0`) |
| `/tmp/oracle-qc` | 0 KiB | Clear only after QC report and no live process, ideally within 24 h | 0 | 0 |
| `/tmp/harbor-jobs-qc` | 18,464 KiB, 5 dirs | Clear after report/score archive and no live process, ideally within 24 h | 0 at 7 days | 0 verified |
| `bundles/_work` | 1,400,596 KiB, 26 dirs | Review 30 days after task pushed/parked; keep work explicitly cited by decisions or QC; archive unique evidence | 0 at 30 days; 11,380 KiB at 7 days | 0 verified |
| Old issued prompts | 5,524 KiB, 38 task dirs | Keep issued prompt text forever as provenance; only generated duplicate copies may go after 30 days | 0 at 30 days | 0 |
| Live `opencode.db` | 4.5G (`du -sh`) | Never manually delete/vacuum while live; plan an export and supported retention process in a separate idle maintenance step | UNVERIFIED | 0 verified |

**Recommendation.** Implement a dry-run retention report that resolves board SHA, task stage, decisions, QC reports, and pushed-task manifest before marking any object disposable. Preserve record text and checksums forever; if large bytes are moved to an archive, keep a verified content-addressed pointer. **Gain:** potential future recovery of bulk work and run storage; currently **0 bytes are proved safe**. **Risk:** deleting a referenced copy breaks QC and decision reconstruction. **Verify:** dry-run report shows zero protected IDs, archive hash matches, and task reconstruction succeeds before any deletion.

## 5. Private Git repository

**Finding.** `master_chat_tasks` has no `.git` at depth 2 (`find` result above). A repo rooted there cannot include sibling `master_chat_work`, `QC`, harness, or teammate folders through normal `git add .`. Candidate allowlist: control code (`tools/`, `auto/` except `runs/`), prompt templates and issued text, `knowledge/`, `registry/`, README/GOALS, board/state/open questions, decisions/feedback/lessons. `python3 scripts/repo_scan.py` measured **631 regular files, 6,734,167 bytes** for that allowlist, excluding `pending.db`, `log.jsonl`, and `auto/runs/`; generated `.gitignore` excludes additional secret/binary patterns. Secret-keyword scan with `rg -n -i -e 'key|token|secret|password|sk-'` over the candidate paths, omitting the same runtime files, yielded **991 file:line locations** in `SECRET_SCAN_RG_LOCATIONS.txt` (values deliberately omitted). This is broad triage, not clearance. Additional `rg -l` checks found 0 files matching private-key header, AWS key ID pattern, or GitHub token pattern; 37 files matched the broad `sk-` substring. No secret values were printed.

**Recommendation.** Use the draft `.gitignore` and `REPO_PLAN.md`; stage from a positive allowlist and review staged paths plus a credential scanner before the first push. Never put bundles, jobs, trajectories, QC copies, Docker data, live DB, secrets, or large binaries in the repo. Commit only quiescent snapshots of mutable board/registry/state files. **Gain:** a small, recoverable, pullable control repo with zero sibling folders in its worktree. **Risk:** sensitive text could be embedded in prompts/records despite the pattern scan; concurrent pulls can conflict with live state. **Verify:** `git status --short` shows only allowed paths, clean secret review, fresh clone reproduces control tools and required state, and no active writer during pull.
