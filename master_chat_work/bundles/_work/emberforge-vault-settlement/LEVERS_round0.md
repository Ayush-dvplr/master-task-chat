# LEVERS (round 0, before hardening)

Lever names come from `solution/TRUTH.md` (Defect items 1 to 7) and the rulebooks. Run = claude-opus-5 Run 1 (20 Oct 2026, 00:10 to 01:25 IST), from `verifier/reward-details.json`; re-scored locally with the run's own program under method (b): 0.68, the same as the harness.

| lever | name (source) |
|---|---|
| STRUCT | delivery: program present, records parse, optional dirs (instruction) |
| B | dependent chain: charge, cap closure, vault, conservation, roll-ups (A4, H1-H5, V3-V4, N4, N5) |
| L1 | scarcity fixed point (TRUTH focal 1, V8) |
| L2 | draw recovery from the slice (TRUTH focal 2, instruction, calibration_slice.md) |
| L3 | requisition optimum (TRUTH focal 3, Q1-Q8) |
| L4 | dated, transitive identity; retirement on the canonical id (TRUTH drift 4, I2-I4) |
| L5 | salvage governed by the forge-day edition (TRUTH trap 5, E3) |
| L6 | one salvage per forge (TRUTH trap 6, S6) |
| L7 | every condition that holds is a finding, cap and floor at one forge (TRUTH trap 7, N3 x A4 x V4) |
| L8 | quiet rules, settlement order, window, scope (N1, A2, V2, S2, Q1-Q5 edge cases) |
| L9 | canonical serialisation (published bytes) |

## Per check

| check | w | lever | observable read | run |
|---|---|---|---|---|
| structure_program_delivered | 1 | STRUCT | settle_vault.py compiles, over 500 chars | pass |
| structure_artifacts_are_json | 1 | STRUCT | 11+ records parse, non-empty | pass |
| structure_program_takes_directories | 1 | STRUCT | summary.json on arg dirs and on defaults | pass |
| c01_canonical_smith_identity | 5 | L4 | workshop `smiths` rows; RETIRED_SMITH entry set | pass |
| c02_workshop_charge_cap | 5 | B | workshop charge_ember, cap_ember, cap_reached, charter_tier | pass |
| c03_vault_stock_and_timing | 5 | L7 | vault opening/acquired/consumed; STOCK_FLOOR entry set | FAIL |
| c04_salvage_credit_window | 5 | L8 | summary credited/uncredited; UNCREDITED_SALVAGE set | pass |
| c05_scarcity_assignment | 5 | L1 | summary and vault scarcity_index | pass |
| c06_settlement_order | 5 | B | workshop entries_admitted/rejected | pass |
| c07_governing_edition | 5 | L5 | UNRESOLVED_EDITION set; vault returned_units | pass |
| c10_findings_canonical_form | 1 | L7 | finding order, dedupe, known entries, counts | pass |
| c11_conservation_closes | 5 | B | reconciliation patches, residuals | pass |
| c12_requisition_allocation | 5 | L3 | allocation.json; workshop allocated_units | pass |
| c13_canonical_serialisation | 3 | L9 | raw bytes of every record | pass |
| c14_repeated_salvage | 5 | L6 | SALVAGE_ALREADY_CREDITED set | pass |
| stage_01_season_window | 1 | L8 | summary season, entries_total | pass |
| stage_02_charter_binding | 1 | L8 | workshop guild_id, charter_id | pass |
| stage_03_season_admission_totals | 1 | L8 | summary admitted/rejected | pass |
| stage_04_finding_details | 5 | L7 | detail column per code | FAIL |
| stage_05_vault_closing_balances | 5 | B | vault closing, grade, scarce | pass |
| stage_06_charge_rollup | 5 | B | reconciliation charge maps, summary and guild charge | pass |
| stage_07_reagent_flow | 5 | B | workshop and guild reagent_flow | pass |
| stage_08_guild_rollup | 5 | B | guild workshops/admitted/allocated; N5 agreement | pass |
| gen_draw_shift_alpha | 5 | L2 | every record, corpus under RS-F/half-up/SGF/opening | FAIL (L7 cascade) |
| gen_draw_shift_beta | 5 | L2 | every record, corpus under RS-G/ceil/FSG/acquired | FAIL (L7 cascade) |
| gen_priority_tie_flip | 5 | L3 | every record, RQ01 priority raised | FAIL (L7 cascade) |
| gen_cap_boundary_push | 5 | B | every record, caps 50000/22000 | pass |
| gen_partition_change | 5 | L8 | every record, two workshops out of scope | pass |
| gen_temporal_boundary | 5 | L8 | every record, edition and acquisition shifted | FAIL (L7 cascade) |
| gen_identity_merge_chain | 5 | L4 | every record, two-step merge chain | FAIL (L7 cascade) |
| gen_nonapplying_rules | 5 | L8 | every record, quiet rules triggered, ledger reversed | FAIL (L7: CAP+floor forge L0902 at an open workshop) |
| negative_hardcoded_sample_answers | -3 | cheat | summary on cap_push corpus equals shipped | not triggered |
| negative_filename_dependent_behaviour | -1 | cheat | output differs by dir name | not triggered |
| negative_nondeterministic_output | -1 | cheat | two runs differ | not triggered |

Every gen check compares all 11 records of a whole corpus, so it fails on any lever that corpus touches; the run's 6 gen failures all come from L7 (local diff: only `data_quality.json` differs, missing STOCK_FLOOR co-findings; in nonapplying also the cap closure L0902 triggers).

## Totals per lever

| lever | points | run earned | status |
|---|---|---|---|
| STRUCT | 3 | 3 | LEAKED |
| B | 40 | 40 | LEAKED |
| L1 | 5 | 5 | LEAKED |
| L2 | 10 | 0 | LEAKED (own reading right; lost via L7 cascade) |
| L3 | 10 | 5 | LEAKED (own reading right; lost via L7 cascade) |
| L4 | 10 | 5 | LEAKED (own reading right; lost via L7 cascade) |
| L5 | 5 | 5 | LEAKED |
| L6 | 5 | 5 | LEAKED |
| L7 | 11 | 1 | HELD |
| L8 | 23 | 13 | LEAKED (own reading right; lost via L7 cascade) |
| L9 | 3 | 3 | LEAKED |
| total | 125 | 85 (0.68) | |
