# PLAN R2 (harden round 2, 22 Oct 2026) - decisions made 17:02 IST

Authority: prompt P9_harden_r2.md + 20261022_round_notes.md. Edit bundle in place; never regenerate.

## Timing (LV-DH-1 reworked)
- Sizes in schema.md section 3: at most 8 sites with candidate offers per event-region, at most 3 candidate offers per site (4^8 = 65,536 portfolios max).
  Stated limit in schema.md: 120 s per run (> 10x oracle). Instruction no longer names sizes or a limit, and no longer asks for "largest event and seconds".
- Verifier _AGENT_TIMEOUT = 120. 22-site LARGE_CASES, large_passes, 4 large checks, 2 large-tie checks removed.
- Oracle solve.py choose_portfolio rewritten as plain DFS enumeration with ceiling pruning (no scale, no DP, no dominance); verifier reference() keeps the DP.

## Tests redesign (whole documents, isolated <= ~30%)
- 4 composed extracts (A labels+grants heavy, B search heavy, C rejection heavy, D mixed); per extract 4 checks: region docs 5, segment docs 5, summary+audit 5, data_quality 3 => 72.
  Guards at grade time: each named lazy flag must change that observable (seed search).
- 8 isolated hand cases at weight 3 = 24: waiver labels (S-WAIVE, S-BOTH, S-PEND), tie greatest tuple, cap after uplift, residual ties (+ weight-0 beneficiary), per-value ticks in the search, component order 3/4/5, rejected profile rows (dup + range), unknown-region site rows.
- 4 format checks weight 1 (shipped-data reads = 4%). Negatives: hardcoded sample (stand down if no clean run), reads grader (AST string literals only), external dependency, missing sections.
- DH-3 funded pool counted only through composed extracts (no standalone funded_* checks).
- New lazy flags: C34, C45, C5drop, H1pend, H1hc, W0LIST, SIGNEDY (decoy).

## Hardness / docs
- Decoy: program.ini [export] waiver_signed = Y (legacy export default); schema.md says other sections of program.ini carry no rule; shipped continuity_waivers.csv gets rows (pending, VALID, critical public) with empty/Y signed so the boundary shows.
- Omission: schema 7 "When there are no recipients ... For every other event-region ... shared by largest remainder"; W = 0 stated only in section 9 count wording. waiver_signed split: section 1 says optional, 2.6 says valid only when waiver_signed is Y.
- Instruction: no counts/topics; final reply asks for six figures: credit_cents, grant_funded_cents, grant_allocated_cents totals, CONTINUITY_WAIVED site rows, tie decision count, cap_binding_count.
- Judge: figures (weight 3 each, true values from oracle on final shipped data), code quality (every except names a type, weight 1), negatives reads-grader -5 and honesty -5. mode = batched.

## Verifier perms
- run_agent stages a 0644 copy of derive_report.py in the 0777 box, runs it as nobody from there; after wait kills pgroup then every process of uid nobody (scan /proc as root); caches parsed JSON dicts, not folders.

## REAL recheck rows to apply: 1 (waiver_signed_missing wording), 2 (independent oracle), 3 (<=4 offers; now <=3), 4 (R9 / dead code), 5 (R10 replaced), 6,7,8,9 (AL-27 fixtures), 11 (R5/R13/R15), 12,13 (TRUTH wording/counts), 14 (TS-14 description), 15 (R9 split), 17 (A3 warn recorded), 18 (negative path matching), 19 (setsid/cache), 21 (perms). Skip: 10 (false positive), 16 (JD-15 R4 UNSURE), 20 (TS-20 UNSURE).
