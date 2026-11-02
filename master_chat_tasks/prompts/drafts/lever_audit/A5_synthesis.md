DRAFT 27 Oct 2026, not issued. Board <SHA>. Prompt <PROMPT_PATH>. Run only after A1-A4 have finished.

# Lever audit A5: synthesis

You are a read-only research session. Write only inside `master_chat_work/_dev_research/lever_audit/`.

## Inputs
`master_chat_work/_dev_research/lever_audit/{A1,A2,A3,A4}/VERDICTS.md` and their `L_*.md` cards; `master_chat_tasks/knowledge/LEVER_RULES_v3.md`; `master_chat_tasks/prompts/drafts/lever_audit/PLAN.md`.

## Task
1. Merge the four verdict tables into one. Where two groups judged the same lever or overlapping tasks, reconcile them from the cited evidence and say which citation decided it.
2. Spot-check at least one GENUINE claim per HELPFUL lever by opening the cited ctrf.json and log step yourself. Downgrade any claim you cannot confirm.
3. Rank HELPFUL levers by GENUINE points per delivered use and note which pairs interacted (one lever's slip feeding another's check).
4. For every HELPFUL lever, write the build recipe in at most 5 lines: sentence placement, data planting, grading, weight, and the writing pitfall that makes it leak.
5. Draft LEVER_RULES edits: DISABLED marks with their evidence line, recipe updates, and any lever to unpause from section 1C. Do not edit LEVER_RULES itself.

## Output
- `LEVER_VERDICTS.md`: merged table `| lever | verdict | delivered uses | GENUINE pts | our evidence | spot-check | recipe |`, the ranking, the interaction notes.
- `PROPOSED_EDITS.md`: each edit as `section | old text | new text | evidence`.

Finish with one line: `AUDIT SYNTHESIS DONE HELPFUL <a> WEAK <b> DISABLE <c> UNKNOWN <d>`.
