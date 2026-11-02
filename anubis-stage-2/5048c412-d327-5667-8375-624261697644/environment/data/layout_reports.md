# Report layout standard

The balancing program writes thirty-one reports into its output directory: `summary.json`, `policy_audit.json`, `data_quality.json`, `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`, `segment_commercial.json`, `segment_public.json`, `station_ledger.csv`, `loss_ledger.tsv`, `balanced.sqlite`, `loss_book.xlsx`, `reconciliation.json`, `prior_delta.json`, `licence_losses.csv`, `scheme_losses.json`, `gauging_net.psv`, `station_index.xml`, `exits.yaml`, `loss_by_day.csv`, `basin_North.tsv`, `basin_South.tsv`, `basin_West.tsv`, `basin_East.tsv`, `segment_commercial.tsv`, `segment_public.tsv`, `catchment_totals.csv`, `storage_bands.txt`, `season_brief.md` and `manifest.json`. The four `region_` reports are the basin reports, one per basin, named after the basin. Basin names in any listing ordered by basin are in Unicode code point order (East, North, South, West).

## Byte forms

Every JSON report is UTF-8 text holding one JSON object, written with object keys sorted by Unicode code point, an indentation of two spaces with each key and each array item on its own line, a comma at the end of every line that is followed by another item of the same object or array, a colon and one space between a key and its value, integers as plain decimal numbers, every non-ASCII character escaped as a backslash, the letter u and four lowercase hexadecimal digits, and one newline at the end of the file. This is exactly the text that Python's `json.dumps(value, indent=2, sort_keys=True)` returns, followed by a newline. An empty array is written `[]` and an empty object `{}`.

Every other text report is UTF-8 text in which every line, the last included, ends in a newline, with no blank line except where a layout below places one. The csv, tsv and psv reports have a header line and one record per line, with fields separated by commas, tab characters and `|` characters respectively; no field is quoted except `station_name` in `station_ledger.csv`, which is always enclosed in double quotes. Integers are plain decimal numbers everywhere.

## summary.json

Keys: `season` (the season label), `basins` (an object with one key per basin name, each holding `exit` and `rounds` as the basin reports them under `std_balancing.md`), `transferred_ml_total` (the sum of `transferred_ml` over the four basin reports), `loss_kl_total` (the sum of `loss_kl` over the two segment reports), `gaugings_net` (the number of net gaugings) and `reservoirs` (the number of reservoirs in the register authority).

## policy_audit.json

Keys: `season`, `revision_cutoff` (integer), `basins` (an object with one key per basin name, each holding `damping_percent`, `patience` and `round_budget` as the basin operating parameters table of `sc_k2.docx` gives them) and `loss_rates` (an array of objects with `segment`, `revised_on` and `rate_milli`, one per row of the rate table of `mt_loss.pdf`, ordered by `segment` and then by `revised_on`).

## data_quality.json

Keys: `gaugings_read` (gauging records read from the three exports), `revisions_applied` (revision lines at or below the cutoff that name a gauging an export holds), `revisions_after_cutoff` (revision lines above the cutoff), `revisions_unmatched` (revision lines at or below the cutoff that name a gauging no export holds), `gaugings_voided` (gaugings whose net state is void) and `mirror_mismatches` (reservoirs of the register authority whose `stn_mirror.csv` row is missing, or differs from the register authority in station name or basin, or from the meter file in its meter reading).

## region_North.json, region_South.json, region_West.json, region_East.json

