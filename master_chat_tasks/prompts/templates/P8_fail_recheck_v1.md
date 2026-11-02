# P8 FAIL recheck in a separate session, template v1 (21 Oct 2026)

Ayush's rule: QC can produce vague or false-positive FAILs. Each FAIL is re-checked in a NEW session, never in the QC terminal that produced it.

=== PASTE BELOW ===

You are re-checking the FAIL findings of a QC report on one Harbor 0.24 bundle. Assume nothing from that report beyond the text of its findings. You decide, with evidence, whether each FAIL is real. Do not edit anything.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`.

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

## Deliverables (OUT)
- `RECHECK.md`: a table of finding, rule quote, evidence quote, label and fix.
- `recheck.json`: `[{"finding":"","id":"","label":"REAL|FALSE_POSITIVE|UNSURE","rule_quote":"","evidence_quote":"","fix":"","difficulty_effect":""}]`

Done when: every FAIL has a row with both quotes, and the JSON parses. Final reply: counts of REAL, FALSE POSITIVE and UNSURE, the false-positive IDs, and paths.
