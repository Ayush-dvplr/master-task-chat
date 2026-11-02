# backdated-entitlement-replay: IDEA (31 Oct 2026 12:35 IST, Ayush "lets start this in parallel")

Purpose: a lever PILOT. It tests three patterns from the stage-2 study (`master_chat_work/20261031_learning/L5_stage2_study/PATTERNS.md` "Tomorrow's copy" 1-3) on one new task before they go into LEVER_RULES or the build template:
- P-A many small hidden extracts, each one exercising ONE stated boundary or precedence pair (stage-2 billing has 18, PM2.5 20);
- P-B a finite latent value per account that the account's own paid invoices fix uniquely (stage-2 billing per-day clock offset; our warrant/pilotage L-CONV);
- P-C per-document / per-field checks, never one hash over all reports and never `except: return False`.
Not copied (PATTERNS.md item 4): unstated rules, whole-scenario hashes, broad exception wrappers.

## World (from L6 IDEAS.md idea 3, `master_chat_work/20261031_learning/L6_web_ideas/IDEAS.md:9`)
A subscription billing ledger. Accounts hold entitlements (seats, usage blocks) and carry-forward credits. Corrections arrive late and are backdated: they change an entitlement from an earlier effective date, after invoices for later periods were already issued. The program must replay the account from the correction's effective date: re-rate every later invoice, re-derive every carry-forward credit (credits expire, can transfer between accounts of one parent), and output corrected invoices, credit ledger, adjustment notes and a reconciliation summary.

Typical wrong program (the lever): a forward-only adjuster that corrects only the invoice whose period contains the effective date and posts one delta. Totals still balance, but later customer rows, expired/transferred credits and notes are wrong.

## Latent value (P-B)
Each account has a billing anchor day (1-28) and a proration basis (actual days vs 30-day month). The docs state, once, that both are per account and are recovered from that account's own paid invoices, and that exactly one combination fits each account. They do not list per-account values. The generator asserts unique fit per account per extract and plants invoices that contradict every rival (warrant UNIQUE_FIT pattern).

## Hidden extracts (P-A)
About 16-20 small hidden extracts (w5 tier >= 50% of positive test weight). Each plants ONE of the stated pairs below on top of a latent combination shipped never shows:
- correction effective date before vs on an invoice boundary (inclusive rule stated once);
- credit expiry exactly on the replayed date (stated inclusive/exclusive);
- transfer and correction on the same day (stated order);
- correction that removes an entitlement a later credit was derived from (stated cascade);
- two corrections whose effective dates are out of arrival order (stated: effective order, then arrival);
- rounding per line vs per invoice (stated half-even per line).
Shipped data: degenerate (Shape D): the anchor and basis are the same for every account, and no pair fires, so a forward-only adjuster is exact on shipped.

## Gate notes (override the template where they differ)
- G-1 Determinacy: every graded value follows from shipped docs plus that extract's own data; unique fit asserted per account per extract (EVIDENCE_MAP fact). Every stated pair has a triggering hidden input (AL-27, RULE_COVERAGE row).
- G-2 No enumeration of per-account readings; QC_DEFENCE shows how a careful agent finds them from invoices alone (IN-15, IN-16).
- G-3 Per-field checks (P-C): one check per document per extract tier, partial credit by field family; no whole-scenario hash; no broad except wrappers. CL-4: one wrong fact must not lose more than ~10% of test points.
- G-4 Kill table (Docker, capped): (1) forward-only adjuster, (2) latest-record-wins replay, (3) careful replay with the shipped anchor/basis carried to every account, (4) careful wide replay that fits anchor/basis over the full stated domain (P6o style), (5) a first-write blind-style program. Rows 1-3 must lose the lever by WRONG. Row 4 must still lose >= 15% of lever points, else NO CORE. Optimisation solver rows: "N/A (replay task, no optimisation)".
- G-5 DESIGN READY bar (v3.7): predicted final <= 35; lever share >= 40%; every kill/blind row <= 65 tests, none > 70; lost lever points by WRONG (crash/timeout <= 30%); reference fast (< 5 s per extract); verifier worst 900-1,200 s (never > 2,430 s); judge probe band mid <= 20.
- G-6 Stop at DESIGN READY (master asks Ayush), and at DESIGN BLIND READY (master issues one P13 design blind; it must lose >= 40% of lever points, else back to design or NO CORE).
- G-7 Pilot record: in DESIGN_SUMMARY.md and the final report, a table "pattern | where in the bundle | measured effect (kill rows, blind)" for P-A, P-B, P-C, so the master can decide what goes into LEVER_RULES.
- G-8 Little Docker: dockfree before every container; scratch under `_runs/20261031/backdated-entitlement-replay/`.
