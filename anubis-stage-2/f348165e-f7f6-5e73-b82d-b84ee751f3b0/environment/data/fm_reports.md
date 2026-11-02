# Report forms

Every report of a settlement run is written into the output folder under the file name given here. Classes are always listed in the class order of ct_svc.md, pools by pool id and tenants by code, ids and codes compared by code point; rows about members or bill lines are ordered by class, then pool, then tenant, unless a form below gives another order. Every count and amount is a whole number written in decimal with no sign for positive values, no leading zero and no separator.

Byte forms. JSON reports are written with two-space indentation, keys sorted by code point, a comma at the end of every item but the last, a colon and one space between key and value, characters outside ASCII escaped as \u sequences, and one line feed after the closing bracket. CSV reports have a header row, fields separated by commas, a field enclosed in double quotes only when it holds a comma, a double quote or a line feed (a double quote inside is doubled), and every row ended by one line feed. TSV and PSV reports have the same rows with a tab or a vertical bar as separator and no quoting. XML reports start with the line `<?xml version="1.0" encoding="UTF-8"?>`, put each element on its own line with two spaces of indentation per level, write attributes in the order given here with double quotes, escape the characters ampersand, less-than, greater-than and double quote in attribute values as entities, and end with one line feed; an element without children is written self-closing as `<name attr=".."/>`, and a root element without children as `<name/>`. A text report with no header row and nothing to list is empty (zero bytes). Every text report ends with one line feed and has no other blank line unless a form below places one.

The result object of a class is a JSON object with the keys label (the label of the control file), traffic_class, counted_requests (requests in the window that are neither rejected nor orphans), token_units (the sum of the token units of the members of every pool of the class), and pools: a list with one object per settled pool, holding pool, exit, rounds (the round count), final_step (the step in force when it stopped) and members: a list with one object per member, holding tenant, contracted_ru (after corrections), demand_ru and settled_ru, as st_settle.md defines them. When the program is called with a request log and the control file, it prints the result object of the class of that log on one line, keys sorted, a comma and one space between items, a colon and one space between key and value, followed by one line feed, characters outside ASCII escaped as in the JSON reports.

scenario_CLASS.json, one file for each of the five classes with CLASS the class name: for a class in scope the keys traffic_class, in_scope (true), window (the start and end instants of the control file), result (the result object) and bill_total_micro (the class total of st_bill.md); for a class out of scope only traffic_class and in_scope (false).

perf_report.json: classes_in_scope (list of class names), pool_count (settled pools), member_count (members of settled pools) and counted_requests (over all classes).

bottleneck_analysis.json: longest (list of lists of class, pool and round count for every pool whose round count is the largest of the run, the cycle count -1 taking part as written), unsettled (list of lists of class, pool and exit for every pool whose exit is cycled or budget) and stalled (list of lists of class and pool for every stalled pool).

recommendations.json: review_shift_ru (the threshold of the control file) and actions (list of lists of class, tenant, action and shift for every member whose settled reservation differs from its contracted reservation by at least the threshold, the shift being settled minus contracted and the action raise when the shift is positive and lower when it is negative; a member whose settled reservation equals its contracted reservation has no action, whatever the threshold).

data_quality.json: orphan_requests, out_of_window and rejected_requests (each an object mapping every class in scope to its count), retired_members (list of lists of class and tenant, by class and then tenant, for every tenant row of a class in scope that is retired after corrections) and corrections (an object with the counts applied, cutoff and unmatched).

pool_settlement.csv: columns traffic_class, pool, members (member count), exit, rounds, final_step, pool_total_ru; one row per settled pool.

tenant_holdings.tsv: columns traffic_class, pool, tenant, contracted_ru, demand_ru, settled_ru; one row per member, rows by class, pool and tenant.

round_trace.psv: columns traffic_class, pool, round, residual_total, step; one row per round each settled pool opened, in round order, where step is the step in force for the movements of that round (for a round that settles the pool, the step in force when it settled).

