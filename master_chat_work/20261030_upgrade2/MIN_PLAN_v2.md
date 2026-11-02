# Minimum change plan v2 (31 Oct 2026) - VERIFIED, PLAN ONLY, nothing applied

Ayush (31 Oct): "1. keep 3 2. 3 GiB 3. ... first verify end to end then i will check and then when i say proceed then will be implemented".
So: oracle stays x3 (A-6 dropped), Docker headroom 3 GiB, nothing changes until "proceed".

## 1. Verification done (read-only, 31 Oct ~09:30)

| Plan item | What I checked | Result |
|---|---|---|
| D-1 slot rule | Where the "wait for a slot" rules really are | v1 cited the wrong lines. Real rules: `P11_full_qc_v3.md:77` (wait while 2+ harbor containers from other sessions, `sleep 200`, max 30 min, then start anyway), `AUTO_POLICY.md:47` (spawn at most 2 Docker-heavy workers), `knowledge/PROMPT_CHECKLIST.md:35` (max 2 Docker-heavy). P7/P9/P12 lines only describe the gate block. **Corrected below.** |
| D-1 memory numbers | Does each container carry a real memory limit? | Yes. Harbor sets `mem_limit = task memory_mb` and `cpus` (`harbor/environments/docker/__init__.py:55-57`); worker solver runs use `docker run --memory 4g --cpus 2` (`_COMMON_RULES_v5.md:48`). So `docker inspect` gives a true charge per container. Docker total: 16,746,086,400 B (15,970 MiB), 8 CPUs. Free for jobs = 15,970 - 3,072 = 12,898 MiB. |
| D-1 charge | v1 said task memory +50% | **Corrected:** charge exactly task.toml `memory_mb` (that is the hard cap Harbor gives the container; +50% would block an 8,192 MB task almost always). Containers with no limit count as 4,096. |
| D-1 vs paid runs | Does the harness queue see worker containers? | No: `master_queue.docker_budget` (`master_queue.py:249-259`) = Docker total minus 3 GiB minus its own runs. Not changed today. Effect: a paid run may start beside worker jobs; dockfree counts the paid-run containers, so workers back off, not the paid run. Acceptable for today; the full fix (shared leases) stays in FAST_TRACK v2 step 7. |
| D-2 waits | Can a worker "wait on the job" in one call? | Not as written in v1: jobs started with `nohup` in an earlier call are not children of the next shell, so `wait <pid>` fails, and rule 3 keeps each call under ~4 min. **Corrected:** one call loops in 10 s steps for up to 200 s and returns as soon as ALL_DONE / the result file appears; keep the rising poll counter (rule 18, doom_loop guard). Gain: reacts within 10 s instead of up to 200 s. |
| D-3 lanes | Why the template is serial | `P11_full_qc_v3.md:93`: "strictly one after another ... two at once build the same image and stall". The fix is already the rule: warm the image once first (`:90`), then lanes. 3 lanes ran fine on warrant, cold-chain and Nikhil (30 Oct issued prompts). |
| D-4 folders | Where runs go and who may write there | Templates use `/tmp/oracle-qc`, `/tmp/harbor-jobs-qc`, `/tmp/opencode-logs` (`P11:49,76-83,99`), `/tmp/blind` (`P13_blind_solve_v2.md:7`), scratch/logs (`_COMMON_RULES_v5.md:17`). Auto workers may only write outside the project in `/tmp` and `/var/folders` (`auto.py:135-141`); manual sessions use opencode defaults (no permission block in `~/.config/opencode/opencode.jsonc`). **Corrected:** put runs inside the project at `TB/_runs/<date>/<slug>/...` (no permission change; survives reboot; 699 GiB free). The QC kit's `/tmp/step10run` paths are examples (`Final_checklist.md:340-358`); our P11 already uses its own paths. `cd /tmp` before `exe_copy.py` stays (keeps `__pycache__` out of the kit). |
| A-1 parser | `auto.py:498-500` | Confirmed: `re.search(r"\d+", ...)` takes the first digit anywhere. Fix as planned. |
| A-2 stall | `auto.py check_stall` :1492-1513 | Confirmed: fires only when the newest activity of all active workers is older than STALL_MIN. Fix: check each worker; one STALL line per quiet worker. |
| A-3 prompt check | `tools/issue.py:130-149` | Confirmed: only checks `<SHA>`, `name_session.py`, caps. Lint fits before line 147. **Limit found:** go/continue messages (like the cold-chain 12:00 go) are not issued through issue.py, so the check must also run alone: `issue.py --lint FILE`, which I run on every go/continue message. A text check catches mechanical faults (schema "oracle once" vs x3 in one prompt: caught; leftover `[[...]]`: caught). The cold-chain fault (judge frozen but target needs judge changes) is caught only by a required one-line "Reachable:" calculation in any message that sets a score target. |
| A-4 receipt | `P12_recheck_fix_v4.md:73-75` | Confirmed: result json and final reply have counts and oracle/owner/nop, no before/after tree sha, changed checks or score change. Add them as P12 v5. |
| A-5 kill rows | `P2_build_v5.md:66`, `P9_harden_from_results_v4.md:67` | Confirmed: both list "strongest generic solvers + plain first-write"; neither names a split-into-parts solver (outage's miss). Add 2 rows. |
| Baseline tests | ran now | `auto/tests`: 73 OK. `tools/tests`: 30 run, 3 FAIL (old pinned district values in `test_upgrade_tools.A2Intake`, known item R10) - will be fixed in step 2 so the suite is green. Harness tests not touched (no MQ change today; pytest not installed). |
| Running work | board + QC folder | Docker empty; no worker busy. Nikhil QC `0d957b9` finished 01:15 = FAIL (board still says running; waits for you). |

## 2. Changes (final list)

### Docker
- **D-1 `tools/dockfree.py` (new, read-only)**: `dockfree.py --need-mb N [--cpus C]` prints `FREE_MB=… USED_MB=… CONTAINERS=… START=yes|no`. Free = Docker total - 3,072 MiB - sum of running containers' memory limits (no limit = 4,096). CPU soft rule: start=no if container CPUs + C > 12 (1.5 x 8). Exit 0 = yes, 1 = no, 2 = Docker unreachable (treat as no).
  Text changes (replace the count rules): `P11_full_qc_v3.md:77` → "run `dockfree.py --need-mb <task memory_mb>`; START=no → wait (poll per D-2, every 60 s), max 60 min, then write 'no Docker slot' in _progress and keep waiting; never start on no"; `AUTO_POLICY.md:47` and `PROMPT_CHECKLIST.md:35` → "spawn a Docker-heavy worker only if dockfree says yes for its task". `_COMMON_RULES_v5.md` rule 16: "before `docker run`, dockfree --need-mb 4096".
- **D-2 waits**: `_COMMON_RULES_v5.md` rules 3 and 18 → one call: `for i in $(seq 20); do grep -q ALL_DONE <log> && break; sleep 10; done; echo poll <n>; tail -5 <log>` (under 4 min, returns early, rising n).
- **D-3 lanes**: `P11_full_qc_v3.md:90-93` → warm image once, then 3 lanes (lane 1 oracle-1..3, lane 2 owner-1, lane 3 nop-1 then stub-1), each its own nohup with its own log, ALL_DONE when all 3 end. Same text in the P12 gate step (`P12_recheck_fix_v4.md:67`) and `P9_harden_from_results_v4.md:70`.
- **D-4 folders**: every template `/tmp/oracle-qc`, `/tmp/harbor-jobs-qc`, `/tmp/opencode-logs`, `/tmp/blind`, scratch → `/Users/mac/Desktop/Terminal Bench/_runs/<YYYYMMDD>/<slug>/<step>-<TS>/{copies,jobs,logs,blind,scratch}`. Locks stay where they are. Old prompts unchanged.

### Accuracy
- **A-1** `auto.py paid_run_cap`: value must be a whole number or exactly `no cap`; anything else → refuse at start/status with the line shown; missing → 6. `PLAN_TEMPLATE.md` example becomes a bare number.
- **A-2** `auto.py check_stall`: per-worker STALL after STALL_MIN of no activity; once per quiet spell.
- **A-3** `tools/issue.py`: lint before issuing + `--lint FILE` mode. Hard refuse: leftover `[[…]]`; two different oracle counts. Warning (needs `--force-lint "<reason>"`, logged): a final/test/rubric target that differs from the live gate (<85/<85/<40) when no exception for that slug is in decisions.jsonl; a score target with no "Reachable:" line.
- **A-4** `P12_recheck_fix_v5.md` (copy of v4 + receipt): before/after tree sha, changed check/criterion ids with old→new weights, oracle/owner/nop and saved agent-program score before/after, and a rescan for stale TRUTH/prose (AL-18/DS-22/DS-27), judge overlap (JD-14/AL-28), untested promise (AL-1/AL-2), rule never triggered (AL-27). `issue.py` KINDS map points fix to v5.
- **A-5** kill table rows in `P2_build_v5.md:66` and `P9_harden_from_results_v4.md:67`: (1) split-into-independent-parts exact solver, (2) strongest plain exact solver.
- **Test fix**: update the 3 stale `test_upgrade_tools` A2Intake cases to read the live tree/gate instead of pinned district values.

## 3. Steps when you say "proceed" (~2.5 h, all by me, only while Docker is idle)

1. Snapshot every touched file into `master_chat_work/20261030_upgrade2/min_bak/` + sha256 list.
2. A-1, A-2 + unit tests; test fix; A-3 + tests (replay: schema "oracle once" note refused; last 10 issued prompts pass or only warn).
3. D-1 `dockfree.py` + unit test with fake `docker` output; run it live (empty Docker → START=yes, FREE_MB about 12,898).
4. Template text: D-1, D-2, D-3, D-4, A-4 (new v5 file), A-5. CHANGELOG + INDEX lines.
5. End-to-end check: one real QC Step 10 gate on a small already-frozen task (outage-window-replan, tree 005e42b1b4aa) using the new P11 text: dockfree yes, 3 lanes, folders under `_runs/`, oracle x3 = 1.0, nop 0, owner 1. Compare wall time with its earlier gate.
6. All suites green; decisions.jsonl row; report to you.

Undo: copy files back from `min_bak/`; delete `dockfree.py`, `P12_recheck_fix_v5.md` and `_runs/`. Running sessions are never touched; only prompts issued afterwards use the new text.

## 4. Not in this plan (stay in FAST_TRACK v2)
Shared Docker leases (harness queue + workers), gate reuse on recheck, pre-approvals, popup alerts, Codex pre-QC check, database, repo, signing.

## 5. Open question
- Step 5 needs one real Docker gate (about 20-40 min, no paid agent, no cost). OK to use outage-window-replan for it?
