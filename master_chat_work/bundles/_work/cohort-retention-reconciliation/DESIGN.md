# DESIGN cohort-retention-reconciliation

## Harden round 1 (22 Oct 2026)

Source: converted bundle, QC v3 post-fix. Real run claude-opus-5 scored tests
36/85 = 0.4235 only because the permission trap fired (Errno 13 on
/app/out/derive_report.py under the dropped uid); the agent's program passes all
12 program-run checks locally, so every v0 lever leaked.

Changes:
1. Format: litellm==1.105.0 pin in tests/Dockerfile; judge header mode batched;
   grader grants read on the program and /app/out parents, serialises runs with a
   thread lock plus fcntl file lock, kills leftovers by process group and by uid.
2. Data: events e029 to e034 (refund, ooc+excluded, ooc duplicate, Feb 30,
   "45.00" duplicate, unknown a777); qualifying_rules revenue types
   [purchase, refund]; new plan_history.csv; new audit_policy.md (plan in force,
   rejection register); schema.md rewritten without counts of rules, residuals or
   artifacts and pointing to audit_policy.md.
3. Levers CR-1 (A), CR-2 (B), CR-3 (E), CR-4 (F), CR-5 (B); see LEVERS.md.
4. Tests: 20 positive (60) and 5 negative (-23). Hidden whole documents on three
   regenerated studies 42 (70%), fixtures 17 (28.3%), shipped-only 1 (1.7%).
   Independent functional reference derive(); agrees with solve.py on 120 seeds.
5. Judge: 8 criteria, six single-figure outcomes asked plainly by the
   instruction and computed through the full chain, one code-quality criterion,
   one honesty negative.
6. instruction.md: no counts, names schema.md and "the study records it points
   to", asks for six computed figures.

## Harden round 2 (board 7cbd9f5, 23 Oct)
- Root cause of 100/100/100 on a2: levers weak by design (each rule one plain sentence near its use; agent wrote the program once). Lever plan LEVER_PLAN_v1: L1 manifest control, L2 identifiers vs strict fields, L3 refundable balance, L4 segment override.
- Data: e035 (` 4500`), extract_manifest.json, segments.csv weight_override column (blank). Docs: schema.md Identifiers section, revenue ledger, control figures, new output fields; audit_policy.md weight override paragraph, register text without the trap explanation. Instruction: "Each output document is graded whole on fresh inputs"; final reply asks for total revenue and clean count only.
- Tests: 19 positive (71, kit scale 1/3/5) + 5 negatives (-23). Hidden whole documents 43 (60.6%, credit = share of 3 studies matched), format/determinism 6 (8.5%), fixtures + 2 mutations 21 (29.6%), shipped-only 1 (1.4%). Generator: minimum always > 0, offset_zero_is_full true in 3 of 4 draws, subtracting types always include chargeback or credit_note, ledger accounts, identifier variants in every file, faulty manifest figures.
- Judge: R1-R5 conduct w3 (L1, L2 ids, L2 spaced date, L3, L4), R6 named-shape code quality w3, R7 rerun after last edit w1, R8 honesty -5; reward.toml 0.5/71 and 0.5/19.
