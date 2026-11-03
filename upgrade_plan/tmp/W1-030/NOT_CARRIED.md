NOT CARRIED (W1-030, draft, 3 Nov 2026)

Source lines the fix map does not carry, each with one neutral reason. Paths are relative to /home/user/master-task-chat unless they start with upgrade_plan.

A. Keeps that could leave a real defect in place

| source file:line | what it proposes | why not carried |
|---|---|---|
| master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v3.md:58 | NOISE row: keep a finding on lines unchanged since a passing round, with the diff as evidence | A diff shows the lines did not change, not that the finding is false; the loop study records a real defect among such findings (ANALYSIS.md:8, sentinel v7 CL-2). The map keeps such a finding only when a kit line shows it false (an FP_DOSSIER row). |
| master_chat_tasks/knowledge/QC_RULINGS.md:150 | an unchanged line or kept item finding that does not answer the earlier reason with a kit line is recorded as acknowledged, not a fail | It reclassifies a finding by process instead of fixing or rebutting it on the kit text, so a real defect (for example a DS-21 solvability fail) can stay open. |
| upgrade_plan/drafts/P1/BUILD_RULES.md:10 (last clause) | "a finding on unchanged lines that passed before is noise, kept with diff evidence" | Same reason as the NOISE row: diff evidence alone does not prove a finding false. |
| upgrade_plan/drafts/P1/RULES_IN_FORCE.md:17 | a fail counts as a false positive when "proven with diff evidence" | Carried only with a kit line showing the finding false; diff evidence alone is not carried. |
| master_chat_work/20261024_process/qc_reverse/B/DEFENCES.md:33 | keep a DS-6 minor because changing the data "would signal the acceptance-row lever" | A lever reason is not a kit reason; PB:53 already lists a keep "because it would reveal lever L" as never. The map fixes or signposts the data (FIX_MAP row 37). |
| master_chat_work/20261024_process/qc_reverse/B/DEFENCES.md:48 | keep an omnibus TS-13 check because a split "would pay 6/71 format and rerun credit" | A real minor kept for a lever reason; the map splits it and gates each half on earned output (FIX_MAP row 4), which keeps the credit away from wrong programs. |
| master_chat_work/20261024_process/qc_reverse/B/DEFENCES.md:68 | keep a TS-26 double payment because isolating it "would hand 5 points to a solver with a wrong resolve" | A real double payment kept for a lever reason; it escalated to a fail (CASCADES.md:154). The map narrows the observable inside the lever family (FIX_MAP row 20). |

B. Fix texts not carried for side effect reasons (no hiding involved)

| source file:line | what it proposes | why not carried |
|---|---|---|
| master_chat_work/_dev_research/qc_loop_analysis/3b00450/ANALYSIS.md:127 (QC v7 sentinel Fix text) | merge checks so the count is 35 | TS-23 above 35 is a warn in the kit (03:62); merging to a count produced TS-13 and moved weight. FIX_MAP row 2 records the warn instead. |
| QC report "Fix:" lines in general (ANALYSIS.md:58) | paste the reviewer's Fix text as the direction | PB:64 G1: at least 22 fix caused findings came from pasted Fix text; the map restates the property and lists side effects instead. |
