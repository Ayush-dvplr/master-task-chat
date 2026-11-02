# QL_MASTER_STEPS v1: the QL loop (from R1 086e1b4 draft; added 29 Oct 2026). Templates: prompts/templates/P16_ql_report_triage_v1.md, P17_ql_handback_v1.md, QL_REPLY_TEMPLATE.md; inbound folder master_chat_work/_ql/<slug>/

## A. QL pastes a QC report
1. Save his text verbatim to `master_chat_work/_ql/<slug>/<YYYYMMDDTHHMM>_report/QL_REPORT.md`, with the header (IST, QL, slug, frozen tree sha from the registry). Number the findings `QL<n>-F<k>`.
2. Check that the tree sha of BUNDLE, Tasks_INPUT and Output_RFP (excluding trajectories/) equals the frozen sha. If not, stop and ask Ayush.
3. Issue P16 (kind `ql`). Wait for TRIAGE.md, then read the labels and spot-check 2 rows against the kit lines.
4. No REAL or PARTLY findings: go to step 9.
5. Any lever not `none`, or `ASK: rule change`: ask Ayush and show the rows.
6. Issue P12 v4. QC_REPORT = QL_REPORT.md, directions = TRIAGE "Directions for P12", PREV_QC_COPY = last QC copy. Check its result json: precheck CLEAN, oracle 1x3, owner 1, nop 0, trap_survival PASS.
7. Issue P11 v3 MODE recheck with PREV = last QC. On PASS, freeze: write the tree sha into the registry (`status.py` field `tree_sha`, spec T3).
8. Ask Ayush: "QL rerun for <slug> (outside the daily cap of 6): ok?" On yes, run `auto.py harness <BUNDLE>`. At the end, run `intake.py --job <slug> --event ql_rerun --apply`, then trajectory_readout to TRIP.md.
   - Gate met (tests < 85, rubric < 85, final < 40): repackage that slug only (spec T4). Back up trajectories/ and take before/after sha listings, so that Output_RFP (excluding trajectories/) = Tasks_INPUT = frozen.
   - Gate missed: use the KNOWLEDGE.md:118 path. Never re-run the same bytes. Ask Ayush.
   - If tests/ and judge are unchanged and Ayush says no run, skip the run and write that in the reply.
9. Write REPLY_QL.md from QL_REPLY_TEMPLATE.md. For each FALSE POSITIVE, add an FP_DOSSIER row now, and a QC_RULINGS row once the QL agrees.
10. Registry: `ql_round`, `next`. Ayush says "pushed", then set stage `pushed`. Add a decisions.jsonl line.

## B. QL hands back a zip
1. Save the zip and its sha256 plus REQUEST.md (his words) to `master_chat_work/_ql/<slug>/<TS>_zip/`.
2. Issue P17 with REQUEST = trajectory_only / regrade_only / lower_score / qc_fix.
3. Read CONFLICTS.md. Any row: ask Ayush and show the row and the two choices (keep his hunk / keep ours).
4. Apply the hunks ROUTE.md accepts to BUNDLE through the next worker prompt, never by hand. Sync Tasks_INPUT.
5. Follow the route:
   - **trajectory_only:** send the TRIP summary and the gate. No run.
   - **regrade_only:** this is a judge-only edit. Only if Ayush allows it (FINDINGS Q1), run one regrade worker in the sentinel 188771e shape. Stop if rubric is 0 or final ≥ gate. On gate met, run step 6 Output_RFP.
   - **lower_score:** if trajectories are present, P9 v4. If not, 3 × P13 v2, then P9 v4. Then P11 v3 full, freeze, A8 (ask, 1 run).
   - **qc_fix:** P11 v3 recheck against the last QC copy, then A6-A8.
6. Write the reply (template) and update the registry (A10).

## Always
- Ask Ayush before every paid run in the QL loop, because it is outside the cap of 6.
- One regrade is one sample. Say so when you report a regrade score.
- Never send a trajectory or a score made on bytes other than the ones delivered.
