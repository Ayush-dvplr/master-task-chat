# Minimum change plan v1 (31 Oct 2026) - PLAN ONLY, nothing applied

Ayush: "no major changes; minimum changes to make tasks faster and more accurate, and fix Docker". Small edits only: template text, two short tools, three small auto.py fixes. No database, repo, signing, dockslot leases or gate reuse today (they stay in FAST_TRACK_PLAN_v2 for later).

## Docker (the main flaw)

| # | Change | Where | Check | Undo |
|---|---|---|---|---|
| D-1 | Replace the "max 2 Docker-heavy" count rule with a memory rule: start a Docker job if free Docker memory >= the task's memory_mb (+50%), free = 16 GiB VM - running containers' memory - 3 GiB headroom. | new `tools/dockfree.py` (read-only: `docker ps` + `docker inspect`, prints FREE_MB and yes/no for a given memory); text in `_COMMON_RULES_v5.md` rule 16, `P9_v4:70`, `P12_v4:67`, `P7_fix_qc_v2:35`, `AUTO_POLICY.md:47` | unit test with fake docker output; run once now (empty Docker -> yes) | restore template snapshots |
| D-2 | Stop sleep polling for own jobs: wait on the job itself (`wait <pid>` / `docker wait <container>`) with a time cap; poll only when waiting for a slot, every 60 s via dockfree. | `_COMMON_RULES_v5.md` rules 3 and 18 | read-back of the rule text; next worker log shows no 200 s sleeps on own jobs | restore snapshot |
| D-3 | 3 lanes by default in QC Step 10 (already used in issued prompts since 30 Oct) + build the verifier image once before the lanes. | `P11_full_qc_v3.md:35` (still says one serial chain), `P12_v4` gate step | diff vs last issued QC prompt | restore snapshot |
| D-4 | Work folders out of `/tmp` (reboot wiped 77 of 80): gate copies, jobs, logs, blind dirs go to `~/tb_runs/<date>/<slug>/`. Container `HOME=/tmp` unchanged. | P11/P12/P13 template path lines; allow `~/tb_runs/**` in `auto.py` worker permissions (:135-141) | one test folder created/read; `harbor run -p ~/tb_runs/...` oracle on a small task (Docker Desktop mount check) | old paths |

## Accuracy

| # | Change | Where | Check | Undo |
|---|---|---|---|---|
| A-1 | Paid-run line: whole number or exact `no cap`, else refuse (fixes `00:40` -> cap 0). | `auto.py:498-500` + `PLAN_TEMPLATE.md` | unit cases 6 / no cap / 00:40 / blank | revert |
| A-2 | Stall alarm per worker (today only when ALL workers are quiet). | `auto.py check_stall` :1492-1504 | unit test: one quiet + one busy worker -> STALL for the quiet one | revert |
| A-3 | Small prompt check before issue: refuse leftover `<SHA>`/`[[...]]`, two different oracle counts, or a gate number different from the live gate (<85/<85/<40 or the task's logged exception). | `tools/issue.py` | replay cold-chain 12:00 go + schema "oracle once" note (both caught); last 10 issued prompts pass | `--force-lint "<reason>"` |
| A-4 | Fix receipt in P12: before/after tree sha, changed checks + weights, score change, and a rescan for the 4 usual new-error kinds (stale TRUTH/prose, judge overlap, promise not tested, rule never triggered). | `P12_recheck_fix_v4.md` final-reply block -> v5 | read-back; next fix report has the block | v4 snapshot |
| A-5 | Kill table gets 2 rows: split-into-independent-parts solver and strongest plain exact solver (outage lesson). | `P2_build_v5.md:66-75`, `P9_harden_v4` | read-back | snapshot |
| A-6 | Oracle count at final QC matches the kit (5 runs) - only if you say yes (question 1). | P2/P11/P12 templates | read-back | snapshot |

## Order and time

1. Snapshot all touched files (`apply_bak/min_plan/`), run tool tests (baseline). 10 min
2. A-1, A-2, A-3 (code + tests). ~1 h
3. D-1 dockfree.py + tests; D-2, D-3, D-4 template text; A-4, A-5 (A-6 if yes). ~1 h
4. Tool tests green; one real check: dockfree on live Docker + one oracle run from `~/tb_runs`. 20 min
5. Log in decisions.jsonl + CHANGELOG. Applies only to prompts issued after this; running sessions are not touched.

Total about 2.5 h, done by me (no worker sessions), only when nothing Docker-heavy is running.

## Expected gain (estimate, to be measured)

- Docker waits: jobs start as soon as memory is free instead of waiting for a count of 2 (tariff waited 1 h 42 min with 1-2 containers up); no 2-4 min sleep gaps on own jobs.
- Fewer QC rounds: A-3/A-4/A-5 target the mistakes that caused the last re-runs.
- No more lost gates after a reboot.

## Questions

1. Oracle runs at final QC: 5 as the QC kit says (recommended, about +40 min per full QC), or keep 3?
2. Headroom for D-1: keep 3 GiB free (recommended) or 2 GiB?
3. OK to apply today when no Docker job is running (after Nikhil's QC 0d957b9 is finished)?
