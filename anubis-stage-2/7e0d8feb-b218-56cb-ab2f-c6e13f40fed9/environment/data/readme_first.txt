readme first
============

This directory is the whole of the material for one transmission day of a
regional playout channel. Nothing outside it is needed and nothing outside
it is authoritative.

The file names are deliberately non obvious. They name the record they hold
and not the stage that consumes them, so the way to find a value is to open
files rather than to guess from a stem. Start with these three:

  pipeline_contract_overview.md      what the fourteen stages are
  data_lineage.md                    which file feeds which stage
  output_artifact_contract.md        what has to be written, and where

Two load bearing sources are not plain text.

  contract_terms_workbook.xlsx       a real workbook with three sheets. One of
                                     them carries the settled control set and
                                     the other two are superseded, each with
                                     terms of its own. The sheet name settles
                                     nothing and neither does the sheet
                                     position; the control set cell does.
  regulatory_minutage_memo.pdf       a real document. Three settlement
                                     constants are published there and
                                     nowhere else in this directory.

Three files are decoys and each is disavowed in data_lineage.md:
legacy_commission_table.csv, blackout_overlay_drafts.xml and
prior_conform_register.csv. The prior register is the superseded automated
computation of this same day. It is reported against and never consumed.

Every identifier in this directory is minted for this instance. There is
nothing here to look up anywhere else, and no external source knows these
references.
