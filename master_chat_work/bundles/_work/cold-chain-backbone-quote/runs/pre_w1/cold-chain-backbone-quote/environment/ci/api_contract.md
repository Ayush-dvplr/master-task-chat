# Quote book contract

The package `task` imports from `src/` and quotes the cold-chain backbone of
every project in a quote book. `task.VERSION` and the `version` in
`pyproject.toml` both equal the `version` in `/app/ci/package_manifest.json`.
The package uses the Python 3.12 standard library only and installs nothing.

## Command

    PYTHONPATH=<repository>/src python3 -m task --book <book dir> --out <out dir>

The command reads the five book files from `--book`, writes `module_core.json`,
`module_parser.json`, `module_report.json` and `summary.json` into `--out`
(creating it when absent) and exits with status 0. It reads nothing else,
writes nowhere else, leaves the book directory as it found it, and gives the
same documents whatever the working directory, whichever user runs it, and
when the repository files are read-only.

If one of the five book files is absent, the command writes
`E_MISSING_FILE <name>` to standard error, with `<name>` the missing file's
name (the first missing one in the order of the list below), writes no
document and exits with a non-zero status.

The directory `/app/ci` is a quote book: the current one. The command is also
run on other books in the same format.

## Book files

- `sites.csv`: header `project,site,role,class`. One row per site. `role` is
  `depot`, `cold_room` or `relay`. Every project has exactly one depot.
- `layout.tsv`: tab separated, header `project	site	corridor	slot`. One row
  per site other than the depot. `slot` is a whole number.
- `links.jsonl`: one JSON object per line with keys `project`, `link`, `a`,
  `b`, `band` and `km` (`km` is a whole number). `a` and `b` are the site ids
  of the two ends; a link has no direction. Link ids are unique in a book.
- `access_rules.toml`: `[corridors] order` lists the corridor names in corridor
  order. Each `[tariff.<band>]` table holds whole numbers `base` and `per_km`.
  `[closed] links` lists link ids that are closed.
- `activation.ini`: `[classes]` maps a site class to its activation charge.
  `[overrides]` maps `<project>/<site>` to an activation charge that replaces
  the class charge of that one site. Keys are matched with their exact spelling
  and case.

Project ids, site ids and link ids are compared as strings. All costs and
charges are positive whole numbers.

## Corridor positions

A site's corridor position is one consecutive whole number. The depot of a
project is at position 0. The other sites of the project take positions 1, 2,
3 and onwards, ranked first by the place of their corridor in `[corridors]
order` and then by their slot, with slots compared as numbers. No two sites of
one project share a corridor and a slot in any book; books are built that way.

## Links and charges

A closed link is removed from the book before any other rule here is applied.
Every other link is open. The cost of an open link is `base + per_km * km` of
its band. A site's activation charge is its override when one exists and its
class charge otherwise.

## Rejections

A project is rejected with the first of these codes that applies, checked in
this order:

1. `E_DUP_SITE`: one site id is on two rows of `sites.csv` for the project.
2. `E_UNKNOWN_ENDPOINT`: an open link of the project has an end that is not a
   site of the project.
3. `E_BAD_SPAN`: an open link between two sites other than the depot joins
   positions more than 4 apart. Links with the depot at one end have no span
   limit.
4. `E_NO_NETWORK`: some cold room cannot be reached from the depot over open
   links.

Every other project is accepted.

## Networks and the quote

A network of an accepted project is a set of its open links in which the
depot and every cold room are joined to each other. A network activates the
depot, every cold room and every site at an end of one of its links. The quote
of a network is the sum of the costs of its links plus the activation charge
of every site it activates, each site charged once however many of the
network's links touch it.

The quote of a project is the smallest quote of any of its networks, and its
minimum-cost network is a network with that quote. When two or more networks
share the smallest quote, write each one as a vector over the project's open
links in ascending link id order, with 1 for a link in the network and 0 for
a link outside it; the minimum-cost network is the one whose vector is smaller
at the first position where the vectors differ.

Limits: every accepted project in any book has at most 52 sites including the
depot, at most 95 links and at most 17 cold rooms, and the command must finish
a book within 4 seconds per project in it plus 10 seconds of start-up.

## Charging lines

Each link of the minimum-cost network is booked to its end with the larger
corridor position. Every activated site has one line. A site's line total is
its activation charge plus the costs of the links booked to it; the depot's
line total is its activation charge. A corridor's total is the sum of the line
totals of its activated sites. The `share_bp` of a line or corridor is its
total times 10000 divided by the project's quote, rounded down to a whole
number.

Every reported total of a project is computed from its minimum-cost network.

## Documents

Each document under `/app/out` is one JSON object; key order and whitespace
are free. Lists are in ascending order. Numbers are whole numbers. Objects
keyed by project, site or corridor hold one entry per accepted project,
activated site or corridor with an activated site, and no others.

- `module_core.json`: `{"projects": {<project>: {"quote": int, "links": [link
  ids of the minimum-cost network], "sites": [ids of the sites it
  activates]}}}`.
- `module_parser.json`: `{"accepted": [project ids], "rejected": {<project>:
  code}, "projects": {<project>: {"sites": int, "links": int, "open_links":
  int, "cold_rooms": int, "relays": int}}}`. `sites` counts the depot, `links`
  counts the project's rows in `links.jsonl` and `open_links` the open ones.
- `module_report.json`: `{"projects": {<project>: {"depot": {"total": int,
  "share_bp": int}, "corridors": {<corridor>: {"total": int, "share_bp":
  int}}, "sites": {<site>: {"corridor": name, "total": int, "share_bp":
  int}}}}}`. `sites` holds the activated sites other than the depot.
- `summary.json`: `{"book_total": int, "projects_quoted": int,
  "projects_rejected": int, "depot_total": int, "corridor_totals":
  {<corridor>: int}}`. `book_total` is the sum of the project quotes,
  `depot_total` the sum of the depot line totals, and each corridor total the
  sum of that corridor's totals over the projects.

The four documents above, written to `/app/out`, are those of the book in
`/app/ci`. Two more documents go there:

- `test_fixes.json`: `{"previously_failing": [names], "regression_quotes":
  {<case>: int or code}}`. `previously_failing` holds the name of every test
  method whose result line in `/app/ci/failing_tests.log`
  (`<name> (<module>.<class>.<name>) ... <result>`) ends in `FAIL` or `ERROR`,
  each name once. `regression_quotes` holds, for every case in
  `/app/ci/regression_cases.jsonl`, the quote of the repaired package for that
  case, or its rejection code when the case is rejected.
- `repair-report.json`: `{"defects": [{"file": path in the repository,
  "summary": text}], "checks": [text]}` with at least one entry in each list:
  what was wrong and fixed, and what was run to check the repair.

## Regression cases

Each line of `regression_cases.jsonl` is one project written out in full:
`{"case": id, "sites": [{"site", "role", "charge", "position"}], "links":
[{"link", "a", "b", "cost"}]}`. Positions, charges and costs are given
directly and every link is open; the rejection rules, the network, the quote
and the tie rule are the same as for a book project.

## Archive

`/app/out/patched-repo.zip` holds the repaired repository with its files at
the archive root (`pyproject.toml`, `src/task/...`, `tests/...`). It follows
`/app/ci/build_config.json`: members sorted by name, no directory entries, no
`__pycache__` or `.pyc` member, every member's timestamp equal to
`archive.timestamp`, compressed with `archive.compression`, and with unix
permission bits equal to `archive.mode`. The archive is what is imported and
run.
