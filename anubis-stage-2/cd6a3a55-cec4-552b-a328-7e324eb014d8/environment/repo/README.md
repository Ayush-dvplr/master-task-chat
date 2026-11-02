# helios-close

The close program of the Helios model-training dependency programme. It reads the exports of a quarter close and writes all logical layers
of the close in one atomic run; the rules it implements are written in the close contract that ships with the exports (close_contract.md) and
in the documents that contract names.

Layout:

- `src/helios_close/`: the program, one module per concern (cell decoding, record layer, close rules, ledger, stages 2 and 3,
  command line).
- `tools/amalgamate.py`: writes the program as one self-contained file (`python3 tools/amalgamate.py OUT_FILE`).
- `tests/test_visible.py`: unit tests (`PYTHONPATH=src python3 -m unittest discover -s tests`).

Command line (also of the amalgamated file):

    python3 -m helios_close.cli DATA_DIR OUT_DIR

Status: the Q3 dry run disagreed with the published control figures and with the security review board's spot checks, so
the implementation is known to be wrong in places. The contract is the authority.
