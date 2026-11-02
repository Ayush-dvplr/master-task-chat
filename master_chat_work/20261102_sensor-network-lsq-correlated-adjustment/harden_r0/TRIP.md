# TRIP 868afdf sensor-network-lsq-correlated-adjustment (R0 lever)

- Start 2026-11-02 18:37 IST. Session renamed (opencode ses_e63a0c69fffeZQhOSx2TQ1Rp2p).
- BUNDLE tree sha 376ab407134e (before any edit). Live QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271.
- Paid run: Output_RFP/.../claude-opus-5/run_1, P = artifacts/app/out/derive_report.py (914 lines, sha 68c82e495ad5).
  Registry: tests 100, rubric 75 (R1-R5, R9 pass; R10, R11 fail), overall 87.5.

## Paid trajectory (44 steps, about 14 min, $3.79)
- Steps 2-20 read schema.md and every data file with head/sed/awk; step 18 parses shards with split.
- Step 21/23 first write of derive_report.py; step 33 only edit (read_workbook); runs at 24, 34, 39.
- Step 34 reruns into a fresh dir and diffs (reproducibility). Every run uses the shipped extract.
- Never builds a modified or larger extract, never reads a shard with the csv module, never quotes a field.

## Confirmed lines
- P reader: read_table P:77-94, line.split(delim) at P:86, cells stripped P:88/P:92, no quote handling.
  load_shard_rows P:240-266 (read_table at P:264 for CSV/TSV/PSV shards).
- P core: kind P:313-315 (factors[(unit, quantity)] lookup), value P:317-318, dir test
  `.strip().upper() == "R"` P:320-322, sigma branch `row["sigma_kind"].strip() == "stddev"` P:328-332.
- O: solution/solve.py table_rows solve.py:76-80 (csv.DictReader after dropping # lines);
  variance branch solve.py:262.
- T: tests/test_output.py read_delimited 2162-2177 (csv.DictReader, row["sigma_kind"] at 2174).
- Generator: write_csv test_output.py:606-617 (csv.writer QUOTE_MINIMAL) used only by
  emit_source_shards 1167-1191 (csv 1180, tsv 1182, psv 1185). emit_corpus 2035 writes SCHEMA_MD
  (constant in tests) to schema.md, so a schema sentence goes in both places.

## Card check
- Card premise "shipped rows use stddev" holds for the shipped extract, but the hidden plans differ:
  challenge and eval north.csv hold variance, south.tsv stddev (test_output.py:981-986, 1012-1017);
  audit north.csv holds stddev (1032-1037). So the literal carrier (sigma_kind quoted in CSV only)
  reaches audit only: measured 23/86, below the 35/86 bar.
- Redesign (once): quote fields of the hidden CSV shard generally (RFC 4180), not one field.
  Measured below in DESIGN.md.
