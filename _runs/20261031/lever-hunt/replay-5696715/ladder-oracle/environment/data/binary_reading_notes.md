# Reading the Binary Inputs (stdlib only)

The spreadsheet is a standard OOXML zip: open it with `zipfile`, read
`xl/worksheets/sheet1.xml` and any shared strings, and parse cells with
`xml.etree.ElementTree`. The live sheet is the one whose B1 cell equals the
`calibration_version` in season_profile.json.

The policy document is a plain PDF 1.4 with uncompressed text streams. Extract
the text with `zlib` (for any deflated stream) and two regexes over the raw
bytes: the stream body pattern `stream\r?\n(.*?)\r?\nendstream` and the
show-text pattern `\(((?:\\.|[^\\()])*)\)\s*Tj`. As hex byte strings these
are `73747265616d5c723f5c6e282e2a3f295c723f5c6e656e6473747265616d` and
`5c2828283f3a5c5c2e7c5b5e5c5c28295d292a295c295c732a546a`. The review unit cost,
the F-beta beta, and the CI z read out of the extracted text lines.

The levy addendum is a standard OOXML DOCX zip: open it with `zipfile`, read
`word/document.xml`, and pull the text out of the `<w:t>` elements with
`xml.etree.ElementTree`. The smurf levy basis points and the settlement floor
read out of those paragraphs. The SQLite lookups (`.sqlite` and `.db`) are
real databases; open them with the `sqlite3` module. Every value they hold is
also present in a flat file.
