# QC_DEFENCE: backdated-entitlement-replay (board 99230f0)

One entry per lever and per cascade. Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7, JD-15. Fallbacks name the QC_FIX_PLAYBOOK_v3 row and its DO-column fix for this bundle; no NEVER-column fix is used.

## L-FIT: per-account anchor day and basis, unique fit (billing_terms.md B2)

- Touches: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-19.
- Live rule quoted: IN-16 "every graded question has one reading"; AL-1 "a deliverable property is either stated or settled by one determinate shipped fact"; AL-27 "every stated rule is triggered by some graded input".
- Why it passes: B2 states the domain once (anchor day 1 to 28, basis actual or thirty), the evidence set (the account's paid invoices rated with the original events, void and open invoices are not evidence), the uniqueness condition and both failure labels (`anchor_none`, `anchor_ambiguous`, `candidates_fitting`). No per-account value is listed anywhere (IDEA G-2). The generator asserts, per hidden extract, that every non-planted account has exactly one fitting candidate equal to its truth, and that each planted account has 0 or 2+ (EVIDENCE_MAP + UNIQUENESS.md). AL-27: the unique branch fires on every hidden account; `anchor_ambiguous` fires on PB1, PB1b and the quiet account of every k=1 extract; `anchor_none` fires on PB2. QC_RULINGS IN-16 PASS ("ungraded gaps pass if the generator never produces the open case") covers anything outside the stated domain: the generator never draws anchor 29 to 31.
- How a careful agent finds it: B2 is in the governing file named by rule_register.md; the program must try 56 candidates, which the sentence names. Nothing is announced (IN-17): the sentence is a computation rule, not a description of the input.
- Fallback: IN-16 row DO: "REBUT quoting 01:46; generator never produces the open case; settling clause general" (file WORK/QC_DEFENCE.md quote + tests/ generator assert line). If QC says the shipped data cannot show the ambiguous case, AL-1 row DO direction 4b: keep the sentence (it states the branch) and add the EVIDENCE_MAP row; never add a shipped ambiguous account (W5: separating cases hidden only).

## L-REPLAY: full replay from the earliest effective correction (correction_policy.md C1, C2, C4; credit_policy.md K3, K5)

- Touches: IN-15, IN-16, AL-27, CL-4, TS-13, TS-19.
- Live rule quoted: IN-15 "every rule of engagement is stated in a copied file"; TS-19 "hidden inputs stay inside the stated bounds and every promise is graded with a generated case".
- Why it passes: C4 says every non-void invoice from the first affected statement month on is re-rated and the credit ledger is re-derived; K5 says the moved amount is the lesser of the request and the sender's usable balance in the replayed ledger and that the `posted=` figure in the log is not used. PA4 plants a transfer whose replayed cap differs from `posted`; PS sets `credit_expiry_cycles` 2 or 3 so overpayment lots expire inside the window. Hidden values are drawn inside the stated bounds (window 6 months, quantities >= 0, anchors 1..28) with generator asserts (TS-19).
- Fallback: AL-27 row DO "add hidden triggering rows" (already present per tier); TS-19 row DO: add the missing bound assert in the tests generator and cite it.

## L-PAIRS: the stated boundary pairs (PA1 cycle start, PA2 expiry, PA3 same day, PA5 order, PA6 half-even, PS live legacy key)

- Touches: IN-16, IN-17, AL-27, CL-4, TS-19.
- Live rule quoted: IN-17 "no sentence announces what the input establishes"; W6 at most one toy worked example per rule on invented values.
- Why it passes: each pair is one plain sentence in its governing file (B3 change on the cycle start day is billed in full that cycle; K1 a lot can be used up to the day before `expires_on`; K4 on one date transfers post before invoices are issued; C2 effective-date order, same item and date by higher `arrival_seq`; B5 half-even per line). None of them describes the shipped input; shipped never fires them (BRANCH_FIRE shipped count 0). Each fires in two hidden extracts (AL-27). No pair is explained as a trap (W1).
- Fallback: IN-17 row DO "REBUT: 'Default to keeping the sentence'; delete only if it announces a shipped fact"; for any sentence QC reads two ways, IN-16 row DO: reword the one sentence to a single reading in its governing file (no extra example on shipped values).

## S5 partial-authority decoy: legacy_terms.yaml

- Touches: IN-16, AL-1, AL-27, JD-15.
- Why it passes: its header states it is superseded by billing_terms.md and credit_policy.md for every key except `credit_expiry_cycles`, which stays in force; rule_register.md repeats the arbiter. Graded on both sides: dead keys (`default_anchor_day`, `default_basis`, `rounding`) lose PB2/PA6 points if used; the live key loses PS points if ignored. Void invoices are rated by the old default (ambient), and B2 already says void invoices are not evidence.
- Fallback: AL-1 row DO direction 4b (EVIDENCE_MAP row for the void witness); IN-16 row DO REBUT 01:46.

## Cascade 1 (coupling): recovered anchor/basis and replayed balance carried into every document

- Touches: CL-4, TS-13, TS-26, TS-20.
- Live rule quoted: CL-4 FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately."
- Why it passes: instruction.md states whole-document exactness and the rerun promise. Per-row ownership (G1a): ledger family owns region files, rollup family owns segment files + summary, control family owns policy_audit + data_quality; one wrong account fact costs at most one tier's three checks = 15/166 = 9.0%, one wrong fact in one family 3.0% (COST_TABLE one-fact column). TS-13: each check opens one family of one tier; the family grouping is justified in SELF_CHECKS (same observable class, one ownership map). TS-20: hidden checks w5 core, shipped w3 sub-goal, existence w1.
- Fallback: CL-4 row DO "REBUT FC:491 + one-fact-wrong score"; TS-13 row DO "split" by document if QC insists (weights split evenly, totals unchanged).

## Cascade 2: corrections -> first affected month -> credits applied -> overpayment lots -> transfers

- Touches: TS-26, AL-28, JD-7, JD-15.
- Why it passes: no two checks read the same observable with the same logic (families disjoint by document, tiers disjoint by extract). Negatives grade cheating acts only (`negative_program_ignores_input` -5, `negative_mutates_input_directory` -3; judge J3a -3, J3b -5, scope -1, grader-read -5), each act charged once across tests and judge (AL-28). Every judge probe is performed by a solve.sh self-check line `check <id> ok` (JD-7); probes are labelled process/trajectory, J10 is labelled instruction following (JD-15).
- Fallback: AL-28 row DO: drop the judge-side duplicate of an act already charged by a test; JD-7 row DO "fix oracle" (add the self-check stage to solve.sh); JD-15/16 row DO relabel.

## Items a full build must state or grade (blind 1861cfe lessons, 31 Oct)
1. Negative corrected total (seat reduction via proration): state whether credit applies to it and whether a negative amount due becomes an overpayment lot; plant it on a hidden extract or keep the generator from producing it (IN-16).
2. Applied correction whose first affected month falls after the window: state the value of `first_affected_statement_month` (or state corrections never take effect after the window and keep the generator inside it).
3. "Declared input file": define it in output_contract.md as the 9 data files listed in the rule_register.md input table (the .md documents excluded or included, stated).
4. anchor_none / anchor_ambiguous / account_unresolved never fire on shipped data: expected under Shape D; QC_DEFENCE answer = BRANCH_FIRE.md + AL-27 hidden triggers (PB1, PB1b, PB2, quiet accounts) with the rule sentences in billing_terms.md and correction_policy.md.
5. Transfers dated after the window end and PAYMENT lines whose account= differs from the invoice's account: state the order/keying (payments keyed on invoice=; transfers after window end posted or ignored), or keep the generator from producing them.
