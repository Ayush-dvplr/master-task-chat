# Prompt-writing checklist (A1), v1 23 Oct 2026

Every prompt the master writes (from a template or ad hoc) passes this list before Ayush gets the link. Tick it mentally; any NO is fixed first. Template changes need a CHANGELOG line with the lesson id (A3).

## 0. Handoff message to Ayush (feedback.jsonl 25 Oct 16:20-16:55: link missing once, wrong link twice)
- [ ] Every issued prompt has its clickable file:/// link in the same message.
- [ ] Exactly ONE link per action: the file he pastes whole (paste-only file, nothing to cut). Never a template link.
- [ ] Say where it runs (harness chat, ChatGPT, Claude chat) and where the result goes (file path, or "nothing to paste").
- [ ] Never mark a step running until Ayush says it is running.

## 1. Identity and survival
- [ ] Board id line `Board id: \`<sha>\`` present, and the rename step is `python3 ".../master_chat_tasks/tools/name_session.py" <same sha>` (works in opencode and Codex, matches only a session whose FIRST message has the board id), run first thing AND as the last step. Never use a raw `opencode db ... LIKE '%Board id%'` command: run from Codex it renamed the master session (23 Oct 15:28).
- [ ] The prompt names its own saved path, and says to re-read it after compaction.
- [ ] "Rules that survive compaction" section: tools-available rule (bash `date`), re-read prompt then TODO.md after compaction, never re-run a finished Docker block (ALL_DONE), copy the section word for word into compaction summaries, TODO.md/LOG.md kept current, reads of at most 50 KB.

## 2. Scope
- [ ] One bundle or one group per session; scope stated in the first paragraph.
- [ ] Inputs listed with absolute, quoted paths; every `[[...]]` filled (grep for `[[`).
- [ ] OUT folder named; deliverable files listed by name.
- [ ] Stops named: "DESIGN READY", "DIAGNOSIS READY" (wait for "go"), "PILOT WEAK", "PAUSED", "ROUND LIMIT", "ARTEFACT", as the step needs.
- [ ] Result json `result_<sha>.json` with `"sha"` = board id, its fields listed, and "It must parse".
- [ ] Final reply length cap.

## 3. What it reads
- [ ] `_COMMON_RULES_v5.md` (except P11 QC and P13 blind-solve, which must stay blind).
- [ ] `knowledge/LEVER_RULES_v3.md` by path for any build, rebuild, harden, fix, hardness or analysis prompt; never pasted.
- [ ] `LEAK_LIBRARY.md`, `QC_RULINGS.md` and `QC_FIX_PLAYBOOK.md` where levers, QC defences or QC fixes are designed.
- [ ] The approved plans and any lesson that changed this prompt type (lessons.jsonl `master_process` lines, feedback.jsonl).
- [ ] Blind prompts (P11, P13) contain no lever names, notes paths, scores or trap words.

## 4. What it must NOT do
- [ ] No git writes; read-only git only.
- [ ] Never edit the harness clone, QC kit, `QC assigned/`, `my tasks/`, `QC_*/bundles/`, the Anubis repo, or master records (unless the prompt is the master's own rewrite session).
- [ ] Never hide a rule (IN-15); never explain a trap (W1).
- [ ] Docker clash rules: bundle lock, TS with seconds + random hex, no `--delete`, no prune, one nohup chain with ALL_DONE, waits under 4 minutes, max 2 Docker-heavy jobs.
- [ ] Oracle x3 per Ayush (state that the kit asks x5).

## 5. Evidence rules
- [ ] Every claim: quote with file:line, trajectory step index, or command output.
- [ ] Inferred items marked INFERRED; unmeasured = "did not run"; unconfirmed = UNVERIFIED.
- [ ] Scores labelled tests-only unless a real judged run happened; artefact runs never used as baselines (Phase A).

## 6. Gates (build / rebuild / harden / fix)
- [ ] STACKING_CHECK with `tools/stacking_check.py`, reflex gate <= 0.20, and what happens above it (2 tries, then PILOT WEAK / PAUSED).
- [ ] QC_DEFENCE.md entries before QC.
- [ ] P12 (any fix prompt): a master fix-directions block with one line per QC finding, FIX (file, change, to what) / KEEP (reason) / REBUT (why), each fix checked to keep the difficulty (Ayush 23 Oct, major gap). Every line cites a `QC_FIX_PLAYBOOK.md` row in its section 2 format; no line uses a NEVER-column fix.
- [ ] Fix prompts require the trap-survival check (playbook section 3) and a `## Trap survival` table; QC_DEFENCE entries in build/rebuild/harden prompts name a playbook row and its pre-agreed DO fix.
- [ ] Report ends with `## Lessons for the master` (max 5 lines).

## QC folder layout (from 23 Oct 2026 12:50, Ayush "go")
- QC copies: `Terminal Bench/QC/copies/<board-sha>/<slug>`; reports: `Terminal Bench/QC/reports/<slug>/` (vN.md, result_<sha>.json, _progress*.md); notes: `QC/notes/`. Never a `QC_<date>` folder at the root. Old paths: `QC/PATH_MAP.md`.
- When closing a QC board row: keep the newest 2 copies per slug in QC/copies, delete older ones and mark them `pruned` in PATH_MAP.md (P12 trap "before" uses the previous copy).
- When verifying any run: `ls -d "Terminal Bench"/QC_*` must print nothing; flag anything new at the root.
