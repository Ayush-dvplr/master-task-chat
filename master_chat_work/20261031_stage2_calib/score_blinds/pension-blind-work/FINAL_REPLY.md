Built `/app/out/calculate_pension.py`, a Python standard-library PACR-1.0 engine run as `python3 /app/out/calculate_pension.py DATA_DIR OUT_DIR`. It ran on the shipped extract and wrote all nine reports to `/app/out`: manifest, data_quality, service_ledger, accrual_ledger, cola_ledger, member_benefits, plan_rollups, exception_register and audit_trace.

What it does:
- Service revisions: picks the winner by maximum (revision, chronological UTC recorded_at, record_id), flags REVISION_TIE_CONFLICT, gives cancelled winners a decision with no effective service, and validates active winners (INVALID_SERVICE).
- Input validation: members, salary, leave, COLA, rebase and elections are checked with the INVALID_* codes and quarantined. Each member's election is the one with maximum (retirement_date, election_id).
- Accrual atoms: half-open atoms cut at service endpoints, overlapping salary and leave endpoints, January 1 and the valuation date. Salary is the covering record with maximum (start, salary_id), capped at the plan cap. Leave factor is the minimum covering credit_bps. ROUND_HALF_UP is applied only to credited_days and accrual_cents. A missing salary raises MISSING_SALARY as `service_id:start`.
- Revaluation: a chronological ACCRUAL < COLA < REBASE event stream applies the factors with ROUND_HALF_UP. Events after the valuation date are ignored.
- Payable: early-retirement reduction, then the option factor, each rounded once.
- Rollups, exceptions and audit: plan rollups, MATERIAL_BENEFIT where |payable| >= material_cents, and a SHA-256 audit chain starting from 64 zeros.
- Determinism: input rows are canonically sorted before processing. Output uses integer cents, days, months and bps, sorted keys, 2-space indent and a trailing newline.

Self-check on the shipped data (one run, real 0.06 s, exit 0): PASS.
- All nine files are byte-identical to their canonical serialization.
- Atom sums equal each member's base accrual and credited days, and base + revaluation = accrued = final ledger balance.
- Plan rollups equal the member sums.
- The audit chain recomputes to the stored final_hash.
- Manifest counts and the sha256/byte values of all 10 inputs match.

I did not test the program on any other extract or with reordered rows.

Key figures (valuation 2025-01-01):
- **Counts:** 3 valid members, 3 effective services, 22 atoms.
- **Issues (5):** INVALID_ELECTION EL-BAD, INVALID_LEAVE LV-BAD, INVALID_MEMBER MEM-BAD, INVALID_SALARY SAL-BAD, INVALID_SERVICE SR-BAD.
- **Member benefits:**
  - MEM-101: accrued 450041, payable 359369 (EL-101, reduction 1225 bps)
  - MEM-102: accrued 359780, payable 253790 (EL-102, reduction 2415 bps)
  - MEM-201: accrued 401312, payable 316957 (EL-201, reduction 1025 bps)
- **Plan payable:** PLAN-A 613159, PLAN-B 316957.
- **Material benefits:** 3 MATERIAL_BENEFIT exceptions.
- **final_hash:** 44d8a2a09a13ab9b894332ff1d76df60ca5ac80e45ad6e0035a74af73ec10df6

The contract left some report details open, so I chose these:
- record_counts is keyed by file name for the jsonl files and plans.json.
- Revision decisions carry service_id, record_id, revision, recorded_at, status, candidate_count, tie_conflict and effective.
- INVALID_SERVICE uses the winning record_id, and REVISION_TIE_CONFLICT uses the service_id.
- ACCRUAL events have event_id `service_id:start` and factor_bps null.
- Members without an election get null election fields, 0 early months and 0 reduction.
