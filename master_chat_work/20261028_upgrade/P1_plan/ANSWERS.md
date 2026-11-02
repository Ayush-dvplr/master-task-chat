# Ayush's answers to QUESTIONS.md (29 Oct 2026 ~00:10 IST, in the master chat)

All 25 answered. 24 took the recommended option; Q6 took the recommended settings with a different method.

| Q | Answer |
|---|---|
| Q1 regrade as push evidence | a) Yes, named exception (judge files only, valid run, Ayush OK per regrade, repackaged with A4) |
| Q2 gate < 40 for pushed tasks | a) Only when the QL asks to lower the score |
| Q3 issue.py for QL work | a) Add kind `ql`, time-box rule, `--by` |
| Q4 one-task repackage tool | a) Build `MT/tools/repackage_one.py` (harness untouched) |
| Q5 QL zip changes tests/judge | a) Old run void; new paid run, asked each time, outside the cap |
| Q6 Docker settings | Recommended settings (memory 12->16 GiB, swap 1->2 GiB, builder GC policy). Verbatim: "i will keep you recommended settings but after all questions done give me step by step process for that and i will do the restart if needed after the session upgrade". So: Ayush applies B-N2/N3/N4 himself in the Docker Desktop GUI from master's step-by-step, after the upgrade, with no Docker job running. |
| Q7 sleep on battery | a) Ayush runs `sudo pmset -b sleep 0 displaysleep 10 powermode 0`; charger in, lid open during auto runs |
| Q8 clean-ups | All four: N5 VACUUM opencode.db (backup, all opencode stopped, end of day), N7 close stale pids 15335/23171 if still present and not Ayush's window, N8 delete /tmp/opencode-logs files > 7 days, N9 Ayush adds Terminal Bench to Spotlight privacy |
| Q9 design aims | a) Tests <= 60 first-write/all-but-one, blinds <= 65, judge mid <= 20, DESIGN READY predicted final <= 35, lever share >= 40% |
| Q10 lever table v3.7 | a) Adopt all rows as in plan C3 |
| Q11 next new task shape | a) Held-out w5 tier >= 50% + probe-band judge pilot; bounded induction later |
| Q12 versioning | a) Snapshot old bytes (`*_v3.6_snapshot.md` + sha256), edit in place as v3.7 |
| Q13 reply to QL | a) Full Markdown reply; Ayush reads before sending |
| Q14 teammate scripts | a) Ayush asks Aditya Jain and Anjali Kumari |
| Q15 learning loop stop rule | a) Accept a version only with >= 1 S/M angle; 2 weak runs in a row -> stop and tell Ayush |
| Q16 budget and caps | a) Paid run only with no LIMIT and <= 2 busy workers; max 3 workers while a run is going, else 5; AP "4 workers" -> 5 |
| Q17 usage limit hit | a) Hold spawns/runs, pause queue, resume at reset + 5 min, REPORT line + macOS notification |
| Q18 kill on "accounts exhausted" | a) Log only first; kill + requeue after one real observed case |
| Q19 doom_loop | a) Keep deny + one auto "continue" with rising-counter poll rule, then BLOCKED |
| Q20 stop and wind-down | a) `auto.py stop --now`; post-STOP runs only via `--wind-down` inside the cap; no new worker in last 20 min |
| Q21 resume paused tasks | a) After Batch 2 (gate change + limit fixes tested) |
| Q22 cold-chain | a) 1 paid run on frozen 8ca9c267f59b, read-out, then harden toward < 40 |
| Q23 metered | a) Finish QC v1 report from kept results (no rerun); PASS -> freeze -> 1 run; miss -> read-out, harden once, 1 new run |
| Q24 schema | a) Redo DESIGN for < 40 (~42-45 held-out worlds + probe-band judge), build, recheck, attempt 7; a miss -> park |
| Q25 QL reruns | a) Outside the cap of 6, ask each time; still wait for a fresh usage window |

Effect on the plan: B-N2/N3/N4 move from "Ayush GUI, Batch 4" to "Ayush GUI after the upgrade, from master's step list"; every other item stays as written in UPGRADE_PLAN_v1.md with the recommended branch taken (A7 is IN because Q1 = yes).
