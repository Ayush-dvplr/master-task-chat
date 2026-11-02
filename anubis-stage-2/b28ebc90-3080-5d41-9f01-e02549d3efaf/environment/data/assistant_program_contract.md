# Daybreak routing programme contract

Cycle HB-2034-231, acquisition profile weekday.

The router turns one directory of working papers into the
twenty eight derived documents of one routing cycle. It runs in
fourteen stages. Each stage has one specification paper and
consumes only what the stages before it published.

## Stages and their papers

| stage | title | paper |
| --- | --- | --- |
| r01 | unit normalisation | `spec_stage_r01_unit_normalisation.md` |
| r02 | identifier resolution | `spec_stage_r02_identifier_resolution.md` |
| r03 | routine expansion | `spec_stage_r03_routine_expansion.md` |
| r04 | policy layer resolution | `spec_stage_r04_policy_layer_resolution.md` |
| r05 | initial eligibility | `spec_stage_r05_initial_eligibility.md` |
| r06 | dependency graph | `spec_stage_r06_dependency_graph.md` |
| r07 | cycle settlement | `spec_stage_r07_cycle_settlement.md` |
| r08 | canonical order | `spec_stage_r08_canonical_order.md` |
| r09 | demand | `spec_stage_r09_demand.md` |
| r10 | capacity binding | `spec_stage_r10_capacity_binding.md` |
| r11 | fallback expansion | `spec_stage_r11_fallback_expansion.md` |
| r12 | precedence overturn | `spec_stage_r12_precedence_overturn.md` |
| r13 | state transitions | `spec_stage_r13_state_transitions.md` |
| r14 | feedback and publication | `spec_stage_r14_feedback_and_publication.md` |

## Stage order

A stage runs only after every stage that feeds it. The feeding
relation is:

- r01 feeds r02
- r01 feeds r03
- r02 feeds r03
- r01 feeds r04
- r02 feeds r04
- r03 feeds r04
- r04 feeds r05
- r03 feeds r05
- r01 feeds r06
- r02 feeds r06
- r05 feeds r07
- r06 feeds r07
- r07 feeds r08
- r05 feeds r08
- r04 feeds r09
- r08 feeds r09
- r09 feeds r10
- r04 feeds r10
- r10 feeds r11
- r11 feeds r12
- r12 feeds r13
- r13 feeds r14
- r05 feeds r14
- r10 feeds r14

## What the router may not do

- It holds nothing about a cycle. Every identifier, count,
  control value, threshold and vocabulary member is read from
  the directory it is pointed at.
- It uses no binary floating point anywhere in the derivation.
- It writes only the derived documents, and only into the
  destination it is given.
- It leaves the paper directory byte for byte as it found it.
- Two runs over one directory produce identical bytes, and the
  same cycle under another directory name produces them again.

## Papers that are not plain text

- `capacity_and_intensity_workbook.xlsx` carries the per window
  per device energy ceilings, the per action class surcharges,
  the per capacity class window scales and the reserve share.
  Several grids of the same shape are present; the live one is
  the grid whose key cell equals the cycle key in
  `cycle_header.json`, byte for byte. Sheet name and sheet
  position say nothing about which grid is live.
- `household_operations_memo.pdf` carries the four scalar
  controls and the per routine occurrence cap table.
- `precedence_directive.docx` carries the seven policy layers
  and their ranks, the settlement key order, the mandatory
  reserve share, the number of reconciliation rounds and the
  layer one directive schedule.

None of those values appears in any other paper.
