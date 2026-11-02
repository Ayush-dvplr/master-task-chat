# pagerecover

Restart recovery for counter pages that live behind a write-ahead journal.

    python -m pagerecover recover --data DIR --out DIR

reads the recovery inputs of one book from `DIR` and writes the four
recovery documents (`module_core.json`, `module_metrics.json`,
`dependency_resolution.json`, `summary.json`) into the output directory.

Modules:

- `loader.py` reads the journal, the disk image, the page map, the master
  records, the transaction catalog and the audit queries.
- `pages.py` decodes `disk_pages.bin`.
- `recovery.py` validates one crash image and recovers it.
- `reports.py` turns recovered images into the four documents.

Run the tests with `python -m unittest discover -s tests -v`.
