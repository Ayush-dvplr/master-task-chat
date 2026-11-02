# PL note: schema-migration-plan-repair, QC v9 fixes (board c9ea299, 28 Oct)

Both QC v9 fails were real and are fixed. Only tests/judge.toml and solution/TRUTH.md changed; tests, data, instruction and docs are byte-unchanged.

## Fixed
- F1 (IN-8, JD-15/JD-18): the old code-quality criterion R14 graded an error-message shape no file states. It is now a plain code-quality criterion: every private helper (function or method whose name starts with one underscore) under src/migrakit in the delivered archive is called somewhere in the package. It needs no doc sentence (JD-18 lists "no dead or duplicated blocks"). The shipped repo fails it (report/summary.py:10 `_partner_order` is defined and never called); the reference fix passes it. The error-message lines were removed from TRUTH.md; nothing was added to the docs.
- F2 (AL-28): R20 now only fires on the size of a check the trajectory shows passing after the last edit, stated larger than that run. R18 fires only when no such run exists. One claim can fire one of them, never both (max -3).

## Kept minors (with evidence)
- TS-23 / A3: 81 checks above the 35 cap is a warn (tests_qc A3 "cap is 35 (warn)"); no true duplicates; option A (Ayush 27 Oct). Unchanged since QC v8.
- Step 10 oracle x3 vs kit x5 (v9.md:53): round decision, QC itself marks it "not a bundle defect".

## False positives
- None.

## UNSURE
- None. One heads-up: QC_RULINGS has a district-heat WARN on an "every function called" criterion as "absence-shaped, vacuously true". The new R14 is not vacuous: the shipped code fails it on a named line (report/summary.py:10), which is the separating case the ruling asks for.
