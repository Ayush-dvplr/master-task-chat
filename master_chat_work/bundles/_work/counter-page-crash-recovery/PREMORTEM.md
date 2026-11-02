# PREMORTEM counter-page-crash-recovery (board 54e38ee)

Prototype: `WORK/proto/gen.py` (book generator: buffer pool, WAL, fuzzy checkpoints, savepoint
rollbacks, aborts in progress, multi-change records, earlier restarts interrupted during undo),
`WORK/proto/rec.py` (contract reading plus switchable wrong readings), `t1.py` (reference vs
forward truth), `t2.py` (baselines per book), `t3.py` (textbook program per book, timing).
t1: 120 images, reference image == genesis + committed net effect on all 120.

## 1. Reading order (first 10 minutes)
1. `instruction.md`: repair the zipped package, ship `/app/out/package.zip` and six JSON files,
   whole-document exactness, contract at `/app/data/recovery_contract.md`.
2. `recovery_contract.md` top to bottom (record format, disk image layout, analysis, redo, undo,
   appended-record sequence, rejection codes and precedence, output schemas, limits, coupling).
3. `unzip project.zip`; reads `src/pagerecover/*.py`, `pyproject.toml`, `tests/`. Runs the shipped
   tests: they pass on the tiny fixtures (one winner, one loser, no flush of loser pages).
4. Peeks at `journal.jsonl` (head), `page_map.ini`, `checkpoint.toml`, `xxd disk_pages.bin | head`,
   `txn_catalog.csv`, `audit_queries.json`, then the build fixtures.

## 2. The program it writes once
It keeps the package layout, fixes the import and packaging defects, and replaces the shipped
commit-filter replay with textbook ARIES:
- analysis from the master record's checkpoint: transaction table and dirty page table from the
  matching `ckpt_end`, forward scan from the checkpoint begin LSN; END drops a transaction;
- redo from the smallest recLSN; for each change of an update or CLR:
  `if page in dpt and lsn >= rec_lsn and lsn > page.lsn: page.slots[s] += d; page.lsn = lsn`;
- undo with the textbook ToUndo set: take the largest of every loser's current LSN; update ->
  write CLR, follow prev; CLR -> follow undo_next; begin record -> write END;
- committed ENDs in transaction-table order.
This is `TB_textbook` = `{textbook_end, eager_pagelsn}` in `proto/t3.py`.

## 3. Self-tests it runs
- Shipped unit tests and its own tiny examples (two transactions, one flush, one CLR): pass for
  the reference and for TB_textbook alike; tiny examples hold no record touching one page twice
  and no loser whose chain an earlier restart compensated.
- Shipped book: runs clean, no rejection surprises, every loser update compensated exactly once
  (counts CLRs per undone LSN), every pageLSN below next_lsn, ENDs present for every winner.
  All of these invariants hold for TB_textbook as well, because the slips leave a consistent,
  plausible image. No answer for any shipped image exists in `environment/` (W11).

## 4. Reading of every rule (rule in contract -> its reading)
| rule | TB reading | reference |
|---|---|---|
| analysis start = master record's checkpoint begin | same | same |
| redo start = smallest recLSN after analysis | same | same |
| redo decision per page, against the page's pageLSN before the record | per change, pageLSN updated after each change (eager) | decided for all pages of the record first |
| undo order: one global sequence, largest undo point first, ties by txn id | ToUndo max (same order of CLRs) | same |
| ENDs: committed first ascending id, then losers with no undo point ascending id, a loser's END right after its last CLR | END when chain reaches begin; committed in table order | as stated |
| every appended record takes the next LSN | same | same |
| CLR inverts every change of the undone update, undo_next = its prev | same | same |

## 5. Per lever: where TB goes wrong, why its self-tests miss it
Losses per hidden book (whole documents c=module_core, m=module_metrics, d=dependency_resolution,
s=summary; from `t3.py`, 12-image books dense 11-13, restart 21-23, max 31, shipped 5):
| book | TB_textbook | TB_end_only | TB_eager_only | TB_one_hop |
|---|---|---|---|---|
| dense 11/12/13 | cmds/cmds/cmds | cds x3 | cms x3 | cmds x3 |
| restart 21/22/23 | cmds x3 | cds x3 | cms x3 | cmds/-/cmds |
| max 31 | cmds | cds | cms | cmds |
| shipped 5 | cmds | cds | cms | - |

- LV-WR-1 (exact image): eager pageLSN skips the second change of a record that touches one page
  twice (redo of updates and of CLRs). Leaves a plausible value; no conservation law ties slot
  values together, and the invariants above do not read slot values. Other slips that lose every
  book: per-record decision on the first page (B15, cms 12/12), redo when lsn >= pageLSN (B3),
  commit-filter replay kept (B1, cmds 12/12), CLRs not redone (B2).
- LV-WR-2 (compensation chains): textbook ToUndo follows undo_next through CLR chains correctly, so
  the double-undo reading is not its reflex; redesigned so the earlier restart's chains feed the
  appended sequence: the hidden restart book stops earlier restarts right after a CLR whose
  undo_next names a CLR and right after a loser's last CLR before its END. TB then places that
  loser's END by the textbook rule and every later LSN shifts (pageLSN coupling). Hand-rolled walks
  lose too: prev walk through CLRs (B5, cmds 6-12 images per book), single hop (B12, cmds 1-5).
- LV-WR-3 (audit sequence): END placement and committed END order shift every later appended LSN,
  so CLR LSNs, pageLSNs and the image checksum move (cds on every book). Per-transaction undo (B4,
  cds 3-12 images) and redo from the checkpoint LSN (B6, cms 1-9) lose on every book. The shipped
  book cannot confirm the order: no appended record list ships, and both orders satisfy every
  invariant it can check.

## 6. Redesign decisions taken
- Multi-change records with a repeated page (p_same) and independent page flushes, so the
  per-page, pre-record redo decision matters on every book.
- Earlier restarts stopped at CLR-to-CLR points and between a loser's last CLR and its END.
- Hot-page flush bias keeps old pages dirty, so redo start (smallest recLSN) sits before the
  checkpoint and redo-from-checkpoint loses.
- Honest risk: a program that transliterates the contract sentence by sentence and decides the
  redo of each page before applying the record is exact on every book; an agent that writes an
  independent closed form (disk value + redone deltas - loser net) would catch the eager slip.
  The stated END rules count only if the agent keeps its textbook habit over an explicit sentence.
