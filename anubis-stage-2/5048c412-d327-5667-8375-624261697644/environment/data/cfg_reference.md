# Parameter and method-container reference

## basin_cfg.ini

An INI file. Section `season` holds `label` (the season label written into reports) and `revision_cutoff` (an integer; see `dict_gaugings.md`). The balancing parameters of each basin are in the basin operating parameters table of `sc_k2.docx`.

## Method containers

The method constants of the season live in three containers and in no plain-text file: the head offset table in `tab_h3.xlsx`, the conveyance loss rates in `mt_loss.pdf` and the scheme segments and the basin operating parameters in `sc_k2.docx`.

`tab_h3.xlsx` is a workbook in the Office Open XML SpreadsheetML format of ECMA-376. Row 1 of each sheet is a header. Sheet `offset` gives the head offset for every draw share: column A holds the share written as text with two decimals (`0.00` to `1.00`) and column B the head offset in megalitres, a whole number, negative below `0.50`.

`mt_loss.pdf` is a one-page document in the PDF format of ISO 32000-1. Its page shows the schedule as text, one line of the schedule per line of the page, in reading order.

`sc_k2.docx` is a document in the Office Open XML WordprocessingML format of ECMA-376, read as a consumer that understands the WordprocessingML namespace and no other namespace reads it. Its body holds two tables, each with a header row. The first, headed `scheme`, `class` and `segment`, has one row per scheme. The second, the basin operating parameters table, is headed `basin`, `damping_percent`, `patience` and `round_budget` and has one row per basin, holding three integers: the opening damping percentage (1 to 100), the patience (a positive integer) and the round budget (a positive integer).

## Prior balancing summary

`prior_balance.json` is the summary an earlier balancing run wrote, kept for comparison with the current run. Its figures carry no authority for the current season.
