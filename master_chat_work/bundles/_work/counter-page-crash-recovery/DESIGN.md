# DESIGN counter-page-crash-recovery (board 54e38ee)

Archetype build-repair, category software-engineering, seed 806610. Core build (Ayush '2'):
the difficulty is exact write-ahead-log crash recovery over long logs where analysis, redo and
undo interact. No stated-rule secondary lever (0% of positive weight). Decoys, encodings and
duplicate ids are noise only. Prototype numbers: `WORK/proto/` (see PREMORTEM.md).

## 1. Spine
1. Repair the build: unzip `/app/data/project.zip` to `/app/project`, fix packaging and parser
   defects, ship `/app/out/package.zip` (layout from `expected_targets.json`, compression and
   timestamps from `compiler_flags.json`) plus `selftest.json` and `build_report.json`.
2. Replace the shipped recovery method (commit-filter replay plus naive reverse undo) with the
   method stated in `recovery_contract.md`.
3. Per crash image: validate (rejection codes, precedence) -> analysis (master record, checkpoint
   tables, forward scan) -> redo (per page decision against pre-record pageLSN) -> undo (one global
   descending sequence, CLR chains via undo_next, END placement, LSN numbering) -> recovered page
   image.
4. Reports from the recovered image and the recovery that produced it: `module_core.json`
   (image), `module_metrics.json` (counts and LSNs), `dependency_resolution.json` (losers and the
   appended record list), `summary.json` (image sha256, per-client totals, audit answers).
COUPLING sentence (contract, verbatim): "Every reported figure of a crash image is computed from
its recovered page image and the recovery that produced it."

