# PLAN
See TODO.md; design in DESIGN.md.

## Harden r1 plan (21:05 IST)
New levers: CR-1 (A) rejection register lists every reason per removed row (field in schema.md, definition in audit_policy.md; split across files);
CR-2 (B, decoy) plan in force on event date from plan_history.csv for the RESOLVED account, inclusive boundary; accounts.csv plan = opening plan (decoy default); shipped boundary e009 a002 2026-02-12;
 chained into weighted revenue -> weighted share -> segment weighted -> per-cohort -> reconciliation;
CR-3 (scope-by-omission) purchase adds, every other revenue type subtracts (hidden uses chargeback/credit names);
CR-4 (F) malformed rows: date must be YYYY-MM-DD real date (fromisoformat accepts 20260304), value plain non-negative digits; counts per step; crash poisons all docs.
Weights: hidden whole-doc ~70%, isolated <=30%, shipped-only artifact_set 1 only. Judge: 4 single-figure criteria (total revenue, weighted total, register reason entries, clean events), honesty negative, code quality.
