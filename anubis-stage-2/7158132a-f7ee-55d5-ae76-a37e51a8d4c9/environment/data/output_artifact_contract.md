# output artifact contract

A settlement run writes every artifact below into its output directory,
in this order for the purpose of the digest. Names are exact.

  01. canonical_contact_ledger.csv
  02. admitted_contact_ledger.csv
  03. rejected_contact_ledger.psv
  04. normalized_contact_intervals.tsv
  05. antenna_capacity_ledger.csv
  06. capacity_cap_exceptions.psv
  07. contention_groups.jsonl
  08. winning_resource_assignments.csv
  09. displaced_contact_ledger.psv
  10. mission_entitlement_state.csv
  11. carry_forward_ledger.csv
  12. rationing_pass_trace.jsonl
  13. delivered_volume_ledger.csv
  14. deferred_volume_ledger.csv
  15. unused_capacity_ledger.tsv
  16. station_utilisation_ledger.csv
  17. antenna_utilisation_ledger.tsv
  18. mission_settlement_statements.csv
  19. station_settlement_statements.csv
  20. contract_compliance_ledger.csv
  21. credit_debit_ledger.csv
  22. outage_adjustment_ledger.psv
  23. exception_classification_report.jsonl
  24. tie_resolution_report.csv
  25. cross_source_discrepancy_report.psv
  26. invariant_check_report.json
  27. period_reconciliation_totals.json
  28. network_settlement_summary.xml
  29. per_mission_final_summary.md

  30. stage_digest_manifest.json

Every artifact is written on every run, including when it has no rows.
An artifact is never omitted because it turned out empty.

The settlement program is a deliverable in its own right rather than
one of the thirty. It is placed once at /app/out/settle.py, and a run
of it leaves its own source alone, so the data directory stays the
only place a run reads from.
