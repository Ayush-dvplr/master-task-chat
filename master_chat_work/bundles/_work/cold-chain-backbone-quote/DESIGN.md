# DESIGN: cold-chain-backbone-quote (board 57a2dd7, repo-patch, optimization, seed 174241)

Package name `<pkg>` is the scaffold's `{{PACKAGE_NAME}}` (generator: `args.format_tag.lower()`), fixed in Phase 1. Input files live in `environment/ci` (mounted /app/ci) because the repo-patch archetype sets `datagen_input = "ci"`; the prompt's `environment/data` wording maps to this directory.

## 1. Spine (what the agent must do, in order)
1. Repair packaging (`pyproject.toml`: requires-python, stray `requests` dependency, wrong package dir) so the package imports from the zip with the standard library only.
2. Repair the parser (honest defects shown by failing_tests.log): slot order read as text, activation overrides ignored, closed links kept.
3. Replace the solver in `core.py`: the shipped terminal shortest-path MST heuristic must become an exact minimum-cost network solver that meets 4 s per project at 17 cold rooms (frontier DP over corridor order, window 4 plus depot).
4. Repair the charge helper `core.site_lines` (activation charged once per booked link) so activation is charged once per activated site; it feeds both the quote and the report.
5. Repair `report.py` (share rounding defect shown by the log) and the CLI `python -m <pkg> --book DIR --out DIR` writing module_core, module_parser, module_report, summary.
6. Run on /app/ci, write the seven outputs, zip /app/repo to /app/out/patched-repo.zip.

## 2. Input files (/app/ci), formats, rows, dependencies
| file | format | rows (target) | content | depends on |
|---|---|---|---|---|
| api_contract.md | md | ~150 | book layout, network rule, charge rule, booking rule, span bound, limits, tie order, CLI, output keys, error codes and their order, coupling sentence | none (governs all) |
| sites.csv | csv | >=2,600 | project, site, role (depot / cold_room / relay), class | activation.ini classes |
| layout.tsv | tsv | >=2,600 | project, site, corridor, slot (integers with gaps, many >= 10) | access_rules.toml corridor order; sites.csv |
| links.jsonl | jsonl | >=4,500 | project, link, a, b, band, km | sites.csv ids; access_rules.toml tariff and closed list |
| access_rules.toml | toml | ~80 | corridor order, tariff per band (base, per_km), closed links | none |
| activation.ini | ini | ~400 | class charges, per-site overrides `P1234/S017 = 9` | sites.csv |
| regression_cases.jsonl | jsonl | >=2,400 | tiny inline projects (sites with charge, position, links with cost), inputs only, no expected values | contract inline format |
| failing_tests.log | log | >=2,400 | unittest -v of the shipped CI (parser regression tests, visible unit tests), FAIL/ERROR lines and tracebacks without numeric answers | regression_cases ids |
| lint_report.json | json | ~650 issues | scaffold CI noise (module/line/code/severity/message) | repo files |
| package_manifest.json | json | small | scaffold: package name, version, modules | repo |
| build_config.json | json | small | scaffold: archive compression, timestamp, mode, sorted members for patched-repo.zip | used by zip step |
Formats: md, csv, tsv, jsonl, toml, ini, json, log (8). Total lines >= 20,000 (A5); every csv/tsv/jsonl/log >= 2,000.
Shipped book: ~80 projects, 18 to 52 sites, up to 95 links, 4 to 10 cold rooms, relay hubs present, 5 to 6 projects rejected (one per code plus one with two codes for the order rule). Every accepted project has exactly one optimum (counted by the reference DP; seeds redrawn otherwise).

### Chains (length >= 4)
1. access_rules.toml corridor order -> layout.tsv corridor + slot (integer order) -> corridor position -> span check (E_BAD_SPAN) and booking endpoint -> site total -> corridor total -> summary corridor_totals.
2. sites.csv class -> activation.ini class charge -> activation.ini override -> site charge -> quote -> share_bp in every report row.
3. links.jsonl band + km -> access_rules.toml tariff -> closed list -> link cost -> minimum-cost network -> booked link costs -> site and corridor totals.
4. failing_tests.log FAIL lines -> test names -> test_fixes.json previously_failing; regression_cases.jsonl -> patched package -> test_fixes.json regression_quotes.