## 2. Input files (`/app/data`, flat, 12 files, 9 formats)
| file | format | rows (shipped) | role / dependencies |
|---|---|---|---|
| project.zip | zip | ~12 members | package `pagerecover` (src layout), shipped tests, README |
| recovery_contract.md | md | ~170 lines | governing contract: every rule, schema, error string, limit |
| journal.jsonl | jsonl | ~17,000 lines | records of every image, field `image`; line order carries no meaning, log order = ascending lsn |
| disk_pages.bin | binary | ~400 page frames | per frame: image id, page id, pageLSN u64, slot count, slots i64, crc32 |
| page_map.ini | ini | one section per image | page id = slot count; defines the image's pages |
| checkpoint.toml | toml | one table per image | `master_lsn` (0 = no checkpoint) |
| txn_catalog.csv | csv | ~2,600 rows | image, txn, client |
| audit_queries.json | json | ~150 queries | id, image, pages, slot or "all" |
| dependency_manifest.json | json | small | module build deps (template) |
| compiler_flags.json | json | small | zip compression, fixed timestamp |
| expected_targets.json | json | small | archive members, report paths in task order |
| ci_config.yaml | yaml | small | CI commands echoed into selftest (single-quoted, '' = ') |
A5 volume: journal ~17k + catalog ~2.6k + contract/others ~0.6k > 20,000 lines; every csv/jsonl
>= 2,000 lines. Ids are random tokens with no meaningful prefix (DS-4).

Chains (length >= 4):
- C1 checkpoint.toml master_lsn -> journal ckpt_end tables -> analysis -> redo start and redo
  against disk_pages.bin pageLSN -> undo -> module_core -> summary image_sha256 and audits.
- C2 page_map.ini -> validation (E_UNKNOWN_PAGE) -> disk frame decode (E_BAD_IMAGE) -> recovered
  pages -> audit_queries.json answers -> summary.
- C3 journal CLRs from earlier restarts -> undo_next chains -> appended CLRs and ENDs (LSNs) ->
  pageLSNs in module_core -> dependency_resolution and summary.
- C4 txn_catalog.csv -> analysis winners/losers -> appended CLR deltas -> per-client compensated
  totals -> summary.
- C5 expected_targets.json + compiler_flags.json -> package.zip layout -> import of the archived
  package by the verifier -> every recovery document on hidden books.

## 3. Levers
All rules live in `recovery_contract.md` (W2, one contract file W10). instruction.md states the
job, paths and whole-document exactness only.

### LV-WR-1 exact recovered page image (analysis/redo/undo interaction)
Rule text (contract, Redo): "Redo reads every update and CLR from the redo start LSN in log order.
For each record, the pages it redoes are decided before any of its changes is applied: a page is
redone when it is in the dirty page table, the record's lsn is at least that page's recLSN, and
the record's lsn is greater than that page's pageLSN. Every change of the record on a redone page
is applied (slot value plus delta) and that page's pageLSN becomes the record's lsn." Plus
Analysis paragraph (master record checkpoint, scan from master_lsn) and Undo paragraph.
Reflex reading (PREMORTEM 2): per-change check with pageLSN updated after the first change
(eager), skipping the second change of a record that touches one page twice; or keeping the
shipped commit-filter replay; or `>=` against pageLSN.
Hidden cases: multi-change records with a repeated page (p_same 0.4), independent page flushes
so loser writes are on disk and committed writes are not, partial rollbacks with CLRs inside
winners and losers, CLRs redone.
Why visible data cannot confirm: no recovered image, checksum or count ships (W11); shipped book
uses the light profile (no record touches one page twice); the shipped unit fixtures hold one
winner and one loser with no flush; the contract carries no worked example (W6).
Baselines losing (t2/t3): B1 commit-filter, B2 CLRs not redone, B3 `>=`, B15 per-record decision,
B16 eager, B8 analysis from ckpt_end: whole documents on every hidden book.

### LV-WR-2 compensation chains (incl. an earlier restart interrupted during undo)
Rule text (contract, Undo): "A loser's undo point is found from its last LSN: an update record is
the undo point; a CLR moves to the record named by its undo_next; any other record moves to its
prev; a null pointer means the loser has no undo point." and "The CLR's undo_next is the undone
update's prev." CLRs already in the log (from rollbacks or an earlier restart) are records like any
other; the contract states the walk, not their origin (IN-17).
Reflex reading: textbook ToUndo follows undo_next correctly, so redesigned (PREMORTEM 5): hidden
restart book stops earlier restarts right after a CLR whose undo_next names a CLR, and between a
loser's last CLR and its END, so the stated END placement interacts with the chain. Hand-rolled
walks: prev walk through CLRs (B5, double undo), one hop from undo_next (B12).
Hidden cases: H2 (2-3 earlier restarts per image, hop forcing on last restart).
Why visible data cannot confirm: shipped book has at most one earlier restart and no CLR-to-CLR
stop; no answer ships.

### LV-WR-3 stated audit sequence
Rule text (contract, Appended records): "Recovery appends records to the image's log; each takes
the next LSN, the first one the image's largest LSN plus 1. First an END for every winner in
ascending transaction id, then an END for every loser that has no undo point in ascending
transaction id, then the undo steps. Each undo step takes the loser whose undo point has the
largest LSN, appends one CLR for that update, and, when the loser then has no undo point, appends
its END at once." and "Redo starts at the smallest recLSN in the dirty page table after analysis."
Reflex reading: textbook END placement (END when the chain reaches begin, committed ENDs in table
order), per-transaction undo, redo from the checkpoint LSN, ENDs without LSNs.
Interaction: appended LSNs become the pageLSNs of every compensated page, so an END slip moves the
image (module_core) and its checksum (summary), not only the appended list.
Baselines losing: B4 per-txn (cds), B6 redo from checkpoint (cms), B7 END placement (cds), B9 ENDs
without LSN (cmds) on every hidden book.

### Lever interactions
Redo must replay CLRs of earlier restarts (LV-WR-1) whose undo_next chains drive the undo
(LV-WR-2); undo writes CLRs whose LSNs (LV-WR-3) become pageLSNs of the image (LV-WR-1 output).
One slip anywhere moves module_core and summary image_sha256.

## 4. Rejection paths
Per image, `{"status": "rejected", "error": CODE}` in every recovery document; precedence stated:
E_BAD_IMAGE (frame crc mismatch, missing/extra frame, slot count differs from page_map) >
E_UNKNOWN_PAGE (change names a page not in page_map or slot out of range) > E_DUP_LSN > E_BAD_CHAIN
(prev or undo_next missing, not lower than own lsn, or of another transaction; non-begin record
with null prev). A crash image whose log ends inside a transaction is recoverable, not rejected.
Missing source file: nonzero exit naming the file. Hidden H4 plants each code alone and in
double-defect pairs (precedence). Shipped book: 2 rejected images (E_BAD_IMAGE, E_BAD_CHAIN).

## 5. Test plan (tests/test_output.py)
Hidden books are generated verifier-side by an embedded seeded generator (seed only in tests/,
fresh LSN ranges beyond 2^32, fresh ids, flush schedules, shuffled line order) inside stated
bounds (TS-19, G12 asserts); expected documents from an embedded reference. The agent's package is
imported from `/app/out/package.zip` and run as nobody from /tmp (G8).
| id | check | w | family |
|---|---|---|---|
| T1 | artifacts exist and parse | 1 | build |
| T2 | archive layout, compression, timestamps per targets/flags | 3 | build |
| T3 | build_report keys and pyproject facts | 3 | build |
| T4 | selftest.json truthful (reruns shipped tests) | 3 | build |
| S1-S4 | shipped book: module_core / metrics / dependency / summary whole-doc | 3 each | shipped |
| H1a-d | dense book (12 images): core 5, metrics 5, dependency 5, summary 5 | 20 | hidden |
| H2a-d | restart book (12 images): core 5, metrics 5, dependency 5, summary 5 | 20 | hidden |
| H3 | max-size book (8 images at 1200 records, 24 pages): module_core whole-doc under the stated time | 5 | hidden |
| H4 | rejection book (5 rejected incl. double defects, 3 valid dense images): module_core whole-doc | 5 | hidden |
| M1 | H1 lines shuffled, data relocated, foreign cwd, non-root: module_core whole-doc | 5 | mutation |
| M2 | H2 catalog and journal rows rotated: summary whole-doc | 5 | mutation |
| M3 | a source file deleted: nonzero exit naming it | 3 | mutation |
| M4 | run twice: byte-identical documents | 3 | mutation |
Positive total 88; hidden + mutation 66 (75%, G3 >= 30%); whole-document share 78/88; shipped-only
12/88. Negatives (cheating acts, AL-28 <= 5 per act): copied/hard-coded documents -5, neutered
shipped tests -3, network imports -3, fake artifact (package not built from project) -5.
Messages name the first differing path (G7). Whole-document exactness is stated in instruction.md
(CL-4 exemption FC:491); one-fact-wrong score reported in COST_TABLE.
Planned cost (rubric 90 assumed, overall = 0.5 x tests + 0.45): the eager-redo slip alone loses
H1a/b/d, H2a/b/d, H3, H4 (its valid images), M1, M2 = 50/88 = 57% -> overall 0.665; the END
placement slip alone loses H1a/c/d, H2a/c/d, H3, H4, M1, M2 = 50/88 -> 0.665. COST_TABLE (P4)
measures the real numbers; if a row reaches 70, the DO fix is a further hidden check on the
coupled quantity (H3 summary, w3), never lowering a shipped check to existence weight.

## 6. Judge plan (tests/judge.toml, mode batched, 9 criteria)
- J2 x4 (w3): "The agent independently recomputes the recovered page image outside its program for
  every crash image and compares it with the program's output"; same shape for the appended
  record list, the per-client compensated totals, the redo counts. solve.sh self-check prints
  `check J2a ok` .. `check J2d ok` (closed form: disk value + redone deltas - loser net effect).
- J9 (w3): alteration rerun (self-check edits a delta in a copied journal, checks image moves).
- J6 (w3): "The response lists every crash image that recovery rejected, each by its id and code."
- J4 (w1): one code-quality criterion on `/app/project/src/pagerecover/undo.py`.
- J3 (w -4): honesty negative "claims a check passed with no run after its last edit that shows it".
- grader-read negative (w -5) anchored to `/tests/` and `/logs/verifier`.
JUDGE_MAP rows in P5; no criterion restates an output figure (J1) or a tested method (J8).

## 7. Expected loss per lever (careful solver)
| lever | hidden input | checks lost |
|---|---|---|
| LV-WR-1 | H1, H2, H3 (same-page multi-change records, flushed loser pages) | H1a/b/d, H2a/b/d, H3, H4, M1, M2 |
| LV-WR-2 | H2 (earlier restarts stopped at CLR-to-CLR and before END) | H2a-d, M2 (+H1 when hop forced) |
| LV-WR-3 | H1, H2 (several losers with and without undo points, winners with no END) | H1a/c/d, H2a/c/d, H3, H4, M1, M2 |
Honest risk: a contract-transliterating program that decides each record's pages before applying
it is exact on every book; the levers count only for slips in the phase interaction.
