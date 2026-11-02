# Leak library (B3), v1 seeded 23 Oct 2026

One line per lever that leaked on a real trajectory: how it was written, the step it leaked at, and the fix rule. Build, rebuild, harden and fix sessions read this before designing. New rows come from P9 v2 diagnoses (`LEAK_LIBRARY rows` section); the master appends them at intake. Rule ids (W*, G*, J*) refer to `knowledge/LEVER_RULES_v1.md`.

## Common causes (cohort harden_r2 DIAGNOSIS section 0, confirmed by vendor harden_lp1_r1 section 3)
- Every rule was one explicit sentence that named its own exception; no rule had a plausible wrong reading. Fix: W2, W3.
- Two rules spelled out the trap in the rule text. Fix: W1 (hard rule in `_COMMON_RULES_v2` Never 8).
- The only "split across files" was a two-file read that the instruction pointed to together. Fix: L4 with 3 to 5 files, W2.
- A decoy was refuted on the same page as its use. Fix: never ship a decoy with its refutation beside it; use L6/W3 forms.
- Shipped boundary rows let the agent watch each rule fire. Fix: W5 (separating cases hidden-only, except L5), W6.
- Hidden cases only repeated rules the agent had already coded; the agent's own self-test covered every hidden-case family. Fix: levers whose reflex reading passes shipped-data and invariant self-tests (L1, L2, L3).
- Judge "states figure X" criteria were met by the same code. Fix: J1, J2.
- The earlier low score was a grader permission artefact, not difficulty. Fix: Phase A before any baseline (LEVER_RULES section 6).

## Rows: cohort-retention-reconciliation (a2 trajectory bb8ec0, 100/100/100)
| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| CR-1 every reason per rejected row | audit_policy.md L20-25, the trap spelled out ("not only the one for the cleaning step that removed it"); shipped rows e030/e031/e033 carry 2 reasons each | step 8 plan; step 11 `rejection_register` | W1, W5 |
| CR-2 plan in force (decoy) | decoy pointer "its account's plan" (schema.md L107) resolved two paragraphs later in plain words (audit_policy.md L9-16); shipped a002/e009 shows it | step 11 `plan_in_force` | W5, W6; decoy never refuted beside its use |
| CR-3 non-purchase subtracts | one sentence, schema.md L104-105, no alternative reading | step 11 | W3 (needs a real second reading) |
| CR-4 strict malformed | one sentence, schema.md L59-61; the regex follows from it | step 11 DATE_RE / DIGITS_RE | L5 form instead: strict field beside a normalising rule |
| CR-5 two duplicate notions | split across 2 files but each fully explicit | step 8 plan ("register independently on raw rows"); step 11 | L4 with 3 to 5 files |
| V0-1 cleaning order | schema.md numbered steps 1-6 | step 11 | numbered lists leak; W3 |
| V0-2 pre-cohort out | schema.md L92 "never before its own cohort" | step 11 | W3 |
| V0-3 exclusion on resolved account | schema.md L68-73 | step 11 | W2 |
| V0-4 merge history | schema.md L28-32, chain and tie stated together | step 8 plan quote; step 11 | L3 state, W2 |
| V0-5 minimum value | schema.md L80-81 | step 11 | W3 |
| V0-6 offset_zero flag | schema.md L118 | step 11 | W3 |
| V0-7 fraction format | schema.md L12-15 | step 11 `rate()` | format rules are not levers |
| V0-8 survival running min | schema.md L98 "never rises" | step 11 `floor = min(...)` | W3 |

## Rows: vendor-archive-roundtrip-recovery (a2 trajectory 0204d5, 100/100/100; from harden_lp1_r1 DIAGNOSIS section 3)
| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| RUN state per stream run | decoder_appendix.md L17-21, next to its use; shipped stream 3 separates the readings; judge R1/R2 made the agent compute it | step 12 | W2, W5, J1 |
| REV own revision per segment | decoy (loader_notes) refuted in plain words on the line that uses it | step 12 | decoy never refuted beside its use |
| REMAP before alias | numbered procedure, format_contract.md L131-142 | steps 11-12 | numbered lists leak |
| STATE dict/reset | exception written as its own sentence, format_contract.md L97-99 | step 12 | W3 |
| ESC/EXT bounded unescape | escape_rules.md L11-16 explains the trap | step 12 | W1 |
| SALV resync and state | escape_rules.md L54-65 names both reflexes | step 12 | W1 |
| ENC delta_raw_len | stated twice; caught by the agent's own self-test (step 25) | step 15 | self-testable rules are not levers |
| REJ precedence | numbered list in one file | step 12 | numbered lists leak |
| judge R1-R4 figures | figures asked in the instruction, computed from shipped files | steps 22-23 | J1 |