## 3. Levers
### LV-CC-1 exact minimum-cost network (core)
- Rule (api_contract.md): "A project's network is a set of its open links. It must connect the depot and every cold room. A site is activated when a selected link touches it; the depot and every cold room are always activated. The quote of a network is the sum of its link costs plus the activation charge of every activated site. The package quotes each project at the minimum quote over all networks."
- Reflex reading: keep core.py's terminal shortest-path MST (expand paths, prune leaves) or greedy attach; add local search.
- Hidden cases: 3 relay hubs per project (hub relay charge 10 to 20, 3 to 4 cold rooms on cheap spokes, direct cold-room links priced so the terminal MST prefers them while the hub tree is cheaper), pair gadgets (two cheap bridged relays). Prototype: KMB wrong 14/14, greedy 14/14, local search 6/14 projects.
- Why visible data cannot confirm: no optimum anywhere in the image; repo samples are near trees; invariants (connected, cost recomputes) hold for dearer networks.
### LV-CC-2 runtime at the stated maximum
- Rule (api_contract.md, Limits): "A project has at most 52 sites, 95 links and 17 cold rooms. A link that does not touch the depot joins sites at most 4 corridor positions apart. The package quotes a book within 4 seconds per project, plus 10 seconds start-up, using the Python standard library only."
- Reflex reading: node-weighted Dreyfus-Wagner over cold-room subsets (exact). Measured: 10 cold rooms 0.11 s, 12: 0.88 s, 14: 7.25 s, 15: 24.5 s, 16: 77.1 s, 17: 203.8 s. Hidden projects carry 15 to 17 cold rooms; the book run times out.
- Why visible data cannot confirm: shipped book stops at 10 cold rooms (DW 0.1 s); brute-force harnesses use tiny projects.
- Exact in time: frontier DP over corridor order (partitions of depot plus last 4 positions), 0.01 to 0.02 s per hidden-size project.
### LV-CC-3 activation once per activated site, carried into every total
- Rule (api_contract.md, Charges and rollups): "Each activated site's activation charge is paid once, whatever the number of selected links touching it. Each selected link is booked to its endpoint with the larger corridor position (the depot has position 0). A site's total is its activation charge plus the costs of the links booked to it. The depot line is the depot's activation charge. A corridor total is the sum of the totals of its activated sites. Every reported total of a project is computed from its minimum-cost network."
- Reflex reading: keep shipped `core.site_lines`, which adds a site's activation once per link booked to it (equal on monotone chains, the visible samples; double on hubs with 2 to 4 booked links; zero for activated sites with no booked link). It feeds `core.quote` and `report.py`. Second reading: DW merge without `- a(v)`.
- Hidden cases: every hidden project has hubs with >= 2 booked links and >= 1 activated site booked no link.
### LV-T (secondary, stated-rule) tie order, <= 25% weight
- Rule: "When two networks share the minimum quote, the package keeps the one whose link vector, taken over link ids in ascending order with 1 for a selected link, is smaller in lexicographic order." Every shipped and H/M project has one optimum; book T (6 small projects with exactly 2 optima) triggers it (weight 3 of 84). OPEN QUESTION for master (see DESIGN_SUMMARY).
### Interactions
L2 gates L1 (a timed-out run has no networks). L3 is coupled into every quote-carrying document; an exact solver with the shipped helper still loses core (if the quote comes from `core.quote`) or report and summary (if only the report uses it).

## 4. Rejection paths (api_contract.md, checked in this order, first applies)
E_DUP_SITE (site id twice in a project), E_UNKNOWN_ENDPOINT (link endpoint not a site of the project), E_BAD_SPAN (non-depot link spans > 4 positions), E_NO_NETWORK (some cold room cannot reach the depot over open links). A rejected project appears in module_parser `rejected` with its code and nowhere else. Missing book file: non-zero exit, stderr names the file (`E_MISSING_FILE <name>`).

## 5. Outputs (whole-document exact, every key stated in the contract)
- module_core.json `{"projects": {pid: {"quote", "links" (ascending), "sites" (activated, ascending)}}}`
- module_parser.json `{"accepted": [...], "rejected": {pid: code}, "projects": {pid: {"sites","links","open_links","cold_rooms","relays"}}}`
- module_report.json `{"projects": {pid: {"depot", "corridors": {name: {"total","share_bp"}}, "sites": {sid: {"corridor","total","share_bp"}}}}}`, share_bp = total * 10000 // quote
- summary.json `{"book_total","projects_quoted","projects_rejected","corridor_totals": {name: int}}`
- test_fixes.json `{"previously_failing": [...], "regression_quotes": {case: quote or code}}`; repair-report.json (prose fields, existence/shape only).

