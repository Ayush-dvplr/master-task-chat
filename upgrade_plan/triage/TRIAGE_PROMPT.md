TRIAGE PROMPT FOR OPENCODE (P19). Ayush pastes the text inside the code block after the line PROMPT START into his local opencode session (Opus 5.5) in the planning clone. Replace nothing by hand: the session asks for the folder.

PROMPT START

```text
Task: triage a folder of old teammate or assigned Harbor tasks, read only, and help me pick which ones to fix and push under the gate.

Read first: upgrade_plan/opencode_handoff/AGENTS.md (rules, style, how to ask), upgrade_plan/triage/README.md (what the script reports and its limits), upgrade_plan/tmp/W1-035/P13_INTAKE.md (the outside intake), upgrade_plan/knowledge/PATTERNS.md (families D1 to D9), upgrade_plan/tmp/W1-030/FIX_MAP.md (fix map rows by check id), upgrade_plan/PLAN_FINAL.md sections H and K.

Hard rules for this whole task:
1. Read only. Never write, move, rename or delete anything inside TASKS_DIR. Never run git in TASKS_DIR. All output goes to upgrade_plan/tmp/TRIAGE_<yyyymmdd>/ in the planning clone.
2. No Docker, no harbor command, no paid run, no oracle, no nop, no regrade until I choose it for a named task in an options question. No other AI model calls, no subagents for this task.
3. Never copy a person's name or email into any file. Refer to every task by its folder name or task id. If a folder is named after a person, write it as TASK 1, TASK 2 in the files and say the folder name only in chat.
4. Never copy a secret, a key or the env block of a result.json or config.json into any file or chat message.
5. Every broken or unsure score stays out of the real score. Never present a corrected score as a gate run; a corrected score is a diagnostic only (P13 H4: only a run of claude-opus-5 on exactly the frozen QC passed bytes counts).
6. Keep the owner's design and author. Any hardening of a teammate task needs the owner's agreement, stored word for word. Author fields are never edited.
7. Style in chat and files: no dashes or hyphens as punctuation or list markers, no bold, italic or # headings, contractions written out, numbered lists.

Step 1. Ask me for TASKS_DIR (the folder that holds the tasks) with an options question: the folder I named last time if upgrade_plan/RESUME.md records one, or "I will type the path". Also confirm the kit folder (KIT_DIR, the Input_Bundle_QC folder of the company clone) and the settings file: upgrade_plan/drafts/P1/settings.json, or the installed system's settings.json if upgrade_plan/RESUME.md says the new system is live (Recommended: the live one, it holds the gate in force).

Step 2. Create upgrade_plan/tmp/TRIAGE_<yyyymmdd>/ and touch upgrade_plan/tmp/TRIAGE_<yyyymmdd>/.start, then run, from the planning clone root:
  python3 upgrade_plan/triage/triage_tasks.py --tasks-dir "TASKS_DIR" --settings SETTINGS --kit "KIT_DIR" --out upgrade_plan/tmp/TRIAGE_<yyyymmdd>
If it exits with an error, show me the last 5 lines and stop. Then check that nothing in TASKS_DIR changed: run find "TASKS_DIR" -newer upgrade_plan/tmp/TRIAGE_<yyyymmdd>/.start | head and expect no output.

Step 3. Show me the ranked table from TRIAGE.md as it is (columns rank, task, score, recommendation, trusted, recorded, runs, sign, to gate, slip pct, why). Under it, in at most 8 lines: how many tasks per recommendation; every task with a BROKEN or UNSURE paid run and its sign; every task where the recorded score and the trusted score differ; any task with a structure fail.

Step 4. Ask me which tasks to study deeply, as an options question:
  a. The top 3 that are FIX AND PUSH, HARDEN WITH OWNER or REGRADE (Recommended: these can reach a push soonest; DROP rows are skipped).
  b. The top 3 by score whatever the recommendation.
  c. I name them.
  d. None now.

Step 5. For each picked task, read the task deeply: instruction.md, every doc under environment/ that the instruction or the tests name, tests/test_output.py (the checks the paid model lost and their generators), tests/judge.toml, solution/TRUTH.md, and the trusted runs (for each run with verifier/reward-details.json: python3 master_chat_tasks/tools/trajectory_readout.py "<run folder>" --out upgrade_plan/tmp/TRIAGE_<yyyymmdd>/<task id>_TRIP_<run>.md, and once per task python3 master_chat_tasks/tools/loss.py "<task folder>" with its output saved in the TRIAGE folder; never write into TASKS_DIR). Confirm or reject every family, slip and QC hint from TRIAGE.md with the file and line you read; a hint you cannot confirm is marked "not confirmed". For a BROKEN or UNSURE run read the evidence line it cites and say whether you agree.

Step 6. Write one card per picked task, at most one page, to upgrade_plan/tmp/TRIAGE_<yyyymmdd>/cards/<task id>.md, in this order:
  1. Task: folder name or id, intake kind it would take (assigned, teammate_agreed, own_outside), what the deliverable is in one line.
  2. Real score: trusted tests, rubric, final and the runs they come from; the broken or unsure runs and their signs; the distance to the gate from settings.
  3. Levers: each lever with its family, the deciding doc line (file:line), the checks that pay for it and their share of positive test points; the largest share one slip took against slip_cap_pct.
  4. QC risks: each confirmed hint with its check id, the kit line and the fix map row that answers it; mark which are real fails and which are warns.
  5. Plan under the P13 intake: register (intake.py --outside, dry run first), first checks (precheck.sh, oracle and nop, DECIDING_MAP.md, LEVERS_FOUND.md), full QC, fixes by fix map row, regression check, QC again, then the run that K2 asks for; one line per step with what it costs (Docker kind, paid run or none).
  6. Needs the owner's agreement: every change that touches the design, a lever, the tests' hidden data or the judge, each in one line, plus "author fields stay as received".
  7. Your recommendation in one line and the predicted final after the fixes, marked UNVERIFIED.

Step 7. Before any Docker run, ask me per task, as an options question (one question per task, at most 4 tasks per message):
  a. Oracle and nop through the dockslot fast lane (Recommended for every task I pick: it proves the oracle scores 1.000 and nop 0.000 before anything is spent).
  b. Regrade the saved run (Recommended when the run is BROKEN with a permission sign or the task is REGRADE: replay the saved artifacts with readable modes, or regrade with the current tests and judge; costs one verifier run, no model tokens).
  c. One new paid run of claude-opus-5 (only after QC passes on frozen bytes, P13 step 4f; Recommended last).
  d. No Docker now.
For a BROKEN permission task also ask whether the fix of the tests (a read grant before the uid drop) may be proposed to the owner, because it changes tests/.

Step 8. Ask me per picked task, as options questions, and store each answer:
  a. Intake kind: assigned (given to me by the PL or QL; Recommended when it came from them), teammate_agreed (needs my words that the teammate agreed and the PL oversees it), own_outside.
  b. Counts for me: no (Recommended default, P13 rule 3) or yes in my own words.
  c. Score band for a teammate_agreed task: plus or minus 5 on the final (Recommended, as for b7c42a8f) or none.
  d. Register it now through the new system's intake, or later (Recommended: later, after the oracle and nop answer).

Step 9. Record. Write my answers word for word in upgrade_plan/ANSWERS.md as the next ENTRY n with the IST time (TZ=Asia/Kolkata date), each question named "Triage 1", "Triage 2" and so on, then "Recorded as:" with your reading; tasks by folder name or id only. Add a line to upgrade_plan/RESUME.md (STATE and NEXT STEPS) with the TRIAGE folder, the picked tasks and the next step.

Step 10. Registry. Only when I say "register" for a named task: run the new system's intake as P13 step 1 describes (intake.py --outside SRC --origin <kind> --author "<as I give it>" [--traj DIR] [--agreement "<my words>"]), first without --apply, show me the would be provenance block, and run it with --apply only on my "yes". If the installed intake.py has no --outside mode, stop and tell me; never write the registry by hand.

Questions you must ask (and your recommendation for each):
1. TASKS_DIR, kit folder and settings file (Recommended: the live settings).
2. Which tasks to study deeply (Recommended: the top 3 FIX AND PUSH, HARDEN WITH OWNER or REGRADE rows).
3. Per task, which Docker step if any: oracle and nop, regrade, new paid run, none (Recommended: oracle and nop first; regrade first for a permission broken or REGRADE task).
4. Per task, intake kind, counts for me, score band, register now or later (Recommended: assigned or teammate_agreed as the source says; counts no; band plus or minus 5; register later).
5. For HARDEN WITH OWNER tasks: may I draft the hardening proposal for the owner (Recommended: yes, as a proposal file only; nothing changes before the owner agrees).
6. For a task whose real score is unknown because every paid run is broken: accept the corrected score as a diagnostic only and plan one regrade or new run (Recommended), or drop it.

Finish by telling me in at most 6 lines: the TRIAGE folder, the cards written, what each picked task needs next, and the questions still open.
```
