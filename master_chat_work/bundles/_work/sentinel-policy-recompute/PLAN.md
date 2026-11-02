# PLAN sentinel-policy-recompute (Harden P9 v2 r1)

1. Data (WORK/gen_data.py, idempotent from SOURCE): ledger conventions/seq/rev/tenant/controls, override allowance, per-term risk rounding, clamp order, tier key, version selection, leak retirement, field spec.
2. Shipped tool.zip (WORK/build_tool.py): adds raw-reading ledger_controls and applied_overrides; keeps old faults.
3. Oracle solve.py: repaired resolve, self_check_ledger, driver.
4. instruction.md: trap list replaced by pointer and G5 sentence.
5. Tests (WORK/test_body.py + build_tests.py): 3 hidden corpora, 2 mutations, validate, canonical rerun, shipped merged; 3 negatives; P=52.
6. Judge batched 15 criteria P=38; reward.toml; tests/Dockerfile K8.
7. Docs: TRUTH, DESIGN, LEVERS, QC_DEFENCE, XREF; xref_check 0.
8. Phase 3: stacking_check, reflex gate (adapted 0.1538), QC scripts, validator, playground, Docker block.
9. Deliverables.