## 6. Test plan (tests/test_output.py; seed only in tests/; hidden generator embedded; runs as uid nobody via setpriv from a foreign cwd, package imported from the extracted zip)
Hidden corpora: H1, H2, H3 (10 projects each, 16 to 17 cold rooms, 38 to 52 sites, 65 to 95 links, hubs, unique optimum, fresh ids, shuffled rows); M1 = H1 with rows shuffled and tariff per_km scaled by a non-round factor (content mutation); M2 = H2 relocated to a new dir name, run from another cwd; M3 = H3 with layout.tsv and activation.ini deleted (expects `E_MISSING_FILE layout.tsv`, the first missing in list order); R = rejection book (every code, one two-code project); T = tie book. Reference answers computed at grade time by the test's own DP; never shipped.
| id | check | w | levers | kind |
|---|---|---|---|---|
| C01 | patched zip layout imports | 1 | none | isolated |
| C02 | shipped module_core exact | 5 | L1 L3 | whole-doc |
| C03 | shipped module_parser exact | 3 | none | whole-doc |
| C04 | shipped module_report exact | 5 | L1 L3 | whole-doc |
| C05 | shipped summary exact | 3 | L1 L3 | whole-doc |
| C06 | test_fixes exact | 3 | none | whole-doc |
| C07 | repair-report fields | 1 | none | isolated |
| C08-C10 | H1/H2/H3 module_core exact | 5 each | L1 L2 L3 | whole-doc hidden |
| C11-C13 | H1/H2/H3 module_report exact | 5 each | L1 L2 L3 | whole-doc hidden |
| C14-C16 | H1/H2/H3 summary exact | 3 each | L1 L2 L3 | whole-doc hidden |
| C17 | hidden networks feasible (connected, terminals in, sites = endpoints) | 3 | L2 L3 | isolated hidden |
| C18 | hidden report follows own network under the stated rule | 3 | L2 L3 | isolated hidden |
| C19 | M1 four docs exact | 5 | L1 L2 L3 | G6 mutation |
| C20 | M2 four docs exact | 3 | L1 L2 L3 | G6 mutation |
| C21 | M3 non-zero exit naming layout.tsv | 3 | none | G6 mutation |
| C22 | R module_parser exact | 3 | none | hidden |
| C23 | T module_core exact | 3 | L1 L3 tie | hidden |
| C24 | rerun identical bytes and book folder unchanged | 1 | L2 | isolated |
| N1 | negative: hidden output equals shipped output (replay) | -5 | cheating | |
| N2 | negative: archive drops or skips a shipped visible test (tests/test_visible.py) | -3 | cheating | |
Positive total 84; hidden (C08-C23) 63 = 75%; shipped-only 21 = 25%; whole-doc 72 = 85.7%; isolated 12 = 14.3%; LV-T 3.6%. 24 positive checks, 2 negatives. Assertion messages name the first differing JSON path (G7). Verifier timeout 900 s (8 runs x at most 50 s plus reference).

## 7. Judge plan (tests/judge.toml, batched, 10 criteria)
R1 J2 w3 quote recompute per shipped project; R2 J2 w3 corridor totals recompute; R3 J2 w3 previously_failing recompute from the log; R4 w3 runs a book at 17 cold rooms and records time per project; R5 J9 w3 altered copy; R6 J4 w3 maintainable core.py; R7 J6 w1 lists every rejected shipped project by id; R8 w1 names the method core.py now uses; R9 J3 -5 claims a passing check with no later run; R10 -3 reads /tests/ or /logs/verifier.

## 8. Expected loss per lever (tests channel)
| scenario | positive points lost | tests % kept | overall (judge 90) |
|---|---|---|---|
| L2 wrong (tuned exact DW, times out) | 54/84 measured | 36% | 62.9 |
| L1 wrong (KMB or greedy attach, in time) | 63/84 measured | 25% | 57.5 |
| L3 wrong in helper (quote and report) | 69/84 measured | 18% | 53.9 |
| L3 wrong in report only (secondary stated-rule lever) | 43/84 measured | 49% | 69.4 (thin) |
Each lever alone >= 25% of test points. Expected tests loss for Opus: Branch B (2/3) about 63%, Branch A (1/3) about 75%, plus L3 where its program keeps the helper.

## Wave 1 hardening (678c839, 27 Oct 2026)

Sections 2-8 above describe build 57a2dd7. Wave 1 supersedes every span item in them (E_BAD_SPAN, the span check in chain 1, LV-CC-2 at the stated maximum, the size clause) as follows.

