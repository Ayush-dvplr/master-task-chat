# Table reports and manifest

## sweep.sqlite

A SQLite database with two tables. `envelope_final` has the columns `district` (TEXT), `code` (TEXT) and `final_dollars` (INTEGER), one row per envelope, inserted by district and then envelope code. `household_exit` has the columns `district` (TEXT), `exit` (TEXT), `rounds` (INTEGER) and `damping_percent` (INTEGER), one row per household, inserted by district. The database is compared by its tables, columns, row order and values, not by its bytes.

## sweep_book.xlsx

An Office Open XML workbook with two worksheets, in this order: `exits`, whose header row is `district`, `exit`, `rounds`, `damping_percent`, and `final`, whose header row is `district`, `code`, `final_dollars`. Below each header, one row per household or per envelope in the same order as in sweep.sqlite. Text cells hold text and number cells hold whole numbers. The workbook is compared by its worksheet names and order and its cell values, not by its bytes.

## manifest.json

A JSON report (layout_reports.md) with one key, `reports`: a list, in code point order of the name, with one object per other report holding `name` and `sha256`, the lowercase hexadecimal SHA-256 digest of a byte string. For a text report the byte string is the report's file content. For sweep.sqlite and sweep_book.xlsx it is the report's table text: for each table (sweep.sqlite, in the order listed above) or worksheet (sweep_book.xlsx, in workbook order), a line `table <name>: ` followed by the column names or header cells joined by `|`, then one line per row with its values joined by `|`, numbers as decimal integers; every line ends with a line feed.
