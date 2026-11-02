# The office register workbook

The register file named by the index is an XLSX workbook: a ZIP archive of XML
parts. It is the only source of office zones, longitudes, working windows,
solar windows, working days and attendee rates. A comma separated snapshot of
the register exists as a lower authority copy (authority-and-audit.md).

## Finding the sheets

The sheet names are listed in `xl/workbook.xml`; each `sheet` element names a
relationship identifier, and `xl/_rels/workbook.xml.rels` maps that identifier
to the worksheet part. The worksheet file names follow no pattern and do not
match the sheet names or their order. A cell is a `c` element whose `r`
attribute is its reference, such as `B2`. A cell with `t="s"` holds an index
into the shared string table `xl/sharedStrings.xml`; a cell with
`t="inlineStr"` holds its text inside; any other cell holds a number in its
`v` element. Text cells may hold digits, and the digits are the value: a
numeric column can mix number cells and text cells, and a text cell may write
a number with comma thousands separators, so `12,500` is twelve thousand five
hundred.

The sheet in force for a table is chosen by its first two rows, never by its
name: cell `A1` names the table (`office register` or `attendee rates`), cell
`B1` names the edition and cell `B2` the status. For each table the sheet in
force is the one whose `A1` is that table, whose `B1` equals the
`register_edition` of the store, and whose `B2` is `in force`. Sheets of other
editions, and sheets of the same edition that are `superseded`, `withdrawn` or
`draft`, are never read. Row 3 is a note. Row 4 names the columns. Data starts
on row 5.

## Serial dates

Dates are cell numbers counting days from the workbook epoch. When the
`workbookPr` element of `xl/workbook.xml` carries `date1904="1"` the epoch is
1904-01-01, so serial 0 is 1904-01-01 and serial 44926 is 2027-01-01;
otherwise the epoch is 1899-12-30.

## Office register rows

Columns: `office`, `tzid`, `longitude`, `weekday`, `working`, `open minute`,
`close minute`, `solar open`, `solar close`, `effective from`.

Each row describes one office on one local weekday (`MO` to `SU`) from its
`effective from` date onward. For an office and a local date, the row in force
is the row for that office and that date's weekday with the greatest
`effective from` that is not later than the date. `working` is `Y` on a working
day of the office and `N` on a non working day. The working window and the
solar window of that date are the half open minute ranges
[`open minute`, `close minute`) and [`solar open`, `solar close`) counted from
local midnight; a non working day has a working window of 0 to 0.

Worked example. San Francisco has a Monday row effective 2026-01-01 with a
working window 540 to 1050 and a Monday row effective 2027-06-01 with 510 to
1050. On Monday 2027-05-31 the window is 540 to 1050; on Monday 2027-06-07 it
is 510 to 1050.

`tzid` is the zone of the office. `longitude` is a decimal string that is read
exactly as written: the solar offset of an office in whole minutes is the
longitude multiplied by four and then rounded half away from zero, with the
product formed and rounded in exact decimal arithmetic. A longitude of
`174.8749999999999999` gives 699.4999999999999996 and so 699 minutes, which a
binary float reading would turn into 700.

The solar minute of an instant for an office is

    (instant expressed in whole minutes since 1970-01-01T00:00:00Z
     plus the solar offset of the office) modulo 1440

with the modulo taken as the non negative remainder.

## Attendee rates

Columns: `attendee`, `cents per hour`, `effective from`. For an attendee and a
date, the rate in force is the row with the greatest `effective from` not
later than the date. An attendee with no row in force costs nothing.
