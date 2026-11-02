The archive `/app/data/tool.zip` holds `dpcc`, a small Python command-line tool that compiles the layered configuration of a catalog of data products. The tool is broken. Extract it to `/app/tool`, repair it, and use the repaired tool to compile the release described by the input files in `/app/data`.

What the tool must do is written in `/app/data/config_contract.md`: its commands, its error lines, how each input file is read, how the layers combine, and the exact shape of every output document. That contract is the behaviour of record. Where the tool's code, its README or your own expectation of such a tool says something else, the contract wins.

Produce these files with the repaired tool, not by hand:

- `/app/out/config.json`
- `/app/out/profile_dev.json`
- `/app/out/profile_prod.json`
- `/app/out/validation_report.json`
- `/app/out/summary.json`
- `/app/out/report.json`

Then deliver the repaired tool as `/app/out/tool.zip`, with `cli.py` at the root of the archive next to the modules it imports. The delivered archive is the tool that counts: it must compile other releases on its own, at other scales, from any working directory and any data folder, exactly as the contract says. Each output document must match the contract whole and exactly, on these files and on fresh data of the same kind.

Before you finish, check your work. Work out the expected figures of the documents from the contract and the input files on your own, outside the tool, and compare them with what the tool wrote. Run the tool from the delivered archive after your last change. In your final message, list every file you wrote under `/app/out`.

Use only the Python standard library and the files provided. Treat `/app/data` as read-only.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
