# Pipeline contract

This contract fixes how the season's work is put together. Terms defined in the glossary carry their defined meaning wherever they appear in the documents.

## Stages

The season's figures come from one chain. The register authority gives every reservoir and its basin. The meter file, its replacements resolved and its corrections applied as of the survey date, gives the corrected meter readings; the storage survey, read against them, fixes the datum offsets; together they give every opening storage. The three gauging exports, brought to their net state by the revision log, give the net gaugings. Each basin is balanced on its own net gaugings with its own parameters (`std_balancing.md`). The conveyance loss of every net gauging is then accounted from the balanced storages (`std_loss.md`), and the reports are written (`layout_reports.md`). A wrong reading at any stage shows up in many figures downstream of it.

## Authority

Where two files give the same fact, the file a dictionary names as the authority for it governs, and the other file is used only for the counts the report layout asks of it. Method constants are taken only from the method containers `cfg_reference.md` names. A file kept from an earlier run is not an input to any stage.

## Order of work

Every basin is balanced and every loss accounted before any report is written. When an input breaks a rule its dictionary states, no report is written for the extract.

## Extracts in this layout

Every extract in this layout, the shipped one and the others the program is run on, keeps within these facts: 4 to 11 catchments, each holding at least one reservoir; 12 to 30 reservoirs; up to 60 survey rows, each listing 2 to 6 reservoirs; up to 80 meter records; gauge numbers from G1000 to G9999. Every `.csv` file is comma-separated values as RFC 4180 defines them, with a header line; `gx_b.tsv` and `rv_log.psv` follow the same rules with a tab and a pipe as the delimiter. Each container file follows the standard its format reference names, in any form that standard allows.
