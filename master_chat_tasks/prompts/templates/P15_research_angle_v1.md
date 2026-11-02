# P15 Research angle prompt, template v1 (23 Oct 2026)

New (IMPROVEMENT_PLAN_v1 A2 "Research angles", D4). One research question is sent to three angles at once; each answer uses the same output format so the master can merge them:
- `gemini` = academic: benchmark-hardness literature, contamination, reasoning failure modes of LLM agents.
- `chatgpt` = practical: concrete task mechanics and worked lever examples that fit our frame.
- `own` = evidence: our trajectories (`master_chat_work/<date>_<slug>/traj_aN/`) and the peer store (`registry/peer_tasks.json`, `_dev_research/peer_levers/`). Run as an opencode session; READ ONLY.

How the master uses it: fill `[[ANGLE]]`, `[[ANGLE_BRIEF]]`, `[[QUESTIONS]]` once per angle (the questions are identical across the three), check against `knowledge/PROMPT_CHECKLIST.md`, and save each as `prompts/issued/_adhoc/<YYYYMMDDTHHMM>_research/<angle>.md`. Gemini and ChatGPT get only the part below the line; their replies are saved verbatim to `master_chat_work/_dev_research/<angle>_r<N>/REPLY.md`. The `own` session also gets the "Own-session rules" block. Merge: one row per claim id across the three files into `_dev_research/RESEARCH_MERGE_r<N>.md` (agree / conflict / single-source).

Angle briefs (paste the one for the angle into `[[ANGLE_BRIEF]]`):
- gemini: "Answer from published research: benchmark papers, evaluation methodology, contamination studies, studies of LLM agent reasoning failures. Cite each source (title, authors, year, venue or URL). Prefer 2023 onward. Say when evidence is thin."
- chatgpt: "Answer from practice: concrete task mechanics, how a rule is written, what a careful agent does, and a worked lever example for each answer (described, no code, no data). Say which parts are your judgement."
- own: "Answer only from our files: trajectories, STACKING_CHECK/DIAGNOSIS reports, the peer store. Every claim cites file:line or a trajectory step. Mark anything inferred INFERRED."

=== PASTE BELOW ===

Research angle: [[ANGLE]]. [[ANGLE_BRIEF]]

Context: we design hard but fair tasks for a terminal-agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container, input files and a written instruction, and must deliver a program plus exact output files. Hidden tests rerun its program on fresh inputs and compare whole documents; a reviewer reads its work log. Every graded rule must be fully stated in a visible file with one reading; difficulty may not come from hidden rules, secrecy, volume, arithmetic or puzzles. What we measured: the agent reads every spec in its first minute, writes its program once 3 to 10 minutes in, never changes the graded logic, and self-tests on shipped data, its own small examples and invariants. Rules written as one plain sentence near their use leaked every time. Levers that cost points in peer tasks: a green control that checks a lower layer than the graded meaning; a plausible "make it match" repair; a stateful ledger where early decisions consume later state; one value composed from 3 to 5 files; a type-strict field beside a global normalising rule; a scope carried by a glossary definition; a per-item rounding unit.

Questions (answer every one, in order):
[[QUESTIONS]]

Output format (exactly this; it is merged with two other angles):
1. For each question, a block:
   - `Q<n>` heading;
   - claims, one per line: `C<n>.<k> | <claim in one sentence> | evidence: <source or file:line> | confidence: high/medium/low | type: finding/judgement`;
   - `Implication:` one or two lines on what we should do differently;
   - `Would change our rules if:` what evidence would overturn the claims.
2. A final block `Conflicts with the context above`: any statement in the context you believe is wrong, with evidence.
3. A final block `Open`: what you could not answer and why.
No code, no generated data, no task text. Do not invent sources; if unsure a source exists, leave it out.

Own-session rules (only for the `own` angle; not sent to Gemini or ChatGPT):
- Board id: `[[SHA]]`. Rename the session first:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error. After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this block word for word into any compaction summary.
- READ ONLY except OUT `[[OUT]]`. No Docker, no edits to bundles or master records, read-only git only. Read files in pieces of at most 50 KB; list trajectory steps with python/jq, never print a whole trajectory.
- Write `OUT/REPLY.md` in the output format above, ending with `## Lessons for the master` (max 5 lines), and `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","step":"P15","angle":"own","status":"DONE","questions":N,"claims":N,"report":"<OUT>/REPLY.md"}. It must parse. Final reply: 5 lines max.
