# PL_NOTE sentinel-policy-recompute P12 r2 (board 47d0997)

## False positives

None. All 13 QC v2 findings were rechecked against the live kit (HEAD 71a653b2, same as the report kit) and are real.

## Kept items

- M1 TS-13 and M2 TS-20 (shipped_artifacts_follow_field_specs stays one weight-1 check, Ayush option a, 23 Oct 19:45). Defence (WORK/QC_DEFENCE.md, TS-13 / TS-26): the config property is graded at weight 5 on three hidden corpora by hidden_config_document_rebuilt_by_cli_matches, so the shipped check only adds shape; every legal split (3,1,1,1,1,1 or all 1) failed trap survival in P12 r1 (reflex 0.2895 / 0.2500 > 0.20, controls lever ratio 0.816 / 0.861 < 0.90) and broke the shipped-only cap (<= 5% of positive weight).
- W7 TS-26 (hidden_config_document_rebuilt_by_cli_matches feeds the delivered policy into init/set). The dependence is a natural cascade (LEVER_RULES G1). Feeding the reference policy instead would hand 5 points to a solver whose resolve is wrong, which makes the task easier. This cascade is also why the merged shipped check is safe at weight 1.
- W13 X1 (eight binary files skipped by the dash scan). Acknowledged, no edit; the members were read by hand in Gate 02 DS-7.

## UNSURE questions

None.

## Open for the master (trap survival)

- F2 was applied as directed, but trap survival fails on one lever: L7 sum rounding loses 9/31 before and 8/31 after (ratio 0.889 < 0.90). The old rerun check compared hidden-a against the reference, so every wrong reading lost that point too; F2 removed exactly that double payment. No compensation is allowed beyond lowering a shipped weight, and the only shipped-only check is already at 1. Question: accept the 0.889 (the lost point was the double payment QC flagged), or approve one more hidden L7 row where per-term rounding moves the converged risk_threshold?

## Lessons for the master

- A trap baseline that includes a double-paying check sets a bar the TS-26 fix cannot meet on the smallest lever; the trap rule may need "before" measured without the flagged pairing.
- Judge R10 is now a negative for a code-quality act (not cheating); LEVER_RULES G4 allows negatives for cheating acts only, so QC may flag it next round.
- TRUTH.md:183 still says "for each lever" in the Channel B paragraph; QC did not flag it, left untouched (DS-27 risk).
