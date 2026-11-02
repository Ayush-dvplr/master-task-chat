# PL note: dispatch-plan-reoptimization (eb5e097), P12 r1

QC v1 (kit 3fb1650b, same as live kit) found 4 fails, 3 minors, 2 warns. We agree with 8 and fixed all 8. One warn is informational.

## False positives (rebuttals)
- W9 (structure_qc X1, binary files skipped): this is an information line, not a defect. The script itself says "re-check any that are text"; the five files (docx, xlsx, sqlite, pdf, manifest db) are real binary formats the task is built on, and QC already checked them by hand and found nothing. Nothing to fix.

## Kept minors
- None. All three minors (M5 stray cache.txt, M6 TRUTH.md slips, M7 R6 wording) were cheap and fixed.

## UNSURE questions
- None.

## What changed (for the re-run)
- instruction.md now states the no-randomness / no-clock rule the nondeterminism negative grades (F1).
- JSON artifacts are compared by value and JSON type, so 1, 1.0 and true differ; key order still free (F2).
- New judge criterion R9 on solver.py code quality, weight 3; judge total 21, reward weight 0.5/21 (F3).
- Handbook states that certificate checks and budget_binding are JSON booleans (F4); the stricter type compare keeps difficulty.
- cache.txt removed, TRUTH.md counts and hashes match the shipped bundle, R6 reworded in positive grammar, OPENAI_API_KEY stripped from the solver's environment in the verifier.
