# DIAGNOSIS: emberforge-vault-settlement, harden lp1 r1 (board e215748)

Result read: `20261021_emberforge-vault-settlement/baseline_v0/trajectory_job/trajectory/claude-opus-5/Run 1/`.
The run's suite (50 checks: cap_and_floor_*, retired_reagent_*, consumed_reference_*, requisitions_*) is the
harden r1 suite, so the run sat on the harden r1 bundle, two rounds before the current one (harden r2, P12 r1-r3).
Recorded harness score 43.07 (tests 3/155 from a permission trap); corrected Docker replay 146/155 = 0.9419,
rubric 84.21.

## 1. Baseline on the CURRENT tests (tests channel, local scorer)

Program saved as `agent_program/settle_vault.py` (1326 lines, sha256 fec9d8a0...). It recovers the council draw
from `calibration_controls.json` plus a `calibration_*` slice, both deleted in harden r2.

| program | earned / positive | score | evidence |
|---|---|---|---|
| as delivered | 2 / 101 | 0.0198 | crashes on missing `calibration_controls.json`; `evidence/score_current_as_delivered.json` |
| adapted: only `recover_draw` swapped to replay `council_rulings.json` | 87 / 101 | 0.8614 | `evidence/score_current_adapted.json` |

The as-delivered score is low only because the file it read is gone. That is not hardness. The adapted copy keeps
every settlement rule the agent wrote and scores 0.86. It is the reflex program used in STACKING_CHECK. It fails
only closure_mix (S6 credit window) and the quiet-rules season (crash on a missing forge reference).
Current suite also misses G1 (mixed tests assert 2 or 3 documents at once), G5 (no "graded whole" sentence), G6 (no
mutation test) and J1 (judge R1-R5 are "states figure X"). Not ALREADY_HARD; Phase 2 runs.

## 2. Lever table (trajectory, 23 steps)

Steps 3-9 read every document. Steps 10-14 wrote the whole program in one pass. Step 15 ran it once. Steps 16-22
checked only identities (charge sums, conservation, key order, Q2-Q6) plus its own 48-requisition stress season.

| lever | rule (current bundle) | step right | what gave it away | state now |
|---|---|---|---|---|
| LV-EF-1 cap judged on every forge, all conditions reported | A4 line 41, N3 "every other forge is tested against the charge cap, the vault floor and every retired reagent alike" | 14 (lines 599-622) | rule stated next to its use with the exception named | LEAKED (adapted passes consumed_cap_mix) |
| LV-EF-2 retired reagent V9 | V9 plus "never stands in for the charge cap or the floor" | 14 (600-605) | trap explained in the rule itself | LEAKED |
| LV-EF-3 consumed reference counts every floor-tested forge | register scope sentence | 14 (598 `floor_tested`) | one explicit sentence with the scope named | LEAKED |
| LV-EF-4 requisition ladder Q1-Q8 in 38 s | rulebook_requisitions.md | 14 (746-935), stress test step 20 | full rule set stated; agent self-tested speed | LEAKED (plan48, plan24, ld12 pass) |
| LV-EF-5 clerks digest decoy (same-day window) | S2 bold "strictly before" plus explanation | 14 | S2 explains the trap in bold | LEAKED in the adapted copy except one closure_mix case |
| L8 every-condition finding | N3 | 14 | stated beside the finding order | LEAKED |
| E3 salvage edition by source day | E3 plus "This is deliberate..." paragraph | 14 | trap explained | LEAKED |
| I3 identity time dependence | I3 explanation | 14 | trap explained | LEAKED |

Shipped separating examples: none since harden r2 (calibration removed). Self-test: identities only; the agent never
built an input that would split two readings of a rule. Every lever above leaked through rule text, not through data.

## 3. What Phase 2 changes

Retire LV-EF-1..5 as levers (keep the rules, strip the explanations). New levers per LEVER_PLAN_v1:
- L7: charge operators act on the unit charge; the forge charge is the reduced unit charge times units
  (rulebook_charge.md). Reflex: base charge times units first, then operators (agent `charge_of` line 449).
- L3: a credited salvage gives its source forge's charge back to the workshop's cap ledger from that salvage on
  (rulebook_salvage.md, exception to the A4 default in another file). Reflex: accrued charge = sum of settled charges.
- L6: the S2 credit window counts only "open forges", a term defined in the invariants glossary as a settled forge
  no salvage has been credited against. Reflex: every settled forge occupies the window.
- L1: no shipped control figure exists in the data (no counts or checksums); not used.
