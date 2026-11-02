# PL note: district-heat-flex-procurement (6fa0bdf), P12 r1

All 3 QC warnings were rechecked against the live kit (3fb1650b; same rule wording as the report's kit). All 3 are real and all 3 are fixed. There are no false positives, no kept minors and no open questions.

- DS-27: TRUTH.md no longer says the judge was not run. It now says "No oracle score exists for the judged channel."
- TS-25: the canonical-format check no longer passes on empty `{}` files. It now also needs a JSON integer at every integer field the schema defines. Same weight, same totals. This makes the task slightly harder.
- JD-18: R7 no longer pays for having no bad except clause. It is now a -1 penalty for a bare except or one that swallows the error. R8 (every function is called) stays as the positive code-quality criterion. The judge weight in reward.toml is now 0.5/19.

Gates: xref 0 findings; 4 QC scripts 0 FAIL; tests-only Docker runs: oracle x3 1.000, owner-only 1.000, nop 0.000.
