VERDICT: All three blinds exactly match Opus scores and lost checks, but pension has an additional ledger mismatch, so score calibration does not establish complete root-cause equivalence.

## Scores

| task | Opus tests | blind tests | checks lost by both | only Opus | only blind | blind judge est | Opus judge |
|---|---:|---:|---:|---:|---:|---:|---:|
| billing | 7/97 (7.2165%) | 7/97 (7.2165%) | 18 | 0 | 0 | 11-14/58 | 14/58 |
| pm25 | 10/110 (9.0909%) | 10/110 (9.0909%) | 20 | 0 | 0 | 11/58 (8-11 sensitivity) | 14/58 |
| pension | 12/52 (23.0769%) | 12/52 (23.0769%) | 8 | 0 | 0 | 15-18/56 | 12/56 |

All three independent oracle runs scored 100% (97/97, 110/110, 52/52). No judge was run. Blind estimates above are copied from each blind work folder, not newly scored; PM2.5 preserves both its JSON estimate and its Markdown penalty caveat. The original combined rewards (0.1568, 0.1661, 0.2225) are not test scores.

## Causes And Calibration

- Billing: same root as Opus YES, with all 13 report bytes identical on all 18 hidden extracts. Every generated extract changes at least one handset offset by day, contradicting `record_dictionary.md:19` (clock never adjusted). Example hidden 01 H-16 requires offsets -1 and +5. Both programs assume one fixed offset. Region gross/segment net threshold handling is explicitly correct, not a separate defect.
- PM2.5: same root as Opus YES, with all nine report bytes identical on all 20 held-out extracts. Every extract has one or more offset steps, contradicting `record_dictionary.md:40-44` (offset holds for every card row). Example held-out 01 AQ525 changes from -3 to -12 at row 560; its received_packets expects 1749 versus 1256. Do not interpret every downstream mismatch as an independent clock or arithmetic mistake.
- Pension: shared root as Opus YES, all roots identical NO. Both choose metadata schemas the contract leaves unspecified (`schema.md:27,29`), and both use SR-BAD where the frozen oracle requires SVC-BAD. A2 independently names these P-COUNTS, P-DECISIONS and P-INVALID-ID. The blind additionally writes ACCRUAL rows into the COLA ledger, unlike Opus. Removing only those rows makes that entire report match in every scenario. We attribute this to RULE-MISREAD of the revaluation-recording distinction in `schema.md:19`; the report stanza at line 33 does not explicitly enumerate allowed event kinds, so this attribution has residual contract ambiguity. In every scenario, manifest, accrual ledger, member benefits, plan rollups and audit trace match exactly. Valuation clipping also exposes the reference rejecting otherwise valid future events instead of merely ignoring them (schema lines 11,19).

Primary loss attribution counts each failed check once: billing UNFAIR 90/90 (100%), PM2.5 UNFAIR 100/100 (100%), pension RULE-MISREAD 40/40 (100%), with shared UNFAIR metadata blockers on those same 40 pension points. Overall: UNFAIR 190/230 = 82.61%; RULE-MISREAD 40/230 = 17.39%; other primary codes 0%. This is a transparent attribution convention, not a uniquely identifiable split: fixing only the blind COLA ledger still leaves all eight pension checks lost. If its event-kind omission is treated as under-specification too, UNFAIR rises to 230/230 (100%). No paid-run quality conclusion should hinge on that labeling choice.

AMPLIFIED is secondary, never added again to lost points. One clock assumption or one extra ledger event family expands into many positional field differences, and one bundle mismatch costs all five points. N below counts recursive field paths, including list displacement, not N independent semantic defects.

| task | lost checks instrumented | blind mismatched field paths per check | execution |
|---|---:|---:|---|
| billing | 18 | 667-29534 | 0.451-1.472s per instrumentation case; No exception; successful program, exact predicate returns false |
| pm25 | 20 | 3-186 | 0.710-6.185s per instrumentation case; No exception; successful program, exact predicate returns false |
| pension | 8 | 145-157 | 0.027-0.037s per instrumentation case; AssertionError, empty message; program itself exits successfully |

Every lost check has expected/actual report files, a field-level `diff.json`, exception type/message (null when no exception occurred), wall time, and truth offsets or a verified frozen oracle hash under `blind-evidence/<task>-instrument/<case>/`. Independent Opus runs are under `opus-evidence/`. `INSTRUMENTATION.json` indexes all 46 checks; each CSV links its exact trace and records its own N and root. No observed crash or timeout. Billing reference-only `__stdout__` is excluded to match the real REPORT_NAMES predicate; normalization script documents this instrumentation correction.

## Gate Recommendation And Provenance

Use a blind as a cheap directional gate for these test scores: all 46 lost positive checks agree and there are zero one-sided losses. Do not use shipped-data self-check PASS, exact score equality, or the blind judge estimate as evidence of fair hidden coverage or identical solution quality. Audit the task contract first, then inspect roots and financial invariants. Pension demonstrates a blind-only mismatch that the already-failing whole-bundle checks completely mask. These three cases do not establish calibration on unrelated tasks or a judge-score predictor.

All source tasks and blind folders were read-only. Harbor used only `--agent oracle`: frozen blind program copied to the exact instruction path and run on shipped data, or the original solution on the oracle copy. QC exe_copy disabled the judge and normalized deterministic weights; task check modules remain byte-identical. Infrastructure-only changes use cached local `python:3.12-slim`, remove the unused OpenHands installation and permit Docker Desktop network metadata. Instrumentation containers were network-disabled and unprivileged program runners remained unchanged. A2 instrument.py was copied unchanged and executed for pension; A1 scripts did not exist when clock instrumentation was authored, and its later diagnose.py was read for cross-checking. Original logs and captured verifier results are retained. The first instrumentation attempt failed before container creation because A2 had removed its image; rebuilding an owned cached image resolved it without grading edits.

Session rename was attempted first and returned NOT RENAMED (no matching board session). No subagents, paid agents, host pip, git, or web were used. Python/Bash language servers were unavailable; syntax checks, six real Harbor runs and six real instrumentation runs provide execution validation instead. See `VALIDATION.json` and `CLEANUP.json` for final validation and resource cleanup.
