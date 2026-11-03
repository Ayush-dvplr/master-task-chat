KIT CLASSIFY PROMPT (S7, W1-032 draft, 3 Nov 2026). Template for one read only session that classifies a QC kit change. Family: P10 (upstream diff, QC half). The master fills every [[...]] and issues it with tools/issue.py SLUG research <draft> <OUT>.

Master steps before issuing
1. Run tools/kit_watch.py check with --out master_chat_work/[[DATE]]_kit/ (S7_KIT_WATCH.md step 2) and save its printed report there as kit_watch.txt. Exit 1 means changed; exit 0 means nothing to classify, do not issue.
2. Fill [[CHANGED_IDS]] from the CHANGED CHECK IDS table of the kit_watch output (id, files, lines) and [[FIXMAP_ROWS]] by pasting, word for word, every FIX_MAP.md row whose check id column names one of those ids, plus THE LINE paragraph when IN-17, DS-21, AL-1, IN-15 or IN-16 is among them.
3. Never edit the kit, the snapshot or FIX_MAP.md for this. Do not answer the classes yourself; the session does, the master verifies on disk (R1), and Ayush decides.

=== PASTE BELOW ===

Template: KIT_CLASSIFY_PROMPT.md
You are classifying one change of the QC kit (Input_Bundle_QC) for the master chat. Board id: `<SHA>`. This prompt is saved at `<PROMPT_PATH>`. Read only: you write only in `<OUT>`. Strictly do not run subagents. No git command other than read only ones; never pull, commit, push or checkout. Never edit the kit, the snapshot, FIX_MAP.md, BUILD_RULES.md, any template or any bundle.

First thing: rename this session to `<SHA>`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" <SHA>

Inputs
1. KIT WATCH OUTPUT: `[[KIT_WATCH_DIR]]` (kit_watch.json, diffs/<file>.diff, and the printed report kit_watch.txt). The unified diffs are the evidence; read every one in full, in pieces of at most 50 KB.
2. LIVE KIT (read only, for context around a hunk): `[[KIT_DIR]]` at head `[[KIT_HEAD]]`. SNAPSHOT: `[[SNAPSHOT]]` (head `[[SNAPSHOT_HEAD]]`).
3. CHANGED CHECK IDS (from kit_watch):
[[CHANGED_IDS]]
4. FIX MAP ROWS THAT CITE THEM (pasted by the master, word for word):
[[FIXMAP_ROWS]]
Full fix map: `[[FIXMAP_PATH]]`.
5. RULES: `[[BUILD_RULES_PATH]]` and `[[RULES_IN_FORCE_PATH]]`. Current templates: the files named current in `[[CURRENT_JSON]]`.

Classes (Q86)
LENIENT: QC only gets easier: a check removed, a threshold relaxed, a fail turned into a minor or warn, a requirement narrowed. Nothing we do now would newly fail.
MINOR: stricter or reworded, and both of these still hold: (a) every FIX_MAP row that cites the id still meets the new text with its listed fix and its "wording that passes"; (b) nothing changes about what may stay hidden from the solving agent or how a trap stays hidden. A new check id is MINOR only when its fix touches author side files alone (solution/TRUTH.md, task.toml, metadata) and no agent visible file, test, judge criterion or hidden data.
MAJOR: anything else. In particular: a FIX_MAP row's fix or wording no longer meets the new text; the change touches what may be withheld or how a trap may stay hidden (IN-17, DS-21, AL-1, IN-15, IN-16, the FIX_MAP paragraph THE LINE, or any check that rules on hidden data, hidden branches or announcements); a new check whose fix touches agent visible files, tests, the judge or hidden data; a severity raised to fail on a check that fired against our tasks (FIX_MAP "fires" above 0).
When two classes fit, choose the stricter. When you cannot tell, write MAJOR and say what would settle it.

Steps
1. For each changed id: quote the old and the new text from the diff (file and line on both sides) and say in one sentence what changed.
2. For each id: read the FIX_MAP rows that cite it and test them against the new text: does the listed fix still meet it, does the "wording that passes" still pass, are the side effects the same. Say yes or no per row with the reason.
3. For each id: does BUILD_RULES.md or RULES_IN_FORCE.md rest on the old text (for example HIDING T7, QC FIXES T22, GRADING T13)? Name the item or say none.
4. Classify per the rules above.
5. For every changed hunk that kit_watch could not tie to an id (headings, preamble, scripts without ids), add a row with id "(none)" and classify it the same way.
6. Proposed follow ups, never applied: per MINOR or MAJOR row, the FIX_MAP row text, template line (file:line from the current templates) or BUILD_RULES item that would change, with the proposed new text. A MAJOR row's proposal is marked "waits for Ayush".

Rule that binds the master and you: a MAJOR row always goes to Ayush before any template, rule or fix map change. MINOR and LENIENT rows are reported first; the master acts on them only after the report.

Deliverables in `<OUT>`
1. KIT_CLASSES.md, starting with the kit heads (snapshot and live) and the live file hashes, then the table, one row per changed id:
   id | change (old to new, short) | class | reason (one sentence, with the kit file:line) | fix map rows affected (row numbers, "THE LINE", or "new row needed", or none)
   then the proposed follow ups (step 6), then a line "MAJOR: n, MINOR: n, LENIENT: n", then `## Lessons for the master` (at most 5 lines).
2. result_<SHA>.json: {"sha":"<SHA>","step":"KIT_CLASSIFY","kit_head":"[[KIT_HEAD]]","snapshot_head":"[[SNAPSHOT_HEAD]]","rows":N,"major":["<id>"],"minor":["<id>"],"lenient":["<id>"],"fix_map_rows_affected":[],"report":"<OUT>/KIT_CLASSES.md"}. It must parse.

Final reply (at most 6 lines): counts per class, the MAJOR ids with one reason each, the fix map rows affected, anything you could not read, report path. No fixes, no edits, no offers.
