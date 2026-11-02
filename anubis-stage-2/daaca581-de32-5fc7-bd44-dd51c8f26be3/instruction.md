KVEC's November 2025 settlement run never completed. The meter data management team has handed you the raw export directory `/app/data`: about a hundred files from six meter head-end systems, the MDM registers, substation SCADA, tariff books, account and lighting records, mailbox and log exports, and the documents that govern them. Several sources disagree with each other, some files are drafts, previews, resends or presentation copies, and the cooperative's rules decide which source wins. The computation and the exact deliverable formats are defined in `/app/data/settlement_data_contract.md`; authority and precedence between sources are defined in the settlement procedures manual it names; each head-end profile defines how its export is parsed. Work out from the material itself which files feed which figure.

Deliver a reusable settlement program at `/app/out/transform.py`. Keep the whole program inside that one file: it has to run on its own, without importing any other file you write. It must run as

```bash
python3 /app/out/transform.py <DATA_DIR> <OUT_DIR>
```

and write all nine deliverables into `OUT_DIR` (creating it when it does not exist yet) from the files in `DATA_DIR` alone, so that the same code settles a directory it has never seen that follows the same documented rules. Then run it on this directory so that these files exist:

- `/app/out/account_settlement.csv`
- `/app/out/meter_summary.csv`
- `/app/out/read_resolution.csv`
- `/app/out/interval_injection.csv`
- `/app/out/lighting_deemed.csv`
- `/app/out/daytype_calendar.csv`
- `/app/out/feeder_balance.json`
- `/app/out/control_report.json`
- `/app/out/settlement_summary.json`

Write every deliverable under /app/out exactly as named, in the formats section 9 of the contract defines. Your deliverables are compared byte for byte with the output the contract defines, both for this directory and for the output of your program on a freshly generated directory that uses the same file names and documented rules but different identifiers, values and data defects. Each run of your program on such a directory must finish within 1500 seconds. Every settlement figure is coupled to the system-wide unaccounted-for energy reconciliation, so a single misread record anywhere changes the totals and every account row that carries them; rows and figures only count when they are exact.

The program must read nothing outside its DATA_DIR argument, must write nothing outside its OUT_DIR argument, and must produce identical bytes every time it runs on the same input. Use Python 3.12 with its standard library and the preinstalled openpyxl, python-docx, pypdf, pdfplumber, pyarrow, lxml, PyYAML and icalendar packages; there is no network, and anything else you install will not exist at grading time. Do not install packages or try to download anything. Do not edit or delete anything under `/app/data`.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
