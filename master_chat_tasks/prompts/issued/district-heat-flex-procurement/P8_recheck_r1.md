# P8 FAIL recheck r1, issued 21 Oct 2026 21:00 IST (from template P8 v1)

You are re-checking the FAIL findings of a QC report on one Harbor 0.24 bundle. Assume nothing from that report beyond the text of its findings. You decide, with evidence, whether each FAIL is real. Do not edit anything.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement/` (read only)
- QC REPORT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_district-heat-flex-procurement/baseline_v0/qc_report_v1.md`
- QC (live rules): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_district-heat-flex-procurement/recheck_r1/`

## Master's notes
- UPSTREAM CHANGED is known and approved (master, 22 Oct 09:27): the stored fingerprints are at 9b8229f6, the live QC is at bde868c4, and the QC report you recheck was run at bde868c4. Run this recheck on the live bde868c4 QC as it is. Ignore `_COMMON_RULES.md` Always rule 1 (stop on fingerprint change) for this session; do not stop for it.
- The bundle is in use by other read-only sessions; never write inside it. Scratch only under `/tmp/p8-district-heat-flex-procurement-20261021T2100/`.
- Also check, as one extra row labelled VERIFIER-PERMISSION: does tests/test_output.py let the dropped-privilege uid read every agent file it runs and every grader temp input (a 0600 agent file must still be gradable)? Quote file:line.

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
