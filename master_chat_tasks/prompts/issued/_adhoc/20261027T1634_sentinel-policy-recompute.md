# QC loop analysis (READ-ONLY research session) — 3b00450
First thing, rename this session: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 3b00450` (if the output does not show 3b00450, note it in the report and carry on; never retry on another ID).

You are a fresh analysis session. This prompt: /Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261027T1634_sentinel-policy-recompute.md. Your only writable place is OUT: /Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/qc_loop_analysis/3b00450

## Question to answer (from Ayush)
"How are we fixing QC findings, why do tasks get more errors after each QC fix round, and are the fixes making the task easier?"
Answer it with evidence from the files, not opinion. The master chat has a hypothesis (below); confirm or refute it with numbers.

## Hard rules
1. READ-ONLY outside OUT. Do not edit, move, copy-over or delete anything in: bundles, Tasks_INPUT, QC/copies, QC/reports, master_chat_tasks (knowledge, templates, board, pending, registry, feedback), master_chat_work, the QC kit. No git commands that write. No harness runs. No Docker.
2. No heavy compute. You only read and diff text. If you run a script, wrap it: `perl -e 'alarm 300; exec @ARGV' python3 script.py`. Before you finish, `ps` must show no python process of yours.
3. Do not propose fixes by editing files. Proposals go only into OUT/PROPOSALS.md.
4. Every claim cites a file path and line (or a finding ID + report version).

## Sources
- QC reports (one dir per task, v1.md..vN.md + result_<sha>.json): "/Users/mac/Desktop/Terminal Bench/QC/reports/<slug>/"
  Cover these tasks (most rounds first): emberforge-vault-settlement (9), dispatch-plan-reoptimization (8), sentinel-policy-recompute (7), schema-migration-plan-repair (7), match-replay-desync-audit (7), vendor-archive-roundtrip-recovery (6), district-heat-flex-procurement (5), cohort-retention-reconciliation (5). Sentinel first and in full; then the others.
- Bundle copies QC reviewed, one per QC session SHA: "/Users/mac/Desktop/Terminal Bench/QC/copies/<qc_sha>/<slug>/" (map report version -> qc sha via result_<sha>.json or the report sign-off). Diff consecutive copies of the same task (`diff -ru`, exclude __pycache__) to see exactly what each fix/harden changed.
- Fix prompts master issued: "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/<slug>/" (files *_fix.md, P12_*.md, P7*, *_harden.md, P9*).
- Fix session outputs: "/Users/mac/Desktop/Terminal Bench/master_chat_work/*_<slug>/*/" (RECHECK_FIX.md, result_*.json, DIAGNOSIS.md, COST_TABLE).
- Harness scores per attempt: "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/scores.jsonl" and runs.jsonl under Terminal_2.0_Harbor_Harness (grep the slug).
- Rule definitions (finding IDs CL-*, TS-*, JD-*, AL-*, IN-*, DS-*, A3 ...): QC kit "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC" (read-only).
- Our rules: master_chat_tasks/knowledge/QC_RULINGS.md, QC_FIX_PLAYBOOK_v2.md, LEVER_RULES_v3.md, master_chat_tasks/feedback.jsonl (entries class master-error, rule, gap).

## Master's hypothesis (test it)
H1. Fix prompts written by the master cause new findings (example: sentinel v7 TS-13 from the v6 fix merging the rebuild assert into one check; v7 JD-15 from moving R6 weight onto R7-R9 at w5; v7 CL-2 from the v5 fix relabelling R10).
H2. Rules conflict: CL-4/TS-13 push toward splitting checks, A3 caps checks at 35 and pushes toward merging.
H3. Each QC round is a fresh reviewer that re-flags old unchanged lines or items we kept with a reason (QC_RULINGS).
H4. Fixes did not make tests easier; they made the judge slightly easier (sentinel attempt 7: 5 of 8 judge points from vacuous R10).

## Work
Step 1. FINDINGS table. One row per finding in every report version of every task above. Columns:
task, qc_version, qc_sha, finding_id, rule_id, severity(fail/minor/warn), file:line, one-line summary, origin, cause_evidence, resolution_next_round(fixed/kept/reopened/still-open), caused_new_finding(y/n + id).
origin is exactly one of:
- FIX_CAUSED: the flagged line/weight/check changed in the previous fix round (show the diff hunk and the fix prompt line that asked for it, or "fix session's own choice" if the prompt did not ask).
- HARDEN_CAUSED: changed by a harden/rebuild/build session, not a QC fix.
- MISSED_EARLIER: line unchanged since an earlier QC version that did not flag it.
- REFLAG_KEPT: item kept with a reason in a previous round or covered by QC_RULINGS.
- REFLAG_FIXED: same rule on same item that an earlier round marked fixed (fix did not hold).
- RULE_CONFLICT: the fix for another rule forced it (name both rules).
- NEW_RULE: the kit added/changed the rule between rounds (check kit history if available; else "unknown").
Write as OUT/FINDINGS.csv.

Step 2. Numbers, in OUT/ANALYSIS.md:
a) Per task per round: count by origin and severity. Totals across tasks. Share of findings that are FIX_CAUSED vs MISSED_EARLIER vs REFLAG_*.
b) Fix-prompt attribution: for FIX_CAUSED findings, split "prompt told the session to do it" vs "session's own choice". Quote the prompt lines. List recurring prompt patterns that cause findings (e.g. moving weight, merging asserts, rewriting criteria, renumbering, adding doc sentences).
c) Rule IDs that recur most (top 10) and which pairs of rules conflict, with the concrete edits that ping-ponged.
d) Reviewer variance: lines unchanged across N rounds and flagged only in round N; kept items re-flagged; QC_RULINGS entries ignored by QC.
e) Difficulty impact ("is QC making it easy?"): per task, for each fix round, did the diff change any of: test check bodies, test weights, expected data, hidden data, instruction/doc sentences that name the method or the trap, judge criteria/weights. Mark each change as HARDER / EASIER / NEUTRAL with a reason. Then line up the harness attempts (scores.jsonl) before and after each change: tests %, judge %, final. State plainly per task whether QC fixes lowered difficulty, and by how much, and which fix did it.
f) Fix rounds per task until QC pass (or still failing), and how many findings per round were introduced by that round's own fix.

Step 3. Verdict on H1-H4: CONFIRMED / PARTLY / REFUTED, each with the numbers.

Step 4. OUT/PROPOSALS.md (proposals only, nothing applied): concrete changes ranked by how many past findings each would have prevented (count them from FINDINGS.csv). Cover at least: guard rules for fix prompts, the split-vs-cap ruling (give the options and how many past findings each option would have avoided or caused), what the next QC round should receive from the previous one (previous report, kept list, changed-lines list), build-time self-checks for the top recurring rule IDs, and whether a narrow "recheck only changed lines" QC should replace full QC after round 2. For each proposal name the exact file it would change (template / playbook / rulings) and the text to add.

## Deliverables in OUT
- FINDINGS.csv, ANALYSIS.md (tables first, short), PROPOSALS.md
- result_3b00450.json: {"sha":"3b00450","step":"qc-loop-analysis","tasks_covered":[...],"findings_total":N,"by_origin":{...},"fix_caused_share":x,"qc_made_easier":{"<slug>":"yes/no/partly + one line"},"h1":"...","h2":"...","h3":"...","h4":"...","top_proposals":[...]}
Stop when these exist. Final message: 10 lines max: the H1-H4 verdicts with numbers, the "is QC making it easy" answer per task, and the top 3 proposals.
