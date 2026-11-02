The Thornvale land board apportions its district levy with an engine that has been retired. Its source code and its rule book are lost. What survives is the board's archive: past exports, each stored next to the ledger the retired engine printed for it. Your job is to rebuild the engine so that it prints the same ledger for any export the board produces.

An export is a directory of survey books (files ending in `.svy`) plus five policy tables: `datums.json`, `land_use.json`, `regions.json`, `policy.json` and `quality.json`. The archive lives in `/app/data/archive`; each folder there, such as `/app/data/archive/export-01`, holds one export and a `ledger` folder with the nine reports the retired engine wrote for it. The export the board needs today is `/app/data/current`. It has no ledger.

Nothing explains the rules. You have to recover them from the archive: how books, records, revisions and voids are read and reconciled, how datum transforms apply, which records are quarantined and under which code, how parcels are measured, how overlapping parcels share land, how parcels fall into districts, how the ruleset in force is chosen, how seats are awarded and how the levy is split into cents. Every rule the retired engine applied shows up somewhere in the archive, but no single export shows all of them, and the current export shows fewer still.

Write the engine as `/app/out/derive_report.py`, run as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`. It reads the export in `DATA_DIR`, creates `OUT_DIR` if it is missing, and writes the nine reports there under the same names the ledgers use. Run it on the current export so that these files exist:

- `/app/out/summary.json`
- `/app/out/policy_audit.json`
- `/app/out/data_quality.json`
- `/app/out/region_North.json`
- `/app/out/region_South.json`
- `/app/out/region_West.json`
- `/app/out/region_East.json`
- `/app/out/segment_commercial.json`
- `/app/out/segment_public.json`

A report matches a ledger when it parses to the same JSON value: key order and whitespace do not matter, but every value, every list order and every type does. The ledgers print exact rationals as strings in lowest terms, so binary floating point anywhere on the path to a reported number will produce a wrong ledger.

Rules for the whole session:

- Treat `/app/data` as read only.
- Work with the tools already installed; package installation is off limits.
- Keep scratch files under `/tmp`; the only place under `/app` where you create files is `/app/out`.

Rules for the engine:

- Use only the Python standard library.
- Write nothing outside `OUT_DIR`.
- Read every value from the export at run time. Nothing from the current export or the archive may be hardcoded. The engine may read only export inputs and policy tables within the supplied `DATA_DIR`; it must ignore any `ledger` subtree and must not discover sibling archive exports on its own. Validation may invoke the same engine with an archive export directory as `DATA_DIR`.
- The board's future exports differ from everything in the archive: other books, datums, land uses, district order, rulesets and quality precedence, and they combine every rule the archive shows, including spellings and layouts of book lines that appear only in some archive exports.
- Book file names are random. Renaming a book file must not change a byte of the output.
- Output must be byte identical across runs and Python hash seeds.
- Future exports hold a market square built like the small ones in the archive but far larger: about sixteen hundred overlapping stall claims from every book. An export of a dozen books with such a market must finish within 60 seconds on one core.

Do not look up the board's ledgers or any solution online; everything needed is in `/app/data`.

You have 14400 seconds to complete this task. When you finish, reply with a short note naming the ruleset in force for the current export and the seat count of each district.
