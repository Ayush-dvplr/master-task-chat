# Master upgrade plan v1 (for approval), 24 Oct 2026 11:15 IST

Replaces v0 (same folder). Inputs read: leak audit e59fc8d, QC kit A 5087cd2, QC reports B ef7d851, strategy e66cd5f (Phase 1-2 only; it stopped at Phase 3 waiting for Ayush).
Ayush 24 Oct: "1. yes 2-6. your recommendation 7. what is it?" -> section 4 holds my recommendations.
**APPROVED 24 Oct 11:26** (decisions.jsonl): 2-6 as recommended; stale questions closed in one list; e66cd5f not continued; Q-A = (a) probe before QC allowed; Q54 yes, Q55 park as is, Q57 only Pass@1_New/Dinshi_Jain/Aditya Patel, Q58 closed. Q56 still unanswered.

## 1. What the research changed in v0
| Finding | Source | Change to the plan |
|---|---|---|
| 60% of new QC findings came from our own edits (harden 32%, fix 28%); 38% are reviewer noise on unchanged text; 0% from kit changes | B SUMMARY, CASCADES.md | U12 stop-at-first-PASS; U13 noise check before fixing; U14 keep every QC copy |
| 14 of 42 QC rounds ran after the point where stopping was right (first PASS or drop rule) | B LOOPS.md | U1 refusal covers "harden after PASS" and the 3-edit-round drop rule |
| IN-15 covers rules of engagement only; outcome rules may be withheld if derivable from data and testable (01:39, 02:70, FC:498) | A lesson 1 | U10: fix QC_FIX_PLAYBOOK L13 and COMMON_RULES Never 6 wording |
| Kit cap is 35 tests and 35 judge criteria (warn above); 70 is our house rule; PL counts warns | A lesson 2, dec 101 | U10: <=35 tests, <=35 criteria; delete dec 88 / COMMON_RULES:42 "warn is fine" |
| Whole-document cascades can fail CL-4 unless the instruction says only exact documents count | A lesson 4, CONFLICTS Q1 | U10: amplification only after a probe shows a loss, plus the exactness sentence |
| Conduct criteria the oracle cannot show fail JD-7 | A lesson 5 | U10: oracle must perform every conduct criterion, else drop it |
| Fix chains: JD-5 reword -> new judge finding (5 of 8); test regeneration from a stale generator -> 6 new fails; new/split checks -> TS-14/15/23/25/26 | B top chains | U4 side-effect table; playbook rows JD-5 and "re-run hygiene checks on every new check"; diff generator before regenerating |
| Defences hold only when verifiable or about layer ownership; authority, lever and count-cap KEEPs never hold; QC never sees QC_DEFENCE | B DEFENCES.md | U13: KEEP only with diff evidence; pass the defence file to the reviewer |
| No grader leak; real risk = author notes in environment/data; 18 of 26 job configs staged from old `Harbor_Harness/` | leak audit | U2 intake checks staged path; U11 author-note grep gate |
| Old-copy scores for the 7 converted tasks are VALID: old vs current differ only in `task.toml` allowed_hosts (host.docker.internal) | my diff -rq, 24 Oct 11:05 | Q4 answer: no re-runs needed |
| Harness capacity: median 26 min, mean 38 min per run (37 runs); one Docker task at a time | .master-queue/state.json; harness chat | My "~2 h per run, 10-12 per day" was wrong. Real: ~1.5 runs/hour, ~12-15 usable per day |
| Only computation traps on hidden data cost Opus points (emberforge max-flow 20 pts, dispatch sweep 32 pts); wording levers lost 0 | strategy CRITIQUE D3, row 15 | U15 probe-first + kill rule; trap-first ideas |
| Only P13 blind solve predicted real scores (3 of 3); reflex solvers are blind | strategy CRITIQUE D4 | U8: G11 = real probe is proof; P13 is a pre-filter only |
| Gate judged on one run; run variance unmeasured | strategy A2 | U15: a gate candidate gets 2 runs before PL |

## 2. Upgrades (v0 U1-U10 kept, U11-U16 new)
| id | Upgrade | Type |
|---|---|---|
| U1 | `tools/issue.py`: real-time prompt name, writes all records, prints the handoff only as board sha + step + clickable link; **refuses** past caps (2 fix rounds, drop rule, harden after PASS, time box) unless Ayush's override line is logged verbatim | tool |
| U2 | `tools/intake.py`: reads result.json, checks the OUT folder, and for harness runs checks staged path + bundle diff; writes board, pending, scores, log | tool |
| U3 | Every lesson gets `template_change: file:line` or `no change: reason` at intake | rule |
| U4 | No KEEP/FIX ruling without the kit line (A checks.json) and the side-effect row (B FIX_SIDE_EFFECTS) | rule |
| U5 | `knowledge/INDEX.md`, one line per doc; read before proposing research | knowledge |
| U6 | Store cleanup (section 4, Q2) | records |
| U7 | Open questions older than 12 h listed at each Ayush turn | rule |
| U8 | GOALS G11 rewritten (real probe = proof) | knowledge |
| U9 | Every plan states harness runs needed (capacity above) | rule |
| U10 | Template v3 (section 4, Q5) | templates |
| U11 | `tools/precheck.sh <bundle>`: 4 kit scripts + exe_copy + A's 5 grep gaps (TODO/FIXME, lowercase `{{}}`, ENV HOME line, litellm pin, RUN-created /app/data paths) + author-note grep (TRAP, inverse, _traps, decoy) + test/criteria counts <=35. Every build and fix session runs it until clean | tool |
| U12 | Stop at first QC PASS. No harden after PASS. Drop rule enforced by U1 | rule |
| U13 | Before fixing a new finding: diff the cited lines against the previous QC copy. Unchanged and passed last round = noise -> KEEP with the diff as evidence, into a standing false-positive dossier (strategy A3) | rule |
| U14 | Keep every QC copy (no pruning) so U13 is always possible | rule |
| U15 | Probe-first: probe validity (oracle 1.0, nop 0, current staged path), one real run, kill rule (tests >= 95 -> kill or swap core, no QC, no harden), 2 runs for a gate candidate, judge criteria written from what the probe got wrong (strategy A5, A8, A10, A2) | method |
| U16 | `tools/loss.py <job>`: points lost per check and per hidden input from a verifier output (strategy A7), replaces hand P14 attribution | tool |