exit_summary.xml: root element exits holding one element class per class in scope with the attributes name, settled, stalled, cycled and budget (the number of pools of each exit).

pool_members.json: an object mapping every class in scope to an object mapping each settled pool to the list of its member codes.

holding_shift.xml: root element shifts holding one element shift per member whose settled reservation differs from its contracted reservation, with the attributes class, pool, tenant, from (contracted), to (settled) and delta (settled minus contracted).

tenant_bills.csv: columns traffic_class, pool, tenant, settled_ru, token_units, overage_units, reservation_micro, overage_micro, orchestration_micro, total_micro; one row per bill line.

class_billing.json: an object mapping every class in scope to an object with the keys lines, reservation_micro, overage_micro, orchestration_micro and total_micro (the sums over its bill lines; lines is their number).

invoice_lines.yaml: one entry per bill line, each written as three lines: `- class: CLASS`, `  tenant: CODE` and `  total_micro: AMOUNT`, with nothing else in the file.

invoice_digest.md: for every class in scope a heading line `## CLASS`, a blank line, the table header line `| tenant | total_micro |`, the line `|---|---:|`, one line `| CODE | AMOUNT |` per bill line of the class, and a blank line after the table except after the last class.

overage.txt: one line per bill line with positive overage units: the class left-aligned in 10 characters, the tenant left-aligned in 12 characters, the overage units right-aligned in 12 characters and the overage charge right-aligned in 14 characters, padded with spaces.

rate_application.json: an object mapping every class in scope to an object with the keys eff_from, ru_rate_micro, over_rate_micro and round_fee_micro of the rate row that applies, and units_per_ru: an object mapping each settled pool of the class with a member whose token units are not zero to its units per RU.

billing_ledger.sqlite: a SQLite database with the table bills (columns traffic_class TEXT, tenant TEXT, total_micro INTEGER; one row per bill line, inserted in report order) and the table pools (columns traffic_class TEXT, pool TEXT, exit TEXT, rounds INTEGER; one row per settled pool, inserted in report order). The report is compared by the rows of each table in rowid order.

billing_book.xlsx: a workbook with one sheet named bills whose first row is the header traffic_class, tenant, reservation_micro, overage_micro, orchestration_micro, total_micro, followed by one row per bill line; text cells hold strings and amount cells hold numbers. The report is compared by the cell values of the sheet, row by row.

delta_prior.csv: columns traffic_class, tenant, settled_ru, prior_ru, delta_ru (settled minus prior); one row per member, rows by class and tenant. The prior output is a JSON object whose key settled maps each class to an object mapping tenant codes to settled RU.

reconciliation.json: an object mapping every class in scope to an object with the keys bill_lines_total (sum of total_micro over the rows of tenant_bills.csv of the class), class_total (total_micro of class_billing.json for the class), ledger_total (sum of total_micro over the rows of the bills table of billing_ledger.sqlite written in the same run, for the class), residual_micro (bill_lines_total plus ledger_total minus twice class_total) and ru_residual (the sum of settled reservations minus the sum of contracted reservations over the members of the class).

demand_by_model.tsv: columns traffic_class, model, counted_requests, token_units; one row per class in scope and model with at least one counted request, models by name.

orphans.csv: columns traffic_class, req_id, reason; one row per request of a class in scope that adds nothing to demand, with the reason orphan, rejected or out_of_window, rows by class and req_id. A request outside the window has the reason out_of_window whatever its status.

corrections_applied.csv: columns layer (amendment or override), seq, tenant, traffic_class, field, status; amendments first and then overrides, each by seq.

window_counts.csv: columns traffic_class, in_window, out_of_window; one row per class in scope.

manifest.json: the key reports mapping the file name of every other report of the run to the lowercase hexadecimal SHA-256 digest of its content. A text report is digested as its bytes. The database report is digested as its dump: for each table in name order, the line `table NAME` followed by one line per row in rowid order with the values joined by tabs, each line ended by a line feed. The workbook report is digested as its dump: one line per sheet row with the cell values joined by tabs, each line ended by a line feed.
