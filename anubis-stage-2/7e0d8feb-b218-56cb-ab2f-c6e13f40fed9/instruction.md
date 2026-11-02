You are the conform engineer for a regional playout channel that runs into four markets,
and one transmission day has to be recomputed from source. The previous automated conform
of that same day survives in the corpus and it is wrong, so derive the day again from the
records rather than repair the old answer. Everything you need sits under `/app/data`.

Read `/app/data/readme_first.txt`, then `/app/data/pipeline_contract_overview.md`, which
names the fourteen stages and points at the specification for each one. The file names are
deliberately non-obvious, so `/app/data/data_lineage.md` records which file feeds which
stage and which files are decoys. `/app/data/glossary_and_field_dictionary.md` defines the terms and the fields of the main
input registers. `/app/data/output_artifact_contract.md` and
`/app/data/output_schema_reference.md` fix what to write and with which columns in which
order, and `/app/data/serialisation_and_digest_contract.md` fixes the bytes down to the
line ending. Two load-bearing sources are not plain text: `/app/data/contract_terms_workbook.xlsx` is a
real workbook carrying three control sets of contract terms, and
`/app/data/regulatory_minutage_memo.pdf` is a real document that is the only publication
of three settlement constants. Both carry values the day cannot be derived without.

Derive the day and write every artifact into `/app/out`. Publish the canonical ingest
attempt of every asset with its resolved rate and source span in
`/app/out/asset_register.csv`, the per-part channel frame counts in
`/app/out/segment_conform.csv`, the conditioned position of every break in
`/app/out/break_positions.csv`, and the placed start, trim and transmitted duration of
every slot in `/app/out/slot_placement.csv`. Publish every correction in
`/app/out/conform_trace.json` and the filler for each gap in `/app/out/filler_plan.csv`.
Publish the admitted spots in `/app/out/avail_plan.tsv` and every deferral with the reason
that settled it in `/app/out/deferral_ledger.jsonl`. Publish the market substitutions in
`/app/out/market_overrides.csv`, the four per-market break sets in
`/app/out/market_avails_mk_coast.json`, `/app/out/market_avails_mk_metro.json`,
`/app/out/market_avails_mk_north.json` and `/app/out/market_avails_mk_valley.json`, and
their union in `/app/out/market_avail_stream.jsonl`. Publish the money of every admitted
spot in `/app/out/settlement_ledger.psv`, the capped obligations in
`/app/out/makegood_ledger.json`, the unpriced and empty deliveries in
`/app/out/exception_ledger.jsonl`, and the per-advertiser totals in
`/app/out/advertiser_summary.csv`. Publish the advertising frames of every market clock
hour against the regulatory cap in `/app/out/minutage_report.csv`, and the residual each
carry scope was left holding in `/app/out/carry_ledger.json`. Publish the recomputed day
against the previous computation in `/app/out/reconciliation.xml`, the transmitted day in
`/app/out/playout_schedule.ini`, the two summaries in `/app/out/day_report.md` and
`/app/out/compliance_summary.md`, and the digest and day-level figures in
`/app/out/manifest.json`.

Hand the derivation back as a reusable program at `/app/out/conform.py`. It has to take an
optional data directory after `--data` and an optional output directory after `--out`,
creating the output directory and any missing parent when they do not exist, fall back to `/app/data` and
`/app/out` when given neither, read only the directory it was given, write those
twenty-five artifacts and nothing else, and only into the directory it was told to write
to, and leave its input directory exactly as it found it. It will be run against
transmission days of this channel other than this one, so build no figure and no
identifier from this day into it, and make two runs over the same inputs produce the same
bytes. Leave `/app/out` holding those twenty-five artifacts and `conform.py` and nothing
else, and keep one run over one day inside ten minutes.

Every published quantity is exact. Every frame count is a whole number of channel frames,
every amount of money is a whole number of minor units in the advertiser settlement
currency except the `gross_major` columns, which carry the currency's own number of
decimal places, and every ratio carries exactly ten decimal places. Do the whole
derivation in exact rational or whole number arithmetic and round only when a value is
written, in the directions the stage specifications and `/app/data/rounding_policy.yaml`
set out. Take the channel rate, the timecode base and the drop frame behaviour from the
records rather than from any rounded label. Honour the broadcast day boundary the channel
configuration publishes rather than a calendar day boundary. Apply the carry rule at every
conversion into channel frames, inside the scope each stage names, and publish what each
scope was left holding. Order every artifact as `/app/data/output_schema_reference.md`
and the Published section of each stage specification require, use the delimiter each
format takes, write one header row on every delimited artifact, sort json keys at every
level, and end every file with exactly one line feed and no carriage returns.

Resolve every closed vocabulary against `/app/data/deferral_reason_reference.txt`,
`/app/data/correction_reason_reference.txt` and `/app/data/snap_side_reference.txt`, and
publish only members of those vocabularies. Treat
`/app/data/legacy_commission_table.csv`, `/app/data/blackout_overlay_drafts.xml` and
`/app/data/prior_conform_register.csv` as the rejected sources that
`/app/data/data_lineage.md` says they are, consuming the last of the three only where the
reconciliation stage reports against it.

Work inside `/app`, leave `/app/data` unmodified, and use the Python standard library
alone, since the system Python carries no third-party package and none is needed. Every
identifier and every value in the corpus is specific to this channel, so the day has to be
derived from the records under `/app/data`. You have 14400 seconds to complete this task.