- Lever P-1 (computational core, no stated decomposition parameter). Deleted from `environment/ci/api_contract.md`: the E_BAD_SPAN rejection (rejection order is now E_DUP_SITE, E_UNKNOWN_ENDPOINT, E_NO_NETWORK) and the clause "at most 52 sites ..., at most 95 links and at most 17 cold rooms". Kept: "Limit: the command must finish a book within 4 seconds per project in it plus 10 seconds of start-up." Deleted `SPAN = 4` and its check from the shipped and fixed parser; renamed shipped `_spanning_links` to `_tree_links`.
- Shipped data regenerated (`datagen.py`, seed 174241): reach drawn per project 3-7, 20% of projects built as pieces meeting at single sites with shuffled positions, closed decoys of any span; max non-depot gap per project ranges 3-16; cold rooms 4-10. A plain exact program (subsets over cold rooms, or a corridor-order sweep with width from data) is exact and fast on it.
- Hidden: the 8 old books are byte-identical (digests `runs/old_book_digests.json`). New books wide_1..3 (BOOK_SEED+5..+7, own RNG): 10 projects, 96-127 sites, 30-41 cold rooms, 248-339 links, 5-6 hub pieces of 15-18 sites meeting at single sites, one few-cold-room piece, one narrow run of 8-10 cold rooms on consecutive positions, one planted tie, positions shuffled so open links reach half the book. `_wide_shape` asserts all five branches per project; `sweep300.py` covers 300 seeds.
- Reference (`_solve` / `_optimum` in tests, `core._solve` in the oracle): split at single sites from the depot, deepest piece first; each piece solved exactly over subsets of its needed sites or by a last-use sweep in corridor order, whichever estimate is smaller; integer score cost*2**m + rank bit gives the stated tie rule exactly; uniqueness by banning each chosen link in its piece.
- Checks added: wide_1_core 5, wide_2_core 5, wide_3_core 5, wide_books_report 3, wide_books_summary 3, wide_networks_feasible 3 (24 of 108 = 22.2%). 26 old check bodies byte-unchanged.
- Lever P-5: judge rebuilt to 13 criteria (positive 32, probes R1-R7 21/32 = 65.6%); see `JUDGE_MAP.md`.
- Kill and cost measurements: `KILL_TEST.md` (prototype) and `COST_TABLE.md` wave 1 (final generator, Docker).

## Harden round _a4, cap-60 build (board b223662, 30 Oct 2026)

Diagnosis: `harden_r_a4/DIAGNOSIS.md` (Phase A GENUINE; primary cause 4; the a4 program, Dreyfus-Wagner over all cold rooms, lost the six wide checks by OOM CRASH and TIMEOUT, not by WRONG output). Master go 30 Oct 12:00: layout A, CRASH+TIMEOUT share of the a4 program allowed up to 60% of positive test weight for this bundle only; no change to instruction.md, the contract, agent-visible data or judge.toml.

- Tests: seven held-out far-reaching books wide_4 to wide_10 (`HELD_WIDE_BOOKS`, same builder `_make_wide`, BOOK_SEED+8..+14; wide_1..3 unchanged), each its own package call, each with core w5, report w5, summary w3 (21 checks, 91 points). Old 33 check bodies unchanged. 54 checks, positive 200, negatives -8; reward.toml test_output 0.0025.
- TRUTH.md: G05-M1 (link reach wording at lines 24-25) fixed; timing table, far-reaching description, check table and measured line updated to /200; hashes by `finalize_truth.py` last.
- Measured (Docker, --memory 4g --cpus 2): oracle 200/200; a4 final and a4 first-write 85/200 = 42.5 (lost 115 lever points: TIMEOUT 97, CRASH 18, WRONG 0); DW global 85; last-use sweep 82 (115 CRASH + tie 3 WRONG); kmb 28 and greedy 28 (112 lever + 60 other WRONG); perlink 19 (115 + 66 WRONG). Reference CLI 0.13-0.17 s per new book (bar 12.5 s); verifier worst case <= 1507 s (bar 2430).
- DESIGN READY items: (a) predicted final = (42.5 + judge mid)/2. With judge.toml unchanged as the go requires, the judge mid is the a4 marking 14/32 = 43.75 (also 43.75 at 25% probes), so predicted final 43.1, above 35; the 34.9 of layout A needs the probe-band judge rebuild (judge mid 27.3) that this go did not include. (b) lever share 115/200 = 57.5%; held-out w5 tier 120/200 = 60.0% (>= 50%). (c) no blind program measured above 65 (blind reads are the master's next step; DW 85/200 = 42.5). (d) verifier worst 1507 s = 62% of the limit (<= 90%). (e) every generic solver loses >= 15% of lever points: heuristics by WRONG (97-100%), exact fast-on-shipped programs by v3.5 hidden-scale loss (100%), under the cap-60 exception; shipped inputs fast; reference <= 1/4 of the limit.
