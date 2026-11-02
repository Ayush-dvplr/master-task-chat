# HARDEN_REPORT e2bfbf0 slipway-overhaul-replan-repair (harden-g37-a3): NO_CORE

Session: opencode session renamed to e2bfbf0; name_session.py printed "codex: no match" (not retried).
Fingerprints QC 12/12 and GEN 160/160 equal; QC kit HEAD 5574d77e. BUNDLE tree 62dbcde0c809 before
and after (no edit). Tasks_INPUT copy diff -rq empty (already equal; no sync needed).

## Diagnosis
a3 lost 19 test points, all on two reference/document disputes (Q1 cycle lodgements, Q2 top-level
weighted_resource rounding); on the documents a3 = 68/68. The generator is fixed-structure, so
held-out seeds fire no new branch (TRIP.md).

## Tries (WORK/KILL_TEST.md)
1. Held-out seeds via write_corpus/_corpus/_reference: 4 existing + 20 fresh (13 abort in
   write_corpus). a3 EXACT on every non-disputed document of every buildable seed. 0 lever points.
2. Stated invocation variants (relative, spaces, read-only papers, stale out dir, cwd in papers,
   trailing slash): a3 identical to its plain run on 14 runs. 0 lever points.
Reference 0.05-0.12 s per corpus, so no hidden-scale lever; no engine runtime sentence exists.

## Outcome
NO CORE: OUT/DESIGN.md. Judge channel alone predicts final 55 (tests 72.06, judge mid about 38),
69 with Q1/Q2 settled. QC risks Q1-Q8 in OUT/QC_RISKS.md. Phase 2/3 not entered; no Docker
gate run. Kill-test containers e2bf-diag, e2bf-seeds, e2bf-var exited (--rm).

## Lessons for the master
fixed-structure generators (same shapes and amendment list every seed) give no held-out lever once an agent matches the reference | template_change: LEVER_RULES_v3.md triage: check mint variety before issuing a harden
diff the lost artifacts against the docs before counting them as WRONG; here all 19 points were reference/doc disputes | no change: TRIP step already covers it, make it the first gate
generator seeds abort 13/20 via SystemExit in write_corpus; seed additions need a buildable-seed scan | no change: G12 covers new generators only
judge holds 47 pts of repair restatements overlapping tests (JD-8) and lacks J3/J4; a QC pass will move the judge anyway | no change: P11 QC owns it
