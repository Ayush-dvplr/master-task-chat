# DESIGN_SUMMARY counter-page-crash-recovery (54e38ee), build-repair, seed 806610
Core: repair `pagerecover` (commit-filter replay + naive undo, tomli import, u32 pageLSN, unsigned
slots, wrong package-dir) into exact WAL crash recovery of counter pages: analysis from the master
record's checkpoint, per-page redo decided against the pre-record pageLSN, one global undo by
largest undo point following CLR undo_next, stated END placement and LSN numbering. Outputs:
package.zip, selftest, build_report, module_core (image), module_metrics, dependency_resolution
(appended records), summary (image sha256, client totals, audits). All rules in
recovery_contract.md; instruction states job, paths, whole-document exactness. No secondary lever.

Limits (contract): <= 1200 records and <= 24 pages per image, 4..8 slots, 12 images within 60 s.
Reference 0.003-0.008 s per image locally (Docker measure in P8, target <= 15 s for H3).
Inputs: 12 flat files, 9 formats; journal.jsonl ~17k lines, txn_catalog.csv ~2.6k; 5 chains >= 4.

Textbook ARIES (TB = eager pageLSN redo + textbook END placement) and baselines, whole docs lost
(c core, m metrics, d dependency, s summary), prototype t2/t3, 12-image books:
| program | dense H1 | restart H2 | max H3 | shipped (proto p_same 0.2) |
|---|---|---|---|---|
| TB textbook | cmds | cmds | cmds | cmds |
| TB END placement only | cds | cds | cds | cds |
| TB eager redo only | cms | cms | cms | cms |
| B1 commit-filter (shipped) | cmds 12/12 | cmds | cmds | cmds |
| B5 prev walk (double undo) | cmds 6-12 imgs | cmds | not run | cmds |
| B12 one-hop undo_next | cmds 1-5 imgs | cmds 2 of 3 seeds | cmds | none |
| B4 per-txn undo | cds | cds | not run | not run |
| B6 redo from checkpoint | cms 1-9 imgs | cms | not run | not run |
| B3 redo lsn >= pageLSN, B15 per-record | cmds all | cmds all | not run | not run |
Hidden seeds kept only if every baseline loses >= 1 whole doc on each book (G-4).

Tests 17 (88 pts): build 10, shipped book 4x3, H1/H2 4 docs x5, H3 5, H4 rejections 5,
mutations M1 shuffle+relocate 5, M2 rotate rows 5, M3 deleted source 3, M4 run twice 3; hidden +
mutation 75%; negatives 4 acts. Judge 9 (J2 x4, J9, J6, J4, J3 -4, grader-read -5), batched.
Cost (planned): eager alone loses 50/88 -> overall 0.665; END placement alone 50/88 -> 0.665;
one-hop alone ~45/88 -> 0.69 (thin; P4 COST_TABLE decides, DO fix = extra hidden coupled check).

Open questions: (1) shipped book uses the light profile (no same-page multi-change record, no
CLR-to-CLR stop) to keep W5 strict; OK? (2) H3 timing inside the document check vs split (TS-13).
Risk: a contract-transliterating program that decides each record's pages before applying it is
exact on every book; levers count only for phase-interaction slips and textbook END habits.
Detail: WORK/PREMORTEM.md, WORK/DESIGN.md, WORK/QC_DEFENCE.md.
