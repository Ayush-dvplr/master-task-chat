# P8 FAIL recheck in a separate session, template v2 (22 Oct 2026 17:12 IST; v1 + kit-HEAD record, QL coverage, compaction safety)

Ayush's rule: QC can produce vague or false-positive FAILs. Each FAIL is re-checked in a NEW session, never in the QC terminal that produced it.

=== PASTE BELOW ===

You are re-checking the FAIL findings of a QC report on one Harbor 0.24 bundle. Assume nothing from that report beyond the text of its findings. You decide, with evidence, whether each FAIL is real. Do not edit anything.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. This prompt is saved at `[[PROMPT_PATH]]`; after any compaction run bash `date`, re-read it, then `OUT/RECHECK.md` and continue from the first finding without a row. Tools are available; never claim otherwise without a quoted tool error.

Run once and record in RECHECK.md: `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. The live kit is the authority even if it is newer than the QC report's kit; if a finding's rule changed between the two, say so in that row. Read-only git only.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/` (read only)
- QC REPORT: `[[QC_REPORT_PATH]]`
- QC (live rules): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/recheck_r[[ROUND]]/`

## For every FAIL (and every MINOR or WARN the report asks to fix)
1. Quote the finding exactly.
2. Find the rule in the live QC by ID AND wording, and quote it with `file:line`. If the ID does not exist or its wording differs, say so. Renumbering is common.
3. Read every bundle file the rule concerns, in full. Quote the evidence for or against the finding with `file:line`.
4. If the rule is script-owned, run that script on the bundle and quote the line.
5. Label the finding:
   - **REAL**: the rule is broken; quote both sides.
   - **FALSE POSITIVE**: the rule is met, or the finding misreads the rule or the file; quote both sides.
   - **UNSURE**: the evidence is not decisive; write the exact question to put to the PL.
6. For each REAL finding, write a one-line minimal fix and its likely effect on difficulty (none, easier, harder, or unknown).

## QL coverage (QL rule 22 Oct: QC against all kit changes since 2690e960)
If the QC report has a "QL coverage" section, recheck every FAIL row in it like any other finding. If it has none, run `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" diff 2690e960 HEAD -- Input_Bundle_QC/` once and add one row per changed check (label REAL if the bundle breaks it, otherwise PASS), so nothing from those commits is missed.

Write each row to RECHECK.md as you finish it, not at the end.

## Deliverables (OUT)
- `RECHECK.md`: a table of finding, rule quote, evidence quote, label and fix.
- `recheck.json`: `[{"finding":"","id":"","label":"REAL|FALSE_POSITIVE|UNSURE","rule_quote":"","evidence_quote":"","fix":"","difficulty_effect":""}]`

Done when: every FAIL has a row with both quotes, and the JSON parses. Final reply: counts of REAL, FALSE POSITIVE and UNSURE, the false-positive IDs, and paths.
