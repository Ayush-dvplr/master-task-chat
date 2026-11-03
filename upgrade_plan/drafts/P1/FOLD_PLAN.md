FOLD PLAN DRAFT (P1 step 5, 3 Nov 2026 12:45 IST). Nothing here is applied before PROCEED.

AIM: one current version of every rule file. Superseded text moves to a history folder the master never reads (Q8). Rules the master follows live in one layer, RULES_IN_FORCE.md; the knowledge files keep how to do things, not rules that contradict it.

1. FILES ALREADY MARKED SUPERSEDED OR SNAPSHOT (knowledge/INDEX.md): move to knowledge/history/ (Q8)
LEVER_RULES_v1.md (26.8 KB), LEVER_RULES_v2.md (26.8 KB), LEVER_RULES_v3.6_snapshot.md (54.5 KB), KNOWLEDGE_v3.6_snapshot.md (15.6 KB), QC_FIX_PLAYBOOK.md v1 (12.7 KB), QC_FIX_PLAYBOOK_v2.md (20.6 KB), PLAN_v1.md (8.2 KB, replaced by pipeline v4), prompts/templates/_COMMON_RULES_v5_v3.6_snapshot.md, master_chat_work/_dev_research/pipeline_v4/PLAN_v3.6_snapshot.md. About 170 KB the master can no longer pick up by mistake.
Then QC_FIX_PLAYBOOK_v3.md is renamed QC_FIX_PLAYBOOK.md (one name, version inside the file), and the same for LEVER_RULES.
Old template versions (prompts/templates/*_v1 to v4) belong to P10, not here.

2. ACTIVE FILES THAT STILL HOLD LAYERS (content fold)
a. LEVER_RULES_v3.md (62.7 KB): v3.3 to v3.8 changes stacked in one file, and route1 notes R0 "overrides LEVER_RULES_v3 where they differ". Fold R0 into it, delete the overridden text, keep one version line.
b. README.md pipeline paragraph (line 31): says gate "tests<100, rubric<100, overall<70", "Count cap option A (over 35 = warn)" and "every strong solver loses by WRONG output"; its own bracket says this is superseded by v3.8. Replace with one line pointing at STATE_CARD.md and settings.json.
c. QC_FIX_PLAYBOOK_v3.md: "count cap option A (over 35 = warn)" against the caps decided now (QC minimum, soft 70, hard 100, R15 no round caps).
d. tools/issue.py: refuses past caps (2 fix rounds per QC, 2 QC rounds, 3 edit rounds, 8 session time box). Q114 says no caps; Ayush decides each time. DECIDED (ENTRY 48): the caps become warnings, never refusals.
e. _COMMON_RULES_v5.md (19.7 KB) and pipeline v4 PLAN.md: checked line by line against RULES_IN_FORCE.md.
f. KNOWLEDGE.md and state.json "standing rules": same check.

3. HOW THE CONTENT FOLD IS DONE
A helper (W1-027, read only, own tmp folder) reads 2a to 2f and RULES_IN_FORCE.md and writes one table: file, line, rule text, matches / contradicts / missing from RULES_IN_FORCE.md, and the proposed new text. The master spot checks; every contradiction goes to Ayush (never voided automatically, G2). A rule that would cross the agreed line (README GOAL item 7) is listed for Ayush, not folded. Nothing is rewritten in master_chat_tasks before PROCEED.

4. CONTRADICTIONS FOUND NOW (master, 3 Nov, from README.md and issue.py)
1. Gate: README line 31 "tests<100, rubric<100, overall<70" against settings 85, 85, 40 (DR2, R26).
2. Count cap: "option A, over 35 = warn" (README, PLAYBOOK v3) against soft 70, hard 100.
3. Round caps in issue.py against Q114 (no caps).
4. Lever wording "every strong solver loses by WRONG output" against R0 and R25 (primary lever from PATTERNS families, TIMEOUT counts).
5. README Docker line "max 2 Docker heavy jobs" against R21 to R23 (limits are settings).
