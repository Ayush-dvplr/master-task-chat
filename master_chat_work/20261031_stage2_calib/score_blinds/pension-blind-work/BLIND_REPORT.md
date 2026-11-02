# BLIND REPORT de212ed (stage2-calib-pension)

Session rename: name_session.py matched opencode ses_e6e77c684fferhR5uNSxzB5QTy.

## Files read, in order
1. instruction.md
2. environment/data/schema.md
3. environment/Dockerfile, data/policy.json, data/plans.json, `wc -l` + head -4 of every data/*.jsonl
4. tail of service_revisions.jsonl, salary_history.jsonl, leave_intervals.jsonl (all rows now seen)
5. (step 5 only, after freeze) blind-pension-20261031T1552-1540.judge.md

## Timing
Start 16:06 IST; first full write of calculate_pension.py ~16:08 (≈2 min). Single run: real 0.06 s.

## Self-check (shipped data only): PASS
Run exit 0, 9 reports. All 9 are canonical (sorted keys, indent 2, trailing newline) with contract top-level keys. Per member, the atom sums equal base accrual and credited days, base + revaluation = accrued = final ledger balance. Plan rollups equal the member sums. The audit chain recomputed to final_hash. The manifest sha256/bytes of all 10 inputs match. Details are in CHECKS.md.
Key figures: payable MEM-101 359369, MEM-102 253790, MEM-201 316957. There are 5 INVALID_* issues and 3 MATERIAL_BENEFIT exceptions.

## Crash fixed
None.

## Judge estimate
lower 15, upper 18 (of 56 positive). 8 process criteria not performed (R2-R8, R11): independent arithmetic spot checks, a fresh extract and a reorder/immutability rerun. No negatives fired.

## Lessons for the master
- The rubric pays 43/56 for validation acts: independent recomputes, a fresh extract and a reorder rerun. The blind protocol's "no extra test inputs" rule makes R8/R11 unattainable by design.
- The schema leaves revision_decisions row shape, record_counts keying, and record_id for REVISION_TIE_CONFLICT/INVALID_SERVICE unspecified, so the hidden tests may disagree.
- The ACCRUAL event_id and factor_bps for cola_ledger are undefined in the contract.
- It is unclear whether "every regular input file" in the manifest includes schema.md. I included it, giving 10 files.
