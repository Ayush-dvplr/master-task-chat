# Self-improvement plan v1 (APPROVED 09:08, all parts; applied now per Q8 b), 23 Oct 2026 09:05 IST

Ayush's request (09:01, verbatim in feedback.jsonl): improve every kind of prompt (build, rebuild, task analysis, research angles for Gemini / ChatGPT / own sessions, QC); analyse tasks more deeply; keep stacking and difficulty while passing QC; check whether a few levers are enough to fail a frontier model; keep researching; and survive compaction and restarts.

Principle for QC: we do NOT trick or hide anything from QC. We design difficulty that is QC-legal by construction. Every lever ships with its QC defence (rule quote + why it passes), and our own pre-QC check runs before P11.

## Part A: Prompt quality (all prompt types)
A1. One prompt-writing checklist `knowledge/PROMPT_CHECKLIST.md`. Every prompt I write must pass it before I give the link:
  - scope, inputs, OUT, stops, deliverables, result json (sha = board id);
  - compaction section;
  - which lessons and plans it reads;
  - what it must NOT do;
  - evidence rules (quote + file:line, INFERRED marking).
A2. Per-type template updates (in the S90 template rewrite, after the pilots):
  - Build / rebuild: start from LEVER_RULES, plus a "reflex pre-mortem": before writing files, the session writes how claude-opus-5 would solve the task in its first 10 minutes, and designs against that.
  - Analysis (our own tasks or peer tasks): use the G1-G5 Phase A/B/C structure as the standard (genuineness, rule map, lever table, contrast, agent behaviour, test/judge design, QC safety, writing style).
  - Research angles:
    - Gemini = academic (benchmark-hardness literature, contamination, reasoning failure modes);
    - ChatGPT = practical (concrete task mechanics, worked lever examples);
    - own sessions = evidence (our trajectories + peer tasks).
    Each prompt states the angle, the exact questions, and the output format, so the three can be merged.
  - QC and fix: P12 v2 must label each fix's effect on every lever, and re-run the reflex program.
A3. A prompt is versioned whenever a lesson changes it (CHANGELOG line + the lesson id).

## Part B: Deeper task analysis
B1. For each pilot result (pass or fail), one "trajectory autopsy":
  - the step where each lever was met;
  - what the agent read, in which order;
  - its self-tests, and which levers they covered;
  - time spent per phase.
  Results go to `levers.json` real_effect.
B2. Peer store (Q48) grows: when new Anubis tasks appear, `peer_manifest.py check` lists only new or changed tasks, and they are mined in groups of 4 with the same prompt.
B3. Our own failure library: every leaked lever gets one line, `knowledge/LEAK_LIBRARY.md` (lever, how it was written, the step it leaked at, the fix). Build sessions read it.

## Part C: QC-legal difficulty (keep stacking, pass QC)
C1. A `QC_DEFENCE.md` entry for every lever and every cascade, written BEFORE QC:
  - the rule ids it touches (IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7, JD-15);
  - the quoted rule;
  - why the design passes;
  - the safe fallback if QC still flags it.
C2. A pre-QC self-check script (`tools/stacking_check.py`) that reads test_output.py and judge.toml. It reports:
  - test → observable map (TS-26 duplicates);
  - one property per test (TS-13 hints);
  - penalty groups and sums (AL-28);
  - weight shares (isolated / whole-document / shipped-only);
  - the 70/70 caps.
  It runs in every build, harden and fix, before P11.
C3. Each P11 QC result line for a lever-touching rule goes into `knowledge/QC_RULINGS.md` (rule, our design, verdict, reason). Later designs reuse what QC accepted and avoid what it rejected.

## Part D: Are a few levers enough?
D1. Measure, don't guess. Each pilot uses 4 levers. After the trajectories, per pilot, record:
  - points lost per lever;
  - whether one lever alone would push the score under the gate.
D2. Dose test (after the pilots): on a pilot that passes, a reflex replay with levers switched off one at a time shows each lever's share. Needs no new trajectory.
D3. If the pilots land at 70-85 instead of below 70, the next step is MORE INTERACTION, not more levers:
  - chain two levers so one feeds the other (L3 state feeding L1 control);
  - add L2-style repairs to more controls.
  Peer evidence: the biggest losses (127-205 pts) came from levers that interact.
D4. Research question for the next Gemini/ChatGPT round: "what number and kind of interacting mechanisms do published hard agent benchmarks use per task?"

## Part E: Surviving compaction and restarts
E1. Everything learned lives on disk, never only in chat:
  - rules → `state.json` / `knowledge/`;
  - lessons → `lessons.jsonl` (`master_process` kind for my own mistakes);
  - corrections → `feedback.jsonl`;
  - plans → `_dev_research/*_PLAN_v*.md`.
E2. The README read order already loads all master_process lessons, all feedback, and the approved plans (step 6 / 6b). This plan is added to 6b once approved.
E3. Session learnings: every session's report ends with a "Lessons for the master" section (max 5 lines). I copy them into lessons.jsonl at intake (intake rule step 3).
E4. Before every compaction, I write a checkpoint line to log.jsonl (phase, running sessions, next step) and confirm the restart line.