Keys: `basin` (the basin name), `exit` (`balanced`, `stalled`, `cycle` or `budget`), `rounds` (the round count the exit reports), `damping_percent` (the damping the basin holds when its balancing ended), `reservoirs` (an array with one object per reservoir of the basin, in register order), `transferred_ml` (the sum over the reservoirs of the absolute value of `change`) and `storage_total` (the sum of the reservoirs' `balanced_ml`). Each reservoir object has `stn`, `station_name`, `opening_ml`, `balanced_ml` (the balanced storage the basin reports for it under `std_balancing.md`) and `change` (`balanced_ml` minus `opening_ml`).

## segment_commercial.json, segment_public.json

One report per segment. Keys: `segment`, `licences` (an array with one object per licence of that segment in `lc_register.json`, ordered by licence code, each with `licence`, `date`, `gaugings` (its net gaugings) and `loss_kl` (the sum of their losses, `std_loss.md`)), `gaugings` and `loss_kl` (the sums over the array).

## station_ledger.csv

Header `basin,stn,station_name,opening_ml,balanced_ml,change`; one line per reservoir, ordered by basin name (Unicode code point order) and, within a basin, in register order. The values are those of the basin reports.

## loss_ledger.tsv

Header `gauging_id`, `licence`, `segment`, `from_stn`, `to_stn`, `loss_kl` (tab-separated); one line per net gauging, ordered by gauging id.

## basin_North.tsv, basin_South.tsv, basin_West.tsv, basin_East.tsv

Header `stn`, `gauge_no`, `catchment`, `opening_ml`, `balanced_ml`, `change`; one line per reservoir of the basin, in register order, with the values of the basin report.

## segment_commercial.tsv, segment_public.tsv

Header `gauging_id`, `licence`, `date`, `loss_kl`; one line per net gauging of the segment, ordered by gauging id, `date` being its licence's date.

## licence_losses.csv

Header `licence,scheme,segment,date,gaugings,loss_kl`; one line per licence of `lc_register.json`, ordered by licence code, with its net gaugings and the sum of their losses.

## scheme_losses.json

One key, `schemes`: an array with one object per scheme of `sc_k2.docx`, ordered by scheme code, each with `scheme`, `segment`, `licences` (the number of licences of `lc_register.json` issued under it), `gaugings` and `loss_kl` (the sums over those licences).

## loss_by_day.csv

Header `date,gaugings,loss_kl`; one line per distinct licence date of `lc_register.json`, ascending, with the net gaugings and the loss summed over the licences of that date.

## gauging_net.psv

Header `gauging_id|licence|from_stn|to_stn|from_points`; one line per net gauging, ordered by gauging id, with the from station's draw points written `0`, `1/2` or `1`.

## station_index.xml

The line `<?xml version="1.0" encoding="UTF-8"?>`, then `<stations season="LABEL">` with the season label, then one line per reservoir of the register authority in register order, written as two spaces and `<station stn="..." gauge="..." catchment="..." basin="...">NAME</station>` with the station name as the element text, then `</stations>`. In attribute values and element text the characters `&`, `<`, `>` and `"` are written `&amp;`, `&lt;`, `&gt;` and `&quot;`.

## exits.yaml

The line `season: LABEL`, the line `basins:`, then per basin in basin order the line of two spaces, the basin name and a colon, followed by four lines of four spaces each: `exit: `, `rounds: `, `damping_percent: ` and `transferred_ml: `, each followed by the basin report's value.

## catchment_totals.csv

Header `catchment,basin,reservoirs,opening_ml,balanced_ml`; one line per catchment of `bs_map.xml`, ordered by catchment code, with its basin, the number of its reservoirs and the sums of their opening and balanced storages.

## storage_bands.txt

One line per basin and storage band holding at least one of the basin's reservoirs, ordered by basin and then by band: the basin name, a space, the band written `LOW-HIGH`, a space and the number of the basin's reservoirs whose balanced storage lies in the band. The bands are 0-249, 250-499, 500-749 and so on, 250 megalitres wide.

## season_brief.md

The line `# Season LABEL balancing`, a blank line, the line `| Basin | Exit | Rounds | Damping | Transferred ML |`, the line `|---|---|---|---|---|`, then one line per basin in basin order: `| `, then the basin name, exit, round count, damping and megalitres transferred of the basin report separated by ` | `, then ` |`.

## reconciliation.json

Keys: `storage` (an object with one key per basin holding `opening_total` and `balanced_total`, the sums of the basin's opening and balanced storages), `loss_kl` (an object with `by_gauging`, `by_licence`, `by_segment` and `by_day`: the total loss summed over the lines of `loss_ledger.tsv`, of `licence_losses.csv`, over the two segment reports and over the lines of `loss_by_day.csv`) and `gaugings` (an object with `net`, the number of net gaugings, and `by_licence`, the sum of the `gaugings` column of `licence_losses.csv`).

## prior_delta.json

Keys: `prior_season` (the season of `prior_balance.json`), `transferred_ml_total` and `loss_kl_total` (each an object with `prior`, `current` and `difference`, the current figure from `summary.json` minus the prior figure) and `basins` (an object with one key per basin holding `prior_exit`, `exit`, `prior_rounds` and `rounds`).

## balanced.sqlite

An SQLite database with two tables, each filled in the order given here. Table `basin` has the columns `basin` (TEXT), `exit` (TEXT), `rounds` (INTEGER), `damping_percent` (INTEGER) and `transferred_ml` (INTEGER), one row per basin in basin order. Table `reservoir` has the columns `basin` (TEXT), `stn` (TEXT), `opening_ml` (INTEGER), `balanced_ml` (INTEGER) and `change` (INTEGER), one row per reservoir in the order of `station_ledger.csv`. The rows of each table are read in insertion order. Its content dump is one line per row, table `basin` first: the table name, then the row's values in column order, all joined by `|`, each line ending in a newline.

## loss_book.xlsx

An Office Open XML workbook with two sheets in this order. Sheet `licences` has the header row `licence`, `scheme`, `segment`, `date`, `gaugings`, `loss_kl` and then the rows of `licence_losses.csv`; sheet `segments` has the header row `segment`, `gaugings`, `loss_kl` and then one row each for `commercial` and `public`. Text values are text cells and integer values are numeric cells. Its content dump is one line per row in sheet order: the sheet name, then the row's cell values, all joined by `|`, each line ending in a newline.

## manifest.json

One key, `reports`, holding an object that maps the file name of each of the other thirty reports to a lowercase hexadecimal SHA-256 digest: of the report's bytes for a text report, and of its content dump, encoded as UTF-8, for `balanced.sqlite` and `loss_book.xlsx`.
