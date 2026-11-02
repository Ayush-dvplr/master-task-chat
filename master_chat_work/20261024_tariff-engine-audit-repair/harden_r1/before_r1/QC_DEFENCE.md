# QC_DEFENCE: tariff-engine-audit-repair (a5f8657)

Live rule text quoted from `20261024_process/qc_reverse/A/checks.json` (pass_condition); fallback rows from `QC_FIX_PLAYBOOK_v2.md`. File:line references are planned positions; Phase 8 replaces them with real lines.

## Rules quoted once
- IN-15: "Judge whether an agent could tell, before acting, whether a given action complies." Not required: the prompt may delegate ("the rules are in /app/ci/api_contract.md").
- IN-16: "a graded expectation with two defensible readings and nothing in any agent-visible file to settle them"; "A finding without both readings written out is not usable".
- TS-13: "A test asserting two unrelated properties hides which one failed and skews the weight".
- TS-19: "Every graded behaviour must be learnable by the agent, and every promise made to the agent must be graded by something."
- TS-20: "a core-deliverable test carrying weight 1, or an existence/formatting check carrying 5, is wrong."
- TS-26: "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice." Not a duplicate: "two tests reading genuinely different aspects of the same object".
- AL-28: "name the single concrete agent action that triggers it"; one action never fires more than one max-severity penalty.
- JD-7: "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/."
- JD-15: outcome criteria trace to the contract; conduct criteria need no instruction sentence; "conduct preference criteria weighted 1 or 3" minor; "odds-raising conduct criteria weighted 5" minor.

## LV-TR-4 strict quantity (L5)
- IN-15: stated twice in `api_contract.md` (field block; malformed list), each value type named (string, decimal point, exponent, true, false, null, negative). An agent can tell before acting that `"37"` is a JSON string. PASS reuse: QC_RULINGS REUSE "strict field beside a normalising rule, stated twice".
- IN-16: readings "quoted digits are a JSON string -> malformed" vs "trim rule normalises strings, so `" 37 "` is 37". Settled: the trim sentence names its fields (`account`, `meter`, `read_id`), the quantity block says "a JSON integer" and the malformed list says "a JSON string". QC_RULINGS AVOID schema v3:32 avoided by naming every value type.
- TS-13 / TS-26: T6 (shipped exceptions), T9 (H1 exceptions) own exception rows; T10 owns energy lines; coupled T12-T23 own settlement keys. Different observables.
- TS-19: hidden quoted values are integers 0..9999 inside the stated bounds; asserted in the generator (G12).
- AL-28: no negative grades the lever.
- Fallback: IN-16 row DO: "one settling clause in the governing file, written for the general case ('for every value type ...')": `api_contract.md` quantity block gains "for every value type, only a JSON integer is accepted". TS-26 row DO below.

## LV-TR-3 proration denominator (L9)
- IN-15: "days in the month" + Definitions entry "month: the account's billing period, its row of billing_periods.csv, from start to end with both days included" + rate card "standing_charge: the charge for one month of supply". Stated in the governing file, bare property, clause form (W3).
- IN-16: readings "calendar month of the period start" vs "billing period". Settled by the Definitions entry in the same file; the kit requires "nothing in any agent-visible file to settle them" for a finding. PASS reuse: QC_RULINGS REUSE "global default + exception elsewhere / one settling sentence in governing file".
- TS-19: hidden periods 2..62 days inside the stated period bounds; the meter active window inside stated bounds.
- TS-20: T11 and coupled tests w5 (core, hidden whole-row).
- Fallback: IN-16 row DO: add one general clause to the Definitions entry "every use of month in this file means this period" in `api_contract.md` (never a worked figure, never in instruction.md). IN-15 row DO: restate as a bare property in the Standing charge stage in the file's own vocabulary.

## LV-TR-2 exact-decimal half-even, round the total (L8)
- IN-15: Amounts stage states decimal values as written, half to even at 0.01 per line, subtotal = sum of line amounts; Credit stage states total rounding and credit = subtotal - total.
- IN-16: readings "round the credit, total = subtotal - credit" vs "round the total, credit = subtotal - total": settled by the Credit stage sentence (total is the rounded figure, credit is the difference). "float then round" vs "exact decimal": settled by "computed from the decimal values as written".
- TS-19: tie lines use rates with <= 8 decimals and integer units inside stated bounds.
- TS-26: T10 (energy lines) vs T12 (subtotals) are different keys; a tie error changes both by design (G1 amplification through COUPLING).
- Fallback: IN-16 row DO: one general clause in the Amounts stage "every figure in this file is an exact decimal; no step uses binary floating point" (general case). TS-20 row DO: keep T10/T12-T23 at 5.

## LV-TR-1 contract over visible tests (amplifier)
- IN-15: arbiter sentence in instruction and contract; "Visible tests" section states correction, no deletion/rename/skip, and the `corrected_tests` key.
- IN-16: "may I delete a contradicting test" settled by "no visible test function is deleted, renamed or skipped".
- TS-13: T2 (delivered tests pass on delivered package) and T3 (`corrected_tests` exact) are separate properties.
- TS-20: T2/T3 w3 (sub-goal), below core settlement tests: matches the instruction's priority (invoices first).
- AL-28: `negative_visible_test_removed` -3 is the only penalty for that act; judge has no criterion on it.
- Fallback: TS-26/JD-14 row DO if T2 and `negative_visible_test_removed` are read as one observable: narrow T2 to "unittest exit status 0 on the delivered package", negative stays "a function name from the shipped file is absent or carries a skip decorator".

## Cascade: COUPLING (credit base) across T12-T23
- TS-26 risk: subtotals, credits and totals of one corpus share upstream rows. Defence: three keys, three rules (sum of line amounts; threshold + rounding of the total; credit = difference). Kit: "NOT a duplicate: genuinely different aspects of the same object". The four corpora differ in seed and mutation (G6), so they are different inputs, not repeats.
- CL-4 (recorded): one wrong line costs about 20/111 (line test + one corpus' settlement tests); not required by CL-4: "exact-match bar stated deliberately".
- AL-28: no negative on settlement figures.
- Fallback: TS-26 row DO: "narrow the wording of one so they read different observables": T13-style credit tests compare the credit against the rule applied to the delivered subtotal of the same account (a different decisive logic), weight kept at 5 in the COUPLING family; never delete the hidden whole-row totals tests.

## Judge (JD-7, JD-15, AL-28)
- JD-7: every conduct criterion R1-R6, R8 is performed by a `solve.sh` self-check stage printing `check <id> ok`; R7 holds by construction of the oracle repair (no bare except, short functions, no dead code); negatives R9-R11 avoided by solve.sh. JUDGE_MAP.md gives the oracle line for each.
- JD-15: R1-R6 conduct (odds-raising) w3; R7 code quality = conduct w3 (QC_RULINGS REUSE "code-quality named shape"); R8 final-reply enumeration = conduct w3; R10 contract edit = constraint, labelled `instruction following`, quotes "When the code ... disagree with this file, this file wins" and the file path.
- AL-28 acts: hard-coding (test -5 only), removing a visible test (test -3 only), unproven pass claim (judge -5), editing the contract (judge -3), reading grader paths (judge -5). One layer per act.
- Fallback: JD-7 row DO: fix the oracle and TRUTH.md to meet the criterion; JD-15 row DO: re-label, never announce judge expectations in instruction.md.
