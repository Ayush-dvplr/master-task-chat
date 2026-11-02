# Master chat upgrade plan v0 (DRAFT, not approved), 24 Oct 2026 10:50 IST

Ayush 24 Oct: "plan everything and then when research and everything is done discuss with me and i will approve then upgrade yourself also clear all questions with me before upgrade".
Status: draft. Nothing below is applied. Inputs still to land: 5087cd2 (QC kit A), ef7d851 (QC reports B), e66cd5f (strategy review). Done: e59fc8d (leak audit: no leak).

## 1. What I did wrong in this session (evidence)
| # | Failure | Evidence | Cost |
|---|---|---|---|
| M1 | Handoff format wrong 3 times after being told | feedback.jsonl 23 Oct 17:10, 18:35, 24 Oct 10:10 | Ayush's time, trust |
| M2 | Guessed tool arguments instead of reading usage | pending.py `slug=` and kind `session` rejected (24 Oct 10:04); zsh word-split loop created 3 bogus slugs in registry/tasks.json (24 Oct 01:10) | repair work, risk of bad records |
| M3 | Did not enforce my own caps | QC rounds 6-7 on schema/emberforge/dispatch vs cap 3; drop rule (22 Oct 22:34) never applied; schema and emberforge at 16 sessions each | most of the wasted day |
| M4 | Lessons stayed lessons; templates kept the old method | 23 Oct 12:52 lesson "reflex score did not predict the real agent", yet GOALS G11 and P3/P9 still gate on local reflex programs | repeated wrong go/no-go decisions |
| M5 | My rulings started loops | sentinel W7 cascade kept in r1 then failed as TS-26 in v3; emberforge harden deleting the I3 sentence created the IN-16 ambiguity (18 of 54 points) | extra QC and fix rounds |
| M6 | Intake did not check what the harness actually ran | leak audit: 18 of 26 job configs staged from the old `Harbor_Harness/` path | scores possibly from stale copies (converted tasks, sentinel, match-replay) |
| M7 | Proposed work that already existed | QC_FIX_PLAYBOOK (23 Oct) nearly re-proposed; peer mining G1-G5 existed when I proposed peer research | wasted turns |
| M8 | Wrong timestamps and stale estimates | prompt files named T0140 at 10:04; told Ayush probes run in parallel at 45-60 min, harness is serial at ~2 h | bad planning numbers |
| M9 | Records sprawl | 7+ stores (board, pending, status, registry, decisions, log, lessons, feedback, scores); one context compression of 1257 messages | slow restarts, drift |
| M10 | Open questions pile up | Q54-Q58 open with no review cadence | decisions stall |

## 2. Proposed upgrades (each closes rows above)
| id | Upgrade | Closes |
|---|---|---|
| U1 | `tools/issue.py <slug> <step> <prompt-path>`: runs `date`, names the prompt file with the real time, writes board + pending + status + log in one call, refuses when the task is past its round cap or drop rule, prints the handoff in the ONLY allowed form (board sha, step, clickable file:/// link). I never hand-write a handoff again. | M1, M2, M3, M8 |
| U2 | `tools/intake.py <sha>`: reads result.json, checks the OUT folder exists, for harness results checks job-config staged path and bundle tree sha, then writes board/pending/scores/log. | M2, M6 |
| U3 | Lesson to template rule: every lesson gets `template_change: <file:line>` or `no change: <reason>` at intake; a weekly-style sweep before any new template version. | M4 |
| U4 | Ruling check: before I rule KEEP/FIX on a finding, I cite the side-effect row (from ef7d851) and the kit line (from 5087cd2). No ruling without both. | M5 |
| U5 | `knowledge/INDEX.md`: one line per knowledge/research doc (what it answers, date). Read before proposing any research. | M7 |
| U6 | One state view: `status.py` table is the single "where are we" read; README read order shortened to README, STATE, INDEX, open questions. Old stores stay for history but are written only by tools. | M9 |
| U7 | Question cadence: at every Ayush turn I list open questions older than 12 h in one line; none older than a day. | M10 |
| U8 | GOALS G11 rewritten: hardness is proven by a real Opus probe, not local solvers; local solvers stay only as a sanity floor. | M4 |
| U9 | Capacity planner: the harness is serial (~2 h per run, ~10-12 per day). Every plan states how many runs it needs and where they sit in the queue. Harness queue protocol saved in KNOWLEDGE.md (24 Oct 10:45). | M8 |
| U10 | Template v3 (P2 build, P4 rebuild, P9 harden, P11 QC, P12 fix): fix kit-template defects once (R6 anchored, no named-function judge criteria, <=35 checks, timed perf limits), author-note grep gate, self-QC before external QC, diff-only QC round 2, rebuild = core swap. Written only after A, B and e66cd5f land and Ayush approves. | M3, M5 |

## 3. Questions to clear before upgrading (asked after the research lands)
1. U1 refusal: hard refuse past the cap, or warn and require your explicit "override <sha>"?
2. Records: keep all current stores (tools write them) or retire some (which)?
3. Probe budget: how many of the ~10-12 daily harness slots go to probes vs final runs?
4. Converted tasks S25-S31 and sentinel/match-replay scores came from old staged copies: re-run on current copies, or drop them from the plan?
5. Template v3: one batch for all templates, or pilot on 2-3 tasks first (lesson 23 Oct: pilot method changes on >=3 tasks)?
6. The three held P12 sessions (69e1128, 9fe2a50, f99c855): cancel, run under the old flow, or reissue under v3?
7. Q54-Q58 (match-replay grammar, schema R6/K14, kit R6 note, peer QC research, loop changes): settle each in the same discussion.

## 4. Order
1. Wait for 5087cd2, ef7d851, e66cd5f.
2. Merge A + B into the check / fix / side-effect matrix; read the strategy output.
3. Discuss with Ayush, one topic at a time; clear section 3 questions.
4. Ayush approves; I build U1-U10 in that order (tools first, then knowledge, then templates); each verified by a dry run.