## 3. One question I cannot answer by research
**Q-A (needed before U15):** dec 55 records the QL rule "fix every issue BEFORE any trajectory". Is a private probe run on our harness (never submitted, recorded as `probe`) allowed before QC? Only you or QL can say. If no, U15 moves to "after QC PASS" and the kill rule still applies.

## 4. Recommendations (Ayush answered 1 = yes; 2-6 = master recommends; 7 = explained)
1. **U1 refusal: hard refuse past caps; override only by your verbatim line, logged.** (approved)
2. **Records.** Keep 7 sources of truth, written only by tools: board.json (sessions), pending.db (open items and questions), registry/tasks.json (task state), registry/scores.jsonl (runs), decisions.jsonl, lessons.jsonl, feedback.jsonl. Retire 3: `open_questions.json` (11 old open Q2-Q32 from 20-21 Oct; move live ones to pending.db, close the stale ones in one list you confirm), `state.json` (status.py replaces it; it was stale for 3 tasks), `log.jsonl` (duplicates board and pending history; freeze read-only). BOARD.md becomes a generated view. README read order: README, status.py output, INDEX, open questions.
3. **Harness slots (~12-15 runs/day, one at a time).** Queue order: (1) repeat runs of gate candidates (dispatch, emberforge), max 4/day; (2) probes, each capped at 60 min, oracle and nop check first; (3) nothing else. No final submit run until a candidate has 2 runs under the gate.
4. **Converted tasks.** Scores are valid (only the staging network line differs). Drop cohort-uplift 1.0, pcggc 1.0, specdec 1.0 and 7ef8d80a 0.99. For caldermoor 0.87, numeric-reduction 0.87 and season-ladder 0.82, one read-only session reads which tests failed in the v0 runs to find a natural trap like dispatch (strategy A6). Sentinel and match-replay old scores belong to old versions; they get a probe only if kept.
5. **Template v3.** Two parts. Part 1, one batch now (corrections, not a method change): R6 anchored, <=35 tests and criteria, J1 lint (no criterion that only restates a TRUTH number), oracle-timed performance limits (>= 3x oracle or no limit), author-note gate, precheck.sh, stop-at-PASS, playbook rows JD-5 and new-check hygiene, generator diff before regeneration, IN-15 wording fix. Part 2, pilot on 3 tasks (dispatch, emberforge, one new idea): probe-first, kill rule, trap-first ideas, judge from probe. Roll out only if the pilot gets a gate result.
6. **Held fix sessions.** 9fe2a50 (dispatch) and f99c855 (emberforge): cancel the old prompts and reissue as short v3 fixes, because these are the two live candidates (dispatch tests 67.33 needs only rubric < 72.67; emberforge needs the I3 sentence restored to recover its 20-point max-flow loss). 69e1128 (sentinel): cancel; sentinel has no run showing a loss, so it waits for a probe.
7. **Q54-Q58 explained, with my recommendation:**
   - **Q54 match-replay:** QC failed DS-21 because the fragment grammar that decides 100 of 158 points is not written anywhere the agent can see. (a) write the grammar into calibration.md, (b) defend again, (c) ship only partial controls. **Rec (a)**: B shows defences of this kind never held; then probe before any more QC.
   - **Q55 schema:** real run tests 100, so under the kill rule it stops. **Rec: park as is (changed from my earlier "small fix")**; the R6 and K14 lessons go into template v3 instead of another schema session.
   - **Q56 PL note on kit R6:** the kit's "reads grader files" judge template (04_Judge_QC.md:20-21) is unanchored and fired on the repo's own tests in schema (-5). **Rec: yes**, one line with the schema evidence in the PL notes bundle.
   - **Q57 peer QC research:** how do teammates pass zero-finding PL with hidden rules? **Rec: one read-only session**: run the kit scripts (no LLM) on 4 peer bundles and read accepted verdicts in Finalized_Tasks_RFP via `gh api`.
   - **Q58 loop changes:** now covered by U1, U12-U15. **Rec: close it when you approve this plan.**

## 5. Strategy session e66cd5f
It stopped at Phase 3 topic 1 (asked 10:45) and has no STRATEGY_v1. Its topics overlap this discussion. **Rec:** do not continue it; I treat its SCENARIOS, CRITIQUE and ALTERNATIVES as input (already merged above) and write STRATEGY_v1 myself after you approve this plan.

## 6. Build order after approval
1. Records cleanup (U6) and INDEX (U5). 2. issue.py, intake.py, precheck.sh, loss.py (U1, U2, U11, U16), each dry-run once. 3. GOALS G11, README, rules U3/U4/U7/U9/U12-U14. 4. Template v3 Part 1 + CHANGELOG. 5. Reissue dispatch and emberforge fixes under v3; queue their runs. 6. Converted-task read session and Q57 research session.
