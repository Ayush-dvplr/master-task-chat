# Shared brief for per-task QC-loop analysis (session 3b00450)

ROOT = /Users/mac/Desktop/Terminal Bench
OUT  = ROOT/master_chat_work/_dev_research/qc_loop_analysis/3b00450

## Hard rules
- READ-ONLY everywhere except OUT/_work/. Never edit/move/delete anything in bundles, Tasks_INPUT, QC/, master_chat_tasks/, master_chat_work/ (other than OUT/_work), the QC kit. No git writes. No harness runs, no Docker.
- Text reading and diffing only. Any python script: `perl -e 'alarm 300; exec @ARGV' python3 script.py`. Leave no python process running.
- Every claim cites a file path:line, or finding ID + report version.

## Sources
- QC reports: ROOT/QC/reports/<slug>/v1.md..vN.md. Each has "## Findings (worst first)" (numbered, severity ❌ fail / 🟡 minor / ⚠️ warn, gate + rule id, file:line, Fix line) and from v2 on a "## Compared with v(N-1)" section with Fixed / Still open / New lists. USE THOSE SECTIONS FIRST.
- Report version -> QC sha: "Board id" in report header or result_<sha>.json in the same dir (field "report"). Kit commit per report is in the header / result json ("kit"). Kit history: `git -C ROOT/Terminal_2.0_Harbor_Harness log --oneline -- Input_Bundle_QC` and `git show <commit> --stat` (read-only). Kit commits in use: bde868c4, f3765e67, 3fb1650b < 71a653b2 < 976c1666 < 5574d77e (5574d77e added IN-17 + "prompt is the coverage unit").
- Bundle copy QC reviewed: ROOT/QC/copies/<qc_sha>/<slug>/ (exists only for versions with a sha in a result json). Diff consecutive copies: `diff -ru -x __pycache__ copies/<shaN-1>/<slug> copies/<shaN>/<slug>`. For versions with no copy, origin can only be judged from the reports' Compared-with section, prompts and fix-session outputs; say so in cause_evidence.
- Fix/harden prompts master issued: ROOT/master_chat_tasks/prompts/issued/<slug>/ (*_fix.md, P12_*.md, P7*, *_harden.md, P9*, *_rebuild.md). Map each to the QC round it answers by timestamp/content.
- Fix session outputs: ROOT/master_chat_work/*_<slug>/*/ (RECHECK_FIX.md lists each finding REAL/FP, fixed/kept with reason; DIAGNOSIS.md; HARDEN_REPORT.md).
- Harness scores per attempt: ROOT/Terminal_2.0_Harbor_Harness/MASTER_RUN_LEDGER.md (grep slug; columns final, tests, judge) and ROOT/master_chat_tasks/registry/scores.jsonl (grep slug).
- Rule defs: ROOT/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/0*_*.md, Final_checklist.md, tests_qc.py (A3 = check cap 35).
- Our rules: ROOT/master_chat_tasks/knowledge/QC_RULINGS.md, QC_FIX_PLAYBOOK_v2.md, LEVER_RULES_v3.md, ROOT/master_chat_tasks/feedback.jsonl.

## Deliverable 1: OUT/_work/<slug>.csv
Header exactly:
task,qc_version,qc_sha,finding_id,rule_id,severity,file_line,summary,origin,cause_evidence,resolution_next_round,caused_new_finding
- One row per finding in EVERY report version (fail, minor AND warn). finding_id = the report's id (e.g. G05-1) or "F<n>" by list position if no id.
- severity: fail/minor/warn. qc_sha blank if unknown.
- origin, exactly one of:
  FIX_CAUSED (flagged line/weight/check changed in the previous QC-fix round; cause_evidence = short diff hunk ref + the fix-prompt file:line that asked for it, or "fix session's own choice")
  HARDEN_CAUSED (changed by a harden/rebuild/build session, not a QC fix)
  MISSED_EARLIER (line unchanged since an earlier QC version that did not flag it)
  REFLAG_KEPT (item kept with a reason earlier, e.g. RECHECK_FIX "kept", or covered by QC_RULINGS)
  REFLAG_FIXED (same rule on same item an earlier round marked fixed)
  RULE_CONFLICT (fix for another rule forced it; name both rules in cause_evidence)
  NEW_RULE (kit added/changed the rule between rounds)
  For v1 findings with nothing earlier to compare, use HARDEN_CAUSED if the build/harden authored it, else MISSED_EARLIER is impossible -> use "BASELINE" (allowed only for v1 of a task).
- resolution_next_round: fixed / kept / reopened / still-open / last-round (for the final version).
- caused_new_finding: "y:<next version finding id>" if the fix of this finding produced a new finding next round, else "n".
- Quote CSV fields with double quotes; keep summary <= 120 chars; cause_evidence <= 250 chars.

## Deliverable 2: OUT/_work/<slug>_notes.md (short, tables first)
1. Round table: version, sha, kit, fails/minors/warns, count by origin.
2. FIX_CAUSED attribution: prompt-asked vs session-own-choice, with prompt quotes (file:line). Name the edit pattern (moving weight, merging asserts, splitting checks, rewriting criteria, renumbering, adding doc sentences, other).
3. Rule ping-pong: concrete edits that flipped between rules across rounds (e.g. split for CL-4/TS-13 then merge for A3/TS-23).
4. Reviewer variance: lines unchanged across rounds but flagged only late; kept items re-flagged; QC_RULINGS entries QC ignored (cite ruling line).
5. Difficulty impact per fix/harden round: did the diff change test check bodies, test weights, expected data, hidden data, instruction/doc sentences naming the method or trap, judge criteria/weights. Mark each HARDER/EASIER/NEUTRAL with a reason. Then the harness attempts (ledger) before/after each change: tests %, judge %, final. One-line verdict: did QC fixes lower difficulty, how much, which fix.
6. Rounds until QC pass (or still failing) and per round how many findings were introduced by that round's own preceding fix.
