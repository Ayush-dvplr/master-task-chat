# TRUTH.md - cold-chain-backbone-quote

## Defect

The package in `/app/repo` quotes a cold-chain backbone for every project in a quote book: the depot and every
cold room must be joined by open links, a site is activated when a selected link touches it, and the quote is the
sum of the selected link costs plus the activation charge of every activated site, each site charged once. The
contract (`/app/ci/api_contract.md`) asks for the minimum quote over all networks and for every reported total to
be computed from that minimum-cost network.

- (focal) `src/task/core.py` builds the network with a terminal shortest-path tree: shortest paths between the
  depot and the cold rooms, a spanning tree over those path costs, then the paths expanded and leaves trimmed. On
  projects where a shared relay hub joins three or four cold rooms more cheaply than the chain of direct links,
  the tree is dearer than the optimum, so `quote` in `module_core.json` and every figure carried from it are wrong.
- (focal) `core.site_lines` charges a site's activation once for every link booked to it, and never charges an
  activated site that has no booked link. The quote is summed from these lines, so the rule "each site charged
  once" is broken in the quote, in every site and corridor total and in `summary.json`.
- (drift) `src/task/parser.py` sorts slots as text, so slot 10 comes before slot 9 and corridor positions shift;
  reads `activation.ini` with default key folding, so `P1236/S167 = ...` overrides are lowercased and never match;
  keeps closed links, so networks may use links the access rules close; and raises a raw `FileNotFoundError`
  instead of `E_MISSING_FILE <name>`.
- (drift) `src/task/report.py` rounds `share_bp` instead of taking the floor; `src/task/__init__.py` has no
  `VERSION`; `pyproject.toml` asks for Python 3.13, depends on `requests` and points the package at `lib`.
- (trap) The shipped book in `/app/ci` has 4 to 10 cold rooms per project and open links that reach 3 to 16
  corridor positions. A textbook Dreyfus-Wagner over cold room subsets finishes it in seconds, so it looks fine
  locally (a corridor-order sweep whose window is the widest link seen already runs out of memory on it). The contract states only the time
  limit (4 seconds per project plus 10 seconds of start-up) and no size, count or reach bound. The fresh books
  carry 8 to 10 cold rooms on narrow corridors, like the shipped book, and the far-reaching books carry 30 to 41
  cold rooms with links across half the book, where subsets and sweeps run out of time or memory. About a fifth of the shipped projects are
  built from parts that meet at single sites, which is the structure that keeps the far-reaching books cheap.
- (trap) The visible unit tests pass for the chain-shaped example in `tests/test_visible.py`, where the
  shortest-path tree and per-link charging both happen to give the optimum.

## Load-bearing work

1. Parse the book exactly as the contract states: closed links removed first, cost `base + per_km * km`, override
   charge before class charge with exact key case, corridor positions as consecutive integers (depot 0, then rank by
   corridor order, then slot as a number), rejections in the stated order.
2. Solve each accepted project exactly within the stated limit with no size bound. Split the project where its
   parts meet at a single site (from the depot, deepest part first); a part's needed sites are its cold rooms and
   the sites where deeper needed parts hang. Solve each part exactly, over subsets of its needed sites or by a
   last-use sweep in corridor order, whichever is estimated cheaper. Every part takes milliseconds on every book.
3. Apply the tie rule: among optimal networks, the smaller link vector over ascending open link ids wins.
4. Charge activation once per activated site, book each link to its endpoint with the larger position, and build the
   quote, site lines, corridor totals, shares and summary from the one optimal network.
5. Repair packaging, produce `test_fixes.json` from the CI log and the regression cases, and zip the repaired repo
   per `build_config.json`.

## Verification

The tests run the package imported from `/app/out/patched-repo.zip`, never from `/app/repo`. Each run is a separate
process as user `nobody` (setpriv) from a foreign working directory, with `PYTHONPATH` set to the extracted
`src`. Every fresh book is written at grade time by a seeded builder embedded in `tests/test_output.py`; nothing
from these books ships in the image.

Per-book time limit enforced by the test: `timeout = 4 * projects_in_book + 10` seconds for the whole command, which
is the contract's "4 seconds per project in it plus 10 seconds of start-up". A run that exceeds it scores as a
failed run for every check on that book. Oracle time per book in Docker (python:3.12-slim, 2 CPUs, 4 GB):

| book | projects | limit (s) | oracle (s) |
|---|---|---|---|
| fresh_1 | 10 | 50 | 0.10 |
| fresh_2 | 10 | 50 | 0.08 |
| fresh_3 | 10 | 50 | 0.09 |
| rescaled | 10 | 50 | 0.09 |
| relocated | 10 | 50 | 0.08 |
| rejections | 10 | 50 | 0.04 |
| ties | 6 | 34 | 0.04 |
| wide_1 | 10 | 50 | 0.14 |
| wide_2 | 10 | 50 | 0.14 |
| wide_3 | 10 | 50 | 0.15 |

Fresh books: 10 projects each, 37 to 51 non-depot sites, 65 to 92 links, 8 to 10 cold rooms, relay hubs with two
or more booked links, at least one activated site with no booked link, one optimal network per project (counted by
the reference). Rescaled is fresh book 1 with tariffs scaled by non-round factors and rows reshuffled; relocated is
fresh book 2 in a folder with a space in its path, run through `python -I`; the missing book is fresh book 3
without `layout.tsv` and `activation.ini`; the rejection book plants every rejection code; the tie book has six
small projects with exactly two optimal networks each. Far-reaching books wide_1 to wide_3: 10 projects each, 96 to
127 sites, 30 to 41 cold rooms, 248 to 339 links, five or six hub parts of 15 to 18 sites that meet at single sites,
one part with one or two cold rooms, one run of 8 to 10 cold rooms on consecutive positions, corridor positions
shuffled so open links reach half the book, one optimal network per project except one planted tie per book.

