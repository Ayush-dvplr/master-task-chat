# Round notes for every rebuild / harden prompt issued 22 Oct 2026 (master chat, 10:20 IST)

Every P4 / P9 prompt issued on 22 Oct tells you to read this file in full. It holds the rules that apply to all four bundles. Your own prompt holds the bundle-specific fixes. If this file and your prompt disagree, stop and report the conflict.

## A. Upstream state (verified by the master, 22 Oct 13:00; updated from bfe40804)
- Harness clone HEAD = `c9e3454a` (15:00: commit c9e3454a adds QC H6/TS-30 and an owner-only oracle run in Step 10: `exe_copy.py --owner-only`; templates gain `_grant_read()` that chmods agent paths under /app before the uid drop. Use that same pattern for section C, and add the owner-only oracle run to gate D3). Previously `a74bda85`; fingerprints in `master_chat_tasks/knowledge/fingerprints/` are at `a74bda85` (older set in `fingerprints/archive_bfe40804/`). The three commits after bfe40804: 2690e960 restores `chmod 755`; a72c20a4 removes `playground.py` and `task_memory.py` and aligns `validate_bundle.py` with the QC; a74bda85 adds tests_qc K8 (litellm pin). Do NOT stop with UPSTREAM CHANGED for these four commits; stop only if the HEAD is newer than f3765e67. UPDATE 16:00: HEAD must be `f3765e67` (Ayush pulls). Two later QC commits also bind you: d9f94333 judge.toml `[judge]` `mode = "batched"` (judge_qc G2 FAILs on `individual`), and f3765e67 H6 skips interpreter switches. QL rule: QC against ALL `Input_Bundle_QC/` changes since 2690e960 (`git -C <clone> diff 2690e960 HEAD -- Input_Bundle_QC/`) and fix every issue before any trajectory; list each changed check with PASS/FIXED in your report.
- UPDATE 23 Oct 15:55: approved HEAD is now `71a653b2` (after 3fb1650b T14 author name, and 71a653b2 structure_qc S3/S5: a root `trajectories/` dir and run records inside it warn instead of fail; FORMAT_SPEC.md says the same). Fingerprints in `fingerprints/` are re-hashed at 71a653b2 (previous set in `fingerprints/archive_3fb1650b/`). Do NOT stop with UPSTREAM CHANGED for 3fb1650b or 71a653b2; stop only if HEAD is newer than 71a653b2 or a hash differs from the 71a653b2 set.
- `knowledge/qc_authoring_checklist_9b8229f6.md` is stale: read the live QC files instead, matching IDs on ID + wording.
- What the live QC/generator wants: judge annotations exactly `mode, type, evaluation_target, importance`; no `authored_by/status/archetype/generator_seed/trailer_token` in TRUTH.md; `tests/test.sh` uses `chown root:root /logs/verifier` + `chmod 755 /logs/verifier` (keep 755; 700 now WARNs in H5 and breaks Harbor's reward read on Linux; Ayush Q39); `tests/Dockerfile` pip line is exactly `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` (tests_qc K8 FAIL without the litellm pin; never 1.107.0); named input dirs under `environment/` (repo-patch = `environment/repo` + `environment/ci`).
- Full diff: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_upstream/UPSTREAM_DIFF.md`.

## B. Why we are rebuilding (real evidence, 21-22 Oct)
- Real claude-opus-5 runs on our tasks: emberforge 94.19 tests / 84.21 rubric; vendor-archive 88.97 / 100; schema-migration 99.3 / 69.57; district-heat timed out twice at 7200 s. Our hand-written careful solvers (S4) predicted 0.17-0.65 and were wrong by 0.25-0.77.
- A study of 10 team tasks that scored below 30% (7 of them genuinely) found what makes a frontier agent fail. Read section 6 of `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/SYNTHESIS.md` in full; its 13 rules are binding for this round. The short version:
  1. Never state how many rules, defects, conventions or traps exist (no "fifteen rules", "four conventions").
  2. Never list trap topics in the final-reply ask; ask for computed figures instead.
  3. Do not name the evidence files that decide a rule; name the authority doc and let it point at "the records".
  4. Put at least one load-bearing rule in a scope-by-omission sentence ("for every other X") or split it across two files (field named in one, defined in another). It stays fully documented.
  5. Give one rule a decoy default (a plausible legacy doc or shipped default) that the authoritative record contradicts on a rare boundary the shipped data shows.
  6. Route that rule through a dependent chain and grade whole downstream documents on regenerated hidden inputs. Rule-isolating checks: at most about 30% of the test weight.
  7. Do not ship anything that confirms the full answer (calibration slice with settled outputs, worked full examples, visible tests that reveal values). Ship evidence that decides each rule; identities the agent can check (conservation, row counts) must still hold under the wrong reading.
  8. Every graded unit must be identifiable from shipped files.
  9. The grader must work on an editor-written 0600 file (section C).
  10. Cheat detectors must stand down when the program did not run cleanly.
  11. Checks that only read the shipped-data outputs: at most 5% of the test weight.
  12. Judge: one figure per criterion, each needing the full chain and absent from every file; one honesty negative for a claimed validation the trajectory does not show; no multi-figure criteria; no criteria that echo doc sentences.
  13. Never byte-compare a serialization the docs do not state.
- Hard limits that still apply: QC must pass; every graded rule stays documented in visible files (no hidden rules); no volume, arithmetic, puzzle or formatting difficulty. The instruction stays plain and short and states the end state, not a procedure.

## C. Verifier permission fix (mandatory, all four bundles)
Harbor keeps file modes when it copies the agent's files into the verifier. The OpenHands editor writes files 0600. Any test that runs agent code as another uid (setpriv/nobody/4001/65532) must, before dropping privileges:
- copy every agent program it runs into a grader-made temp folder and `chmod 0644` the copy (folders `0755`), or `chmod a+r` the program and `a+rx` every parent folder; and
- make every grader temp input readable by that uid (files `0644`, folders `0755`; a folder the agent program must write into: `0777` with the sticky bit or a per-run folder owned by that uid).
- Kill leftovers by uid as well as by process group: `killpg` misses a child that called `setsid()`.

## D. Gates for today (Ayush decision Q29, option C, TEMPORARY for 22-23 Oct)
No build-time hardness solvers this round (no S2/S3/S4/shortcut runs; do not spend time on them). After your edits, run once each:
1. The 4 QC scripts: 0 FAIL. WARN above 35 checks is fine (cap 70).
2. For generator bundles: `validate_bundle.py --archetype <archetype>`: 0 FAIL (`playground.py` no longer exists; skip it). For emberforge (converted, no archetype) these are advisory only (open Q23); report them, fix only cheap ones.
3. `exe_copy.py` (it drops the OpenHands SDK, builds in seconds), then in Docker, tests only: oracle x2 = 1.0 both times; nop x1 = 0.0; and one extra oracle run whose `solve.sh` ends with `chmod 600` on every delivered program, which must also be 1.0 (proves section C).
4. Tests-channel forgery: delivered outputs written from the docs with no working program. Report its score; target 0.05 or less.
5. The judge cannot run here (no API key). Check every criterion against B.12 by reading, and report it as "judge not run".
Docker: at most 2 Docker runs at once on this Mac; each run under nohup with a log; never wait on one command longer than 4 minutes.
Then stop. Ayush runs the PL QC and 1 real trajectory himself.

## E. Working rules
- Edit the bundle in place; never regenerate, never `--force`.
- The `_work/<slug>/` build scripts (make_judge.py, judge_build.py, make_truth.py, TRUTH.src.md, embed.py, datagen.py ...) still emit the old format and old data. Either update them and regenerate from them, or edit the bundle directly and mark the scripts stale in `_work/<slug>/README_STALE.md`. Never run a stale script.
- After any edit to input data: re-embed `_SHIPPED_DATA`, recompute `reward.toml` (`0.5/P` per channel at full float precision), update every sha256 in TRUTH.md (common rule 6).
- Compaction safety: keep `_work/<slug>/TODO.md`, `PLAN.md` and `LOG.md` current after every step (common rule Always 5). After a compaction re-read your prompt file, this file, then TODO.md, and continue from the first unticked item.
- Write your report as each gate finishes, not at the end.


## Kill-by-uid caution (master 20:45, from S10/S11 Docker runs)
kill-by-uid hits every process of that uid, including other checks running in parallel: the first oracle runs scored 0.11-0.28. Serialise every check that runs agent code under the dropped uid (a file lock around each run) or kill only the run's own process group/session. Re-check oracle x2 after adding it.


## F. Defence, cross-reference and result files (master 21:40, Ayush 21:29; binding for every session that starts after 21:40)
- `_work/<slug>/QC_DEFENCE.md`: one entry per lever and per deliberate design choice: what it is, why it is there (which wrong reading it punishes), which QC check it could trip, why that is not a defect (quote the rule), and the safe fix if QC insists (one that keeps the difficulty). Write it as you design; it is how the later fix session tells a false positive from a real defect.
- `_work/<slug>/XREF.md`: a ```json block `{"entries":[{"key":"","value":"","files":[...],"retired":[...]}]}` listing every value that appears in more than one file (task name, slug, file/folder names, field and key names, stated figures, check IDs, judge figures). After every edit: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" "<bundle>" "<_work>/XREF.md"` must print 0 findings before the gates. On a rename or changed value update every listed file and move the old value to `retired`. Never rename the slug or the bundle folder (the harness queue matches by folder name).
- `OUT/result_<sha>.json` (sha = the board id in your prompt; if your prompt has none, use `nosha`): {"sha":"","slug":"","step":"","status":"DONE|STOPPED","report":"<path>","qc_fail":N,"oracle":[],"owner":x,"nop":x,"forgery":x,"isolated_share":x,"xref_findings":0,"tree_sha":"<first 12 of sha256 over sorted paths+contents>"}. It must parse.

## G. Docker and name clash rules (master 21:40)
- Never pass `--delete` to harbor: it runs `down --rmi local` and deletes the `hb__<content-hash>` image that another session's copy of the same bundle may be using. Never prune images (only the master's idle cleanup, Q32).
- Bundle lock before any Docker work: `mkdir -p /tmp/opencode-logs/locks && mkdir /tmp/opencode-logs/locks/<slug>.lock`; if it exists, another session is running Docker on this bundle: `sleep 200` and retry (max 30 minutes, then report). Remove it after your last run.
- Unique folder names: TS = `$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)` in every /tmp path.
- Max 2 Docker-heavy jobs on this Mac across all sessions and the harness queue: check `docker ps` before launching; wait if 2 task containers are up. Never stop, remove or kill another session's containers, processes or folders.
- Kill-by-uid inside the verifier only kills processes in its own container; still serialise checks that drop to the same uid (section "Kill-by-uid caution").

- Docker runs strictly one after another (master 21:40, from e0841ac): two runs started a minute apart both built the same `hb__` verifier image and sat at 0% CPU for 12+ minutes. Chain every harbor run in ONE nohup chain, each starting only after the previous ends; never start a second chain on the same bundle.

- Warm the verifier image once before any harbor run (master 21:46): Docker's network is slow (pip ~68 kB/s), so a cold verifier build passes Harbor's 900 s limit (`EnvironmentStartTimeoutError: Verifier environment start timed out`). Before the first harbor run, build the bundle's verifier image yourself, outside Harbor's timer: `cd "<copy>/tests" && nohup docker build --progress plain -t warm-<slug> . > <logs>/warm.log 2>&1 &`, poll until it ends (waits under 4 minutes; it can take 20-30 minutes cold, seconds when cached). Harbor then reuses the cached layers. Do the same for `environment/` if its build is slow. If `docker images` already shows a recent build for the same FROM + pip line, skip it. Never prune the build cache. If a harbor run still times out after warming, stop and report; never retry in a loop.
