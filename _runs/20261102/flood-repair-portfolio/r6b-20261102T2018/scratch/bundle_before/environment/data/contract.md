# Flood repair funding book: data and report contract

A book is a folder of files describing several funding rounds of a flood repair programme. In each round the programme funds a portfolio of repair proposals. This contract defines every file of a book, how each round is checked, valued and planned, and every output document.

The report program is one self-contained file that uses python3 and its standard library only. It is run as `python3 derive_report.py DATA_DIR OUT_DIR`, reads the book in `DATA_DIR`, and writes the documents listed under "Output documents" into `OUT_DIR`, creating that folder when it is missing. It must not depend on its own working directory or on where the book folder is.

## Limits

Every book this program is given stays inside these limits:

- at most 200 rounds in a book and at most 160 proposal rows in a round;
- at most 900 conflict records in a round, counting its rows in `permits.csv` and its entries in `exclusions.json` together;
- every segment rate is a whole number from 5 to 60, every risk uplift a whole number from -10 to 30, and every site premium a whole number from 0 to 800.

The program must write all documents for a book inside these limits within 20 seconds of wall time.

## Files

`manifest.json` holds an object with `book` (the book id) and `files` (the names of the nine data files of the book, in the book's declared order). If a declared file is missing from the folder, the program writes no documents, writes the line `ERROR MISSING_FILE <name>` to standard error, where `<name>` is the first missing file in declared order, and exits with status 1.

All ids are compared as plain strings. CSV and TSV files have one header line; a data row is any later non-empty line. Row numbers in this contract count data rows of the whole file from 1 (the first line after the header is row 1). Entries of `exclusions.json` are numbered from 1 in array order.

- `proposals.csv` with columns `round,proposal,site,crew,households,risk_override`. One row per proposal of a round. The rounds of the book are exactly the round ids that appear in this file. `households` is the number of households the repair protects. `risk_override`, when not empty, is the risk class used for the proposal in place of the risk class of its site; when empty, the proposal uses the risk class of its site from `sites.jsonl`.
- `segment_codes.tsv` with columns `round`, `proposal`, `segment`. Gives the segment of each proposal of the round. Every proposal row of a round has exactly one row here for that round.
- `sites.jsonl`, one JSON object per line with `site`, `risk_class` (one of `A`, `B`, `C`, `D`) and `premium`. This register is shared by all rounds.
- `region_codes.csv` with columns `site,region`. Region of each site, one of `North`, `South`, `West`, `East`.
- `crews.tsv` with columns `crew`, `mode`. Mode is `exclusive` or `shared`. This register is shared by all rounds.
- `permits.csv` with columns `round,permit,proposal,status`. Each row says that in that round the proposal is attached to the permit, with status `held`, `applied` or `withdrawn`. Permit ids may recur in other rounds; a permit is considered within one round only.
- `exclusions.json`, a JSON array of objects `{"round", "first", "second"}`. Each of `first` and `second` names either a proposal of that round or a site; a site name stands for every proposal of that round at that site.
- `benefits.ini` with section `[segment_rate]` (one whole-number rate per segment name) and section `[risk_uplift]` (one whole-number uplift for each of `A`, `B`, `C`, `D`). Segment names are lower case.
- `audit_queries.txt`, one query per line: `VALUE <round> <proposal>` or `PAIR <round> <proposal> <proposal>`. Queries name rounds of the book and proposals of the named round.

## Checking a round

The round-scoped files are `proposals.csv`, `segment_codes.tsv`, `permits.csv` and `exclusions.json`. A round is checked by taking these files in the declared order of `manifest.json` and, inside each file, the rows (or entries) of that round in file order. Each row is tested against the checks of its file in the order listed; the first check that applies is the row's fault. The first faulty row found this way rejects the round with that fault.

- `proposals.csv`: `DUPLICATE_PROPOSAL` when the proposal id already appeared on an earlier row of the same round; `INVALID_INPUT` when `households` is not a whole number written in digits from 1 to 60, when the site is not in `sites.jsonl`, when the crew is not in `crews.tsv`, or when `risk_override` is neither empty nor one of `A`, `B`, `C`, `D`.
- `segment_codes.tsv`: `UNKNOWN_PROPOSAL` when the proposal is not a proposal of the round; `INVALID_INPUT` when the segment is not a key of `[segment_rate]`.
- `permits.csv`: `UNKNOWN_PROPOSAL` when the proposal is not a proposal of the round; `INVALID_INPUT` when the status is not `held`, `applied` or `withdrawn`.
- `exclusions.json`: `UNKNOWN_PROPOSAL` when `first` or `second` is neither a proposal of the round nor the site of a proposal of the round; `INVALID_INPUT` when `first` equals `second`.

A round with no faulty row is then valued. If any proposal of the round has a benefit below 1, the round is rejected with `NONPOSITIVE_BENEFIT`; the reported file is `proposals.csv` and the reported row is the first such proposal row of the round. Every other round is planned.

## Valuing a proposal

The benefit of a proposal is

    households * (segment rate + risk uplift) + site premium

where the segment rate is the `[segment_rate]` value of the proposal's segment, the risk uplift is the `[risk_uplift]` value of the proposal's risk class (its `risk_override` when not empty, otherwise its site's `risk_class`), and the site premium is the `premium` of the proposal's site. All arithmetic is in whole numbers.

## Conflicts

Two different proposals of a planned round conflict when at least one of these sources joins them:

- `crew`: both have the same crew and that crew's mode is `exclusive`;
- `permit`: both are attached in that round to the same permit by rows whose status is `held` or `applied` (rows with status `withdrawn` count for nothing);
- `exclusion`: an entry of that round names one of them in `first` and the other in `second`, in either order.

## Planning a round

A portfolio of a planned round is a set of its proposals with no two in conflict. A crew whose mode is `shared` can work on at most four of the proposals in a portfolio. Its total benefit is the sum of the benefits of its proposals. The chosen portfolio of the round is the one with the greatest total benefit. When several portfolios share that greatest total, compare their id lists, each sorted in ascending order, at the first position where they differ; the portfolio whose list has the smaller id there is chosen.

Every reported figure of a round is computed from the one portfolio chosen for it.

## Output documents

All documents are JSON. Id lists are sorted ascending; rounds are listed in ascending round id.

`summary.json`: `{"book", "rounds", "planned_rounds", "rejected_rounds", "selected_proposals", "total_benefit"}`. `rounds` holds one object per round of the book: `{"round", "status", "proposals", "selected", "total_benefit"}` where `status` is `planned` or `rejected`, `proposals` is the number of proposal rows of the round, `selected` is the chosen portfolio (an empty list for a rejected round) and `total_benefit` its total benefit (0 for a rejected round). The top-level counts and `total_benefit` add up over all rounds.

`policy_audit.json`: `{"book", "rows"}` with one row per non-empty line of `audit_queries.txt`, in file order. Every row has `line` (the 1-based line number in the file), `kind` (`VALUE` or `PAIR`), `round` and `status` (the round's status). A row for a rejected round has only these four keys. A `VALUE` row of a planned round adds `proposal`, `segment`, `segment_rate`, `risk_class` (the class used), `risk_uplift`, `households`, `premium`, `benefit` and `selected` (true when the proposal is in the chosen portfolio). A `PAIR` row of a planned round adds `first`, `second` (as written in the query), `sources` (the sources that join the two proposals, in the order `crew`, `permit`, `exclusion`, possibly empty), `conflict` (true when `sources` is not empty), `first_selected` and `second_selected`.

`data_quality.json`: `{"book", "rejected", "planned_rounds", "rejected_rounds", "conflict_pairs", "conflicts_by_source", "withdrawn_permit_rows"}`. `rejected` holds one object `{"round", "code", "file", "row"}` per rejected round, in ascending round id, where `code` is the fault, `file` the name of the file it was found in and `row` its row number (its entry number for `exclusions.json`). `conflict_pairs` counts the conflicting pairs of proposals over all planned rounds, each pair once. `conflicts_by_source` is an object with keys `crew`, `permit` and `exclusion`, each counting the conflicting pairs of planned rounds that this source joins (a pair joined by two sources counts under both). `withdrawn_permit_rows` counts the `withdrawn` rows of `permits.csv` belonging to planned rounds.

`region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`: `{"book", "region", "rounds", "selected_proposals", "total_benefit"}`. `rounds` holds one object `{"round", "selected", "benefit"}` for every planned round: the proposals of the chosen portfolio whose site lies in the region, and the sum of their benefits. The last two keys add up over `rounds`.

`segment_commercial.json` and `segment_public.json`: the same shape with key `segment` in place of `region`, restricted to proposals of that segment.
