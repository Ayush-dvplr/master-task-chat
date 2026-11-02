WORKERS: HOW THIS UPGRADE SESSION USES OTHER SESSIONS

Agreed by Ayush on 3 Nov 2026 (Q58 to Q60): W1 and W2 both allowed, no limit on number or tokens (flag Q62 open); report only, full findings in tmp/; W3 prompts go into opencode GPT Sol 6.1.

WORDS
"Helper" (W1, W2, W3) = a session that works for THIS upgrade session. "Task session" = a session in Ayush's task system (build, QC, fix), which Ayush runs in opencode or Codex. The "no subagents" line in a brief applies to the helper itself.

THE MODEL
1. This session is the upgrade master. It plans, asks, decides with Ayush, and stores. It stays light.
2. Heavy reading and research (big folders, the records, the QC kit, many files) runs in worker sessions. The master gets only the report.
3. Every worker report is verified before anything goes into FINDINGS.md, ANSWERS.md or the plan.
4. Any contradiction (between a report and the records, between two reports, or with Ayush's answers) goes to Ayush as a question. The master never picks a winner.

THREE KINDS OF WORKER
W1. Helper inside this session (Claude starts it with its Agent tool).
  For: reading and researching anything in this repo.
  How: Claude writes the brief, the helper reads in its own context and returns only its report. Its reading does not fill this session's context.
  Writes: nothing. Read only. The master stores the result.
W2. Separate cloud session (Claude starts it with its create_session tool).
  For: long jobs that would run for a long time, or several jobs in parallel.
  How: Claude sends the brief, the session works on its own, Claude reads its final report.
  Writes: nothing in upgrade_plan/; the report comes back as its final message.
W3. Prompt for Ayush to paste on the Mac.
  For: anything this cloud container cannot see: opencode, Docker, the harness, the QC kit, files that exist only on the Mac.
  How: Claude writes the prompt into prompts/ in this folder and gives it in chat. Ayush pastes it, then pastes back the result or pushes it to inputs/.

EVERY BRIEF CONTAINS
1. Goal in one line, and the exact questions to answer (with their Q ids).
2. Where to look, and what not to read.
3. Read only. No edits, no commits, no pushes, no subagents of its own.
4. Report format: every claim with file and line, or the command and its output. Mark guesses UNVERIFIED. List contradictions found.
5. A self check at the end: the worker rereads every cited line and confirms it says what the report claims, then lists anything it could not confirm.

VERIFICATION BY THE MASTER (before storing)
1. Spot check: the master opens at least 3 cited lines itself (or all, for a short report) and compares.
2. Any claim that changes a decision gets its line checked, always.
3. A failed spot check means the report is not stored; the worker is asked again or the point goes to Ayush.
4. Stored facts in FINDINGS.md carry the worker id and "verified by master" or "UNVERIFIED".

TMP FOLDER (Q59)
When findings are long, the helper writes them itself into upgrade_plan/tmp/<helper id>/ (its only allowed write; no commit, no push) and returns a short report. The master spot checks, then commits the folder so it survives compaction. Each file is listed in WORKER_LOG.md with the first 8 characters of its sha256, so a reference like "W1-002 a1b2c3d4" always points to one exact file version.

W3 PROMPTS (Q60)
Default target: opencode with GPT Sol 6.1. Every W3 prompt says: read only, do not run subagents (they would start on Claude, F6.7), do all work in this chat, return plain text.

LOG
Every worker gets a row in WORKER_LOG.md: id, kind (W1, W2, W3), date, purpose, questions covered, status (running, done, verified, rejected), where the report is stored.
Full reports are saved under reports/ with the worker id in the name.

COST CONTROL (P5)
1. A worker is used only when the reading is bigger than a few files.
2. One brief per topic; no open ended "study everything".
3. Each report has a size cap (stated in the brief).
