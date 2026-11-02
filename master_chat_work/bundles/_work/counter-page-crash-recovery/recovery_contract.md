# Recovery contract for pagerecover

This contract defines the inputs, the restart recovery protocol, the four
recovery documents and the build deliverables of the `pagerecover` package.
Where the package source, its README, its tests or a comment disagree with
this contract, this contract decides.

Every reported figure of a crash image is computed from its recovered page
image and the recovery that produced it.

## 1. Book and crash images

A book is one directory holding six recovery inputs: `journal.jsonl`,
`disk_pages.bin`, `page_map.ini`, `checkpoint.toml`, `txn_catalog.csv` and
`audit_queries.json`. A book holds one or more crash images; the images of a
book are the sections of `page_map.ini`. Each image is an independent
database of counter pages: its own pages, its own journal, its own disk state
and its own master record.

Limits: an image has at most 1200 journal records and at most 24 pages, and
every page has between 4 and 8 slots. A book has at most 40 images.

## 2. Input files

`page_map.ini` has one section per image, named by the image id. Each line
of a section is `<page id> = <slot count>`. Page ids are case sensitive.
Line order carries no meaning.

`journal.jsonl` holds one JSON object per line. Every object has `image` (the
image id), `lsn` (an integer, the record's log sequence number) and `type`.
Line order carries no meaning: the log order of an image is ascending `lsn`.
The record types are:

- `begin`, `commit`, `abort`, `end`: transaction records with `txn` (an
  integer transaction id) and `prev` (the lsn of the transaction's previous
  record, or null).
- `update`: a transaction record that also has `changes`, a list of objects
  `{"page", "slot", "delta"}`. Each change adds the integer `delta` to slot
  number `slot` (counted from 0) of page `page`.
- `clr`: a compensation record. It has `txn`, `prev`, `changes` as for an
  update, and `undo_next` (an lsn or null).
- `checkpoint_begin`: no further fields.
- `checkpoint_end`: `begin_lsn` (the lsn of its `checkpoint_begin`),
  `txn_table` (a list of `{"txn", "state", "last_lsn"}` with state `running`,
  `committed` or `aborting`) and `dirty_pages` (a list of
  `{"page", "rec_lsn"}`).

`disk_pages.bin` is the 4 bytes `CPG1` followed by frames, one frame per page
of every image, in no meaningful order. All integers are big endian. A frame
is: a 16 bit unsigned length and that many ASCII bytes of image id; a 16 bit
unsigned length and that many ASCII bytes of page id; the page's pageLSN as a
64 bit unsigned integer; the slot count as a 16 bit unsigned integer; that
many slot values, each a 64 bit signed two's complement integer; and a 32 bit
unsigned CRC-32 (as computed by `zlib.crc32`) of every preceding byte of the
frame.

`checkpoint.toml` has a table `[images.<image id>]` per image with the
integer `master_lsn`: the lsn of the `checkpoint_begin` of the image's master
checkpoint, whose `checkpoint_end` is in the journal. A `master_lsn` of 0
means the image has no master checkpoint.

`txn_catalog.csv` has the header `image,txn,client` and one row per
transaction of every image, naming the client that owns it.

`audit_queries.json` is `{"queries": [...]}`; each query has `id`, `image`,
`pages` (a list of page ids of that image) and `slot` (a slot number or the
string `"all"`).

## 3. Validation

Before recovery an image is checked in this order; the first failing check
rejects the image with its error code, and a rejected image is not
recovered.

1. `E_BAD_IMAGE`: the image's frames do not hold exactly one frame for each
   page of its page map section, a frame's CRC-32 does not match, or a
   frame's slot count differs from the page map.
2. `E_UNKNOWN_PAGE`: a change of an update or CLR names a page outside the
   image's page map section, or a slot number outside 0 to slot count - 1.
3. `E_DUP_LSN`: two records of the image have the same lsn.
4. `E_BAD_CHAIN`: a `begin` whose `prev` is not null, another transaction
   record whose `prev` is null, or a `prev` or non-null `undo_next` that does
   not name a record of the same transaction with a smaller lsn.

## 4. Recovery protocol

Recovery of an image starts from its disk state: every page with the pageLSN
and slot values of its frame.

### 4.1 Analysis

When `master_lsn` is 0, the transaction table and the dirty page table start
empty. Otherwise they start as the `txn_table` and `dirty_pages` of the
`checkpoint_end` whose `begin_lsn` equals `master_lsn`: each transaction with
its state and last LSN, each page with its recLSN.

Analysis then reads, in log order, every transaction record whose lsn is at
least `master_lsn`; checkpoint records are skipped. An `end` removes its
transaction from the transaction table. Any other record adds its transaction
with state `running` when it is absent, and sets the transaction's last LSN
to the record's lsn; a `commit` sets the state to `committed` and an `abort`
sets it to `aborting`. Every page named by a change of an update or CLR that
is not yet in the dirty page table is added with recLSN equal to the record's
lsn.

After analysis, the winners are the transactions in the table with state
`committed`, and the losers are the other transactions in the table.

### 4.2 Redo

Redo starts at the smallest recLSN in the dirty page table after analysis.
When that table is empty, nothing is redone and the redo start is null.

Redo reads every update and CLR from the redo start LSN in log order. For
each record, the pages it redoes are decided before any of its changes is
applied: a page is redone when it is in the dirty page table, the record's
lsn is at least that page's recLSN, and the record's lsn is greater than that
page's pageLSN. Every change of the record on a redone page is applied (slot
value plus delta) and that page's pageLSN becomes the record's lsn.

