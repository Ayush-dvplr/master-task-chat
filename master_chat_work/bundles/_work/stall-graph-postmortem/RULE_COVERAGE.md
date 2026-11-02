# RULE_COVERAGE (harden round 1)

One AL-2 unit per row. The mutant reads that one rule the reflex way inside the reference
(tests/test_output.py decode_journal, resolve_identity, resolve_owner, derive, settle_blame) and is
scored on the 36-check channel; the last column counts the positive checks it fails.
Measured 26 Oct 2026 15:05 IST with the temp driver coverage.py (deleted after the round).

| rule | written at | checks it fails (first four) | failing checks |
|---|---|---|---|
| 0x001 zigzag wait | journal-and-wire.md:42 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 14 more | 18 |
| 0x002 chained hold mask | journal-and-wire.md:48 | shipped_window_summary, shipped_policy_audit, trap-chain_hold, fresh and 12 more | 16 |
| 0x004 stride order over event lines | journal-and-wire.md:53 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 14 more | 18 |
| 0x008 biased declared count | journal-and-wire.md:60 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 15 more | 19 |
| 0x010 least significant byte first origin | journal-and-wire.md:68 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 15 more | 19 |
| 0x020 chained segment origin | journal-and-wire.md:72 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 15 more | 19 |
| 0x040 sentinel marks following line | journal-and-wire.md:76 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 14 more | 18 |
| 0x080 owner window reference | journal-and-wire.md:81 | shipped_policy_audit, trap-ring_owner, fresh, tie_config and 11 more | 15 |
| 0x100 coarse spin unit | journal-and-wire.md:88 | shipped_window_summary, shipped_reconciliation_record, trap-coarse_spins, fresh and 12 more | 16 |
| 0x200 rotated token | journal-and-wire.md:91 | shipped_window_summary, shipped_cell_reports, shipped_tenant_segment_reports, trap-rot_token and 13 more | 17 |
| 0x400 registry alias worker | journal-and-wire.md:95 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 15 more | 19 |
| 0x800 shadow slot | journal-and-wire.md:98 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 15 more | 19 |
| tick from exclusive hold prefix | epochs-and-clocks.md:13 | shipped_policy_audit, trap-zigzag_wait, trap-chain_hold, trap-stride and 22 more | 26 |
| lowest revision live row governs | identity-and-registry.md:22 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 25 more | 29 |
| alias walk six rows | identity-and-registry.md:34 | nonapplying_rule | 1 |
| retired by own non-active row | identity-and-registry.md:42 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 25 more | 29 |
| pool at the event own epoch | epochs-and-clocks.md:41 | boundary_shift | 1 |
| pool window half open | epochs-and-clocks.md:31 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 13 more | 17 |
| set aside tallied once per reason | invariants-and-closure.md:9 | shipped_reconciliation_record, trap-stride, trap-count_bias, trap-le_origin and 11 more | 15 |
| bytes emitted per spin | invariants-and-closure.md:20 | shipped_window_summary, shipped_reconciliation_record, trap-zigzag_wait, trap-chain_hold and 23 more | 27 |
| ordering by segment then slot | invariants-and-closure.md:44 | shipped_policy_audit, trap-zigzag_wait, trap-stride, trap-count_bias and 14 more | 18 |
| blame settles to a fixpoint | attribution-and-blame.md:30 | shipped_window_summary, shipped_policy_audit, shipped_cell_reports, shipped_tenant_segment_reports and 25 more | 29 |
| contended is a strict majority over budget | attribution-and-blame.md:20 | trap-zigzag_wait, cycle, boundary_shift, new_entity | 4 |
| implicated is a strict majority | attribution-and-blame.md:24 | shipped_policy_audit, trap-zigzag_wait, trap-stride, trap-le_origin and 14 more | 18 |
| quarantine needs rung 0 and contended | attribution-and-blame.md:42 | shipped_policy_audit, trap-zigzag_wait, trap-chain_hold, trap-stride and 19 more | 23 |
| within budget at or under | attribution-and-blame.md:45 | trap-zigzag_wait, trap-le_origin, cap_edge, scale_population | 4 |
| LV-2 padding writes owner window | journal-and-wire.md:83 | shipped_policy_audit, fresh, tie_config, cap_edge and 10 more | 14 |
| LV-3 owner tags follow alias rows | identity-and-registry.md:59 | trap-chain_hold, trap-count_bias, trap-chain_origin, trap-ring_owner and 8 more | 12 |
| LV-1 every cell and segment reports | invariants-and-closure.md:53 | trap-zigzag_wait, trap-stride, trap-le_origin, trap-sentinel and 8 more | 12 |

The alias walk six rows unit bites only generalises_when_a_dormant_rule_fires and the pool-at-own-epoch unit only generalises_when_the_pool_boundary_shifts; both were dormant-by-design variations before this round and are left as they are.
