# P15 Research angle prompt, template v2 (DRAFT, R4 1d26a6e, 28 Oct 2026; not in prompts/templates/)

Changes from v1:
- Adds a persistent angle log and self-improvement: read ANGLES.md, pick untried angles, append rows, propose the next version.
- Adds a repo-mining mode for peer task repos.
- Corrects the v1 context line on withheld rules (see "Context").
Everything else in v1 (three angles, output format, merge) is kept.

How the master uses it:
- Fill `[[ANGLE]]`, `[[ANGLE_BRIEF]]`, `[[QUESTIONS]]`, `[[ANGLES_FILE]]`, `[[CORPUS]]`, and check against `knowledge/PROMPT_CHECKLIST.md`.
- Save as `prompts/issued/_adhoc/<YYYYMMDDTHHMM>_research/<angle>.md`.
- `[[ANGLES_FILE]]` is the current angle log. Its first copy is `master_chat_work/20261028_upgrade/R4_teammate_repo/ANGLES.md`; the master moves it to `knowledge/ANGLES.md` at merge.
- Gemini and ChatGPT get only the part below the line plus the ranked UNTRIED list from the angle log.

Angle briefs:
- gemini, chatgpt, own: as v1.
- own-repo (new): "Answer only from the corpus `[[CORPUS]]` (task folders with report.json, trajectories, TRUTH.md). Use scripts in OUT/scripts that re-run from scratch. Every number cites a script output, file:line or trajectory step."

=== PASTE BELOW ===

Research angle: [[ANGLE]]. [[ANGLE_BRIEF]]

Context: we design hard but fair tasks for a terminal-agent benchmark.
- A frontier coding agent (Claude Opus class) gets a Linux container, input files and a written instruction. It must deliver a program plus exact output files.
- Hidden tests rerun its program on fresh inputs and compare whole documents; a reviewer (judge) reads its work log.
- Every graded rule is stated in a visible file with one reading, or is settled by one determinate shipped fact.
- Difficulty may not come from unstated rules, volume or puzzles.
- Measured on 90 peer tasks (R4):
  - Low scores come from weight on rerun-on-fresh-input checks, not from rerun itself. Every band reruns. Hard tasks put about 2/3 of test weight on hidden instances; easy tasks about 1/6.
  - Agents quit early; time is rarely the limit.
  - Judge what-if figures that need a rerun on changed inputs stay hard. Headline figures computed by the same code leak.
- Levers that cost points in peer tasks:
  - a green control that checks a lower layer;
  - a plausible "make it match" repair;
  - a stateful ledger;
  - one value composed from 3 to 5 files;
  - a strict field beside a normalising rule;
  - a scope carried by a definition;
  - per-item rounding;
  - a bounded withheld fact settled only by a stated domain plus a degenerate shipped instance;
  - per-field-class source precedence;
  - an interlocking allocation whose carried state never heals.

Questions (answer every one, in order):
[[QUESTIONS]]

Output format: as v1 (Q<n> blocks with `C<n>.<k> | claim | evidence | confidence | type` lines, `Implication:`, `Would change our rules if:`, then `Conflicts with the context above`, then `Open`). No code, no generated data, no task text. Do not invent sources.

Own-session rules (own and own-repo angles only; not sent to Gemini or ChatGPT):
- Board id `[[SHA]]`. First and last thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]`.
- Tools work in every turn; get IST time with `TZ=Asia/Kolkata date`. After every compaction re-read this prompt, then OUT/TODO.md, and copy this block word for word into the summary.
- READ ONLY except OUT `[[OUT]]` and `/tmp/<sha>-*/`. No Docker, no harness runs, read-only git, no edits to bundles, master records, `prompts/templates/` or the angle log's master copy. Read at most 50 KB per read; parse JSON with python.
- Angle discipline (new in v2):
  1. Read `[[ANGLES_FILE]]` first. Copy its ranked UNTRIED list into OUT/TODO.md.
  2. Pick at least 2 UNTRIED angles. You may also pick one tried angle only if your corpus is new; say so. Do not re-run a tried angle on the same corpus.
  3. For each angle, write a script in OUT/scripts, run it, and record one row: `| id | question | method | tasks | result in one line | strength S/M/W/N |`. Strength S means it survives a within-contributor or within-domain contrast. A low score is not evidence until Phase A of P14 shows it genuine.
  4. Write `OUT/ANGLES.md`: the full input log plus your new rows, then a re-ranked UNTRIED list. Remove the angles you ran. Add at least 2 new untried angles your results suggested, and say why each ranks where it does.
- Reports: `OUT/REPLY.md` in the output format, ending with `## Lessons for the master` (max 5 lines) and `## Proposed prompt changes`, then `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","step":"P15","angle":"[[ANGLE]]","status":"DONE","questions":N,"claims":N,"angles_tried":N,"angles_untried":N,"report":"<OUT>/REPLY.md","angles":"<OUT>/ANGLES.md"}. It must parse. Final reply: 5 lines max.
- `## Proposed prompt changes`: numbered edits to this template (quote the line, give the new text, give the reason with evidence from your run), then one CHANGELOG line of the form `P15 v<N+1> (<date>): <change summary>; evidence <OUT path>`. The master checks and applies them; you never edit the template.

## Proposed prompt changes (for v3, from this R4 run)
1. Add "verifier stdout may hold only the reward; take crash vs wrong value from the judge's exact-figure justifications and the artifacts manifest" to the own-repo brief. Reason: test-stdout.txt held 15 bytes in all 13 models (genuineness.py).
2. Add "rubric negatives apply when passed=False; tests negatives when passed=True; check on 3 tasks before counting". Reason: an inverted reading mislabelled 7 negatives on 18b5d99f (losses.py docstring).
3. Report judge sensitivity as 50/P final points per judge weight for every task studied. Reason: 725e575c P=12 (4.17), 42e79476 P=16 (3.12).

CHANGELOG line (proposed): `P15 v2 (28 Oct 2026): angle log ANGLES.md read first, >=2 untried angles per run, rows appended, own-repo angle, context updated from R4 90-task contrast, Proposed prompt changes section; evidence master_chat_work/20261028_upgrade/R4_teammate_repo/`