### 4.3 Appended records and undo

Recovery appends records to the image's log. Each appended record takes the
next LSN; the first one takes the image's largest journal lsn plus 1.

First an `end` for every winner in ascending transaction id. Then an `end`
for every loser that has no undo point, in ascending transaction id. Then the
undo steps, until no loser is left.

A loser's undo point is found from its last LSN: an update record is the
undo point; a CLR moves to the record named by its `undo_next`; any other
record moves to its `prev`; a null pointer means the loser has no undo point.

Each undo step takes the loser whose undo point has the largest LSN, appends
one CLR for that update, and, when the loser then has no undo point, appends
its `end` at once. The CLR has the loser's `txn`; `prev` is the loser's last
LSN; `changes` are the undone update's changes in their order with every
delta negated; `undo_next` is the undone update's `prev`. Appending the CLR
adds each of its deltas to its slot, sets the pageLSN of every page it names
to the CLR's lsn, and makes the CLR the loser's last LSN; the loser's undo
point is then found again from there.

An appended `end` is `{"lsn", "type", "txn", "prev"}` with `prev` the
transaction's last LSN. An appended CLR is
`{"lsn", "type", "txn", "prev", "changes", "undo_next"}`.

The recovered page image of an image is every page's pageLSN and slot values
after the last appended record.

## 5. Recovery documents

`python -m pagerecover recover --data DIR --out OUT` reads the six inputs of
the book in `DIR` and writes the four documents below into `OUT`, creating it
when absent. It runs with the package's `src` directory on the import path,
from any working directory, with the standard library only. When one of the
six inputs is missing, it writes no document, names the missing file on
standard error and exits with a nonzero status.

Each document is a JSON object `{"images": {<image id>: <entry>}}` with an
entry for every image of the book. Object key order and whitespace carry no
meaning; list order does. The entry of a rejected image in all four documents
is `{"status": "rejected", "error": <code>}`. The entry of a recovered image
has `"status": "recovered"` and these keys:

- `module_core.json`: `pages`, an object mapping every page id of the image
  to `{"page_lsn", "slots"}` of the recovered page image.
- `module_metrics.json`: `winners` and `losers` (counts); `redo_start_lsn`
  (the redo start, or null); `redo_records` (the updates and CLRs redo read);
  `redo_changes_applied` (the changes redo applied); `clrs_appended` and
  `ends_appended` (counts of appended records by type); `next_lsn` (the LSN
  the next appended record would take).
- `dependency_resolution.json`: `losers` (the loser ids in ascending order)
  and `appended` (every appended record in the order appended).
- `summary.json`: `image_sha256`, the lowercase hex SHA-256 of the UTF-8
  bytes of the `pages` object of `module_core.json` serialized with keys
  sorted and no whitespace (Python `json.dumps(pages, sort_keys=True,
  separators=(",", ":"))`); `clients`, an object with an entry
  `{"winners", "losers", "compensated"}` for every client owning a winner or
  a loser of the image, where `compensated` is the sum of the absolute deltas
  of the changes of the CLRs appended for that client's losers; and `audits`,
  an object mapping the id of every query on the image to the sum, over the
  query's pages, of the recovered value of slot `slot`, or of all slots of
  the page when `slot` is `"all"`.

A book at the stated limits is recovered within 60 seconds. The package
computes every document from the book in `DIR`; it holds no figure or image
id of any book. It leaves the files in `DIR` unchanged, and a second run on
the same book writes the same four documents.

## 6. Build deliverables

`/app/out/package.zip` holds the repaired project with `pyproject.toml` at
the archive root, every member listed as `archive_members` in
`expected_targets.json` and no other member except added `.py` files under
`src/pagerecover/`, using the compression and member timestamp of
`compiler_flags.json`. Its `pyproject.toml` names project `pagerecover`
with the `required_version` of `dependency_manifest.json`, requires Python
`>=3.12`, has no runtime dependencies and maps the package directory to
`src`; `pagerecover.__version__` is the same version. The archive's
`tests/test_smoke.py` keeps every test of the shipped one, none of them
skipped.

`/app/out/module_core.json`, `/app/out/module_metrics.json`,
`/app/out/dependency_resolution.json` and `/app/out/summary.json` are the
documents of the book in `/app/data`, written by the archived package.

`/app/out/selftest.json` has `ok` (true only when every other value below
was obtained and every test passed), `package`, `version`, `archive`
(`/app/out/package.zip`), `tests_run` and `tests_passed` (the unittest
counts of the archive's tests), `ci_commands` (the commands of
`ci_config.yaml` in order, without their YAML quoting), `reports` (the four
document paths in the order above), and `images_total`, `images_recovered`
and `images_rejected` for the book in `/app/data`.

`/app/out/build_report.json` has `ok`, `package`, `version`, `layout`
(`src`), `python` (`3.12`), `fixed_modules` (the sorted file names under
`src/pagerecover/` that the repair changed or created) and `fix_categories`
(a sorted, non-empty list drawn from `packaging`, `dependency`, `decoding`,
`config`, `validation`, `recovery`, `reporting`, `cli`).
