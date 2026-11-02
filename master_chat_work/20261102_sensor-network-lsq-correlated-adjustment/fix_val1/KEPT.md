# KEPT - 3302dbb

| ID | Disposition | Evidence and boundary |
|---|---|---|
| S1.12 | KEPT by master disposition, Ayush 2 Nov '1. b' | `validate_bundle.py:51-68` matches a template only when its entire artifacts list equals the task's; Sensor's 32 outputs match none. `:86-87` defaults to format-recovery; `:837-840` then rejects the mismatch. Clearing this requires changing the task's output contract or harness templates, both forbidden. Same pre-existing FAIL shipped with slipway: `master_chat_work/20261102_slipway-overhaul-replan-repair/fix_ql1/FIX_REPORT.md:44`. Validator after: 48 PASS, this one FAIL. This is not a clean generic-validator verdict or authorization to ship. |
| X1 | KEPT binary-file structure WARN | `structure_qc.txt`: 17 pass, 1 warn, 0 fail. Five existing binary inputs are skipped: adjustment_control_workbook.xlsx, archive_backfill.db, archive_ledger.sqlite, datum_authority_record.pdf, field_survey_dossier.docx. Every input digest is unchanged; no binary content or artifact contract was edited. |

## Lessons for the master
Exact template artifact matching does not classify this custom task | no change: retain the approved manifest exception; do not alter its contract.