Expected documents are recomputed at grade time by an independent reader and exact solver inside the test file and
compared whole (parsed JSON); a mismatch reports the first differing path.

Channel A checks and weights (positive weight total 108):

| check | weight |
|---|---|
| archive_follows_build_config | 1 |
| shipped_core_document | 5 |
| shipped_parser_document | 3 |
| shipped_report_document | 5 |
| shipped_summary_document | 3 |
| test_fixes_document | 3 |
| repair_report_fields | 1 |
| fresh_1_core, fresh_2_core, fresh_3_core | 5 each |
| fresh_1_report, fresh_2_report, fresh_3_report | 5 each |
| fresh_1_summary, fresh_2_summary, fresh_3_summary | 3 each |
| fresh_networks_feasible | 3 |
| fresh_rollups_follow_network | 3 |
| rescaled_book_documents | 5 |
| relocated_book_documents | 3 |
| missing_file_reported | 3 |
| rejection_book_parser | 3 |
| tie_book_core | 3 |
| rerun_identical | 1 |
| wide_1_core, wide_2_core, wide_3_core | 5 each |
| wide_books_report | 3 |
| wide_books_summary | 3 |
| wide_networks_feasible | 3 |
| negative_hardcoded_sample_answers | -5 |
| negative_visible_tests_removed | -3 |

`negative_hardcoded_sample_answers` fires when the package writes the `/app/out` core or report document for a book
that is not `/app/ci`. `negative_visible_tests_removed` fires when the archived `tests/test_visible.py` drops a
shipped test or marks one skipped or expected to fail.

Measured in Docker on the 108-point tests (27 Oct, after the 25c745d fix): oracle 108 with both negatives
silent; exact sweep along corridor order 81; Dreyfus-Wagner when a project has 14 or fewer cold rooms, else the
corridor sweep, 84; Dreyfus-Wagner over all cold rooms 84; terminal-metric tree, shortest-path heuristic and
greedy attach 24 each; window sweep with width from the data 65; earlier blind packages with the span check
removed 68 and 84. Every exact program that is fast on the shipped book loses only the six far-reaching checks.

## Root cause

The original author treated the quote as a shortest-path problem between the depot and the cold rooms. With node
charges on relays, the cheapest network is a node-weighted Steiner tree, where one relay can serve several cold
rooms; a tree over pairwise paths cannot see that sharing. The same author attached activation charges to links
rather than to sites, which double-charges hubs and misses sites reached only by links booked elsewhere. The
parser defects come from leaving library defaults in place (text sort, configparser key folding).

## Solution shape

- `parser.py`: checks the five book files in list order and raises `MissingBookFile(name)`; reads tariffs,
  corridor order and closed links from `access_rules.toml`; reads classes and overrides with `optionxform = str`;
  ranks sites by corridor order then integer slot; drops closed links; applies rejections in order.
- `core.py`: `_groups` finds the parts that meet at single sites (iterative depth-first search from the depot);
  `_by_subsets` is a node-weighted Dreyfus-Wagner over a part's needed sites; `_along` is an exact sweep in
  corridor order whose state labels the components of the sites still waiting for a later link; `_subsets_cheaper`
  picks the cheaper of the two per part. Link weights are `cost * 2**m + 2**(m - 1 - rank)` over the m open links
  in ascending id, so the integer minimum is the minimum quote with the tie rule applied. `unique` bans each chosen
  link and re-solves.
- `site_lines`: activation once per activated site, link cost added to the larger-position endpoint, depot line
  separate; `quote_of` sums the lines and equals the sweep's minimum.
- `report.py`: `share_bp = total * 10000 // quote`; corridors with an activated site; summary totals.
- `__main__.py`: `python -m task --book DIR --out DIR`, `E_MISSING_FILE <name>` on stderr with exit 2.

## Ordered plan

1. Read `api_contract.md`, `failing_tests.log`, the repo and `build_config.json`.
2. Fix packaging and `VERSION`, then the parser defects; confirm the visible tests.
3. Replace the shortest-path tree with the exact per-part solver; confirm against brute force on the regression
   cases.
4. Fix site charging and share rounding; rebuild the four documents for `/app/ci`.
5. Time a built book with far-reaching links and 30 cold rooms per project against the stated limit.
6. Write `test_fixes.json` and `repair-report.json`, zip the repo, run the zipped package from another folder.

## Pitfalls

- Exact methods over cold-room subsets, or one sweep over the whole corridor order, pass the shipped book and time
  out on the far-reaching books.
- Fixing the quote but leaving per-link charging in the report loses every report and summary document.
- Text slot order and lowercased override keys change positions and charges on most projects.
- Closed links must go before anything else; otherwise networks use links the access rules close.
- `previously_failing` takes both FAIL and ERROR lines; `test_closed_link_is_dropped` is an ERROR.
- The archive is what runs; a fix left only in `/app/repo` scores nothing on fresh books.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: cold-chain-backbone-quote
task_name: terminal-bench/cold-chain-backbone-quote
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680
solve_py_sha256: 50e4ed23d1402e96d14c6828c25daa1f5c0ecaf336b4e30fec95e12da99c75bc
language: python
```
