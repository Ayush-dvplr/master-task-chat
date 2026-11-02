# Brief for per-task leak auditors (board ed0bc62)

ROOT = /Users/mac/Desktop/Terminal Bench
OUT  = ROOT/master_chat_work/20261025_process/leak_audit_ed0bc62

## Goal
Audit ONE Harbor 0.24 bundle for LEAKS: anything the agent can see (or reach) inside the container that tells it a hidden test or trap exists, where it is, or what the right reading is. Context: fresh claude-opus-5 scored tests 98.45-100 on these after harden/redesign. Earlier diagnoses blamed wording that names amount/method/separating case (Opus transliterates every sentence). We want EVERY other way the bundle gives itself away, too.

## Hard rules
- AUDIT ONLY. Never edit/create/delete any file outside OUT. Never touch master_chat_work/bundles/, _work/, the harness clone, jobs/, master_chat_tasks/, the Anubis repo. If a tool might write (e.g. unzip, python import that writes __pycache__), copy the file to OUT/_scratch/<slug>/ first (cp -R) and run there. No Docker, no harbor, no pip, no git commit/push/pull.
- Read files in pieces of at most 50 KB. Never print a whole trajectory. List steps with python (index, tool, command first 200 chars, output first 300 chars), then read only the steps you need.
- Every finding has evidence: file:line quote, trajectory step index, or command output. Inferred = mark INFERRED. Never guess.

## Background knowledge to read first (skim, do not copy)
- ROOT/master_chat_tasks/knowledge/LEVER_RULES_v1.md (W1-W10, H1-H7, LV-ENUM, G5, G8, J2, J9, G10)
- ROOT/master_chat_tasks/knowledge/LEAK_LIBRARY.md
- ROOT/master_chat_tasks/knowledge/QC_RULINGS.md, QC_FIX_PLAYBOOK_v2.md (for "QC rule the fix touches")
- The latest diagnosis for the task (path given in your prompt).

## Inputs per task
- Bundle: ROOT/master_chat_work/bundles/<slug>/ (instruction.md, task.toml, environment/, tests/, solution/)
- Trajectory: ROOT/Terminal_2.0_Harbor_Harness/jobs/<slug>/trajectory/claude-opus-5/Run 1/ (agent/trajectory.json, agent/instruction.txt, verifier/, report.json, judge_response.txt). trajectory.json: dict with key steps; each step has step_id, source, message, tool_calls[{function_name, arguments{command}}], observation{results[{content}]}.
  IMPORTANT: check the trajectory run date vs bundle mtime; if agent/instruction.txt differs from the bundle instruction.md, say so (the run was on an older bundle) and judge J only against what that run saw.

## Step 1 - agent-visible surface
From environment/Dockerfile (COPY/ADD, WORKDIR, ENV, USER, chmod/chown, RUN that generates files) + instruction.md: list each path the agent can see with size. List what is NOT visible (tests/, solution/) with Dockerfile proof (quote lines). Note how Harbor mounts tests (tests are copied at verify time, after the agent finishes - confirm from tests/test.sh/task.toml if possible). Anything among tests/solution/reference outputs/generators/TRUTH/oracle outputs/_work reachable by the agent = CRITICAL. Also check: does any shipped file contain the expected output, a digest/checksum of expected output, or a script that computes it?

## Step 2 - checklist A-J, each Y/N with evidence
A names (file names, ids, column names, enum values, record ids that point at the trap, e.g. stale_, deprecated_, _b, decoy-like ids, meaningful id prefixes DS-4)
B instruction/doc tone (emphasis, "note that", "be careful", "exactly", warnings, CAPS, bold)
C rules naming the separating case (W1-W3, LV-ENUM, H7: amount + method + repetition) - quote the sentence and say which hidden test it maps to (read tests/test_output.py)
D shipped data showing the separating case (W5), sample outputs, worked examples, digests
E visible tests / self-check scripts / CI logs / validators the agent can run
F repo/history (.git dirs, code comments pointing at the bug, TODO/FIXME)
G leftovers (__pycache__, .DS_Store, backups, ~ files, author notes, board shas, words Harbor/QC/lever/rubric/trap/decoy/hidden/grader/oracle in visible files; run grep -rniE over environment/ and instruction.md)
H cross-file consistency (two docs disagreeing in a way that points at the trap, or agreeing redundantly so the rule is said twice)
I judge/conduct hints doubling as test plan (tests/judge.toml criteria wording echoed in instruction; does instruction tell the agent what to self-check?)
J what the agent actually used (trajectory step indices; which A-I leak it read and then acted on; quote the agent's own message where it names the trap)

Map every hidden test in tests/test_output.py to: the visible sentence/data that reveals it (or "none - genuinely hidden").

## Step 3 - write OUT/<slug>.md
Sections: header (slug, bundle mtime, trajectory date, probe score), Step 1 surface table, Step 2 A-J table (Y/N + evidence), test-to-leak map, then the findings table:
`id | category A-J | severity | file:line + quote | evidence it helped the agent (trajectory step) or INFERRED | proposed fix (one line, NOT applied) | QC rule the fix touches + risk | fix touches tests/data (Y/N)`
Severity: CRITICAL = agent can reach answers/tests/oracle; HIGH = names/shows separating case AND trajectory shows the agent used it; MEDIUM = would reveal but no trajectory evidence; LOW = cosmetic.
End with "## What is clean".
Finally one line: `TOP_LEAK: <id> <short>` and `COUNTS: C=<n> H=<n> M=<n> L=<n>`.

Do not write any other file except OUT/<slug>.md and anything under OUT/_scratch/<slug>/.
