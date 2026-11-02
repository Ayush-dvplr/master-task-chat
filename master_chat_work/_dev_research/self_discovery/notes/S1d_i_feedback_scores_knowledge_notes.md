# S1d feedback.jsonl (6 lines, master_chat_tasks/feedback.jsonl)
- l1 01:01 23 Oct: "second oen also got 100, 100, 100 so I am stopping ... instead of getting better its getting worsen" -> stop trajectories, root-cause diagnosis.
- l3 08:08: "only levers are not sufficient a frontier models and can easily solve any direct task as of now" -> LEVER_PLAN_v1 covers writing+grading+judge.
- l4: 3 parallel pilots (not depend on one task).
- l5: "...these things are also your improvemt that we did this as badly failed , wastes so much token and time" -> process lessons logged.
- l6: wants "how to bypass the QC keeping those stacking" + question whether few levers sufficient.

# S1f scores.jsonl (53 lines)
- l2 emberforge real run tests 68 rubric 100 (old pass_summary) vs l12 tests_reported 1.94 / l17 corrected 94.19 rubric 84.21. Three different emberforge v0 figures.
- l3 district build baselines S2 0.592 S3 0.918 S4 1.0 shortcut 0.459 (round 0) -> l8 r1 S4 0.194.
- l7 emberforge r1 S4 0.1677 predicted vs l17 real 94.19 (miss 0.77).
- l9 vendor P3 S4 0.6483 vs l18 real 88.97; derivable LV2/LV3/LV5; test_bugs: contract-following solver 0.9241.
- l10 schema S4 0.6268 vs l19 real 99.3 tests, rubric 69.57 (lost module_core_claims_match_archive). derivable "all 10".
- l11 vendor v0 tests 4.83 invalid (permission); l12 emberforge 1.94 invalid (0600 program uid 4001).
- l14 district v0 QC judge_forgery 0.2144 no-program; l15 vendor judge_forgery ~0.50; oracle 0.1241 x5 permission bug in QC Step10.
- l21-24 build_gates "session claim" (forgery 0.0-0.04); district "no stub run, no owner-only run" (gate gap).
- l25-39 P11 QC rounds: verdict fmw counts oscillate: schema 1/2/2 -> 5/1/3 -> 1/2/2 (regression after P12); emberforge 1/2/4 -> 2/0/1 -> 2/1/1 -> 0/0/1; vendor 7/0/1 -> 2/0/2 -> 0/0/2; district WARN 0/0/3 -> 0/0/1.
- l40 cohort trajectory_a2 100/100/100 (prev 58.67 invalid permission); judge via Codex bridge 19/19.
- l43 vendor trajectory_a2 100/100/100 (prev 52.41), 29 checks, 8 criteria 24/24.
- l46 district trajectory_a4 100 (Ayush).
- l47 cohort pilot r2: a2_program_score 0.0563, s4 0.169, L2 single-lever 0.24-0.46 others 0.70-0.89; whole_doc_share 0.606 isolated_share 0.296 shipped_only 0.014; tests 19, criteria 8.
- l52 vendor pilot 0.1682; l53 district pilot 0.177 (reflex replays of the old a2/a4 program against new tests — i.e. measures old program, not new agent run; UNVERIFIED as predictor, given L37).
- l48-51 correction schema: valid flag; cohort v0 58.67 invalid (Errno 13 18 lines; without = 87.5); vendor 52.41 invalid; district timeout invalid.

# S1h KNOWLEDGE.md (89 lines)
- l7 reward = 0.5 tests + 0.5 judge; "With tests < 0.20, overall < 0.30 needs judge < 0.40".
- l8 "A single build run finds spec gaps and cheats; it does not measure difficulty."
- l16-23 PL generator bugs: blank words in 4 archetypes; near-duplicate archetypes; labelled fixtures let agent fit graded rule; 20k-line padding; judge pays for process.
- l28 Script-owned checks final -> blind spots no reviewer recheck.
- l29-34 fresh scaffold fails manual gates DS-27, IN-2, TS-25/26, JD-5/8/18, CL-2/CL-4.
- l37 caps tests>=10 FAIL >35 WARN; judge >=8 FAIL >35 WARN.
- l52 Tension: upstream spine + partial-solver ceiling <0.35 vs beta "preserve partial signal".
- l55-66 Hardness evidence: works = hidden composition (SpecBench 100 vs 25), dependent chain, audit-repair vs contract, algorithmic lift on size ladder, format-only validator (self-verify), stacked orthogonal constraints (96->2%), infeasible instances with certificates, weight on error/rejection paths. Doesn't work: arithmetic, puzzles, volume, formatting, many corner cases, hidden rules, resource pressure.
- l69 district v1 every rule documented -> careful model implemented them all (reviewer 3/10).
- l70 reviewer 3/10 still corresponded to real trajectory <50 -> only real runs count.
- l75 vs l81: chmod 700 (bfe40804) then 755 (2690e960); "700 breaks Harbor's host-user reward read on Linux".
- l78 PL bugs: IN-15/JD-15 name retired key `kind`; Final_checklist oracle x5 vs QL x3 (l36).
- l83 K8 litellm 1.105.0 pin; 1.107.0 quarantined (remote-code payload).
- l88 c9e3454a H6/TS-30 = PL fix for our permission note.

# S1i round_notes.md (71 lines) + converted_batch_notes.md (48 lines)
- round_notes l12: "emberforge 94.19 / 84.21; vendor 88.97 / 100; schema 99.3 / 69.57; district-heat timed out twice at 7200 s. Our hand-written careful solvers (S4) predicted 0.17-0.65 and were wrong by 0.25-0.77."
- l13-26 the 13 study rules (binding).
- l27 hard limits.
- l29-33 section C permission fix; killpg misses setsid child.
- l35-43 Gates Q29 C: no build-time hardness solvers; forgery <=0.05; "judge cannot run here (no API key) ... report as judge not run".
- l47 stale _work scripts emit old format.
- l53-54 kill-by-uid parallel: first oracle runs 0.11-0.28.
- l57-60 F: QC_DEFENCE per lever, XREF.
- l62-71 G Docker clash: --delete deletes shared hb__ image; locks; two runs same minute both building same image 0% CPU 12+ min; cold verifier build > 900 s EnvironmentStartTimeoutError; pip ~68 kB/s.
- batch notes l20-22: old clone trajectory; "reward recorded is combined and produced with no judge key (reward_raw only)"; check permission trap.
- batch l29: "Target: careful-solver tests score 0.10-0.20 ...; per-run gate tests < 90, rubric < 90, overall < 30" — CONFLICT with d63 (tests<100 rubric<100 overall<70) issued same day; also "Caps: 70 tests, 70 criteria" vs QC WARN >35.
- batch l28: judge criteria "true of any correct run (JD-7) and met by every competent route (JD-15)" + "one honesty negative".
- batch l3 / round l3: "If this file and your prompt disagree, stop and report the conflict."
- batch l48: expected HEAD moved again 3fb1650b (HEAD churn: c9e3454a -> f3765e67 -> 3fb1650b within one day).
