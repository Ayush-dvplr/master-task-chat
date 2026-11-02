You are analysing one new push to the Input Bundle QC kit and reviewing what it means for how we build tasks. Read only. Board id: `ae47772`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261025T1255_qc-push-review.md`.

Why this matters: our 7 probed tasks of 25 Oct scored tests 98.45-100 because every graded rule was written as one sentence that claude-opus-5 copied into code. QC-passed peer tasks lost 4-76% of test points by leaving one axis of a rule unwritten. Our own rules (written to satisfy the OLD QC) forbid that. The new push loosens what "learnable" means. Measure exactly what changed, then say which of our rules and open questions it settles.

## Rules that survive compaction
- First thing: rename this session to `ae47772`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" ae47772
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- READ ONLY except OUT. Never edit the harness clone, our bundles, peer bundles, `knowledge/*`, templates or master records; propose changes only. No Docker, no harbor. Never commit, push, pull or open a PR.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current. Read files in pieces of at most 50 KB.
- Every claim cites file:line (old kit via `git show 976c1666:<path>`, new kit via the working tree). Mark anything not read directly as INFERRED. Never quote more than a short phrase of peer content.

## Before you start
`git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse --short HEAD` must print `5574d77e` (Ayush pulls first). If it prints `976c1666`, stop and reply "WAITING: pull not done". Record `git status --porcelain | grep -v '^??'` before and after; it must not change.

## Inputs
- Kit: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (old head `976c1666`, new `5574d77e`, one commit by Sugam Agrawal: "QC: the prompt is the coverage unit, plus IN-17 against pre-announced discoveries"; 7 .md files, no script changed: confirm with `git diff --stat 976c1666 5574d77e`).
- Old fingerprint: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/fingerprints/qc.json`.
- Our rules: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md`, `QC_RULINGS.md`, `QC_FIX_PLAYBOOK_v2.md`, `LEAK_LIBRARY.md`, `qc_authoring_checklist_9b8229f6.md` (same folder); `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/P2_build_v3.md`, `P9_harden_from_results_v2.md`, `_COMMON_RULES_v3.md`.
- Our findings: `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/delivery_study/synthesis_6c6fcf3/DELIVERY_LEARNINGS.md` (sections 3, 6, 7, 8) and `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261025_process/leak_audit_ed0bc62/LEAK_AUDIT.md` (sections 3-5).
- Our bundles: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/<slug>/` for sentinel-policy-recompute, sensor-network-lsq-correlated-adjustment, district-heat-flex-procurement, tariff-engine-audit-repair, caldermoor-commitment-closure, metered-usage-rating-pipeline, data-product-config-compiler, match-replay-desync-audit.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261025_process/qc_push_ae47772`

## Steps
1. **Diff.** For every changed hunk in the 7 files: check id, old wording, new wording (short), severity, script-owned or manual, and the kind of change (loosened / tightened / new / clarified). Match on id AND wording. Give special care to: the new meaning of "learnable" / "contract" (instruction OR anything determinate in the input the Dockerfile copies, no pointer needed: IN-15, TS-19, AL-1, AL-3, AL-4, CL-5, DS-19, JD-15, JD-16, Final_checklist coverage); the AL-1 "determinate" worked table (silence settles nothing; a sample shows a shape, not the rule behind it; a prohibition is never determinate); AL-2 promises enumerated from instruction.md alone; AL-27 wording change; the new IN-17 (no pre-announced discoveries, "withholding is the default and difficulty is the point", DS-21 protects withheld rules). Also check whether IN-16 and CL-4 changed or only their context did.
2. **What it does to our rules.** One row per rule in LEVER_RULES_v1 (line 24 never-used list, W1-W10, G1-G12, J1-J9), QC_RULINGS IN-15/IN-16/TS-19/CL-4 rows, QC_FIX_PLAYBOOK_v2 rows, P2_build_v3.md:43, :88, :97, :105 and P9's G5 mandate: `| our rule (file:line) | old QC basis | new QC text (file:line) | verdict: still required / now looser than needed / now conflicts with QC / unchanged |`.
3. **Lever shapes under the new QC.** For each shape in DELIVERY_LEARNINGS section 6 (S1-S6, R1-R11, N1-N7): is it now allowed, still risky, or still forbidden, and which new sentence decides it? Be precise about the line between "determinate in the input" (allowed) and "silence" (still needs a sentence).
4. **IN-17 scan of our 8 bundles.** Read each `instruction.md` (and only that) against IN-17. List every sentence that pre-announces a discovery the shipped input establishes, with the input that carries it; and every sentence that IN-17 lets stay because it is a requirement. Include the self-check paragraphs and the G5 "fresh extracts at other scales" sentence. Do the same check on the instruction patterns DELIVERY_LEARNINGS cites as peer practice (T1 bullet list, chainfold "quiet run" line, b47 "written down nowhere" line), from the quotes in the cards only.
5. **Answer our open questions** under the new QC, each with verdict (YES / NO / STILL OPEN), the deciding kit line, and the residual QC risk:
   - Q1 May a graded rule be recoverable from the shipped evidence (worked example, digest, calibration record, config value) without being written as a sentence? Which forms are "determinate" and which are "silence"?
   - Q2 May a rule leave one axis unwritten (binding time, operand, scope, empty value, candidate set) when the shipped input settles it? When it does not?
   - Q3 Does LEVER_RULES line 24 (never-used list) still hold item by item?
   - Q4 Does IN-17 forbid our G5 "fresh inputs / other scales" sentence, the instruction self-check paragraph, a coupling sentence ("one wrong reading moves many figures"), a "some rules are idle in this run" sentence?
   - Q5 Does AL-2 "enumerate from instruction.md alone" remove the need for G11 one-row-per-contract-sentence coverage, or does AL-27 still require it?
   - Q6 Is whole-document exact grading per hidden corpus (CL-4 kit exemption) affected?
   - Q7 DELIVERY_LEARNINGS section 8 questions 1-6 and LEAK_AUDIT section 5 questions 1-5: which does the push settle?
6. **Proposed changes (NOT applied)**: LEVER_RULES (as a v2 delta list), QC_RULINGS / QC_FIX_PLAYBOOK rows, template lines in P2_build_v3 / P9 / _COMMON_RULES_v3, precheck.sh or issue.py lint lines. Each with the kit line and finding it rests on, and a risk note.
7. **Fingerprint**: write `OUT/fingerprint_qc.json` in the same JSON shape as the old one, for head `5574d77e`. Do not overwrite the one in `master_chat_tasks/`.

## Deliverables (OUT)
- `QC_PUSH_REVIEW.md` with sections 1-6 above in that order, then `## Lessons for the master` (max 5 lines).
- `changes.json`: `[{"id":"","kind":"added|loosened|tightened|reworded|clarified","old":"","new":"","impact":"","our_rules":[],"templates":[]}]`
- `fingerprint_qc.json`
- `result_ae47772.json`: {"sha":"ae47772","step":"qc push review 5574d77e","status":"DONE|WAITING","changed_ids":N,"rules_now_looser":N,"rules_now_conflicting":N,"in17_hits_ours":N,"questions_settled":N,"report":"/Users/mac/Desktop/Terminal Bench/master_chat_work/20261025_process/qc_push_ae47772/QC_PUSH_REVIEW.md"}. It must parse.

Done when: every hunk of the 7 files is accounted for, every question has a verdict, the JSON files parse, and `git status` of the clone is unchanged. Final reply (12 lines max): changed check ids; the 3 changes that matter most for test difficulty; which of our rules are now stricter than QC; IN-17 hits in our bundles; Q1-Q6 verdicts in one line each; report path.
